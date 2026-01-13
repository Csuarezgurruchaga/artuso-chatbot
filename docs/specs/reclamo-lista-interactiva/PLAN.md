# Plan: Reclamo list interactive (tipo de reclamo)

1. Update `SERVICE_TYPE_OPTIONS` with the new option labels and IDs.
2. Replace `send_service_type_buttons` with a list-based sender using `send_interactive_list`.
3. Update all prompt/copy strings that list reclamo options to reflect the new list.
4. Update `_match_service_option` to map free-text synonyms to the new options.
5. Update interactive handling so list replies map to the new option IDs/labels.
6. Update any prompt templates/examples that enumerate reclamo options to the new list.
7. Validate manually with a WhatsApp test number:
   - Initial reclamo flow shows the list.
   - Correction flow shows the list.
   - Free-text synonyms map to the correct option.
