# SPEC

## Summary

Persistir checkpoints de sesiones bot-reanudables en Firestore para que el chatbot pueda retomar conversaciones interrumpidas por cold starts o scale-to-zero en Cloud Run (`min_instances=0`), sin agregar costo fijo ni rediseñar handoff/encuesta en la primera versión.

## Goals / Non-goals

### Goals

- Reanudar conversaciones del bot desde donde quedaron dentro de una ventana de 24 horas.
- Evitar pérdida de estado en flujos de expensas, reclamos y corrección/confirmación por reinicio de instancia.
- Mantener lookup por `document id` para que el costo por request no dependa de la cantidad total de checkpoints almacenados.
- Limpiar checkpoints vencidos con un cleanup diario.
- Mantener la solución simple y económica: Firestore + checkpoints chicos + sin costo fijo adicional.

### Non-goals

- No incluir handoff humano, cola FIFO ni encuesta en la v1.
- No persistir historial completo de mensajes.
- No cambiar la UX de reinicio luego de 24 horas: si vence, reinicia silenciosamente.
- No resolver en esta iniciativa optimizaciones de cold start ajenas a la pérdida de estado.

## Constraints

- El servicio corre en Cloud Run con `min_instances=0`.
- La solución debe seguir siendo serverless y sin costo fijo relevante.
- El repo ya tiene dependencia y patrón simple de Firestore (`google-cloud-firestore` y `services/optin_service.py`).
- El diseño debe priorizar simplicidad operacional y bajo riesgo de regresión.
- El costo por request debe mantenerse predecible: sin scans globales para resolver mensajes entrantes.

## Key Flows

1. Usuario está en un flujo bot-reanudable, la instancia se apaga, vuelve a escribir dentro de 24 horas y el chatbot retoma desde el checkpoint persistido.
2. Usuario responde a un botón contextual, por ejemplo confirmación de comprobante, después de un cold start y el chatbot reanuda correctamente usando el checkpoint.
3. Usuario vuelve luego de 24 horas; el checkpoint ya no es válido y la conversación reinicia desde cero sin reutilizar contexto anterior.
4. Cleanup diario elimina checkpoints vencidos que no fueron tocados nuevamente.

## Data / Interfaces

- Nuevo almacenamiento de checkpoints por conversación en Firestore, en la base `default`.
- Colección dedicada: `conversation-checkpoints`.
- Clave de documento: `<canal>:<telefono>`.
- Snapshot persistido mínimo:
  - `estado`
  - `estado_anterior`
  - `tipo_consulta`
  - `nombre_usuario`
  - `datos_temporales`
  - `datos_contacto` si aplica
  - `updated_at`
  - `last_user_message_at`
  - `expires_at`
  - `schema_version`
- Marcador liviano separado para dedupe por inbound:
  - colección dedicada `processed-inbound-message-ids`
  - `doc_id = message_id`
  - `processed_at`
  - `expires_at`
- La deduplicación no debe depender de que exista un checkpoint de sesión.
- Los lookups normales deben ser por `document id`, no por queries globales.
- El cleanup diario correrá por endpoint dedicado invocado por Cloud Scheduler.
- El cleanup puede usar query por `expires_at` para borrar checkpoints vencidos que no hayan sido eliminados por finalización o por lectura.

## Edge cases & Failure modes

- Si llega un mensaje duplicado de Meta, no debe duplicar side effects ni avanzar dos veces el flujo.
- Si el proceso crea contexto y envía un prompt sin persistir antes, la sesión puede volver a perderse.
- Si se persisten estados innecesarios (handoff/encuesta) en v1, aumenta el alcance y riesgo de regresión.
- Si el checkpoint vence luego de 24 horas, un mensaje nuevo no debe reanudar ni arrastrar datos viejos.
- Si Firestore falla temporalmente durante un `persist-before-send`, no debe enviarse el prompt crítico que depende de ese contexto no persistido.
- Si Firestore falla temporalmente en un guardado no crítico al final del request, el flujo puede seguir degradado en RAM pero debe quedar loggeado.

## Observability

- Loggear hydrate, save, delete y cleanup de checkpoints con teléfono y estado, sin payloads sensibles.
- Loggear dedupe por `message_id`.
- Loggear reinicio silencioso por checkpoint vencido.
- Loggear fallas de persistencia diferenciando `critical_save_before_send_failed` vs `final_save_failed`.
- Contadores recomendados:
  - `session_checkpoint_saved`
  - `session_checkpoint_loaded`
  - `session_checkpoint_deleted`
  - `session_checkpoint_expired`
  - `session_checkpoint_deduped`

## Security / Privacy

