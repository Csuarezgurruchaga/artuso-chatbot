from datetime import datetime, timedelta, timezone

from chatbot.models import ConversacionData, EstadoConversacion, TipoConsulta
from chatbot.states import ConversationManager
from services.conversation_session_service import ConversationCheckpoint


class FakeSessionService:
    def __init__(self, checkpoint=None):
        self.checkpoint = checkpoint
        self.load_calls = []
        self.delete_calls = []

    def load_for_key(self, conversation_key):
        self.load_calls.append(conversation_key)
        return self.checkpoint

    def delete_for_key(self, conversation_key):
        self.delete_calls.append(conversation_key)

    def is_resumable_state(self, state):
        return state in {
            EstadoConversacion.RECOLECTANDO_DATOS,
            EstadoConversacion.RECOLECTANDO_DATOS_INDIVIDUALES,
            EstadoConversacion.RECOLECTANDO_SECUENCIAL,
            EstadoConversacion.ELIMINANDO_DIRECCION_GUARDADA,
            EstadoConversacion.VALIDANDO_UBICACION,
            EstadoConversacion.VALIDANDO_DATOS,
            EstadoConversacion.CONFIRMANDO,
            EstadoConversacion.CONFIRMANDO_MEDIA,
            EstadoConversacion.CORRIGIENDO,
            EstadoConversacion.CORRIGIENDO_CAMPO,
        }

    def is_expired(self, expires_at):
        return expires_at <= datetime.now(timezone.utc)


class ExplodingSessionService(FakeSessionService):
    def load_for_key(self, conversation_key):
        raise RuntimeError("firestore unavailable")


def _build_checkpoint(phone, state, *, expires_at):
    conversation = ConversacionData(
        numero_telefono=phone,
        estado=state,
        estado_anterior=EstadoConversacion.RECOLECTANDO_SECUENCIAL,
        tipo_consulta=TipoConsulta.PAGO_EXPENSAS,
        datos_temporales={"monto": "42000"},
        nombre_usuario="Ana",
    )
    updated_at = datetime.now(timezone.utc)
    return ConversationCheckpoint(
        doc_id=f"whatsapp:{phone}",
        conversation=conversation,
        updated_at=updated_at,
        last_user_message_at=updated_at,
        expires_at=expires_at,
        schema_version=1,
    )


def test_manager_hydrates_checkpoint_when_ram_is_empty():
    phone = "+5491111111111"
    checkpoint = _build_checkpoint(
        phone,
        EstadoConversacion.CONFIRMANDO,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session_service = FakeSessionService(checkpoint=checkpoint)
    manager = ConversationManager(session_service=session_service)

    conversation = manager.get_conversacion(phone)

    assert conversation.estado == EstadoConversacion.CONFIRMANDO
    assert conversation.tipo_consulta == TipoConsulta.PAGO_EXPENSAS
    assert conversation.datos_temporales["monto"] == "42000"
    assert session_service.load_calls == [phone]
    assert session_service.delete_calls == []

    same_conversation = manager.get_conversacion(phone)
    assert same_conversation is conversation
    assert session_service.load_calls == [phone]


def test_manager_deletes_expired_checkpoint_and_starts_new_conversation():
    phone = "+5491222222222"
    checkpoint = _build_checkpoint(
        phone,
        EstadoConversacion.CONFIRMANDO,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    session_service = FakeSessionService(checkpoint=checkpoint)
    manager = ConversationManager(session_service=session_service)

    conversation = manager.get_conversacion(phone)

    assert conversation.estado == EstadoConversacion.INICIO
    assert conversation.numero_telefono == phone
    assert session_service.load_calls == [phone]
    assert session_service.delete_calls == [phone]


def test_manager_ignores_non_resumable_checkpoint():
    phone = "+5491333333333"
    checkpoint = _build_checkpoint(
        phone,
        EstadoConversacion.ATENDIDO_POR_HUMANO,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session_service = FakeSessionService(checkpoint=checkpoint)
    manager = ConversationManager(session_service=session_service)

    conversation = manager.get_conversacion(phone)

    assert conversation.estado == EstadoConversacion.INICIO
    assert session_service.load_calls == [phone]
    assert session_service.delete_calls == []


def test_manager_falls_back_to_memory_when_checkpoint_load_fails():
    phone = "+5491444444444"
    manager = ConversationManager(session_service=ExplodingSessionService())

    conversation = manager.get_conversacion(phone)

    assert conversation.estado == EstadoConversacion.INICIO
    assert conversation.numero_telefono == phone
