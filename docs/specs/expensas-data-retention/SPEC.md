# Expensas data retention (monthly purge)

## Summary
Purge old rows from the `chatbot-expensas` sheet so only the current month is retained, based on `FECHA AVISO` (month/year only).

## Context
- The expensas sheet grows indefinitely and will eventually exceed practical limits.
- Only recent data is useful: current month plus previous month.

## Goals
- Keep only rows from the current month.
- Use `FECHA AVISO` as the primary date field (month/year only).
- If `FECHA AVISO` is invalid, fall back to `FECHA DE PAGO`.
- If both dates are invalid, keep the row and mark it in `COMENTARIO`.
- Delete rows (no empty gaps).
- Run automatically via Cloud Scheduler -> Cloud Run Job on the 1st of each month at 02:00 ART.
- Log a summary of what was deleted.

## Non-goals
- Archiving old data elsewhere.
- Changing expensas flow or sheet schema.
- Daily or weekly purge.

## Users and primary flows
- Ops/admin: run the monthly purge job.

## Functional requirements
1. Retention window is the current month only.
2. Date evaluation uses month/year only (ignore day).
3. Primary date field: `FECHA AVISO`.
4. Fallback date field: `FECHA DE PAGO` if `FECHA AVISO` is invalid.
5. Accepted date format is strictly `dd/mm/yyyy`.
6. If both dates are invalid or missing:
   - Keep the row.
   - Append a note to `COMENTARIO` indicating invalid date.
7. Rows older than the retention window are deleted in place (no blank rows).
8. The job identifies required columns by header name (case-insensitive):
   - `FECHA AVISO`
   - `FECHA DE PAGO`
   - `COMENTARIO`
9. Future dates are kept.
10. The job fails fast if required headers are missing or the sheet cannot be read.

## Non-functional requirements
- Low cost and minimal operational overhead.
- Idempotent within the same month (no additional deletes after first run).
- Argentina timezone for determining current month.

## System design (high level)
- A Cloud Run Job executes a purge script.
- A Cloud Scheduler cron triggers the job monthly (1st, 02:00 ART).
- The script reads the sheet, determines the retention window, and deletes old rows.

## Interfaces
- Environment variables:
  - `EXPENSAS_SPREADSHEET_ID`
  - `ENABLE_EXPENSAS_SHEET`
  - `GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON`

## Data model
- Existing sheet `chatbot-expensas` with headers including:
  - `FECHA AVISO`
  - `FECHA DE PAGO`
  - `COMENTARIO`

## Observability
- Log summary including: total rows scanned, rows deleted, rows kept, invalid date rows, and months evaluated.

## Rollout plan
- Deploy Cloud Run Job and Scheduler.
- Run once manually to validate logs.

## Rollback plan
- Disable or delete the Scheduler job.

## Testing strategy
- Unit tests for:
  - Date parsing (dd/mm/yyyy).
  - Retention window logic (current + previous month).
  - Fallback from `FECHA AVISO` to `FECHA DE PAGO`.
  - Invalid date handling (keep + comment).

## Decisions and trade-offs
- **Decision:** Retention window is the current month only.
  - **Rationale:** Matches the requested one-month window.
- **Decision:** Only `dd/mm/yyyy` is accepted.
  - **Rationale:** Sheet data is expected to be consistent; keeps parsing strict.
- **Decision:** If both dates are invalid, keep the row and mark `COMENTARIO`.
  - **Rationale:** Avoids accidental deletion of ambiguous data.
- **Decision:** Use Cloud Run Job triggered by Scheduler.
  - **Rationale:** Isolation from the main service and predictable scheduling.
- **Decision:** Delete rows in place (no empty gaps).
  - **Rationale:** Keeps the sheet compact.
- **Decision:** Fail fast on missing headers or read errors.
  - **Rationale:** Avoid silent partial deletes.

## Open questions
- None.

## Glossary
- **Retention window:** Months of data kept in the sheet (current + previous).
- **Cloud Run Job:** A scheduled task execution separate from the main service.
