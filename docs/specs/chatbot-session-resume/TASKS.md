# TASKS

## Phase 0 — Setup / scaffolding
- T0.1 Crear el servicio de checkpoints
  - Goal: Introducir un servicio mínimo de Firestore para guardar/cargar/borrar checkpoints sin tocar aún el flujo del chatbot.
  - Inputs: `requirements.txt`, `services/optin_service.py`, `chatbot/models.py`, `docs/specs/chatbot-session-resume/SPEC.md`
  - Outputs: nuevo archivo `services/conversation_session_service.py` con cliente lazy, serialización básica y helpers `load/save/delete/is_expired`.
  - Steps:
    - Definir nombre de colección y shape del documento.
    - Reutilizar patrón simple de cliente Firestore ya usado en el repo.
    - Implementar serialización/hidratación explícita de snapshot.
  - Done condition: existe un servicio reutilizable que permite operar checkpoints por `doc_id` sin scans globales.
  - Depends on: []
  - Risks: serialización inconsistente de enums/datetimes; acoplar demasiado el servicio al flujo.
  - Test/Verification: `python3 -m pytest -q tests/test_session_checkpoint_service.py` con resultado verde, o crear primero ese test si aún no existe.

## Phase 1 — Core logic
- T1.1 Hidratar conversaciones desde Firestore cuando RAM no tenga estado
  - Goal: Hacer que `ConversationManager` pueda reanudar una sesión existente antes de crear una nueva conversación vacía.
  - Inputs: `chatbot/states.py`, `chatbot/models.py`, `services/conversation_session_service.py`
  - Outputs: `ConversationManager` integrado con carga por checkpoint.
  - Steps:
    - Agregar intento de `load()` antes de crear una conversación nueva.
    - Rehidratar solo estados bot-reanudables.
    - Ignorar y borrar checkpoints vencidos al leerlos.
  - Done condition: una conversación bot activa puede reconstruirse desde Firestore tras limpiar RAM.
  - Depends on: [T0.1]
  - Risks: crear conversaciones “fantasma” cuando no corresponde; hidratar estados fuera de alcance v1.
  - Test/Verification: `python3 -m pytest -q tests/test_session_resume_manager.py`

- T1.2 Agregar dedupe global por `message_id`
  - Goal: Evitar reprocesamiento de inbound duplicados.
  - Inputs: `main.py`, extracción actual de `message_id`, `services/conversation_session_service.py`
  - Outputs: guardrail de dedupe aplicado a todo inbound con `message_id`.
  - Steps:
    - Crear un marcador liviano separado para `message_id` procesados.
    - Cortar el procesamiento si el inbound ya fue visto.
    - Loggear el caso deduplicado.
  - Done condition: el mismo inbound no produce doble side effect incluso si no existe checkpoint activo o la conversación ya terminó.
  - Depends on: [T0.1]
  - Risks: falsos positivos si el id no es estable; costo extra por write de marcador.
  - Test/Verification: `python3 -m pytest -q tests/test_session_dedupe.py`

- T1.3 Implementar `persist-before-send` en prompts críticos
  - Goal: Eliminar la ventana de pérdida de contexto antes de mensajes que esperan respuesta futura.
  - Inputs: `main.py`, `chatbot/rules.py`, `services/conversation_session_service.py`
  - Outputs: guardado previo al envío en confirmación de media y otros prompts críticos definidos por el spec.
  - Steps:
    - Identificar ramas críticas de prompt.
    - Guardar checkpoint antes del `send`.
    - En fallas críticas, no enviar el prompt y loggear el error.
  - Done condition: los prompts críticos no se envían sin checkpoint persistido.
  - Depends on: [T0.1, T1.1]
  - Risks: omitir una rama crítica; degradar UX si el save falla y no se maneja claro.
  - Test/Verification: `python3 -m pytest -q tests/test_media_confirm_checkpoint.py`

- T1.4 Guardar al final del request en estados reanudables
  - Goal: Persistir el snapshot final del request cuando la conversación queda en un estado bot-reanudable.
  - Inputs: `main.py`, `chatbot/states.py`, `services/conversation_session_service.py`
  - Outputs: save final integrado en el webhook principal.
  - Steps:
    - Definir puntos únicos de save final.
    - Filtrar por estados persistibles.
    - Evitar escrituras redundantes cuando la conversación no requiere checkpoint.
  - Done condition: el request deja persistido el estado reanudable resultante sin escribir en cada setter.
  - Depends on: [T0.1, T1.1]
  - Risks: doble escritura innecesaria; perder un branch que retorna temprano.
  - Test/Verification: `python3 -m pytest -q tests/test_session_resume_manager.py tests/test_media_confirm_checkpoint.py`

## Phase 2 — Integration
- T2.1 Borrar checkpoints al finalizar o reiniciar conversación
  - Goal: Evitar basura y asegurar que una conversación finalizada no se reanude.
  - Inputs: `chatbot/states.py`, `main.py`, `services/conversation_session_service.py`
  - Outputs: delete explícito en finalización exitosa y reinicio.
  - Steps:
    - Integrar delete en `finalizar_conversacion`.
    - Integrar delete en reinicios explícitos y expiración por lectura.
    - Loggear borrados.
  - Done condition: una sesión finalizada o reiniciada no deja checkpoint activo.
  - Depends on: [T0.1, T1.1]
  - Risks: borrar demasiado temprano; dejar checkpoints huérfanos en errores.
  - Test/Verification: `python3 -m pytest -q tests/test_session_delete_on_finalize.py`

