## Plan

### Phase 0 — Baseline and constraints validation
- Confirm current Cloud Run config (region, VPC connector, CPU/RAM, concurrency).
- Establish baseline cold start p95 using existing Cloud Run logs/metrics.

### Phase 1 — Image optimization
- Review Dockerfile for size and layer efficiency.
- Apply non-functional image optimizations (slim base, multi-stage, reduce build deps, cache-friendly ordering).

### Phase 2 — Startup path optimization
- Identify module-level work and heavy imports in app startup.
- Move safe initializations to lazy execution paths without changing outputs.
- Avoid any warmup logic or CPU always-on settings.

### Phase 3 — Cloud Run config tuning (within constraints)
- Evaluate startup CPU boost (if available) without increasing idle cost.
- Keep concurrency unchanged unless evidence shows no risk (default: no change).

### Phase 4 — Verification and rollout
- Validate cold start p95 against target using existing logs/metrics.
- Verify functional outputs remain unchanged.
- Document any residual cold start contributors and trade-offs.
