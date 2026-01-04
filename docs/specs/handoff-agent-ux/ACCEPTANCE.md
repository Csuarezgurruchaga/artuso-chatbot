# Acceptance criteria: handoff-agent-ux

## Functional
- Given queue [A] and survey enabled, when agent sends /r, then agent receives one message with:
  "✅ Cierre enviado a {nombre} ({telefono}). ⏳ Encuesta en curso (auto-cierre 15 min). Usa /queue." and "Cola vacia.", and no "Handoff Activado" follows.
- Given queue [A,B] and survey enabled, when agent sends /r, then agent receives the single /r message containing "Usa /queue." and then a "Handoff Activado" message for B. /queue shows B active and A is not listed.
- Given survey disabled, when /r is sent, then the conversation closes immediately and agent receives:
  "✅ Cierre enviado a {nombre} ({telefono}). Usa /queue." plus "Cola vacia." when no queue.
- Given survey Q2 (1-5), when client responds with invalid text, the same question is repeated with instructions matching 1-5.
- Given 3 invalid responses for the same question, the survey aborts, the client receives the completion message, and partial results are saved with missing values set to "N/A". survey_accepted is stored as timeout.
- Survey completion or timeout does not notify the agent.
- /queue does not list survey pending or survey in progress conversations.
- Survey offer timeout is 2 minutes and survey in progress timeout is 15 minutes even when atendido_por_humano is False.

## Negative/edge cases
- /r repeated while the active conversation is already in a survey state yields no agent response.
- Survey question send failure closes the conversation and allows queue progress.

## Observability checks
- INFO logs exist for: survey_offer_sent, survey_started, survey_invalid, survey_aborted_invalids, survey_completed, survey_timeout, and handoff_activated_suppressed.
- Logs include client_phone and agent_phone but no message text.

## Validation commands
- `pytest -q`
