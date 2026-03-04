# AGENTS.md

Guidelines for Codex sessions in this repository.

## Project overview
- FastAPI chatbot for Artuso that handles pagos de expensas y reclamos.
- Hybrid flow: rule-based conversation + NLU extraction.
- Integrations: Meta WhatsApp/Messenger, email (SES), Google Sheets, and handoff to human agents.

## Key paths
- `main.py`: FastAPI entrypoint + webhook handlers.
- `chatbot/`: conversation models, state machine, and rules.
- `services/`: external integrations (Meta APIs, NLU, sheets, email, handoff, metrics).
- `config/`: company profiles and contact info.
- `templates/`: prompts for LLM extraction.
- `tests/`: standalone Python scripts (no pytest harness).

## Workflow expectations
- For non-trivial design or architecture work, use the spec workflow first and do not code until `SPEC.md` has no Open Questions.
- Prefer minimal, reviewable diffs; avoid unrelated refactors.
- Ask before adding dependencies, changing public APIs, or altering data models/schemas.
- Avoid assumptions; ask when ambiguity exists.

## Local setup
- Python project; use a per-project virtual environment (`.venv`).
- Install: `pip install -r requirements.txt`
- Run: `python main.py` or `uvicorn main:app --host 0.0.0.0 --port 8080 --reload`
- Configure environment in `.env` (see `CLAUDE.md` for variable list).

## Testing
- Tests are runnable scripts. Execute the relevant ones under `tests/`, e.g.:
  - `python tests/test_chatbot.py`
  - `python tests/test_llm_first.py`
  - `python tests/test_contact_info.py`
- If tests/linters exist, run and report results; otherwise state that clearly.

## Work log
- date: 2026-02-12
- context: `services/expensas_sheet_service.py`, `tests/test_expensas_uf_parser.py`
- problem: Al detectar `UF` desde `DPTO`, se copiaba a la columna `UF` pero se mantenía también en `DPTO`, dejando datos duplicados en la fila de expensas.
- solution: Se agregó limpieza de `UF` en `DPTO` (`_strip_uf_from_dpto`) y se aplica en `append_pago` cuando se autocompleta `UF`, preservando el resto del texto útil en `DPTO`.
- proof: `pytest -q tests/test_expensas_uf_parser.py` y `pytest -q tests/test_expensas_address_map.py`

- date: 2026-02-12
- context: `services/expensas_sheet_service.py`, `tests/test_expensas_comprobante_links.py`
- problem: Cuando llegaban 2+ comprobantes, se generaba una fórmula concatenada con múltiples `HYPERLINK(...)` en una sola celda; en Sheets el texto podía perder clicabilidad (sin color azul/atajo de click).
- solution: Se mantuvo fórmula `HYPERLINK` solo para 1 comprobante y, para múltiples, se evita la fórmula concatenada y se conservan los URLs crudos (uno por línea) ya escritos al append, que quedan navegables.
- proof: `pytest -q tests/test_expensas_comprobante_links.py` y `pytest -q tests/test_expensas_address_map.py tests/test_expensas_uf_parser.py`

- date: 2026-02-12
- context: `services/expensas_sheet_service.py`, `tests/test_expensas_comprobante_links.py`
- problem: En celdas de `COMPROBANTE` con múltiples archivos, se necesitaban etiquetas clickeables por archivo (no solo URLs crudos ni fórmula concatenada inestable).
- solution: Para múltiples comprobantes se implementó escritura de rich text en Sheets con labels `Ver comprobante 1`, `Ver comprobante 2`, cada uno con su link; para un único comprobante se mantiene `HYPERLINK` clásico.
- proof: `pytest -q tests/test_expensas_comprobante_links.py` y `pytest -q tests/test_expensas_address_map.py tests/test_expensas_uf_parser.py`

- date: 2026-02-12
- context: `services/expensas_sheet_service.py`, `tests/test_expensas_uf_parser.py`
- problem: El parser de UF no interpretaba `UNIDAD <n>` como unidad funcional, por lo que casos como `UNIDAD 49, DEPTO 319` no llenaban columna `UF` y dejaban todo en `DPTO`.
- solution: Se amplió la detección/limpieza de UF para aceptar `UF`, `U.F.`, `UNIDAD FUNCIONAL` y `UNIDAD`, manteniendo el número y removiendo esa porción de `DPTO` cuando corresponde.
- proof: `pytest -q tests/test_expensas_uf_parser.py` y `pytest -q tests/test_expensas_address_map.py`

- date: 2026-02-12
- context: `chatbot/rules.py`, `services/nlu_service.py`, `templates/template.py`, `tests/test_expensas_ed_combined_llm.py`
- problem: En ED (`campo_actual == "direccion"` de expensas), inputs “todo en uno” no se resolvían con una extracción combinada única ni autocompletaban campos validados; además no había cobertura de repro para casos reales complejos.
- solution: Se agregó heurística exclusiva de ED para disparo “todo en uno”, nuevo llamado LLM combinado único (`extraer_expensas_ed_combinado`) con prompt dedicado, autocompletado de campos vacíos y validados (`direccion`, `piso_depto`, `fecha_pago`, `monto`) con fallback seguro al flujo previo, y resumen UX cuando se completan 2+ campos.
- notes: No se usó feature flag ni se extendió el comportamiento a otros pasos.
- proof: `.venv/bin/pytest -q tests/test_expensas_ed_combined_llm.py` y `.venv/bin/pytest -q tests/test_expensas_ed_combined_llm.py tests/test_expensas_comprobante_links.py tests/test_expensas_uf_parser.py tests/test_expensas_address_map.py tests/test_address_unit_nlu.py`

