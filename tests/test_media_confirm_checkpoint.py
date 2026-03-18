import json
import os
import sys

from fastapi.testclient import TestClient

from chatbot.models import EstadoConversacion
from services.conversation_session_service import ConversationSessionService

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


def _enable_memory_session_store(main, monkeypatch):
    serializer = ConversationSessionService()
    store = {}

    def save_for_key(conversation_key, conversation, **kwargs):
        payload = serializer.serialize(conversation, **kwargs)
        store[conversation_key] = payload
        return payload

    def load_for_key(conversation_key):
        payload = store.get(conversation_key)
        if payload is None:
            return None
        channel, identifier = serializer.resolve_channel_and_identifier(conversation_key)
        checkpoint = serializer.hydrate(identifier, payload, channel=channel)
        checkpoint.conversation.numero_telefono = conversation_key
        return checkpoint

    def delete_for_key(conversation_key):
        store.pop(conversation_key, None)

    monkeypatch.setattr(main.conversation_session_service, "save_for_key", save_for_key)
    monkeypatch.setattr(main.conversation_session_service, "load_for_key", load_for_key)
    monkeypatch.setattr(main.conversation_session_service, "delete_for_key", delete_for_key)
    return store


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


def test_final_save_runs_after_standard_resumable_response(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765436"
    events = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "Necesito ayuda", "wamid.text.3", "Usuario Test", "text", ""),
    )

    def fake_process(*_args, **_kwargs):
        conversation.estado = EstadoConversacion.RECOLECTANDO_SECUENCIAL
        return "seguimos"

    monkeypatch.setattr(main.ChatbotRules, "procesar_mensaje", fake_process)
    monkeypatch.setattr(
        main.conversation_session_service,
        "save_for_key",
        lambda *args, **kwargs: events.append("save") or {},
    )
    monkeypatch.setattr(
        main,
        "send_message",
        lambda *_args: events.append("send") or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert events == ["send", "save"]


def test_final_save_skips_non_resumable_state(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765437"
    save_calls = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "Necesito ayuda", "wamid.text.4", "Usuario Test", "text", ""),
    )

    def fake_process(*_args, **_kwargs):
        conversation.estado = EstadoConversacion.INICIO
        return "hola"

    monkeypatch.setattr(main.ChatbotRules, "procesar_mensaje", fake_process)
    monkeypatch.setattr(
        main.conversation_session_service,
        "save_for_key",
        lambda *args, **kwargs: save_calls.append(args) or {},
    )
    monkeypatch.setattr(main, "send_message", lambda *_: True)

    response = _post_payload(client)

    assert response.status_code == 200
    assert save_calls == []


