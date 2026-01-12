import base64
import json
import logging
import os
import time
from datetime import date, datetime
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

from services.expensas_sheet_service import (
    EXPENSAS_SCOPES,
    EXPENSAS_SHEET_NAME,
    EXPENSAS_SPREADSHEET_ID,
)

logger = logging.getLogger(__name__)

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
INVALID_DATE_NOTE = "Fecha invalida"


class ExpensasPurgeService:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"
        self._gc = None
        self._last_auth_ts = 0.0
        self._auth_ttl = 60 * 30

    @staticmethod
    def _normalize_header(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(value.strip(), "%d/%m/%Y").date()
        except ValueError:
            return None

    @staticmethod
    def _previous_month(year: int, month: int) -> Tuple[int, int]:
        if month == 1:
            return year - 1, 12
        return year, month - 1

    @staticmethod
    def _retention_months(now_date: date) -> Set[Tuple[int, int]]:
        return {(now_date.year, now_date.month)}

    @staticmethod
    def _select_date(fecha_aviso: str, fecha_pago: str) -> Optional[date]:
        parsed_aviso = ExpensasPurgeService._parse_date(fecha_aviso)
        if parsed_aviso is not None:
            return parsed_aviso
        return ExpensasPurgeService._parse_date(fecha_pago)

    @staticmethod
    def _append_invalid_comment(existing: str) -> str:
        existing = (existing or "").strip()
        note_lower = INVALID_DATE_NOTE.lower()
        if existing and note_lower in existing.lower():
            return existing
        if existing:
            return f"{existing} | {INVALID_DATE_NOTE}"
        return INVALID_DATE_NOTE

    @staticmethod
    def _should_keep_date(
        selected_date: date,
        now_date: date,
        retention_months: Set[Tuple[int, int]],
    ) -> bool:
        if selected_date > now_date:
            return True
        return (selected_date.year, selected_date.month) in retention_months

    @staticmethod
    def _col_to_a1(col: int) -> str:
        result = ""
        while col:
            col, rem = divmod(col - 1, 26)
            result = chr(65 + rem) + result
        return result

    def _load_credentials(self):
        sa_raw = os.getenv("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON", "").strip()
        if not sa_raw:
            raise ValueError("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON is required for ExpensasPurgeService")
        try:
            if sa_raw.startswith("{"):
                info = json.loads(sa_raw)
            else:
                decoded = base64.b64decode(sa_raw)
                info = json.loads(decoded)
            return Credentials.from_service_account_info(info, scopes=EXPENSAS_SCOPES)
        except Exception as exc:
            raise ValueError(f"Invalid GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON: {str(exc)}")

    def _get_client(self):
        now = time.time()
        if self._gc and now - self._last_auth_ts < self._auth_ttl:
            return self._gc
        if gspread is None or Credentials is None:
            raise RuntimeError("gspread/google-auth not installed")
        creds = self._load_credentials()
        self._gc = gspread.authorize(creds)
        self._last_auth_ts = now
        return self._gc

    def _get_sheet(self):
        gc = self._get_client()
        sh = gc.open_by_key(EXPENSAS_SPREADSHEET_ID)
        return sh.worksheet(EXPENSAS_SHEET_NAME)

    def purge_old_rows(self) -> dict:
        if not self.enabled:
            logger.info("Expensas purge skipped (ENABLE_EXPENSAS_SHEET=false)")
            return {
                "scanned": 0,
                "deleted": 0,
                "kept": 0,
                "invalid": 0,
                "disabled": True,
            }

        ws = self._get_sheet()
        rows = ws.get_all_values()
        if not rows or not rows[0]:
            raise ValueError("Missing header row in chatbot-expensas sheet")

        header = rows[0]
        header_map = {
            self._normalize_header(value): idx
            for idx, value in enumerate(header)
            if value.strip()
        }

        required_headers = {
            "fecha aviso": "FECHA AVISO",
            "fecha de pago": "FECHA DE PAGO",
            "comentario": "COMENTARIO",
        }
        missing = [
            original
            for key, original in required_headers.items()
            if key not in header_map
        ]
        if missing:
            raise ValueError(f"Missing required headers: {', '.join(missing)}")

        idx_aviso = header_map["fecha aviso"]
        idx_pago = header_map["fecha de pago"]
        idx_comment = header_map["comentario"]

        now_date = datetime.now(AR_TZ).date()
        retention_months = self._retention_months(now_date)
        months_label = sorted(retention_months)

        delete_indices: List[int] = []
        comment_updates: List[Tuple[int, str]] = []
        invalid_count = 0
        kept_count = 0

        for offset, row in enumerate(rows[1:], start=2):
            fecha_aviso = row[idx_aviso] if idx_aviso < len(row) else ""
            fecha_pago = row[idx_pago] if idx_pago < len(row) else ""
            selected_date = self._select_date(fecha_aviso, fecha_pago)

            if selected_date is None:
                invalid_count += 1
                kept_count += 1
                existing_comment = row[idx_comment] if idx_comment < len(row) else ""
                new_comment = self._append_invalid_comment(existing_comment)
                if new_comment != (existing_comment or ""):
                    comment_updates.append((offset, new_comment))
                continue

            if self._should_keep_date(selected_date, now_date, retention_months):
                kept_count += 1
                continue

            delete_indices.append(offset)

        if comment_updates:
            comment_col = idx_comment + 1
            comment_col_letter = self._col_to_a1(comment_col)
            for row_idx, new_comment in comment_updates:
                ws.update(
                    f"{comment_col_letter}{row_idx}",
                    [[new_comment]],
                    value_input_option="RAW",
                )

        deleted_count = len(delete_indices)
        if delete_indices:
            for start, end in self._group_delete_ranges(delete_indices):
                ws.delete_rows(start, end)

        summary = {
            "scanned": max(len(rows) - 1, 0),
            "deleted": deleted_count,
            "kept": kept_count,
            "invalid": invalid_count,
            "months": months_label,
        }
        logger.info(
            "Expensas purge summary: scanned=%s deleted=%s kept=%s invalid=%s months=%s",
            summary["scanned"],
            summary["deleted"],
            summary["kept"],
            summary["invalid"],
            summary["months"],
        )
        return summary

    @staticmethod
    def _group_delete_ranges(indices: Sequence[int]) -> Iterable[Tuple[int, int]]:
        if not indices:
            return []
        sorted_indices = sorted(indices, reverse=True)
        ranges: List[Tuple[int, int]] = []
        start = end = sorted_indices[0]
        for idx in sorted_indices[1:]:
            if idx == end - 1:
                end = idx
            else:
                ranges.append((end, start))
                start = end = idx
        ranges.append((end, start))
        return ranges


expensas_purge_service = ExpensasPurgeService()
