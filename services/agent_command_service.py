import logging
import os
from typing import Optional
from chatbot.states import conversation_manager
from services.meta_whatsapp_service import meta_whatsapp_service
from services.phone_display import format_phone_for_agent

logger = logging.getLogger(__name__)


def _get_client_messaging_service(client_id: str):
    """
    Devuelve el servicio correcto para enviar mensajes al cliente.
    """
    if client_id.startswith("messenger:"):
        from services.meta_messenger_service import meta_messenger_service
        clean_id = client_id.replace("messenger:", "")
        return meta_messenger_service, clean_id
    else:
        return meta_whatsapp_service, client_id


class AgentCommandService:
    """Servicio para gestionar comandos del agente en el sistema de cola de handoffs."""

    _OPTIN_COMMAND = os.getenv("OPTIN_COMMAND", "optin").strip().lower()

    # Comandos reconocidos y sus alias
    COMMAND_ALIASES = {
        'done': ['done', 'd', 'resuelto', 'r', 'resolved', 'finalizar', 'cerrar'],
        'next': ['next', 'n', 'siguiente', 'sig', 'skip', 's'],
        'queue': ['queue', 'q', 'cola', 'list', 'lista', 'c'],
        'help': ['help', 'h', 'ayuda', '?', 'comandos'],
        'active': ['active', 'current', 'a', 'activo', 'actual'],
        'historial': ['historial', 'history', 'contexto', 'context', 'chat', 'recap', 'mensajes', 'messages'],
        'optin': [_OPTIN_COMMAND] if _OPTIN_COMMAND else ['optin'],
    }

    def is_command(self, message: str) -> bool:
        """
        Verifica si un mensaje es un comando del agente.

        Args:
            message: Mensaje a verificar

        Returns:
            bool: True si es un comando
        """
        if not message or not message.strip():
            return False

        clean_msg = message.strip().lower()

        # Verificar si empieza con /
        if clean_msg.startswith('/'):
            return True

        return False

    def parse_command(self, message: str) -> Optional[str]:
        """
        Extrae y normaliza el comando del mensaje.

        Args:
            message: Mensaje con comando

        Returns:
            Optional[str]: Comando normalizado o None si no se reconoce
        """
        if not message or not message.strip():
            return None

        clean_msg = message.strip().lower()

        # Remover / si existe
        if clean_msg.startswith('/'):
            clean_msg = clean_msg[1:]

        # Buscar en los alias
        for command_name, aliases in self.COMMAND_ALIASES.items():
            if clean_msg in aliases:
                return command_name

        return None

    def execute_done_command(self, agent_phone: str) -> str:
        """
        Ejecuta el comando /done: ofrece encuesta al cliente o cierra conversación si encuestas deshabilitadas.

        Args:
            agent_phone: Número del agente (para logs)

        Returns:
            str: Mensaje de respuesta para el agente
        """
        try:
            from services.survey_service import survey_service
            from chatbot.models import EstadoConversacion
            from datetime import datetime

            active_phone = conversation_manager.get_active_handoff()

            if not active_phone:
                return "⚠️ No hay conversación activa para finalizar.\n\nUsa /queue para ver el estado de la cola."

            # Obtener info del cliente
            conversacion = conversation_manager.get_conversacion(active_phone)
            nombre_cliente = conversacion.nombre_usuario or "Cliente"

            if conversacion.estado in (
                EstadoConversacion.ESPERANDO_RESPUESTA_ENCUESTA,
                EstadoConversacion.ENCUESTA_SATISFACCION,
            ):
                return ""

            # Verificar si las encuestas están habilitadas
            if survey_service.is_enabled():
                # Enviar mensaje opt-in/opt-out de encuesta usando el servicio correcto
                survey_message = self._build_survey_offer_message(nombre_cliente)
                service, clean_id = _get_client_messaging_service(active_phone)
                success = service.send_text_message(clean_id, survey_message)

                if success:
                    # Cambiar estado a esperar respuesta de encuesta
                    conversacion.estado = EstadoConversacion.ESPERANDO_RESPUESTA_ENCUESTA
                    conversacion.survey_offered = True
                    conversacion.survey_offer_sent_at = datetime.utcnow()
                    conversacion.atendido_por_humano = False

                    conversation_manager.remove_from_handoff_queue(active_phone)

                    logger.info(
                        "survey_offer_sent client_phone=%s agent_phone=%s state=%s",
                        active_phone,
                        agent_phone,
                        conversacion.estado,
                    )
                    return self._build_done_agent_message(
                        nombre_cliente,
                        active_phone,
                        with_survey=True,
                    )
                else:
                    logger.error(f"❌ Error enviando oferta de encuesta al cliente {active_phone}")
                    active_now = conversation_manager.get_active_handoff()
                    if active_now == active_phone:
                        conversation_manager.close_active_handoff()
                    else:
                        conversation_manager.remove_from_handoff_queue(active_phone)
                        conversation_manager.finalizar_conversacion(active_phone)
                    return f"❌ Error enviando mensaje al cliente. Intenta nuevamente."
            else:
                # Encuestas deshabilitadas: comportamiento original (cerrar inmediatamente)
                service, clean_id = _get_client_messaging_service(active_phone)
                service.send_text_message(
                    clean_id,
                    "¡Gracias por tu consulta! Damos por finalizada esta conversación. ✅"
                )

                # Cerrar conversación activa (esto automáticamente activa la siguiente)
                next_phone = conversation_manager.close_active_handoff()

                logger.info(f"✅ Agente {agent_phone} finalizó conversación con {active_phone} (encuestas deshabilitadas)")

                return self._build_done_agent_message(
                    nombre_cliente,
                    active_phone,
                    with_survey=False,
                )

        except Exception as e:
            logger.error(f"Error ejecutando comando /done: {e}")
            return f"❌ Error finalizando conversación: {str(e)}"

    def _build_done_agent_message(self, nombre_cliente: str, telefono: str, with_survey: bool) -> str:
        queue_size = conversation_manager.get_queue_size()
        telefono_display = format_phone_for_agent(telefono)
        base = f"✅ Cierre enviado a {nombre_cliente} ({telefono_display})."
        if with_survey:
            base += " ⏳ Encuesta en curso (auto-cierre 15 min)."
        if queue_size > 1:
            base += " Usa /queue o /next."
        else:
            base += " Usa /queue."
        if queue_size == 0:
            base += " Cola vacia."
        return base

    def _build_survey_offer_message(self, nombre_cliente: str) -> str:
        """
        Construye el mensaje de oferta de encuesta con opt-in/opt-out.

        Args:
            nombre_cliente: Nombre del cliente

        Returns:
            str: Mensaje formateado
        """
        return f"""¡Gracias por tu consulta, {nombre_cliente}! 🙏

¿Nos ayudas con 3 preguntas rápidas? (toma menos de 1 minuto)
Tu opinión es muy valiosa para mejorar nuestro servicio.

1️⃣ Sí, con gusto
2️⃣ No, gracias

Si no respondes en 2 minutos, cerraremos la conversación automáticamente."""

    def execute_next_command(self, agent_phone: str) -> str:
        """
        Ejecuta el comando /next: mueve conversación activa al final y activa siguiente.

        Args:
            agent_phone: Número del agente (para logs)

        Returns:
            str: Mensaje de respuesta para el agente
        """
        try:
            active_phone = conversation_manager.get_active_handoff()

            if not active_phone:
                return "⚠️ No hay conversación activa.\n\nUsa /queue para ver el estado de la cola."

            queue_size = conversation_manager.get_queue_size()

            if queue_size <= 1:
                return "⚠️ Solo hay una conversación en la cola. Usa /done para finalizarla."

            # Obtener info antes de cambiar
            old_conversacion = conversation_manager.get_conversacion(active_phone)
            old_nombre = old_conversacion.nombre_usuario or "Cliente anterior"

            # Mover al final y activar siguiente
            next_phone = conversation_manager.move_to_next_in_queue()

            if next_phone:
                new_conversacion = conversation_manager.get_conversacion(next_phone)
                new_nombre = new_conversacion.nombre_usuario or "Nuevo cliente"

                logger.info(f"✅ Agente {agent_phone} cambió de {active_phone} a {next_phone}")

                tip = "💡 Para ver los últimos mensajes del cliente activo: /historial"
                return (
                    f"🔄 Conversación con {old_nombre} movida al final de la cola.\n\n"
                    f"✅ Activando conversación con {new_nombre}...\n\n"
                    f"{tip}"
                )
            else:
                return "❌ Error al cambiar de conversación."

        except Exception as e:
            logger.error(f"Error ejecutando comando /next: {e}")
            return f"❌ Error cambiando de conversación: {str(e)}"

    def execute_queue_command(self, agent_phone: str) -> str:
        """
        Ejecuta el comando /queue: muestra estado completo de la cola.

        Args:
            agent_phone: Número del agente (para logs)

        Returns:
            str: Mensaje con estado de la cola formateado
        """
        try:
            queue_status = conversation_manager.format_queue_status()
            logger.info(f"Agente {agent_phone} solicitó estado de cola")
            return queue_status

        except Exception as e:
            logger.error(f"Error ejecutando comando /queue: {e}")
            return f"❌ Error obteniendo estado de cola: {str(e)}"

    def execute_help_command(self, agent_phone: str) -> str:
        """
        Ejecuta el comando /help: muestra ayuda de comandos.

        Args:
            agent_phone: Número del agente (para logs)

        Returns:
            str: Mensaje de ayuda
        """
        help_text = """📚 *COMANDOS DISPONIBLES*

🔹 *Comandos principales (en español):*

**/resuelto** (alias cortos: /r)
   Cierra la conversación activa y activa la siguiente en la cola.

**/siguiente** (alias cortos: /s)
   Mueve la conversación activa al final y activa la próxima.

**/cola** (alias cortos: /c)
   Muestra toda la cola y quién está activo.

━━━━━━━━━━━━━━━━━━━━━━━

🔹 *Comandos de información:*

**/activo** (alias cortos: /a)
   Muestra la conversación activa.

**/historial** (alias cortos: /h)
   Muestra los últimos mensajes del cliente activo.

**/ayuda**
   Muestra esta ayuda rápida.

**/optin**
   Envía el consentimiento para habilitar plantillas.

━━━━━━━━━━━━━━━━━━━━━━━

💡 *Funcionamiento del Sistema de Cola:*

• Siempre hay UNA conversación activa
• Los mensajes que escribas van al cliente activo
• Usa /resuelto cuando termines con un cliente
• La siguiente conversación se activa automáticamente
• Puedes ver la cola completa con /cola

━━━━━━━━━━━━━━━━━━━━━━━

❓ *¿Dudas?* Pregúntale al equipo técnico."""

        logger.info(f"Agente {agent_phone} solicitó ayuda")
        return help_text

    def execute_active_command(self, agent_phone: str) -> str:
        """
        Ejecuta el comando /active: muestra conversación activa.

        Args:
            agent_phone: Número del agente (para logs)

        Returns:
            str: Mensaje con información de conversación activa
        """
        try:
            active_phone = conversation_manager.get_active_handoff()

            if not active_phone:
                return "ℹ️ No hay conversación activa.\n\nUsa /queue para ver el estado de la cola."

            conversacion = conversation_manager.get_conversacion(active_phone)
            nombre = conversacion.nombre_usuario or "Sin nombre"
            queue_size = conversation_manager.get_queue_size()

            # Calcular tiempo activo
            tiempo_activo = ""
            if conversacion.handoff_started_at:
                from datetime import datetime
                delta = datetime.utcnow() - conversacion.handoff_started_at
                minutos = int(delta.total_seconds() / 60)
                if minutos < 60:
                    tiempo_activo = f"{minutos} min"
                else:
                    horas = minutos // 60
                    mins = minutos % 60
                    tiempo_activo = f"{horas}h {mins}min"

            telefono_display = format_phone_for_agent(active_phone)
            message = f"""🟢 *CONVERSACIÓN ACTIVA*

*Cliente:* {nombre}
*Teléfono:* {telefono_display}
*Tiempo activo:* {tiempo_activo or 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━

📋 *Cola:* {queue_size} conversación(es) total(es)

💬 Los mensajes que escribas irán a {nombre}."""

            if queue_size > 1:
                message += f"\n\nUsa /queue para ver todas las conversaciones o /next para cambiar."

            logger.info(f"Agente {agent_phone} solicitó conversación activa")
            return message

        except Exception as e:
            logger.error(f"Error ejecutando comando /active: {e}")
            return f"❌ Error obteniendo conversación activa: {str(e)}"
    
    def execute_historial_command(self, agent_phone: str, numero_especifico: Optional[str] = None) -> str:
        """
        Ejecuta el comando /historial: muestra los últimos mensajes de la conversación activa.

        Args:
            agent_phone: Número del agente (para logs)
            numero_especifico: Opcional - número específico si el agente pone /historial +549...

        Returns:
            str: Mensaje de respuesta con el historial
        """
        try:
            # Determinar de qué conversación mostrar historial
            if numero_especifico:
                numero_telefono = numero_especifico
                conversacion = conversation_manager.get_conversacion(numero_telefono)
                
                # Verificar que esté en handoff
                if not (conversacion.atendido_por_humano or conversacion.estado.value == 'atendido_por_humano'):
                    telefono_display = format_phone_for_agent(numero_telefono)
                    return f"⚠️ El número {telefono_display} no está en handoff actualmente."
            else:
                # Usar conversación activa
                active_phone = conversation_manager.get_active_handoff()
                
                if not active_phone:
                    return "⚠️ No hay conversación activa.\n\nUsa /queue para ver las conversaciones en cola."
                
                numero_telefono = active_phone
                conversacion = conversation_manager.get_conversacion(numero_telefono)
            
            # Obtener historial (últimos 5 mensajes)
            historial = conversation_manager.get_message_history(numero_telefono, limit=5)
            
            if not historial:
                nombre = conversacion.nombre_usuario or "Cliente"
                return f"📜 *HISTORIAL - {nombre}*\n\n⚠️ No hay mensajes registrados en esta conversación aún.\n\nEl historial comienza a guardarse después del primer mensaje durante el handoff."
            
            # Construir mensaje de historial
            nombre = conversacion.nombre_usuario or "Cliente"
            lines = [f"📜 *HISTORIAL - {nombre}*\n"]
            
            # Formatear mensajes
            from datetime import datetime
            now = datetime.utcnow()
            
            for msg in historial:
                timestamp = msg.get('timestamp')
                sender = msg.get('sender')
                message = msg.get('message', '')
                
                # Calcular tiempo relativo
                if timestamp:
                    delta = now - timestamp
                    segundos = int(delta.total_seconds())
                    
                    if segundos < 60:
                        tiempo = f"{segundos} seg"
                    elif segundos < 3600:
                        minutos = segundos // 60
                        tiempo = f"{minutos} min"
                    else:
                        horas = segundos // 3600
                        tiempo = f"{horas} h"
                    
                    hora_str = timestamp.strftime('%H:%M')
                    tiempo_display = f"🕐 {hora_str} (hace {tiempo})"
                else:
                    tiempo_display = "🕐 --:--"
                
                # Icono según quién habló
                if sender == "client":
                    emisor = "Cliente"
                    icono = "👤"
                elif sender == "agent":
                    emisor = "Agente"
                    icono = "👨🏻‍💼"
                else:
                    emisor = "Sistema"
                    icono = "🤖"
                
                # Truncar mensaje si es muy largo
                if len(message) > 150:
                    message = message[:150] + "..."
                
                lines.append(f"{tiempo_display} - {icono} *{emisor}:*")
                lines.append(f'"{message}"')
                lines.append("")  # Línea en blanco entre mensajes
            
            # Agregar info de tiempo activo
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
            
            if conversacion.handoff_started_at:
                delta = datetime.utcnow() - conversacion.handoff_started_at
                minutos = int(delta.total_seconds() / 60)
                if minutos < 60:
                    tiempo_activo = f"{minutos} min"
                else:
                    horas = minutos // 60
                    mins_restantes = minutos % 60
                    tiempo_activo = f"{horas}h {mins_restantes}min"
                
                lines.append(f"⏱️ Conversación activa desde hace {tiempo_activo}")
            
            if conversacion.last_client_message_at:
                delta = datetime.utcnow() - conversacion.last_client_message_at
                segundos = int(delta.total_seconds())
                if segundos < 60:
                    tiempo_ultimo = f"{segundos} seg"
                elif segundos < 3600:
                    minutos = segundos // 60
                    tiempo_ultimo = f"{minutos} min"
                else:
                    horas = segundos // 3600
                    tiempo_ultimo = f"{horas} h"
                
                lines.append(f"📨 Último mensaje del cliente: hace {tiempo_ultimo}")
            
            logger.info(f"✅ Agente {agent_phone} solicitó historial de {numero_telefono}")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error ejecutando comando /historial: {e}")
            return f"❌ Error obteniendo historial: {str(e)}"

    def execute_optin_command(self, agent_phone: str) -> str:
        """
        Ejecuta el comando /optin: envia el prompt de consentimiento al agente.

        Args:
            agent_phone: Número del agente (para logs)

        Returns:
            str: Mensaje de opt-in a enviar al agente
        """
        try:
            from services.optin_service import optin_service

            prompt_payload = optin_service.start_optin("whatsapp", agent_phone)
            if not prompt_payload:
                return "❌ Opt-in deshabilitado o no disponible."
            prompt, use_buttons = prompt_payload
            if use_buttons:
                buttons = optin_service.get_optin_buttons()
                if meta_whatsapp_service.send_interactive_buttons(agent_phone, prompt, buttons):
                    logger.info("optin_prompt_sent agent_phone=%s", agent_phone)
                    return ""
            logger.info("optin_prompt_sent agent_phone=%s", agent_phone)
            return prompt
        except Exception as e:
            logger.error(f"Error ejecutando comando /optin: {e}")
            return f"❌ Error enviando opt-in: {str(e)}"


# Instancia global del servicio
agent_command_service = AgentCommandService()
