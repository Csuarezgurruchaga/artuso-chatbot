# Runbook: Session checkpoint cleanup

## Endpoint
- Route: `POST /session-checkpoints/cleanup`
- Auth: form field `token` must match `SESSION_CHECKPOINT_CLEANUP_TOKEN`
- Batch size: `SESSION_CHECKPOINT_CLEANUP_BATCH_SIZE` (default `100`)

## Cloud Scheduler trigger
- Frequency: daily
- Suggested schedule: `5 3 * * *`
- Timezone: `America/Argentina/Buenos_Aires`
- Target: authenticated HTTP POST to the chatbot service
- Form body:
  - `token=<SESSION_CHECKPOINT_CLEANUP_TOKEN>`

## Manual validation
- Call the endpoint with a valid token in a non-production environment.
- Confirm the JSON response includes `deleted`, `deleted_doc_ids` and `batch_limit`.
- Confirm logs include `checkpoint_cleanup_delete` for each deleted checkpoint and one `checkpoint_cleanup_run` summary line.
