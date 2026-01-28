# PLAN: Cloud Run image slimming

1) Add `.dockerignore` to shrink build context and avoid copying local artifacts.
2) Update `Dockerfile` to copy only runtime-required files/folders.
3) Validate via Cloud Build logs and Cloud Run cold start metrics.

