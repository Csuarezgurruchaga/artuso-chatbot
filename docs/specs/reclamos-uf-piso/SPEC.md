# Reclamos: piso/depto/UF separado en ubicación

## Summary
Add a dedicated `piso/depto/UF` step to the reclamo flow so it matches expensas: the location is captured separately from the unit, and the unit appears in summary and email.

## Context
- Expensas already captures `piso_depto` as a separate field.
- Reclamos currently store unit information inside `direccion_servicio`, so "UF 11" is not separated.

## Goals
- Ask for `piso/depto/UF` in reclamos after the ubicación step.
- Reuse the existing `piso_depto` field for reclamos.
- Auto-detect UF/piso/depto in ubicación, split it, and ask for confirmation.
- Show the unit in the WhatsApp summary and reclamo email.

## Non-goals
- Changing the expensas flow or data model.
- Changing the overall reclamo fields beyond adding the unit step.
- New storage or dependencies.

## Users and primary flows
- User reports a reclamo -> selects tipo -> provides ubicación -> provides piso/depto/UF -> provides detalle -> confirms.
- If the user includes UF in ubicación, the bot suggests it and asks confirmation.
- If a saved address is selected, both ubicación and piso/UF are autofilled and the unit step is skipped.

## Functional requirements
1. Insert a new step `piso_depto` for reclamos after `direccion_servicio` and before `detalle_servicio`.
2. Store the value in the existing `piso_depto` field (shared with expensas).
3. The new field is mandatory in reclamos.
4. Prompt text for the new step: **"¿Cuál es el piso/departamento/UF?"**
5. If the user writes ubicación including UF/piso/depto (e.g., "Av... UF 11"):
   - Split the unit from the address.
   - Store the base address in `direccion_servicio`.
   - Suggest the extracted unit and ask for confirmation before continuing.
6. The extractor must recognize `uf` as a unit keyword (in addition to piso/depto/dto).
7. If a saved address is selected for reclamos:
   - Autocomplete `direccion_servicio` and `piso_depto`.
   - Skip the unit step and continue to `detalle_servicio`.
8. Summary for reclamos includes a new line:
   - "🚪 *Piso/Departamento/UF:* <valor>"
9. Reclamo email includes the unit as a separate row.
10. Corrections menu for reclamos adds a specific option for `piso/depto/UF`.

## Non-functional requirements
- Minimal, reviewable diffs.
- Keep existing behavior outside the reclamo flow.

## System design (high level)
- ConversationManager adds `piso_depto` to the reclamo field order and validations.
- ChatbotRules parses UF/piso/depto from `direccion_servicio` using existing helpers and confirmation buttons.
- Email service includes `piso_depto` in reclamo emails.

## Interfaces
- No new external interfaces or environment variables.

## Data model
- Reuse `datos_temporales["piso_depto"]` for reclamos.

## Observability
- Reuse existing logs for field validation and interactive selections.

## Testing strategy
- Manual: run a reclamo flow and verify unit prompt, confirmation, summary, and email.
- Unit: ensure UF parsing and confirmation path for reclamos works with "UF 11".

## Decisions and trade-offs
- **Decision:** Insert the unit step after ubicación.
  - **Rationale:** Matches expensas and keeps flow natural.
- **Decision:** Reuse `piso_depto` for reclamos.
  - **Rationale:** No new schema; shared semantics across flows.
- **Decision:** Unit is mandatory in reclamos.
  - **Rationale:** Ensures precise location for service.
- **Decision:** Auto-split and confirm when UF/piso is detected in ubicación.
  - **Rationale:** Reduces friction while keeping accuracy.
- **Decision:** Autofill unit from saved addresses and skip the step.
  - **Rationale:** Faster flow for repeat users.

## Open questions
- None.

## Glossary
- **Unidad (UF/piso/depto):** Identifier inside the building used to locate the reclamo.
