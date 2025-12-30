# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **hybrid WhatsApp and Messenger chatbot with NLU capabilities** for Argenfuego (fire safety equipment company) built with FastAPI. It combines rule-based logic with OpenAI-powered natural language understanding for flexible conversation flow. Handles lead qualification and capture through **WhatsApp Cloud API** and **Facebook Messenger** integration using Meta Graph API, with email notifications via AWS SES.

## Project Structure

### Directory Organization
```
rulebased-chatbot/
├── main.py                   # 🚀 FastAPI application entry point & webhook handler
├── requirements.txt          # 📦 Python dependencies (includes OpenAI, dateparser)
├── .env                     # 🔐 Environment variables (API keys, secrets)
│
├── chatbot/                 # 🧠 Core conversation logic
│   ├── models.py           # 📋 Data models (Pydantic) & conversation states
│   ├── rules.py            # ⚖️ Business logic + hybrid NLU processing
│   └── states.py           # 💾 In-memory conversation state management
│
├── services/               # 🔌 External service integrations
│   ├── meta_whatsapp_service.py  # 📱 WhatsApp messaging via Meta Cloud API
│   ├── meta_messenger_service.py # 💬 Facebook Messenger integration
│   ├── email_service.py    # 📧 Lead notifications via AWS SES
│   ├── nlu_service.py      # 🤖 OpenAI NLU intent mapping & data extraction
│   ├── whatsapp_handoff_service.py # 🔄 Human handoff for WhatsApp & Messenger
│   ├── agent_command_service.py # 🎮 Agent command processing (/done, /next, etc.)
│   ├── survey_service.py   # 📋 Post-handoff satisfaction surveys
│   ├── slack_service.py    # 📢 Legacy Slack integration (fallback)
│   ├── error_reporter.py   # 🚨 Error reporting and tracking
│   ├── metrics_service.py  # 📊 Usage metrics collection (Google Sheets)
│   ├── otel_metrics_service.py  # 📈 OpenTelemetry metrics for Datadog
│   ├── otel_middleware.py  # 🔍 HTTP metrics middleware for FastAPI
│   └── sheets_service.py   # 📄 Google Sheets integration
│
├── config/                 # ⚙️ Multi-company configuration system
│   └── company_profiles.py # 🏢 Company profiles & contact information
│
├── templates/              # 📝 Jinja2 templates for NLU prompts
│   └── template.py         # 🤖 OpenAI prompt templates & examples
│
├── tests/                  # 🧪 Comprehensive testing suite
│   ├── test_chatbot.py     # 🔄 Hybrid chatbot testing
│   ├── test_llm_first.py   # 🤖 LLM-first parsing tests
│   ├── test_simple.py      # 🔍 Basic parsing validation
│   └── test_contact_info.py # 📞 Contact interruption & urgency tests
```

### Component Responsibilities

**`main.py`**: FastAPI server with webhook endpoints for Meta WhatsApp/Messenger integration  
**`chatbot/models.py`**: Pydantic data models, enums, and validation schemas  
**`chatbot/rules.py`**: Core business logic with hybrid parsing (regex + NLU fallbacks)  
**`chatbot/states.py`**: In-memory session management and conversation state persistence  
**`services/meta_whatsapp_service.py`**: WhatsApp Cloud API integration (send messages, validate webhooks)  
**`services/meta_messenger_service.py`**: Facebook Messenger Send API integration  
**`services/email_service.py`**: HTML email templates and AWS SES integration  
**`services/nlu_service.py`**: OpenAI API integration for intent recognition & data extraction  
**`services/whatsapp_handoff_service.py`**: Human handoff system for WhatsApp and Messenger  
**`services/agent_command_service.py`**: Agent command processing (/done, /next, /queue, /help)  
**`services/survey_service.py`**: Post-handoff satisfaction survey system  
**`services/slack_service.py`**: Legacy Slack integration for fallback handoff support  
**`services/error_reporter.py`**: Structured error reporting and exception tracking  
**`services/metrics_service.py`**: Usage metrics collection to Google Sheets  
**`services/otel_metrics_service.py`**: OpenTelemetry metrics export to Datadog  
**`services/otel_middleware.py`**: FastAPI middleware for automatic HTTP metrics  
**`services/sheets_service.py`**: Google Sheets integration for data persistence  
**`config/company_profiles.py`**: Multi-company configuration, contact info & urgency redirects  
**`templates/template.py`**: Jinja2 templates for OpenAI prompts with JSON examples

