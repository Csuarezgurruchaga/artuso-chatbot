import os
import re
import json
import base64
import time
import logging
import unicodedata
from datetime import datetime
from typing import Optional, Iterable, Tuple, Set, Any

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

from config.company_profiles import get_active_company_profile

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

    _LOCALIDAD_TOKENS = {
        "caba",
        "capital",
        "capital federal",
        "ciudad autonoma",
        "ciudad autonoma de buenos aires",
        "buenos aires",
        "provincia",
        "provincia de buenos aires",
        "gba",
        "bs as",
        "bs. as.",
    }

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

        direccion_ingresada = datos.get("direccion", "")
        direccion_mapeada = self._resolve_address_code(direccion_ingresada)
        direccion_salida = direccion_mapeada if direccion_mapeada is not None else direccion_ingresada

        row = [
            "ws",  # TIPO AVISO
            fecha_aviso,  # FECHA AVISO
            datos.get("fecha_pago", ""),  # FECHA DE PAGO
            datos.get("monto", ""),  # MONTO
            direccion_salida,  # ED
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

    @staticmethod
    def _normalize_address_text(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", text.lower().strip())
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        normalized = re.sub(r"[.,]", " ", normalized)
        normalized = re.sub(r"\bavda\.?\b", "avenida", normalized)
        normalized = re.sub(r"\bav\.?\b", "avenida", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _strip_localidad_tokens(self, text: str) -> str:
        if not text:
            return ""
        normalized = self._normalize_address_text(text)
        for token in sorted(self._LOCALIDAD_TOKENS, key=len, reverse=True):
            normalized = normalized.replace(f" {token} ", " ")
            if normalized.endswith(f" {token}"):
                normalized = normalized[: -len(token) - 1].strip()
            if normalized.startswith(f"{token} "):
                normalized = normalized[len(token) + 1 :].strip()
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _expand_slash_numbers(chunk: str) -> Iterable[int]:
        parts = [part for part in chunk.split("/") if part]
        if not parts or not parts[0].isdigit():
            return []
        base = parts[0]
        base_len = len(base)
        numbers = [int(base)]
        for part in parts[1:]:
            if not part.isdigit():
                continue
            if len(part) < base_len:
                prefix = base[: base_len - len(part)]
                numbers.append(int(prefix + part))
            else:
                numbers.append(int(part))
        return numbers

    def _extract_numbers_from_raw(self, raw: str) -> Tuple[str, Set[int]]:
        if not raw:
            return "", set()
        slash_match = re.search(r"\b(\d{1,5}(?:/\d{1,5})+)\b", raw)
        if slash_match:
            numbers = set(self._expand_slash_numbers(slash_match.group(1)))
            street_raw = (raw[: slash_match.start()] + raw[slash_match.end() :]).strip()
            return street_raw, numbers
        match = re.search(r"\b(\d{1,5})\b", raw)
        if match:
            street_raw = (raw[: match.start()] + raw[match.end() :]).strip()
            return street_raw, {int(match.group(1))}
        return raw, set()

    @staticmethod
    def _coerce_code(code: Any):
        try:
            return int(code)
        except Exception:
            return code

    def _resolve_address_code(self, direccion: str) -> Optional[Any]:
        try:
            profile = get_active_company_profile()
            address_map = profile.get("expensas_address_map", {})
        except Exception:
            return None

        if not direccion or not address_map:
            return None

        input_clean = self._strip_localidad_tokens(direccion)
        input_street_raw, input_numbers = self._extract_numbers_from_raw(input_clean)
        input_street_norm = self._normalize_address_text(input_street_raw)
        input_full_norm = self._normalize_address_text(input_clean)

        for code, raw_address in address_map.items():
            raw_str = str(raw_address)
            mapped_clean = self._strip_localidad_tokens(raw_str)
            mapped_street_raw, mapped_numbers = self._extract_numbers_from_raw(mapped_clean)
            mapped_street_norm = self._normalize_address_text(mapped_street_raw)
            mapped_full_norm = self._normalize_address_text(mapped_clean)

            if input_numbers and mapped_numbers and input_street_norm == mapped_street_norm:
                if any(num in mapped_numbers for num in input_numbers):
                    return self._coerce_code(code)

            if input_full_norm and input_full_norm == mapped_full_norm:
                return self._coerce_code(code)

        return None

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
