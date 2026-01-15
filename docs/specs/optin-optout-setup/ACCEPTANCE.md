# Acceptance criteria

## Functional
- Al enviar `/optin` desde un numero de agente, el sistema responde con el prompt de opt-in y crea estado `pending`.
- Responder `SI` cambia el estado a `accepted`, registra auditoria en GCS, y envia el mensaje de agradecimiento con opt-out.
- Responder `NO` cambia el estado a `declined`, registra auditoria y envia confirmacion de rechazo con ALTA.
- En estado `accepted`, responder `BAJA` o `STOP` cambia el estado a `opted_out`, registra auditoria y envia confirmacion.
- Responder `ALTA` re-envia el opt-in y requiere `SI` para volver a `accepted`.
- Antes de enviar cualquier template (WhatsApp/Messenger), se verifica opt-in en Firestore.
- Si no hay opt-in `accepted`, el template no se envia y se registra el bloqueo.
- En Messenger se almacena PSID y canal como identificador.

## Non-functional
- No se usa cache en memoria para opt-in (compatible con Cloud Run min instances=0).
- La auditoria se guarda en un bucket nuevo sin borrado automatico.
