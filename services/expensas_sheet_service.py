import os
import logging
from datetime import datetime

from services.sheets_service import sheets_service

logger = logging.getLogger(__name__)

EXPENSAS_SPREADSHEET_ID = "1WTzQlPRp63HDyUfsCMI5HNFaCUn82SYeDksZGMkKXi4"
EXPENSAS_SHEET_NAME = "chatbot-expensas"


class ExpensasSheetService:
    def __init__(self):
        self.enabled = os.getenv("ENABLE_EXPENSAS_SHEET", "true").lower() == "true"

    def append_pago(self, conversacion) -> bool:
        if not self.enabled:
            logger.info("ExpensasSheetService disabled (ENABLE_EXPENSAS_SHEET=false)")
            return False

        datos = conversacion.datos_temporales or {}
        fecha_aviso = datetime.now().strftime("%d/%m/%Y")
        comentario = datos.get("comentario") or ""

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
            gc = sheets_service._get_client()
            sh = gc.open_by_key(EXPENSAS_SPREADSHEET_ID)
            ws = sh.worksheet(EXPENSAS_SHEET_NAME)
            ws.append_row(row, value_input_option="RAW")
            return True
        except Exception as e:
            logger.error(f"Error guardando expensas en Sheets: {str(e)}")
            return False


expensas_sheet_service = ExpensasSheetService()
