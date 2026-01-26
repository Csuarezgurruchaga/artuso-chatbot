import base64
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

gspread = None
Credentials = None

from services.expensas_sheet_service import EXPENSAS_SPREADSHEET_ID

logger = logging.getLogger(__name__)

CLIENTS_SHEET_NAME = os.getenv("EXPENSAS_CLIENTS_SHEET_NAME", "CLIENTES").strip()
MAX_DIRECCIONES = 5
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


class ClientsSheetService:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"
        self._gc = None
        self._last_auth_ts = 0
        self._auth_ttl = 60 * 30

    def _load_credentials(self):
        sa_raw = os.getenv("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON", "").strip()
        if not sa_raw:
            raise ValueError("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON is required for CLIENTES")
        if sa_raw.startswith("{"):
            info = json.loads(sa_raw)
        else:
            decoded = base64.b64decode(sa_raw)
            info = json.loads(decoded)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    def _get_client(self):
        global gspread, Credentials
        if not self.enabled:
            raise RuntimeError("ClientsSheetService disabled")
        if gspread is None or Credentials is None:
            try:
                import gspread as _gspread
                from google.oauth2.service_account import Credentials as _Credentials
            except Exception as exc:
                raise RuntimeError("gspread/google-auth not installed") from exc
            gspread = _gspread
            Credentials = _Credentials
        now = datetime.now(timezone.utc).timestamp()
        if self._gc and now - self._last_auth_ts < self._auth_ttl:
            return self._gc
        creds = self._load_credentials()
        self._gc = gspread.authorize(creds)
        self._last_auth_ts = now
        return self._gc

    def _get_sheet(self):
        gc = self._get_client()
        sh = gc.open_by_key(EXPENSAS_SPREADSHEET_ID)
        return sh.worksheet(CLIENTS_SHEET_NAME)

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", text.lower().strip())
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _sort_direcciones(direcciones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def _key(item: Dict[str, Any]) -> str:
            value = item.get("last_used") or item.get("created_at") or ""
            return str(value)

        return sorted(direcciones, key=_key, reverse=True)

    @classmethod
    def _address_key(cls, direccion: str, piso: str) -> str:
        return f"{cls._normalize_text(direccion)}|{cls._normalize_text(piso)}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _find_row(self, ws, telefono: str) -> Tuple[Optional[int], Optional[List[str]]]:
        rows = ws.get_all_values()
        if not rows:
            return None, None
        start_idx = 0
        header = rows[0][0].strip().lower() if rows[0] else ""
        if header == "telefono":
            start_idx = 1
        for idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
            if row and row[0].strip() == telefono:
                return idx, row
        return None, None

    def get_direcciones(self, telefono: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            ws = self._get_sheet()
            _, row = self._find_row(ws, telefono)
            if not row or len(row) < 2 or not row[1].strip():
                return []
            try:
                parsed = json.loads(row[1])
                if not isinstance(parsed, list):
                    return []
                return self._sort_direcciones(parsed)
            except json.JSONDecodeError:
                logger.error("CLIENTES JSON invalido para telefono=%s", telefono)
                return []
        except Exception as exc:
            logger.error("Error leyendo CLIENTES telefono=%s error=%s", telefono, str(exc))
            return []

    def _save_direcciones(self, telefono: str, direcciones: List[Dict[str, Any]]) -> bool:
        if not self.enabled:
            return False
        try:
            ws = self._get_sheet()
            row_idx, _ = self._find_row(ws, telefono)
            updated_at = self._now_iso()
            direcciones_sorted = self._sort_direcciones(direcciones or [])
            payload = [
                telefono,
                json.dumps(direcciones_sorted, ensure_ascii=True),
                updated_at,
            ]
            if row_idx:
                ws.update(f"A{row_idx}:C{row_idx}", [payload], value_input_option="RAW")
            else:
                ws.append_row(payload, value_input_option="RAW")
            return True
        except Exception as exc:
            logger.error("Error guardando CLIENTES telefono=%s error=%s", telefono, str(exc))
            return False

    def update_last_used(self, telefono: str, direccion: str, piso: str) -> bool:
        direcciones = self.get_direcciones(telefono)
        if not direcciones:
            return False
        key = self._address_key(direccion, piso)
        updated = False
        for item in direcciones:
            if self._address_key(item.get("direccion", ""), item.get("piso_depto", "")) == key:
                item["last_used"] = self._now_iso()
                updated = True
                break
        if not updated:
            return False
        return self._save_direcciones(telefono, direcciones)

    def remove_direccion(self, telefono: str, index: int) -> bool:
        direcciones = self.get_direcciones(telefono)
        if index < 0 or index >= len(direcciones):
            return False
        direcciones.pop(index)
        return self._save_direcciones(telefono, direcciones)

    def add_or_replace_direccion(self, telefono: str, direccion: str, piso: str) -> Tuple[bool, str]:
        direcciones = self.get_direcciones(telefono)
        key = self._address_key(direccion, piso)
        now_iso = self._now_iso()
        for item in direcciones:
            if self._address_key(item.get("direccion", ""), item.get("piso_depto", "")) == key:
                item["direccion"] = direccion
                item["piso_depto"] = piso
                item["last_used"] = now_iso
                if not item.get("created_at"):
                    item["created_at"] = now_iso
                saved = self._save_direcciones(telefono, direcciones)
                return saved, "replaced"
        if len(direcciones) >= MAX_DIRECCIONES:
            return False, "limit"
        direcciones.append(
            {
                "direccion": direccion,
                "piso_depto": piso,
                "created_at": now_iso,
                "last_used": now_iso,
            }
        )
        saved = self._save_direcciones(telefono, direcciones)
        return saved, "added"


clients_sheet_service = ClientsSheetService()