def test_final_save_failure_does_not_block_response(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765438"
    sent_messages = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "Necesito ayuda", "wamid.text.5", "Usuario Test", "text", ""),
    )

    def fake_process(*_args, **_kwargs):
        conversation.estado = EstadoConversacion.RECOLECTANDO_SECUENCIAL
        return "seguimos"

    monkeypatch.setattr(main.ChatbotRules, "procesar_mensaje", fake_process)

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(main.conversation_session_service, "save_for_key", fail_save)
    monkeypatch.setattr(
        main,
        "send_message",
        lambda user_id, message: sent_messages.append((user_id, message)) or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert sent_messages == [(phone, "seguimos")]


def test_final_save_runs_after_interactive_response(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765439"
    events = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "btn_confirmar", "wamid.interactive.1", "Usuario Test", "interactive", ""),
    )

    async def fake_handle(*_args, **_kwargs):
        conversation.estado = EstadoConversacion.RECOLECTANDO_SECUENCIAL
        return "respuesta interactiva"

    monkeypatch.setattr(main, "handle_interactive_button", fake_handle)
    monkeypatch.setattr(
        main.conversation_session_service,
        "save_for_key",
        lambda *args, **kwargs: events.append("save") or {},
    )
    monkeypatch.setattr(
        main,
        "send_message",
        lambda *_args: events.append("send") or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert events == ["send", "save"]


def test_media_flow_resumes_after_cold_start_and_button_reply(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765440"
    store = _enable_memory_session_store(main, monkeypatch)

    main.conversation_manager.reset_conversacion(phone)

    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "media:test-media", "wamid.media.resume", "Usuario Test", "image", ""),
    )
    monkeypatch.setattr(main.meta_whatsapp_service, "download_media", lambda *_: (b"img", "image/jpeg"))

    from services.gcs_storage_service import gcs_storage_service

    monkeypatch.setattr(gcs_storage_service, "upload_public", lambda *_: "https://example.com/test.jpg")
    monkeypatch.setattr(main.ChatbotRules, "send_media_confirmacion", lambda *_: True)
    monkeypatch.setattr(main.ChatbotRules, "send_fecha_pago_hoy_button", lambda *_: True)
    monkeypatch.setattr(main, "send_message", lambda *_: True)

    first_response = _post_payload(client)

    assert first_response.status_code == 200
    assert store[phone]["datos_temporales"]["_media_confirmacion"] is True
    assert store[phone]["estado"] == EstadoConversacion.CONFIRMANDO_MEDIA.value

    main.conversation_manager.conversaciones.clear()
    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "media_expensas_si", "wamid.media.resume.2", "Usuario Test", "interactive", ""),
    )

    second_response = _post_payload(client)

    assert second_response.status_code == 200
    conversation = main.conversation_manager.conversaciones[phone]
    assert conversation.estado == EstadoConversacion.RECOLECTANDO_SECUENCIAL
    assert conversation.datos_temporales["comprobante"] == ["https://example.com/test.jpg"]
    assert store[phone]["estado"] == EstadoConversacion.RECOLECTANDO_SECUENCIAL.value


def test_correction_flow_resumes_after_cold_start(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765441"
    store = _enable_memory_session_store(main, monkeypatch)
    sent_messages = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)
    conversation.estado = EstadoConversacion.CORRIGIENDO_CAMPO
    conversation.tipo_consulta = "pago_expensas"
    conversation.datos_temporales.update(
        {
            "_campo_a_corregir": "fecha_pago",
            "monto": "42000",
            "direccion": "Av Siempre Viva 742",
            "piso_depto": "2A",
        }
    )
    main.conversation_session_service.save_for_key(phone, conversation)

    main.conversation_manager.conversaciones.clear()
    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "fecha_hoy", "wamid.correction.1", "Usuario Test", "interactive", ""),
    )
    monkeypatch.setattr(
        main,
        "send_message",
        lambda user_id, message: sent_messages.append((user_id, message)) or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert sent_messages
    assert sent_messages[0][0] == phone
    assert sent_messages[0][1].startswith("✅ Campo actualizado correctamente.")
    assert store[phone]["estado"] == EstadoConversacion.CONFIRMANDO.value
    assert store[phone]["datos_temporales"]["fecha_pago"]


def test_final_confirmation_survives_cold_start(monkeypatch):
    main, client = _build_client(monkeypatch)
    phone = "+5491198765442"
    _enable_memory_session_store(main, monkeypatch)
    sent_messages = []

    main.conversation_manager.reset_conversacion(phone)
    conversation = main.conversation_manager.get_conversacion(phone)
    conversation.estado = EstadoConversacion.CONFIRMANDO
    conversation.tipo_consulta = "pago_expensas"
    conversation.datos_temporales.update(
        {
            "fecha_pago": "12/03/2026",
            "monto": "42000",
            "direccion": "Av Siempre Viva 742",
            "piso_depto": "2A",
        }
    )
    main.conversation_session_service.save_for_key(phone, conversation)

    main.conversation_manager.conversaciones.clear()
    monkeypatch.setattr(
        main.meta_whatsapp_service,
        "extract_message_data",
        lambda *_: (phone, "si", "wamid.confirm.1", "Usuario Test", "interactive", ""),
    )
    monkeypatch.setattr(
        main,
        "send_message",
        lambda user_id, message: sent_messages.append((user_id, message)) or True,
    )

    response = _post_payload(client)

    assert response.status_code == 200
    assert sent_messages == [(phone, "⏳ Procesando tu solicitud...")]
    assert main.conversation_manager.conversaciones[phone].estado == EstadoConversacion.ENVIANDO
