# Expensas flow enhancements (fecha, media, direcciones)

## Summary
Agregar boton "Ayer" y parsing de "hoy/ayer" para fecha de pago, iniciar flujo de expensas desde media con confirmacion, adjuntar multiples comprobantes/archivos, y permitir multiples direcciones por telefono con seleccion por texto numerado. Corregir el calculo de fecha de pago a horario Argentina solo para "hoy/ayer".

## Context
El flujo actual de expensas pide fecha, monto, direccion y piso/depto en cada interaccion. Los usuarios suelen ser recurrentes y usan el mismo numero para distintos departamentos. Ademas, cuando envian una imagen/PDF de comprobante sin contexto, el bot no inicia automaticamente el flujo. Se detecto un problema de fecha al usar el boton "Hoy" fuera del horario UTC.

## Goals
- Hacer mas rapido el registro de expensas con botones "Hoy/Ayer" y parsing de texto.
- Iniciar flujo de expensas desde media y reutilizar comprobantes.
- Permitir multiples direcciones por telefono con seleccion por texto numerado y limite de 5.
- Adjuntar multiples archivos en expensas y servicios sin mostrar URLs en WhatsApp.
- Corregir fecha de pago a zona horaria Argentina solo para "hoy/ayer".

## Non-goals
- Cambiar escalas o contenido de encuestas.
- Redisenar flows de servicios o emergencia mas alla de adjuntos.
- Agregar soporte a Messenger en estas mejoras.
- Cambiar tiempos de handoff o logica de cola.
- Introducir nuevas dependencias externas.

## Users & primary flows
- Cliente (WhatsApp):
  - Registra pago de expensas con fecha "Hoy/Ayer".
  - Envia comprobante como imagen/PDF y confirma si es pago de expensas.
  - Selecciona direccion guardada o ingresa nueva.
  - Adjunta archivos en solicitud de servicio.
- Administracion (backoffice):
  - Recibe pagos con multiples comprobantes en Sheets.
  - Recibe emails de servicio con adjuntos listados.

## Functional requirements
1. En el paso `fecha_pago` del flujo de expensas, enviar botones interactivos "Hoy" y "Ayer".
2. Si el usuario responde exactamente "hoy" o "ayer" (case-insensitive) cuando el campo siguiente es `fecha_pago`, interpretar como fecha del dia en Argentina y continuar el flujo.
3. Si el usuario escribe "hoy/ayer" fuera del paso `fecha_pago`, no se interpreta como fecha (se responde con la pregunta actual).
4. Calcular "Hoy/Ayer" usando zona horaria `America/Argentina/Buenos_Aires` (sin offsets manuales).
5. Al recibir media (image/document) fuera de contexto de comprobante:
   - Preguntar con botones "Si/No": "Este archivo es un pago de expensas?"
   - Si elige "Si", iniciar flujo de expensas y guardar el media como comprobante.
   - Si elige "No", volver al menu y conservar el archivo para adjuntarlo si luego elige "Solicitar servicio".
6. Si llega media antes del paso "comprobante" en expensas, guardar el archivo como comprobante y continuar el flujo normal.
7. Soportar multiples comprobantes en expensas. Guardar todos los URLs en la columna `COMPROBANTE` con separacion por salto de linea.
8. Para solicitudes de servicio, guardar adjuntos en un campo separado y mostrar en confirmacion un texto del estilo "Adjuntos: 2 archivos".
9. En el email de servicio, incluir links clickeables etiquetados "Archivo 1", "Archivo 2" sin mostrar URL completa.
10. Si el media tiene caption/texto, usar ese texto para pre-rellenar campos del flujo correspondiente.
11. Crear y usar hoja `CLIENTES` en el spreadsheet de expensas con una lista JSON de direcciones por telefono.
12. Al llegar al paso de direccion:
   - Si hay direcciones guardadas, mostrar un texto numerado con las direcciones y una opcion final "Otra Direccion".
   - No usar botones ni listas interactivas para esta seleccion.
13. La seleccion de direccion debe aceptar:
   - Numeros (1, 2, 3, ...)
   - Palabras "uno/dos/tres/cuatro/cinco"
   - "otra" o "otra direccion"
14. Al seleccionar una direccion guardada en expensas, autocompletar `direccion` y `piso_depto` y continuar con el siguiente campo.
15. En servicios, al seleccionar una direccion guardada, completar `direccion_servicio` con "direccion + piso/depto".
16. Al elegir "Otra Direccion", continuar flujo normal: pedir direccion y luego piso/depto.
17. Guardar nueva direccion al confirmar expensas y servicios (estado ENVIANDO).
18. Maximo 5 direcciones por telefono. Si se intenta guardar una sexta, pedir que elimine una existente (texto numerado).
19. Si la nueva direccion+piso coincide con una existente (normalizada), reemplazar la existente y actualizar `last_used`.
20. Actualizar `last_used` cuando el usuario selecciona una direccion guardada (expensas o servicios).
21. Alcance: solo WhatsApp. Messenger mantiene comportamiento actual.

