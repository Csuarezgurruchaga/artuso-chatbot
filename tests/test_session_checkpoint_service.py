from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from chatbot.models import ConversacionData, DatosContacto, EstadoConversacion, TipoConsulta
from services import conversation_session_service as session_module


class FakeSnapshot:
    def __init__(self, data):
        self._data = deepcopy(data)
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self._data)


class FakeDocumentReference:
    def __init__(self, storage, doc_id):
        self._storage = storage
        self._doc_id = doc_id

    def set(self, payload):
        self._storage[self._doc_id] = deepcopy(payload)

    def get(self):
        return FakeSnapshot(self._storage.get(self._doc_id))

    def delete(self):
        self._storage.pop(self._doc_id, None)


class FakeCollectionReference:
    def __init__(self, storage, name):
        self._storage = storage
        self._name = name

    def document(self, doc_id):
        collection = self._storage.setdefault(self._name, {})
        return FakeDocumentReference(collection, doc_id)


class FakeFirestoreClient:
    instances = []

    def __init__(self, database):
        self.database = database
        self.collections = {}
        FakeFirestoreClient.instances.append(self)

    def collection(self, name):
        return FakeCollectionReference(self.collections, name)


def _build_conversation():
    return ConversacionData(
        numero_telefono="+5491122334455",
        estado=EstadoConversacion.CONFIRMANDO,
        estado_anterior=EstadoConversacion.RECOLECTANDO_SECUENCIAL,
        tipo_consulta=TipoConsulta.PAGO_EXPENSAS,
        nombre_usuario="Ana",
        datos_contacto=DatosContacto(
            email="ana@example.com",
            direccion="Av Siempre Viva 742",
            horario_visita="9 a 18",
            descripcion="Necesito revisar la liquidacion del mes.",
        ),
        datos_temporales={
            "fecha_pago": "12/03/2026",
            "monto": "45200",
            "_media_confirmacion": True,
        },
        atendido_por_humano=True,
        message_history=[{"sender": "client", "message": "hola"}],
    )


def test_checkpoint_service_round_trip(monkeypatch):
    FakeFirestoreClient.instances.clear()
    monkeypatch.setattr(
        session_module,
        "firestore",
        SimpleNamespace(Client=FakeFirestoreClient),
    )

    service = session_module.ConversationSessionService()
    conversation = _build_conversation()
    updated_at = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
    last_user_message_at = datetime(2026, 3, 18, 11, 55, tzinfo=timezone.utc)

    payload = service.save(
        "whatsapp",
        conversation.numero_telefono,
        conversation,
        updated_at=updated_at,
        last_user_message_at=last_user_message_at,
    )

    assert payload["estado"] == EstadoConversacion.CONFIRMANDO.value
    assert payload["schema_version"] == session_module.CHECKPOINT_SCHEMA_VERSION
    assert payload["expires_at"] == last_user_message_at + timedelta(hours=24)

    client = FakeFirestoreClient.instances[-1]
    raw_doc = client.collections[session_module.CHECKPOINT_COLLECTION][
        "whatsapp:+5491122334455"
    ]
    assert set(raw_doc.keys()) == session_module.CHECKPOINT_FIELDS
    assert raw_doc["datos_contacto"]["email"] == "ana@example.com"
    assert "message_history" not in raw_doc
    assert "atendido_por_humano" not in raw_doc

    checkpoint = service.load("whatsapp", "+5491122334455")

    assert checkpoint is not None
    assert checkpoint.doc_id == "whatsapp:+5491122334455"
    assert checkpoint.updated_at == updated_at
    assert checkpoint.last_user_message_at == last_user_message_at
    assert checkpoint.expires_at == last_user_message_at + timedelta(hours=24)
    assert checkpoint.conversation.estado == EstadoConversacion.CONFIRMANDO
    assert checkpoint.conversation.estado_anterior == EstadoConversacion.RECOLECTANDO_SECUENCIAL
    assert checkpoint.conversation.tipo_consulta == TipoConsulta.PAGO_EXPENSAS
    assert checkpoint.conversation.datos_temporales["monto"] == "45200"
    assert checkpoint.conversation.datos_contacto.email == "ana@example.com"
    assert checkpoint.conversation.atendido_por_humano is False
    assert checkpoint.conversation.message_history == []

    service.delete("whatsapp", "+5491122334455")
    assert service.load("whatsapp", "+5491122334455") is None


def test_is_expired_handles_aware_and_naive_datetimes():
    now = datetime(2026, 3, 18, 14, 0, tzinfo=timezone.utc)

    assert session_module.ConversationSessionService.is_expired(
        now - timedelta(seconds=1),
        now=now,
    )
    assert session_module.ConversationSessionService.is_expired(
        datetime(2026, 3, 18, 13, 59, 59),
        now=now,
    )
    assert not session_module.ConversationSessionService.is_expired(
        now + timedelta(seconds=1),
        now=now,
    )
