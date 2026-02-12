import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from chatbot.models import EstadoConversacion, TipoConsulta
from chatbot.rules import ChatbotRules
from chatbot.states import conversation_manager
from services.nlu_service import nlu_service


def _prepare_expensas_en_paso_direccion(numero: str) -> None:
    conversation_manager.reset_conversacion(numero)
    conversation_manager.set_tipo_consulta(numero, TipoConsulta.PAGO_EXPENSAS)
    conversation_manager.update_estado(numero, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    conversation_manager.set_datos_temporales(numero, "fecha_pago", "12/02/2026")
    conversation_manager.set_datos_temporales(numero, "monto", "45800")


@pytest.mark.parametrize(
    "mensaje, llm_output, direccion_esperada, piso_esperado",
    [
        (
            "Calle Sarmiento 1922 2° A Unidad funcional 6 a nombre de Diego Alberto Vicente",
            {
                "direccion_altura": "Sarmiento 1922",
                "piso_depto": "2A, Uf 6",
                "fecha_pago": "",
                "monto": "",
                "comentario_extra": "a nombre de Diego Alberto Vicente",
            },
            "Sarmiento 1922",
            "2A, Uf 6",
        ),
        (
            "Calle Paraguay 2957, departamento 7D. Barrios Recoleta, Ciudad autónoma de Buenos Aires",
            {
                "direccion_altura": "Paraguay 2957",
                "piso_depto": "7D",
                "fecha_pago": "",
                "monto": "",
                "comentario_extra": "",
            },
            "Paraguay 2957",
            "7D",
        ),
        (
            "Tte. Gral. Juan Domingo Perón 2250 Piso 10 Departamento D",
            {
                "direccion_altura": "Tte. Gral. Juan Domingo Perón 2250",
                "piso_depto": "10D",
                "fecha_pago": "",
                "monto": "",
                "comentario_extra": "",
            },
            "Tte. Gral. Juan Domingo Perón 2250",
            "10D",
        ),
    ],
)
def test_expensas_ed_usa_llm_combinado_y_autocompleta_campos(
    monkeypatch,
    mensaje: str,
    llm_output: dict,
    direccion_esperada: str,
    piso_esperado: str,
) -> None:
    calls = {"combined": 0}

    def _forbidden_old_llm_call(*_args, **_kwargs):
        raise AssertionError("No debe usar extraer_direccion_unidad en ED combinado")

    def _fake_combined(texto: str):
        calls["combined"] += 1
        assert texto == mensaje
        return llm_output

    monkeypatch.setattr(nlu_service, "extraer_direccion_unidad", _forbidden_old_llm_call)
    monkeypatch.setattr(
        nlu_service,
        "extraer_expensas_ed_combinado",
        _fake_combined,
        raising=False,
    )

    numero = f"messenger:test_ed_combined_{abs(hash(mensaje))}"
    _prepare_expensas_en_paso_direccion(numero)

    respuesta = ChatbotRules._procesar_campo_secuencial(numero, mensaje)
    conversacion = conversation_manager.get_conversacion(numero)

    assert calls["combined"] == 1
    assert conversacion.datos_temporales.get("direccion") == direccion_esperada
    assert conversacion.datos_temporales.get("piso_depto") == piso_esperado
    assert conversacion.datos_temporales.get("_piso_depto_sugerido") in (None, "")
    assert "complet" in respuesta.lower()
    assert "comprobante" in respuesta.lower()


def test_expensas_ed_no_autocompleta_fecha_monto_desde_paso_direccion(monkeypatch) -> None:
    mensaje = "Sarmiento 1922 2A, pague 45800 el 11/02/2026"
    llm_output = {
        "direccion_altura": "Sarmiento 1922",
        "piso_depto": "2A",
        "fecha_pago": "11/02/2026",
        "monto": "45800",
        "comentario_extra": "",
    }

    def _fake_combined(texto: str):
        assert texto == mensaje
        return llm_output

    monkeypatch.setattr(
        nlu_service,
        "extraer_expensas_ed_combinado",
        _fake_combined,
        raising=False,
    )

    numero = "messenger:test_ed_scope"
    conversation_manager.reset_conversacion(numero)
    conversation_manager.set_tipo_consulta(numero, TipoConsulta.PAGO_EXPENSAS)
    conversation_manager.update_estado(numero, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    conversation_manager.set_datos_temporales(numero, "fecha_pago", "")
    conversation_manager.set_datos_temporales(numero, "monto", "")

    ChatbotRules._procesar_campo_secuencial(numero, mensaje)
    conversacion = conversation_manager.get_conversacion(numero)

    assert conversacion.datos_temporales.get("direccion") == "Sarmiento 1922"
    assert conversacion.datos_temporales.get("piso_depto") == "2A"
    assert conversacion.datos_temporales.get("fecha_pago") == ""
    assert conversacion.datos_temporales.get("monto") == ""
