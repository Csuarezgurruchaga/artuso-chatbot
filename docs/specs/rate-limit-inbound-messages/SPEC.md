# Rate limit por inicio de conversación (mensajes entrantes)

## Summary
Apply a daily per-phone rate limit on conversation starts so repeated inbound "hola" (or any first message) is capped at 20/day and prevents Meta blocking.

## Context
- Current limiter increments only when a user selects an intent (via `_aplicar_tipo_consulta`).
- Repeated "hola" messages do not increment and therefore are not blocked.

## Goals
- Count inbound **conversation starts** for WhatsApp and block once the daily limit is reached.
- Treat the first message of a session as a start even if it is not "hola" (e.g., media or text).
- Do **not** count every message inside an ongoing conversation.
- Keep the existing user-facing rate limit message.

## Non-goals
- Changing the expensas/reclamos flow beyond rate limiting.
- Introducing new storage backends or dependencies.

## Functional requirements
1. Apply a 20/day limit **per phone** (AR timezone date) for WhatsApp.
2. A "conversation start" must be counted when the session begins, even if the first message is not "hola".
3. Messages inside an already-started conversation should not be counted.
4. When the limit is exceeded, respond with the existing `RATE_LIMIT_MESSAGE`.
5. Do not count during handoff once it has been activated.
6. If the sheet write fails, allow the message (fail-open) and log the error.
7. While the state is `INICIO` or `ESPERANDO_OPCION`, repeated "hola" should count toward the daily limit.
8. "Volver al menú / empezar de nuevo" must not count as a new start.
9. Media without caption as the first inbound message must count as a start.
10. When blocked, do not update `Updated_at` or increment further counts.
11. Do not count messages during `POST_FINALIZADO_WINDOW` (120s).
12. Allow disabling the inbound rate limit check via config (`RATE_LIMIT_INBOUND_ENABLED=false`).

## Non-functional requirements
- Minimal, reviewable diffs.
- Preserve current behavior outside the limiter.

## Open questions

## Decisions and trade-offs
- **Decision:** Limit by phone per day in AR timezone.
  - **Rationale:** Simple daily cap aligned with existing sheet layout.
- **Decision:** Apply to WhatsApp only.
  - **Rationale:** Only WhatsApp is in scope for this limit.
- **Decision:** Fail open on sheet errors.
  - **Rationale:** Avoid blocking users due to external storage issues.
- **Decision:** Keep current `RATE_LIMIT_MESSAGE`.
  - **Rationale:** Consistent UX.
- **Decision:** Do not count after handoff is activated.
  - **Rationale:** Human support should not be blocked by the limit.
- **Decision:** Count starts based on state `INICIO` or `ESPERANDO_OPCION`.
  - **Rationale:** Matches "conversation start" and avoids counting messages mid-flow.
- **Decision:** If the user sends "hola" mid-flow, reset and count as a new start.
  - **Rationale:** Explicit restart should consume a new daily slot.
- **Decision:** "Volver al menú / empezar de nuevo" does not count as a new start.
  - **Rationale:** Navigation should not consume the daily budget.
- **Decision:** Once blocked, do not keep incrementing the counter.
  - **Rationale:** Avoid inflating counts beyond the daily cap.
- **Decision:** Any inbound message type can start a session (text or media).
  - **Rationale:** First message should count regardless of format.
- **Decision:** Do not count during `POST_FINALIZADO_WINDOW` (120s).
  - **Rationale:** Grace window should not consume daily budget.
- **Decision:** When blocked, keep the current state and return `RATE_LIMIT_MESSAGE`.
  - **Rationale:** Avoid losing context; consistent UX.
- **Decision:** Count repeated "hola" while in `INICIO/ESPERANDO_OPCION`.
  - **Rationale:** Spam should consume the daily budget.
- **Decision:** Media without caption as first message counts as a start.
  - **Rationale:** Prevent media-only spam.
- **Decision:** Do not update `Updated_at` when blocked.
  - **Rationale:** Avoid extra writes for blocked attempts.
- **Decision:** Apply the rate-limit check in `main.py` before flow routing.
  - **Rationale:** Captures media-first starts and blocks early.

## Glossary
- **Conversation start:** First inbound message that begins a new chat session and triggers the bot flow.
- **POST_FINALIZADO_WINDOW:** 120-second grace window after finalization where follow-up messages are treated as post-close.
