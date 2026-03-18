import copy
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from google.cloud import firestore
except Exception:
    firestore = None

from chatbot.models import ConversacionData, DatosContacto, EstadoConversacion, TipoConsulta

logger = logging.getLogger(__name__)

CHECKPOINT_COLLECTION = "conversation-checkpoints"
DEFAULT_FIRESTORE_DATABASE = "default"
CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_TTL_HOURS = 24

RESUMABLE_STATES = {
    EstadoConversacion.RECOLECTANDO_DATOS,
    EstadoConversacion.RECOLECTANDO_DATOS_INDIVIDUALES,
    EstadoConversacion.RECOLECTANDO_SECUENCIAL,
    EstadoConversacion.ELIMINANDO_DIRECCION_GUARDADA,
    EstadoConversacion.VALIDANDO_UBICACION,
    EstadoConversacion.VALIDANDO_DATOS,
    EstadoConversacion.CONFIRMANDO,
    EstadoConversacion.CORRIGIENDO,
    EstadoConversacion.CORRIGIENDO_CAMPO,
}

CHECKPOINT_FIELDS = {
    "estado",
    "estado_anterior",
    "tipo_consulta",
    "nombre_usuario",
    "datos_temporales",
    "datos_contacto",
    "updated_at",
    "last_user_message_at",
    "expires_at",
    "schema_version",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _enum_value(value) -> Optional[str]:
    if value is None:
        return None
    return getattr(value, "value", value)


@dataclass
class ConversationCheckpoint:
    doc_id: str
    conversation: ConversacionData
    updated_at: datetime
    last_user_message_at: datetime
    expires_at: datetime
    schema_version: int


class ConversationSessionService:
    def __init__(self) -> None:
        self.database = DEFAULT_FIRESTORE_DATABASE
        self.collection = CHECKPOINT_COLLECTION
        self._fs_client = None

    def _get_firestore_client(self):
        if firestore is None:
            raise RuntimeError("google-cloud-firestore not installed")
        if self._fs_client is None:
            self._fs_client = firestore.Client(database=self.database)
        return self._fs_client

    @staticmethod
    def build_doc_id(channel: str, identifier: str) -> str:
        return f"{channel}:{identifier}"

    def _document(self, channel: str, identifier: str):
        client = self._get_firestore_client()
        doc_id = self.build_doc_id(channel, identifier)
        return doc_id, client.collection(self.collection).document(doc_id)

    def serialize(
        self,
        conversation: ConversacionData,
        *,
        last_user_message_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> dict:
        updated_at = _ensure_utc(updated_at) or _utc_now()
        last_user_message_at = _ensure_utc(last_user_message_at) or updated_at
        expires_at = last_user_message_at + timedelta(hours=CHECKPOINT_TTL_HOURS)
        payload = {
            "estado": _enum_value(conversation.estado),
            "estado_anterior": _enum_value(conversation.estado_anterior),
            "tipo_consulta": _enum_value(conversation.tipo_consulta),
            "nombre_usuario": conversation.nombre_usuario,
            "datos_temporales": copy.deepcopy(conversation.datos_temporales or {}),
            "datos_contacto": (
                conversation.datos_contacto.model_dump(mode="json")
                if conversation.datos_contacto
                else None
            ),
            "updated_at": updated_at,
            "last_user_message_at": last_user_message_at,
            "expires_at": expires_at,
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
        }
        return payload

    def hydrate(self, identifier: str, payload: dict, *, channel: str = "whatsapp") -> ConversationCheckpoint:
        raw = payload or {}
        estado = raw.get("estado", EstadoConversacion.INICIO.value)
        estado_anterior = raw.get("estado_anterior")
        tipo_consulta = raw.get("tipo_consulta")
        datos_contacto = raw.get("datos_contacto")
        updated_at = _ensure_utc(raw.get("updated_at")) or _utc_now()
        last_user_message_at = _ensure_utc(raw.get("last_user_message_at")) or updated_at
        expires_at = _ensure_utc(raw.get("expires_at")) or (
            last_user_message_at + timedelta(hours=CHECKPOINT_TTL_HOURS)
        )
        conversation = ConversacionData(
            numero_telefono=identifier,
            estado=EstadoConversacion(estado),
            estado_anterior=EstadoConversacion(estado_anterior) if estado_anterior else None,
            tipo_consulta=TipoConsulta(tipo_consulta) if tipo_consulta else None,
            nombre_usuario=raw.get("nombre_usuario"),
            datos_temporales=copy.deepcopy(raw.get("datos_temporales") or {}),
            datos_contacto=DatosContacto.model_validate(datos_contacto) if datos_contacto else None,
        )
        return ConversationCheckpoint(
            doc_id=self.build_doc_id(channel, identifier),
            conversation=conversation,
            updated_at=updated_at,
            last_user_message_at=last_user_message_at,
            expires_at=expires_at,
            schema_version=int(raw.get("schema_version") or CHECKPOINT_SCHEMA_VERSION),
        )

    def save(
        self,
        channel: str,
        identifier: str,
        conversation: ConversacionData,
        *,
        last_user_message_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> dict:
        doc_id, document = self._document(channel, identifier)
        payload = self.serialize(
            conversation,
            last_user_message_at=last_user_message_at,
            updated_at=updated_at,
        )
        document.set(payload)
        logger.info(
            "checkpoint_save doc_id=%s estado=%s",
            doc_id,
            payload["estado"],
        )
        return payload

    def load(self, channel: str, identifier: str) -> Optional[ConversationCheckpoint]:
        doc_id, document = self._document(channel, identifier)
        snapshot = document.get()
        if not snapshot.exists:
            return None
        checkpoint = self.hydrate(identifier, snapshot.to_dict() or {}, channel=channel)
        logger.info(
            "checkpoint_load doc_id=%s estado=%s",
            doc_id,
            _enum_value(checkpoint.conversation.estado),
        )
        return checkpoint

    def delete(self, channel: str, identifier: str) -> None:
        doc_id, document = self._document(channel, identifier)
        document.delete()
        logger.info("checkpoint_delete doc_id=%s", doc_id)

    @staticmethod
    def is_expired(expires_at: Optional[datetime], *, now: Optional[datetime] = None) -> bool:
        expires_at = _ensure_utc(expires_at)
        if expires_at is None:
            return False
        now = _ensure_utc(now) or _utc_now()
        return expires_at <= now


conversation_session_service = ConversationSessionService()
