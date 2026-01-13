# Plan: Expensas data retention (monthly purge)

## Phase 1: Prepare purge logic
1. Add a purge service/module (e.g., `services/expensas_purge_service.py`) to:
   - Load the `chatbot-expensas` sheet using existing Sheets credentials/env vars.
   - Resolve required headers case-insensitively: `FECHA AVISO`, `FECHA DE PAGO`, `COMENTARIO`.
   - Parse dates strictly as `dd/mm/yyyy`.
   - Determine the cutoff month using Argentina timezone (current month).
2. Implement row evaluation:
   - Use `FECHA AVISO` if valid; otherwise try `FECHA DE PAGO`.
   - If both invalid, keep row and append a short note to `COMENTARIO` (avoid overwriting existing text).
   - Delete rows in the current or past months.
   - Keep future-dated rows but append a short note to `COMENTARIO`.
3. Implement deletion:
   - Delete rows in descending order (or batch delete) to avoid index shifts.
   - Do not clear cells; actually delete rows.
4. Log a summary: rows scanned, deleted, kept, invalid dates, and months evaluated.

## Phase 2: Job entrypoint
5. Add a job entrypoint (e.g., `jobs/expensas_purge.py`) that:
   - Calls the purge service.
   - Exits non-zero on errors.
6. Ensure it uses the same environment variables already used for Sheets access.

## Phase 3: Tests
7. Add unit tests for:
   - Strict date parsing (`dd/mm/yyyy`).
   - Deletion cutoff logic (current or past months).
   - Fallback from `FECHA AVISO` to `FECHA DE PAGO`.
   - Invalid date handling (kept + comment updated).
   - Future-date handling (kept + comment updated).

## Phase 4: Ops/runbook
8. Document how to configure Cloud Run Job and Cloud Scheduler trigger:
   - Monthly schedule: 25th at 02:00 ART.
   - Required env vars: `EXPENSAS_SPREADSHEET_ID`, `ENABLE_EXPENSAS_SHEET`, `GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON`.
9. Provide a manual run instruction for validation.

## Rollout
- Deploy job + scheduler.
- Run once manually and verify logs.

## Rollback
- Disable Scheduler or delete the job.
