# Input validation and per-phone rate limits

## Summary
Add stricter validation for expensas inputs (fecha, monto, direccion) and enforce a per-phone daily limit of 20 flow starts, persisted in Google Sheets.

## Context
- Current validation only checks basic formats/lengths.
- Users can send many requests in a short time without throttling.

## Goals
- Enforce date format and accept flexible separators.
- Validate monto as numeric, positive, and bounded.
- Enforce address rules (must include letters and numbers; allow limited punctuation).
- Limit each phone to 20 flow starts per day (Argentina calendar day).
- Persist rate limit counters in Google Sheets.

## Non-goals
- Change the overall expensas/servicio flow order.
- Add new external dependencies or databases beyond Sheets.
- Redesign NLU or address parsing beyond validation rules.

## Users and primary flows
- Tenant: submits expensas payment info.
- Tenant: submits service request info.
- System: blocks new flow starts beyond daily limit.

## Functional requirements
1. Fecha (expensas):
   - Accept only dd/mm/yyyy format for validation.
   - Accept "-" and "." as separators and normalize to "/".
   - Keep "hoy/ayer" as valid inputs for expensas.
2. Monto (expensas):
   - Accept numeric values with optional thousands and decimals.
   - Must be > 0 and <= 2,000,000.
   - When both "." and "," appear, the last separator is the decimal separator.
   - Normalize to a string with "." as decimal separator and no thousands.
3. Direccion (expensas and servicio):
   - Must include at least one letter and one number.
   - Allow only letters, numbers, spaces, and these symbols: ".,#/-º°".
   - Reject any other symbols.
4. Rate limit:
   - Count one "request" per flow start (expensas/servicio/emergencia).
   - Limit: 20 per Argentina calendar day.
   - Check the limit at flow start (before advancing state).
   - On limit exceeded: block and show the configured wait message (no handoff).
   - Persist counters in Google Sheets.

## Non-functional requirements
- Latency: validation and rate checks under 200ms average.
- Reliability: rate limit must survive process restarts (Sheets persistence).
- Locale: Argentina timezone for daily window.

## System design (high level)
- Validation rules applied when capturing individual fields and during final validation.
- Rate limit check executed at flow start before advancing state.
- Counters stored in a new sheet named RATE_LIMIT.

## Interfaces
- User input: date, amount, address fields.
- System output: validation error prompts and rate-limit message.

## Data model
- Add a new sheet named RATE_LIMIT to store:
  - phone
  - date (yyyy-mm-dd)
  - count
  - updated_at (timestamp)

## Security and privacy
- Avoid logging raw address input on validation errors.
- Keep phone numbers as PII; log only when needed for rate limiting.

## Observability
- Log rate-limit blocks with phone and date.
- Log validation failures with field name (no raw user input).

## Rollout plan
- Deploy with default limits enabled.
- Monitor rate-limit logs for false positives.

## Rollback plan
- Disable rate limiting via config or revert release.

## Testing strategy
- Unit tests for date, amount, and address validation.
- Unit tests for rate-limit counting and daily reset.

## Decisions and trade-offs
- **Decision:** Date validation is format-only (dd/mm/yyyy).
  - **Rationale:** User chose format validation; simpler and lower friction.
  - **Rejected alternatives:** Calendar-valid dates; rejecting future dates.
- **Decision:** Date separators "-" and "." are accepted and normalized.
  - **Rationale:** User wants flexible input while keeping stored format consistent.
  - **Rejected alternatives:** Only "/" separator.
- **Decision:** Keep "hoy/ayer" as valid inputs for expensas.
  - **Rationale:** Maintains the current shortcut while enforcing format on other inputs.
  - **Rejected alternatives:** Disallow textual shortcuts or limit to buttons only.
- **Decision:** Amount accepts thousands + decimals and must be <= 2,000,000.
  - **Rationale:** Support common input formats with a clear upper bound.
  - **Rejected alternatives:** Integers only; no upper bound.
- **Decision:** If both "." and "," appear, the last separator is decimal; normalize to ".".
  - **Rationale:** Handles inputs like 1.234,56 with predictable parsing.
  - **Rejected alternatives:** Reject mixed separators or force a single locale.
- **Decision:** Normalized amount is stored as a plain numeric string with "." decimal and no thousands.
  - **Rationale:** Consistent downstream storage without locale ambiguity.
- **Decision:** Address validation applies to both expensas and service.
  - **Rationale:** Consistent hygiene across flows.
  - **Rejected alternatives:** Only validate expensas or only service.
- **Decision:** Address requires at least one letter and one number; only ".,#/-º°" punctuation is allowed.
  - **Rationale:** Enforces real address structure while allowing common formatting.
  - **Rejected alternatives:** Allow broader symbols or allow no-number addresses.
- **Decision:** Rate limit counts flow starts; limit 20/day (Argentina calendar day).
  - **Rationale:** Prevent spam without blocking ongoing flows; aligns with local day.
  - **Rejected alternatives:** Per-message limits; rolling 24h window.
- **Decision:** Rate limit is checked at flow start only.
  - **Rationale:** Avoids blocking users mid-flow.
  - **Rejected alternatives:** Check on every message or at confirmation.
- **Decision:** Store rate-limit counters in Google Sheets.
  - **Rationale:** Avoid new infra; consistent with existing storage.
  - **Rejected alternatives:** Memory-only or new DB.
- **Decision:** Use a dedicated RATE_LIMIT sheet for counters.
  - **Rationale:** Keeps counters isolated and simple to query/update.
  - **Rejected alternatives:** Extend CLIENTES or chatbot-expensas.
- **Decision:** On limit exceeded, block and show a wait message (no handoff).
  - **Rationale:** Simple enforcement; avoids queue overload.
  - **Message:** "Por hoy ya alcanzaste el máximo de 20 interacciones 😊 Mañana podés volver a usar el servicio sin problema!"

## Open questions
- None.

## Glossary
- **Flow start:** When a user selects a main menu option (expensas/servicio/emergencia).
- **Rate limit:** A cap on how many flow starts a phone number can initiate per day.
