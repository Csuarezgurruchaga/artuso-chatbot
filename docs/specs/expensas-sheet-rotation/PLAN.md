# Plan: Expensas sheet rotation (current/previous tabs)

## Phase 1: Sheet naming and append path
1. Introduce constants for `PAGOS MES ACTUAL` and `PAGOS MES ANTERIOR`.
2. Update `ExpensasSheetService.append_pago` to append to `PAGOS MES ACTUAL`.
3. Add helpers to:
   - Ensure a tab exists with title + headers.
   - Format the title row (merge, colors, alignment).
   - Build the month label string in Spanish abbreviations.

## Phase 2: Rotation job
4. Replace the date-based purge logic with a rotation service:
   - Delete `PAGOS MES ANTERIOR` if it exists.
   - Rename `PAGOS MES ACTUAL` to `PAGOS MES ANTERIOR`.
   - Create a new empty `PAGOS MES ACTUAL` with formatting.
   - Update titles to current and previous month labels.
5. Update the job entrypoint (`jobs/expensas_purge.py` or a renamed file) to call the rotation service.
6. Keep environment variables unchanged.

## Phase 3: Verification and docs
7. Manually verify on a test spreadsheet:
   - Append goes to `PAGOS MES ACTUAL`.
   - Rotation moves data to `PAGOS MES ANTERIOR` and resets current.
   - Title formatting is correct on both tabs.
8. Update any relevant runbook/docs to reflect the new monthly rotation and schedule.
