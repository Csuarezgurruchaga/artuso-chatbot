import os
import re
from typing import Dict, Optional, List, Any
from .models import ConversacionData, EstadoConversacion, TipoConsulta
from services.metrics_service import metrics_service
from services.phone_display import format_phone_for_agent
from datetime import datetime, timedelta

POST_FINALIZADO_WINDOW_SECONDS = int(os.getenv("POST_FINALIZADO_WINDOW_SECONDS", "120"))

class ConversationManager:
    def __init__(self):
        self.conversaciones: Dict[str, ConversacionData] = {}
        self.recently_finalized: Dict[str, datetime] = {}

        # Sistema de cola FIFO para handoffs
        self.handoff_queue: List[str] = []  # Lista de números de teléfono en orden FIFO
        self.active_handoff: Optional[str] = None  # Número de teléfono activo actualmente
    
    def get_conversacion(self, numero_telefono: str) -> ConversacionData:
        if numero_telefono not in self.conversaciones:
            self.conversaciones[numero_telefono] = ConversacionData(
                numero_telefono=numero_telefono,
                estado=EstadoConversacion.INICIO
            )
        return self.conversaciones[numero_telefono]
    
    def update_estado(self, numero_telefono: str, nuevo_estado: EstadoConversacion):
        conversacion = self.get_conversacion(numero_telefono)
        # Guardar el estado anterior antes de cambiarlo
        conversacion.estado_anterior = conversacion.estado
        conversacion.estado = nuevo_estado
    
    def set_tipo_consulta(self, numero_telefono: str, tipo: TipoConsulta):
        conversacion = self.get_conversacion(numero_telefono)
        conversacion.tipo_consulta = tipo
    
    def set_datos_temporales(self, numero_telefono: str, key: str, value: str):
        conversacion = self.get_conversacion(numero_telefono)
        conversacion.datos_temporales[key] = value
    
    def get_datos_temporales(self, numero_telefono: str, key: str) -> Optional[str]:
        conversacion = self.get_conversacion(numero_telefono)
        return conversacion.datos_temporales.get(key)
    
    def validar_y_guardar_datos(self, numero_telefono: str) -> tuple[bool, Optional[str]]:
        conversacion = self.get_conversacion(numero_telefono)
        datos_temp = conversacion.datos_temporales
        error_msgs = []

        if conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            fecha_pago = (datos_temp.get('fecha_pago') or '').strip()
            monto = (datos_temp.get('monto') or '').strip()
            direccion = (datos_temp.get('direccion') or '').strip()
            piso_depto = (datos_temp.get('piso_depto') or '').strip()

            if not re.match(r'^\d{2}/\d{2}/\d{4}$', fecha_pago):
                error_msgs.append("📅 Fecha inválida. Usá el formato dd/mm/yyyy (ej: 12/09/2025).")
            if not re.match(r'^\d+(?:[.,]\d+)?$', monto):
                error_msgs.append("💰 Monto inválido. Escribí solo números (ej: 45800).")
            if len(direccion) < 5:
                error_msgs.append("🏠 Dirección inválida. Debe tener al menos 5 caracteres.")
            if len(piso_depto) < 1:
                error_msgs.append("🚪 Piso/departamento inválido. Indica al menos un valor.")

        elif conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            tipo_servicio = (datos_temp.get('tipo_servicio') or '').strip()
            direccion = (datos_temp.get('direccion_servicio') or '').strip()
            detalle = (datos_temp.get('detalle_servicio') or '').strip()

            if not tipo_servicio:
                error_msgs.append("🔧 Falta seleccionar el tipo de servicio.")
            if len(direccion) < 5:
                error_msgs.append("📍 Dirección inválida. Debe tener al menos 5 caracteres.")
            if len(detalle) < 5:
                error_msgs.append("📝 Contanos un poco más sobre el problema (mínimo 5 caracteres).")

        if error_msgs:
            return False, "\n".join(error_msgs)

        return True, None
    
    def clear_datos_temporales(self, numero_telefono: str):
        conversacion = self.get_conversacion(numero_telefono)
        conversacion.datos_temporales.clear()
    
    def set_nombre_usuario(self, numero_telefono: str, nombre: str):
        conversacion = self.get_conversacion(numero_telefono)
        conversacion.nombre_usuario = nombre
    
    def finalizar_conversacion(self, numero_telefono: str):
        self.recently_finalized[numero_telefono] = datetime.utcnow()
        if numero_telefono in self.conversaciones:
            del self.conversaciones[numero_telefono]
        try:
            metrics_service.on_conversation_finished()
        except Exception:
            pass
    
    def reset_conversacion(self, numero_telefono: str):
        if numero_telefono in self.conversaciones:
            del self.conversaciones[numero_telefono]
        self.recently_finalized.pop(numero_telefono, None)
    
    # Métodos para manejo secuencial de campos
    def get_campo_siguiente(self, numero_telefono: str) -> str:
        """Retorna el próximo campo que necesita ser recolectado"""
        conversacion = self.get_conversacion(numero_telefono)
        datos_temp = conversacion.datos_temporales

        if conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            campos_orden = ['fecha_pago', 'monto', 'direccion', 'piso_depto', 'comprobante', 'comentario']
        elif conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            campos_orden = ['tipo_servicio', 'direccion_servicio', 'detalle_servicio']
        else:
            return None

        for campo in campos_orden:
            valor_campo = datos_temp.get(campo)
            if valor_campo is None:
                return campo

        return None
    
    def marcar_campo_completado(self, numero_telefono: str, campo: str, valor: str):
        """Marca un campo como completado y lo guarda"""
        self.set_datos_temporales(numero_telefono, campo, valor)
    
    def es_ultimo_campo(self, numero_telefono: str, campo_actual: str) -> bool:
        """Verifica si el campo actual es el último que necesitamos"""
        conversacion = self.get_conversacion(numero_telefono)

        if conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            return campo_actual == 'comentario'
        if conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            return campo_actual == 'detalle_servicio'

        return False
    
    def get_progreso_campos(self, numero_telefono: str) -> tuple[int, int]:
        """Retorna (campos_completados, total_campos) para mostrar progreso"""
        conversacion = self.get_conversacion(numero_telefono)
        datos_temp = conversacion.datos_temporales

        if conversacion.tipo_consulta == TipoConsulta.PAGO_EXPENSAS:
            campos_orden = ['fecha_pago', 'monto', 'direccion', 'piso_depto', 'comprobante', 'comentario']
        elif conversacion.tipo_consulta == TipoConsulta.SOLICITAR_SERVICIO:
            campos_orden = ['tipo_servicio', 'direccion_servicio', 'detalle_servicio']
        else:
            campos_orden = []

        completados = sum(1 for campo in campos_orden if datos_temp.get(campo) is not None)

        return completados, len(campos_orden)

    # ========== MÉTODOS PARA GESTIÓN DE COLA DE HANDOFFS ==========

    def add_to_handoff_queue(self, numero_telefono: str) -> int:
        """
        Agrega una conversación a la cola de handoffs.
        Si no hay conversación activa, la activa automáticamente.

        Args:
            numero_telefono: Número de teléfono del cliente

        Returns:
            int: Posición en la cola (1-indexed)
        """
        # Solo agregar si no está ya en la cola
        if numero_telefono not in self.handoff_queue:
            self.handoff_queue.append(numero_telefono)

        # Si no hay conversación activa, activar esta
        if self.active_handoff is None:
            self.activate_next_handoff()

        # Retornar posición (1-indexed)
        try:
            return self.handoff_queue.index(numero_telefono) + 1
        except ValueError:
            return 1

    def activate_next_handoff(self) -> Optional[str]:
        """
        Activa la siguiente conversación en la cola (la primera).

        Returns:
            Optional[str]: Número de teléfono activado o None si la cola está vacía
        """
        if self.handoff_queue:
            self.active_handoff = self.handoff_queue[0]
            return self.active_handoff
        else:
            self.active_handoff = None
            return None

    def get_active_handoff(self) -> Optional[str]:
        """
        Obtiene el número de teléfono de la conversación activa.

        Returns:
            Optional[str]: Número activo o None
        """
        return self.active_handoff

    def get_queue_position(self, numero_telefono: str) -> Optional[int]:
        """
        Obtiene la posición de un número en la cola.

        Args:
            numero_telefono: Número a buscar

        Returns:
            Optional[int]: Posición (1-indexed) o None si no está en cola
        """
        try:
            return self.handoff_queue.index(numero_telefono) + 1
        except ValueError:
            return None

    def get_queue_size(self) -> int:
        """
        Obtiene la cantidad de conversaciones en la cola.

        Returns:
            int: Tamaño de la cola
        """
        return len(self.handoff_queue)

    def close_active_handoff(self) -> Optional[str]:
        """
        Cierra la conversación activa, la remueve de la cola,
        y activa automáticamente la siguiente.

        Returns:
            Optional[str]: Número del siguiente activado o None
        """
        if self.active_handoff and self.active_handoff in self.handoff_queue:
            # Remover de la cola
            self.handoff_queue.remove(self.active_handoff)

            # Finalizar conversación
            self.finalizar_conversacion(self.active_handoff)

            # Reset activo
            self.active_handoff = None

            # Activar siguiente
            return self.activate_next_handoff()

        return None

    def move_to_next_in_queue(self) -> Optional[str]:
        """
        Mueve la conversación activa al final de la cola
        y activa la siguiente.

        Returns:
            Optional[str]: Número del siguiente activado o None
        """
        if self.active_handoff and self.active_handoff in self.handoff_queue:
            # Mover al final
            self.handoff_queue.remove(self.active_handoff)
            self.handoff_queue.append(self.active_handoff)

            # Activar el nuevo primero
            return self.activate_next_handoff()

        return None

    def get_handoff_by_index(self, index: int) -> Optional[str]:
        """
        Obtiene el número de teléfono por posición en la cola.

        Args:
            index: Posición en la cola (1-indexed)

        Returns:
            Optional[str]: Número de teléfono o None si índice inválido
        """
        try:
            return self.handoff_queue[index - 1]
        except IndexError:
            return None

    def remove_from_handoff_queue(self, numero_telefono: str) -> bool:
        """
        Remueve un número de la cola de handoffs.
        Si era el activo, activa el siguiente automáticamente.

        Args:
            numero_telefono: Número a remover

        Returns:
            bool: True si fue removido, False si no estaba en cola
        """
        if numero_telefono not in self.handoff_queue:
            return False

        was_active = (self.active_handoff == numero_telefono)

        # Remover de la cola
        self.handoff_queue.remove(numero_telefono)

        # Si era el activo, activar siguiente
        if was_active:
            self.active_handoff = None
            self.activate_next_handoff()

        return True

    def format_queue_status(self) -> str:
        """
        Genera un mensaje formateado con el estado completo de la cola.

        Returns:
            str: Mensaje formateado
        """
        survey_states = {
            EstadoConversacion.ESPERANDO_RESPUESTA_ENCUESTA,
            EstadoConversacion.ENCUESTA_SATISFACCION,
        }
        visible_queue = []
        for numero in self.handoff_queue:
            conversacion = self.conversaciones.get(numero)
            if not conversacion:
                continue
            if conversacion.estado in survey_states:
                continue
            visible_queue.append(numero)

        if not visible_queue:
            return "📋 *COLA DE HANDOFFS*\n\n✅ No hay conversaciones activas.\n\nTodas las consultas han sido atendidas."

        lines = ["📋 *COLA DE HANDOFFS*\n"]

        for i, numero in enumerate(visible_queue):
            conversacion = self.conversaciones.get(numero)
            if not conversacion:
                continue
            is_active = (numero == self.active_handoff)

            # Calcular tiempo desde el inicio del handoff
            tiempo_desde_inicio = ""
            if conversacion.handoff_started_at:
                delta = datetime.utcnow() - conversacion.handoff_started_at
                minutos = int(delta.total_seconds() / 60)
                if minutos < 60:
                    tiempo_desde_inicio = f"{minutos} min"
                else:
                    horas = minutos // 60
                    mins = minutos % 60
                    tiempo_desde_inicio = f"{horas}h {mins}min"

            # Calcular tiempo desde último mensaje
            tiempo_ultimo_mensaje = ""
            if conversacion.last_client_message_at:
                delta = datetime.utcnow() - conversacion.last_client_message_at
                segundos = int(delta.total_seconds())
                if segundos < 60:
                    tiempo_ultimo_mensaje = f"{segundos} seg"
                else:
                    minutos = segundos // 60
                    tiempo_ultimo_mensaje = f"{minutos} min"

            nombre = conversacion.nombre_usuario or "Sin nombre"
            numero_display = format_phone_for_agent(numero)

            if is_active:
                lines.append(f"🟢 *[ACTIVO]* {nombre}")
                lines.append(f"   📞 {numero_display}")
                if tiempo_desde_inicio:
                    lines.append(f"   ⏱️ Iniciado hace {tiempo_desde_inicio}")
                if tiempo_ultimo_mensaje:
                    lines.append(f"   💬 Último mensaje hace {tiempo_ultimo_mensaje}")
            else:
                lines.append(f"\n⏳ *[#{i+1}]* {nombre}")
                lines.append(f"   📞 {numero_display}")
                if tiempo_desde_inicio:
                    lines.append(f"   ⏱️ Esperando hace {tiempo_desde_inicio}")

                # Mostrar fragmento del mensaje inicial
                if conversacion.mensaje_handoff_contexto:
                    fragmento = conversacion.mensaje_handoff_contexto[:40]
                    if len(conversacion.mensaje_handoff_contexto) > 40:
                        fragmento += "..."
                    lines.append(f"   💭 \"{fragmento}\"")

            lines.append("")  # Línea en blanco

        lines.append("─" * 30)
        lines.append(f"📊 Total: {len(visible_queue)} conversación(es)")

        # Calcular tiempo promedio de espera
        if len(visible_queue) > 1:
            tiempos_espera = []
            for numero in visible_queue[1:]:  # Excluir el activo
                conv = self.conversaciones.get(numero)
                if not conv:
                    continue
                if conv.handoff_started_at:
                    delta = datetime.utcnow() - conv.handoff_started_at
                    tiempos_espera.append(delta.total_seconds() / 60)

            if tiempos_espera:
                promedio = int(sum(tiempos_espera) / len(tiempos_espera))
                lines.append(f"⏰ Tiempo promedio espera: {promedio} min")

        return "\n".join(lines)
    
    def add_message_to_history(self, numero_telefono: str, sender: str, message: str, max_messages: int = 10):
        """
        Agrega un mensaje al historial de la conversación.
        
        Args:
            numero_telefono: Número de teléfono del cliente
            sender: "client" o "agent"
            message: Contenido del mensaje
            max_messages: Máximo de mensajes a mantener en historial (default: 10)
        """
        conversacion = self.get_conversacion(numero_telefono)
        
        # Solo guardar historial si está en handoff
        if not (conversacion.atendido_por_humano or conversacion.estado == EstadoConversacion.ATENDIDO_POR_HUMANO):
            return
        
        # Agregar mensaje al historial
        mensaje_entry = {
            "timestamp": datetime.utcnow(),
            "sender": sender,  # "client" o "agent"
            "message": message[:500]  # Limitar longitud para no consumir mucha memoria
        }
        
        conversacion.message_history.append(mensaje_entry)
        
        # Mantener solo los últimos N mensajes
        if len(conversacion.message_history) > max_messages:
            conversacion.message_history = conversacion.message_history[-max_messages:]
    
    def mark_recently_finalized(self, numero_telefono: str):
        self.recently_finalized[numero_telefono] = datetime.utcnow()
    
    def was_finalized_recently(self, numero_telefono: str) -> bool:
        timestamp = self.recently_finalized.get(numero_telefono)
        if not timestamp:
            return False
        if datetime.utcnow() - timestamp <= timedelta(seconds=POST_FINALIZADO_WINDOW_SECONDS):
            return True
        self.recently_finalized.pop(numero_telefono, None)
        return False
    
    def clear_recently_finalized(self, numero_telefono: str):
        self.recently_finalized.pop(numero_telefono, None)
    
    def get_message_history(self, numero_telefono: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de mensajes de una conversación.
        
        Args:
            numero_telefono: Número de teléfono del cliente
            limit: Cantidad máxima de mensajes a retornar (default: 5)
            
        Returns:
            List: Lista de mensajes [{timestamp, sender, message}]
        """
        conversacion = self.get_conversacion(numero_telefono)
        
        # Retornar los últimos N mensajes
        return conversacion.message_history[-limit:] if conversacion.message_history else []

conversation_manager = ConversationManager()
