import hashlib
import hmac
import json
import os
import sys

from fastapi.testclient import TestClient
from chatbot.models import ConversacionData, EstadoConversacion

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _build_payload(message_id: str, text_body: str = "Necesito ayuda"):
    return {
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
                        "text": {"body": text_body},
                    }],
                },
                "field": "messages",
            }],
        }],
    }


def _post_signed(client: TestClient, payload: dict):
    body = json.dumps(payload)
    signature_hash = hmac.new(
        b"test_secret",
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return client.post(
        "/webhook/whatsapp",
        data=body,
        headers={
            "X-Hub-Signature-256": f"sha256={signature_hash}",
            "Content-Type": "application/json",
        },
    )


def test_duplicate_message_id_is_processed_only_once(monkeypatch):
    monkeypatch.setenv("META_WA_ACCESS_TOKEN", "test_token_123")
    monkeypatch.setenv("META_WA_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_WA_APP_SECRET", "test_secret")
    monkeypatch.setenv("META_WA_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491135722871")

    import main

    phone = "+5491198765432"
    processed_ids = set()
    process_calls = []
    sent_messages = []

    main.conversation_manager.reset_conversacion(phone)
    fake_conversation = ConversacionData(
        numero_telefono=phone,
        estado=EstadoConversacion.INICIO,
    )

    def fake_mark_message_processed(message_id):
        if message_id in processed_ids:
            return True
        processed_ids.add(message_id)
        return False

    def fake_process_message(numero_telefono, mensaje_usuario, profile_name=""):
        process_calls.append((numero_telefono, mensaje_usuario, profile_name))
        return "respuesta dedupe"

    def fake_send_message(user_id, message):
        sent_messages.append((user_id, message))
        return True

    monkeypatch.setattr(
        main.conversation_session_service,
        "mark_message_processed",
        fake_mark_message_processed,
    )
    monkeypatch.setattr(main.whatsapp_handoff_service, "is_agent_message", lambda _: False)
    monkeypatch.setattr(main.conversation_manager, "get_conversacion", lambda _: fake_conversation)
    monkeypatch.setattr(main.conversation_manager, "was_finalized_recently", lambda _: False)
    monkeypatch.setattr(main.conversation_manager, "get_campo_siguiente", lambda _: None)
    monkeypatch.setattr(main.conversation_manager, "clear_recently_finalized", lambda _: None)
    monkeypatch.setattr(main, "_maybe_notify_handoff", lambda _: None)
    monkeypatch.setattr(main, "_postprocess_enviando", lambda _: None)
    monkeypatch.setattr(main.ChatbotRules, "es_mensaje_agradecimiento", lambda _: False)
    monkeypatch.setattr(main.ChatbotRules, "procesar_mensaje", fake_process_message)
    monkeypatch.setattr(main, "send_message", fake_send_message)

    client = TestClient(main.app)
    payload = _build_payload("wamid.duplicate-1")

    response_first = _post_signed(client, payload)
    response_second = _post_signed(client, payload)

    assert response_first.status_code == 200
    assert response_second.status_code == 200
    assert process_calls == [(phone, "Necesito ayuda", "Usuario Test")]
    assert sent_messages == [(phone, "respuesta dedupe")]
