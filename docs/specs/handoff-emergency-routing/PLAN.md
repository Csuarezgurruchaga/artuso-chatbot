# Plan: handoff emergency routing

## Phase 1: Discovery and setup
- Locate the current handoff notification routing logic.
- Identify all references to `AGENT_WHATSAPP_NUMBER`.
- Note tests that cover handoff activation.

## Phase 2: Implementation
- Introduce `HANDOFF_WHATSAPP_NUMBER` for standard handoffs.
- Add `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` and routing based on `TipoConsulta=EMERGENCIA`.
- Implement fallback to standard number if emergency number is missing.
- Keep existing template name/lang and message content.

## Phase 3: Tests
- Add/adjust unit tests for emergency vs standard routing.
- Cover fallback when emergency env var is missing.

## Phase 4: Documentation and rollout
- Update any env var documentation in repo (if present).
- Deploy with new env vars.
- Run smoke tests for emergency and standard handoffs.
