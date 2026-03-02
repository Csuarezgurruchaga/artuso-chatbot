import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("COMPANY_PROFILE", "administracion-artuso")


class _StubNLUService:
    def detectar_solicitud_humano(self, _mensaje):
        return False

    def detectar_consulta_contacto(self, _mensaje):
        return False

    def generar_respuesta_contacto(self, _mensaje):
        return ""

    def extraer_expensas_ed_combinado(self, _mensaje):
        return None


class _StubNLUServiceClass:
    @staticmethod
    def construir_unidad_sugerida(_parsed):
        return None


_nlu_module = types.ModuleType("services.nlu_service")
_nlu_module.nlu_service = _StubNLUService()
_nlu_module.NLUService = _StubNLUServiceClass
sys.modules["services.nlu_service"] = _nlu_module

from chatbot.models import EstadoConversacion, TipoConsulta
from chatbot.rules import ChatbotRules
from chatbot.states import conversation_manager


def _setup_expensas_address_step(phone: str):
    conversation_manager.reset_conversacion(phone)
    conv = conversation_manager.get_conversacion(phone)
    conv.tipo_consulta = TipoConsulta.PAGO_EXPENSAS
    conv.estado = EstadoConversacion.RECOLECTANDO_SECUENCIAL
    conv.datos_temporales["fecha_pago"] = "01/03/2026"
    conv.datos_temporales["monto"] = "1000"
    conv.datos_temporales.pop("direccion", None)
    conv.datos_temporales.pop("piso_depto", None)
    conv.datos_temporales.pop("_direccion_fuzzy_candidates", None)
    conv.datos_temporales.pop("_piso_depto_sugerido", None)
    return conv


def test_typo_prompts_single_canonical_choice():
    phone = "test-fuzzy-typo"
    _setup_expensas_address_step(phone)

    response = ChatbotRules.procesar_mensaje(phone, "Peorn 1875")
    conv = conversation_manager.get_conversacion(phone)

    assert "No pude identificar la direccion. ¿Quisiste decir?" in response
    assert "1) Tte. Gral. Juan Domingo Perón 1875" in response
    assert conv.datos_temporales.get("direccion") is None
    assert conv.datos_temporales.get("_direccion_fuzzy_candidates") == [
        "Tte. Gral. Juan Domingo Perón 1875"
    ]


def test_confirming_fuzzy_choice_persists_canonical_address():
    phone = "test-fuzzy-confirm"
    _setup_expensas_address_step(phone)

    first_response = ChatbotRules.procesar_mensaje(phone, "Peorn 1875")
    assert "1) Tte. Gral. Juan Domingo Perón 1875" in first_response

    response = ChatbotRules.procesar_mensaje(phone, "1")
    conv = conversation_manager.get_conversacion(phone)

    assert conv.datos_temporales["direccion"] == "Tte. Gral. Juan Domingo Perón 1875"
    assert conv.datos_temporales.get("_direccion_fuzzy_candidates") is None
    assert "¿Quisiste decir?" not in response


def test_wrong_number_does_not_open_fuzzy_prompt():
    phone = "test-fuzzy-wrong-number"
    _setup_expensas_address_step(phone)

    response = ChatbotRules.procesar_mensaje(phone, "Peron 1877")
    conv = conversation_manager.get_conversacion(phone)

    assert "No pude identificar la direccion. ¿Quisiste decir?" not in response
    assert "No pude identificar la direccion. ¿Cual es la correcta?" not in response
    assert conv.datos_temporales["direccion"] == "Peron 1877"
    assert conv.datos_temporales.get("_direccion_fuzzy_candidates") is None


def test_direct_match_canonicalizes_without_fuzzy_prompt():
    phone = "test-fuzzy-direct"
    _setup_expensas_address_step(phone)

    response = ChatbotRules.procesar_mensaje(phone, "Peron 1875")
    conv = conversation_manager.get_conversacion(phone)

    assert "No pude identificar la direccion. ¿Quisiste decir?" not in response
    assert conv.datos_temporales["direccion"] == "Tte. Gral. Juan Domingo Perón 1875"
    assert conv.datos_temporales.get("_direccion_fuzzy_candidates") is None
