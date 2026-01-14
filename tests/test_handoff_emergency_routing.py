import os

import pytest

os.environ.setdefault("META_WA_ACCESS_TOKEN", "test_token")
os.environ.setdefault("META_WA_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("META_WA_APP_SECRET", "test_app_secret")
os.environ.setdefault("META_WA_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("HANDOFF_WHATSAPP_NUMBER", "+5491000000000")

from chatbot.models import TipoConsulta
from chatbot.states import conversation_manager
import main


class DummyMetaService:
    def __init__(self):
        self.template_calls = []
        self.text_calls = []

    def send_template_message(self, to_number, template_name, language_code, body_params):
        self.template_calls.append((to_number, template_name, language_code, body_params))
        return True

    def send_text_message(self, to_number, message):
        self.text_calls.append((to_number, message))
        return True


def _reset_conversation_manager():
    conversation_manager.conversaciones.clear()
    conversation_manager.handoff_queue.clear()
    conversation_manager.active_handoff = None
    conversation_manager.recently_finalized.clear()


@pytest.fixture(autouse=True)
def reset_state():
    _reset_conversation_manager()
    yield
    _reset_conversation_manager()


def _build_conversation(phone: str, tipo: TipoConsulta):
    conv = conversation_manager.get_conversacion(phone)
    conv.tipo_consulta = tipo
    conv.mensaje_handoff_contexto = "mensaje de prueba"
    conv.nombre_usuario = "Cliente Test"
    return conv


def test_emergency_handoff_routes_to_emergency_number(monkeypatch):
    dummy_service = DummyMetaService()
    monkeypatch.setattr(main, "meta_whatsapp_service", dummy_service)
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491000000000")
    monkeypatch.setenv("HANDOFF_EMERGENCY_WHATSAPP_NUMBER", "+5492000000000")

    conv = _build_conversation("+5491111111111", TipoConsulta.EMERGENCIA)
    assert main._notify_handoff_activated(conv, 1, 1) is True

    assert dummy_service.template_calls
    assert dummy_service.template_calls[0][0] == "+5492000000000"


def test_emergency_handoff_falls_back_to_standard_number(monkeypatch):
    dummy_service = DummyMetaService()
    monkeypatch.setattr(main, "meta_whatsapp_service", dummy_service)
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491000000000")
    monkeypatch.delenv("HANDOFF_EMERGENCY_WHATSAPP_NUMBER", raising=False)

    conv = _build_conversation("+5491222222222", TipoConsulta.EMERGENCIA)
    assert main._notify_handoff_activated(conv, 1, 1) is True

    assert dummy_service.template_calls
    assert dummy_service.template_calls[0][0] == "+5491000000000"


def test_standard_handoff_uses_standard_number(monkeypatch):
    dummy_service = DummyMetaService()
    monkeypatch.setattr(main, "meta_whatsapp_service", dummy_service)
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491000000000")
    monkeypatch.setenv("HANDOFF_EMERGENCY_WHATSAPP_NUMBER", "+5492000000000")

    conv = _build_conversation("+5491333333333", TipoConsulta.PAGO_EXPENSAS)
    assert main._notify_handoff_activated(conv, 1, 1) is True

    assert dummy_service.template_calls
    assert dummy_service.template_calls[0][0] == "+5491000000000"
