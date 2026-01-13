# Runbook: Expensas data retention purge

## Cloud Run Job setup
- Create a Cloud Run Job using the same container image as the service.
- Command/args: `python jobs/expensas_purge.py`
- Environment variables:
  - `EXPENSAS_SPREADSHEET_ID`
  - `ENABLE_EXPENSAS_SHEET`
  - `GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON`

## Cloud Scheduler trigger
- Schedule: `0 2 25 * *` (25th of the month at 02:00)
- Timezone: `America/Argentina/Buenos_Aires`
- Target: Cloud Run Job execution

## Manual run (validation)
- Execute the job manually and confirm logs include the summary line:
  - scanned, deleted, kept, invalid, months