## Core Architecture

### State Machine Pattern
- **Entry Point**: `main.py` - FastAPI application with uvicorn server
- **State Management**: `chatbot/states.py` - `ConversationManager` handles user sessions in-memory
- **Business Logic**: `chatbot/rules.py` - `ChatbotRules` static class processes conversation flow with NLU fallbacks
- **Data Models**: `chatbot/models.py` - Pydantic models with validation

### Conversation Flow States
```
INICIO → ESPERANDO_OPCION → RECOLECTANDO_DATOS → RECOLECTANDO_DATOS_INDIVIDUALES → VALIDANDO_UBICACION → CONFIRMANDO → ENVIANDO → FINALIZADO

Additional states:
- MENU_PRINCIPAL: For returning to main menu from any conversation state
- CORRIGIENDO: For asking which field to correct
- CORRIGIENDO_CAMPO: For receiving new field value
```

### Service Integration Layer
- **WhatsApp**: `services/meta_whatsapp_service.py` - Message sending/receiving via Meta Cloud API
- **Messenger**: `services/meta_messenger_service.py` - Facebook Messenger integration via Send API
- **Email**: `services/email_service.py` - Lead notifications via AWS SES with HTML templates
- **NLU Service**: `services/nlu_service.py` - OpenAI integration for intent mapping and data extraction
- **Human Handoff**: `services/whatsapp_handoff_service.py` - Agent notification and conversation routing (supports both channels)
- **Error Tracking**: `services/error_reporter.py` - Structured exception reporting
- **Analytics**: `services/metrics_service.py` - Usage statistics and performance tracking
- **Data Storage**: `services/sheets_service.py` - Google Sheets integration for lead persistence

## Development Commands

### Running the Application
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload enabled)
python main.py

# Or run with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Testing
```bash
# Run individual test scripts (no pytest framework)
python tests/test_simple.py          # Basic parsing validation
python tests/test_llm_first.py       # LLM-first parsing tests  
python tests/test_chatbot.py         # Hybrid chatbot scenarios
python tests/test_contact_info.py    # Contact interruption tests
python tests/test_flujo_secuencial.py # Sequential flow tests
python tests/test_humano_contact.py  # Human handoff tests

# All tests are standalone Python scripts with direct execution
```

### Environment Setup
```bash
# Copy and configure environment variables
cp .env.example .env  # Create from template if needed

# Required environment variables:
OPENAI_API_KEY=your_openai_api_key  # Required for NLU features
COMPANY_PROFILE=argenfuego  # Company profile selection (argenfuego, empresa_ejemplo)
COMPANY_EMAIL=your_company_email

# Meta WhatsApp Cloud API Configuration
META_WA_ACCESS_TOKEN=your_meta_access_token     # Meta app access token (used for both WhatsApp and Messenger)
META_WA_PHONE_NUMBER_ID=your_phone_number_id    # WhatsApp phone number ID
META_WA_APP_SECRET=your_app_secret              # Meta app secret for webhook signature validation
META_WA_VERIFY_TOKEN=your_verify_token          # Webhook verification token
WHATSAPP_STICKER_MEDIA_ID=your_sticker_media_id # Optional: Media ID for faster sticker delivery

# Facebook Messenger Configuration (Optional)
META_PAGE_ID=your_facebook_page_id              # Facebook Page ID for Messenger (enables Messenger support)

# AWS SES Email Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
SES_FROM_EMAIL=your_verified_ses_email

# WhatsApp Handoff Configuration
AGENT_WHATSAPP_NUMBER=+5491135722871  # Agent's WhatsApp for handoff notifications
AGENT_API_TOKEN=your_secure_token     # Authentication for agent API endpoints
HANDOFF_TTL_MINUTES=120              # Handoff timeout in minutes (default 120)

# OpenTelemetry / Datadog Metrics Configuration
OTEL_METRICS_ENABLED=true            # Enable/disable metrics (default: false)
DD_API_KEY=your_datadog_api_key      # Datadog API key (required for metrics)
DD_SITE=datadoghq.com               # Datadog site (US1: datadoghq.com, EU: datadoghq.eu)
DD_SERVICE=chatbot-argenfuego       # Service name shown in Datadog (unique per chatbot)
DD_ENV=production                   # Environment tag (production, staging, dev)
DD_VERSION=1.0.0                    # Version tag (optional)

# Optional
PORT=8080  # Server port, defaults to 8080
```

