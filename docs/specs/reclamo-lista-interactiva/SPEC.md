# Reclamo list interactive (tipo de reclamo)

## Summary
Replace interactive buttons with an interactive list whenever the chatbot asks for `tipo_servicio` (tipo de reclamo). Update the available options to: Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos, Otro reclamo.

## Context
- The current flow uses interactive buttons for selecting the type of reclamo.
- New reclamo categories are needed and the selection should be a list instead of buttons.

## Goals
- Use a WhatsApp interactive list for all prompts where the user selects the type of reclamo.
- Provide the new list of options in the exact order and labels provided.
- Map free-text user input to the closest option (synonyms).
- Keep existing prompt copy and update any option lists in messages to match the new options.

## Non-goals
- Changing the rest of the reclamo flow (campos, validations, emails).
- Introducing new dependencies or storage changes.
- Supporting additional reclamo categories beyond the specified list.

## Users and primary flows
- User starts a reclamo flow -> receives a list with the five options -> selection stored.
- User corrects the tipo de reclamo -> receives the same list -> selection stored.
- User types a synonym instead of selecting -> value is mapped to the correct option.

## Functional requirements
1. Replace the interactive buttons for `tipo_servicio` with an interactive list everywhere the type is requested:
   - Initial reclamo flow.
   - Corrections / re-asking for `tipo_servicio`.
2. List body text keeps existing copy (e.g., "¿Qué tipo de reclamo queres realizar?").
3. The list button text is **"Elegir opción"**.
4. The list options are exactly, in this order and with these labels:
   1) Destapación  
   2) Filtracion/Humedad  
   3) Pintura  
   4) Ruidos Molestos  
   5) Otro reclamo
5. The value saved in `tipo_servicio` is the exact label string selected.
6. When the user types free text, map synonyms to the options:
   - Destapación: matches "destap", "destapación".
   - Filtracion/Humedad: matches "filtracion", "filtración", "humedad".
   - Pintura: matches "pintura", "pintar".
   - Ruidos Molestos: matches "ruido", "ruidos", "molesto", "molestos".
   - Otro reclamo: matches "otro".
7. Any user-facing text that enumerates reclamo options must be updated to the new list.
8. If the interactive list cannot be sent, fallback to text with the updated options.

## Non-functional requirements
- Minimal, reviewable diffs.
- Preserve existing behavior outside of reclamo type selection.

## System design (high level)
- `ChatbotRules` sends a WhatsApp interactive list for `tipo_servicio`.
- `handle_interactive_button` consumes list replies by option ID and maps to the new labels.
- `_match_service_option` maps free-text synonyms to the new option labels.

## Interfaces
- Uses existing `send_interactive_list` in `services/meta_whatsapp_service.py`.

## Data model
- `tipo_servicio` continues to store a string, now one of the new labels.

## Observability
- Reuse existing logging for interactive messages and service selection.

## Testing strategy
- Manual: trigger reclamo flow and verify the interactive list, selected value, and fallback text.
- Unit: ensure synonym mapping returns the correct label for each option.

## Decisions and trade-offs
- **Decision:** Use interactive list for all `tipo_servicio` prompts.
  - **Rationale:** Consistent UX and supports 5 options.
- **Decision:** Store the exact label in `tipo_servicio`.
  - **Rationale:** Matches the UI and avoids extra mapping layers.
- **Decision:** Map free-text synonyms to options.
  - **Rationale:** Improves UX when users type instead of selecting.

## Open questions
- None.

## Glossary
- **Interactive list:** WhatsApp list message with a button that opens selectable rows.
