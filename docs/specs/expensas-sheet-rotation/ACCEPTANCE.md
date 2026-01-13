# Acceptance criteria: Expensas sheet rotation (current/previous tabs)

1. The spreadsheet has two tabs named exactly `PAGOS MES ACTUAL` and `PAGOS MES ANTERIOR`.
2. Each tab has:
   - Row 1 merged across the first 9 columns.
   - Centered, bold, white text on black background.
   - Title text formatted as `PAGOS MES ACTUAL (Mar 2025)` / `PAGOS MES ANTERIOR (Feb 2025)` using Spanish month abbreviations.
3. Row 2 contains the 9 column headers in order, with no blank row between title and headers.
4. When there are no payments, tabs still show the title + headers (no extra rows).
5. Appending a payment always adds a new row at the end of `PAGOS MES ACTUAL` only.
6. Duplicate appends are allowed (no dedupe).
7. When the rotation job runs on the 1st at 00:05 AR time:
   - The existing `PAGOS MES ANTERIOR` tab is removed.
   - `PAGOS MES ACTUAL` is renamed to `PAGOS MES ANTERIOR`.
   - A new empty `PAGOS MES ACTUAL` tab is created with correct formatting.
   - Titles reflect current and previous month labels.
8. After rotation, only current and previous month tabs remain.
9. The old date-based purge job is no longer used; the job entrypoint triggers rotation.
