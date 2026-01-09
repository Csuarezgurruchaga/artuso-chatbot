import base64
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

from services.expensas_sheet_service import EXPENSAS_SPREADSHEET_ID

logger = logging.getLogger(__name__)

RATE_LIMIT_SHEET_NAME = "RATE_LIMIT"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


class RateLimitService:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"
        self._gc = None
        self._last_auth_ts = 0
        self._auth_ttl = 60 * 30

    def _load_credentials(self):
        sa_raw = os.getenv("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON", "").strip()
        if not sa_raw:
            raise ValueError("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON is required for RATE_LIMIT")
        if sa_raw.startswith("{"):
            info = json.loads(sa_raw)
        else:
            decoded = base64.b64decode(sa_raw)
            info = json.loads(decoded)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    def _get_client(self):
        if not self.enabled:
            raise RuntimeError("RateLimitService disabled")
        if gspread is None or Credentials is None:
            raise RuntimeError("gspread/google-auth not installed")
        now = datetime.utcnow().timestamp()
        if self._gc and now - self._last_auth_ts < self._auth_ttl:
            return self._gc
        creds = self._load_credentials()
        self._gc = gspread.authorize(creds)
        self._last_auth_ts = now
        return self._gc

    def _get_sheet(self):
        gc = self._get_client()
        sh = gc.open_by_key(EXPENSAS_SPREADSHEET_ID)
        return sh.worksheet(RATE_LIMIT_SHEET_NAME)

    @staticmethod
    def _today_key() -> str:
        return datetime.now(AR_TZ).date().isoformat()

    @staticmethod
    def _parse_int(value: str) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    def _find_row(self, ws, telefono: str, date_key: str) -> Tuple[Optional[int], Optional[list]]:
        rows = ws.get_all_values()
        if not rows:
            return None, None
        start_idx = 0
        header = rows[0][0].strip().lower() if rows[0] else ""
        if header in {"phone", "telefono"}:
            start_idx = 1
        for idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
            if not row or len(row) < 2:
                continue
            if row[0].strip() == telefono and row[1].strip() == date_key:
                return idx, row
        return None, None

    def check_and_increment(self, telefono: str, limit: int = 20) -> Tuple[bool, int, str]:
        date_key = self._today_key()
        if not self.enabled:
            return True, 0, date_key
        try:
            ws = self._get_sheet()
            row_idx, row = self._find_row(ws, telefono, date_key)
            updated_at = datetime.utcnow().isoformat()
            if row_idx:
                count = self._parse_int(row[2]) if len(row) > 2 else 0
                if count >= limit:
                    return False, count, date_key
                count += 1
                ws.update(
                    f"A{row_idx}:D{row_idx}",
                    [[telefono, date_key, str(count), updated_at]],
                    value_input_option="RAW",
                )
                return True, count, date_key
            ws.append_row(
                [telefono, date_key, "1", updated_at],
                value_input_option="RAW",
            )
            return True, 1, date_key
        except Exception as exc:
            logger.error("rate_limit_error phone=%s error=%s", telefono, str(exc))
            return True, 0, date_key


rate_limit_service = RateLimitService()
