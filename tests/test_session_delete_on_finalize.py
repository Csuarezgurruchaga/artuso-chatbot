from chatbot.models import EstadoConversacion
from chatbot.states import ConversationManager


class FakeSessionService:
    def __init__(self):
        self.deleted = []

    def load_for_key(self, _conversation_key):
        return None

    def is_resumable_state(self, _state):
        return False

    def is_expired(self, _expires_at):
        return False

    def delete_for_key(self, conversation_key):
        self.deleted.append(conversation_key)


def test_finalize_deletes_checkpoint_and_clears_ram():
    phone = "+5491190000001"
    session_service = FakeSessionService()
    manager = ConversationManager(session_service=session_service)

    conversation = manager.get_conversacion(phone)
    conversation.estado = EstadoConversacion.CONFIRMANDO

    manager.finalizar_conversacion(phone)

    assert phone not in manager.conversaciones
    assert phone in manager.recently_finalized
    assert session_service.deleted == [phone]


def test_reset_deletes_checkpoint_and_clears_recent_flag():
    phone = "+5491190000002"
    session_service = FakeSessionService()
    manager = ConversationManager(session_service=session_service)

    manager.get_conversacion(phone)
    manager.mark_recently_finalized(phone)

    manager.reset_conversacion(phone)

    assert phone not in manager.conversaciones
    assert phone not in manager.recently_finalized
    assert session_service.deleted == [phone]
