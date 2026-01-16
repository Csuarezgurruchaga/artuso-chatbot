import json
import logging
import os
import unicodedata
from datetime import datetime, timezone
from typing import Optional, Tuple

try:
    from google.cloud import firestore
    from google.cloud import storage
except Exception:
    firestore = None
    storage = None

from config.company_profiles import get_active_company_profile

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _normalize_keyword(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text.strip().upper())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


class OptInService:
    def __init__(self) -> None:
        self.enabled = os.getenv("OPTIN_ENABLED", "true").lower() == "true"
        self.database = os.getenv("OPTIN_FIRESTORE_DATABASE", "default").strip() or "default"
        self.collection = os.getenv("OPTIN_FIRESTORE_COLLECTION", "opt-in").strip()
        self.bucket_name = os.getenv("OPTIN_GCS_BUCKET", "optin-audit").strip()
        self.optin_command = os.getenv("OPTIN_COMMAND", "optin").strip().lower()
        self.optout_keywords = self._parse_keywords(
            os.getenv("OPTIN_OUT_KEYWORDS", "BAJA,STOP")
        )
        self.resubscribe_keyword = _normalize_keyword(
            os.getenv("OPTIN_RESUBSCRIBE_KEYWORD", "ALTA")
        )
        self._fs_client = None
        self._storage_client = None
        self._bucket = None

    @staticmethod
    def _parse_keywords(raw: str) -> set:
        keywords = {k.strip() for k in raw.split(",")} if raw else set()
        return {_normalize_keyword(k) for k in keywords if k}

    def _get_firestore_client(self):
        if firestore is None:
            raise RuntimeError("google-cloud-firestore not installed")
        if self._fs_client is None:
            self._fs_client = firestore.Client(database=self.database)
        return self._fs_client

    def _get_bucket(self):
        if storage is None:
            raise RuntimeError("google-cloud-storage not installed")
        if self._storage_client is None:
            self._storage_client = storage.Client()
        if self._bucket is None:
            self._bucket = self._storage_client.bucket(self.bucket_name)
        return self._bucket

    @staticmethod
    def _normalize_whatsapp_identifier(raw_id: str) -> str:
        normalized = raw_id.replace("whatsapp:", "").strip()
        for ch in (" ", "-", "(", ")"):
            normalized = normalized.replace(ch, "")
        if normalized.startswith("+"):
            normalized = normalized[1:]
        return f"+{normalized}" if normalized else ""

    @staticmethod
    def _normalize_messenger_identifier(raw_id: str) -> str:
        normalized = raw_id.replace("messenger:", "").strip()
        return normalized

    def _doc_id(self, channel: str, identifier: str) -> str:
        return f"{channel}:{identifier}"

    def normalize_identifier(self, channel: str, identifier: str) -> str:
        if channel == "messenger":
            return self._normalize_messenger_identifier(identifier)
        return self._normalize_whatsapp_identifier(identifier)

    def _company_name(self) -> str:
        profile = get_active_company_profile()
        return profile.get("name", "la empresa")

    def _build_prompt(self) -> str:
        company = self._company_name()
        return (
            "Este numero será utilizado para recibir comunicaciones laborales de soporte y atención "
            f"de parte de {company}. Aceptas recibir estos mensajes?\n\n"
            "Responde SI para aceptar o NO para rechazar."
        )

    def _build_accepted(self) -> str:
        company = self._company_name()
        return (
            "Gracias por aceptar. A partir de ahora vas a recibir mensajes de soporte y atención "
            f"de {company}.\n\n"
            "Si en cualquier momento queres dejar de recibirlos, responde “BAJA” o “STOP”."
        )

    def _build_declined(self) -> str:
        company = self._company_name()
        return (
            f"Listo, no vas a recibir mensajes de {company}.\n"
            "Si cambias de idea, escribi ALTA para volver a aceptar."
        )

    def _build_optout_confirm(self) -> str:
        company = self._company_name()
        return (
            f"Listo, no vas a recibir mas mensajes de {company}.\n"
            "Si fue un error, escribi ALTA y te enviaremos nuevamente el consentimiento."
        )

    @staticmethod
    def _build_optout_already() -> str:
        return (
            "Tu baja ya estaba registrada.\n"
            "Si queres reactivar, escribi ALTA y te enviamos el consentimiento."
        )

    @staticmethod
    def get_optin_buttons() -> list:
        return [
            {"id": "SI", "title": "SI"},
            {"id": "NO", "title": "NO"},
        ]

    def _write_audit_event(
        self,
        channel: str,
        identifier: str,
        prompt_text: str,
        response: str,
    ) -> None:
        try:
            bucket = self._get_bucket()
            timestamp = _now_iso()
            date_path = _today_utc()
            safe_identifier = identifier.replace("/", "_")
            object_name = f"optin/{date_path}/{timestamp}_{safe_identifier}.json"
            payload = {
                "identifier": identifier,
                "channel": channel,
                "prompt_text": prompt_text,
                "response": response,
                "timestamp": timestamp,
            }
            blob = bucket.blob(object_name)
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=True),
                content_type="application/json",
            )
        except Exception as exc:
            logger.error("optin_audit_error channel=%s id=%s error=%s", channel, identifier, str(exc))

    def _get_status(self, channel: str, identifier: str) -> Tuple[Optional[str], str]:
        client = self._get_firestore_client()
        doc_id = self._doc_id(channel, identifier)
        snap = client.collection(self.collection).document(doc_id).get()
        if not snap.exists:
            return None, ""
        data = snap.to_dict() or {}
        return data.get("status"), data.get("prompt_text", "")

    def _set_status(
        self,
        channel: str,
        identifier: str,
        status: str,
        prompt_text: str,
        response: str,
    ) -> None:
        client = self._get_firestore_client()
        doc_id = self._doc_id(channel, identifier)
        client.collection(self.collection).document(doc_id).set(
            {
                "status": status,
                "prompt_text": prompt_text,
                "response": response,
                "updated_at": _now_iso(),
            }
        )

    def start_optin(self, channel: str, identifier: str) -> Optional[Tuple[str, bool]]:
        if not self.enabled:
            return None
        identifier = self.normalize_identifier(channel, identifier)
        prompt = self._build_prompt()
        self._set_status(channel, identifier, "pending", prompt, "")
        return prompt, channel == "whatsapp"

    def is_opted_in(self, channel: str, identifier: str) -> bool:
        if not self.enabled:
            return True
        identifier = self.normalize_identifier(channel, identifier)
        try:
            status, _ = self._get_status(channel, identifier)
            return status == "accepted"
        except Exception as exc:
            logger.error(
                "optin_check_error channel=%s id=%s error=%s",
                channel,
                identifier,
                str(exc),
            )
            return False

    def resolve_identifier(self, raw_id: str) -> Tuple[str, str]:
        if raw_id.startswith("messenger:"):
            return "messenger", self._normalize_messenger_identifier(raw_id)
        return "whatsapp", self._normalize_whatsapp_identifier(raw_id)

    def handle_inbound_message(self, raw_id: str, message: str) -> Tuple[bool, Optional[str], bool]:
        if not self.enabled:
            return False, None, False
        normalized = _normalize_keyword(message)
        if not normalized:
            return False, None, False
        if normalized not in self.optout_keywords and normalized not in {"SI", "NO", self.resubscribe_keyword}:
            return False, None, False

        channel, identifier = self.resolve_identifier(raw_id)

        try:
            status, prompt_text = self._get_status(channel, identifier)

            if normalized == self.resubscribe_keyword:
                prompt = self._build_prompt()
                self._set_status(channel, identifier, "pending", prompt, normalized)
                return True, prompt, channel == "whatsapp"

            if normalized in self.optout_keywords:
                if status == "accepted":
                    self._set_status(channel, identifier, "opted_out", prompt_text, normalized)
                    self._write_audit_event(channel, identifier, prompt_text, normalized)
                    return True, self._build_optout_confirm(), False
                if status == "opted_out":
                    self._set_status(channel, identifier, "opted_out", prompt_text, normalized)
                    self._write_audit_event(channel, identifier, prompt_text, normalized)
                    return True, self._build_optout_already(), False
                return False, None, False

            if normalized in {"SI", "NO"}:
                if status != "pending":
                    return False, None, False
                new_status = "accepted" if normalized == "SI" else "declined"
                self._set_status(channel, identifier, new_status, prompt_text, normalized)
                self._write_audit_event(channel, identifier, prompt_text, normalized)
                if normalized == "SI":
                    return True, self._build_accepted(), False
                return True, self._build_declined(), False

        except Exception as exc:
            logger.error(
                "optin_handle_error channel=%s id=%s error=%s",
                channel,
                identifier,
                str(exc),
            )
        return False, None, False


optin_service = OptInService()
