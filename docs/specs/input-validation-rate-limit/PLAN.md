# Plan: input-validation-rate-limit

## Implementation tasks
1. Update date validation to accept "-" and "." and normalize to "/"; keep "hoy/ayer" for expensas.
2. Update amount parsing/validation to allow thousands + decimals, enforce >0 and <= 2,000,000, and normalize to dot-decimal string.
3. Update address validation for expensas and servicio:
   - require at least one letter and one number
   - allow only letters, numbers, spaces, and ".,#/-º°"
4. Add rate-limit check at flow start (expensas/servicio/emergencia) with Argentina calendar day window.
5. Persist rate-limit counters in a new RATE_LIMIT sheet with columns: phone, date, count, updated_at.
6. Add logs for validation failures (field only) and rate-limit blocks (phone + date).
7. Add/adjust unit tests for date parsing, amount parsing, address validation, and daily rate limiting.

## Files to change
- `chatbot/rules.py`
- `chatbot/states.py`
- `services/clients_sheet_service.py` or a new sheet service for RATE_LIMIT
- `tests/...`

## Test plan
- `pytest -q`