## API Endpoints

### Core Endpoints
- `GET /` - API info and health check
- `GET /health` - Service health status  
- `GET /webhook/whatsapp` - Meta webhook verification endpoint
- `POST /webhook/whatsapp` - **Main webhook** for incoming WhatsApp and Messenger messages (auto-detects source)
- `GET /stats` - Conversation statistics
- `POST /reset-conversation` - Debug endpoint for resetting user conversations

### WhatsApp Handoff Endpoints  
- `POST /handoff/ttl-sweep` - Automated job to close inactive handoff conversations
- `POST /agent/reply` - Agent API endpoint for sending responses to clients
- `POST /agent/close` - Agent API endpoint for closing conversations

### Legacy Slack Endpoints (Fallback)
- `POST /slack/commands` - Slack slash commands (/responder, /resuelto, /finalizar)
- `POST /slack/actions` - Slack interactive components (buttons, modals)
- `POST /slack/events` - Slack events API for message handling

## Data Models and Business Logic

### Service Types (TipoConsulta enum)
- `PRESUPUESTO` - Budget quotes (when customer knows exactly what they need)
- `VISITA_TECNICA` - Technical visits (when customer needs evaluation/assessment)  
- `URGENCIA` - Emergency services
- `OTRAS` - Other inquiries

### Contact Data Validation
- **Email**: Full email validation via pydantic
- **Address**: Minimum 5 characters
- **Schedule**: Minimum 3 characters
- **Description**: Minimum 10 characters

## Hybrid NLU Features

### Intent Mapping with OpenAI
The chatbot automatically maps natural language to service types based on specificity:

**PRESUPUESTO** (customer knows exactly what they need):
- **"necesito 3 matafuegos ABC de 5kg"** → `PRESUPUESTO`
- **"quiero comprar 2 extintores para oficina"** → `PRESUPUESTO`
- **"necesito que me fijen 4 matafuegos, 2 placas"** → `PRESUPUESTO`

**VISITA_TECNICA** (customer needs evaluation):
- **"no sé qué equipos necesito para mi local"** → `VISITA_TECNICA`
- **"necesito que evalúen qué dotación requiere mi empresa"** → `VISITA_TECNICA`
- **"qué tipo de matafuegos necesito?"** → `VISITA_TECNICA`

**Other classifications:**
- **"se me rompió el extintor"** → `URGENCIA`
- **"cuándo abren?"** → `OTRAS`

### LLM-First Data Extraction
Advanced semantic parsing system:
- **OpenAI as Primary Parser**: Handles complex multi-field input in single messages
- **Context-Aware Extraction**: "Del valle centenera 3222 piso 4D, pueden pasar de 15-17h" → separates address + schedule
- **Intelligent Field Separation**: Uses semantic understanding vs rigid regex patterns
- **Regex Fallback**: Falls back to keyword scoring when LLM extraction insufficient

### Progressive Data Collection
Smart questioning system that:
- Extracts partial data from user messages using LLM-first approach
- Shows progress: "✅ Ya tengo: 📧 Email, 📍 Dirección"
- Asks only for missing fields individually
- Uses `RECOLECTANDO_DATOS_INDIVIDUALES` state for step-by-step collection

### Geographic Location Validation
Intelligent CABA/Provincia detection system:
- **Auto-Detection**: Extensive synonym mapping for neighborhoods and localities
- **LLM Geographic Intelligence**: Fallback detection for ambiguous addresses
- **Decision Tree**: Manual selection when auto-detection unclear
- **New State**: `VALIDANDO_UBICACION` for geographic confirmation flow
- **Smart Integration**: Seamlessly continues conversation after location validation

### Advanced Features

#### Multi-Company Support
- **Configurable Profiles**: Support for multiple companies via `COMPANY_PROFILE` env var
- **Dynamic Contact Info**: Company-specific phone numbers, addresses, and hours
- **Brand Personalization**: Custom bot names and company-specific messaging

#### Contextual Intent Interruption
- **Contact Queries**: Users can ask "cuál es su teléfono?" mid-conversation
- **Smart Detection**: NLU identifies contact requests in any state
- **Seamless Return**: Conversation continues after providing contact info

