# PLAN

## Phase 1 — Persistence boundaries and model

Definir el contrato exacto del checkpoint y los estados que entran en v1. La persistencia debe cubrir solo sesiones bot-reanudables, mantener documentos chicos y usar Firestore `default` con colección `conversation-checkpoints`. También se debe definir la semántica de `expires_at`, la colección separada de dedupe por `message_id` y la serialización/hidratación de `ConversacionData`.

## Phase 2 — Runtime integration in conversation flow

Integrar hydrate/save/delete en el flujo actual sin reescribir la arquitectura general. `ConversationManager` seguirá usando RAM como cache natural, pero intentará cargar desde Firestore antes de crear una conversación nueva. Los prompts críticos deberán usar `persist-before-send`, y al final del request se guardará la sesión si quedó en un estado reanudable.

## Phase 3 — Cleanup and operational hooks

Agregar un endpoint dedicado de cleanup para checkpoints vencidos, invocado diariamente por Cloud Scheduler. El cleanup debe ser idempotente, pequeño y desacoplado del sweep de handoff existente. También debe borrarse el checkpoint inmediatamente al finalizar una conversación o al detectar expiración por lectura.

## Phase 4 — Robustness, observability and rollout

Incorporar dedupe global por `message_id`, logs de operaciones de checkpoint y cobertura de tests para cold starts simulados, expiración de 24 horas y eliminación al finalizar. El rollout debe empezar por los flujos bot críticos y validar que el comportamiento actual se preserve fuera del nuevo mecanismo de persistencia.

## Dependencies and prerequisites

- Firestore accesible con las credenciales actuales del servicio.
- Nueva colección `conversation-checkpoints` en la base `default`.
- Token y wiring para endpoint HTTP diario vía Cloud Scheduler.
- Cobertura de tests en los flujos afectados (`expensas`, corrección, confirmación, media interactiva).

## Observability

- Logs de `checkpoint_load`, `checkpoint_save`, `checkpoint_delete`, `checkpoint_cleanup_delete`.
- Logs de `checkpoint_expired_on_read`.
- Logs de `message_deduped`.
- Logs diferenciados para fallas de persistencia crítica y no crítica.

## Rollout / rollback

- Rollout en una sola revisión con logs reforzados.
- Verificación manual de un caso `media -> confirmación -> reanudación tras reset de RAM`.
- Rollback simple: desactivar el nuevo wiring de persistencia y volver al comportamiento en memoria.

## Test strategy

- Tests unitarios del servicio de checkpoints.
- Tests de reanudación de conversación bot tras “cold start” simulado.
- Tests de expiración luego de 24 horas.
- Tests de dedupe por `message_id`.
- Tests de borrado al finalizar y cleanup diario.
