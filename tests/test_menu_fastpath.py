import os

from chatbot.models import EstadoConversacion
from chatbot.rules import ChatbotRules
from chatbot.states import conversation_manager


def _reset(numero: str = "+5491100000000"):
    conversation_manager.reset_conversacion(numero)
    conv = conversation_manager.get_conversacion(numero)
    conv.estado = EstadoConversacion.INICIO
    conv.atendido_por_humano = False
    return conv


def test_emergency_intent_does_not_call_nlu_for_greeting(monkeypatch):
    conv = _reset()

    called = {"nlu": False}

    def fake_mapear(_msg):
        called["nlu"] = True
        return None

    from services import nlu_service as nlu_module

    monkeypatch.setattr(nlu_module.nlu_service, "mapear_intencion", fake_mapear)

    assert ChatbotRules._detect_emergency_intent("hola", conv) is False
    assert called["nlu"] is False


def test_menu_emergency_phrases_map_only_in_menu_match():
    option, source = ChatbotRules._match_menu_option("sin agua")
    assert option is not None
    assert option["id"] == "emergencia"
    assert source == "keyword_phrase"

    option, source = ChatbotRules._match_menu_option("tengo corte de gas en el depto")
    assert option is not None
    assert option["id"] == "emergencia"
    assert source == "keyword_phrase"


def test_menu_normalization_collapses_long_repeats():
    # >=3 repeticiones se colapsan (no rompe dobles letras reales)
    assert ChatbotRules._normalize_menu_text("urgenteeee") == "urgente"
    assert ChatbotRules._normalize_menu_text("expensassss") == "expensas"

def test_emergency_phrases_do_not_trigger_outside_menu(monkeypatch):
    # Si no estamos en INICIO/ESPERANDO_OPCION, frases de "sin agua/sin gas" no deben disparar
    # la detección de emergencia vía keywords; debe delegarse a NLU (OpenAI).
    conv = conversation_manager.get_conversacion("+5491100000001")
    conv.estado = EstadoConversacion.RECOLECTANDO_SECUENCIAL

    called = {"nlu": False}

    def fake_mapear(_msg):
        called["nlu"] = True
        return None

    from services import nlu_service as nlu_module

    monkeypatch.setattr(nlu_module.nlu_service, "mapear_intencion", fake_mapear)

    assert ChatbotRules._detect_emergency_intent("sin agua", conv) is False
    assert called["nlu"] is True


def test_menu_selection_uses_keywords_without_nlu(monkeypatch):
    numero = "+5491199999999"
    conversation_manager.reset_conversacion(numero)
    conversation_manager.update_estado(numero, EstadoConversacion.ESPERANDO_OPCION)

    called = {"nlu": False}

    def fake_mapear(_msg):
        called["nlu"] = True
        return None

    from services import nlu_service as nlu_module

    monkeypatch.setattr(nlu_module.nlu_service, "mapear_intencion", fake_mapear)

    # Debe mapear por keyword (sin OpenAI) y no ejecutar NLU.
    response = ChatbotRules._procesar_seleccion_opcion(numero, "pago expensas")
    assert called["nlu"] is False
    assert isinstance(response, str)
