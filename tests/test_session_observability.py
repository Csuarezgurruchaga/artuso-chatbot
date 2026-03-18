import hashlib
import hmac
import json
import logging
import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from chatbot.models import ConversacionData, EstadoConversacion, TipoConsulta
from chatbot.states import ConversationManager
from services import conversation_session_service as session_module
from services.conversation_session_service import ConversationCheckpoint

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


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


class ExpiredCheckpointSessionService:
    def __init__(self, checkpoint):
        self.checkpoint = checkpoint
        self.deleted = []

    def load_for_key(self, _conversation_key):
        return self.checkpoint

    def delete_for_key(self, conversation_key):
        self.deleted.append(conversation_key)

    def is_resumable_state(self, state):
        return session_module.ConversationSessionService.is_resumable_state(state)

    def is_expired(self, expires_at):
        return session_module.ConversationSessionService.is_expired(expires_at)


def _build_main(monkeypatch):
    monkeypatch.setenv("META_WA_ACCESS_TOKEN", "test_token_123")
    monkeypatch.setenv("META_WA_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_WA_APP_SECRET", "test_secret")
    monkeypatch.setenv("META_WA_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491135722871")

    import main

    monkeypatch.setattr(main.whatsapp_handoff_service, "is_agent_message", lambda *_: False)
    monkeypatch.setattr(main, "_maybe_notify_handoff", lambda *_: None)
    monkeypatch.setattr(main, "_postprocess_enviando", lambda *_: None)
    monkeypatch.setattr(main.meta_whatsapp_service, "extract_status_data", lambda *_: None)
    monkeypatch.setattr(main.meta_whatsapp_service, "validate_webhook_signature", lambda *_: True)
    return main


def _build_signed_payload(message_id: str) -> tuple[str, dict]:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "5491135722871",
                        "phone_number_id": "123456789",
                    },
                    "contacts": [{
                        "profile": {"name": "Usuario Test"},
                        "wa_id": "5491198765432",
                    }],
                    "messages": [{
                        "from": "5491198765432",
                        "id": message_id,
                        "timestamp": "1234567890",
                        "type": "text",
                        "text": {"body": "Necesito ayuda"},
                    }],
                },
                "field": "messages",
            }],
        }],
    }
    body = json.dumps(payload)
    signature_hash = hmac.new(
        b"test_secret",
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return body, {
        "X-Hub-Signature-256": f"sha256={signature_hash}",
        "Content-Type": "application/json",
    }


def test_service_logs_checkpoint_lifecycle_without_sensitive_payloads(monkeypatch, caplog):
    FakeFirestoreClient.instances.clear()
    monkeypatch.setattr(
        session_module,
        "firestore",
        SimpleNamespace(Client=FakeFirestoreClient),
    )
    service = session_module.ConversationSessionService()
    conversation = ConversacionData(
        numero_telefono="+5491111111111",
        estado=EstadoConversacion.CONFIRMANDO,
        tipo_consulta=TipoConsulta.PAGO_EXPENSAS,
        nombre_usuario="Ana",
        datos_temporales={"detalle": "fuga de agua"},
    )

    with caplog.at_level(logging.INFO):
        service.save("whatsapp", conversation.numero_telefono, conversation)
        service.load("whatsapp", conversation.numero_telefono)
        service.delete("whatsapp", conversation.numero_telefono)

    assert "checkpoint_save doc_id=whatsapp:+5491111111111 estado=confirmando" in caplog.text
    assert "checkpoint_load doc_id=whatsapp:+5491111111111 estado=confirmando" in caplog.text
    assert "checkpoint_delete doc_id=whatsapp:+5491111111111" in caplog.text
    assert "fuga de agua" not in caplog.text


def test_manager_logs_expiration_on_read(monkeypatch, caplog):
    phone = "+5491222222222"
    updated_at = datetime.now(timezone.utc) - timedelta(hours=25)
    checkpoint = ConversationCheckpoint(
        doc_id=f"whatsapp:{phone}",
        conversation=ConversacionData(
            numero_telefono=phone,
            estado=EstadoConversacion.CONFIRMANDO,
            tipo_consulta=TipoConsulta.PAGO_EXPENSAS,
            datos_temporales={"monto": "42000"},
        ),
        updated_at=updated_at,
        last_user_message_at=updated_at,
        expires_at=updated_at + timedelta(hours=24),
        schema_version=1,
    )
    manager = ConversationManager(session_service=ExpiredCheckpointSessionService(checkpoint))

    with caplog.at_level(logging.INFO):
        conversation = manager.get_conversacion(phone)

    assert conversation.estado == EstadoConversacion.INICIO
    assert f"checkpoint_expired_on_read doc_id=whatsapp:{phone} estado=confirmando" in caplog.text
    assert "42000" not in caplog.text


def test_main_logs_deduped_inbound(monkeypatch, caplog):
    main = _build_main(monkeypatch)
    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: ("+5491198765432", "Necesito ayuda", "wamid.dup-1", "Usuario Test", "text", ""),
    )
    monkeypatch.setattr(main.conversation_session_service, "mark_message_processed", lambda *_: True)

    client = TestClient(main.app)
    body, headers = _build_signed_payload("wamid.dup-1")

    with caplog.at_level(logging.INFO):
        response = client.post("/webhook/whatsapp", data=body, headers=headers)

    assert response.status_code == 200
    assert "message_deduped phone=+5491198765432 message_id=wamid.dup-1" in caplog.text


def test_main_logs_critical_and_final_save_failures(monkeypatch, caplog):
    main = _build_main(monkeypatch)
    phone = "+5491198765433"

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)
    conversation.estado = EstadoConversacion.CONFIRMANDO

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(main.conversation_session_service, "save_for_key", fail_save)
    monkeypatch.setattr(main, "send_message", lambda *_: True)

    with caplog.at_level(logging.ERROR):
        assert not main._persist_checkpoint_before_send(phone, "confirmacion_interactiva")
        main._save_final_checkpoint_if_needed(phone)

    assert "critical_save_before_send_failed phone=+5491198765433 estado=EstadoConversacion.CONFIRMANDO reason=confirmacion_interactiva error=firestore down" in caplog.text
    assert "final_save_failed phone=+5491198765433 estado=EstadoConversacion.CONFIRMANDO error=firestore down" in caplog.text
