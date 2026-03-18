import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from chatbot.models import ConversacionData, EstadoConversacion
from services import conversation_session_service as session_module

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class FakeSnapshot:
    def __init__(self, doc_id, data, collection):
        self.id = doc_id
        self._data = deepcopy(data)
        self.exists = data is not None
        self.reference = FakeDocumentReference(collection, doc_id)

    def to_dict(self):
        return deepcopy(self._data)


class FakeDocumentReference:
    def __init__(self, storage, doc_id):
        self._storage = storage
        self._doc_id = doc_id

    def set(self, payload):
        self._storage[self._doc_id] = deepcopy(payload)

    def get(self):
        return FakeSnapshot(self._doc_id, self._storage.get(self._doc_id), self._storage)

    def delete(self):
        self._storage.pop(self._doc_id, None)


class FakeQuery:
    def __init__(self, storage, field_path, op_string, value):
        self._storage = storage
        self._field_path = field_path
        self._op_string = op_string
        self._value = value
        self._limit = None

    def limit(self, amount):
        self._limit = amount
        return self

    def stream(self):
        matches = []
        for doc_id, payload in self._storage.items():
            current = payload.get(self._field_path)
            if self._op_string == "<=" and current is not None and current <= self._value:
                matches.append(FakeSnapshot(doc_id, payload, self._storage))
        matches.sort(key=lambda snapshot: snapshot.id)
        if self._limit is not None:
            matches = matches[: self._limit]
        return matches


class FakeCollectionReference:
    def __init__(self, storage, name):
        self._storage = storage
        self._name = name

    def document(self, doc_id):
        collection = self._storage.setdefault(self._name, {})
        return FakeDocumentReference(collection, doc_id)

    def where(self, field_path, op_string, value):
        collection = self._storage.setdefault(self._name, {})
        return FakeQuery(collection, field_path, op_string, value)


class FakeFirestoreClient:
    instances = []

    def __init__(self, database):
        self.database = database
        self.collections = {}
        FakeFirestoreClient.instances.append(self)

    def collection(self, name):
        return FakeCollectionReference(self.collections, name)


def _build_main(monkeypatch):
    monkeypatch.setenv("META_WA_ACCESS_TOKEN", "test_token_123")
    monkeypatch.setenv("META_WA_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_WA_APP_SECRET", "test_secret")
    monkeypatch.setenv("META_WA_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491135722871")
    monkeypatch.setenv("SESSION_CHECKPOINT_CLEANUP_TOKEN", "cleanup-token")
    monkeypatch.setenv("SESSION_CHECKPOINT_CLEANUP_BATCH_SIZE", "2")

    import importlib
    import main

    return importlib.reload(main)


def test_cleanup_service_deletes_only_expired_checkpoints(monkeypatch):
    FakeFirestoreClient.instances.clear()
    monkeypatch.setattr(
        session_module,
        "firestore",
        SimpleNamespace(Client=FakeFirestoreClient),
    )
    service = session_module.ConversationSessionService()
    now = datetime(2026, 3, 18, 15, 0, tzinfo=timezone.utc)

    expired = ConversacionData(numero_telefono="+5491111111111", estado=EstadoConversacion.CONFIRMANDO)
    fresh = ConversacionData(numero_telefono="+5491222222222", estado=EstadoConversacion.CONFIRMANDO)
    other_expired = ConversacionData(numero_telefono="+5491333333333", estado=EstadoConversacion.CONFIRMANDO)

    service.save(
        "whatsapp",
        expired.numero_telefono,
        expired,
        updated_at=now - timedelta(hours=26),
        last_user_message_at=now - timedelta(hours=26),
    )
    service.save(
        "whatsapp",
        fresh.numero_telefono,
        fresh,
        updated_at=now - timedelta(hours=1),
        last_user_message_at=now - timedelta(hours=1),
    )
    service.save(
        "whatsapp",
        other_expired.numero_telefono,
        other_expired,
        updated_at=now - timedelta(hours=30),
        last_user_message_at=now - timedelta(hours=30),
    )

    deleted_doc_ids = service.cleanup_expired_checkpoints(now=now, limit=10)

    assert deleted_doc_ids == [
        "whatsapp:+5491111111111",
        "whatsapp:+5491333333333",
    ]
    assert service.load("whatsapp", "+5491111111111") is None
    assert service.load("whatsapp", "+5491333333333") is None
    assert service.load("whatsapp", "+5491222222222") is not None


def test_cleanup_endpoint_requires_valid_token(monkeypatch):
    main = _build_main(monkeypatch)
    client = TestClient(main.app)

    response = client.post("/session-checkpoints/cleanup", data={"token": "wrong-token"})

    assert response.status_code == 401


def test_cleanup_endpoint_runs_bounded_batch(monkeypatch):
    main = _build_main(monkeypatch)
    captured = {}

    def fake_cleanup_expired_checkpoints(*, limit):
        captured["limit"] = limit
        return ["whatsapp:+5491111111111", "whatsapp:+5491222222222"]

    monkeypatch.setattr(
        main.conversation_session_service,
        "cleanup_expired_checkpoints",
        fake_cleanup_expired_checkpoints,
    )

    client = TestClient(main.app)
    response = client.post(
        "/session-checkpoints/cleanup",
        data={"token": "cleanup-token"},
    )

    assert response.status_code == 200
    assert captured["limit"] == 2
    assert response.json() == {
        "deleted": 2,
        "deleted_doc_ids": [
            "whatsapp:+5491111111111",
            "whatsapp:+5491222222222",
        ],
        "batch_limit": 2,
    }
