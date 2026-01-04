# Handoff agent UX cleanup and survey alignment

## Summary
Remove the duplicate "Handoff Activado" message after /r, advance the queue immediately, and align survey UX and docs with the existing question scales. Keep survey and sheet schema unchanged.

## Context
- After /r, the agent receives a second "Handoff Activado" for the same client.
- The active handoff is not released, blocking next clients in queue.
- Survey docs mention 3 options for Q2 while code uses a 1-5 scale and the invalid response prompt always says "1, 2 o 3".

## Goals
- After /r, the current client is no longer active and the agent continues with the next client if any.
- Agent sees a single, concise message after /r.
- "Handoff Activado" is sent only for a newly activated client.
- Survey prompts and docs reflect the actual per-question ranges.
- Invalid survey responses are handled consistently with a 3-attempt limit.
- Survey pending/in-progress conversations are excluded from /queue.

## Non-goals
- Changing survey questions or scales.
- Changing Google Sheets schema or adding new dependencies.
- Introducing feature flags or new APIs.
- Redesigning client-facing survey offer copy beyond range instructions.

## Users and primary flows
- Agent: uses /r to close current handoff, then continues with next in queue.
- Client: receives survey offer, optionally completes survey.
- System: manages queue state and survey timeouts.

## Functional requirements
1. /r with survey enabled:
   - Send survey offer to the client.
   - Set conversation state to ESPERANDO_RESPUESTA_ENCUESTA.
   - Set atendido_por_humano to False.
   - Remove the client from the handoff queue (so it is not active).
   - Activate next client if present and send "Handoff Activado" for that client only.
   - Do not send "Handoff Activado" for the same client after /r.
2. Agent confirmation message after /r (survey enabled):
   - Text: "✅ Cierre enviado a {nombre} ({telefono}). ⏳ Encuesta en curso (auto-cierre 15 min). Usa /queue." and include " o /next" only if there is more than 1 conversation in queue.
   - If queue is empty, append "Cola vacia."
3. /r with survey disabled:
   - Close the conversation immediately, remove from queue, activate next if present.
   - Agent message: "✅ Cierre enviado a {nombre} ({telefono}). Usa /queue." and include " o /next" only if there is more than 1 conversation in queue. Add "Cola vacia." when no queue.
4. /r repeated while an active conversation is already in survey states:
   - Ignore silently (no agent response).
5. Survey questions and ranges remain as in code:
   - Q1: 1-3
   - Q2: 1-5
   - Q3: 1-2
6. Survey invalid response handling:
   - Per question, allow up to 3 invalid attempts.
   - On invalid response, repeat the same question with instructions matching its range.
   - On the 3rd invalid attempt, abort survey: send completion message, close conversation, and store partial responses with missing values as "N/A".
   - If the aborted conversation is active (edge case), activate next and send "Handoff Activado".
7. Survey timeouts:
   - Survey offer timeout: 2 minutes.
   - Survey in progress timeout: 15 minutes.
   - Timeouts must still be applied even when atendido_por_humano is False.
   - No agent notification on timeouts.
8. /queue:
   - Do not list survey pending or survey in progress conversations.
9. Logging:
   - Add INFO logs for survey offer sent, accepted, declined, started, invalid response, aborted by invalids, completed, timeouts, and suppressed handoff activation.
   - Log full phone numbers and state only; do not log message text.
10. Keep "Handoff Activado" copy unchanged.

## Non-functional requirements
- Latency: agent command responses under 1s in normal conditions.
- Reliability: queue advancement must not be blocked by survey state.
- Cost: no new external services or dependencies.

## System design
- Agent command flow in AgentCommandService handles /r:
  - send survey offer when enabled
  - update conversation state and flags
  - remove from queue and activate next
  - send agent confirmation message
- handle_agent_message sends "Handoff Activado" only for the newly activated client.
- SurveyService handles survey questions, invalid attempts, and completion.
- TTL sweep handles survey timeouts regardless of atendido_por_humano.

## Interfaces
- Agent input: /r (/done alias)
- Agent output messages: per FR-2 and FR-3
- Client output messages:
  - Survey offer (existing copy)
  - Survey question prompts with range-correct instructions
  - Survey completion message (existing)
- Scheduler: /handoff/ttl-sweep applies timeouts.

## Data model
- No schema changes.
- Store invalid attempt counters in conversacion.datos_temporales (e.g., survey_invalid_q1).

## Error handling and failure modes
- If survey offer fails to send, close conversation and log error.
- If sending survey question fails, close conversation and log error.
- If queue activation fails, log error and keep queue consistent.

## Security and privacy
- Phone numbers are PII; logs will include full numbers as requested.
- Do not log message content.

## Observability
- INFO logs for key survey and queue transitions.
- Log event name, client_phone, agent_phone, state.

## Rollout plan
- Direct deploy to Cloud Run.
- Manual verification using a test agent and client.

## Rollback plan
- Revert the deploy to the previous release.

## Testing strategy
- Unit tests for /r flow with survey enabled and disabled.
- Unit tests for queue advancement and suppression of "Handoff Activado".
- Unit tests for survey invalid attempts and partial save behavior.
- Manual end-to-end test with a real agent and client number.

## Decisions and trade-offs
- Removed survey conversations from queue so agents can continue working; this keeps survey async.
- Logs keep full phone numbers for troubleshooting at the cost of PII exposure.
- Keep survey scale as currently implemented to avoid changing analysis.

## Open questions
- None.
