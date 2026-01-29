import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from chatbot.rules import ChatbotRules
from services.nlu_service import NLUService


def test_trigger_heuristica() -> None:
    ejemplos_reales = [
        "Sarmiento1922 4toA",
        "Lavalle 1282 piso 1 oficina 8 y 10",
        "Lavalle 1282 1 piso of 1",
        "Lavalle 1282, uf 27, uf 28 y",
        "Calle Sarmiento 1922 2° A Unidad funcional 6 a nombre de Diego Alberto Vicente",
        "Calle Paraguay 2957, departamento 7D. Barrios Recoleta, Ciudad autónoma de Buenos Aires",
        "Guemes 3972 Piso 9o Dto B",
        "Av.Santa Fe 2647 .. piso 2 depto D",
        "Ortiz de Ocampo 2561, 2 A.",
    ]

    for texto in ejemplos_reales:
        assert ChatbotRules._parece_direccion_con_unidad(texto), texto


def test_construir_unidad_sugerida() -> None:
    parsed = {
        "direccion_altura": "Lavalle 1282",
        "piso": "1",
        "depto": "",
        "ufs": [],
        "cocheras": [],
        "oficinas": ["8", "10"],
        "es_local": False,
        "unidad_extra": "",
    }
    assert NLUService.construir_unidad_sugerida(parsed) == "Piso 1, Of 8, Of 10"

    parsed = {
        "direccion_altura": "Lavalle 1282",
        "piso": "",
        "depto": "",
        "ufs": ["27", "28"],
        "cocheras": ["1", "2"],
        "oficinas": [],
        "es_local": False,
        "unidad_extra": "",
    }
    assert NLUService.construir_unidad_sugerida(parsed) == "Uf 27, Uf 28, Cochera 1, Cochera 2"

    parsed = {
        "direccion_altura": "Sarmiento 1922",
        "piso": "2°",
        "depto": "a",
        "ufs": ["6"],
        "cocheras": [],
        "oficinas": [],
        "es_local": False,
        "unidad_extra": "a nombre de Diego Alberto Vicente",
    }
    assert (
        NLUService.construir_unidad_sugerida(parsed)
        == "2A, Uf 6 (a nombre de Diego Alberto Vicente)"
    )

    parsed = {"es_local": True}
    assert NLUService.construir_unidad_sugerida(parsed) == "Local"

    assert NLUService.construir_unidad_sugerida({}) == ""

def test_extract_oficinas_from_raw() -> None:
    assert NLUService._extract_oficinas_from_raw("Lavalle 1282 1 piso of 1") == ["1"]
    assert NLUService._extract_oficinas_from_raw("Lavalle 1282 piso 1 oficina 8 y 10") == ["8", "10"]
    assert NLUService._extract_oficinas_from_raw("of. 12, of 12, OF 13") == ["12", "13"]
    assert NLUService._extract_oficinas_from_raw("ofic 7") == ["7"]
    assert NLUService._extract_oficinas_from_raw("ofic. 7") == ["7"]

def test_extract_ufs_from_raw() -> None:
    assert NLUService._extract_ufs_from_raw("uf 2") == ["2"]
    assert NLUService._extract_ufs_from_raw("unidad funcional 6") == ["6"]
    assert NLUService._extract_ufs_from_raw("unidad 2") == ["2"]


if __name__ == "__main__":
    test_trigger_heuristica()
    test_construir_unidad_sugerida()
    test_extract_oficinas_from_raw()
    test_extract_ufs_from_raw()
    print("OK")
