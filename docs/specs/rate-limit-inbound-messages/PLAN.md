# Plan: rate-limit inbound conversation starts

## Phase 1 — Identify integration points
1. Review `main.py` message handling order (media handling, post-finalized window, handoff, and routing).
2. Confirm available helpers for greeting and menu detection in `ChatbotRules`.

## Phase 2 — Implement rate-limit check
3. Add a small helper (local in `main.py` or in `ChatbotRules`) to determine whether an inbound message is a **conversation start**:
   - Count when state is `INICIO` or `ESPERANDO_OPCION`.
   - Count if the message is a greeting (“hola”/“inicio”/“empezar”) even mid-flow.
   - Do **not** count if the message is “volver al menú / empezar de nuevo”.
   - Do **not** count if handoff is active (`ATENDIDO_POR_HUMANO` or `atendido_por_humano`).
   - Do **not** count if `was_finalized_recently` is true.
4. Apply `rate_limit_service.check_and_increment` in `main.py` **before flow routing**, including media-first messages.
5. If blocked, return `RATE_LIMIT_MESSAGE` and keep state unchanged.

## Phase 3 — Tests & validation
6. Add unit tests to validate:
   - First message counts even if not “hola”.
   - Repeated “hola” while in `INICIO/ESPERANDO_OPCION` increments and blocks at limit.
   - Messages inside a flow do not increment.
   - Messages within `POST_FINALIZADO_WINDOW` do not increment.
   - Media without caption counts as start.
   - Handoff-active conversations are not counted.
7. Run existing tests (or at minimum the new ones) and report results.

## Phase 4 — Manual verification
8. Manual walkthrough with WhatsApp:
   - Send >20 “hola” from same number, confirm block.
   - Start a flow, answer steps, confirm no extra counts.
   - Send media as first message, confirm it counts.
