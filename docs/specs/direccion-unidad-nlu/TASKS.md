# TASKS — direccion-unidad-nlu

## Task 1 — Prompt + extractor NLU
- [ ] Agregar `NLU_DIRECCION_UNIDAD_PROMPT` en `templates/template.py`.
- [ ] Implementar `NLUService.extraer_direccion_unidad()` en `services/nlu_service.py`.
- [ ] Implementar `NLUService.construir_unidad_sugerida(parsed)` en `services/nlu_service.py`.
- [ ] Usar `OPENAI_NLU_MODEL` (default `gpt-4o-mini`) en las llamadas NLU.

## Task 2 — Integración en flujo dirección
- [ ] Agregar `ChatbotRules._parece_direccion_con_unidad(texto)` en `chatbot/rules.py`.
- [ ] Integrar en `_procesar_campo_secuencial()` para `direccion` y `direccion_servicio`.
- [ ] Mantener fallback a `_extraer_piso_depto_de_direccion()` si falla.

## Task 3 — Tests
- [ ] Crear `tests/test_address_unit_nlu.py` con asserts para trigger y normalización.
- [ ] Ejecutar `python tests/test_address_unit_nlu.py`.

