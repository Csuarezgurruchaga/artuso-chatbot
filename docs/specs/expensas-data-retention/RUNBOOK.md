# Runbook: Expensas sheet rotation

## Cloud Run Job setup
- Create a Cloud Run Job using the same container image as the service.
- Command/args: `python jobs/expensas_purge.py`
- Environment variables:
  - `EXPENSAS_SPREADSHEET_ID`
  - `ENABLE_EXPENSAS_SHEET`
  - `GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON`

## Cloud Scheduler trigger
- Schedule: `5 0 1 * *` (1st of the month at 00:05)
- Timezone: `America/Argentina/Buenos_Aires`
- Target: Cloud Run Job execution

## Manual run (validation)
- Execute the job manually and confirm logs include the summary line:
  - moved, cleared, current_tab, previous_tab, current_label, previous_label