- date: 2026-02-12
- context: `chatbot/rules.py`, `services/nlu_service.py`, `templates/template.py`, `tests/test_expensas_ed_combined_llm.py`, `tests/test_welcome_sticker_fallback.py`
- problem: En el paso `direccion` de expensas ED se estaban autocompletando `fecha_pago` y `monto` desde extracción LLM combinada (fuera de alcance del paso); además, cuando fallaba `WHATSAPP_STICKER_MEDIA_ID` no había retry por URL y se perdía el sticker inicial.
- solution: Se acotó el flujo ED para usar extracción combinada solo en `direccion/piso_depto` (+ flag de mención de comprobante) sin autocompletar `fecha_pago/monto`; se actualizó prompt + sanitización en NLU a ese alcance. En saludo inicial, se agregó fallback automático a `sticker_url` cuando falla envío por `sticker_id`.
- proof: `python3 -m pytest -q tests/test_expensas_ed_combined_llm.py tests/test_expensas_uf_parser.py tests/test_expensas_address_map.py tests/test_expensas_comprobante_links.py tests/test_welcome_sticker_fallback.py`

- date: 2026-02-12
- context: `chatbot/rules.py`, `tests/test_welcome_sticker_fallback.py`
- problem: Se introdujo un fallback automático `sticker_id -> sticker_url` en el saludo inicial, pero para operación se requiere comportamiento estricto (sin fallback) para detectar/configurar rápido IDs inválidos.
- solution: Se removió el retry por URL cuando `WHATSAPP_STICKER_MEDIA_ID` está presente; el flujo vuelve a enviar únicamente por `sticker_id` en ese caso. Se ajustó el test para validar que no haya segundo intento.
- proof: `python3 -m pytest -q tests/test_welcome_sticker_fallback.py`

- date: 2026-02-12
- context: `services/clients_sheet_service.py`, `services/meta_whatsapp_service.py`
- problem: Latencia evitable en avance entre preguntas por lecturas repetidas de Sheet `CLIENTES` (incluyendo escaneo completo de hoja) y logging excesivo en `send_text_message` (serialización de payload completo en INFO).
- solution: Se agregó cache in-memory por teléfono para direcciones (`CLIENTS_DIRECCIONES_CACHE_TTL_SECONDS`, `CLIENTS_DIRECCIONES_CACHE_MAX_ITEMS`), se redujo el fetch de Sheets a rango `A:C` en `_find_row`, y se hizo logging liviano en `send_text_message` moviendo detalles/payload a DEBUG.
- proof: `python3 -m pytest -q tests/test_welcome_sticker_fallback.py tests/test_delete_saved_address.py tests/test_expensas_ed_combined_llm.py` y `python3 -m pytest -q tests/test_meta_webhook.py::test_meta_whatsapp_service_send_text`

- date: 2026-02-12
- context: `chatbot/rules.py`, `tests/test_welcome_sticker_fallback.py`
- problem: El flujo de sticker en saludo aún priorizaba `WHATSAPP_STICKER_MEDIA_ID` (storage de Meta), lo que mantiene riesgo de expiración periódica de media IDs.
- solution: Se migró a modo URL-only para sticker: siempre se envía `sticker.link` usando `WHATSAPP_STICKER_URL` (o URL por defecto). `WHATSAPP_STICKER_MEDIA_ID` queda deprecada e ignorada con warning explícito.
- proof: `python3 -m pytest -q tests/test_welcome_sticker_fallback.py`

- date: 2026-02-12
- context: GCS (`artuso-assets-prod`) y asset `assets/artu.webp`
- problem: Se necesitaba evitar rotación manual de `sticker_id` (media expirable) para WhatsApp y servir un sticker estable por URL pública.
- solution: Se creó bucket dedicado de assets `gs://artuso-assets-prod` en `southamerica-east1`, se habilitó lectura pública de objetos (`roles/storage.objectViewer` a `allUsers`) y se subió `artuso/stickers/bot-v1.webp`.
- proof: `gcloud storage ls gs://artuso-assets-prod/artuso/stickers/` + `gcloud storage objects describe gs://artuso-assets-prod/artuso/stickers/bot-v1.webp` + `curl -I https://storage.googleapis.com/artuso-assets-prod/artuso/stickers/bot-v1.webp`

- date: 2026-02-12
- context: `chatbot/rules.py`, `tests/test_welcome_sticker_fallback.py`
- problem: El link de sticker estaba hardcodeado a GitHub raw; para operar con assets en GCS/CDN sin depender de `media_id` se necesitaba override por entorno.
- solution: Se agregó `WHATSAPP_STICKER_URL` como override de URL del sticker en saludo. Si la variable no está, se mantiene fallback al comportamiento anterior de URL por GitHub.
- proof: `python3 -m pytest -q tests/test_welcome_sticker_fallback.py`
