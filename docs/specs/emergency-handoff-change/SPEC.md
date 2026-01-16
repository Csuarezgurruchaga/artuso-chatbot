# Emergency handoff change

## Summary
Replace the current emergency handoff with an immediate client-facing message that directs them to call a phone number. Do not initiate handoff/queue for emergencies. Support emergency detection via menu, keywords, and NLU on both WhatsApp and Messenger. Preserve in-progress flows by pausing them and resuming only when the user sends an explicit `CONTINUAR` command.

## Context
Today, emergencies trigger the same handoff flow as other requests. The new requirement is to bypass handoff and instruct users to call a dedicated emergency phone number, while keeping the rest of the chatbot flow intact for non-emergencies.

## Goals
- Detect emergencies through all existing signals (menu button, keywords, NLU).
- Send a fixed emergency message to the client (WhatsApp + Messenger).
- Avoid all handoff/queue notifications for emergencies.
- Allow in-progress flows to be paused and resumed explicitly.
- Keep rate limit behavior unchanged.

## Non-goals
- Changing non-emergency handoff flow, queue, TTL, or templates.
- Adding new notification channels (email/Slack/WhatsApp to agents).
- Adding new dependencies or data model changes.
- Changing survey, expensas, or reclamo flows outside of emergency interception.

## Functional requirements
1. **Emergency detection triggers**
   - Trigger on: menu button `emergencia`, keyword matches, and NLU classification to `EMERGENCIA`.
   - Applies to both WhatsApp and Messenger.

2. **Emergency client message**
   - Replace the current handoff response with:
     "🚨 *Emergencia detectada*\n\nPara una atención inmediata, comunicate directamente con nuestro equipo al siguiente número:\n\n📞 *11-5609-6511*\n\nEste canal es el más rápido para resolver situaciones urgentes.\nEl chatbot no gestiona emergencias en tiempo real."
   - This exact formatting (markdown + line breaks) must be preserved.

3. **No handoff for emergencies**
   - Do not enqueue or notify agents for emergency events.
   - Do not send templates or fallback handoff messages.

4. **Emergency number source + formatting**
   - Use `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` as the source of the phone number.
   - If the env var contains a +54911... value, display it in `11-XXXX-XXXX` format (local BA format).
   - Display formatting must be `11-XXXX-XXXX` (with a hyphen) per requirement.

5. **Missing/invalid emergency number**
   - If `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is missing or cannot be formatted into `11-XXXX-XXXX`, log a clear error for Cloud Run.
   - Do not attempt to send the emergency response in this case.

6. **Post-message behavior**
   - If the conversation is not mid-flow (e.g., initial/menu states), finalize the conversation after sending the emergency message.
   - Finalized conversations should restart on any new text or media input (no special “hola” requirement).

7. **Mid-flow emergency handling**
   - If the emergency is detected mid-flow (data collection/validation/confirmation/etc.), pause the flow and preserve in-progress data.
   - The flow must only resume when the user sends the explicit command `CONTINUAR` (case-insensitive).
   - Any other input while paused keeps the flow paused; the emergency message may be re-sent to the user.

8. **Emergency during active handoff**
   - If the conversation is already in handoff/queue, keep the queue state unchanged and still send the emergency message to the client.
   - Do not send additional agent notifications for this emergency.

9. **Rate limit**
   - Emergency handling must respect the existing rate limit (no bypass).

## Non-functional requirements
- Minimal diff limited to emergency detection and flow control.
- No new external dependencies.
- No measurable latency impact.

## System design
- Intercept emergency detection before the standard handoff activation path.
- Use `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` to derive a display string `11-XXXX-XXXX`.
- If formatting fails, log `ERROR` with a clear message including the env var key name.
- Store pause/resume state in existing conversation fields or `datos_temporales` (no schema changes).

## Data model
- No schema changes.

## Error handling and failure modes
- Missing/invalid emergency number: log error and skip emergency response.
- Standard handoff path remains unchanged for non-emergency requests.

## Observability
- Add/keep INFO logs for emergency detection and whether message was sent.
- Add ERROR log when emergency number is missing/invalid.

## Rollout plan
- Deploy code change.
- Ensure `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is set in all environments.
- Smoke test emergency detection on WhatsApp and Messenger.

## Rollback plan
- Revert to previous release.

## Testing strategy
- Unit tests for emergency detection → response message.
- Unit tests for formatting of `HANDOFF_EMERGENCY_WHATSAPP_NUMBER`.
- Unit tests for mid-flow pause/resume with `CONTINUAR`.
- Manual test: trigger emergency from menu and via text; verify no handoff is created.

## Decisions and trade-offs
- **Decision:** Emergency triggers include menu + keywords + NLU.  
  **Rationale:** Max coverage; matches existing detection.
- **Decision:** Emergency response replaces handoff and sends the fixed call-to-action message.  
  **Rationale:** Emergencies should be handled off-chat.
- **Decision:** No agent notifications for emergencies.  
  **Rationale:** Avoids handoff workload and aligns with direct-call requirement.
- **Decision:** Use `HANDOFF_EMERGENCY_WHATSAPP_NUMBER`, formatted as `11-XXXX-XXXX`.  
  **Rationale:** Ensures user-friendly local display.
- **Decision:** If emergency number missing/invalid, log error and do not send response.  
  **Rationale:** Avoids sending incorrect contact info while surfacing misconfig.
- **Decision:** Mid-flow emergencies pause and resume only with `CONTINUAR`.  
  **Rationale:** Preserves user progress while requiring explicit resume.
- **Decision:** Respect rate limits for emergencies.  
  **Rationale:** Keep behavior consistent and avoid bypassing safeguards.

## Glossary
- **NLU:** Natural Language Understanding; the intent classification step used to map free text to `TipoConsulta`.

## Open questions
- None.