- T2.2 Reanudar media, corrección y confirmación final end-to-end
  - Goal: Validar que los principales flujos bot sobrevivan a pérdida de RAM.
  - Inputs: `main.py`, `chatbot/rules.py`, `chatbot/states.py`, tests de flujo existentes
  - Outputs: cobertura de escenarios de expensas/reclamos reanudables.
  - Steps:
    - Simular `media -> confirmación -> cold start -> botón`.
    - Simular corrección de campo tras cold start.
    - Simular confirmación final tras cold start.
  - Done condition: los flujos críticos se retoman desde el punto exacto esperado.
  - Depends on: [T1.1, T1.2, T1.3, T1.4, T2.1]
  - Risks: cubrir solo el caso de comprobante y dejar otros estados frágiles.
  - Test/Verification: `python3 -m pytest -q tests/test_media_confirm_checkpoint.py tests/test_session_resume_manager.py`

## Phase 3 — Observability / hardening
- T3.1 Implementar expiración por lectura a 24 horas
  - Goal: Invalidar checkpoints viejos y reiniciar silenciosamente sin arrastrar contexto anterior.
  - Inputs: `services/conversation_session_service.py`, `chatbot/states.py`, `main.py`
  - Outputs: lógica de `expires_at` aplicada al cargar checkpoints.
  - Steps:
    - Calcular `expires_at` al guardar.
    - Comparar al cargar.
    - Borrar checkpoint vencido y continuar con conversación nueva.
  - Done condition: sesiones de más de 24 horas no se reanudan.
  - Depends on: [T0.1, T1.1]
  - Risks: timezone incorrecta; reanudar sesiones viejas por comparación defectuosa.
  - Test/Verification: `python3 -m pytest -q tests/test_session_expiration.py`

- T3.2 Agregar métricas/logs operativos de checkpoints
  - Goal: Tener visibilidad suficiente para rollout y soporte sin exponer payloads sensibles.
  - Inputs: `main.py`, `services/conversation_session_service.py`, servicios de logging existentes
  - Outputs: logs y, si aplica, hooks mínimos a métricas.
  - Steps:
    - Loggear load/save/delete/expire/dedupe.
    - Distinguir fallas críticas y no críticas.
    - Verificar formato consistente para troubleshooting en Cloud Logging.
  - Done condition: los eventos principales del ciclo de vida del checkpoint quedan trazables en logs.
  - Depends on: [T1.2, T1.3, T1.4, T2.1, T3.1]
  - Risks: exceso de logs; logs con datos sensibles.
  - Test/Verification: revisión manual de logs locales/tests y, si aplica, `python3 -m pytest -q tests/test_meta_webhook.py`

## Phase 4 — Release / rollout
- T4.1 Crear endpoint dedicado de cleanup y wiring con Cloud Scheduler
  - Goal: Eliminar checkpoints vencidos no tocados sin mezclar responsabilidades con handoff.
  - Inputs: `main.py`, `services/conversation_session_service.py`, `docs/specs/chatbot-session-resume/SPEC.md`
  - Outputs: endpoint HTTP dedicado y documentación de invocación diaria.
  - Steps:
    - Crear endpoint protegido por token.
    - Implementar query de vencidos por `expires_at`.
    - Borrar en lotes chicos e idempotentes.
    - Documentar trigger diario con Cloud Scheduler.
  - Done condition: existe cleanup diario desacoplado y seguro.
  - Depends on: [T0.1, T3.1]
  - Risks: scans costosos; borrado de documentos no vencidos.
  - Test/Verification: `python3 -m pytest -q tests/test_session_cleanup.py` y verificación manual del endpoint con token válido.

- T4.2 Verificación final y plan de rollout
  - Goal: Confirmar que la funcionalidad actual se preserva y que la persistencia cubre el incidente original.
  - Inputs: todos los cambios anteriores, `ACCEPTANCE.md`
  - Outputs: evidencia de verificación, pasos de despliegue y rollback.
  - Steps:
    - Ejecutar suite focalizada.
    - Hacer walkthrough manual de sesión reanudada.
    - Preparar pasos de rollback lógico.
  - Done condition: hay evidencia suficiente para desplegar con bajo riesgo.
  - Depends on: [T2.2, T3.2, T4.1]
  - Risks: falsa sensación de cobertura si falta validación manual del caso original.
  - Test/Verification: `python3 -m pytest -q tests/test_media_confirm_checkpoint.py tests/test_session_resume_manager.py tests/test_session_expiration.py tests/test_session_cleanup.py`

## Chunking guidance

- Suggested implementation chunk size: 1–2 tasks per chunk
- Review cadence: after each chunk, verify acceptance criteria impacted by those tasks
- Stop points:
  - after Phase 0: safe to stop here
  - after Phase 1: safe to stop here
  - after Phase 2: safe to stop here
  - after Phase 3: safe to stop here
  - after Phase 4: safe to stop here

## Execution status
- Status: IN_PROGRESS
- Current task: T1.3
- Completed tasks: T0.1, T1.1, T1.2
- Last updated: 2026-03-18
