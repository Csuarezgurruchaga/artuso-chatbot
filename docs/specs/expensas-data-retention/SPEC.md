# Expensas data retention (monthly purge)

## Summary
Purge rows from the `chatbot-expensas` sheet so any row dated in the current month or earlier is deleted (month/year only), while future-dated rows are kept but flagged.

## Context
- The expensas sheet grows indefinitely and will eventually exceed practical limits.
- Ops wants to delete current-month records on the 25th and remove any older months.

## Goals
- Delete rows dated in the current month and any previous months (month/year only).
- Keep future-dated rows but append a note in `COMENTARIO`.
- Use `FECHA AVISO` as the primary date field.
- If `FECHA AVISO` is invalid, fall back to `FECHA DE PAGO`.
- If both dates are invalid, keep the row and mark it in `COMENTARIO`.
- Delete rows (no empty gaps).
- Run automatically via Cloud Scheduler -> Cloud Run Job on the 25th of each month at 02:00 ART.
- Log a summary of what was deleted.

## Non-goals
- Archiving old data elsewhere.
- Changing expensas flow or sheet schema.
- Daily or weekly purge.
- Keeping current or past months.

## Users and primary flows
- Ops/admin: run the monthly purge job.

## Functional requirements
1. Rows dated in the current month or any prior month are deleted (month/year only).
2. Date evaluation uses month/year only (ignore day).
3. Primary date field: `FECHA AVISO`.
4. Fallback date field: `FECHA DE PAGO` if `FECHA AVISO` is invalid.
5. Accepted date format is strictly `dd/mm/yyyy`.
6. If both dates are invalid or missing:
   - Keep the row.
   - Append a note to `COMENTARIO` indicating invalid date.
7. Rows with future dates are kept and appended with a note in `COMENTARIO` (without overwriting existing text).
8. Rows are deleted in place (no blank rows).
9. The job identifies required columns by header name (case-insensitive):
   - `FECHA AVISO`
   - `FECHA DE PAGO`
   - `COMENTARIO`
10. The job fails fast if required headers are missing or the sheet cannot be read.

## Non-functional requirements
- Low cost and minimal operational overhead.
- Safe to re-run; each run applies the same deletion rule.
- Argentina timezone for determining current month.

## System design (high level)
- A Cloud Run Job executes a purge script.
- A Cloud Scheduler cron triggers the job monthly (25th, 02:00 ART).
- The script reads the sheet, determines the cutoff month, and deletes rows in the current or past months.

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
  - Deletion cutoff logic (current or past months).
  - Fallback from `FECHA AVISO` to `FECHA DE PAGO`.
  - Invalid date handling (keep + comment).
  - Future-date handling (keep + comment).

## Decisions and trade-offs
- **Decision:** Delete rows dated in the current month or earlier; keep future-dated rows but mark them in `COMENTARIO`.
  - **Rationale:** Matches the request to purge the current month and remove older months while preserving future entries for review.
- **Decision:** Only `dd/mm/yyyy` is accepted.
  - **Rationale:** Sheet data is expected to be consistent; keeps parsing strict.
- **Decision:** If both dates are invalid, keep the row and mark `COMENTARIO`.
  - **Rationale:** Avoids accidental deletion of ambiguous data.
- **Decision:** Future dates are kept and marked in `COMENTARIO`.
  - **Rationale:** Preserves potentially valid early entries while flagging them for review.
- **Decision:** Use Cloud Run Job triggered by Scheduler.
  - **Rationale:** Isolation from the main service and predictable scheduling.
- **Decision:** Scheduler runs on the 25th at 02:00 ART.
  - **Rationale:** Matches the operational cadence requested.
- **Decision:** Delete rows in place (no empty gaps).
  - **Rationale:** Keeps the sheet compact.
- **Decision:** Fail fast on missing headers or read errors.
  - **Rationale:** Avoid silent partial deletes.

## Open questions
- None.

## Glossary
- **Deletion cutoff:** Month/year of the run; any row dated in that month or earlier is deleted.
- **Cloud Run Job:** A scheduled task execution separate from the main service.
