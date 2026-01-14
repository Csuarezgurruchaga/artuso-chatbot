# Acceptance criteria: handoff emergency routing

## Functional acceptance
- When `TipoConsulta=EMERGENCIA` and `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is set, the handoff notification is sent to that emergency number.
- When `TipoConsulta=EMERGENCIA` and `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is missing/empty, the notification is sent to `HANDOFF_WHATSAPP_NUMBER`.
- When `TipoConsulta` is not `EMERGENCIA`, the notification is sent to `HANDOFF_WHATSAPP_NUMBER`.
- Handoff message content and template are unchanged.
- Handoff queue/TTL behavior is unchanged.

## Non-functional acceptance
- No new dependencies added.
- No new data model or schema changes.

## Observability acceptance
- Logs indicate whether a handoff was routed as emergency or standard.

## Rollback acceptance
- Reverting the deploy restores previous handoff routing behavior.
