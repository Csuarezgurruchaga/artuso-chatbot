from datetime import date

from services.expensas_sheet_service import (
    EXPENSAS_CURRENT_SHEET_NAME,
    EXPENSAS_PREVIOUS_SHEET_NAME,
    build_expensas_title,
    previous_month_date,
)


def test_previous_month_date_wraps_year():
    assert previous_month_date(date(2025, 1, 15)) == date(2024, 12, 1)
    assert previous_month_date(date(2025, 3, 10)) == date(2025, 2, 1)


def test_build_expensas_title_spanish_abbrev():
    assert (
        build_expensas_title(EXPENSAS_CURRENT_SHEET_NAME, date(2025, 3, 1))
        == "PAGOS MES ACTUAL (Mar 2025)"
    )
    assert (
        build_expensas_title(EXPENSAS_PREVIOUS_SHEET_NAME, date(2025, 2, 1))
        == "PAGOS MES ANTERIOR (Feb 2025)"
    )