#### Personalized Experience
- **WhatsApp Profile Names**: Uses ProfileName from webhook for personalization
- **Dynamic Greetings**: OpenAI-generated personalized welcome messages
- **Context Preservation**: Maintains conversation state across interruptions

#### Emergency Handling
- **Immediate Redirect**: Urgency detection triggers instant phone number display
- **Priority Numbers**: Shows both landline and emergency mobile numbers
- **State Termination**: Ends conversation flow for immediate human intervention

### Supported Use Cases
- ✅ **Traditional**: Numeric selection + structured data in one message
- ✅ **LLM-First Multi-Field**: Single message with multiple data fields extracted intelligently
- ✅ **Geographic Validation**: Auto-detection of CABA/Provincia with manual fallback
- ✅ **NLU Intent**: Natural language → automatic service type mapping
- ✅ **Progressive Questions**: Missing fields → individual targeted questions
- ✅ **Complex Natural Language**: Full semantic parsing with context understanding
- ✅ **Contact Interruption**: Mid-conversation contact queries with flow resumption
- ✅ **Emergency Routing**: Immediate human redirect for urgent situations
- ✅ **Menu Return**: Users can return to main menu from any conversation state
- ✅ **Pre-saved Descriptions**: Initial detailed requests auto-saved as description field

### Example Interactions

#### Standard Flow
```
User: "Del valle centenera 3222 piso 4D, pueden pasar de 15-17h"
✅ Extracts: address="Del valle centenera 3222 piso 4D", schedule="15-17h"

User: "juan@empresa.com, Palermo cerca del shopping, mañanas, necesito extintores ABC"  
✅ Extracts all fields + auto-detects Palermo = CABA

User: "Ramos Mejía altura 2500"
✅ Auto-detects Ramos Mejía = Provincia de Buenos Aires
```

#### Contextual Interruption
```
User: "1" (selects budget option)
Bot: "Para ayudarte con presupuesto, necesito..."
User: "cuál es su teléfono?"
Bot: "📞 Argenfuego - Tel: 4567-8900 | Cel: 11-3906-1038. Sigamos con tu consulta..."
```

#### Emergency Handling
```
User: "3" (selects urgency)
Bot: "🚨 URGENCIA DETECTADA 🚨 
     📞 Teléfono fijo: 4567-8900
     📱 Celular emergencias: 11-3906-1038"
[Conversation terminates for immediate human intervention]
```

#### Personalized Greeting
```
User: "hola" (ProfileName: Carlos R)
Bot: "¡Hola Carlos R! 👋 Soy Eva de Argenfuego, bienvenido. ¿En qué puedo ayudarte?"
```

#### Menu Return Functionality
```
User: "necesito 3 matafuegos ABC" (auto-detected as PRESUPUESTO)
Bot: "¡Listo! 📝 Para armar tu presupuesto, pásame: 📧 Email..."
User: "menú"
Bot: "↩️ Volviendo al menú principal... ¡Hola Carlos R! ¿En qué puedo ayudarte?"
```

## Important Technical Notes

### Session Management
- **In-memory storage only** - conversations reset on server restart
- Each conversation identified by phone number
- State persists throughout user journey until completion

### Message Processing Flow (LLM-First Hybrid)
1. Webhook receives message from Meta (WhatsApp Cloud API or Messenger)
2. **Auto-detect source**: Check `object` field ("whatsapp_business_account" vs "page")
3. **Validate signature**: HMAC-SHA256 validation with app_secret
4. Extract user ID (phone number or messenger:PSID), message content, and profile name
5. **Contextual Interruption Check**: Detect contact queries in any state first
6. **Intent Recognition**: NLU service maps natural language to service types (fallback)
7. **Emergency Detection**: Immediate redirect for urgency with phone numbers
8. **LLM-First Data Extraction**: OpenAI semantic parsing for multi-field extraction
9. **Geographic Validation**: Auto-detect CABA/Provincia or trigger decision tree
10. **Progressive Collection**: Individual field questions for remaining missing data
11. **Fallback Strategy**: Regex/keyword parsing if LLM extraction insufficient
12. Process through hybrid state machine (LLM + rules + NLU)
13. Generate contextual response and send via appropriate channel (WhatsApp or Messenger)
14. Trigger email notification when lead is complete

### AI/ML Dependencies (Active)
The project uses several AI libraries for NLU capabilities:
- ✅ **`openai`**: Active for intent mapping and complex data extraction
- ✅ **`dateparser`**: Smart Spanish date/time parsing
- ⚠️ **`langchain-core`, `pinecone`, `guardrails-ai`**: Available but not currently used

