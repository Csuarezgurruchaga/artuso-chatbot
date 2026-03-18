# ACCEPTANCE

## A1 — Reanudación de sesión bot dentro de 24 horas
- Dado un flujo bot-reanudable de expensas o reclamos en curso, cuando la RAM del proceso se pierde y el usuario vuelve a escribir dentro de 24 horas, entonces el chatbot retoma exactamente desde el punto en que quedó usando el checkpoint persistido.

## A2 — Confirmación de comprobante robusta a cold start
- Dado un media recibido que dispara la pregunta `Este archivo es un pago de expensas?` y deja la conversación en `CONFIRMANDO_MEDIA`, cuando la instancia original ya no existe y el usuario responde `Sí`, entonces el sistema encuentra el contexto en Firestore y continúa el flujo correcto sin perder el comprobante.

## A3 — Expiración funcional luego de 24 horas
- Dado un checkpoint con más de 24 horas desde `expires_at`, cuando el usuario vuelve a escribir, entonces la conversación vieja no se reanuda, el checkpoint se invalida y el chatbot reinicia desde cero sin reutilizar ese contexto.

## A4 — Borrado al finalizar
- Dado un flujo completado exitosamente o reiniciado explícitamente, entonces el checkpoint asociado se elimina y no puede reutilizarse en mensajes posteriores.

## A5 — Deduplicación por `message_id`
- Dado un inbound duplicado con el mismo `message_id`, entonces el sistema no reprocesa side effects ni duplica cambios de estado, escrituras o registros finales, incluso si no hay checkpoint activo o la conversación ya fue finalizada.

## A6 — Lookup económico y acotado
- La resolución normal de una sesión se hace por `document id` directo (`<canal>:<telefono>`) y no requiere scans de toda la colección para procesar mensajes entrantes.

## A7 — Cleanup diario desacoplado
- Existe un endpoint dedicado de cleanup, invocable por Cloud Scheduler, que borra checkpoints vencidos sin mezclar responsabilidades con el sweep de handoff.

## A8 — Observabilidad suficiente
- Los logs permiten distinguir al menos: load, save, delete, expiration on read, cleanup delete, dedupe y fallas de persistencia crítica/no crítica, sin exponer payloads sensibles ni contenido completo del usuario.

## A9 — Preservación del comportamiento fuera de alcance
- Los flujos fuera de la v1 (handoff humano, cola y encuesta) mantienen el comportamiento actual y no pasan a depender del nuevo mecanismo de checkpoints.
