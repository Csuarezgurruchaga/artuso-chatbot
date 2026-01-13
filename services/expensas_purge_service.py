import base64
import json
import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

from services.expensas_sheet_service import (
    EXPENSAS_CURRENT_SHEET_NAME,
    EXPENSAS_DEFAULT_ROWS,
    EXPENSAS_HEADERS,
    EXPENSAS_PREVIOUS_SHEET_NAME,
    EXPENSAS_SCOPES,
    EXPENSAS_SPREADSHEET_ID,
    apply_expensas_title_and_headers,
    build_expensas_title,
    previous_month_date,
)

logger = logging.getLogger(__name__)

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


class ExpensasPurgeService:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"
        self._gc = None
        self._last_auth_ts = 0.0
        self._auth_ttl = 60 * 30

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

    def _get_spreadsheet(self):
        gc = self._get_client()
        return gc.open_by_key(EXPENSAS_SPREADSHEET_ID)

    @staticmethod
    def _count_data_rows(ws) -> int:
        values = ws.get_all_values()
        if not values:
            return 0
        return max(len(values) - 2, 0)

    def _get_sheet_if_exists(self, sh, title: str):
        try:
            return sh.worksheet(title)
        except Exception as exc:
            if gspread is None:
                raise
            if isinstance(exc, gspread.exceptions.WorksheetNotFound):
                return None
            raise

    def _create_sheet(self, sh, title: str):
        return sh.add_worksheet(
            title=title,
            rows=EXPENSAS_DEFAULT_ROWS,
            cols=len(EXPENSAS_HEADERS),
        )

    def rotate_monthly(self) -> dict:
        if not self.enabled:
            logger.info("Expensas rotation skipped (ENABLE_EXPENSAS_SHEET=false)")
            return {
                "moved": 0,
                "cleared": 0,
                "disabled": True,
            }

        sh = self._get_spreadsheet()
        now_date = datetime.now(AR_TZ).date()
        previous_date = previous_month_date(now_date)
        current_title = build_expensas_title(EXPENSAS_CURRENT_SHEET_NAME, now_date)
        previous_title = build_expensas_title(EXPENSAS_PREVIOUS_SHEET_NAME, previous_date)

        current_ws = self._get_sheet_if_exists(sh, EXPENSAS_CURRENT_SHEET_NAME)
        previous_ws = self._get_sheet_if_exists(sh, EXPENSAS_PREVIOUS_SHEET_NAME)

        moved_rows = self._count_data_rows(current_ws) if current_ws else 0
        cleared_rows = self._count_data_rows(previous_ws) if previous_ws else 0

        if previous_ws is not None:
            sh.del_worksheet(previous_ws)

        if current_ws is None:
            current_ws = self._create_sheet(sh, EXPENSAS_CURRENT_SHEET_NAME)
            apply_expensas_title_and_headers(current_ws, current_title)

        current_ws.update_title(EXPENSAS_PREVIOUS_SHEET_NAME)
        apply_expensas_title_and_headers(current_ws, previous_title)

        new_current_ws = self._create_sheet(sh, EXPENSAS_CURRENT_SHEET_NAME)
        apply_expensas_title_and_headers(new_current_ws, current_title)

        summary = {
            "moved": moved_rows,
            "cleared": cleared_rows,
            "current_tab": EXPENSAS_CURRENT_SHEET_NAME,
            "previous_tab": EXPENSAS_PREVIOUS_SHEET_NAME,
            "current_label": current_title,
            "previous_label": previous_title,
        }
        logger.info(
            "Expensas rotation summary: moved=%s cleared=%s current=%s previous=%s labels=%s/%s",
            summary["moved"],
            summary["cleared"],
            summary["current_tab"],
            summary["previous_tab"],
            summary["current_label"],
            summary["previous_label"],
        )
        return summary

    def purge_old_rows(self) -> dict:
        return self.rotate_monthly()


expensas_purge_service = ExpensasPurgeService()