### Security Considerations
- Twilio webhook signature validation capability implemented
- Environment variables properly gitignored
- Input validation via Pydantic models
- API keys never hardcoded in source

## Language and Localization

- **Hardcoded Spanish**: All user-facing messages are in Spanish
- Company-specific messaging for Argenfuego fire safety services
- No internationalization framework currently implemented

## Testing and Quality

### Manual Testing Tools
- **`tests/test_llm_first.py`**: Comprehensive LLM-first parsing and geographic validation testing
- **`tests/test_chatbot.py`**: Original hybrid chatbot testing with multiple conversation scenarios
- **`tests/test_simple.py`**: Focused parsing validation and debugging
- **`tests/test_contact_info.py`**: Contact interruption, urgency redirects, and personalization testing
- **Manual testing**: `/reset-conversation` endpoint for conversation state reset
- **No automated testing framework**: No unit tests or CI/CD pipeline configured

### Testing Scenarios Covered
- Multi-field extraction from single message input
- Geographic location detection (CABA/Provincia auto-detection)
- LLM vs basic parsing performance comparison
- Intent mapping with natural language input
- Progressive data collection with individual questions
- Contextual contact interruptions with flow resumption
- Emergency urgency detection and immediate redirects
- Multi-company profile configuration and personalized greetings

## Recent Bug Fixes & Improvements

### Jinja2 Template Syntax (Fixed)
- **Issue**: `expected token 'end of print statement', got ':'` error
- **Cause**: JSON examples in templates conflicted with Jinja2 `{{ }}` syntax
- **Solution**: Escaped braces using `{{ "{" }}` and `{{ "}" }}` patterns
- **Files affected**: `templates/template.py`

### Phone Key Configuration (Fixed)  
- **Issue**: `'landline_phone' esta mal una key` error for urgency messages
- **Cause**: Code searched for `landline_phone` but profile used `public_phone`
- **Solution**: Standardized to use `public_phone`, `mobile_phone`, `emergency_phone`
- **Files affected**: `config/company_profiles.py`, `services/nlu_service.py`, `templates/template.py`

### Dynamic Greeting Replaced with Static Personalized Message (Fixed)
- **Issue**: Welcome message changed constantly due to OpenAI generation with temperature=0.4
- **Cause**: `get_mensaje_inicial_personalizado()` used OpenAI for every greeting
- **Solution**: Replaced with static message that includes user's ProfileName when available
- **Result**: Consistent greeting "¡Hola [Nombre]! 👋🏻 Mi nombre es Eva 👩🏻‍🦱" with white skin tone emojis
- **Files affected**: `chatbot/rules.py`

### Contact Query Detection Optimization (Fixed)
- **Issue**: LLM-based contact detection intercepted user data as contact queries
- **Cause**: OpenAI misinterpreted data like "juan@empresa.com, address..." as contact requests
- **Solution**: Replaced with deterministic regex patterns for precise detection
- **Performance**: <1ms vs 200-1000ms, $0 API costs, offline capable
- **Files affected**: `services/nlu_service.py`

### LLM Data Parsing Precision Improvement (Fixed)
- **Issue**: "Mi Mail es email@domain.com" incorrectly extracted email as both email AND address
- **Cause**: Ambiguous LLM prompt allowed over-extraction of fields
- **Solution**: Enhanced prompt with 8 comprehensive examples and strict extraction rules
- **Result**: Conservative parsing - better empty field than incorrect extraction
- **Files affected**: `templates/template.py`

## Company Profile Configuration

### Phone Number Structure
```python
"phone": {
    "public_phone": "4567-8900",        # Main business line
    "mobile_phone": "11-3906-1038",     # Customer service mobile  
    "emergency_phone": "11-3906-1038"   # Emergency/urgency line
}
```

### Supported Company Profiles
- **argenfuego**: Fire safety equipment company (default)
- **empresa_ejemplo**: Template for additional companies
- Set via `COMPANY_PROFILE=argenfuego` environment variable

## Deployment Notes

- Runs on port 8080 by default (configurable via `PORT` env var)
- Uses uvicorn ASGI server with auto-reload in development
- Multi-company support via environment configuration
- No containerization (Dockerfile) currently present
- No CI/CD pipeline configuration
