# Plan: Contact info detection (static contact block)

## Phase 1: Company profile
1. Add `contact_message` to the `administracion-artuso` profile in `config/company_profiles.py` with the exact contact block.
2. Keep existing fields for backwards compatibility; `contact_message` becomes the preferred response.

## Phase 2: Detection and routing
3. Update `services/nlu_service.py`:
   - Replace/extend `detectar_consulta_contacto` with the new regex-based rules and exclusion logic.
   - Add/adjust patterns for phone/WhatsApp/email/call verbs and adjacency rules.
   - Ensure the exclusion list is applied to "numero de X" patterns only.
   - Update `generar_respuesta_contacto` to return `contact_message` (fallback to `get_company_info_text()`).
4. Update `chatbot/rules.py`:
   - Check `detectar_solicitud_humano` before `detectar_consulta_contacto`.
   - Keep the flow-continuation line when in active states.

## Phase 3: Tests
5. Add unit tests covering:
   - Positive contact detection: telefono, numero de contacto, whatsapp, email, "quiero llamar".
   - Negative detection: "numero de reclamo", "numero de cuenta", etc.
   - "contacto" alone requires channel; "informacion de contacto" triggers.
   - "comunicarme" alone -> handoff.
   - Human intent has priority over contact.

## Phase 4: Manual verification
6. Manually validate with sample WhatsApp messages for contact and human requests.
