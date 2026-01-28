# SPEC: Cloud Run image slimming (FastAPI chatbot)

## Summary

Reduce Cloud Run cold start by reducing container image size and avoiding copying unnecessary files into the image. Keep changes minimal and limited to Docker packaging.

## Goals

- Reduce container image size by excluding non-runtime files from the Docker build context and final image.
- Reduce Cloud Run cold start time caused by image pull/expand.
- Keep a minimal, reviewable diff (no dependency changes, no API changes).

## Non-goals

- Refactor application code to change runtime behavior, APIs, or data models.
- Change Python dependencies (requirements) or add new dependencies.
- Switch base image family (distroless/alpine) in this iteration.

## Current state

- `Dockerfile` uses `COPY . .` in the runtime stage.
- There is no `.dockerignore`.
- In the current working tree, `.venv/` exists and is large; without `.dockerignore` it can be included in Docker build context and image.

## Constraints

- Build/push runs via Cloud Build / CI.
- Optimize both: image size and app init/runtime (priority on init/runtime overall), but this spec restricts changes to Docker packaging.
- Do not add dependencies.
- Runtime image should contain only what is needed to serve the API (exclude `tests/`, `docs/`, `.git/`, etc.).

## Proposal

1) Add `.dockerignore` to exclude:
- Local virtualenv and caches: `.venv/`, `__pycache__/`, `*.pyc`, etc.
- Repo metadata and non-runtime folders: `.git/`, `docs/`, `tests/`, etc.
- Local artifacts: `.env`, logs, temp folders.

2) Replace `COPY . .` with selective `COPY` of only runtime-needed paths:
- `main.py`
- `chatbot/`, `services/`, `config/`, `templates/`, `assets/`, `jobs/`
- Keep `requirements.txt` already used in build stage (optional to copy in runtime stage; harmless either way).

## Alternatives considered

- Keep `COPY . .` and rely only on `.dockerignore`: simpler, but still risks accidentally copying new non-runtime files later.
- Switch to distroless/alpine: potentially smaller, but higher risk (glibc/musl issues, debugging friction).
- Refactor imports/lazy-init in app code: can improve init time but out-of-scope for this spec iteration.

## Rollout / validation

- Build via Cloud Build / CI and compare:
  - resulting image size in registry
  - Cloud Run revision cold start time (from logs/metrics)
- Ensure service still starts and responds to health traffic (standard Cloud Run request flow).

## Open questions

None.

