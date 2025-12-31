import os
import json
import base64
import time
import logging
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

logger = logging.getLogger(__name__)

EXPENSAS_SPREADSHEET_ID = "1WTzQlPRp63HDyUfsCMI5HNFaCUn82SYeDksZGMkKXi4"
EXPENSAS_SHEET_NAME = "chatbot-expensas"
EXPENSAS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


class ExpensasSheetService:
    def __init__(self):
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"
        self._gc = None
        self._last_auth_ts = 0
        self._auth_ttl = 60 * 30

    def append_pago(self, conversacion) -> bool:
        if not self.enabled:
            logger.info("ExpensasSheetService disabled (ENABLE_EXPENSAS_SHEET=false)")
            return False

        datos = conversacion.datos_temporales or {}
        fecha_aviso = datetime.now().strftime("%d/%m/%Y")
        comentario = datos.get("comentario") or ""
        sa_raw = os.getenv("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON", "").strip()
        logger.info(
            "Expensas creds status: present=%s length=%s",
            bool(sa_raw),
            len(sa_raw) if sa_raw else 0,
        )

        logger.info(
            "Expensas append intento: phone=%s sheet=%s id=%s",
            conversacion.numero_telefono,
            EXPENSAS_SHEET_NAME,
            EXPENSAS_SPREADSHEET_ID,
        )

        row = [
            "ws",  # TIPO AVISO
            fecha_aviso,  # FECHA AVISO
            datos.get("fecha_pago", ""),  # FECHA DE PAGO
            datos.get("monto", ""),  # MONTO
            datos.get("direccion", ""),  # ED
            datos.get("piso_depto", ""),  # DPTO
            "",  # UF
            comentario,  # COMENTARIO
        ]

        try:
            gc = self._get_client()
            sh = gc.open_by_key(EXPENSAS_SPREADSHEET_ID)
            ws = sh.worksheet(EXPENSAS_SHEET_NAME)
            ws.append_row(row, value_input_option="RAW")
            logger.info("Expensas append OK para %s", conversacion.numero_telefono)
            return True
        except Exception as e:
            logger.exception(
                "Error guardando expensas en Sheets: %s (%s)",
                repr(e),
                type(e).__name__,
            )
            return False

    def _load_credentials(self):
        sa_raw = os.getenv("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON", "").strip()
        if not sa_raw:
            raise ValueError("GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON is required for ExpensasSheetService")
        try:
            if sa_raw.startswith("{"):
                info = json.loads(sa_raw)
            else:
                decoded = base64.b64decode(sa_raw)
                info = json.loads(decoded)
            return Credentials.from_service_account_info(info, scopes=EXPENSAS_SCOPES)
        except Exception as e:
            raise ValueError(f"Invalid GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON: {str(e)}")

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


expensas_sheet_service = ExpensasSheetService()
