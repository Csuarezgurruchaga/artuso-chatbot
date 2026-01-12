# Acceptance criteria: Expensas data retention (monthly purge)

## Functional
1. Retention window keeps only rows from the current month and previous month, based on month/year.
2. `FECHA AVISO` is used as the primary date field; if invalid, `FECHA DE PAGO` is used.
3. Only `dd/mm/yyyy` is accepted as a valid date format.
4. Rows older than the retention window are deleted (not cleared), leaving no empty gaps.
5. Rows with future dates are kept.
6. If both dates are invalid or missing, the row is kept and `COMENTARIO` is appended with a short invalid-date note.
7. Header detection for required columns is case-insensitive.
8. If required headers are missing or the sheet cannot be read, the job fails with a non-zero exit.

## Observability
9. The job logs a summary including: total rows scanned, deleted count, kept count, invalid-date count, and the evaluated months.

## Ops
10. The purge can be run manually (job entrypoint) and produces the same behavior as the scheduled run.
11. Cloud Scheduler is configured to trigger the Cloud Run Job on the 1st of each month at 02:00 ART.

## Tests
12. Unit tests cover date parsing, retention window selection, fallback behavior, and invalid-date handling.
