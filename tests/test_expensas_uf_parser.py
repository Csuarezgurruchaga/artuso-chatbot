import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.expensas_sheet_service import ExpensasSheetService


def test_parse_uf_single():
    assert ExpensasSheetService._parse_uf_from_dpto("2*D UF 5") == "UF 5"
    assert ExpensasSheetService._parse_uf_from_dpto("UF5") == "UF 5"
    assert ExpensasSheetService._parse_uf_from_dpto("U.F. 5") == "UF 5"
    assert ExpensasSheetService._parse_uf_from_dpto("UF 118.") == "UF 118"


def test_parse_uf_multi_two():
    assert ExpensasSheetService._parse_uf_from_dpto("UF 25 Y UF 26") == "UF 25 y UF 26"


def test_parse_uf_multi_three_or_more():
    raw = '2° 1 UF 28, 2° 2 UF 27, Y 3° 7 UF 44'
    assert ExpensasSheetService._parse_uf_from_dpto(raw) == "UF 28, UF 27 y UF 44"


def test_parse_uf_not_present():
    assert ExpensasSheetService._parse_uf_from_dpto("") is None
    assert ExpensasSheetService._parse_uf_from_dpto(None) is None
    assert ExpensasSheetService._parse_uf_from_dpto("COCHERA 38") is None
    assert ExpensasSheetService._parse_uf_from_dpto("0 UF 0") is None


if __name__ == "__main__":
    test_parse_uf_single()
    test_parse_uf_multi_two()
    test_parse_uf_multi_three_or_more()
    test_parse_uf_not_present()
    print("OK")

