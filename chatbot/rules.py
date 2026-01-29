import logging
import os
import re
import unicodedata
from typing import Optional
from .models import EstadoConversacion, TipoConsulta
from .states import conversation_manager
from config.company_profiles import get_active_company_profile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation

POST_FINALIZADO_WINDOW_SECONDS = int(os.getenv("POST_FINALIZADO_WINDOW_SECONDS", "120"))
POST_FINALIZADO_ACK_MESSAGE = os.getenv(
    "POST_FINALIZADO_ACK_MESSAGE",
    "¡Gracias por tu mensaje! Ya registramos tu solicitud. Si necesitás otra cosa, escribime \"hola\" para comenzar de nuevo. 🤖",
)
AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
RATE_LIMIT_MESSAGE = (
    "Por hoy ya alcanzaste el máximo de 10 interacciones 😊 "
    "Mañana podés volver a usar el servicio sin problema!"
)
EMERGENCY_NUMBER_ENV = "HANDOFF_EMERGENCY_WHATSAPP_NUMBER"
EMERGENCY_PAUSED_FLAG = "_emergency_paused"
EMERGENCY_MESSAGE_CACHE = "_emergency_message_cache"


def _fecha_argentina(days_delta: int = 0) -> str:
    fecha = datetime.now(AR_TZ) + timedelta(days=days_delta)
    return fecha.strftime("%d/%m/%Y")


def _parse_fecha_hoy_ayer(texto: str) -> Optional[str]:
    if not texto:
        return None
    normalized = texto.strip().lower()
    if normalized == "hoy":
        return _fecha_argentina(0)
    if normalized == "ayer":
        return _fecha_argentina(-1)
    return None

def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto: lowercase + sin acentos + sin espacios + sin puntos
    """
    texto = texto.lower().strip()
    # Remover acentos
    sin_acentos = ''.join(c for c in unicodedata.normalize('NFD', texto) 
                          if unicodedata.category(c) != 'Mn')
    # Remover espacios y puntos para mejor matching (bsas = bs as = bs. as.)
    return sin_acentos.replace(' ', '').replace('.', '')

# Mapeo de sinónimos para validación geográfica (solo minúsculas, se normalizan automáticamente)
SINONIMOS_CABA = [
    'caba', 'c.a.b.a', 'ciudad autonoma', 
    'capital', 'capital federal', 'microcentro', 'palermo', 
    'recoleta', 'san telmo', 'puerto madero', 'belgrano',
    'barracas', 'boca', 'caballito', 'flores', 'once',
    'retiro', 'villa crespo', 'almagro', 'balvanera'
]

SINONIMOS_PROVINCIA = [
    'provincia', 'prov', 'buenos aires', 'bs as', 'bs. as.',
    'gba', 'gran buenos aires', 'zona norte', 'zona oeste', 
    'zona sur', 'la plata', 'quilmes', 'lomas de zamora',
    'san isidro', 'tigre', 'pilar', 'escobar', 'moreno',
    'merlo', 'moron', 'tres de febrero', 'vicente lopez',
    'avellaneda', 'lanus', 'berazategui', 'florencio varela',
    'ramos mejia'
]

# Sets pre-computados normalizados para búsqueda O(1)
SINONIMOS_CABA_NORM = {normalizar_texto(s) for s in SINONIMOS_CABA}
SINONIMOS_PROVINCIA_NORM = {normalizar_texto(s) for s in SINONIMOS_PROVINCIA}

class ChatbotRules:
    GREETING_COMMANDS = {
        "hola",
        "holi",
        "holis",
        "hi",
        "hello",
        "inicio",
        "empezar",
        "h",
        "alo",
        "ola",
    }
    MENU_OPTIONS = (
        {
            "id": "pago_expensas",
            "title": "Registrar expensas",
            "text": "Registrar expensas",
            "tipo": TipoConsulta.PAGO_EXPENSAS,
        },
        {
            "id": "solicitar_servicio",
            "title": "Reclamos",
            "text": "Reclamos",
            "tipo": TipoConsulta.SOLICITAR_SERVICIO,
        },
        {
            "id": "emergencia",
            "title": "Informar emergencia",
            "text": "Informar emergencia",
            "tipo": TipoConsulta.EMERGENCIA,
        },
    )
    MENU_NUMBER_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}
    MENU_MATCH_PRIORITY = ("emergencia", "pago_expensas", "solicitar_servicio")
    MENU_STOPWORDS = {"un", "una", "de", "del", "la", "el", "las", "los", "para", "por", "a", "y", "en"}
    EXTRA_MENU_KEYWORDS = {
        "pago_expensas": ["expensas", "pago", "abono", "registrar", "registro", "informar"],
        "solicitar_servicio": [
            "servicio",
            "servicios",
            "reclamo",
            "reclamos",
            "arreglo",
            "reparacion",
            "reparación",
            "destapacion",
            "destapación",
            "humedad",
            "fumigacion",
            "fumigación",
            "desinfeccion",
            "desinfección",
            "cucaracha",
            "cucarachas",
            "rata",
            "ratas",
            "plaga",
            "plagas",
            "roedor",
            "roedores",
        ],
        "emergencia": ["emergencia", "urgente", "urgencia", "auxilio", "peligro"],
    }
    _MENU_KEYWORDS = None
    SERVICE_TYPE_OPTIONS = (
        {"id": "servicio_destapacion", "title": "Destapación", "value": "Destapación"},
        {
            "id": "servicio_filtracion_humedad",
            "title": "Filtracion/Humedad",
            "value": "Filtracion/Humedad",
        },
        {"id": "servicio_pintura", "title": "Pintura", "value": "Pintura"},
        {"id": "servicio_ruidos", "title": "Ruidos Molestos", "value": "Ruidos Molestos"},
        {"id": "servicio_otro", "title": "Otro reclamo", "value": "Otro reclamo"},
    )
    MAX_DIRECCIONES_GUARDADAS = 5

    GRATITUDE_KEYWORDS = {
        "gracias",
        "muchas gracias",
        "mil gracias",
        "gracias totales",
        "gracias artu",
        "gracias genia",
        "gracias por todo",
        "gracias!!!",
        "gracias!!",
        "genial gracias",
        "buenísimo gracias",
        "graciass",
        "graciasss",
        "grac",
        "thank you",
        "thanks",
    }
    GRATITUDE_EMOJIS = {"🙏", "🤝", "👍", "🙌", "😊", "😁", "🤗", "👌"}

    @staticmethod
    def _format_emergency_number() -> Optional[str]:
        raw = os.getenv(EMERGENCY_NUMBER_ENV, "").strip()
        logger = logging.getLogger(__name__)
        if not raw:
            logger.error("emergency_number_missing env=%s", EMERGENCY_NUMBER_ENV)
            return None

        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 10:
            digits = digits[-10:]
        if len(digits) != 10 or not digits.startswith("11"):
            logger.error(
                "emergency_number_invalid env=%s value=%s", EMERGENCY_NUMBER_ENV, raw
            )
            return None
        return f"11-{digits[2:6]}-{digits[6:]}"

    @staticmethod
    def _build_emergency_message(formatted_number: str) -> str:
        return (
            "🚨 *Emergencia detectada*\n\n"
            "Para una atención inmediata, comunicate directamente con nuestro equipo al siguiente número:\n\n"
            f"📞 *{formatted_number}*\n\n"
            "Este canal es el más rápido para resolver situaciones urgentes.\n"
            "El chatbot no gestiona emergencias en tiempo real."
        )

    @staticmethod
    def _is_emergency_paused(conversacion) -> bool:
        return conversacion.datos_temporales.get(EMERGENCY_PAUSED_FLAG) is True

    @staticmethod
    def _set_emergency_pause(numero_telefono: str, message: str):
        conversation_manager.set_datos_temporales(
            numero_telefono, EMERGENCY_PAUSED_FLAG, True
        )
        conversation_manager.set_datos_temporales(
            numero_telefono, EMERGENCY_MESSAGE_CACHE, message
        )

    @staticmethod
    def _clear_emergency_pause(numero_telefono: str):
        conversation_manager.set_datos_temporales(
            numero_telefono, EMERGENCY_PAUSED_FLAG, False
        )
        conversation_manager.set_datos_temporales(
            numero_telefono, EMERGENCY_MESSAGE_CACHE, None
        )

    @staticmethod
    def _is_resume_command(mensaje_limpio: str) -> bool:
        return mensaje_limpio.strip().lower() == "continuar"

    @staticmethod
    def _is_midflow_state(conversacion) -> bool:
        return conversacion.estado not in {
            EstadoConversacion.INICIO,
            EstadoConversacion.ESPERANDO_OPCION,
            EstadoConversacion.ATENDIDO_POR_HUMANO,
        }

    @staticmethod
    def _detect_emergency_intent(mensaje: str, conversacion=None) -> bool:
        if not mensaje:
            return False
        # Evitar llamada a NLU por saludos comunes (primer mensaje típico).
        if ChatbotRules._is_greeting_command(mensaje):
            return False
        menu_context = conversacion and conversacion.estado in {
            EstadoConversacion.INICIO,
            EstadoConversacion.ESPERANDO_OPCION,
        }

        # Solo permitir detección por keywords/frases del menú si estamos en contexto de menú.
        # Fuera del menú, la detección de emergencia se delega a NLU (OpenAI) para minimizar falsos positivos.
        if menu_context:
            opcion, _ = ChatbotRules._match_menu_option(mensaje)
            if opcion and opcion.get("tipo") == TipoConsulta.EMERGENCIA:
                return True

        try:
            from services.nlu_service import nlu_service

            intent = nlu_service.mapear_intencion(mensaje)
            return intent == TipoConsulta.EMERGENCIA
        except Exception:
            return False

    @staticmethod
    def _handle_emergency(numero_telefono: str, conversacion, mensaje_original: str = "") -> Optional[str]:
        logger = logging.getLogger(__name__)
        formatted_number = ChatbotRules._format_emergency_number()
        if not formatted_number:
            return None

        emergency_message = ChatbotRules._build_emergency_message(formatted_number)
        logger.info("emergency_detected phone=%s state=%s", numero_telefono, conversacion.estado)

        if conversacion.atendido_por_humano or conversacion.estado == EstadoConversacion.ATENDIDO_POR_HUMANO:
            conversation_manager.set_datos_temporales(
                numero_telefono, EMERGENCY_MESSAGE_CACHE, emergency_message
            )
            return emergency_message

        if ChatbotRules._is_midflow_state(conversacion):
            ChatbotRules._set_emergency_pause(numero_telefono, emergency_message)
            return emergency_message

        conversation_manager.finalizar_conversacion(numero_telefono)
        return emergency_message

    @staticmethod
    def _emergency_message_cached(numero_telefono: str) -> Optional[str]:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        cached = conversacion.datos_temporales.get(EMERGENCY_MESSAGE_CACHE)
        if cached:
            return cached
        formatted_number = ChatbotRules._format_emergency_number()
        if not formatted_number:
            return None
        return ChatbotRules._build_emergency_message(formatted_number)

    @classmethod
    def _get_menu_options(cls):
        return cls.MENU_OPTIONS

    @classmethod
    def _build_menu_lines(cls) -> str:
        lines = []
        for idx, option in enumerate(cls.MENU_OPTIONS, start=1):
            emoji = cls.MENU_NUMBER_EMOJI.get(idx, f"{idx}️⃣")
            lines.append(f"{emoji} {option['text']}")
        return "\n".join(lines)

    @classmethod
    def _normalize_menu_text(cls, text: str) -> str:
        text = text.lower().strip()
        text = ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        text = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text)
        text = " ".join(text.split())
        # Colapsa alargamientos (>=3 repeticiones) sin romper letras dobles reales (ll/rr/etc).
        text = re.sub(r"(.)\1{2,}", r"\1", text)
        return text

    @staticmethod
    def _normalize_greeting_command(text: str) -> str:
        """Normaliza comandos cortos (p.ej. 'hola!') sin afectar el texto para NLU."""
        if not text:
            return ""
        normalized = text.strip().lower()
        normalized = "".join(
            c
            for c in unicodedata.normalize("NFD", normalized)
            if unicodedata.category(c) != "Mn"
        )
        normalized = " ".join(normalized.split())
        # Remueve puntuación y símbolos comunes solo en los bordes (no en el medio).
        normalized = normalized.strip(" \t\n\r¡!¿?.,;:()[]{}\"'`~*_")
        return " ".join(normalized.split())

    @staticmethod
    def _squeeze_repeated_chars(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"(.)\1+", r"\1", text)

    @staticmethod
    def _is_single_transposition(a: str, b: str) -> bool:
        if len(a) != len(b) or a == b:
            return False
        diffs = [i for i, (ca, cb) in enumerate(zip(a, b)) if ca != cb]
        if len(diffs) != 2:
            return False
        i, j = diffs
        if j != i + 1:
            return False
        a_list = list(a)
        a_list[i], a_list[j] = a_list[j], a_list[i]
        return "".join(a_list) == b

    @staticmethod
    def _edit_distance_at_most_one(a: str, b: str) -> bool:
        """Chequea si la distancia de edición (ins/del/subst) es <= 1."""
        if a == b:
            return True
        la, lb = len(a), len(b)
        if abs(la - lb) > 1:
            return False

        # Substitución (misma longitud)
        if la == lb:
            mismatches = sum(1 for ca, cb in zip(a, b) if ca != cb)
            return mismatches <= 1

        # Inserción/eliminación (longitud difiere en 1)
        if la > lb:
            longer, shorter = a, b
        else:
            longer, shorter = b, a
        i = j = 0
        used_edit = False
        while i < len(longer) and j < len(shorter):
            if longer[i] == shorter[j]:
                i += 1
                j += 1
                continue
            if used_edit:
                return False
            used_edit = True
            i += 1  # saltar un char en el string más largo
        return True

    @classmethod
    def _is_hola_typo(cls, token: str) -> bool:
        if not token or " " in token:
            return False
        token = cls._squeeze_repeated_chars(token)
        if not token.isalpha():
            return False
        # Evitar falsos positivos tipo "hora": pedimos 'h' + 'o' + 'l'
        if not token.startswith("h"):
            return False
        if "o" not in token or "l" not in token:
            return False
        if len(token) < 3 or len(token) > 6:
            return False
        if token in {"hol", "hola"}:
            return True
        if cls._is_single_transposition(token, "hola"):
            return True
        return cls._edit_distance_at_most_one(token, "hola")

    @classmethod
    def _is_greeting_command(cls, message_text: str) -> bool:
        token = cls._normalize_greeting_command(message_text)
        if token in cls.GREETING_COMMANDS:
            return True
        return cls._is_hola_typo(token)

    @classmethod
    def _get_menu_keywords(cls) -> dict:
        if cls._MENU_KEYWORDS is not None:
            return cls._MENU_KEYWORDS
        keywords = {}
        for option in cls.MENU_OPTIONS:
            tokens = set()
            for raw in (option["id"], option["text"], option["title"]):
                normalized = cls._normalize_menu_text(raw)
                if normalized:
                    tokens.update(normalized.split())
            for extra in cls.EXTRA_MENU_KEYWORDS.get(option["id"], []):
                normalized = cls._normalize_menu_text(extra)
                if normalized:
                    tokens.update(normalized.split())
            tokens = {t for t in tokens if t not in cls.MENU_STOPWORDS and len(t) > 2}
            keywords[option["id"]] = tokens
        cls._MENU_KEYWORDS = keywords
        return keywords

    @classmethod
    def _get_menu_option_by_id(cls, option_id: str):
        for option in cls.MENU_OPTIONS:
            if option["id"] == option_id:
                return option
        return None

    @classmethod
    def _match_menu_option(cls, mensaje: str):
        if not mensaje:
            return None, ""
        digits = re.findall(r"\d", mensaje)
        if len(digits) == 1:
            idx = int(digits[0])
            if 1 <= idx <= len(cls.MENU_OPTIONS):
                return cls.MENU_OPTIONS[idx - 1], "number"
        normalized = cls._normalize_menu_text(mensaje)
        if not normalized:
            return None, ""
        # Frases específicas para mapear a emergencia SOLO desde el inicio/menú.
        # (No se usan en la detección global de emergencia para no interrumpir flujos en curso.)
        emergency_option = cls._get_menu_option_by_id("emergencia")
        if emergency_option:
            emergency_phrases = (
                "sin agua",
                "corte de agua",
                "agua cortada",
                "falta de agua",
                "no hay agua",
                "baja presion",
                "baja presion de agua",
                "poca presion",
                "poca presion de agua",
                "sin gas",
                "corte de gas",
                "gas cortado",
                "no hay gas",
            )
            for phrase in emergency_phrases:
                if re.search(rf"\b{re.escape(phrase)}\b", normalized):
                    return emergency_option, "keyword_phrase"
        for option in cls.MENU_OPTIONS:
            if normalized == option["id"]:
                return option, "id"
        message_tokens = set(normalized.split())
        keywords = cls._get_menu_keywords()
        for option_id in cls.MENU_MATCH_PRIORITY:
            if keywords.get(option_id, set()) & message_tokens:
                return cls._get_menu_option_by_id(option_id), "keyword"
        return None, ""

    @classmethod
    def _match_service_option(cls, mensaje: str) -> Optional[str]:
        if not mensaje:
            return None
        normalized = cls._normalize_menu_text(mensaje)
        if not normalized:
            return None
        for option in cls.SERVICE_TYPE_OPTIONS:
            option_norm = cls._normalize_menu_text(option["value"])
            if normalized == option_norm:
                return option["value"]
        if "destap" in normalized:
            return "Destapación"
        if "filtracion" in normalized or "humed" in normalized:
            return "Filtracion/Humedad"
        if "pintur" in normalized or "pintar" in normalized:
            return "Pintura"
        if "ruido" in normalized or "molest" in normalized:
            return "Ruidos Molestos"
        if "otro" in normalized:
            return "Otro reclamo"
        return None

    @classmethod
    def _build_menu_prompt(cls) -> str:
        return f"""

