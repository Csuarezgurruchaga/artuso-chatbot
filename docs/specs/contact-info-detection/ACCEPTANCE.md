# Acceptance criteria: Contact info detection (static contact block)

## Functional
1. Contact detection uses regex-only rules; no LLM is used for detection or response.
2. "informacion de contacto" triggers the contact response.
3. Phone keywords (telefono/tel/celular/cel/movil) and call verbs ("llamar") trigger the contact response.
4. WhatsApp keywords (whatsapp/wsp/wa/wpp) trigger the contact response.
5. Email keywords (email/mail/correo) trigger the contact response.
6. "contacto" alone only triggers when a channel keyword is present.
7. "comunicarme" without the email/numero adjacency rule triggers handoff.
8. Explicit human requests (humano/agente/persona) trigger handoff and take priority over contact.
9. "numero de X" where X is in the exclusion list does not trigger contact.
10. Contact response returns the exact `contact_message` block from the active company profile.
11. If `contact_message` is missing, fallback response is `get_company_info_text()`.
12. Contact interception applies in any state; if not in INICIO/ESPERANDO_OPCION, append "💬 *Ahora sigamos con tu consulta anterior...*".

## Tests
13. Unit tests cover positive/negative detection, exclusions, and human-vs-contact priority.
