# Plan: Reclamos with piso/depto/UF step

1. Update `ConversationManager` field order for reclamos to include `piso_depto` between `direccion_servicio` and `detalle_servicio`.
2. Add reclamo validation for `piso_depto` and update error messaging.
3. Update reclamo prompts, summaries, and correction menus to include the unit step.
4. Extend `ChatbotRules` to parse UF/piso/depto from `direccion_servicio`:
   - Split and store base address.
   - Suggest extracted unit and ask for confirmation.
5. Update address selection to set both `direccion_servicio` and `piso_depto` for reclamos and skip the unit step.
6. Update `email_service` to include the unit in reclamo emails.
7. Add/adjust unit tests for UF parsing behavior.
8. Manually verify the reclamo flow end-to-end.
