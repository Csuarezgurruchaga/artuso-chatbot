# ACCEPTANCE: Cloud Run image slimming

- [ ] The Docker build context excludes `.venv/` and common Python caches via `.dockerignore`.
- [ ] The runtime image does not include `docs/`, `tests/`, `.git/`, or local dev artifacts.
- [ ] Cloud Build / CI build succeeds without changing Python dependencies.
- [ ] Cloud Run revision deploys and serves requests successfully.
- [ ] Image size is reduced versus baseline (measured in registry / Cloud Build output).

