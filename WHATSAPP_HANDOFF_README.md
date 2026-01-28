# WhatsApp Handoff System

## Overview

El sistema de handoff usa la WhatsApp Cloud API de Meta. Los agentes humanos reciben notificaciones directamente en su WhatsApp y pueden responder a los clientes desde la misma plataforma.

## Configuration

### Environment Variables Required

```bash
# WhatsApp Agent Configuration
HANDOFF_WHATSAPP_NUMBER=+5491135722871  # Número del agente (formato internacional)
HANDOFF_EMERGENCY_WHATSAPP_NUMBER=+5491130000000  # Opcional (emergencias)

# Meta WhatsApp Cloud API
META_WA_ACCESS_TOKEN=<token_de_acceso>
META_WA_PHONE_NUMBER_ID=<phone_number_id>
META_WA_APP_SECRET=<app_secret>
META_WA_VERIFY_TOKEN=<verify_token>
```

## How It Works

### 1. Handoff Detection
- Cuando un cliente solicita hablar con un humano, el bot detecta la solicitud
- El bot responde: "Te conecto con un agente humano ahora mismo. 👩🏻‍💼👨🏻‍💼"
- Se activa el estado `ATENDIDO_POR_HUMANO`

### 2. Agent Notification
- El agente recibe un mensaje en su WhatsApp con:
  - Información del cliente (nombre y número)
  - Mensaje que disparó el handoff
  - Último mensaje del cliente
  - Instrucciones para responder

### 3. Agent Response
- El agente puede responder directamente desde su WhatsApp
- Sus mensajes se envían al cliente con el prefijo "👨‍💼 *Agente:*"
- El agente recibe confirmación de que su mensaje fue enviado

### 4. Resolution (Mejorado)
- Para finalizar la conversación, el agente envía: `ok`, `listo`, `/r`, etc.
- Si `ENABLE_POST_HANDOFF_SURVEY=true` está habilitado, se envía encuesta de satisfacción
- Si `ENABLE_POST_HANDOFF_SURVEY=false` o no está configurado, la conversación se cierra inmediatamente
- El agente continúa con la siguiente persona en cola (si la hay)

## Agent Commands

| Command | Description |
|---------|-------------|
| `/resuelto`, `/r` | Cierra la conversación activa y ofrece encuesta si `ENABLE_POST_HANDOFF_SURVEY=true` |
| `ok`, `listo`, `done` | Comandos naturales para resolución |
| `/resolved`, `/cerrar`, `/close`, `/fin`, `/end` | Alias para resolución |

### Comandos Cortos y Naturales
- **`/r`** - Resolución rápida
- **`ok`** - Comando natural más usado
- **`listo`** - Comando en español
- **`done`** - Comando en inglés

## Encuesta de Satisfacción

### Configuración
Para habilitar la encuesta de satisfacción post-handoff, configurar:
```bash
ENABLE_POST_HANDOFF_SURVEY=true
# (Legacy) SUMMARY=true  # deprecated
SHEETS_SURVEY_SHEET_NAME=ENCUESTA_RESULTADOS
```

### Funcionamiento
1. **Activación**: Se activa cuando el agente escribe `/r` o `/resuelto`
2. **Preguntas**: 3 preguntas secuenciales con opciones numeradas
3. **Respuestas**: El cliente puede responder con números según cada pregunta o texto
4. **Almacenamiento**: Resultados se guardan en Google Sheets
5. **Finalización**: Conversación se cierra automáticamente

### Preguntas de la Encuesta
1. **¿Pudiste resolver el motivo por el cuál te comunicaste?**
   - 1️⃣ Sí
   - 2️⃣ Parcialmente  
   - 3️⃣ No

2. **¿Qué tan satisfecho quedaste con la atención?**
   - 1️⃣ Muy insatisfecho
   - 2️⃣ Insatisfecho
   - 3️⃣ Neutral
   - 4️⃣ Satisfecho
   - 5️⃣ Muy satisfecho

3. **¿Volverías a utilizar esta vía de contacto?**
   - 1️⃣ Sí
   - 2️⃣ No

## Message Flow

