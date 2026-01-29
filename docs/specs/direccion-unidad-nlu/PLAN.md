# PLAN — NLU para separar Dirección vs Unidad (expensas)

1) Agregar prompt específico de extracción dirección/unidad.
2) Implementar extractor en `services/nlu_service.py` con `OPENAI_NLU_MODEL`.
3) Integrar en `chatbot/rules.py` con trigger heurístico y fallback.
4) Agregar script de tests (sin llamadas a OpenAI).
5) Ejecutar tests relevantes y reportar resultados.

