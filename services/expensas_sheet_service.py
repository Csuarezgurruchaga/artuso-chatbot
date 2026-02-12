import os
import re
import json
import base64
import time
import logging
import unicodedata
from datetime import datetime, date
from typing import Optional, Iterable, Tuple, Set, Any, List
from zoneinfo import ZoneInfo

gspread = None
Credentials = None

from config.company_profiles import get_active_company_profile

logger = logging.getLogger(__name__)

UF_PATTERN = re.compile(
    r"\b(?:U\.?\s*F\.?|UNIDAD(?:\s+FUNCIONAL)?)\s*(\d+)\b",
    re.IGNORECASE,
)
UF_VALUE_PATTERN = re.compile(
    r"\b(?:U\.?\s*F\.?|UNIDAD(?:\s+FUNCIONAL)?)\s*\d+\b",
    re.IGNORECASE,
)

EXPENSAS_SPREADSHEET_ID = os.getenv(
    "EXPENSAS_SPREADSHEET_ID",
    "1LYtHD-a9Ii8QaqLApr8P-7xKKncM-2h_C3i7D10LhSg",
)
EXPENSAS_CURRENT_SHEET_NAME = "PAGOS MES ACTUAL"
EXPENSAS_PREVIOUS_SHEET_NAME = "PAGOS MES ANTERIOR"
EXPENSAS_HEADERS = [
    "TIPO AVISO",
    "FECHA AVISO",
    "FECHA DE PAGO",
    "MONTO",
    "ED",
    "DPTO",
    "UF",
    "COMENTARIO",
    "COMPROBANTE",
]
EXPENSAS_COMPROBANTE_LABEL = "Ver comprobante"
EXPENSAS_DEFAULT_ROWS = 1000
EXPENSAS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
SPANISH_MONTH_ABBR = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def _column_letter(col_index: int) -> str:
    letters = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def previous_month_date(target_date: date) -> date:
    if target_date.month == 1:
        return date(target_date.year - 1, 12, 1)
    return date(target_date.year, target_date.month - 1, 1)


def build_expensas_title(tab_name: str, target_date: date) -> str:
    month_label = SPANISH_MONTH_ABBR.get(target_date.month)
    if not month_label:
        raise ValueError(f"Unsupported month index: {target_date.month}")
    return f"{tab_name} ({month_label} {target_date.year})"


def apply_expensas_title_and_headers(ws, title_text: str) -> None:
    header_count = len(EXPENSAS_HEADERS)
    end_col = _column_letter(header_count)
    title_range = f"A1:{end_col}1"
    header_range = f"A2:{end_col}2"

    ws.update("A1", [[title_text]], value_input_option="RAW")
    ws.update(header_range, [EXPENSAS_HEADERS], value_input_option="RAW")

    try:
        ws.merge_cells(title_range)
    except Exception as exc:
        logger.warning("Expensas title merge skipped: %s", exc)

    try:
        ws.format(
            title_range,
            {
                "horizontalAlignment": "CENTER",
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                },
                "backgroundColor": {"red": 0, "green": 0, "blue": 0},
            },
        )
    except Exception as exc:
        logger.warning("Expensas title format skipped: %s", exc)