```
Client → Bot: "Quiero hablar con un humano"
Bot → Client: "Te conecto con un agente humano ahora mismo..."
Bot → Agent: "🔄 Nueva solicitud de agente humano\nCliente: Juan (+5491123456789)\n..."

Client → Bot: "Tengo un problema con mi pedido"
Bot → Agent: "💬 Nuevo mensaje del cliente\nCliente: Juan (+5491123456789)\nMensaje: Tengo un problema con mi pedido"

Agent → Bot: "Hola Juan, ¿en qué puedo ayudarte?"
Bot → Client: "👨‍💼 Agente: Hola Juan, ¿en qué puedo ayudarte?"
Bot → Agent: "✅ Mensaje enviado al cliente +5491123456789"

Agent → Bot: "/r"
# Si ENABLE_POST_HANDOFF_SURVEY=true:
Bot → Client: "¡Gracias por tu consulta, Juan! 🙏\n\n¿Nos ayudas con 3 preguntas rápidas? (toma menos de 1 minuto)\nTu opinión es muy valiosa para mejorar nuestro servicio.\n\n1️⃣ Sí, con gusto\n2️⃣ No, gracias\n\nSi no respondes en 2 minutos, cerraremos la conversación automáticamente."
Bot → Agent: "✅ Cierre enviado a Juan (+5491123456789). ⏳ Encuesta en curso (auto-cierre 15 min). Usa /queue o /next."

# Si ENABLE_POST_HANDOFF_SURVEY=false:
Bot → Client: "¡Gracias por tu consulta! Damos por finalizada esta conversación. ✅"
Bot → Agent: "✅ Cierre enviado a Juan (+5491123456789). Usa /queue o /next."

# Flujo de encuesta (si ENABLE_POST_HANDOFF_SURVEY=true):
Client → Bot: "1"
Bot → Client: "¡Perfecto! Comencemos:\n\n¿Pudiste resolver el motivo por el cuál te comunicaste?\n\n1️⃣ Sí\n2️⃣ Parcialmente\n3️⃣ No"

Client → Bot: "4"
Bot → Client: "¿Qué tan satisfecho quedaste con la atención?\n\n1️⃣ Muy insatisfecho\n2️⃣ Insatisfecho\n3️⃣ Neutral\n4️⃣ Satisfecho\n5️⃣ Muy satisfecho"

Client → Bot: "1"
Bot → Client: "¿Volverías a utilizar esta vía de contacto?\n\n1️⃣ Sí\n2️⃣ No"

Client → Bot: "1"
Bot → Client: "¡Gracias por tu tiempo! Tus respuestas nos ayudan a mejorar nuestro servicio. ✅"
# Conversación finalizada automáticamente
```

## Technical Implementation

### Files Modified
- `services/whatsapp_handoff_service.py` - New service for WhatsApp handoff
- `main.py` - Modified webhook to handle agent messages and survey responses
- `chatbot/models.py` - Added handoff fields and survey fields
- `chatbot/states.py` - Added `ENCUESTA_SATISFACCION` state
- `services/survey_service.py` - New service for satisfaction surveys
- `services/sheets_service.py` - Added support for survey results sheet

### Key Features
- **Agent Detection**: Automatically detects messages from the agent's WhatsApp number
- **Bidirectional Communication**: Agent can respond to clients directly
- **Smart Resolution**: Natural commands (ok, listo, /r) with client confirmation
- **Satisfaction Surveys**: Optional post-handoff surveys with 3 questions
- **Auto Timeout**: Oferta de encuesta (2 min) y encuesta en curso (15 min)
- **Error Handling**: Comprehensive error handling and logging
- **Confirmation Messages**: Agent receives confirmation of sent messages
- **Improved UX**: Short commands and natural language support
- **Data Collection**: Survey results stored in Google Sheets for analysis

## Migration from Slack

The system has been completely migrated from Slack to WhatsApp:
- ❌ Removed: Slack channel notifications
- ❌ Removed: Slack thread management
- ❌ Removed: Slack button interactions
- ✅ Added: Direct WhatsApp notifications to agent
- ✅ Added: WhatsApp-based agent responses
- ✅ Added: WhatsApp command system

## Testing

To test the handoff system:

1. Set up the `HANDOFF_WHATSAPP_NUMBER` environment variable (and `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` if needed)
2. Send a message to the bot requesting human assistance
3. Verify the agent receives the notification
4. Have the agent respond to test bidirectional communication
5. Use `/resuelto` command to test resolution

## Troubleshooting

### Common Issues

1. **Agent not receiving notifications**
   - Check `HANDOFF_WHATSAPP_NUMBER` is set correctly
   - Verify Meta credentials (`META_WA_*`) are valid
   - Check logs for error messages

2. **Agent messages not reaching clients**
   - Verify agent's WhatsApp number matches `HANDOFF_WHATSAPP_NUMBER`
   - Check que el webhook de Meta esté verificado y activo
   - Review error logs

3. **Resolution commands not working**
   - Ensure agent sends exact command (case insensitive)
   - Check for typos in command
   - Verify conversation is in handoff state

### Logs to Monitor

```bash
# Successful handoff notification
✅ Notificación de handoff enviada al agente para cliente +5491123456789

# Agent message processing
Procesando mensaje del agente +5491135722871: Hola, ¿en qué puedo ayudarte?

# Message delivery confirmation
✅ Mensaje enviado al cliente +5491123456789
```
