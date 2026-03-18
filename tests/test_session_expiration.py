from datetime import datetime, timedelta, timezone

from chatbot.models import ConversacionData, EstadoConversacion, TipoConsulta
from chatbot.states import ConversationManager
from services.conversation_session_service import ConversationCheckpoint, ConversationSessionService


class FakeSessionService:
    def __init__(self, checkpoint=None):
        self.checkpoint = checkpoint
        self.delete_calls = []

    def load_for_key(self, conversation_key):
        return self.checkpoint

    def delete_for_key(self, conversation_key):
        self.delete_calls.append(conversation_key)

    def is_resumable_state(self, state):
        return ConversationSessionService.is_resumable_state(state)

    def is_expired(self, expires_at):
        return ConversationSessionService.is_expired(expires_at)


def _build_checkpoint(phone: str, *, expires_at: datetime) -> ConversationCheckpoint:
    conversation = ConversacionData(
        numero_telefono=phone,
        estado=EstadoConversacion.CONFIRMANDO,
        tipo_consulta=TipoConsulta.PAGO_EXPENSAS,
        datos_temporales={"monto": "42000"},
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


def test_serialize_sets_checkpoint_ttl_to_24_hours():
    service = ConversationSessionService()
    conversation = ConversacionData(
        numero_telefono="+5491111111111",
        estado=EstadoConversacion.CONFIRMANDO,
    )
    last_user_message_at = datetime(2026, 3, 18, 12, 30, tzinfo=timezone.utc)

    payload = service.serialize(
        conversation,
        last_user_message_at=last_user_message_at,
        updated_at=last_user_message_at,
    )

    assert payload["expires_at"] == last_user_message_at + timedelta(hours=24)


def test_hydrate_backfills_missing_expiration_from_last_user_message_at():
    service = ConversationSessionService()
    last_user_message_at = datetime(2026, 3, 18, 11, 0, tzinfo=timezone.utc)

    checkpoint = service.hydrate(
        "+5491222222222",
        {
            "estado": EstadoConversacion.CONFIRMANDO.value,
            "tipo_consulta": TipoConsulta.PAGO_EXPENSAS.value,
            "datos_temporales": {"monto": "42000"},
            "updated_at": last_user_message_at,
            "last_user_message_at": last_user_message_at,
            "schema_version": 1,
        },
    )

    assert checkpoint.expires_at == last_user_message_at + timedelta(hours=24)


def test_exact_24_hour_boundary_is_expired():
    now = datetime(2026, 3, 19, 12, 30, tzinfo=timezone.utc)

    assert ConversationSessionService.is_expired(now, now=now)
    assert not ConversationSessionService.is_expired(now + timedelta(seconds=1), now=now)


def test_manager_discards_expired_checkpoint_after_24_hours():
    phone = "+5491333333333"
    checkpoint = _build_checkpoint(
        phone,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    session_service = FakeSessionService(checkpoint=checkpoint)
    manager = ConversationManager(session_service=session_service)

    conversation = manager.get_conversacion(phone)

    assert conversation.estado == EstadoConversacion.INICIO
    assert conversation.numero_telefono == phone
    assert session_service.delete_calls == [phone]
