# Acceptance criteria: rate-limit inbound conversation starts

1. A daily per-phone limit (20/day, AR timezone) is enforced for WhatsApp conversation starts.
2. The first inbound message counts as a start even if it is not “hola” (text or media).
3. Repeated “hola” while in `INICIO/ESPERANDO_OPCION` increments the counter and blocks at the daily cap.
4. Messages within an already started conversation do not increment the counter.
5. Messages during `POST_FINALIZADO_WINDOW` do not increment.
6. Messages during handoff (`ATENDIDO_POR_HUMANO` or `atendido_por_humano`) do not increment.
7. “Volver al menú / empezar de nuevo” does not increment.
8. When the limit is exceeded, the bot replies with `RATE_LIMIT_MESSAGE` and preserves the current state.
9. Blocked attempts do not update `Updated_at` or increase the stored count.
