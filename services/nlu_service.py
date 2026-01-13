import os
import logging
import json
import re
import unicodedata
from typing import Optional, Dict, Any, Iterable
from openai import OpenAI
from chatbot.models import TipoConsulta
from templates.template import NLU_INTENT_PROMPT, NLU_MESSAGE_PARSING_PROMPT, PERSONALIZED_GREETING_PROMPT
from config.company_profiles import get_active_company_profile, get_company_info_text

logger = logging.getLogger(__name__)

CONTACT_INFO_PHRASE_PATTERN = re.compile(r"\binformacion\s+de\s+contacto\b")
PHONE_KEYWORDS = ("telefono", "tel", "celular", "cel", "movil")
WHATSAPP_KEYWORDS = ("whatsapp", "wsp", "wa", "wpp")
EMAIL_KEYWORDS = ("email", "mail", "correo")
CALL_PATTERNS = [
    re.compile(r"\bllamar(?:le|les|lo|los|la|las|me|nos)?\b"),
    re.compile(r"\bllamo\b"),
]
NUMERO_SYNONYMS_PATTERN = r"(?:\b(?:numero|nro\.?|num)\b|n°|nº|#)"
EXCLUSION_TERMS = (
    "cuenta",
    "factura",
    "reclamo",
    "seguimiento",
    "unidad",
    "depto",
    "dto",
    "piso",
    "contrato",
    "cliente",
    "servicio",
    "pedido",
    "tramite",
    "referencia",
    "comprobante",
    "recibo",
    "expensa",
    "expensas",
    "pago",
    "cbu",
    "dni",
    "cuit",
    "cuil",
)
EXCLUSION_PATTERN = re.compile(
    rf"{NUMERO_SYNONYMS_PATTERN}\s+de\s+(?:{'|'.join(EXCLUSION_TERMS)})\b"
)
CONTACT_ADJ_NUM_PATTERN = re.compile(
    rf"{NUMERO_SYNONYMS_PATTERN}\s+(?:de|para)?\s*(?:contacto|comunicarme)\b"
)
CONTACT_ADJ_EMAIL_PATTERN = re.compile(
    r"\b(?:email|mail|correo)\b\s+(?:de|para)?\s*(?:contacto|comunicarme)\b"
)


def _normalize_text(value: str) -> str:
    value = value.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


def _has_any_keyword(text: str, keywords: Iterable[str]) -> bool:
    for keyword in keywords:
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return True
    return False

# Patrones para detectar intención de hablar con humano/agente
HUMAN_INTENT_PATTERNS = [
    # Palabras clave directas
    r"\bhumano\b",
    r"\bpersona\b",
    r"\balguien\s+real\b",
    r"\batenci[oó]n\s+al\s+cliente\b",
    r"\bagente\b",
    r"\boperador(?:a)?\b",
    r"\brepresentante\b",
    r"\basesor(?:a)?\b",

    # Expresiones comunes
    r"\bquiero\s+hablar\b",
    r"\bnecesito\s+hablar\b",
    r"\bpuedo\s+hablar\b",
    r"\bhablar\s+con\s+(?:alguien|una\s+persona)\b",
    r"\bquiero\s+hablar\s+con\s+(?:alguien|una\s+persona)\b",
    r"\bquiero\s+hablar\s+con\s+(?:vos|ustedes)\b",
    r"\bnecesito\s+hablar\s+con\s+(?:alguien|una\s+persona)\b",
    r"\bcomunicar(?:me)?\s+con\s+(?:alguien|una\s+persona)\b",

    # Frustración / fallback
    r"no\s+me\s+entend[eé]s?",
    r"ninguna\s+opci[oó]n",
    r"ninguna\s+de\s+las\s+anteriores",
    r"quiero\s+que\s+me\s+atiendan?",

    # Mayúsculas / errores comunes
    r"HABLAR\s+CON\s+HUMANO",
    r"humnao",
    r"operadro",
]

