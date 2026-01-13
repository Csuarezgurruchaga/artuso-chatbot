# Expensas sheet rotation (current/previous tabs)

## Summary
Rotate expensas payments monthly between two tabs: `PAGOS MES ACTUAL` and `PAGOS MES ANTERIOR`. All new payments append to the current tab. Replace the date-based purge job with a rotation job.

## Context
- The current design uses a single `chatbot-expensas` tab and a date-based purge.
- Operations want a clearer split between the current month and the previous month.
- Titles must be visually formatted and include month/year.

## Goals
- Keep only current-month and previous-month expensas data.
- Append all new payments to `PAGOS MES ACTUAL` without deduplication.
- Run a monthly rotation job on the 1st at 00:05 (America/Argentina/Buenos_Aires).
- Apply consistent title/header formatting on both tabs.

## Non-goals
- Historical archive beyond the previous month.
- Deduplication or idempotent append logic.
- Changes to the expensas flow fields or validation.
- New dependencies or external storage.

## Users and primary flows
- Chatbot appends a payment to the current-month tab.
- Monthly job rotates current data into the previous tab and resets current.
- Ops reviews current or previous month tabs as needed.

## Functional requirements
1. The spreadsheet has two tabs with exact names:
   - `PAGOS MES ACTUAL`
   - `PAGOS MES ANTERIOR`
2. Each tab has a title row in row 1:
   - Merged across the first 9 columns (dynamic merge width based on column count).
   - Centered, bold, white text on black background.
   - Title format:
     - `PAGOS MES ACTUAL (Mar 2025)`
     - `PAGOS MES ANTERIOR (Feb 2025)`
   - Month abbreviations in Spanish: Ene, Feb, Mar, Abr, May, Jun, Jul, Ago, Sep, Oct, Nov, Dic.
3. Row 2 contains the 9 column headers, in this order:
   - `TIPO AVISO`, `FECHA AVISO`, `FECHA DE PAGO`, `MONTO`, `ED`, `DPTO`, `UF`, `COMENTARIO`, `COMPROBANTE`
4. There is no blank row between the title row and the column headers.
5. If a tab has no data, keep the title row and headers (no "Sin registros").
6. New payments always append to the end of `PAGOS MES ACTUAL`.
7. No deduplication is performed on append (duplicates are allowed).
8. The monthly rotation job runs on the 1st of each month at 00:05 AR time:
   - Delete the existing `PAGOS MES ANTERIOR` tab (if present).
   - Rename `PAGOS MES ACTUAL` to `PAGOS MES ANTERIOR` (preserve data).
   - Create a new empty `PAGOS MES ACTUAL` tab with title + headers.
   - Update title text:
     - `PAGOS MES ACTUAL` uses the current month/year.
     - `PAGOS MES ANTERIOR` uses the previous month/year.
9. If tabs are missing (fresh sheet), create both tabs with the required formatting.
10. Appends are not blocked during rotation; payments may land in either tab around the rotation window.
11. Replace the existing purge-by-date job with this rotation job.

## Non-functional requirements
- Handle ~301–1500 rows/month without noticeable delays.
- Low operational overhead; no manual steps required.
- Use America/Argentina/Buenos_Aires as the time basis.

## System design (high level)
- `ExpensasSheetService` appends payments to `PAGOS MES ACTUAL`.
- A monthly rotation service runs via Cloud Scheduler -> Cloud Run Job.
- Rotation performs delete/rename/create operations with gspread.

## Interfaces
- Environment variables (existing):
  - `EXPENSAS_SPREADSHEET_ID`
  - `ENABLE_EXPENSAS_SHEET`
  - `GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON`

## Data model
- Same 9 columns as today; no schema changes beyond tab naming.

## Observability
- Log a rotation summary: rows moved, rows cleared, tab names, and month labels.

## Rollout plan
- Deploy code changes.
- Create the two tabs if missing (fresh sheet).
- Enable the monthly job on the 1st at 00:05 AR time.

## Rollback plan
- Disable the monthly rotation job.
- Revert to the previous release if needed.

## Testing strategy
- Manual verification against a test spreadsheet:
  - Append behavior to current tab.
  - Monthly rotation (delete/rename/create).
  - Title formatting and month labels.

## Decisions and trade-offs
- **Decision:** Two tabs (current/previous), not two sections in one tab.
  - **Rationale:** Clear separation and simpler rotation.
- **Decision:** Replace date-based purge with monthly rotation.
  - **Rationale:** Matches the new retention model.
- **Decision:** Titles include month/year in the format `PAGOS MES ACTUAL (Mar 2025)`.
  - **Rationale:** Human-friendly and consistent across tabs.
- **Decision:** No dedupe on append.
  - **Rationale:** Keep append logic simple; duplicates are acceptable.
- **Decision:** Rotation does not block concurrent appends.
  - **Rationale:** Simplicity over strict consistency during the rotation window.

## Open questions
- None.

## Glossary
- **Rotation job:** Monthly process that moves current data to previous and resets current.
- **Tab:** A sheet within the Google Spreadsheet (worksheet).
