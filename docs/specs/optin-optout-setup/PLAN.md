# Plan

## Phase 1: Storage and config
- Crear bucket nuevo de GCS para auditoria (sin borrado automatico).
- Habilitar Firestore/Datastore y crear collection `optins`.
- Definir variables de entorno: `OPTIN_FIRESTORE_COLLECTION`, `OPTIN_GCS_BUCKET`, `OPTIN_COMMAND`, `OPTIN_OUT_KEYWORDS`, `OPTIN_RESUBSCRIBE_KEYWORD`.

## Phase 2: Opt-in service
- Implementar servicio de opt-in con lectura de estado en Firestore.
- Implementar writer de auditoria que guarde JSON en GCS.
- Definir esquema de documento y transiciones de estado (pending/accepted/declined/opted_out).
- Fail-closed: si Firestore falla, bloquear envio de templates.

## Phase 3: Command and message handling
- Agregar comando `/optin` en `agent_command_service` para enviar el prompt al mismo numero.
- Procesar respuestas SI/NO cuando el estado esta pendiente.
- Procesar BAJA/STOP para opt-out y ALTA para re-enviar el opt-in.

## Phase 4: Template gating
- Validar opt-in antes de enviar templates de WhatsApp/Messenger (incluye handoff).
- Bloquear envio y registrar evento si no hay opt-in aceptado.

## Phase 5: Tests and verification
- Agregar test manual/script en `tests/` para flujos de opt-in/opt-out.
- Verificar registros en GCS.
- Verificar estados en Firestore y bloqueo de templates.

## Rollout / rollback
- Habilitar via variables de entorno (feature toggle simple) y monitorear logs.
- En rollback, desactivar el chequeo de opt-in para templates.
