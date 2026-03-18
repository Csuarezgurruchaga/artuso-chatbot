import json
import os
import sys

from fastapi.testclient import TestClient

from chatbot.models import EstadoConversacion

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _build_client(monkeypatch):
    monkeypatch.setenv("META_WA_ACCESS_TOKEN", "test_token_123")
    monkeypatch.setenv("META_WA_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_WA_APP_SECRET", "test_secret")
    monkeypatch.setenv("META_WA_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("HANDOFF_WHATSAPP_NUMBER", "+5491135722871")

    import main

    monkeypatch.setattr(main.meta_whatsapp_service, "validate_webhook_signature", lambda *_: True)
    monkeypatch.setattr(main.meta_whatsapp_service, "extract_status_data", lambda *_: None)
    monkeypatch.setattr(main.whatsapp_handoff_service, "is_agent_message", lambda *_: False)
    monkeypatch.setattr(main.conversation_session_service, "mark_message_processed", lambda *_: False)
    monkeypatch.setattr(main, "_maybe_notify_handoff", lambda *_: None)
    monkeypatch.setattr(main, "_postprocess_enviando", lambda *_: None)

    return main, TestClient(main.app)


def _post_payload(client: TestClient):
    return client.post(
        "/webhook/whatsapp",
        data=json.dumps({"object": "whatsapp_business_account"}),
        headers={"Content-Type": "application/json"},
    )


def test_media_confirmation_persists_before_prompt(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765432"
    events = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "media:test-media", "wamid.media.1", "Usuario Test", "image", ""),
    )
    monkeypatch.setattr(main.meta_whatsapp_service, "download_media", lambda *_: (b"img", "image/jpeg"))

    from services.gcs_storage_service import gcs_storage_service

    monkeypatch.setattr(gcs_storage_service, "upload_public", lambda *_: "https://example.com/test.jpg")
    monkeypatch.setattr(
        main.conversation_session_service,
        "save_for_key",
        lambda *args, **kwargs: events.append("save") or {},
    )
    monkeypatch.setattr(
        main.ChatbotRules,
        "send_media_confirmacion",
        lambda *_: events.append("prompt") or True,
    )
    monkeypatch.setattr(main, "send_message", lambda *_: True)

    response = _post_payload(client)

    assert response.status_code == 200
    assert events == ["save", "prompt"]
    assert conversation.datos_temporales["_media_confirmacion"] is True
    assert conversation.datos_temporales["adjuntos_pendientes"] == ["https://example.com/test.jpg"]


def test_media_confirmation_prompt_is_blocked_when_save_fails(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765433"
    sent_messages = []
    prompt_calls = []

    main.conversation_manager.reset_conversacion(phone)
    main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "media:test-media", "wamid.media.2", "Usuario Test", "image", ""),
    )
    monkeypatch.setattr(main.meta_whatsapp_service, "download_media", lambda *_: (b"img", "image/jpeg"))

    from services.gcs_storage_service import gcs_storage_service

    monkeypatch.setattr(gcs_storage_service, "upload_public", lambda *_: "https://example.com/test.jpg")

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(main.conversation_session_service, "save_for_key", fail_save)
    monkeypatch.setattr(
        main.ChatbotRules,
        "send_media_confirmacion",
        lambda *_: prompt_calls.append("prompt") or True,
    )
    monkeypatch.setattr(
        main,
        "send_message",
        lambda user_id, message: sent_messages.append((user_id, message)) or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert prompt_calls == []
    assert sent_messages == [
        (phone, "❌ Hubo un error guardando tu sesión. Por favor intentá nuevamente."),
    ]


def test_confirmacion_interactiva_persists_before_prompt(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765434"
    events = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "Necesito ayuda", "wamid.text.1", "Usuario Test", "text", ""),
    )

    def fake_process(*_args, **_kwargs):
        conversation.estado = EstadoConversacion.CONFIRMANDO
        return ""

    monkeypatch.setattr(main.ChatbotRules, "procesar_mensaje", fake_process)
    monkeypatch.setattr(
        main.conversation_session_service,
        "save_for_key",
        lambda *args, **kwargs: events.append("save") or {},
    )
    monkeypatch.setattr(
        main.ChatbotRules,
        "send_confirmacion_interactiva",
        lambda *_: events.append("prompt") or True,
    )
    monkeypatch.setattr(main, "send_message", lambda *_: True)

    response = _post_payload(client)

    assert response.status_code == 200
    assert events == ["save", "prompt"]


def test_confirmacion_interactiva_is_blocked_when_save_fails(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765435"
    sent_messages = []
    prompt_calls = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "Necesito ayuda", "wamid.text.2", "Usuario Test", "text", ""),
    )

    def fake_process(*_args, **_kwargs):
        conversation.estado = EstadoConversacion.CONFIRMANDO
        return ""

    monkeypatch.setattr(main.ChatbotRules, "procesar_mensaje", fake_process)

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(main.conversation_session_service, "save_for_key", fail_save)
    monkeypatch.setattr(
        main.ChatbotRules,
        "send_confirmacion_interactiva",
        lambda *_: prompt_calls.append("prompt") or True,
    )
    monkeypatch.setattr(
        main,
        "send_message",
        lambda user_id, message: sent_messages.append((user_id, message)) or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert prompt_calls == []
    assert sent_messages == [
        (phone, "❌ Hubo un error guardando tu sesión. Por favor intentá nuevamente."),
    ]
