import os

os.environ.setdefault("META_WA_ACCESS_TOKEN", "test_token")
os.environ.setdefault("META_WA_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("META_WA_APP_SECRET", "test_app_secret")
os.environ.setdefault("META_WA_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("HANDOFF_WHATSAPP_NUMBER", "+5491135722871")

from chatbot.models import EstadoConversacion
from chatbot.states import conversation_manager
from services.agent_command_service import agent_command_service
from services.survey_service import survey_service
from services import sheets_service

_ORIGINAL_SURVEY_ENABLED = survey_service.enabled


def _reset_conversation_manager():
    conversation_manager.conversaciones.clear()
    conversation_manager.handoff_queue.clear()
    conversation_manager.active_handoff = None
    conversation_manager.recently_finalized.clear()


def setup_function(_):
    _reset_conversation_manager()


def teardown_function(_):
    _reset_conversation_manager()
    survey_service.enabled = _ORIGINAL_SURVEY_ENABLED


def test_done_command_releases_queue_and_message(monkeypatch):
    survey_service.enabled = True

    class DummyService:
        def __init__(self):
            self.sent = []

        def send_text_message(self, to_number, message):
            self.sent.append((to_number, message))
            return True

    dummy_service = DummyService()

    monkeypatch.setattr(
        "services.agent_command_service._get_client_messaging_service",
        lambda client_id: (dummy_service, client_id),
    )

    phone_a = "+5491111111111"
    phone_b = "+5491222222222"

    conv_a = conversation_manager.get_conversacion(phone_a)
    conv_a.estado = EstadoConversacion.ATENDIDO_POR_HUMANO
    conv_a.atendido_por_humano = True
    conversation_manager.add_to_handoff_queue(phone_a)

    conv_b = conversation_manager.get_conversacion(phone_b)
    conv_b.estado = EstadoConversacion.ATENDIDO_POR_HUMANO
    conv_b.atendido_por_humano = True
    conversation_manager.add_to_handoff_queue(phone_b)

    response = agent_command_service.execute_done_command("+5491000000000")

    assert "Encuesta en curso" in response
    assert "Usa /queue." in response
    assert "/next" not in response
    assert "Cola vacia." not in response
    assert conversation_manager.get_active_handoff() == phone_b
    assert phone_a not in conversation_manager.handoff_queue
    assert conv_a.estado == EstadoConversacion.ESPERANDO_RESPUESTA_ENCUESTA
    assert conv_a.atendido_por_humano is False
    assert dummy_service.sent


def test_queue_status_hides_survey_states():
    phone_a = "+5491333333333"
    conv_a = conversation_manager.get_conversacion(phone_a)
    conv_a.estado = EstadoConversacion.ESPERANDO_RESPUESTA_ENCUESTA
    conversation_manager.handoff_queue.append(phone_a)
    conversation_manager.active_handoff = phone_a

    status = conversation_manager.format_queue_status()

    assert "No hay conversaciones activas" in status


def test_survey_invalid_attempts_abort(monkeypatch):
    survey_service.enabled = True
    captured = {}

    def fake_append_row(target, row):
        captured["target"] = target
        captured["row"] = row
        return True

    monkeypatch.setattr(sheets_service, "append_row", fake_append_row)

    phone = "+5491444444444"
    conv = conversation_manager.get_conversacion(phone)
    conv.estado = EstadoConversacion.ENCUESTA_SATISFACCION
    conv.survey_sent = True
    conv.survey_question_number = 2
    conv.survey_responses = {}

    for _ in range(2):
        complete, next_message = survey_service.process_survey_response(phone, "foo", conv)
        assert complete is False
        assert "1, 2, 3, 4 o 5" in next_message

    complete, next_message = survey_service.process_survey_response(phone, "foo", conv)
    assert complete is True
    assert "Gracias por tu tiempo" in next_message
    assert captured["target"] == "survey"
    assert captured["row"][2] == "N/A"
    assert captured["row"][3] == "N/A"
    assert captured["row"][4] == "N/A"
    assert conv.survey_accepted is None
    assert conv.datos_temporales.get("survey_aborted_invalids") is True
