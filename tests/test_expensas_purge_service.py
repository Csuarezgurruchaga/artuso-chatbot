from datetime import date

from services.expensas_purge_service import ExpensasPurgeService


def test_parse_date_strict():
    service = ExpensasPurgeService()
    assert service._parse_date("12/09/2025") == date(2025, 9, 12)
    assert service._parse_date("12-09-2025") is None
    assert service._parse_date("12.09.2025") is None
    assert service._parse_date("") is None


def test_select_date_fallback():
    service = ExpensasPurgeService()
    selected = service._select_date("invalid", "05/01/2026")
    assert selected == date(2026, 1, 5)


def test_append_invalid_comment():
    service = ExpensasPurgeService()
    assert service._append_invalid_comment("") == "Fecha invalida"
    assert service._append_invalid_comment("Dato") == "Dato | Fecha invalida"
    assert service._append_invalid_comment("Dato | Fecha invalida") == "Dato | Fecha invalida"


def test_append_future_comment():
    service = ExpensasPurgeService()
    assert service._append_future_comment("") == "Fecha futura"
    assert service._append_future_comment("Dato") == "Dato | Fecha futura"
    assert service._append_future_comment("Dato | Fecha futura") == "Dato | Fecha futura"


def test_should_keep_future_month_only():
    service = ExpensasPurgeService()
    now_date = date(2026, 4, 15)
    assert not service._should_keep_date(date(2026, 4, 1), now_date)
    assert not service._should_keep_date(date(2026, 4, 30), now_date)
    assert not service._should_keep_date(date(2026, 3, 31), now_date)
    assert service._should_keep_date(date(2026, 5, 1), now_date)
