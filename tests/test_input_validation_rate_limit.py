import re

import pytest

from chatbot.rules import ChatbotRules
from services.rate_limit_service import RateLimitService


def test_normalizar_fecha_pago():
    assert ChatbotRules._normalizar_fecha_pago("12/09/2025") == "12/09/2025"
    assert ChatbotRules._normalizar_fecha_pago("12-09-2025") == "12/09/2025"
    assert ChatbotRules._normalizar_fecha_pago("12.09.2025") == "12/09/2025"
    assert ChatbotRules._normalizar_fecha_pago("12/09/25") is None


def test_normalizar_monto():
    assert ChatbotRules._normalizar_monto("1.234,56") == "1234.56"
    assert ChatbotRules._normalizar_monto("1,234.56") == "1234.56"
    assert ChatbotRules._normalizar_monto("45.800") == "45800"
    assert ChatbotRules._normalizar_monto("1234,5") == "1234.5"
    assert ChatbotRules._normalizar_monto("2000000") == "2000000"
    assert ChatbotRules._normalizar_monto("2000000.01") is None


def test_direccion_valida():
    assert ChatbotRules._direccion_valida("Av. Corrientes 1234")
    assert ChatbotRules._direccion_valida("Cochera 2º A")
    assert ChatbotRules._direccion_valida("Pasaje #5 10")
    assert not ChatbotRules._direccion_valida("Calle sin numero")
    assert not ChatbotRules._direccion_valida("1234")
    assert not ChatbotRules._direccion_valida("Calle 12;")


class DummySheet:
    def __init__(self, rows=None):
        self.rows = rows or [["phone", "date", "count", "updated_at"]]

    def get_all_values(self):
        return self.rows

    def update(self, range_name, values, value_input_option="RAW"):
        match = re.search(r"(\d+)", range_name)
        if not match:
            raise ValueError("Invalid range")
        row_idx = int(match.group(1))
        while len(self.rows) < row_idx:
            self.rows.append([])
        self.rows[row_idx - 1] = values[0]

    def append_row(self, row, value_input_option="RAW"):
        self.rows.append(row)


def test_rate_limit_service_counts(monkeypatch):
    service = RateLimitService()
    dummy = DummySheet()

    monkeypatch.setattr(service, "_get_sheet", lambda: dummy)
    monkeypatch.setattr(service, "_today_key", lambda: "2025-01-01")
    service.enabled = True

    allowed, count, date_key = service.check_and_increment("1111", limit=2)
    assert allowed is True
    assert count == 1
    assert date_key == "2025-01-01"

    allowed, count, _ = service.check_and_increment("1111", limit=2)
    assert allowed is True
    assert count == 2

    allowed, count, _ = service.check_and_increment("1111", limit=2)
    assert allowed is False
    assert count == 2


def test_rate_limit_resets_on_date_change(monkeypatch):
    service = RateLimitService()
    dummy = DummySheet(rows=[["phone", "date", "count", "updated_at"], ["1111", "2025-01-01", "5", ""]])

    monkeypatch.setattr(service, "_get_sheet", lambda: dummy)
    monkeypatch.setattr(service, "_today_key", lambda: "2025-01-02")
    service.enabled = True

    allowed, count, date_key = service.check_and_increment("1111", limit=2)
    assert allowed is True
    assert count == 1
    assert date_key == "2025-01-02"
    assert dummy.rows[1][1] == "2025-01-02"
    assert dummy.rows[1][2] == "1"
    assert len(dummy.rows) == 2
