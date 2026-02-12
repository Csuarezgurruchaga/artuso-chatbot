import os
import sys
import threading

os.environ.setdefault("META_WA_ACCESS_TOKEN", "test_token")
os.environ.setdefault("META_WA_PHONE_NUMBER_ID", "123456789")
os.environ.setdefault("META_WA_APP_SECRET", "test_secret")
os.environ.setdefault("META_WA_VERIFY_TOKEN", "test_verify_token")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import config.company_profiles as company_profiles
from chatbot.rules import ChatbotRules
from services.meta_whatsapp_service import meta_whatsapp_service


def test_saludo_sticker_ignora_media_id_y_usa_url(monkeypatch) -> None:
    calls = []

    class _ImmediateThread:
        def __init__(self, target=None, args=(), kwargs=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}
            self.daemon = False

        def start(self):
            if self._target:
                self._target(*self._args, **self._kwargs)

    def _fake_send_sticker(_to, sticker_url=None, sticker_id=None):
        calls.append({"sticker_id": sticker_id, "sticker_url": sticker_url})
        return True

    monkeypatch.setenv("WHATSAPP_STICKER_MEDIA_ID", "invalid-media-id")
    monkeypatch.setenv(
        "WHATSAPP_STICKER_URL",
        "https://storage.googleapis.com/artuso-assets-prod/artuso/stickers/bot-v1.webp",
    )
    monkeypatch.setattr(threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        company_profiles,
        "get_active_company_profile",
        lambda: {"name": "administracion-artuso"},
    )
    monkeypatch.setattr(meta_whatsapp_service, "send_text_message", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(meta_whatsapp_service, "send_sticker", _fake_send_sticker)
    monkeypatch.setattr(ChatbotRules, "send_menu_interactivo", lambda *_args, **_kwargs: True)

    ChatbotRules._enviar_flujo_saludo_completo("5491135722872", "Cliente")

    assert len(calls) == 1
    assert calls[0]["sticker_id"] is None
    assert calls[0]["sticker_url"] == "https://storage.googleapis.com/artuso-assets-prod/artuso/stickers/bot-v1.webp"


def test_saludo_sticker_usa_url_desde_env_si_no_hay_media_id(monkeypatch) -> None:
    calls = []

    class _ImmediateThread:
        def __init__(self, target=None, args=(), kwargs=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}
            self.daemon = False

        def start(self):
            if self._target:
                self._target(*self._args, **self._kwargs)

    def _fake_send_sticker(_to, sticker_url=None, sticker_id=None):
        calls.append({"sticker_id": sticker_id, "sticker_url": sticker_url})
        return True

    monkeypatch.delenv("WHATSAPP_STICKER_MEDIA_ID", raising=False)
    monkeypatch.setenv(
        "WHATSAPP_STICKER_URL",
        "https://storage.googleapis.com/artuso-assets-prod/artuso/stickers/bot-v1.webp",
    )
    monkeypatch.setattr(threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        company_profiles,
        "get_active_company_profile",
        lambda: {"name": "Administracion Artuso"},
    )
    monkeypatch.setattr(meta_whatsapp_service, "send_text_message", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(meta_whatsapp_service, "send_sticker", _fake_send_sticker)
    monkeypatch.setattr(ChatbotRules, "send_menu_interactivo", lambda *_args, **_kwargs: True)

    ChatbotRules._enviar_flujo_saludo_completo("5491135722872", "Cliente")

    assert len(calls) == 1
    assert calls[0]["sticker_id"] is None
    assert calls[0]["sticker_url"] == "https://storage.googleapis.com/artuso-assets-prod/artuso/stickers/bot-v1.webp"
