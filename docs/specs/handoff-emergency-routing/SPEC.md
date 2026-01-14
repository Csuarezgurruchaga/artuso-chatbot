# Handoff emergency routing

## Summary
Route emergency handoffs to a dedicated WhatsApp number while keeping standard handoffs on a renamed standard number env var. Use `TipoConsulta=EMERGENCIA` to trigger emergency routing, keep message content unchanged, and fall back to the standard number if the emergency number is missing.

## Context
Today all handoff notifications use a single WhatsApp number via `AGENT_WHATSAPP_NUMBER`. We need to differentiate emergency handoffs from standard "hablar con un humano" handoffs and also rename the standard number env var to be more indicative.

## Goals
- Route emergency handoffs to a dedicated WhatsApp number.
- Keep all non-emergency handoffs on a standard WhatsApp number.
- Rename the standard handoff env var to a more indicative name.
- Preserve existing handoff messaging, queue, and TTL behavior.

## Non-goals
- Changing handoff copy, templates, or languages.
- Adding new notification channels (email/Slack).
- Changing queue/TTL semantics or handoff flow behavior.
- Introducing new dependencies or data model changes.

## Users and primary flows
- Client requests emergency assistance and triggers handoff: notification goes to the emergency number.
- Client requests a human agent in normal flows: notification goes to the standard number.

## Functional requirements
1. Add env var `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` for the emergency handoff target.
2. Rename the standard handoff env var to `HANDOFF_WHATSAPP_NUMBER` and use it for all non-emergency handoffs.
3. Emergency routing triggers only when `conversacion.tipo_consulta == TipoConsulta.EMERGENCIA`.
4. Emergency handoff notifications are sent to `HANDOFF_EMERGENCY_WHATSAPP_NUMBER`.
5. If `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is missing or empty, fall back to `HANDOFF_WHATSAPP_NUMBER`.
6. Message content and template usage remain unchanged for emergency and standard handoffs.
7. Handoff notifications remain WhatsApp-only.
8. Queue order, TTL, and handoff activation logic remain unchanged.

## Non-functional requirements
- No new external dependencies.
- No measurable latency impact on handoff activation.
- Minimal diff, focused on routing logic and config.

## System design
- Update the handoff notification path (currently in the handoff activation flow) to select the target number based on `TipoConsulta`.
- Read env vars:
  - Standard: `HANDOFF_WHATSAPP_NUMBER`
  - Emergency: `HANDOFF_EMERGENCY_WHATSAPP_NUMBER`
- Keep existing template name/lang and message formatting.

## Interfaces
- Environment variables:
  - `HANDOFF_WHATSAPP_NUMBER`: standard handoff WhatsApp number.
  - `HANDOFF_EMERGENCY_WHATSAPP_NUMBER`: emergency handoff WhatsApp number.

## Data model
- No changes.

## Error handling and failure modes
- If `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is missing, route emergencies to the standard number.
- If the standard number is missing, behavior remains unchanged (handoff notification is not sent and should be logged as today).

## Security and privacy
- No new data collected.
- No changes to PII handling.

## Observability
- Only logs (no new metrics).
- Add or keep INFO logs indicating whether an emergency or standard route was used.

## Rollout plan
- Update environment variables in each deployment environment.
- Deploy application changes.
- Smoke test an emergency and a standard handoff.

## Rollback plan
- Revert to previous release and restore the original env var name if needed.

## Testing strategy
- Unit tests to verify:
  - Emergency handoff uses the emergency number when `TipoConsulta=EMERGENCIA`.
  - Emergency handoff falls back to standard number when emergency env var is missing.
  - Standard handoff uses the standard number.

## Decisions and trade-offs
- **Decision:** Emergency routing is based solely on `TipoConsulta=EMERGENCIA`.  
  **Rationale:** Clear existing signal, minimal changes.  
  **Rejected alternatives:** Broader NLU or rule-based triggers (risk of false positives).
- **Decision:** Rename standard env var to `HANDOFF_WHATSAPP_NUMBER`.  
  **Rationale:** Clearer meaning and matches handoff usage.  
  **Risks / mitigations:** Requires env updates in all environments; document and verify during rollout.
- **Decision:** Use `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` for emergencies with fallback to standard.  
  **Rationale:** Dedicated routing with safe fallback.
- **Decision:** Keep handoff message content and queue behavior unchanged.  
  **Rationale:** Minimize scope and risk.

## Open questions
- None.
