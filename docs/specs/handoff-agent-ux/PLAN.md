# Plan: handoff-agent-ux

## Implementation tasks
1. Update /r handling in `services/agent_command_service.py`:
   - When survey enabled, send offer then remove from queue, set state to ESPERANDO_RESPUESTA_ENCUESTA, set atendido_por_humano False.
   - Build new agent message; append "Cola vacia." when queue empty.
   - If active conversation already in survey states, ignore silently.
2. Update `main.py` handle_agent_message flow to avoid sending "Handoff Activado" for the same client, only for a new active client; add suppression log.
3. Update TTL sweep in `main.py` to apply survey timeouts even if atendido_por_humano is False.
4. Update `services/survey_service.py`:
   - Add per-question invalid attempt counters in datos_temporales.
   - Repeat question with correct range instructions.
   - Abort after 3 invalids with completion message and partial save (N/A).
5. Update `_save_survey_results` to fill missing responses with "N/A".
6. Update docs `SURVEY_README.md` and `WHATSAPP_HANDOFF_README.md` to match current question scales and new agent UX.
7. Add/adjust tests in `tests/...` for /r flow, survey invalids, and queue behavior.

## Files to change
- `services/agent_command_service.py`
- `main.py`
- `services/survey_service.py`
- `chatbot/states.py` (if helper needed for queue/survey state)
- `SURVEY_README.md`
- `WHATSAPP_HANDOFF_README.md`
- `tests/...`

## Data/migration steps
- None. No schema changes.

## Integration points
- Meta WhatsApp API send_text_message
- Conversation queue in `chatbot/states.py`
- Google Sheets survey append

## Test plan
- `pytest -q`
- Manual WhatsApp flow with /r, queue, and survey responses.

## Rollout/rollback
- Deploy to Cloud Run; verify logs.
- Rollback by redeploying previous revision.
