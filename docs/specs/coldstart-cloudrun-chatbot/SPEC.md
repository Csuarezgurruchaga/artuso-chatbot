## Summary
Reduce Cloud Run cold start end-to-end latency for the chatbot (measured from the inbound message that wakes the instance until the chatbot response is received) from ~10s to ≤7s p95, with a preferred stretch outcome around ~5s if feasible, while keeping min instances at 0 and preserving functionality.

## Goals / Non-goals
**Goals**
- Reduce cold start p95 to ≤7s; aim for ~5s if achievable without added risk.
- Keep min instances = 0.
- Preserve functional behavior of the chatbot (outputs unchanged; latency variation acceptable).
- Avoid any increase in steady-state cost at zero traffic.

**Non-goals**
- No new services (e.g., Redis/Memorystore) or external dependencies.
- No warmup/ping strategy or scheduled keep-alive.
- No CPU "always on" setting.
- No new observability instrumentation (logs/traces/profiling) beyond existing platform logs.

## Constraints
- Runtime: Python (FastAPI).
- Cloud Run CPU always on: not permitted.
- Warmup logic: not permitted.
- Concurrency: keep current value (no changes).
- Cost increase: 0% (no additional steady-state cost at zero traffic).
- Allowed changes: Docker image optimization and Cloud Run configuration; functionality must remain unchanged.
- Current Cloud Run resources (known): CPU 1 / RAM 512MB.
- Traffic: moderate (requests every few minutes).

## Key Flows
1) **Cold start request flow**
   - Inbound message triggers instance start.
   - App initializes runtime and any module-level setup.
   - Request is handled and response is sent to the user.

2) **Warm request flow**
   - Instance already running.
   - Request handled and response returned.

## Data / Interfaces
- **Firestore**: opt-in/opt-out storage.
- **AWS SES**: email sending.
- **Google Sheets**: store payments and parameters.
- **Meta WhatsApp/Messenger**: inbound webhooks.
- **Cloud Run**: hosting and scaling.

## Edge cases & Failure modes
- Cold start exceeds request timeout; request retries may cause duplicate side effects.
- External dependency init or DNS/TLS handshake adds latency during cold start.
- VPC connector (if enabled) introduces additional startup latency.
- Large container image causes slow pull/start.
- Module-level imports or client initialization increase startup time.

## Observability
- No new instrumentation will be added.
- Use existing Cloud Run request logs/metrics for latency and cold start visibility.

## Security / Privacy
- No changes to data handling or external access; same secrets and credentials flow.
- Preserve existing security posture and access boundaries.

## Open Questions
1) **Deployment region(s)**: Is the service single-region or multi-region?
   - Consequence: regional startup time variance and image pull latency could differ.
   - Default if not decided: assume single-region for initial analysis.

2) **VPC connector usage**: Is a VPC connector enabled for egress?
   - Consequence: if enabled, connector setup can add cold start latency; tuning may be needed.
   - Default if not decided: assume no VPC connector.

3) **Startup hotspots**: Are there heavy imports or global initializations at startup?
   - Consequence: without knowing, optimizations may miss the primary contributor.
   - Default if not decided: perform code review to identify module-level work.

4) **Connections at startup**: Do Firestore/SES/Sheets clients connect during import/init?
   - Consequence: early network calls can dominate cold start time.
   - Default if not decided: assume some clients initialize at import and plan lazy init refactor.

5) **Scope of allowed changes (Cloud Run config vs. Docker image)**:
   - Potential conflict: “only Cloud Run config” vs. “allow image optimization”.
   - Consequence: if image changes are disallowed, optimization options shrink.
   - Default if not decided: allow image optimization as non-functional change.

6) **CPU/RAM tuning allowed**: Can CPU/RAM be adjusted beyond current 1 CPU / 512MB?
   - Consequence: CPU boost from more CPU could reduce cold start but changes cost.
   - Default if not decided: keep current CPU/RAM.

7) **Dependency init strategy**: Should clients be lazy-initialized on first use?
   - Consequence: may add slight latency to first call but improve cold start.
   - Default if not decided: prefer lazy init where it does not change outputs.

## Decision Log
- **Decision:** Target cold start p95 ≤7s; stretch ~5s if feasible.
  - **Rationale:** Current cold start ~10s; moderate improvement required without added infra.
  - **Risks / mitigations:** If 5s is unreachable, accept ≤7s with minimal changes.

- **Decision:** CPU always on is not permitted.
  - **Rationale:** Cost sensitivity and requirement to keep min instances = 0.
  - **Risks / mitigations:** Focus on image and init optimizations.

- **Decision:** Warmup/ping strategy is not permitted.
  - **Rationale:** Avoid additional logic and cost.
  - **Risks / mitigations:** Optimize startup path only.

- **Decision:** No new observability instrumentation.
  - **Rationale:** Change minimization.
  - **Risks / mitigations:** Use existing Cloud Run metrics/logs for validation.

- **Decision:** Concurrency remains unchanged.
  - **Rationale:** Avoid operational changes.
  - **Risks / mitigations:** Optimize per-request cold start latency.

- **Decision:** Docker image optimization is allowed.
  - **Rationale:** Non-functional change that can reduce cold start.
  - **Risks / mitigations:** Ensure image changes preserve runtime behavior.

## Changelog
- 2026-01-25 — Initial spec draft
  - reason: capture constraints, goals, and decisions for cold start reduction
  - impact: create PLAN/TASKS/ACCEPTANCE

## Glossary
- **Cold start**: Time from first request that starts a new instance until response is returned.
- **CPU always on**: Cloud Run setting that keeps CPU allocated when idle.
- **Concurrency**: Max simultaneous requests per instance in Cloud Run.
- **VPC connector**: Cloud Run networking option routing traffic through a VPC.

> The SPEC is the source of truth. If implementation deviates, update the SPEC + TASKS + ACCEPTANCE and record it in the Changelog.