¿En qué puedo ayudarte hoy? Seleccioná una opción:

{cls._build_menu_lines()}

Responde con el número de la opción que necesitas 📱"""
    
    @staticmethod
    def _normalizar_agradecimiento(texto: str) -> str:
        texto = texto.strip().lower()
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
        texto = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in texto)
        texto = " ".join(texto.split())
        return texto
    
    @staticmethod
    def es_mensaje_agradecimiento(texto: str) -> bool:
        if not texto:
            return False
        
        raw = texto.strip()
        # Emojis o reacciones cortas
        if raw and len(raw) <= 8 and any(emoji in raw for emoji in ChatbotRules.GRATITUDE_EMOJIS):
            return True
        
        normalizado = ChatbotRules._normalizar_agradecimiento(raw)
        if not normalizado:
            return False
        
        if normalizado in ChatbotRules.GRATITUDE_KEYWORDS:
            return True
        
        compact = normalizado.replace(" ", "")
        if compact in {"gracias", "muchasgracias", "milgracias", "graciass", "graciasss", "thankyou"}:
            return True
        
        for keyword in ChatbotRules.GRATITUDE_KEYWORDS:
            if keyword in normalizado:
                return True
        
        palabras = set(normalizado.split())
        if "gracias" in palabras or "thanks" in palabras:
            return True
        
        return False
    
    @staticmethod
    def get_mensaje_post_finalizado_gracias() -> str:
        return POST_FINALIZADO_ACK_MESSAGE
    
    @staticmethod
    def _detectar_volver_menu(mensaje: str) -> bool:
        """
        Detecta si el usuario quiere volver al menú principal
        """
        mensaje_lower = mensaje.lower().strip()
        frases_menu = [
            'menu', 'menú', 'menu principal', 'menú principal'
        ]
        
        return any(frase in mensaje_lower for frase in frases_menu)

    @staticmethod
    def _activar_handoff(numero_telefono: str, mensaje_contexto: str):
        conversation_manager.update_estado(numero_telefono, EstadoConversacion.ATENDIDO_POR_HUMANO)
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        conversacion.atendido_por_humano = True
        conversacion.handoff_started_at = datetime.utcnow()
        conversacion.last_client_message_at = datetime.utcnow()
        conversacion.mensaje_handoff_contexto = mensaje_contexto
        conversation_manager.add_to_handoff_queue(numero_telefono)

    @staticmethod
    def _aplicar_tipo_consulta(numero_telefono: str, tipo_consulta: TipoConsulta, mensaje: str, source: str, handoff_contexto: str = "") -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        adjuntos_pendientes = conversacion.datos_temporales.get("adjuntos_pendientes") or []
        caption_pendiente = conversacion.datos_temporales.get("adjuntos_pendientes_caption", "")

        import logging
        logger = logging.getLogger(__name__)

        if tipo_consulta == TipoConsulta.EMERGENCIA:
            respuesta_emergencia = ChatbotRules._handle_emergency(numero_telefono, conversacion, mensaje)
            return respuesta_emergencia or ""

        conversation_manager.set_tipo_consulta(numero_telefono, tipo_consulta)
        conversation_manager.clear_datos_temporales(numero_telefono)
        if adjuntos_pendientes:
            conversation_manager.set_datos_temporales(
                numero_telefono,
                "adjuntos_pendientes",
                adjuntos_pendientes,
            )
        if caption_pendiente:
            conversation_manager.set_datos_temporales(
                numero_telefono,
                "adjuntos_pendientes_caption",
                caption_pendiente,
            )
        try:
            from services.metrics_service import metrics_service

            metrics_service.on_intent(tipo_consulta.value)
        except Exception:
            pass

        if tipo_consulta == TipoConsulta.EMERGENCIA:
            contexto = handoff_contexto or mensaje.strip() or "Emergencia"
            ChatbotRules._activar_handoff(numero_telefono, contexto)
            return "Detectamos una emergencia. Te conecto con un agente ahora mismo. 🚨"

        conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_SECUENCIAL)

        if tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            if adjuntos_pendientes:
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "comprobante",
                    list(adjuntos_pendientes),
                )
                conversation_manager.set_datos_temporales(numero_telefono, "adjuntos_pendientes", None)
            if not numero_telefono.startswith("messenger:"):
                success = ChatbotRules.send_fecha_pago_hoy_button(numero_telefono)
                if success:
                    respuesta_inicio = ""
                    if caption_pendiente and source != "media":
                        conversation_manager.set_datos_temporales(
                            numero_telefono,
                            "adjuntos_pendientes_caption",
                            None,
                        )
                        respuesta_caption = ChatbotRules.procesar_mensaje(
                            numero_telefono,
                            caption_pendiente,
                            conversacion.nombre_usuario or "",
                        )
                        return respuesta_caption or respuesta_inicio
                    return respuesta_inicio
            respuesta_inicio = ChatbotRules._get_pregunta_campo_secuencial("fecha_pago")
            if caption_pendiente and source != "media":
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "adjuntos_pendientes_caption",
                    None,
                )
                respuesta_caption = ChatbotRules.procesar_mensaje(
                    numero_telefono,
                    caption_pendiente,
                    conversacion.nombre_usuario or "",
                )
                return respuesta_caption or respuesta_inicio
            return respuesta_inicio

        if tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            if adjuntos_pendientes:
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "adjuntos_servicio",
                    list(adjuntos_pendientes),
                )
                conversation_manager.set_datos_temporales(numero_telefono, "adjuntos_pendientes", None)
            mensaje_tipo = (
                "Perfecto 👍\n"
                "Para ayudarte mejor, voy a hacerte unas preguntas cortitas.\n"
                "¿Qué tipo de reclamo queres realizar?"
            )
            success = ChatbotRules.send_service_type_buttons(numero_telefono, mensaje_tipo)
            if success:
                return ""
            return (
                f"{mensaje_tipo}\n"
                "Opciones: Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos, Otro reclamo."
            )

        return ChatbotRules.get_mensaje_error_opcion()

    @staticmethod
    def _aplicar_opcion_menu(numero_telefono: str, opcion: dict, mensaje: str, source: str) -> str:
        handoff_contexto = ""
        if source == "button":
            handoff_contexto = opcion.get("text", "") or opcion.get("id", "")
        return ChatbotRules._aplicar_tipo_consulta(
            numero_telefono,
            opcion["tipo"],
            mensaje,
            source,
            handoff_contexto=handoff_contexto,
        )
    
    @staticmethod
    def get_mensaje_inicial() -> str:
        return (
            "¡Hola! 👋 Mi nombre es Artu."
            + ChatbotRules._build_menu_prompt()
        )
    
    @staticmethod
    def get_mensaje_inicial_personalizado(nombre_usuario: str = "") -> str:
        """
        Genera saludo personalizado estático con nombre si está disponible
        """
        # Saludo personalizado simple sin OpenAI
        if nombre_usuario:
            saludo = f"¡Hola {nombre_usuario}! 👋🏻 Mi nombre es Artu."
        else:
            saludo = "¡Hola! 👋🏻 Mi nombre es Artu."

        return saludo + ChatbotRules._build_menu_prompt()
    
    @staticmethod
    def send_menu_interactivo(numero_telefono: str, nombre_usuario: str = ""):
        """
        Envía el menú principal con botones interactivos reales
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        mensaje_menu = "¿En qué puedo ayudarte hoy?"
        buttons = [
            {"id": option["id"], "title": option["title"]}
            for option in ChatbotRules.MENU_OPTIONS
        ]

        footer_text = "Seleccioná una opción para continuar"

        success = meta_whatsapp_service.send_interactive_buttons(
            numero_telefono,
            body_text=mensaje_menu,
            buttons=buttons,
            footer_text=footer_text
        )

        if success:
            logger.info(f"✅ Menú interactivo enviado a {numero_telefono}")
            return True

        logger.error(f"❌ Error enviando menú interactivo a {numero_telefono}")
        mensaje_fallback = ChatbotRules.get_mensaje_inicial_personalizado(nombre_usuario)
        meta_whatsapp_service.send_text_message(numero_telefono, mensaje_fallback)
        return False

    @staticmethod
    def send_service_type_buttons(numero_telefono: str, body_text: str) -> bool:
        """
        Envía lista interactiva para seleccionar el tipo de reclamo.
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        rows = []
        for option in ChatbotRules.SERVICE_TYPE_OPTIONS:
            title = ChatbotRules._truncate_text(option["title"], 24)
            rows.append({"id": option["id"], "title": title})

        sections = [{"title": "Tipos de reclamo", "rows": rows}]
        success = meta_whatsapp_service.send_interactive_list(
            numero_telefono,
            body_text=body_text,
            button_text="Elegir opción",
            sections=sections,
        )

        if success:
            logger.info(f"✅ Lista de reclamos enviada a {numero_telefono}")
            return True

        logger.error(f"❌ Error enviando lista de reclamos a {numero_telefono}")
        return False
    
    @staticmethod
    def send_handoff_buttons(numero_telefono: str):
        """
        Envía botones de navegación después del handoff
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging
        logger = logging.getLogger(__name__)
        
        mensaje = (
            "Ya me contacté con el equipo; en breve uno de nuestros asesores se unirá a la charla. 🙌\n"
            "Por favor aguardá un momento."
        )
        
        # Enviar mensaje
        success = meta_whatsapp_service.send_text_message(numero_telefono, mensaje)
        
        if success:
            logger.info(f"✅ Botones de handoff enviados a {numero_telefono}")
        else:
            logger.error(f"❌ Error enviando botones de handoff a {numero_telefono}")
        
        return success
    
    @staticmethod
    def send_confirmation_buttons(numero_telefono: str, mensaje: str):
        """
        Envía botones de confirmación (Sí/No) interactivos
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging
        logger = logging.getLogger(__name__)

        buttons = [
            {"id": "si", "title": "✅ Sí"},
            {"id": "no", "title": "❌ No"},
        ]

        success = meta_whatsapp_service.send_interactive_buttons(
            numero_telefono,
            body_text=mensaje,
            buttons=buttons,
            footer_text="Seleccioná una opción para continuar",
        )

        if success:
            logger.info("✅ Botones de confirmación enviados a %s", numero_telefono)
            return True

        logger.error("❌ Error enviando botones de confirmación a %s", numero_telefono)
        fallback = f"{mensaje}\n\nResponde SI para confirmar o NO para corregir."
        meta_whatsapp_service.send_text_message(numero_telefono, fallback)
        return False

    @staticmethod
    def send_media_confirmacion(numero_telefono: str) -> bool:
        """
        Envía confirmación para identificar si un media es pago de expensas.
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        buttons = [
            {"id": "media_expensas_si", "title": "Si"},
            {"id": "media_expensas_no", "title": "No"},
        ]

        success = meta_whatsapp_service.send_interactive_buttons(
            numero_telefono,
            body_text="Este archivo es un pago de expensas?",
            buttons=buttons,
        )

        if success:
            logger.info("media_confirm_prompted phone=%s", numero_telefono)
            return True

        logger.error("media_confirm_prompt_failed phone=%s", numero_telefono)
        meta_whatsapp_service.send_text_message(
            numero_telefono,
            "Este archivo es un pago de expensas? Responde SI o NO.",
        )
        return False

    @staticmethod
    def _procesar_confirmacion_media(numero_telefono: str, mensaje: str) -> Optional[str]:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        if not conversacion.datos_temporales.get("_media_confirmacion"):
            return None

        import logging
        logger = logging.getLogger(__name__)

        respuesta = mensaje.strip().lower()
        acepta = {"si", "sí", "1", "1️⃣"}
        rechaza = {"no", "2", "2️⃣"}

        if respuesta in acepta:
            conversacion.datos_temporales["_media_confirmacion"] = None
            logger.info("media_confirmed_as_expensas phone=%s", numero_telefono)
            respuesta_inicio = ChatbotRules._aplicar_tipo_consulta(
                numero_telefono,
                TipoConsulta.PAGO_EXPENSAS,
                "media",
                "media",
            )
            caption_pendiente = conversacion.datos_temporales.pop("adjuntos_pendientes_caption", "")
            if caption_pendiente:
                respuesta_caption = ChatbotRules.procesar_mensaje(
                    numero_telefono,
                    caption_pendiente,
                    conversacion.nombre_usuario or "",
                )
                return respuesta_caption or respuesta_inicio
            return respuesta_inicio

        if respuesta in rechaza:
            conversacion.datos_temporales["_media_confirmacion"] = None
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.ESPERANDO_OPCION)
            logger.info("media_confirmed_not_expensas phone=%s", numero_telefono)
            if not numero_telefono.startswith("messenger:"):
                success = ChatbotRules.send_menu_interactivo(
                    numero_telefono,
                    conversacion.nombre_usuario or "",
                )
                if success:
                    return ""
            return ChatbotRules.get_mensaje_inicial_personalizado(conversacion.nombre_usuario)

        return "Por favor responde SI o NO."
    
    @staticmethod
    def get_saludo_inicial(nombre_usuario: str = "") -> str:
        """
        Primera parte del saludo: solo el saludo y presentación de Artu
        """
        if nombre_usuario:
            return f"¡Hola {nombre_usuario}! 👋🏻 Mi nombre es *Artu*"
        else:
            return "¡Hola! 👋🏻 Mi nombre es *Artu*"
    
    @staticmethod
    def get_presentacion_empresa() -> str:
        """
        Segunda parte del saludo: presentación de la empresa y menú
        """
        from config.company_profiles import get_active_company_profile
        profile = get_active_company_profile()
        company_name = profile['name']

        return f"Soy la asistente virtual de {company_name}." + ChatbotRules._build_menu_prompt()
    
    @staticmethod
    def _enviar_flujo_saludo_completo(numero_telefono: str, nombre_usuario: str = "") -> str:
        """
        Envía el flujo completo de saludo en background: saludo → sticker → menú
        Retorna inmediatamente (vacío) para que el webhook responda rápido
        
        MEJORA DE LATENCIA:
        - Antes: Webhook bloqueado ~500ms esperando la API de WhatsApp
        - Ahora: Webhook responde en ~15ms, todo se envía en paralelo
        """
        import os
        from services.meta_whatsapp_service import meta_whatsapp_service
        from config.company_profiles import get_active_company_profile
        import threading
        import time
        import logging
        
        logger = logging.getLogger(__name__)
        
        use_interactive_buttons = True
        
        # Función que envía TODO secuencialmente en background
        def enviar_todo_secuencial():
            """
            Envía los 3 mensajes en orden garantizado:
            1. Saludo (inmediato)
            2. Sticker (0.3s después)
            3. Menú (1.5s después del sticker = 1.8s total)
            """
            try:
                # ===== MENSAJE 1: SALUDO =====
                if nombre_usuario:
                    saludo = f"¡Hola {nombre_usuario}! 👋🏻 Mi nombre es Artu"
                else:
                    saludo = "¡Hola! 👋🏻 Mi nombre es Artu"
                
                logger.info(f"⚡ [Background] Enviando saludo a {numero_telefono}")
                inicio = time.time()
                saludo_enviado = meta_whatsapp_service.send_text_message(numero_telefono, saludo)
                tiempo_saludo = (time.time() - inicio) * 1000
                logger.info(f"✅ Saludo enviado en {tiempo_saludo:.0f}ms: {saludo_enviado}")
                
                # ===== MENSAJE 2: STICKER =====
                
                logger.info(f"⚡ [Background] Enviando sticker a {numero_telefono}")
                inicio = time.time()
                profile = get_active_company_profile()
                company_name = profile['name'].lower()
                sticker_url = f"https://raw.githubusercontent.com/Csuarezgurruchaga/argenfuego-chatbot/main/assets/{company_name}.webp"
                sticker_media_id = os.getenv("WHATSAPP_STICKER_MEDIA_ID", "").strip()

                logger.info(
                    "sticker_config media_id_set=%s url=%s",
                    bool(sticker_media_id),
                    sticker_url,
                )
                if sticker_media_id:
                    sticker_enviado = meta_whatsapp_service.send_sticker(
                        numero_telefono,
                        sticker_id=sticker_media_id,
                    )
                else:
                    sticker_enviado = meta_whatsapp_service.send_sticker(
                        numero_telefono,
                        sticker_url=sticker_url,
                    )
                tiempo_sticker = (time.time() - inicio) * 1000
                logger.info(f"✅ Sticker enviado en {tiempo_sticker:.0f}ms: {sticker_enviado}")
                
                # ===== MENSAJE 3: MENÚ =====
                
                logger.info(f"⚡ [Background] Enviando menú a {numero_telefono}")
                inicio = time.time()
                
                if use_interactive_buttons:
                    # Enviar menú con botones interactivos
                    success = ChatbotRules.send_menu_interactivo(numero_telefono, nombre_usuario)
                    tipo_menu = "interactivo"
                    if not success:
                        # Fallback: enviar menú tradicional si falla el interactivo
                        mensaje_completo = ChatbotRules.get_mensaje_inicial_personalizado(nombre_usuario)
                        success = meta_whatsapp_service.send_text_message(numero_telefono, mensaje_completo)
                        tipo_menu = "tradicional_fallback"
                else:
                    # Enviar menú tradicional
                    mensaje_completo = ChatbotRules.get_mensaje_inicial_personalizado(nombre_usuario)
                    success = meta_whatsapp_service.send_text_message(numero_telefono, mensaje_completo)
                    tipo_menu = "tradicional"
                
                tiempo_menu = (time.time() - inicio) * 1000
                logger.info(f"✅ Menú {tipo_menu} enviado en {tiempo_menu:.0f}ms: {success}")
                
            except Exception as e:
                logger.error(f"❌ Error en flujo de saludo para {numero_telefono}: {str(e)}")
                # Fallback: intentar enviar al menos el mensaje completo
                try:
                    mensaje_completo = ChatbotRules.get_mensaje_inicial_personalizado(nombre_usuario)
                    meta_whatsapp_service.send_text_message(numero_telefono, mensaje_completo)
                except Exception as fallback_error:
                    logger.error(f"❌ Error en fallback: {fallback_error}")
        
        # Ejecutar todo en un único thread background
        thread = threading.Thread(target=enviar_todo_secuencial)
        thread.daemon = True
        thread.start()
        
        logger.info(f"🚀 Thread de saludo iniciado para {numero_telefono}, webhook continuará sin esperar")
        
        # Retornar vacío inmediatamente - el webhook responde en ~15ms
        return ""
    
    @staticmethod
    def get_mensaje_recoleccion_datos_simplificado(tipo_consulta: TipoConsulta) -> str:
        if tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            return "Fecha de pago, monto, dirección, piso/departamento, comprobante y comentario."
        if tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            return "Tipo de reclamo, ubicación, piso/departamento/UF y detalle."
        return "Información requerida."
    
    @staticmethod
    def get_mensaje_inicio_secuencial(tipo_consulta: TipoConsulta) -> str:
        """Mensaje inicial para el flujo secuencial conversacional"""
        if tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            return ChatbotRules._get_pregunta_campo_secuencial("fecha_pago")
        if tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            return "Perfecto 👍\nPara ayudarte mejor, voy a hacerte unas preguntas cortitas."
        return "Perfecto 👍"
    
    @staticmethod
    def get_mensaje_recoleccion_datos(tipo_consulta: TipoConsulta) -> str:
        if tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            return ChatbotRules._get_pregunta_campo_secuencial("fecha_pago")
        if tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            return (
                "Perfecto 👍\n"
                "Para ayudarte mejor, voy a hacerte unas preguntas cortitas.\n"
                "¿Qué tipo de reclamo queres realizar?"
            )
        return "Seleccioná una opción del menú para continuar."
    
    @staticmethod
    def get_mensaje_confirmacion(conversacion) -> str:
        datos = conversacion.datos_temporales

        if conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            comentario = datos.get('comentario') or "Sin comentario"
            comprobante_count = ChatbotRules._count_adjuntos(datos.get("comprobante"))
            comprobante = (
                ChatbotRules._format_archivos(comprobante_count)
                if comprobante_count
                else "No"
            )
            return (
                "📋 *Resumen del pago de expensas:*\n\n"
                f"📅 *Fecha de pago:* {datos.get('fecha_pago', '')}\n"
                f"💰 *Monto:* {datos.get('monto', '')}\n"
                f"🏠 *Dirección:* {datos.get('direccion', '')}\n"
                f"🚪 *Piso/Departamento/Cochera:* {datos.get('piso_depto', '')}\n"
                f"🧾 *Comprobante:* {comprobante}\n"
                f"✍️ *Comentario:* {comentario}\n\n"
                "¿Es correcta toda la información?\n"
                "Respondé *SI* para confirmar o *NO* para modificar."
            )

        if conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            adjuntos_count = ChatbotRules._count_adjuntos(datos.get("adjuntos_servicio"))
            adjuntos_texto = ""
            if adjuntos_count:
                adjuntos_texto = f"📎 *Adjuntos:* {ChatbotRules._format_archivos(adjuntos_count)}\n"
            return (
                "📋 *Resumen de tu reclamo:*\n\n"
                f"🛠️ *Tipo de reclamo:* {datos.get('tipo_servicio', '')}\n"
                f"📍 *Ubicación:* {datos.get('direccion_servicio', '')}\n"
                f"🚪 *Piso/Departamento/UF:* {datos.get('piso_depto', '')}\n"
                f"📝 *Detalle:* {datos.get('detalle_servicio', '')}\n"
                f"{adjuntos_texto}"
                "\n"
                "¿Es correcta toda la información?\n"
                "Respondé *SI* para confirmar o *NO* para modificar."
            )

        return "¿Es correcta toda la información?"
    
    @staticmethod
    def send_confirmacion_interactiva(numero_telefono: str, conversacion) -> bool:
        """
        Envía mensaje de confirmación con botones interactivos
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging
        logger = logging.getLogger(__name__)
        
        # Obtener mensaje de confirmación
        mensaje = ChatbotRules.get_mensaje_confirmacion(conversacion)
        
        # Enviar con botones
        success = ChatbotRules.send_confirmation_buttons(numero_telefono, mensaje)
        
        if success:
            logger.info(f"✅ Confirmación interactiva enviada a {numero_telefono}")
        else:
            logger.error(f"❌ Error enviando confirmación interactiva a {numero_telefono}")
        
        return success
    
    @staticmethod
    def _get_texto_tipo_consulta(tipo_consulta: TipoConsulta) -> str:
        textos = {
            TipoConsulta.PAGO_EXPENSAS: "registrar un pago de expensas",
            TipoConsulta.SOLICITAR_SERVICIO: "realizar un reclamo",
            TipoConsulta.EMERGENCIA: "atender una emergencia",
        }
        return textos.get(tipo_consulta, "ayuda")
    
    @staticmethod
    def _get_pregunta_campo_individual(campo: str, tipo_consulta: TipoConsulta = None) -> str:
        fecha_ejemplo = _fecha_argentina(0)
        piso_depto_pregunta = "🚪¿Cual es tu unidad?\nEjemplo: 2° A, UF 14, Cochera 12."
        if tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            piso_depto_pregunta = "¿Cuál es el piso/departamento/UF?"
        preguntas = {
            'fecha_pago': f"📅 ¿En qué fecha realizaste el pago de las expensas?\n(Por ejemplo: {fecha_ejemplo})",
            'monto': "💰 ¿Cuál fue el monto que abonaste?\n(Podés escribir solo el número, por ejemplo: 45800)",
            'direccion': "🏠 ¿A qué dirección corresponde el pago?\n(Ejemplo: Av. Corrientes 1234)",
            'piso_depto': piso_depto_pregunta,
            'comprobante': "🧾 ¿Tenés el comprobante de pago? Podés enviarlo acá.\n(Puede ser imagen o PDF. Si no, escribí “Saltar”)",
            'comentario': "✍️ ¿Querés agregar algún comentario o aclaración?\n(Si no, escribí “Saltar”)",
            'tipo_servicio': (
                "¿Qué tipo de reclamo queres realizar? "
                "(Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos u Otro reclamo)"
            ),
            'direccion_servicio': "¿En qué lugar se presenta el problema?\n(Indicá dirección)",
            'detalle_servicio': "Contame brevemente qué está pasando.",
        }
        return preguntas.get(campo, "Por favor proporciona más información.")
    
    @staticmethod
    def _get_pregunta_campo_secuencial(campo: str, tipo_consulta: TipoConsulta = None) -> str:
        """Preguntas específicas para el flujo secuencial"""
        return ChatbotRules._get_pregunta_campo_individual(campo, tipo_consulta)

    @staticmethod
    def _parece_direccion_con_unidad(texto: str) -> bool:
        """
        Heurística barata para detectar que el usuario mezcló dirección + unidad (piso/depto/UF/cochera/oficina/local).
        Se usa para decidir si vale la pena llamar a OpenAI.
        """
        if not texto:
            return False
        t = texto.lower()

        # Keywords explícitas (alta señal)
        if re.search(
            r"\b(piso|p|depto|dpto|dto|departamento|uf|u\.f\.|unidad\s+funcional|cochera|garage|garaje|local|oficina|of\.|ofic\.?)\b",
            t,
        ):
            return True

        # Caso abreviado: "unidad 2"
        if re.search(r"\bunidad\s*#?\s*\d{1,5}\b", t):
            return True

        # Señales comunes de piso/depto sin keyword (ej: "2° A", "9o Dto B", "4toA")
        if re.search(r"\b(pb|p\.?b\.?)\b", t):
            return True
        if re.search(r"\b\d{1,2}\s*[°º]\s*[a-z]{1,2}\b", t):
            return True
        if re.search(r"\b\d{1,2}\s*(?:o|to|ta)\s*[a-z]{1,2}\b", t):
            return True
        if re.search(r"\b\d{1,2}(?:o|to|ta)\s*[a-z]{1,2}\b", t):
            return True
        # Caso "2 A" al final (muy común en unidades)
        if re.search(r"(?:,|\s)\s*\d{1,2}\s*[a-z]{1,2}\s*\.?\s*$", t):
            return True

        return False

    @staticmethod
    def _extraer_piso_depto_de_direccion(direccion: str) -> tuple[str, Optional[str]]:
        """
        Intenta extraer piso/depto al final de una dirección.
        """
        if not direccion:
            return direccion, None

        texto = direccion.strip()

        # Caso UF / Unidad Funcional al final (case-insensitive)
        uf_pattern = re.compile(
            r"(?:,|\s)(?:uf|u\.?f\.?|unidad\s+funcional)\s*#?\s*"
            r"(\d{1,5}\s*[°º]?\s*[a-zA-Z]{0,2})\s*$",
            re.IGNORECASE,
        )
        match = uf_pattern.search(texto)
        if match:
            sugerido = " ".join(match.group(1).split())
            base = texto[:match.start()].strip(" ,")
            return base, f"UF {sugerido}".strip()

        # Caso con keyword explícita al final (piso/depto/dto)
        keyword_pattern = re.compile(
            r"(?:,|\s)(?:piso|p|depto|dpto|dto|departamento)\s*"
            r"(\d{1,3}\s*[°º]?\s*[a-zA-Z]{0,2})\s*$",
            re.IGNORECASE,
        )
        match = keyword_pattern.search(texto)
        if match:
            sugerido = " ".join(match.group(1).split())
            base = texto[:match.start()].strip(" ,")
            return base, sugerido

        # Caso sin keyword: token final con número + letra (ej: 4B, 3° B)
        suffix_pattern = re.compile(r"\b(\d{1,3}\s*[°º]?\s*[a-zA-Z]{1,2})\s*$")
        match = suffix_pattern.search(texto)
        if match:
            sugerido = " ".join(match.group(1).split())
            base = texto[:match.start()].strip(" ,")
            # Evitar capturar solo el número de calle
            if len(re.findall(r"\d+", base)) >= 1:
                return base, sugerido

        return direccion, None

    @staticmethod
    def send_piso_depto_suggestion(numero_telefono: str, sugerido: str) -> bool:
        """
        Envía sugerencia interactiva para piso/depto detectado en la dirección.
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        body_text = f"Detecté unidad: {sugerido}. ¿Querés usarla?"

        def _button_title_from_sugerido(texto: str) -> str:
            # WhatsApp corta a 20 chars en title; intentar conservar 1–2 componentes.
            raw = (texto or "").strip()
            if not raw:
                return "Usar"
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if not parts:
                return raw[:20]
            title = parts[0]
            if len(parts) <= 1:
                return title[:20]
            candidate = f"{parts[0]}, {parts[1]}"
            if len(candidate) <= 20:
                return candidate
            return title[:20]

        buttons = [
            {"id": "piso_depto_usar", "title": _button_title_from_sugerido(sugerido)},
            {"id": "piso_depto_otro", "title": "Otro"},
        ]

        success = meta_whatsapp_service.send_interactive_buttons(
            numero_telefono,
            body_text=body_text,
            buttons=buttons,
        )

        if success:
            logger.info("✅ Sugerencia de piso/depto enviada a %s", numero_telefono)
        else:
            logger.error("❌ Error enviando sugerencia de piso/depto a %s", numero_telefono)

        return success

    @staticmethod
    def _truncate_text(texto: str, max_len: int) -> str:
        if len(texto) <= max_len:
            return texto
        if max_len <= 3:
            return texto[:max_len]
        return texto[: max_len - 3] + "..."

    @staticmethod
    def _format_direccion_label(direccion: str, piso: str) -> str:
        direccion = (direccion or "").strip()
        piso = (piso or "").strip()
        if direccion and piso:
            return f"{direccion} {piso}"
        return direccion or piso or "Direccion"

    @staticmethod
    def _build_direccion_fallback_text(direcciones: list) -> str:
        lines = ["Tengo estas direcciones guardadas:"]
        for idx, item in enumerate(direcciones, start=1):
            label = ChatbotRules._format_direccion_label(item.get("direccion", ""), item.get("piso_depto", ""))
            lines.append(f"{idx}. {label}")
        lines.append(f"{len(direcciones) + 1}. Otra Direccion")
        lines.append('\nResponde con el numero de la opcion o escribe "eliminar", para borrar una direccion.')
        return "\n".join(lines)

    @staticmethod
    def _normalize_seleccion_texto(texto: str) -> str:
        if not texto:
            return ""
        normalized = unicodedata.normalize("NFD", texto.lower().strip())
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _parse_direccion_seleccion(mensaje: str, total: int) -> Optional[object]:
        normalized = ChatbotRules._normalize_seleccion_texto(mensaje)
        compact = normalized.replace(" ", "")
        if compact in {"otra", "otradireccion"}:
            return "otro"

        word_map = {
            "uno": 1,
            "dos": 2,
            "tres": 3,
            "cuatro": 4,
            "cinco": 5,
        }
        num = word_map.get(normalized)
        if num is None:
            match = re.search(r"\d+", normalized)
            if match:
                num = int(match.group())
        if num is None:
            return None
        if num == total + 1:
            return "otro"
        if 1 <= num <= total:
            return num - 1
        return None

    @staticmethod
    def _count_adjuntos(value) -> int:
        if isinstance(value, list):
            return len(value)
        if value:
            return 1
        return 0

    @staticmethod
    def _format_archivos(count: int) -> str:
        if count == 1:
            return "1 archivo"
        return f"{count} archivos"

    @staticmethod
    def _build_eliminar_fallback_text(direcciones: list) -> str:
        lines = ["Selecciona la direccion que queres eliminar:"]
        for idx, item in enumerate(direcciones, start=1):
            label = ChatbotRules._format_direccion_label(item.get("direccion", ""), item.get("piso_depto", ""))
            lines.append(f"{idx}. {label}")
        lines.append('\nEscribi el numero de la direccion que queres eliminar o "cancelar".')
        return "\n".join(lines)

    @staticmethod
    def _send_direccion_buttons(numero_telefono: str, direcciones: list) -> bool:
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        buttons = []
        for idx, item in enumerate(direcciones):
            label = ChatbotRules._format_direccion_label(item.get("direccion", ""), item.get("piso_depto", ""))
            title = ChatbotRules._truncate_text(label, 20)
            buttons.append({"id": f"dir_sel_{idx}", "title": title})
        buttons.append({"id": "dir_otro", "title": "Otra Direccion"})

        success = meta_whatsapp_service.send_interactive_buttons(
            numero_telefono,
            body_text="Selecciona una direccion guardada o elegi Otra Direccion.",
            buttons=buttons,
        )
        if success:
            logger.info("direccion_seleccion_enviada phone=%s count=%s", numero_telefono, len(direcciones))
        return success

    @staticmethod
    def _send_direccion_list(numero_telefono: str, direcciones: list) -> bool:
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        rows = []
        for idx, item in enumerate(direcciones):
            label = ChatbotRules._format_direccion_label(item.get("direccion", ""), item.get("piso_depto", ""))
            title = ChatbotRules._truncate_text(label, 24)
            rows.append({"id": f"dir_sel_{idx}", "title": title})
        rows.append({"id": "dir_otro", "title": "Otra Direccion"})

        sections = [{"title": "Direcciones", "rows": rows}]
        success = meta_whatsapp_service.send_interactive_list(
            numero_telefono,
            body_text="Selecciona una direccion guardada o elegi Otra Direccion.",
            button_text="Elegir direccion",
            sections=sections,
        )
        if success:
            logger.info("direccion_lista_enviada phone=%s count=%s", numero_telefono, len(direcciones))
        return success

    @staticmethod
    def _send_eliminar_direccion_list(numero_telefono: str, direcciones: list) -> bool:
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        rows = []
        for idx, item in enumerate(direcciones):
            label = ChatbotRules._format_direccion_label(item.get("direccion", ""), item.get("piso_depto", ""))
            title = ChatbotRules._truncate_text(label, 24)
            rows.append({"id": f"dir_del_{idx}", "title": title})

        sections = [{"title": "Eliminar direccion", "rows": rows}]
        success = meta_whatsapp_service.send_interactive_list(
            numero_telefono,
            body_text="Para guardar una nueva direccion, elimina una existente.",
            button_text="Eliminar direccion",
            sections=sections,
        )
        if success:
            logger.info("direccion_eliminar_lista_enviada phone=%s", numero_telefono)
        return success

    @staticmethod
    def _maybe_prompt_direccion_guardada(numero_telefono: str, contexto: str) -> Optional[str]:
        from services.clients_sheet_service import clients_sheet_service

        if numero_telefono.startswith("messenger:"):
            return None
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        if conversacion.datos_temporales.get("_direccion_seleccion_contexto"):
            direcciones = conversacion.datos_temporales.get("_direcciones_guardadas", []) or []
            if not direcciones:
                direcciones = clients_sheet_service.get_direcciones(numero_telefono)
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_direcciones_guardadas",
                    direcciones,
                )
            return ChatbotRules._build_direccion_fallback_text(direcciones)
        direcciones = clients_sheet_service.get_direcciones(numero_telefono)
        if not direcciones:
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", True)
            return None
        conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", direcciones)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_seleccion_contexto", contexto)
        return ChatbotRules._build_direccion_fallback_text(direcciones)

    @staticmethod
    def _apply_direccion_seleccionada(numero_telefono: str, direccion_item: dict, contexto: str) -> str:
        from services.clients_sheet_service import clients_sheet_service

        direccion = direccion_item.get("direccion", "")
        piso = direccion_item.get("piso_depto", "")
        import logging
        logger = logging.getLogger(__name__)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_seleccion_contexto", None)
        conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", None)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", False)

        if contexto == "expensas":
            conversation_manager.set_datos_temporales(numero_telefono, "direccion", direccion)
            conversation_manager.set_datos_temporales(numero_telefono, "piso_depto", piso)
        else:
            conversation_manager.set_datos_temporales(numero_telefono, "direccion_servicio", direccion)
            conversation_manager.set_datos_temporales(numero_telefono, "piso_depto", piso)

        try:
            clients_sheet_service.update_last_used(numero_telefono, direccion, piso)
        except Exception:
            pass
        logger.info("direccion_seleccionada phone=%s", numero_telefono)

        siguiente = conversation_manager.get_campo_siguiente(numero_telefono)
        if not siguiente:
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
            return ChatbotRules.get_mensaje_confirmacion(conversation_manager.get_conversacion(numero_telefono))
        return ChatbotRules._get_pregunta_campo_secuencial(siguiente, conversation_manager.get_conversacion(numero_telefono).tipo_consulta)

    @staticmethod
    def _prompt_eliminar_direccion(
        numero_telefono: str,
        direcciones: list,
        contexto: str,
        *,
        return_mode: str,
    ) -> Optional[str]:
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_contexto", contexto)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_activa", True)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_return_mode", return_mode)
        conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", direcciones)
        # Track previous state so we can restore it after leaving delete mode.
        prev_estado = conversation_manager.get_conversacion(numero_telefono).estado
        prev_estado_value = prev_estado.value if hasattr(prev_estado, "value") else str(prev_estado)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_prev_estado", prev_estado_value)
        conversation_manager.update_estado(numero_telefono, EstadoConversacion.ELIMINANDO_DIRECCION_GUARDADA)
        return ChatbotRules._build_eliminar_fallback_text(direcciones)

    @staticmethod
    def _procesar_seleccion_direccion_text(numero_telefono: str, mensaje: str) -> Optional[str]:
        from services.clients_sheet_service import clients_sheet_service

        conversacion = conversation_manager.get_conversacion(numero_telefono)
        contexto = conversacion.datos_temporales.get("_direccion_seleccion_contexto")
        if not contexto:
            return None
        direcciones = conversacion.datos_temporales.get("_direcciones_guardadas", []) or []
        if not direcciones:
            direcciones = clients_sheet_service.get_direcciones(numero_telefono)
            conversation_manager.set_datos_temporales(
                numero_telefono,
                "_direcciones_guardadas",
                direcciones,
            )
        if not direcciones:
            return None
        # Allow user to enter delete mode from the selection screen without calling NLU.
        if ChatbotRules._normalize_seleccion_texto(mensaje) == "eliminar":
            return ChatbotRules._prompt_eliminar_direccion(
                numero_telefono,
                direcciones,
                contexto,
                return_mode="selection",
            )
        seleccion = ChatbotRules._parse_direccion_seleccion(mensaje, len(direcciones))
        if seleccion is None:
            return ChatbotRules._build_direccion_fallback_text(direcciones)
        if seleccion == "otro":
            return ChatbotRules._procesar_direccion_otro(numero_telefono, contexto, direcciones)
        return ChatbotRules._apply_direccion_seleccionada(numero_telefono, direcciones[seleccion], contexto)

    @staticmethod
    def _procesar_eliminar_direccion_text(numero_telefono: str, mensaje: str) -> Optional[str]:
        from services.clients_sheet_service import clients_sheet_service

        conversacion = conversation_manager.get_conversacion(numero_telefono)
        if not conversacion.datos_temporales.get("_direccion_eliminar_activa"):
            return None
        direcciones = conversacion.datos_temporales.get("_direcciones_guardadas", []) or []
        normalized = ChatbotRules._normalize_seleccion_texto(mensaje)
        if normalized in {"cancelar", "volver"}:
            # Exit delete mode back to address selection.
            contexto = conversacion.datos_temporales.get("_direccion_eliminar_contexto", "expensas")
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_activa", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_contexto", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_return_mode", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", None)

            # Restore prior state if possible.
            prev_estado_raw = conversacion.datos_temporales.get("_direccion_eliminar_prev_estado")
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_prev_estado", None)
            if prev_estado_raw:
                try:
                    conversation_manager.update_estado(numero_telefono, EstadoConversacion(prev_estado_raw))
                except Exception:
                    pass

            refreshed = clients_sheet_service.get_direcciones(numero_telefono)
            conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", refreshed)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_seleccion_contexto", contexto)
            return ChatbotRules._build_direccion_fallback_text(refreshed)

        if not mensaje.strip().isdigit():
            return ChatbotRules._build_eliminar_fallback_text(direcciones)
        idx = int(mensaje.strip()) - 1
        if idx < 0 or idx >= len(direcciones):
            return ChatbotRules._build_eliminar_fallback_text(direcciones)

        contexto = conversacion.datos_temporales.get("_direccion_eliminar_contexto", "expensas")
        return_mode = conversacion.datos_temporales.get("_direccion_eliminar_return_mode", "new_address")
        deleted_item = direcciones[idx] if 0 <= idx < len(direcciones) else {}

        removed = clients_sheet_service.remove_direccion(numero_telefono, idx)
        if not removed:
            # Sheets failure / write denied / other errors.
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_activa", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_contexto", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_return_mode", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", None)

            # Restore prior state if possible.
            prev_estado_raw = conversacion.datos_temporales.get("_direccion_eliminar_prev_estado")
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_prev_estado", None)
            if prev_estado_raw:
                try:
                    conversation_manager.update_estado(numero_telefono, EstadoConversacion(prev_estado_raw))
                except Exception:
                    pass

            refreshed = clients_sheet_service.get_direcciones(numero_telefono)
            conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", refreshed)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_seleccion_contexto", contexto)
            return "No pude eliminarla ahora, intenta mas tarde\n\n" + ChatbotRules._build_direccion_fallback_text(refreshed)

        import logging
        logger = logging.getLogger(__name__)
        label = ChatbotRules._format_direccion_label(
            deleted_item.get("direccion", ""),
            deleted_item.get("piso_depto", ""),
        )
        logger.info("direccion_eliminada phone=%s direccion=%s", numero_telefono, label)

        # Exit delete mode
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_activa", None)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_contexto", None)
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_return_mode", None)
        conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", None)

        # Restore prior state if possible.
        prev_estado_raw = conversacion.datos_temporales.get("_direccion_eliminar_prev_estado")
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_prev_estado", None)
        if prev_estado_raw:
            try:
                conversation_manager.update_estado(numero_telefono, EstadoConversacion(prev_estado_raw))
            except Exception:
                pass

        confirm_msg = f"Direccion eliminada: {label}".rstrip()

        # If the deleted address was selected in this conversation, reset selected fields and re-list.
        if contexto == "expensas":
            if (
                ChatbotRules._normalize_seleccion_texto(conversacion.datos_temporales.get("direccion", ""))
                == ChatbotRules._normalize_seleccion_texto(deleted_item.get("direccion", ""))
                and ChatbotRules._normalize_seleccion_texto(conversacion.datos_temporales.get("piso_depto", ""))
                == ChatbotRules._normalize_seleccion_texto(deleted_item.get("piso_depto", ""))
            ):
                conversation_manager.set_datos_temporales(numero_telefono, "direccion", None)
                conversation_manager.set_datos_temporales(numero_telefono, "piso_depto", None)
        else:
            if (
                ChatbotRules._normalize_seleccion_texto(conversacion.datos_temporales.get("direccion_servicio", ""))
                == ChatbotRules._normalize_seleccion_texto(deleted_item.get("direccion", ""))
                and ChatbotRules._normalize_seleccion_texto(conversacion.datos_temporales.get("piso_depto", ""))
                == ChatbotRules._normalize_seleccion_texto(deleted_item.get("piso_depto", ""))
            ):
                conversation_manager.set_datos_temporales(numero_telefono, "direccion_servicio", None)
                conversation_manager.set_datos_temporales(numero_telefono, "piso_depto", None)

        refreshed = clients_sheet_service.get_direcciones(numero_telefono)

        if return_mode == "selection":
            if not refreshed:
                # No addresses left: proceed as if user chose "Otra Direccion".
                conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", True)
                campo = "direccion" if contexto == "expensas" else "direccion_servicio"
                return confirm_msg + "\n\n" + ChatbotRules._get_pregunta_campo_secuencial(campo, conversacion.tipo_consulta)

            conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", refreshed)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_seleccion_contexto", contexto)
            return confirm_msg + "\n\n" + ChatbotRules._build_direccion_fallback_text(refreshed)

        # Legacy/limit flow: after deletion, continue asking for a new address.
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", True)
        campo = "direccion" if contexto == "expensas" else "direccion_servicio"
        return confirm_msg + "\n\n" + ChatbotRules._get_pregunta_campo_secuencial(campo, conversacion.tipo_consulta)

    @staticmethod
    def _procesar_direccion_otro(numero_telefono: str, contexto: str, direcciones: list) -> str:
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_seleccion_contexto", None)
        conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", None)
        if len(direcciones) >= ChatbotRules.MAX_DIRECCIONES_GUARDADAS:
            prompt = ChatbotRules._prompt_eliminar_direccion(
                numero_telefono,
                direcciones,
                contexto,
                return_mode="new_address",
            )
            return prompt or ""
        conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", True)
        return ChatbotRules._get_pregunta_campo_secuencial(
            "direccion" if contexto == "expensas" else "direccion_servicio",
            conversation_manager.get_conversacion(numero_telefono).tipo_consulta,
        )

    @staticmethod
    def procesar_direccion_interactive(numero_telefono: str, button_id: str) -> Optional[str]:
        from services.clients_sheet_service import clients_sheet_service

        conversacion = conversation_manager.get_conversacion(numero_telefono)
        direcciones = conversacion.datos_temporales.get("_direcciones_guardadas", []) or []
        contexto = conversacion.datos_temporales.get("_direccion_seleccion_contexto")

        if button_id.startswith("dir_sel_"):
            try:
                idx = int(button_id.replace("dir_sel_", ""))
            except ValueError:
                return None
            if not direcciones:
                direcciones = clients_sheet_service.get_direcciones(numero_telefono)
            if idx < 0 or idx >= len(direcciones):
                return ChatbotRules._build_direccion_fallback_text(direcciones)
            contexto = contexto or "expensas"
            return ChatbotRules._apply_direccion_seleccionada(numero_telefono, direcciones[idx], contexto)

        if button_id == "dir_otro":
            if not direcciones:
                direcciones = clients_sheet_service.get_direcciones(numero_telefono)
            contexto = contexto or "expensas"
            return ChatbotRules._procesar_direccion_otro(numero_telefono, contexto, direcciones)

        if button_id.startswith("dir_del_"):
            try:
                idx = int(button_id.replace("dir_del_", ""))
            except ValueError:
                return None
            if not direcciones:
                direcciones = clients_sheet_service.get_direcciones(numero_telefono)
            if idx < 0 or idx >= len(direcciones):
                return ChatbotRules._build_eliminar_fallback_text(direcciones)
            contexto = conversacion.datos_temporales.get("_direccion_eliminar_contexto", "expensas")
            removed = clients_sheet_service.remove_direccion(numero_telefono, idx)
            if not removed:
                return "No pude eliminar esa direccion. Por favor intenta de nuevo."
            import logging
            logger = logging.getLogger(__name__)
            logger.info("direccion_eliminada phone=%s", numero_telefono)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_activa", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_eliminar_contexto", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direcciones_guardadas", None)
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", True)
            return ChatbotRules._get_pregunta_campo_secuencial(
                "direccion" if contexto == "expensas" else "direccion_servicio",
                conversacion.tipo_consulta,
            )

        return None
    
    @staticmethod
    def _get_mensaje_confirmacion_campo(campo: str, valor: str) -> str:
        """Mensajes de confirmación para cada campo con emojis blancos"""
        confirmaciones = {
            'fecha_pago': f"📅 Fecha registrada: {valor}",
            'monto': f"💰 Monto registrado: {valor}",
            'direccion': f"🏠 Dirección registrada: {valor}",
            'piso_depto': f"🚪 Piso/Departamento/UF registrado: {valor}",
            'comprobante': "🧾 Comprobante recibido",
            'comentario': f"✍️ Comentario registrado: {valor}",
            'tipo_servicio': f"🛠️ Tipo de reclamo: {valor}",
            'direccion_servicio': f"📍 Ubicación registrada: {valor}",
            'detalle_servicio': f"📝 Detalle registrado: {valor}",
        }
        return confirmaciones.get(campo, f"✅ {valor} guardado correctamente.")

    @staticmethod
    def send_fecha_pago_hoy_button(numero_telefono: str) -> bool:
        """
        Envía la pregunta de fecha de pago con botón interactivo "Hoy".
        """
        from services.meta_whatsapp_service import meta_whatsapp_service
        import logging

        logger = logging.getLogger(__name__)

        body_text = ChatbotRules._get_pregunta_campo_secuencial("fecha_pago")
        buttons = [
            {"id": "fecha_hoy", "title": "Hoy"},
            {"id": "fecha_ayer", "title": "Ayer"},
        ]

        success = meta_whatsapp_service.send_interactive_buttons(
            numero_telefono,
            body_text=body_text,
            buttons=buttons,
        )

        if success:
            logger.info("✅ Botón 'Hoy' enviado a %s", numero_telefono)
            return True

        logger.error("❌ Error enviando botón 'Hoy' a %s", numero_telefono)
        return False
    
    @staticmethod
    def _procesar_campo_secuencial(numero_telefono: str, mensaje: str) -> str:
        """Procesa un campo en el flujo secuencial conversacional"""
        import logging

        logger = logging.getLogger(__name__)
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        campo_actual = conversation_manager.get_campo_siguiente(numero_telefono)
        logger.info(
            "Secuencial: phone=%s estado=%s campo=%s tipo=%s",
            numero_telefono,
            conversacion.estado,
            campo_actual,
            conversacion.tipo_consulta,
        )

        if not campo_actual:
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
            return ChatbotRules.get_mensaje_confirmacion(conversacion)

        valor = mensaje.strip()
        if campo_actual == "piso_depto":
            sugerido = conversacion.datos_temporales.get("_piso_depto_sugerido")
            valor_lower = valor.lower()
            if valor_lower == "piso_depto_usar":
                if sugerido:
                    valor = sugerido
                    conversation_manager.set_datos_temporales(
                        numero_telefono,
                        "_piso_depto_sugerido",
                        None,
                    )
                else:
                    return ChatbotRules._get_pregunta_campo_secuencial(
                        campo_actual,
                        conversacion.tipo_consulta,
                    )
            elif valor_lower == "piso_depto_otro":
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_piso_depto_sugerido",
                    None,
                )
                return ChatbotRules._get_pregunta_campo_secuencial(
                    campo_actual,
                    conversacion.tipo_consulta,
                )

        if campo_actual == 'fecha_pago':
            fecha_rel = _parse_fecha_hoy_ayer(valor)
            if fecha_rel:
                conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, fecha_rel)
            else:
                fecha_norm = ChatbotRules._normalizar_fecha_pago(valor)
                if not fecha_norm:
                    ChatbotRules._log_validacion_fallida(campo_actual)
                    error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
                    return f"❌ {error_msg}\n{ChatbotRules._get_pregunta_campo_secuencial(campo_actual, conversacion.tipo_consulta)}"
                conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, fecha_norm)
        elif campo_actual == 'monto':
            monto_norm = ChatbotRules._normalizar_monto(valor)
            if not monto_norm:
                ChatbotRules._log_validacion_fallida(campo_actual)
                error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
                return f"❌ {error_msg}\n{ChatbotRules._get_pregunta_campo_secuencial(campo_actual, conversacion.tipo_consulta)}"
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, monto_norm)
        elif campo_actual == 'tipo_servicio':
            matched = ChatbotRules._match_service_option(valor)
            if not matched:
                ChatbotRules._log_validacion_fallida(campo_actual)
                error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
                return f"❌ {error_msg}\n{ChatbotRules._get_pregunta_campo_secuencial(campo_actual, conversacion.tipo_consulta)}"
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, matched)
        elif campo_actual == 'direccion' and conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            direccion_base = valor
            direccion_base, sugerido = ChatbotRules._extraer_piso_depto_de_direccion(valor)

            if ChatbotRules._parece_direccion_con_unidad(valor):
                try:
                    from services.nlu_service import nlu_service, NLUService

                    parsed = nlu_service.extraer_direccion_unidad(valor)
                    if parsed:
                        llm_base = (parsed.get("direccion_altura") or "").strip()
                        llm_sugerido = NLUService.construir_unidad_sugerida(parsed)
                        if llm_base and ChatbotRules._direccion_valida(llm_base):
                            direccion_base = llm_base
                        if llm_sugerido:
                            sugerido = llm_sugerido
                except Exception:
                    pass

            logger.info(
                "Direccion parse: phone=%s base=%s sugerido=%s",
                numero_telefono,
                direccion_base[:80],
                sugerido,
            )

            if sugerido and len(direccion_base) >= 5:
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_piso_depto_sugerido",
                    sugerido,
                )
                valor = direccion_base
            else:
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_piso_depto_sugerido",
                    None,
                )
            if not ChatbotRules._validar_campo_individual(campo_actual, valor):
                ChatbotRules._log_validacion_fallida(campo_actual)
                error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
                return f"❌ {error_msg}\n{ChatbotRules._get_pregunta_campo_secuencial(campo_actual, conversacion.tipo_consulta)}"
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, valor)
        elif campo_actual == 'direccion_servicio' and conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            direccion_base = valor
            direccion_base, sugerido = ChatbotRules._extraer_piso_depto_de_direccion(valor)

            if ChatbotRules._parece_direccion_con_unidad(valor):
                try:
                    from services.nlu_service import nlu_service, NLUService

                    parsed = nlu_service.extraer_direccion_unidad(valor)
                    if parsed:
                        llm_base = (parsed.get("direccion_altura") or "").strip()
                        llm_sugerido = NLUService.construir_unidad_sugerida(parsed)
                        if llm_base and ChatbotRules._direccion_valida(llm_base):
                            direccion_base = llm_base
                        if llm_sugerido:
                            sugerido = llm_sugerido
                except Exception:
                    pass

            logger.info(
                "Direccion servicio parse: phone=%s base=%s sugerido=%s",
                numero_telefono,
                direccion_base[:80],
                sugerido,
            )

            if sugerido and len(direccion_base) >= 5:
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_piso_depto_sugerido",
                    sugerido,
                )
                valor = direccion_base
            else:
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_piso_depto_sugerido",
                    None,
                )
            if not ChatbotRules._validar_campo_individual(campo_actual, valor):
                ChatbotRules._log_validacion_fallida(campo_actual)
                error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
                return f"❌ {error_msg}\n{ChatbotRules._get_pregunta_campo_secuencial(campo_actual, conversacion.tipo_consulta)}"
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, valor)
        elif campo_actual == 'comentario' and valor.lower() in ['saltar', 'skip', 'no', 'n/a', 'na']:
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, "")
        elif campo_actual == 'comprobante' and valor.lower() in ['saltar', 'skip', 'no', 'n/a', 'na']:
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, "")
        else:
            if not ChatbotRules._validar_campo_individual(campo_actual, valor):
                ChatbotRules._log_validacion_fallida(campo_actual)
                error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
                return f"❌ {error_msg}\n{ChatbotRules._get_pregunta_campo_secuencial(campo_actual, conversacion.tipo_consulta)}"
            conversation_manager.marcar_campo_completado(numero_telefono, campo_actual, valor)

        if campo_actual == "piso_depto" and conversacion.datos_temporales.get("_direccion_nueva"):
            if conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
                direccion = conversacion.datos_temporales.get("direccion_servicio", "")
            else:
                direccion = conversacion.datos_temporales.get("direccion", "")
            conversation_manager.set_datos_temporales(
                numero_telefono,
                "_direccion_para_guardar",
                {"direccion": direccion, "piso_depto": valor},
            )
            conversation_manager.set_datos_temporales(numero_telefono, "_direccion_nueva", False)

        if conversation_manager.es_ultimo_campo(numero_telefono, campo_actual):
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
            return ChatbotRules.get_mensaje_confirmacion(conversation_manager.get_conversacion(numero_telefono))

        siguiente_campo = conversation_manager.get_campo_siguiente(numero_telefono)
        if campo_actual == "tipo_servicio":
            caption_pendiente = conversacion.datos_temporales.pop("adjuntos_pendientes_caption", "")
            if caption_pendiente:
                return ChatbotRules._procesar_campo_secuencial(numero_telefono, caption_pendiente)
        if (
            campo_actual == "direccion"
            and conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS
            and siguiente_campo == "direccion"
        ):
            logger.warning(
                "Loop detectado en direccion: phone=%s. Forzando avance a piso_depto.",
                numero_telefono,
            )
            conversation_manager.set_datos_temporales(numero_telefono, "direccion", valor)
            siguiente_campo = "piso_depto"
        if siguiente_campo == "direccion" and conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            direccion_prompt = ChatbotRules._maybe_prompt_direccion_guardada(numero_telefono, "expensas")
            if direccion_prompt is not None:
                return direccion_prompt
        if siguiente_campo == "direccion_servicio" and conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            direccion_prompt = ChatbotRules._maybe_prompt_direccion_guardada(numero_telefono, "servicio")
            if direccion_prompt is not None:
                return direccion_prompt
        if (
            siguiente_campo == 'piso_depto'
            and conversacion.tipo_consulta in {TipoConsulta.PAGO_EXPENSAS, TipoConsulta.SOLICITAR_SERVICIO}
            and not numero_telefono.startswith("messenger:")
        ):
            sugerido = conversacion.datos_temporales.get("_piso_depto_sugerido")
            if sugerido and ChatbotRules.send_piso_depto_suggestion(numero_telefono, sugerido):
                return ""
            if sugerido:
                return (
                    f"Detecté piso/depto: {sugerido}. "
                    f"Respondé con {sugerido} o escribí otro.\n\n"
                    f"{ChatbotRules._get_pregunta_campo_secuencial(siguiente_campo, conversacion.tipo_consulta)}"
                )

        return ChatbotRules._get_pregunta_campo_secuencial(siguiente_campo, conversacion.tipo_consulta)
    
    @staticmethod
    def _procesar_campo_individual(numero_telefono: str, mensaje: str) -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        campos_faltantes = conversacion.datos_temporales.get('_campos_faltantes', [])
        indice_actual = conversacion.datos_temporales.get('_campo_actual', 0)
        
        if indice_actual >= len(campos_faltantes):
            # Error, no deberíamos estar aquí
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_DATOS)
            return "🤖 Hubo un error. Escribe 'hola' para comenzar de nuevo."
        
        campo_actual = campos_faltantes[indice_actual]
        
        # Validar y guardar la respuesta
        valor = mensaje.strip()
        if campo_actual == "fecha_pago":
            fecha_rel = _parse_fecha_hoy_ayer(valor)
            if fecha_rel:
                valor = fecha_rel
            else:
                fecha_norm = ChatbotRules._normalizar_fecha_pago(valor)
                if fecha_norm:
                    valor = fecha_norm
        if campo_actual == "monto":
            monto_norm = ChatbotRules._normalizar_monto(valor)
            if monto_norm:
                valor = monto_norm
        if ChatbotRules._validar_campo_individual(campo_actual, valor):
            conversation_manager.set_datos_temporales(numero_telefono, campo_actual, valor)
            
            # Avanzar al siguiente campo
            siguiente_indice = indice_actual + 1
            conversation_manager.set_datos_temporales(numero_telefono, '_campo_actual', siguiente_indice)
            
            if siguiente_indice >= len(campos_faltantes):
                # Ya tenemos todos los campos, proceder a validación final
                conversation_manager.set_datos_temporales(numero_telefono, '_campos_faltantes', None)
                conversation_manager.set_datos_temporales(numero_telefono, '_campo_actual', None)
                
                valido, error = conversation_manager.validar_y_guardar_datos(numero_telefono)
                
                if not valido:
                    conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_DATOS)
                    return f"❌ Hay algunos errores en los datos:\n\n{error}\n\nPor favor corrige y envía la información nuevamente."
                
                conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
                return ChatbotRules.get_mensaje_confirmacion(conversacion)
            else:
                # Preguntar por el siguiente campo
                siguiente_campo = campos_faltantes[siguiente_indice]
                return f"✅ Perfecto!\n\n{ChatbotRules._get_pregunta_campo_individual(siguiente_campo, conversacion.tipo_consulta)}"
        else:
            # Campo inválido, pedir de nuevo
            ChatbotRules._log_validacion_fallida(campo_actual)
            error_msg = ChatbotRules._get_error_campo_individual(campo_actual)
            return f"❌ {error_msg}\n\n{ChatbotRules._get_pregunta_campo_individual(campo_actual, conversacion.tipo_consulta)}"
    
    @staticmethod
    def _normalizar_fecha_pago(texto: str) -> Optional[str]:
        if not texto:
            return None
        match = re.match(r'^(\d{2})[./-](\d{2})[./-](\d{4})$', texto.strip())
        if not match:
            return None
        return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

    @staticmethod
    def _normalizar_monto(texto: str) -> Optional[str]:
        if not texto:
            return None
        raw = texto.strip().replace(" ", "")
        if not raw or not re.match(r'^[0-9.,]+$', raw):
            return None

        last_dot = raw.rfind(".")
        last_comma = raw.rfind(",")
        decimal_sep = None
        decimal_len = 0

        if last_dot != -1 and last_comma != -1:
            last_idx = last_dot if last_dot > last_comma else last_comma
            decimal_sep = "." if last_dot > last_comma else ","
            decimal_len = len(re.sub(r"\D", "", raw[last_idx + 1 :]))
        else:
            last_idx = None
            if last_dot != -1:
                decimal_sep = "."
                last_idx = last_dot
            elif last_comma != -1:
                decimal_sep = ","
                last_idx = last_comma
            if decimal_sep and last_idx is not None:
                decimal_len = len(re.sub(r"\D", "", raw[last_idx + 1 :]))
                sep_count = raw.count(decimal_sep)
                if (sep_count > 1 and decimal_len > 2) or (
                    sep_count == 1 and decimal_len == 3 and len(raw) > 4
                ):
                    decimal_sep = None
                    decimal_len = 0

        digits_only = re.sub(r"\D", "", raw)
        if not digits_only:
            return None

        if decimal_sep and decimal_len > 0:
            integer_part = digits_only[:-decimal_len] or "0"
            decimal_part = digits_only[-decimal_len:]
            normalized = f"{integer_part}.{decimal_part}"
        elif decimal_sep and decimal_len == 0:
            return None
        else:
            normalized = digits_only

        try:
            value = Decimal(normalized)
        except InvalidOperation:
            return None

        if value <= 0 or value > Decimal("2000000"):
            return None

        return normalized

    @staticmethod
    def _direccion_valida(valor: str) -> bool:
        if not valor:
            return False
        if not any(char.isalpha() for char in valor):
            return False
        if not any(char.isdigit() for char in valor):
            return False
        allowed_symbols = {".", ",", "#", "/", "-", "º", "°"}
        for char in valor:
            if char.isalpha() or char.isdigit() or char.isspace() or char in allowed_symbols:
                continue
            return False
        return True

    @staticmethod
    def _log_validacion_fallida(campo: str) -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info("validation_failed field=%s", campo)

    @staticmethod
    def _validar_campo_individual(campo: str, valor: str) -> bool:
        if campo == 'fecha_pago':
            return ChatbotRules._normalizar_fecha_pago(valor) is not None
        if campo == 'monto':
            return ChatbotRules._normalizar_monto(valor) is not None
        if campo == 'direccion':
            return ChatbotRules._direccion_valida(valor)
        if campo == 'piso_depto':
            return len(valor) >= 1
        if campo == 'comentario':
            return True
        if campo == 'tipo_servicio':
            return ChatbotRules._match_service_option(valor) is not None
        if campo == 'direccion_servicio':
            return ChatbotRules._direccion_valida(valor)
        if campo == 'detalle_servicio':
            return len(valor) >= 5
        return False
    
    @staticmethod
    def _get_error_campo_individual(campo: str) -> str:
        errores = {
            'fecha_pago': "Usá el formato dd/mm/yyyy (ej: 12/09/2025).",
            'monto': "Ingresá un monto válido mayor a 0 y hasta 2000000.",
            'direccion': "La dirección debe tener letras y números. Solo se permiten . , # / - º °",
            'piso_depto': "Indica piso/departamento/UF.",
            'comprobante': "Envía una imagen o PDF del comprobante, o escribe “Saltar”.",
            'tipo_servicio': "Seleccioná: Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos u Otro reclamo.",
            'direccion_servicio': "La dirección debe tener letras y números. Solo se permiten . , # / - º °",
            'detalle_servicio': "Contanos un poco más sobre el problema (mínimo 5 caracteres).",
        }
        return errores.get(campo, "El formato no es válido.")
    
    @staticmethod
    def _validar_ubicacion_geografica(direccion: str) -> str:
        """
        Valida si una dirección especifica CABA o Provincia usando comparación de keywords
        Retorna: 'CABA', 'PROVINCIA', o 'UNCLEAR'
        """
        direccion_lower = direccion.lower()
        
        # Buscar keywords en la dirección
        try:
            for sinonimo in SINONIMOS_CABA:
                if sinonimo in direccion_lower:
                    return 'CABA'
            
            for sinonimo in SINONIMOS_PROVINCIA:
                if sinonimo in direccion_lower:
                    return 'PROVINCIA'
        except Exception:
            print('LOCATION ERROR: NO SE PUDO VALIDAR CON KEYWORDS SI ES CABA O PROVINCIA')
            return 'UNCLEAR'
            
        # Si no encuentra keywords, retornar UNCLEAR para que el usuario seleccione manualmente
        return 'UNCLEAR'
    
    @staticmethod
    def _get_mensaje_seleccion_ubicacion() -> str:
        return """📍 *¿Tu dirección es en...*
1️⃣ *CABA*
2️⃣ *Provincia de Buenos Aires*
"""
    
    @staticmethod
    def _procesar_seleccion_ubicacion(numero_telefono: str, mensaje: str) -> str:
        """
        Procesa la selección del usuario para CABA o Provincia
        Acepta números (1, 2) y texto (caba, provincia, capital federal, bs as, etc.)
        """
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        direccion_original = conversacion.datos_temporales.get('_direccion_pendiente', '')
        
        # Normalizar entrada del usuario (con acentos y mayúsculas)
        texto_normalizado = normalizar_texto(mensaje)
        
        # Verificar si es CABA (opción 1 o sinónimos normalizados)
        if texto_normalizado == '1' or texto_normalizado in SINONIMOS_CABA_NORM:
            # Actualizar la dirección con CABA
            direccion_final = f"{direccion_original}, CABA"
            conversation_manager.set_datos_temporales(numero_telefono, 'direccion', direccion_final)
            conversation_manager.set_datos_temporales(numero_telefono, '_direccion_pendiente', None)
            
            # Continuar con el flujo normal
            return ChatbotRules._continuar_despues_validacion_ubicacion(numero_telefono)
            
        # Verificar si es Provincia (opción 2 o sinónimos normalizados)
        elif texto_normalizado == '2' or texto_normalizado in SINONIMOS_PROVINCIA_NORM:
            # Actualizar la dirección con Provincia
            direccion_final = f"{direccion_original}, Provincia de Buenos Aires"
            conversation_manager.set_datos_temporales(numero_telefono, 'direccion', direccion_final)
            conversation_manager.set_datos_temporales(numero_telefono, '_direccion_pendiente', None)
            
            # Continuar con el flujo normal
            return ChatbotRules._continuar_despues_validacion_ubicacion(numero_telefono)
        else:
            return "❌ Por favor responde *1* para CABA, *2* para Provincia, o escribe el nombre de tu ubicación (ej: CABA, Provincia, Capital Federal, Buenos Aires)."
    
    @staticmethod
    def _continuar_despues_validacion_ubicacion(numero_telefono: str) -> str:
        """
        Continúa el flujo después de validar la ubicación geográfica
        """
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        
        # Verificar si estábamos en flujo de datos individuales
        campos_faltantes = conversacion.datos_temporales.get('_campos_faltantes', [])
        indice_actual = conversacion.datos_temporales.get('_campo_actual', 0)
        
        if campos_faltantes and indice_actual is not None:
            # Volver al flujo de preguntas individuales
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_DATOS_INDIVIDUALES)
            
            if indice_actual >= len(campos_faltantes):
                # Ya tenemos todos los campos, proceder a validación final
                valido, error = conversation_manager.validar_y_guardar_datos(numero_telefono)
                
                if not valido:
                    conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_DATOS)
                    return f"❌ Hay algunos errores en los datos:\n\n{error}\n\nPor favor corrige y envía la información nuevamente."
                
                conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
                return ChatbotRules.get_mensaje_confirmacion(conversacion)
            else:
                # Continuar con el siguiente campo faltante
                siguiente_campo = campos_faltantes[indice_actual]
                return f"✅ Perfecto!\n\n{ChatbotRules._get_pregunta_campo_individual(siguiente_campo, conversacion.tipo_consulta)}"
        else:
            # VERIFICAR SI ESTAMOS EN FLUJO SECUENCIAL
            if conversacion.estado_anterior == EstadoConversacion.RECOLECTANDO_SECUENCIAL or len([k for k in conversacion.datos_temporales.keys() if not k.startswith('_')]) <= 2:
                # Continuar flujo secuencial - pedir siguiente campo
                conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
                siguiente_campo = conversation_manager.get_campo_siguiente(numero_telefono)
                
                if siguiente_campo:
                    conversacion_actualizada = conversation_manager.get_conversacion(numero_telefono)
                    return ChatbotRules._get_pregunta_campo_secuencial(siguiente_campo, conversacion_actualizada.tipo_consulta)
                else:
                    # Todos los campos están completos
                    valido, error = conversation_manager.validar_y_guardar_datos(numero_telefono)
                    
                    if not valido:
                        # Reportar validación final fallida como fricción
                        try:
                            from services.error_reporter import error_reporter, ErrorTrigger

                            error_reporter.capture_experience_issue(
                                ErrorTrigger.VALIDATION_REPEAT,
                                {
                                    "conversation_id": numero_telefono,
                                    "numero_telefono": numero_telefono,
                                    "estado_actual": conversacion.estado,
                                    "estado_anterior": conversacion.estado_anterior,
                                    "tipo_consulta": conversacion.tipo_consulta,
                                    "validation_info": {"error": error},
                                }
                            )
                        except Exception:
                            pass
                        return f"❌ Hay algunos errores en los datos:\n{error}"
                    
                    conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
                    return ChatbotRules.get_mensaje_confirmacion(conversacion)
            else:
                # Flujo normal, proceder a confirmación
                valido, error = conversation_manager.validar_y_guardar_datos(numero_telefono)
                
                if not valido:
                    conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_DATOS)
                    return f"❌ Hay algunos errores en los datos:\n\n{error}\n\nPor favor corrige y envía la información nuevamente."
                
                conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
                return ChatbotRules.get_mensaje_confirmacion(conversacion)
    
    @staticmethod
    def _extraer_datos_con_llm(mensaje: str) -> dict:
        """
        Usa el servicio NLU para extraer datos cuando el parsing básico no es suficiente
        """
        try:
            from services.nlu_service import nlu_service
            return nlu_service.extraer_datos_estructurados(mensaje)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en extracción LLM: {str(e)}")
            return {}
    
    @staticmethod
    def get_mensaje_final_exito() -> str:
        return """¡Listo! Registramos tu información ✅.

Si necesitás algo más, escribí "hola" para comenzar de nuevo."""
    
    @staticmethod
    def get_mensaje_error_opcion() -> str:
        opciones = []
        for idx, option in enumerate(ChatbotRules.MENU_OPTIONS, start=1):
            opciones.append(f"• *{idx}* para {option['text']}")
        opciones_texto = "\n".join(opciones)
        return f"""❌ No entendí tu selección.

Por favor responde con:
{opciones_texto}

_💡 También puedes describir tu necesidad con tus propias palabras y yo intentaré entenderte._"""
    
    @staticmethod
    def get_mensaje_datos_incompletos() -> str:
        return """⚠️ Parece que falta información importante.

Por favor completá los datos solicitados para poder continuar."""
    
    @staticmethod
    def _get_mensaje_pregunta_campo_a_corregir(tipo_consulta: TipoConsulta) -> str:
        if tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            return """❌ Entendido que hay información incorrecta.

¿Qué campo deseas corregir?
1️⃣ Fecha de pago
2️⃣ Monto
3️⃣ Dirección
4️⃣ Piso/Departamento/Cochera
5️⃣ Comprobante
6️⃣ Comentario
7️⃣ Todo (reiniciar)

Responde con el número del campo que deseas modificar."""

        return """❌ Entendido que hay información incorrecta.

¿Qué campo deseas corregir?
1️⃣ Tipo de reclamo
2️⃣ Ubicación
3️⃣ Piso/Departamento/UF
4️⃣ Detalle
5️⃣ Todo (reiniciar)

Responde con el número del campo que deseas modificar."""
    
    @staticmethod
    def _procesar_correccion_campo(numero_telefono: str, mensaje: str) -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        tipo_consulta = conversacion.tipo_consulta

        if tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            opciones_correccion = {
                '1': 'fecha_pago',
                '1️⃣': 'fecha_pago',
                '2': 'monto',
                '2️⃣': 'monto',
                '3': 'direccion',
                '3️⃣': 'direccion',
                '4': 'piso_depto',
                '4️⃣': 'piso_depto',
                '5': 'comprobante',
                '5️⃣': 'comprobante',
                '6': 'comentario',
                '6️⃣': 'comentario',
                '7': 'todo',
                '7️⃣': 'todo',
            }
        else:
            opciones_correccion = {
                '1': 'tipo_servicio',
                '1️⃣': 'tipo_servicio',
                '2': 'direccion_servicio',
                '2️⃣': 'direccion_servicio',
                '3': 'piso_depto',
                '3️⃣': 'piso_depto',
                '4': 'detalle_servicio',
                '4️⃣': 'detalle_servicio',
                '5': 'todo',
                '5️⃣': 'todo',
            }

        campo = opciones_correccion.get(mensaje)

        if not campo:
            return "❌ No entendí tu selección. " + ChatbotRules._get_mensaje_pregunta_campo_a_corregir(tipo_consulta)

        if campo == 'todo':
            conversation_manager.clear_datos_temporales(numero_telefono)
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
            if tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
                mensaje_tipo = (
                    "Perfecto 👍\n"
                    "Para ayudarte mejor, voy a hacerte unas preguntas cortitas.\n"
                    "¿Qué tipo de reclamo queres realizar?"
                )
                success = ChatbotRules.send_service_type_buttons(numero_telefono, mensaje_tipo)
                if success:
                    return ""
                return (
                    f"{mensaje_tipo}\n"
                    "Opciones: Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos, Otro reclamo."
                )
            if not numero_telefono.startswith("messenger:"):
                success = ChatbotRules.send_fecha_pago_hoy_button(numero_telefono)
                if success:
                    return ""
            return f"✏️ Entendido. {ChatbotRules.get_mensaje_recoleccion_datos(tipo_consulta)}"

        conversation_manager.set_datos_temporales(numero_telefono, '_campo_a_corregir', campo)
        conversation_manager.update_estado(numero_telefono, EstadoConversacion.CORRIGIENDO_CAMPO)

        if campo == 'tipo_servicio':
            mensaje_tipo = "Seleccioná el tipo de reclamo correcto:"
            success = ChatbotRules.send_service_type_buttons(numero_telefono, mensaje_tipo)
            if success:
                return ""
            return (
                f"{mensaje_tipo}\n"
                "Opciones: Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos, Otro reclamo."
            )

        if campo == 'fecha_pago' and not numero_telefono.startswith("messenger:"):
            success = ChatbotRules.send_fecha_pago_hoy_button(numero_telefono)
            if success:
                return ""

        return (
            "✅ Perfecto. Por favor envía el nuevo valor para: "
            f"{ChatbotRules._get_pregunta_campo_individual(campo, conversacion.tipo_consulta)}"
        )
        
    @staticmethod
    def _procesar_correccion_campo_especifico(numero_telefono: str, mensaje: str) -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        campo = conversacion.datos_temporales.get('_campo_a_corregir')
        
        if not campo:
            # Error, volver al inicio
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.ESPERANDO_OPCION)
            return "🤖 Hubo un error. Escribe 'hola' para comenzar de nuevo."
        
        valor = mensaje.strip()
        if campo == 'fecha_pago':
            fecha_rel = _parse_fecha_hoy_ayer(valor)
            if fecha_rel:
                valor = fecha_rel
            else:
                fecha_norm = ChatbotRules._normalizar_fecha_pago(valor)
                if fecha_norm:
                    valor = fecha_norm
        if campo == 'monto':
            monto_norm = ChatbotRules._normalizar_monto(valor)
            if monto_norm:
                valor = monto_norm
        if campo == 'tipo_servicio':
            matched = ChatbotRules._match_service_option(valor)
            if not matched:
                ChatbotRules._log_validacion_fallida(campo)
                error_msg = ChatbotRules._get_error_campo_individual(campo)
                return f"❌ {error_msg}\n\n{ChatbotRules._get_pregunta_campo_individual(campo, conversacion.tipo_consulta)}"
            valor = matched
        elif campo == 'comentario' and valor.lower() in ['saltar', 'skip', 'no', 'n/a', 'na']:
            valor = ""
        elif campo == 'comprobante' and valor.lower() in ['saltar', 'skip', 'no', 'n/a', 'na']:
            valor = ""
        elif not ChatbotRules._validar_campo_individual(campo, valor):
            ChatbotRules._log_validacion_fallida(campo)
            error_msg = ChatbotRules._get_error_campo_individual(campo)
            return (
                f"❌ {error_msg}\n\nPor favor envía un valor válido para: "
                f"{ChatbotRules._get_pregunta_campo_individual(campo, conversacion.tipo_consulta)}"
            )

        conversation_manager.set_datos_temporales(numero_telefono, campo, valor)

        if conversacion.datos_temporales.get("_direccion_para_guardar") is not None:
            if campo == "piso_depto":
                if conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
                    direccion = conversacion.datos_temporales.get("direccion_servicio", "")
                else:
                    direccion = conversacion.datos_temporales.get("direccion", "")
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_direccion_para_guardar",
                    {"direccion": direccion, "piso_depto": valor},
                )
            elif campo in {"direccion", "direccion_servicio"}:
                base, sugerido = ChatbotRules._extraer_piso_depto_de_direccion(valor)
                piso_actual = conversacion.datos_temporales.get("piso_depto", "")
                piso = sugerido or piso_actual
                conversation_manager.set_datos_temporales(
                    numero_telefono,
                    "_direccion_para_guardar",
                    {"direccion": base or valor, "piso_depto": piso or ""},
                )

        valido, error = conversation_manager.validar_y_guardar_datos(numero_telefono)
        if not valido:
            return f"❌ Error al actualizar: {error}"

        conversation_manager.set_datos_temporales(numero_telefono, '_campo_a_corregir', None)
        conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
        conversacion_actualizada = conversation_manager.get_conversacion(numero_telefono)
        return f"✅ Campo actualizado correctamente.\n\n{ChatbotRules.get_mensaje_confirmacion(conversacion_actualizada)}"
    
    @staticmethod
    def procesar_mensaje(numero_telefono: str, mensaje: str, nombre_usuario: str = "") -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        
        # Guardar nombre de usuario si es la primera vez que lo vemos
        if nombre_usuario and not conversacion.nombre_usuario:
            conversation_manager.set_nombre_usuario(numero_telefono, nombre_usuario)

        mensaje_limpio = mensaje.strip().lower()
        is_greeting = ChatbotRules._is_greeting_command(mensaje)

        # Reanudar o mantener pausa por emergencia
        if ChatbotRules._is_emergency_paused(conversacion):
            if ChatbotRules._is_resume_command(mensaje_limpio):
                ChatbotRules._clear_emergency_pause(numero_telefono)
                return "Retomamos la conversación. Podés continuar donde quedamos."
            cached = ChatbotRules._emergency_message_cached(numero_telefono)
            return cached or ""

        # Interceptar emergencias antes de cualquier otro flujo
        if ChatbotRules._detect_emergency_intent(mensaje, conversacion):
            respuesta_emergencia = ChatbotRules._handle_emergency(numero_telefono, conversacion, mensaje)
            return respuesta_emergencia or ""

        if is_greeting:
            conversation_manager.reset_conversacion(numero_telefono)
            conversacion = conversation_manager.get_conversacion(numero_telefono)
            
            # Guardar nombre de usuario en la nueva conversación
            if nombre_usuario:
                conversation_manager.set_nombre_usuario(numero_telefono, nombre_usuario)
            
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.ESPERANDO_OPCION)
            
            # Ejecutar metrics en background para no bloquear
            try:
                from services.metrics_service import metrics_service
                import threading
                threading.Thread(target=lambda: metrics_service.on_conversation_started(), daemon=True).start()
            except Exception:
                pass
            
            # Enviar flujo de 3 mensajes: saludo + imagen + presentación (todo en background)
            return ChatbotRules._enviar_flujo_saludo_completo(numero_telefono, nombre_usuario)
        
        # INTERCEPTAR SOLICITUD DE HABLAR CON HUMANO EN CUALQUIER MOMENTO -> activar handoff
        from services.nlu_service import nlu_service
        if nlu_service.detectar_solicitud_humano(mensaje):
            ChatbotRules._activar_handoff(numero_telefono, mensaje)

            # Enviar mensaje de handoff con botones interactivos
            try:
                success = ChatbotRules.send_handoff_buttons(numero_telefono)
                if success:
                    return ""  # Los botones se enviaron exitosamente
                else:
                    # Fallback a mensaje de texto normal
                    profile = get_active_company_profile()
                    fuera_horario = ChatbotRules._esta_fuera_de_horario(profile.get('hours', ''))
                    base = (
                        "Ya me contacté con el equipo; en breve uno de nuestros asesores se unirá a la charla. 🙌\n"
                        "Por favor aguardá un momento."
                    )
                    if fuera_horario:
                        base += "\n\n🕒 En este momento estamos fuera de horario. Tomaremos tu caso y te responderemos a la brevedad."
                    return base
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error enviando botones de handoff: {str(e)}")
                # Fallback a mensaje de texto normal
                profile = get_active_company_profile()
                fuera_horario = ChatbotRules._esta_fuera_de_horario(profile.get('hours', ''))
                base = (
                    "Ya me contacté con el equipo; en breve uno de nuestros asesores se unirá a la charla. 🙌\n"
                    "Por favor aguardá un momento."
                )
                if fuera_horario:
                    base += "\n\n🕒 En este momento estamos fuera de horario. Tomaremos tu caso y te responderemos a la brevedad."
                return base
        
        # INTERCEPTAR CONSULTAS DE CONTACTO EN CUALQUIER MOMENTO (Contextual Intent Interruption)
        if nlu_service.detectar_consulta_contacto(mensaje):
            respuesta_contacto = nlu_service.generar_respuesta_contacto(mensaje)

            # Si estamos en un flujo activo, agregar mensaje para continuar
            if conversacion.estado not in [EstadoConversacion.INICIO, EstadoConversacion.ESPERANDO_OPCION]:
                respuesta_contacto += "\n\n💬 *Ahora sigamos con tu consulta anterior...*"

            return respuesta_contacto

        # INTERCEPTAR SOLICITUDES DE VOLVER AL MENÚ EN CUALQUIER MOMENTO
        if ChatbotRules._detectar_volver_menu(mensaje) and conversacion.estado not in [EstadoConversacion.INICIO, EstadoConversacion.ESPERANDO_OPCION]:
            # Limpiar datos temporales y volver al menú
            conversation_manager.clear_datos_temporales(numero_telefono)
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.ESPERANDO_OPCION)
            return "↩️ *Volviendo al menú principal...*\n\n" + ChatbotRules.get_mensaje_inicial_personalizado(conversacion.nombre_usuario)

        media_response = ChatbotRules._procesar_confirmacion_media(numero_telefono, mensaje)
        if media_response is not None:
            return media_response

        direccion_eliminar = ChatbotRules._procesar_eliminar_direccion_text(numero_telefono, mensaje)
        if direccion_eliminar is not None:
            return direccion_eliminar

        direccion_seleccion = ChatbotRules._procesar_seleccion_direccion_text(numero_telefono, mensaje)
        if direccion_seleccion is not None:
            return direccion_seleccion
        
        if conversacion.estado == EstadoConversacion.INICIO:
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.ESPERANDO_OPCION)
            return ChatbotRules._enviar_flujo_saludo_completo(numero_telefono, conversacion.nombre_usuario or nombre_usuario)
        
        elif conversacion.estado == EstadoConversacion.ESPERANDO_OPCION:
            return ChatbotRules._procesar_seleccion_opcion(numero_telefono, mensaje)
        
        elif conversacion.estado == EstadoConversacion.RECOLECTANDO_DATOS:
            return ChatbotRules._procesar_datos_contacto(numero_telefono, mensaje)
        
        elif conversacion.estado == EstadoConversacion.RECOLECTANDO_DATOS_INDIVIDUALES:
            return ChatbotRules._procesar_campo_individual(numero_telefono, mensaje)
        
        elif conversacion.estado == EstadoConversacion.RECOLECTANDO_SECUENCIAL:
            return ChatbotRules._procesar_campo_secuencial(numero_telefono, mensaje)
        
        elif conversacion.estado == EstadoConversacion.VALIDANDO_UBICACION:
            return ChatbotRules._procesar_seleccion_ubicacion(numero_telefono, mensaje_limpio)
        
        elif conversacion.estado == EstadoConversacion.CONFIRMANDO:
            return ChatbotRules._procesar_confirmacion(numero_telefono, mensaje_limpio)
        
        elif conversacion.estado == EstadoConversacion.CORRIGIENDO:
            return ChatbotRules._procesar_correccion_campo(numero_telefono, mensaje_limpio)
        
        elif conversacion.estado == EstadoConversacion.CORRIGIENDO_CAMPO:
            return ChatbotRules._procesar_correccion_campo_especifico(numero_telefono, mensaje)
        
        else:
            return "🤖 Hubo un error. Escribe 'hola' para comenzar de nuevo."

    @staticmethod
    def _esta_fuera_de_horario(hours_text: str) -> bool:
        """Heurística simple para fuera de horario. Si no se puede parsear, False.
        Aproximación AR (UTC-3): LV 8-17, S 9-13.
        """
        try:
            ahora = datetime.utcnow() - timedelta(hours=3)
            wd = ahora.weekday()  # 0 lunes
            h = ahora.hour
            if wd <= 4:
                return not (8 <= h < 17)
            if wd == 5:
                return not (9 <= h < 13)
            return True
        except Exception:
            return False
    
    @staticmethod
    def _procesar_seleccion_opcion(numero_telefono: str, mensaje: str) -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        opcion, source = ChatbotRules._match_menu_option(mensaje)
        if opcion:
            return ChatbotRules._aplicar_opcion_menu(numero_telefono, opcion, mensaje, source)

        # Fallback: usar NLU para mapear mensaje a intención
        from services.nlu_service import nlu_service
        tipo_consulta_nlu = nlu_service.mapear_intencion(mensaje)

        if tipo_consulta_nlu:
            return ChatbotRules._aplicar_tipo_consulta(numero_telefono, tipo_consulta_nlu, mensaje, "nlu")

        # Reportar intención no clara (fricción NLU)
        try:
            from services.error_reporter import error_reporter, ErrorTrigger

            error_reporter.capture_experience_issue(
                ErrorTrigger.NLU_UNCLEAR,
                {
                    "conversation_id": numero_telefono,
                    "numero_telefono": numero_telefono,
                    "estado_actual": conversacion.estado,
                    "estado_anterior": conversacion.estado_anterior,
                    "nlu_snapshot": {"input": mensaje},
                    "recommended_action": "Revisar patrones y prompt de clasificación",
                }
            )
        except Exception:
            pass
        try:
            from services.metrics_service import metrics_service

            metrics_service.on_nlu_unclear()
        except Exception:
            pass
        return ChatbotRules.get_mensaje_error_opcion()
    
    @staticmethod
    def _procesar_datos_contacto(numero_telefono: str, mensaje: str) -> str:
        # ENFOQUE LLM-FIRST: Usar OpenAI como parser primario
        datos_parseados = {}
        
        # Intentar extracción LLM primero (más potente para casos complejos)
        if len(mensaje) > 20:
            datos_llm = ChatbotRules._extraer_datos_con_llm(mensaje)
            if datos_llm:
                datos_parseados = datos_llm.copy()
        
        # Fallback: Si LLM no extrajo suficientes campos, usar parser básico
        campos_encontrados_llm = sum(1 for v in datos_parseados.values() if v and v != "")
        if campos_encontrados_llm < 2:
            datos_basicos = ChatbotRules._parsear_datos_contacto_basico(mensaje)
            # Combinar resultados, dando prioridad a LLM pero completando con parsing básico
            for key, value in datos_basicos.items():
                if value and not datos_parseados.get(key):
                    datos_parseados[key] = value
        
        # Limpiar el campo tipo_consulta que no necesitamos aquí
        if 'tipo_consulta' in datos_parseados:
            del datos_parseados['tipo_consulta']
        
        # Guardar los datos que sí se pudieron extraer
        campos_encontrados = []
        for key, value in datos_parseados.items():
            if value and value.strip():
                conversation_manager.set_datos_temporales(numero_telefono, key, value.strip())
                campos_encontrados.append(key)
        
        # VALIDACIÓN GEOGRÁFICA: Si tenemos dirección, validar ubicación
        if 'direccion' in campos_encontrados:
            direccion = datos_parseados['direccion']
            ubicacion = ChatbotRules._validar_ubicacion_geografica(direccion)
            
            if ubicacion == 'UNCLEAR':
                # Necesita validación manual - guardar dirección pendiente y cambiar estado
                conversation_manager.set_datos_temporales(numero_telefono, '_direccion_pendiente', direccion)
                conversation_manager.update_estado(numero_telefono, EstadoConversacion.VALIDANDO_UBICACION)
                
                # Mostrar campos encontrados y preguntar ubicación
                mensaje_encontrados = ""
                if len(campos_encontrados) > 1:  # Más campos además de dirección
                    nombres_campos = {
                        'email': '📧 Email',
                        'direccion': '📍 Dirección', 
                        'horario_visita': '🕒 Horario',
                        'descripcion': '📝 Descripción'
                    }
                    campos_texto = [nombres_campos[campo] for campo in campos_encontrados if campo != 'direccion']
                    if campos_texto:
                        mensaje_encontrados = "Ya tengo:\n"
                        for campo in campos_texto:
                            mensaje_encontrados += f"{campo} ✅\n"
                
                return mensaje_encontrados + f"📍 Dirección detectada: *{direccion}*\n\n" + ChatbotRules._get_mensaje_seleccion_ubicacion()
        
        # Determinar qué campos faltan
        campos_requeridos = ['email', 'direccion', 'horario_visita', 'descripcion']
        campos_faltantes = [campo for campo in campos_requeridos if not datos_parseados.get(campo) or not datos_parseados.get(campo).strip()]
        
        if not campos_faltantes:
            # Todos los campos están presentes, proceder con validación final
            valido, error = conversation_manager.validar_y_guardar_datos(numero_telefono)
            
            if not valido:
                return f"❌ Hay algunos errores en los datos:\n\n{error}\n\nPor favor corrige y envía la información nuevamente."
            
            conversacion = conversation_manager.get_conversacion(numero_telefono)
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.CONFIRMANDO)
            return ChatbotRules.get_mensaje_confirmacion(conversacion)
        else:
            # Faltan campos, cambiar a modo de preguntas individuales
            conversation_manager.set_datos_temporales(numero_telefono, '_campos_faltantes', campos_faltantes)
            conversation_manager.set_datos_temporales(numero_telefono, '_campo_actual', 0)
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.RECOLECTANDO_DATOS_INDIVIDUALES)
            
            # Mostrar qué se encontró y preguntar por el primer campo faltante
            mensaje_encontrados = ""
            conversacion = conversation_manager.get_conversacion(numero_telefono)
            
            # Incluir campos pre-guardados en datos_temporales
            campos_temporales = conversacion.datos_temporales or {}
            todos_los_campos = set(campos_encontrados)
            for campo in ['email', 'direccion', 'horario_visita', 'descripcion']:
                if campos_temporales.get(campo):
                    todos_los_campos.add(campo)
            
            if todos_los_campos:
                nombres_campos = {
                    'email': '📧 Email',
                    'direccion': '📍 Dirección', 
                    'horario_visita': '🕒 Horario',
                    'descripcion': '📝 Descripción'
                }
                campos_texto = [nombres_campos[campo] for campo in todos_los_campos if campo in nombres_campos]
                mensaje_encontrados = "Ya tengo:\n"
                for campo in campos_texto:
                    mensaje_encontrados += f"{campo} ✅\n"
                mensaje_encontrados += "\n"
            
            return mensaje_encontrados + ChatbotRules._get_pregunta_campo_individual(campos_faltantes[0])
    
    @staticmethod
    def _procesar_confirmacion(numero_telefono: str, mensaje: str) -> str:
        conversacion = conversation_manager.get_conversacion(numero_telefono)
        if mensaje in ['si', 'sí', 'yes', 'confirmo', 'ok', 'correcto', '1', '1️⃣']:
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.ENVIANDO)
            return "⏳ Procesando tu solicitud..."
        elif mensaje in ['no', 'nope', 'incorrecto', 'error', '2', '2️⃣']:
            # Cambiar a estado de corrección y preguntar qué campo modificar
            conversation_manager.update_estado(numero_telefono, EstadoConversacion.CORRIGIENDO)
            return ChatbotRules._get_mensaje_pregunta_campo_a_corregir(conversacion.tipo_consulta)
        else:
            return "🤔 Por favor responde *SI* para confirmar o *NO* para corregir la información."
    
    @staticmethod
    def _parsear_datos_contacto_basico(mensaje: str) -> dict:
        import re
        
        # Buscar email con regex mejorado
        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        email_match = re.search(email_pattern, mensaje)
        email = email_match.group() if email_match else ""
        
        # Buscar CUIT (11 dígitos con o sin guiones)
        cuit_pattern = r"\b\d{2}-?\d{8}-?\d\b"
        cuit_match = re.search(cuit_pattern, mensaje)
        cuit = cuit_match.group() if cuit_match else ""
        
        # Dividir el mensaje en líneas para buscar patrones
        lineas = [linea.strip() for linea in mensaje.split('\n') if linea.strip()]
        
        direccion = ""
        horario = ""
        descripcion = ""
        razon_social = ""
        
        # Keywords mejoradas con scoring
        keywords_direccion = [
            'dirección', 'direccion', 'domicilio', 'ubicación', 'ubicacion', 
            'domicilio', 'ubicado', 'calle', 'avenida', 'av.', 'av ', 'barrio'
        ]
        keywords_horario = [
            'horario', 'hora', 'disponible', 'visita', 'lunes', 'martes', 
            'miércoles', 'miercoles', 'jueves', 'viernes', 'sabado', 'sábado', 'domingo', 'mañana', 
            'tarde', 'noche', 'am', 'pm'
        ]
        keywords_descripcion = [
            'necesito', 'descripción', 'descripcion', 'detalle', 'matafuego',
            'extintor', 'incendio', 'seguridad', 'oficina', 'empresa', 'local'
        ]
        
        # Buscar patrones con scoring
        for linea in lineas:
            linea_lower = linea.lower()
            
            # Saltar líneas que solo contienen email (ya lo tenemos)
            if email and linea.strip() == email:
                continue
            
            # Scoring para direccion
            score_direccion = sum(1 for kw in keywords_direccion if kw in linea_lower)
            # Scoring para horario
            score_horario = sum(1 for kw in keywords_horario if kw in linea_lower)
            # Scoring para descripcion
            score_descripcion = sum(1 for kw in keywords_descripcion if kw in linea_lower)
            
            # Determinar el valor extraído de la línea
            valor_extraido = linea.split(':', 1)[-1].strip() if ':' in linea else linea
            
            # Solo procesar si el valor no es el email ya encontrado
            if valor_extraido == email:
                continue
                
            # Asignar basado en scores
            if score_direccion > 0 and score_direccion >= score_horario and score_direccion >= score_descripcion and not direccion:
                direccion = valor_extraido
            elif score_horario > 0 and score_horario >= score_direccion and score_horario >= score_descripcion and not horario:
                horario = valor_extraido
            elif score_descripcion > 0 and score_descripcion >= score_direccion and score_descripcion >= score_horario and not descripcion:
                descripcion = valor_extraido
            elif len(linea) > 15 and score_direccion == score_horario == score_descripcion == 0:
                # Sin keywords específicas, clasificar por longitud y posición
                if not descripcion and any(word in linea_lower for word in ['necesito', 'quiero', 'para', 'equipar']):
                    descripcion = linea
                elif not direccion and len(linea) > 8:
                    direccion = linea
                elif not horario and len(linea) > 5:
                    horario = linea
        
        # Fallback: buscar por posición si no encontramos nada estructurado
        if not direccion and not horario and not descripcion and len(lineas) >= 3:
            mensaje_sin_email = mensaje
            if email:
                mensaje_sin_email = mensaje.replace(email, "").strip()
            
            partes = [parte.strip() for parte in mensaje_sin_email.split('\n') if parte.strip()]
            if len(partes) >= 3:
                direccion = partes[0] if not direccion else direccion
                horario = partes[1] if not horario else horario  
                descripcion = " ".join(partes[2:]) if not descripcion else descripcion
        
        # Validación mínima de longitud
        if len(direccion) < 5:
            direccion = ""
        if len(horario) < 3:
            horario = ""
        if len(descripcion) < 10:
            descripcion = ""
        if len(razon_social) < 2:
            razon_social = ""
        
        return {
            'email': email,
            'direccion': direccion,
            'horario_visita': horario,
            'descripcion': descripcion,
            'razon_social': razon_social,
            'cuit': cuit,
        }
