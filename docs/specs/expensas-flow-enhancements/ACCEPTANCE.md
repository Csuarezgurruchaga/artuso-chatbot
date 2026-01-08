# Acceptance Criteria

## Functional acceptance
1. **Fecha "Hoy/Ayer" (boton)**
   - Given el flujo de expensas en `fecha_pago`
   - When el usuario toca "Hoy" o "Ayer"
   - Then se guarda la fecha correcta en horario Argentina y el flujo continua.
2. **Fecha "hoy/ayer" (texto)**
   - Given el flujo de expensas en `fecha_pago`
   - When el usuario escribe exactamente "hoy" o "ayer" (case-insensitive)
   - Then se interpreta igual que el boton correspondiente.
3. **Texto "hoy/ayer" fuera de fecha**
   - Given otro paso distinto de `fecha_pago`
   - When el usuario escribe "hoy" o "ayer"
   - Then no se interpreta como fecha y se mantiene la pregunta actual.
4. **Media sin contexto**
   - Given el usuario envia media sin flujo activo
   - When responde "Si" a "Es un pago de expensas?"
   - Then se inicia el flujo de expensas y el media queda como comprobante.
   - When responde "No"
   - Then se vuelve al menu principal y el adjunto queda pendiente para servicios.
5. **Media durante expensas**
   - Given el flujo de expensas antes de "comprobante"
   - When llega media
   - Then se guarda como comprobante y el flujo sigue sin pedir comprobante.
6. **Multiples adjuntos**
   - Given multiples media enviados
   - When se confirma expensas
   - Then `COMPROBANTE` contiene URLs separadas por salto de linea.
7. **Adjuntos en servicios**
   - Given adjuntos en solicitud de servicio
   - When se confirma la solicitud
   - Then el mensaje de confirmacion muestra cantidad de archivos (sin URL).
8. **Email de servicios**
   - Given adjuntos de servicio
   - When se envia email
   - Then aparecen links etiquetados "Archivo 1", "Archivo 2", etc.
9. **Direccion guardada**
   - Given telefono con direcciones guardadas
   - When llega al paso de direccion
   - Then se muestra un texto numerado con "Otra Direccion" como ultima opcion.
10. **Seleccion de direccion (texto)**
    - Given el texto numerado de direcciones
    - When el usuario responde con numero, "uno/dos/tres/cuatro/cinco" o "otra/otra direccion"
    - Then se selecciona la direccion o se inicia el flujo de "Otra Direccion".
11. **Orden de direcciones**
    - Given direcciones guardadas con distintos `last_used`
    - When se muestran las opciones numeradas
    - Then se ordenan de mas reciente a mas antigua.
12. **Maximo 5 direcciones**
    - Given 5 direcciones guardadas
    - When el usuario intenta agregar una nueva
    - Then el sistema pide eliminar una direccion antes de guardar via texto numerado.
13. **Reemplazo por duplicado**
    - Given una direccion+piso igual (normalizado)
    - When se intenta guardar nuevamente
    - Then se reemplaza la existente y se actualiza `last_used`.
14. **Guardar direccion en servicios**
    - Given una solicitud de servicio con "Otra Direccion"
    - When se confirma el servicio
    - Then la direccion se guarda en `CLIENTES`.

## Negative / edge cases
- Si falla la subida a GCS, se informa error y se pide reenvio del comprobante.
- Si falla Sheets, el flujo continua sin autocompletar direcciones.
- Si la respuesta de direccion es invalida, se re-envia el texto numerado.
- Si el usuario envia media en encuesta/handoff, no se interrumpe ese flujo.

## Observability checks
- Logs INFO para:
  - media_confirm_prompted
  - media_confirmed_as_expensas
  - media_saved_as_comprobante
  - direccion_seleccionada
  - direccion_eliminada
  - adjuntos_servicio_count
- Logs ERROR para fallos de GCS y Sheets.

## Validation commands (manual/optional)
- `python tests/test_chatbot.py`
- `python tests/test_simple.py`
- Manual WhatsApp flow con numero de prueba:
  - media sin contexto (Si/No)
  - flujo expensas con "Hoy/Ayer"
  - seleccion de direccion guardada y "Otra Direccion"
