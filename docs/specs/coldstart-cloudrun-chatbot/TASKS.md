# TASKS

## Phase 0 — Setup / scaffolding
- T0.1 Capture current Cloud Run config and baseline metrics
  - Goal: Record current region/VPC/CPU/RAM/concurrency and baseline cold start p95.
  - Inputs: Cloud Run settings, existing logs/metrics.
  - Outputs: Baseline note with current config + p95 estimate.
  - Steps:
    - Retrieve Cloud Run settings for the service.
    - Inspect request logs/metrics for cold start latency.
  - Done condition: Baseline documented with timestamp and configuration.
  - Depends on: []
  - Risks: Limited visibility without added instrumentation.
  - Test/Verification: Compare baseline p95 to reported ~10s.

## Phase 1 — Core logic
- T1.1 Audit Dockerfile and image size
  - Goal: Identify size and layer optimizations.
  - Inputs: Dockerfile, current image size.
  - Outputs: List of safe image optimizations.
  - Steps:
    - Review base image and build layers.
    - Identify removable build dependencies and cache breaks.
  - Done condition: Optimization plan documented.
  - Depends on: [T0.1]
  - Risks: None if only analysis.
  - Test/Verification: N/A (analysis only).

- T1.2 Implement Docker image optimizations
  - Goal: Reduce image size and startup time without behavior change.
  - Inputs: Optimization plan from T1.1.
  - Outputs: Updated Dockerfile and smaller image.
  - Steps:
    - Apply multi-stage build or slim base image.
    - Reorder layers for cache efficiency.
  - Done condition: Image size reduced and build succeeds.
  - Depends on: [T1.1]
  - Risks: Missing runtime deps if pruned incorrectly.
  - Test/Verification: Build and run container locally; smoke request.

- T1.3 Identify startup hotspots in Python app
  - Goal: Find heavy imports or module-level initialization.
  - Inputs: App code, dependency clients.
  - Outputs: List of candidates for lazy init.
  - Steps:
    - Review imports and global objects.
    - Flag any network calls or heavy setup at import time.
  - Done condition: Candidate list documented.
  - Depends on: [T0.1]
  - Risks: Missing hidden side effects.
  - Test/Verification: N/A (analysis only).

- T1.4 Apply lazy initialization where safe
  - Goal: Reduce cold start by deferring heavy init.
  - Inputs: Candidate list from T1.3.
  - Outputs: Code changes to move init into first-use paths.
  - Steps:
    - Refactor client creation to on-demand functions.
    - Ensure outputs remain identical.
  - Done condition: Cold start path reduced; functionality unchanged.
  - Depends on: [T1.3]
  - Risks: Slight added latency on first-use of a dependency.
  - Test/Verification: Functional checks and cold start measurement.

## Phase 2 — Integration
- T2.1 Evaluate Cloud Run startup CPU boost (if available)
  - Goal: Reduce cold start without changing min instances or idle cost.
  - Inputs: Cloud Run settings, platform capabilities.
  - Outputs: Decision to enable/skip CPU boost.
  - Steps:
    - Check if startup CPU boost is available for the service.
    - Validate that it does not increase idle cost.
  - Done condition: Config decision recorded and applied if approved.
  - Depends on: [T0.1]
  - Risks: Misconfiguration or cost impact if misunderstood.
  - Test/Verification: Compare cold start before/after.

## Phase 3 — Observability / hardening
- T3.1 Validate cold start improvements using existing logs
  - Goal: Confirm p95 improvement within constraints.
  - Inputs: Cloud Run logs/metrics post-change.
  - Outputs: Before/after comparison.
  - Steps:
    - Measure cold start latency post-deploy.
    - Compare against baseline.
  - Done condition: Target met (≤7s) or documented gap.
  - Depends on: [T1.2, T1.4, T2.1]
  - Risks: Insufficient traffic to measure reliably.
  - Test/Verification: Use multiple cold starts where possible.

## Phase 4 — Release / rollout
- T4.1 Rollout and rollback plan
  - Goal: Ensure safe deployment and recovery.
  - Inputs: Changes from earlier tasks.
  - Outputs: Release notes and rollback steps.
  - Steps:
    - Deploy changes to Cloud Run.
    - Document rollback to previous image/config.
  - Done condition: Rollout completed with rollback documented.
  - Depends on: [T3.1]
  - Risks: Regression in cold start or behavior.
  - Test/Verification: Post-deploy smoke test.

## Chunking guidance
- Suggested implementation chunk size: 1–2 tasks per chunk
- Review cadence: after each chunk, verify acceptance criteria impacted by those tasks
- Stop points: safe to stop here after Phase 1, Phase 2, Phase 3

## Execution status
- Status: NOT_STARTED
- Current task: T0.1
- Completed tasks: (optional)
- Last updated: 2026-01-25
