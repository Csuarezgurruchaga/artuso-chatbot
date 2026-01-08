# Plan

## Implementation checklist (ordered)
1. Add Argentina date helper (zoneinfo) and extend fecha_pago buttons to include "Ayer".
2. Update interactive handler to map "fecha_hoy"/"fecha_ayer" and parse exact "hoy"/"ayer" when campo_actual == `fecha_pago`.
3. Extend media extraction to capture caption text for image/document and pass it through message processing.
4. Add attachment lists in conversation data (`comprobantes`, `adjuntos_servicio`, `adjuntos_pendientes`) and update media handling in `main.py` to:
   - Upload all media to GCS.
   - Ask expensas confirmation when no active flow.
   - Start expensas flow on "Si" and mark comprobante as completed.
5. Implement `clients_sheet_service` to read/write `CLIENTES` (same spreadsheet as expensas) using JSON list with max 5.
6. Add address selection flow in `ChatbotRules` for expensas and servicios:
   - Texto numerado con direcciones y "Otra Direccion" como ultima opcion.
   - Parseo de respuestas numericas y "uno/dos/tres/cuatro/cinco", "otra".
   - Eliminacion via texto numerado si ya hay 5 y el usuario quiere agregar una nueva.
7. Update confirmation messages to show attachment counts (no URLs).
8. Update `email_service.py` to include clickable attachment links in service emails.
9. Update `expensas_sheet_service.py` to store newline-separated URLs in `COMPROBANTE` (no HYPERLINK formula).
10. Add/update documentation/config notes if needed.

## Files/components likely to change
- `chatbot/rules.py` (fecha hoy/ayer, address selection states, confirmation text)
- `chatbot/states.py` (temporary flags for selection/deletion, attachment lists)
- `chatbot/models.py` (new fields if needed)
- `main.py` (media handling, expensas confirmation, attachment persistence)
- `services/meta_whatsapp_service.py` (caption extraction)
- `services/gcs_storage_service.py` (no change expected; used for uploads)
- `services/expensas_sheet_service.py` (comprobante multi-URL storage)
- `services/email_service.py` (adjuntos en email)
- `services/clients_sheet_service.py` (new)

## Data/migration steps
- Create a new sheet tab `CLIENTES` in the expensas spreadsheet (`EXPENSAS_SPREADSHEET_ID`).
- Ensure service account in `GOOGLE_EXPENSAS_SERVICE_ACCOUNT_JSON` has access.
- No backfill required initially.

## Integration points
- WhatsApp interactive buttons (Meta Cloud API) para fecha/media/confirmaciones.
- Google Sheets (expensas spreadsheet).
- GCS for media storage.
- AWS SES email for service notifications.

## Test plan mapped to acceptance
- AC1/AC2: Validate "Hoy/Ayer" buttons and exact text handling.
- AC3/AC4: Media confirmation and flow initiation.
- AC5/AC6: Multiple attachments stored and shown correctly.
- AC9/AC10/AC11/AC12: Seleccion de direccion por texto, max 5, delete flow, reemplazo por duplicado.
- AC8: Service emails show attachments as links.

## Rollout steps
1. Deploy to staging (if available) or test number in prod.
2. Verify flows manually with real WhatsApp number.
3. Deploy to production.

## Rollback steps
- Revert to previous release image in Cloud Run.
- Disable any new sheet usage by removing `CLIENTES` tab if needed.