## Non-functional requirements
- Latencia: respuestas de botones y confirmaciones en <1s en condiciones normales.
- Confiabilidad: si falla Sheets o GCS, el flujo debe continuar con mensajes de error claros.
- Costo: no agregar dependencias ni servicios nuevos.
- Compatibilidad: mantener el flujo actual si no hay direcciones guardadas.

## System design
- Agregar un servicio `clients_sheet_service` que lee/escribe `CLIENTES` en el mismo spreadsheet de expensas.
- Guardar direcciones como lista JSON en una sola celda por telefono.
- En `ChatbotRules`/`ConversationManager`, agregar subestados para:
  - Seleccion de direccion (texto numerado)
  - Eliminacion de direccion cuando hay 5 (texto numerado)
  - Confirmacion de media como expensas (`_media_confirmacion`)
- En `main.py`, al recibir media:
  - Descargar, subir a GCS, guardar URL en lista de adjuntos y manejar confirmacion.
  - Si caption existe, procesarlo como mensaje de texto.
- Ajustar confirmaciones:
  - Expensas: "Comprobante: 2 archivos" (si hay adjuntos).
  - Servicios: "Adjuntos: 2 archivos".
- Cambiar el calculo de fecha "Hoy/Ayer" a `zoneinfo.ZoneInfo`.

## Interfaces
### WhatsApp interactive buttons
- Fecha de pago:
  - "Hoy", "Ayer"
- Confirmacion media sin contexto:
  - "Si", "No"

### Seleccion de direccion (texto numerado)
Ejemplo de salida:
```
Tengo estas direcciones guardadas:
1. Calle 1234 3B
2. Otra Direccion

Responde con el numero de la opcion.
```

### Datos de entrada
- Texto "hoy"/"ayer" exacto en paso `fecha_pago`.
- Media image/document con caption opcional.
- Respuesta numerica (1, 2, 3...) o texto ("uno/dos/tres", "otra", "otra direccion") para elegir direccion.
- Seleccion de direccion o eliminacion via texto numerado.

### Datos de salida
- Confirmacion expensas con conteo de comprobantes.
- Email de servicio con links etiquetados.

## Data model
### ConversacionData (in-memory)
- `comprobante`: lista de URLs (expensas).
- `adjuntos_servicio`: lista de URLs (servicio).
- `adjuntos_pendientes`: lista de URLs (media sin contexto hasta que elija servicio).
- Flags temporales para seleccion/eliminacion.

### Sheet `CLIENTES`
Columnas:
- `telefono` (E.164)
- `direcciones_json` (lista JSON)
- `updated_at` (timestamp ISO-8601)

Estructura JSON (lista):
```
[
  {
    "direccion": "Av. Ejemplo 1234",
    "piso_depto": "3B",
    "created_at": "2025-01-01T12:00:00Z",
    "last_used": "2025-02-01T15:30:00Z"
  }
]
```

## Error handling & failure modes
- Fallo GCS: responder error y pedir reenvio del comprobante.
- Fallo Sheets (CLIENTES): continuar flujo sin autocompletar direccion y registrar error en logs.
- Seleccion de direccion invalida: re-enviar texto numerado con opciones.
- Media sin contexto + respuesta invalida: re-preguntar confirmacion.

## Security & privacy
- Telefonos y direcciones son PII; se almacenan en Sheets.
- No exponer URLs en WhatsApp (solo conteo de archivos).
- Mantener credenciales de Google en variables de entorno existentes.

## Observability
- Logs INFO: inicio de flujo por media, confirmacion media, seleccion/eliminacion de direccion, cantidad de adjuntos guardados.
- Logs de error: fallos de GCS/Sheets.
- No loguear contenido de mensajes ni URLs completas.

## Rollout plan
- Desplegar en Cloud Run.
- Verificar manualmente con numero de prueba y media.

## Rollback plan
- Revertir al release anterior si hay fallos en flujo de expensas o adjuntos.

## Testing strategy
- Pruebas manuales:
  - Boton "Hoy/Ayer" con hora AR.
  - Media sin contexto (Si/No).
  - Multiples adjuntos en expensas y servicios.
  - Seleccion de direccion guardada y "Otra Direccion" via texto numerado.
  - Llenado de `CLIENTES` y limite de 5.

## Decisions & trade-offs
- Se usa Sheets como almacenamiento (sin DB) para simplicidad.
- Se limita a 5 direcciones para evitar listas largas.
- URLs no se muestran en WhatsApp por UX/privacidad; si quedan solo en email.
- Se evita el uso de botones/listas en direcciones para prevenir truncado en UI.
- No se soporta Messenger para reducir complejidad.

## Open Questions
- None.
