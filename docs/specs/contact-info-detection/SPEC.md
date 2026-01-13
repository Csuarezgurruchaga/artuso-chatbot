# Contact info detection (static contact block)

## Summary
Detect contact requests (telefono/WhatsApp/email/numero de contacto) using regex-only rules and respond with a fixed contact block from the active company profile. Explicit human requests trigger handoff.

## Context
- Contact requests currently rely on broad regex plus an LLM response.
- The desired behavior is a deterministic, fixed response block for contact info.
- Precision is prioritized to avoid false positives.

## Goals
- Detect contact requests for phone/WhatsApp/email/contact info with high precision.
- Reply with a static contact block defined per company.
- If the user explicitly asks for a human, trigger handoff first.
- Intercept contact requests in any conversation state and preserve flow continuity.

## Non-goals
- Handling address/location queries as contact requests.
- LLM-based detection or response.
- New metrics or logging changes.

## Users and primary flows
- User asks for contact info/phone/WhatsApp/email -> receive full contact block.
- User asks to speak with a human -> handoff.
- If user was in an active flow, append a short continuation line.

## Functional requirements
1. Detection is regex-only with normalization (lowercase + remove accents).
2. Contact triggers include:
   - The phrase "informacion de contacto" (accent-insensitive).
   - Phone channel keywords: telefono, tel, celular, cel, movil.
   - Call verbs without explicit phone keywords (e.g., "quiero llamar").
   - WhatsApp keywords: whatsapp, wsp, wa, wpp.
   - Email keywords: email, mail, correo.
   - "contacto" or "comunicarme" only when adjacent to email/numero synonyms (e.g., "numero de contacto", "email de contacto", "numero para comunicarme").
3. The word "contacto" alone does not trigger unless a channel keyword is present.
4. Exclusion rule: if the message contains a "numero de X" pattern where X is in the exclusion list, do not trigger contact.
   - Numero synonyms: numero, nro, nro., n°, nº, #, num.
   - Exclusion list: cuenta, factura, reclamo, seguimiento, unidad, depto, dto, piso, contrato, cliente, servicio, pedido, tramite, referencia, comprobante, recibo, expensa, expensas, pago, cbu, dni, cuit, cuil.
   - Exclusion applies only to "numero de X" patterns.
5. Priority: explicit human requests (existing humano/agente/persona patterns) trigger handoff before contact handling.
6. Special case: if "comunicarme" appears without the email/numero adjacency rule, trigger handoff.
7. Response is always the exact `contact_message` string from the active company profile.
8. No LLM is used for contact response generation.
9. If `contact_message` is missing, fallback to `get_company_info_text()`.
10. Contact interception works in any state; if not in INICIO/ESPERANDO_OPCION, append: "💬 *Ahora sigamos con tu consulta anterior...*".

## Non-functional requirements
- Deterministic behavior and low latency.
- High precision over coverage.

## System design (high level)
- `chatbot/rules.py` checks `detectar_solicitud_humano` before `detectar_consulta_contacto`.
- `services/nlu_service.py` implements the regex-only detection rules and static response.
- `config/company_profiles.py` provides a per-company `contact_message`.

## Interfaces
- Company profile adds:
  - `contact_message`: static contact block string for the company.

## Data model
- No new persistent data models.

## Observability
- No new metrics or logs beyond existing ones.

## Testing strategy
- Unit tests for contact detection (positive/negative), exclusion patterns, and human-vs-contact priority.

## Decisions and trade-offs
- **Decision:** Regex-only detection.
  - **Rationale:** Deterministic and low-latency with high precision.
- **Decision:** Static `contact_message` per company.
  - **Rationale:** Exact wording control and easy replication across companies.
- **Decision:** Human request has priority over contact.
  - **Rationale:** Aligns with explicit user intent for a person.
- **Decision:** Exclusion list for "numero de X".
  - **Rationale:** Reduces false positives in administrative contexts.
- **Decision:** Intercept in any state and append continuation line.
  - **Rationale:** Immediate answer without breaking ongoing flows.

## Contact message (Administracion Artuso)
Gracias por comunicarte con Administración Artuso.
Podés contactarnos por los siguientes canales:

📞 Teléfonos
4953-3018 / 4953-0577
🕘 Lunes a viernes de 11:00 a 13:00 y de 14:00 a 16:00

📱 WhatsApp
11-5348-8741
🕘 Lunes a viernes de 11:00 a 16:00

✉️ Correo electrónico
• Para asuntos administrativos o reclamos: recepcion.adm.artuso@gmail.com
• Para temas relacionados con pago de expensas: artusoexpensas2@gmail.com

## Open questions
- None.

## Glossary
- **Contact block:** Static message containing all contact channels and hours.
- **Handoff:** Transfer to a human agent.