- Persistir solo datos necesarios para reanudar el flujo.
- No persistir historial completo ni payloads crudos del webhook.
- Mantener documentos chicos y limitar logs a identificadores y estados.
- Usar la misma autenticación server-to-GCP ya utilizada por servicios actuales.

## Open Questions

## Decision Log

- **Decision:** El slug será `chatbot-session-resume`.
  - **Rationale:**
    - Describe el objetivo funcional sin acoplarlo de más a Cloud Run.
    - Deja espacio para abarcar botones, comprobantes y otros pasos del bot.

- **Decision:** La v1 cubre solo flujos bot de expensas/reclamos/correcciones/confirmación.
  - **Rationale:**
    - Reduce alcance y riesgo.
    - Evita mezclar handoff humano, cola y encuesta en la primera implementación.

- **Decision:** Luego de 24 horas, la conversación no se reanuda y reinicia silenciosamente.
  - **Rationale:**
    - Evita arrastrar contexto viejo.
    - Mantiene una regla simple y determinista.

- **Decision:** Cada checkpoint tendrá `expires_at` y además habrá cleanup diario.
  - **Rationale:**
    - `expires_at` define la validez funcional.
    - El cleanup diario limpia basura residual sin afectar el lookup normal por request.

- **Decision:** Usar la base Firestore `default` con colección dedicada `conversation-checkpoints`.
  - **Rationale:**
    - Reutiliza la integración ya presente en el repo.
    - Evita complejidad operativa adicional.

- **Decision:** Persistir solo estados bot-reanudables: `RECOLECTANDO_DATOS`, `RECOLECTANDO_DATOS_INDIVIDUALES`, `RECOLECTANDO_SECUENCIAL`, `VALIDANDO_UBICACION`, `VALIDANDO_DATOS`, `CONFIRMANDO`, `CONFIRMANDO_MEDIA`, `CORRIGIENDO`, `CORRIGIENDO_CAMPO`, `ELIMINANDO_DIRECCION_GUARDADA`.
  - **Rationale:**
    - Mantiene continuidad donde el bot realmente necesita contexto.
    - `CONFIRMANDO_MEDIA` cubre el prompt `Este archivo es un pago de expensas?`, que también requiere continuidad antes de definir `tipo_consulta`.
    - Excluye handoff/encuesta para mantener la v1 acotada y segura.

- **Decision:** Aplicar deduplicación por `message_id` a todo inbound que lo incluya usando un marcador liviano separado del checkpoint de sesión.
  - **Rationale:**
    - Evita side effects duplicados por reentregas de Meta.
    - Sigue funcionando aunque no exista checkpoint activo o la conversación ya haya finalizado.

- **Decision:** Usar `persist-before-send` en prompts críticos y save final al terminar el request cuando la conversación quede en un estado reanudable.
  - **Rationale:**
    - Protege los puntos vulnerables a pérdida de contexto.
    - Evita escribir en Firestore en cada micro-mutación.

- **Decision:** Implementar cleanup con endpoint dedicado invocado por Cloud Scheduler.
  - **Rationale:**
    - Separa responsabilidades respecto al sweep de handoff.
    - Mantiene simplicidad operacional y bajo costo.

## Changelog

- 2026-03-18 — Creación inicial del spec
  - reason: definir persistencia de checkpoints para reanudar sesiones del bot con `min_instances=0`
  - impact: deberán crearse `PLAN.md`, `TASKS.md` y `ACCEPTANCE.md` una vez que `Open Questions` quede vacío

- 2026-03-18 — Cierre de decisiones críticas de diseño
  - reason: se eligieron base Firestore, colección, estados persistibles, dedupe global, estrategia robusta de guardado y cleanup con Cloud Scheduler
  - impact: el spec queda listo para generar `PLAN.md`, `TASKS.md` y `ACCEPTANCE.md`

- 2026-03-18 — Ajuste de estado reanudable para confirmación de media
  - reason: el flujo `media -> confirmación` exigido por `A2` no puede reanudarse si queda modelado como `INICIO`
  - impact: se agrega `CONFIRMANDO_MEDIA` como estado bot-reanudable explícito para el prompt de clasificación de adjuntos

## Glossary

- **Checkpoint:** snapshot mínimo de una conversación activa necesario para reanudar el flujo.
- **Bot-reanudable:** estado del bot que requiere continuidad y por eso debe sobrevivir a cold starts.
- **Cold start:** arranque de una nueva instancia de Cloud Run después de scale-to-zero o falta de capacidad caliente.

> The SPEC is the source of truth. If implementation deviates, update the SPEC + TASKS + ACCEPTANCE and record it in the Changelog.
