# CHECKPOINT — chatbot-session-resume

Last updated: 2026-03-18

## Completed
- T0.1 Crear el servicio de checkpoints.
- T1.1 Hidratar conversaciones desde Firestore cuando RAM no tenga estado.
- T1.2 Agregar dedupe global por `message_id`.
- T1.3 Implementar `persist-before-send` en prompts críticos.

## Current / Next
- Next task: T1.4
- Status: READY

## Important constraints
- Firestore `default` + `conversation-checkpoints`.
- Dedupe global por `message_id` en `processed-inbound-message-ids`.
- Solo estados bot-reanudables definidos en el spec.
- `persist-before-send` en prompts críticos.
- Save final en estados reanudables y delete al finalizar.
- Expiración funcional a 24h + cleanup diario por endpoint dedicado.
- Handoff y encuesta quedan fuera de v1.

## Gotchas / Risks discovered
- El repo original está sucio en `dev`; la implementación corre en worktree limpio sobre `impl/chatbot-session-resume`.
- El helper `verify_contract.py` exige `Open Questions` totalmente vacío, no `- None.`.
- `ConversacionData` usa `use_enum_values=True`, así que el servicio debe tolerar enums serializados como `str`.
- El hydrate no puede asumir credenciales válidas en todos los entornos; ante falla de Firestore debe degradar a RAM y loggear.
- El dedupe global degrada abierto si Firestore no responde: se loggea el error y se sigue procesando para no romper inbound legítimo.
- Los puntos cubiertos con `persist-before-send` en esta fase son `media_confirmacion` y `confirmacion_interactiva`; el save final general queda para T1.4.

## Safe resume instructions
- Abrir `TASKS.md` y seguir `## Execution status`.
- Mantenerse en `impl/chatbot-session-resume`.
- T1.4 debe persistir el snapshot final del request cuando la conversación termine en un estado bot-reanudable, sin duplicar writes innecesarios.