class ExpensasSheetService:
    def __init__(self):
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"
        self._gc = None
        self._last_auth_ts = 0
        self._auth_ttl = 60 * 30

    @staticmethod
    def _parse_uf_from_dpto(dpto: str) -> Optional[str]:
        if not dpto:
            return None

        matches = UF_PATTERN.findall(str(dpto))
        numbers: List[int] = []
        for match in matches:
            try:
                value = int(match)
            except Exception:
                continue
            if value >= 1:
                numbers.append(value)

        if not numbers:
            return None

        parts = [f"UF {num}" for num in numbers]
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return f"{parts[0]} y {parts[1]}"
        return ", ".join(parts[:-1]) + f" y {parts[-1]}"

    @staticmethod
    def _strip_uf_from_dpto(dpto: str) -> str:
        if not dpto:
            return ""

        cleaned = UF_VALUE_PATTERN.sub(" ", str(dpto))
        cleaned = re.sub(r"\bY\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
        cleaned = re.sub(r"(,\s*){2,}", ", ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:/|-")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

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
            EXPENSAS_CURRENT_SHEET_NAME,
            EXPENSAS_SPREADSHEET_ID,
        )

        direccion_ingresada = datos.get("direccion", "")
        direccion_mapeada = self._resolve_address_code(direccion_ingresada)
        direccion_salida = direccion_mapeada if direccion_mapeada is not None else direccion_ingresada

        piso_depto_norm = self._normalize_piso_depto(datos.get("piso_depto", ""))

        comprobante_raw = datos.get("comprobante", "")
        comprobante_urls: List[str] = []
        if isinstance(comprobante_raw, list):
            comprobante_urls = [str(url).strip() for url in comprobante_raw if str(url).strip()]
            comprobante_value = "\n".join(comprobante_urls)
        else:
            comprobante_value = comprobante_raw or ""
            raw_str = str(comprobante_value).strip()
            if raw_str:
                comprobante_urls = [raw_str]
        row = [
            "ws",  # TIPO AVISO
            fecha_aviso,  # FECHA AVISO
            datos.get("fecha_pago", ""),  # FECHA DE PAGO
            datos.get("monto", ""),  # MONTO
            direccion_salida,  # ED
            piso_depto_norm,  # DPTO
            "",  # UF
            comentario,  # COMENTARIO
            comprobante_value,  # COMPROBANTE
        ]

        if not row[6]:
            uf_value = self._parse_uf_from_dpto(piso_depto_norm)
            if uf_value:
                row[6] = uf_value
                row[5] = self._strip_uf_from_dpto(piso_depto_norm)
                logger.info(
                    "Expensas UF autocompletada: phone=%s dpto_raw=%s dpto_clean=%s uf=%s",
                    conversacion.numero_telefono,
                    piso_depto_norm,
                    row[5],
                    uf_value,
                )

        try:
            gc = self._get_client()
            sh = gc.open_by_key(EXPENSAS_SPREADSHEET_ID)
            now_date = datetime.now(AR_TZ).date()
            previous_date = previous_month_date(now_date)
            current_title = build_expensas_title(EXPENSAS_CURRENT_SHEET_NAME, now_date)
            previous_title = build_expensas_title(EXPENSAS_PREVIOUS_SHEET_NAME, previous_date)

            ws = self._ensure_tab(sh, EXPENSAS_CURRENT_SHEET_NAME, current_title)
            self._ensure_tab(sh, EXPENSAS_PREVIOUS_SHEET_NAME, previous_title)
            resp = ws.append_row(row, value_input_option="RAW")
            self._update_comprobante_links(
                ws,
                resp,
                col_index=len(EXPENSAS_HEADERS),
                urls=comprobante_urls,
            )
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
        normalized = re.sub(r"\bsantafe\b", "santa fe", normalized)
        normalized = re.sub(r"\bavda\.?\b", "avenida", normalized)
        normalized = re.sub(r"\bav\.?\b", "avenida", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _strip_avenida_prefix(normalized: str) -> str:
        if not normalized:
            return ""
        normalized = normalized.strip()
        normalized = re.sub(r"^avenida\s+", "", normalized).strip()
        return normalized

    @staticmethod
    def _street_token_set(normalized: str) -> Set[str]:
        if not normalized:
            return set()
        stopwords = {"de", "del", "la", "el", "los", "las"}
        tokens = [token for token in normalized.split() if token]
        return {token for token in tokens if token not in stopwords}

    @staticmethod
    def _normalize_piso_depto(text: str) -> str:
        if not text:
            return ""
        normalized = re.sub(r"\s+", " ", text.strip())
        return normalized.upper()

    @staticmethod
    def _column_letter(col_index: int) -> str:
        return _column_letter(col_index)

    @staticmethod
    def _filter_valid_comprobante_urls(urls: List[str]) -> List[str]:
        safe_urls = [str(url).strip() for url in urls if str(url).strip()]
        return [
            url
            for url in safe_urls
            if url.startswith("http://") or url.startswith("https://")
        ]

    @classmethod
    def _build_multi_comprobante_rich_text(cls, urls: List[str]) -> Tuple[str, List[dict]]:
        safe_urls = cls._filter_valid_comprobante_urls(urls)
        if not safe_urls:
            return "", []

        lines: List[str] = []
        runs: List[dict] = []
        cursor = 0
        for idx, url in enumerate(safe_urls, start=1):
            label = f"{EXPENSAS_COMPROBANTE_LABEL} {idx}"
            lines.append(label)
            runs.append(
                {
                    "startIndex": cursor,
                    "format": {"link": {"uri": url}},
                }
            )
            cursor += len(label)
            if idx < len(safe_urls):
                cursor += 1  # newline separator

        return "\n".join(lines), runs

    def _get_or_create_tab(self, sh, tab_name: str):
        try:
            return sh.worksheet(tab_name)
        except Exception as exc:
            if gspread is None:
                raise
            if isinstance(exc, gspread.exceptions.WorksheetNotFound):
                return sh.add_worksheet(
                    title=tab_name,
                    rows=EXPENSAS_DEFAULT_ROWS,
                    cols=len(EXPENSAS_HEADERS),
                )
            raise

    def _ensure_tab(self, sh, tab_name: str, title_text: str):
        ws = self._get_or_create_tab(sh, tab_name)
        apply_expensas_title_and_headers(ws, title_text)
        return ws

    @staticmethod
    def _escape_sheet_string(value: str) -> str:
        return value.replace('"', '""')

    @classmethod
    def _build_comprobante_hyperlink_formula(cls, urls: List[str]) -> str:
        safe_urls = cls._filter_valid_comprobante_urls(urls)
        if not safe_urls:
            return ""
        if len(safe_urls) == 1:
            url = cls._escape_sheet_string(safe_urls[0])
            label = cls._escape_sheet_string(EXPENSAS_COMPROBANTE_LABEL)
            return f'=HYPERLINK("{url}";"{label}")'
        # Para múltiples comprobantes evitamos fórmulas concatenadas de HYPERLINK.
        # El renderizado se resuelve en _update_comprobante_links con rich text.
        return ""

    def _update_comprobante_links(self, ws, resp, col_index: int, urls: List[str]) -> None:
        try:
            safe_urls = self._filter_valid_comprobante_urls(urls)
            if not safe_urls:
                return

            updated_range = resp.get("updates", {}).get("updatedRange", "")
            match = re.search(r"!([A-Z]+)(\d+)", updated_range)
            if not match:
                logger.error("No se pudo determinar la fila para comprobante: %s", updated_range)
                return
            row_index = int(match.group(2))
            col_letter = self._column_letter(col_index)
            cell_range = f"{col_letter}{row_index}"

            if len(safe_urls) > 1:
                # Usamos rich text para tener varias etiquetas clickeables en una sola celda.
                display_text, runs = self._build_multi_comprobante_rich_text(safe_urls)
                if not display_text or not runs:
                    return
                ws.spreadsheet.batch_update(
                    {
                        "requests": [
                            {
                                "updateCells": {
                                    "range": {
                                        "sheetId": ws.id,
                                        "startRowIndex": row_index - 1,
                                        "endRowIndex": row_index,
                                        "startColumnIndex": col_index - 1,
                                        "endColumnIndex": col_index,
                                    },
                                    "rows": [
                                        {
                                            "values": [
                                                {
                                                    "userEnteredValue": {"stringValue": display_text},
                                                    "textFormatRuns": runs,
                                                }
                                            ]
                                        }
                                    ],
                                    "fields": "userEnteredValue,textFormatRuns",
                                }
                            }
                        ]
                    }
                )
                return

            formula = self._build_comprobante_hyperlink_formula(urls)
            if not formula:
                return
            ws.update(
                [[formula]],
                range_name=cell_range,
                value_input_option="USER_ENTERED",
            )
        except Exception as e:
            logger.error("Error actualizando link de comprobante: %s", str(e))

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
        input_street_norm_wo_avenida = self._strip_avenida_prefix(input_street_norm)
        input_full_norm_wo_avenida = self._strip_avenida_prefix(input_full_norm)

        for code, raw_address in address_map.items():
            candidates = raw_address if isinstance(raw_address, (list, tuple, set)) else [raw_address]
            for candidate in candidates:
                raw_str = str(candidate).strip()
                if not raw_str:
                    continue

                mapped_clean = self._strip_localidad_tokens(raw_str)
                mapped_street_raw, mapped_numbers = self._extract_numbers_from_raw(mapped_clean)
                mapped_street_norm = self._normalize_address_text(mapped_street_raw)
                mapped_full_norm = self._normalize_address_text(mapped_clean)
                mapped_street_norm_wo_avenida = self._strip_avenida_prefix(mapped_street_norm)
                mapped_full_norm_wo_avenida = self._strip_avenida_prefix(mapped_full_norm)

                same_street = input_street_norm == mapped_street_norm
                same_street = same_street or (
                    input_street_norm_wo_avenida
                    and input_street_norm_wo_avenida == mapped_street_norm_wo_avenida
                )
                if not same_street:
                    input_tokens = self._street_token_set(
                        input_street_norm_wo_avenida or input_street_norm
                    )
                    mapped_tokens = self._street_token_set(
                        mapped_street_norm_wo_avenida or mapped_street_norm
                    )
                    if mapped_tokens and mapped_tokens.issubset(input_tokens):
                        same_street = True

                if input_numbers and mapped_numbers and same_street:
                    if any(num in mapped_numbers for num in input_numbers):
                        return self._coerce_code(code)

                if input_full_norm and input_full_norm == mapped_full_norm:
                    return self._coerce_code(code)
                if (
                    input_full_norm_wo_avenida
                    and input_full_norm_wo_avenida == mapped_full_norm_wo_avenida
                ):
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
        global gspread, Credentials
        now = time.time()
        if self._gc and now - self._last_auth_ts < self._auth_ttl:
            return self._gc
        if gspread is None or Credentials is None:
            try:
                import gspread as _gspread
                from google.oauth2.service_account import Credentials as _Credentials
            except Exception as exc:
                raise RuntimeError("gspread/google-auth not installed") from exc
            gspread = _gspread
            Credentials = _Credentials
        creds = self._load_credentials()
        self._gc = gspread.authorize(creds)
        self._last_auth_ts = now
        return self._gc


expensas_sheet_service = ExpensasSheetService()
