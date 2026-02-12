import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.expensas_sheet_service import ExpensasSheetService


def test_single_comprobante_keeps_hyperlink_formula():
    formula = ExpensasSheetService._build_comprobante_hyperlink_formula(
        ["https://example.com/comprobante-1.pdf"]
    )
    assert formula.startswith("=HYPERLINK(")
    assert "Ver comprobante" in formula


def test_multiple_comprobantes_do_not_use_concat_formula():
    formula = ExpensasSheetService._build_comprobante_hyperlink_formula(
        [
            "https://example.com/comprobante-1.pdf",
            "https://example.com/comprobante-2.pdf",
        ]
    )
    # Para múltiples URLs preferimos dejar los links crudos en la celda
    # y evitar fórmulas concatenadas que pueden perder clicabilidad.
    assert formula == ""


def test_multiple_comprobantes_build_rich_text_labels():
    text, runs = ExpensasSheetService._build_multi_comprobante_rich_text(
        [
            "https://example.com/comprobante-1.pdf",
            "https://example.com/comprobante-2.pdf",
        ]
    )
    assert text == "Ver comprobante 1\nVer comprobante 2"
    assert runs == [
        {
            "startIndex": 0,
            "format": {"link": {"uri": "https://example.com/comprobante-1.pdf"}},
        },
        {
            "startIndex": len("Ver comprobante 1") + 1,
            "format": {"link": {"uri": "https://example.com/comprobante-2.pdf"}},
        },
    ]
