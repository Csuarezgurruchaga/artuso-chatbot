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

## Rollout
- Deploy the chatbot revision that includes the session checkpoint changes.
- Configure:
  - `SESSION_CHECKPOINT_CLEANUP_TOKEN`
  - `SESSION_CHECKPOINT_CLEANUP_BATCH_SIZE` (optional, default `100`)
- Create a daily Cloud Scheduler HTTP POST job against `/session-checkpoints/cleanup`.
- After deploy, validate:
  - cold-start resume for a `CONFIRMANDO_MEDIA` checkpoint
  - cleanup endpoint with a valid token
  - logs for `checkpoint_save`, `checkpoint_hydrated`, `message_deduped`, `checkpoint_cleanup_run`

## Rollback
- Disable the Cloud Scheduler job for `/session-checkpoints/cleanup`.
- Roll back the Cloud Run service to the last revision before `chatbot-session-resume`.
- Re-run a webhook smoke check to confirm the bot returns to RAM-only behavior.

## Verification evidence
- Automated suite used for final closure:
  - `python3 -m pytest -q tests/test_media_confirm_checkpoint.py tests/test_session_resume_manager.py tests/test_session_expiration.py tests/test_session_cleanup.py tests/test_session_dedupe.py tests/test_session_delete_on_finalize.py tests/test_session_checkpoint_service.py tests/test_session_observability.py`
- Direct local walkthrough used for closure:
  - rehydrate `CONFIRMANDO_MEDIA` from an in-memory checkpoint store after clearing RAM
  - call `POST /session-checkpoints/cleanup` with a valid token and confirm `200` + expected JSON body
