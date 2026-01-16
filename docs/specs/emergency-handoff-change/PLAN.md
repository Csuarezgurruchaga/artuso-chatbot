# Plan

## Phase 1: Analyze current flow
- Locate emergency detection paths (menu, keywords, NLU) in `chatbot/rules.py`.
- Identify handoff activation points and message sending in `chatbot/rules.py` and `main.py`.

## Phase 2: Emergency message + number formatting
- Add a helper to format `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` to `11-XXXX-XXXX`.
- Build the emergency message using the formatted number and the exact copy from SPEC.
- Log an ERROR and abort emergency response when formatting fails or env var is missing.

## Phase 3: Flow control changes
- Intercept emergency detection before handoff activation.
- Replace emergency response with the new message (WhatsApp + Messenger).
- Ensure no handoff enqueue/notifications for emergencies.
- Implement mid-flow pause logic and store state/data for resumption.
- Implement resume command `CONTINUAR` (case-insensitive) to restore the prior state.
- For paused state, keep the flow paused when input is not `CONTINUAR` (may re-send the emergency message).
- Ensure non-mid-flow emergencies finalize the conversation, and new inputs restart as normal.

## Phase 4: Edge cases + handoff interaction
- If emergency is detected while already in handoff/queue, keep queue intact and send only the emergency message to the client.
- Do not notify agents for emergencies.
- Preserve rate-limit behavior (no bypass).

## Phase 5: Tests & verification
- Add/update test script(s) to cover:
  - Emergency detection → message response.
  - Number formatting from `+54911...` to `11-XXXX-XXXX`.
  - Missing/invalid number → logged error, no emergency response.
  - Mid-flow pause + resume via `CONTINUAR`.
- Manual smoke test on WhatsApp and Messenger.

## Phase 6: Rollout
- Update Cloud Run env var `HANDOFF_EMERGENCY_WHATSAPP_NUMBER`.
- Deploy and verify logs for emergency detection.