class NLUService:
    
    def __init__(self):
        self._client = None

    @staticmethod
    def _matches_contact_adjacency(mensaje_lower: str) -> bool:
        return bool(
            CONTACT_ADJ_NUM_PATTERN.search(mensaje_lower)
            or CONTACT_ADJ_EMAIL_PATTERN.search(mensaje_lower)
        )

    @staticmethod
    def _has_contact_channels(mensaje_lower: str) -> bool:
        if _has_any_keyword(mensaje_lower, PHONE_KEYWORDS):
            return True
        if _has_any_keyword(mensaje_lower, WHATSAPP_KEYWORDS):
            return True
        if _has_any_keyword(mensaje_lower, EMAIL_KEYWORDS):
            return True
        return any(pattern.search(mensaje_lower) for pattern in CALL_PATTERNS)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY es requerido para usar NLU LLM")
            self._client = OpenAI(api_key=api_key)
        return self._client
    
    def mapear_intencion(self, mensaje_usuario: str) -> Optional[TipoConsulta]:
        """
        Mapea un mensaje de usuario a una de las opciones disponibles usando LLM
        """
        try:
            prompt = NLU_INTENT_PROMPT.render(mensaje_usuario=mensaje_usuario)

            response = self._get_client().chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un clasificador de intenciones para un chatbot de expensas y reclamos. Responde solo con la categoría exacta solicitada."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=10
            )
            
            resultado = response.choices[0].message.content.strip().upper()
            logger.info(f"NLU mapeo: '{mensaje_usuario}' -> '{resultado}'")
            
            # Mapear respuesta a enum
            mapeo = {
                'PAGO_EXPENSAS': TipoConsulta.PAGO_EXPENSAS,
                'SOLICITAR_SERVICIO': TipoConsulta.SOLICITAR_SERVICIO,
                'EMERGENCIA': TipoConsulta.EMERGENCIA
            }
            
            return mapeo.get(resultado)
            
        except Exception as e:
            logger.error(f"Error en mapeo de intención: {str(e)}")
            return None
    
    def extraer_datos_estructurados(self, mensaje_usuario: str) -> Dict[str, Any]:
        """
        Extrae datos de contacto de un mensaje usando LLM con enfoque semántico LLM-first
        """
        try:
            prompt = NLU_MESSAGE_PARSING_PROMPT.render(mensaje_usuario=mensaje_usuario)

            response = self._get_client().chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un extractor de datos para expensas y reclamos. Responde solo con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=200
            )
            
            resultado_text = response.choices[0].message.content.strip()
            logger.info(f"NLU extracción: '{mensaje_usuario}' -> '{resultado_text}'")
            
            # Intentar parsear JSON
            try:
                datos = json.loads(resultado_text)
                return datos
            except json.JSONDecodeError:
                logger.error(f"Error parseando JSON de LLM: {resultado_text}")
                return {}
            
        except Exception as e:
            logger.error(f"Error en extracción de datos: {str(e)}")
            return {}
    
    def validar_campo_individual(self, campo: str, valor: str, contexto: str = "") -> Dict[str, Any]:
        """
        Valida y mejora un campo individual usando LLM
        """
        try:
            prompts_campo = {
                'email': f"¿Es '{valor}' un email válido? Responde: {{'valido': true/false, 'sugerencia': 'email corregido o mensaje'}}",
                'direccion': f"¿Es '{valor}' una dirección válida en Argentina? Responde: {{'valido': true/false, 'sugerencia': 'dirección mejorada o mensaje'}}",
                'horario_visita': f"¿Es '{valor}' un horario/disponibilidad comprensible? Responde: {{'valido': true/false, 'sugerencia': 'horario mejorado o mensaje'}}",
                'descripcion': f"¿Es '{valor}' una descripción clara de servicios contra incendios? Responde: {{'valido': true/false, 'sugerencia': 'descripción mejorada o mensaje'}}"
            }
            
            if campo not in prompts_campo:
                return {'valido': True, 'sugerencia': valor}
            
            prompt = prompts_campo[campo]
            if contexto:
                prompt += f"\nContexto: {contexto}"
            
            response = self._get_client().chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Valida datos de contacto. Responde solo con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=100
            )
            
            resultado_text = response.choices[0].message.content.strip()
            try:
                return json.loads(resultado_text)
            except json.JSONDecodeError:
                return {'valido': True, 'sugerencia': valor}
            
        except Exception as e:
            logger.error(f"Error validando campo {campo}: {str(e)}")
            return {'valido': True, 'sugerencia': valor}
    
    
    def detectar_consulta_contacto(self, mensaje_usuario: str) -> bool:
        """
        Detecta si el usuario está preguntando sobre información de contacto de la empresa usando regex
        """
        try:
            mensaje_lower = _normalize_text(mensaje_usuario)

            if EXCLUSION_PATTERN.search(mensaje_lower):
                logger.info(
                    "Detección consulta contacto (regex): '%s' -> NO (exclusion)",
                    mensaje_usuario,
                )
                return False

            if CONTACT_INFO_PHRASE_PATTERN.search(mensaje_lower):
                logger.info(
                    "Detección consulta contacto (regex): '%s' -> CONTACTO (informacion)",
                    mensaje_usuario,
                )
                return True

            if self._has_contact_channels(mensaje_lower):
                logger.info(
                    "Detección consulta contacto (regex): '%s' -> CONTACTO (canal)",
                    mensaje_usuario,
                )
                return True

            if self._matches_contact_adjacency(mensaje_lower):
                logger.info(
                    "Detección consulta contacto (regex): '%s' -> CONTACTO (adjacency)",
                    mensaje_usuario,
                )
                return True

            logger.info("Detección consulta contacto (regex): '%s' -> NO", mensaje_usuario)
            return False
        except Exception as e:
            logger.error(f"Error detectando consulta de contacto: {str(e)}")
            return False

    def detectar_solicitud_humano(self, mensaje_usuario: str) -> bool:
        """
        Detecta si el usuario solicita hablar con un humano/agente.
        Usa patrones regex tolerantes a acentos y variaciones comunes.
        """
        try:
            mensaje_lower = _normalize_text(mensaje_usuario)

            # Negaciones simples para evitar falsos positivos
            negaciones = [
                r"no\s+quiero\s+hablar",
                r"no\s+humano",
                r"sin\s+humano",
            ]
            for neg in negaciones:
                if re.search(neg, mensaje_lower, re.IGNORECASE):
                    logger.info(f"Detección humano (regex): '{mensaje_usuario}' -> NO (negación)")
                    return False

            if "comunicarme" in mensaje_lower:
                if (
                    not self._matches_contact_adjacency(mensaje_lower)
                    and not self._has_contact_channels(mensaje_lower)
                ):
                    logger.info(
                        "Detección humano (regex): '%s' -> HUMANO (comunicarme sin canal)",
                        mensaje_usuario,
                    )
                    return True

            for pattern in HUMAN_INTENT_PATTERNS:
                if re.search(pattern, mensaje_lower, re.IGNORECASE):
                    logger.info(f"Detección humano (regex): '{mensaje_usuario}' -> HUMANO (pattern: {pattern})")
                    return True

            logger.info(f"Detección humano (regex): '{mensaje_usuario}' -> NO")
            return False
        except Exception as e:
            logger.error(f"Error detectando solicitud humano: {str(e)}")
            return False

    def generar_respuesta_humano(self, mensaje_usuario: str = "") -> str:
        """
        Genera un mensaje con teléfonos para hablar con una persona.
        Aclara que el teléfono público es solo para llamadas con una persona.
        """
        try:
            profile = get_active_company_profile()

            public_phone = ""
            mobile_phone = ""
            phone_single = ""

            if isinstance(profile.get('phone'), dict):
                public_phone = profile['phone'].get('public_phone', '')
                mobile_phone = profile['phone'].get('mobile_phone', '')
            else:
                phone_single = profile.get('phone', '')

            partes = [
                "👤 Si necesitás hablar con una persona ahora mismo:",
            ]

            if public_phone:
                partes.append(f"📞 Teléfono fijo (solo llamadas para hablar con una persona): {public_phone}")
            if mobile_phone:
                partes.append(f"📱 Celular / WhatsApp: {mobile_phone}")
            if not public_phone and not mobile_phone and phone_single:
                partes.append(f"📱 Teléfono: {phone_single}")

            partes.append("")
            partes.append("Si preferís, también puedo ayudarte por acá y luego te deriva un asesor 🙌")

            return "\n".join(partes).strip()
        except Exception as e:
            logger.error(f"Error generando respuesta humano: {str(e)}")
            # Fallback a info general de contacto
            return get_company_info_text()
    
    def generar_respuesta_contacto(self, mensaje_usuario: str) -> str:
        """
        Genera una respuesta estática sobre información de contacto de la empresa
        """
        try:
            company_profile = get_active_company_profile()
            contact_message = company_profile.get("contact_message")
            if contact_message:
                logger.info("Respuesta contacto generada (estatica) para: '%s'", mensaje_usuario)
                return contact_message

            logger.info("Respuesta contacto generada (fallback) para: '%s'", mensaje_usuario)
            return get_company_info_text()
        except Exception as e:
            logger.error(f"Error generando respuesta de contacto: {str(e)}")
            return get_company_info_text()
    
    def generar_saludo_personalizado(self, nombre_usuario: str = "", es_primera_vez: bool = True) -> str:
        """
        Genera un saludo personalizado usando el nombre del usuario si está disponible
        """
        try:
            company_profile = get_active_company_profile()
            
            prompt = PERSONALIZED_GREETING_PROMPT.render(
                bot_name=company_profile['bot_name'],
                company_name=company_profile['name'],
                user_name=nombre_usuario or "sin nombre",
                is_first_time=es_primera_vez
            )

            response = self._get_client().chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Eres {company_profile['bot_name']}, asistente virtual amigable de {company_profile['name']}. Genera saludos naturales y profesionales."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=150
            )
            
            saludo = response.choices[0].message.content.strip()
            logger.info(f"Saludo personalizado generado para usuario: '{nombre_usuario}'")
            
            return saludo
            
        except Exception as e:
            logger.error(f"Error generando saludo personalizado: {str(e)}")
            # Fallback a saludo estático si falla el LLM
            company_profile = get_active_company_profile()
            if nombre_usuario:
                return f"¡Hola {nombre_usuario}! 👋 Soy {company_profile['bot_name']} de {company_profile['name']}"
            else:
                return f"¡Hola! 👋 Soy {company_profile['bot_name']} de {company_profile['name']}"

# Instancia global del servicio
nlu_service = NLUService()
