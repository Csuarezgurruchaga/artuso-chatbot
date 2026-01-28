# TASKS: Cloud Run image slimming

- [ ] Add `.dockerignore` excluding `.venv/`, caches, `.git/`, `docs/`, `tests/`, `.env`, and temp artifacts.
- [ ] Update `Dockerfile` runtime stage to use selective `COPY` instead of `COPY . .`.
- [ ] Confirm Cloud Build succeeds and compare image size and cold start metrics.

