# Opt-in/opt-out para conversaciones iniciadas por template

## Summary
Implementar opt-in obligatorio antes de iniciar conversaciones por template en WhatsApp y Messenger, con opt-out y auditoria. Validacion en runtime por Firestore/Datastore (sin cache) y registro en GCS (bucket nuevo).

## Context
- Meta exige opt-in para iniciar conversaciones por template.
- Cloud Run min instances=0 impide cache en memoria.
- El handoff interno envia templates al numero de agente.

## Goals
- Bloquear envio de templates si el numero no tiene opt-in aceptado.
- Solicitar opt-in via mensaje de texto (SI/NO) mediante comando oculto /optin para numeros internos.
- Registrar consentimiento (identificador, texto mostrado, respuesta, timestamp) en GCS.
- Ofrecer opt-out con BAJA/STOP y re-suscripcion via ALTA (requiere nuevo SI).
- Mensajes en espanol informal.

## Non-goals
- Botones interactivos de opt-in.
- Cambiar flujos que no usan templates.
- Introducir cache en memoria.
- Usar Google Sheets para runtime o auditoria.

## Functional requirements
1. El opt-in aplica a conversaciones iniciadas por template en WhatsApp y Messenger.
2. El opt-in se solicita por texto; respuestas validas solo SI o NO cuando el estado esta pendiente.
3. El opt-in se dispara con el comando oculto `/optin` enviado desde un numero de agente interno; responde al mismo numero.
4. Para enviar un template a un numero, debe existir opt-in aceptado en Firestore/Datastore; caso contrario se bloquea el envio.
5. La verificacion de opt-in es por canal (WhatsApp/Messenger) y usa identificador telefono o PSID.
6. Source of truth de runtime: Firestore/Datastore; sin cache local.
7. En cada evento (opt-in aceptado/rechazado, opt-out) se registra auditoria en GCS.
8. Campos de auditoria: identificador, canal, texto mostrado, respuesta, timestamp ISO-8601 UTC.
9. Opt-out: palabras clave `BAJA` o `STOP` desde numeros con opt-in aceptado.
10. ALTA reenvia el opt-in y requiere SI para reactivar.
11. Al aceptar SI, enviar mensaje de agradecimiento con instrucciones de opt-out.
12. Al responder NO, enviar confirmacion de rechazo con instrucciones para ALTA.
13. Para Messenger, almacenar PSID + canal en auditoria y Firestore.

## Copy (texto base)
Opt-in prompt:

Este numero sera utilizado para recibir comunicaciones laborales de soporte y atencion de parte de {empresa}.
Aceptas recibir estos mensajes?
Responde SI para aceptar o NO para rechazar.

Opt-in accepted ack (opt-out info):

Gracias por aceptar. A partir de ahora vas a recibir mensajes de soporte y atencion de {empresa}.
Si en cualquier momento queres dejar de recibirlos, responde BAJA o STOP.
Si fue un error, escribi ALTA y te enviaremos nuevamente el consentimiento.

Opt-in declined ack:

Listo, no vas a recibir mensajes de {empresa}.
Si cambias de idea, escribi ALTA para volver a aceptar.

Opt-out confirmation:

Listo, no vas a recibir mas mensajes de {empresa}.
Si queres volver, escribi ALTA y te enviaremos el consentimiento.

## Data model
- Firestore collection: `optins` (configurable).
- Document id: `{channel}:{identifier}` (ej: `whatsapp:+549...`, `messenger:{psid}`).
- Fields (runtime):
  - status: `accepted` | `declined` | `opted_out` | `pending`
  - prompt_text
  - response
  - updated_at (ISO-8601 UTC)
- Audit storage:
  - GCS bucket nuevo `optin-audit-...` (configurable), objeto por evento (`optin/YYYY-MM-DD/{timestamp}_{identifier}.json`).

## Non-functional requirements
- Bloqueo estricto: si Firestore falla, no enviar templates.
- Latencia baja por uso de lectura por clave en Firestore.
- Auditoria durable en GCS (no se consulta en runtime).

## Decisions and trade-offs
- **Decision:** Usar Firestore/Datastore como fuente autoritativa de opt-in.
  - **Rationale:** Baja latencia, serverless y compatible con Cloud Run min=0 sin cache.
  - **Rejected alternatives:** Sheets para runtime (latencia y cuotas), GCS como lookup (no KV).
- **Decision:** Guardar auditoria en GCS (bucket nuevo); no usar Sheets.
  - **Rationale:** Archivo durable sin afectar la latencia del runtime.
- **Decision:** Opt-in por texto SI/NO con comando `/optin`.
  - **Rationale:** Simplicidad y evita botones.
- **Decision:** Opt-out con BAJA/STOP y re-suscripcion via ALTA (requiere SI).
  - **Rationale:** Evita colisiones con otros flujos y permite corregir errores.
- **Decision:** Bloqueo de envio de templates si no hay opt-in aceptado.
  - **Rationale:** Cumplimiento estricto de Meta.

## Risks / mitigations
- **Riesgo:** Falta de opt-in en numeros de agentes bloquea handoff.
  - **Mitigacion:** Procedimiento interno para ejecutar /optin al configurar numeros.
- **Riesgo:** Fallas de Firestore bloquean templates.
  - **Mitigacion:** Alertas de error y monitoreo.

## Open questions
- None.

## Glossary
- **PSID:** Page-scoped ID de Messenger.
- **Firestore/Datastore:** Base NoSQL serverless de GCP para lecturas por clave.
