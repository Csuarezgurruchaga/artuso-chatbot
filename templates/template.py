from jinja2 import Template

NLU_INTENT_PROMPT=Template("""
Usuario escribió: "{{mensaje_usuario}}"

Las opciones disponibles son:
1. PAGO_EXPENSAS - registrar el pago de expensas (fecha, monto, dirección, piso/departamento)
2. SOLICITAR_SERVICIO - realizar un reclamo (Destapación, Filtracion/Humedad, Pintura, Ruidos Molestos u Otro reclamo)
3. EMERGENCIA - urgencias o emergencias que requieren atención inmediata

EJEMPLOS DE CLASIFICACIÓN:

✅ PAGO_EXPENSAS:
- "pagué las expensas ayer"
- "quiero registrar el pago de expensas"
- "aboné 45800 de expensas"

✅ SOLICITAR_SERVICIO:
- "tengo humedad en la pared"
- "tengo un problema y quiero hacer un reclamo"
- "quiero destapar el caño del baño"

✅ EMERGENCIA:
- "tengo una emergencia"
- "es urgente, necesito ayuda ya"

Analiza la intención del usuario y responde ÚNICAMENTE con una de estas opciones: PAGO_EXPENSAS, SOLICITAR_SERVICIO, o EMERGENCIA

Si no puedes determinar la intención con certeza, responde: UNCLEAR
""")


NLU_MESSAGE_PARSING_PROMPT = Template("""
Eres un experto en parsing de datos para administración de consorcios y reclamos.

Analiza este mensaje y extrae la información relevante:
"{{mensaje_usuario}}"

REGLAS CRÍTICAS DE EXTRACCIÓN:

**FECHA DE PAGO** - Preferir formato dd/mm/yyyy si está presente.
✅ EXTRAER: "12/09/2025"
❌ NO EXTRAER: fechas ambiguas sin formato claro

**MONTO** - Solo números o montos numéricos.
✅ EXTRAER: "45800", "45.800", "45,800"

**CONSERVADURISMO**: Es mejor dejar un campo vacío ("") que extraer información incorrecta.

Devuelve JSON con estos campos (cadena vacía si no encuentras):
- "tipo_consulta": PAGO_EXPENSAS, SOLICITAR_SERVICIO, EMERGENCIA, o ""
- "fecha_pago": fecha de pago
- "monto": monto abonado
- "direccion": dirección del pago (expensas)
- "piso_depto": piso/departamento/cochera
- "comentario": comentario del pago
- "tipo_servicio": tipo de reclamo
- "direccion_servicio": dirección/piso/depto del problema
- "detalle_servicio": descripción breve

EJEMPLOS CRÍTICOS:

# EJEMPLO 1: Pago de expensas
Input: "Pagué las expensas el 12/09/2025 por 45800 en Av. Corrientes 1234, 3° B"
Output: {{ "{" }}"tipo_consulta": "PAGO_EXPENSAS", "fecha_pago": "12/09/2025", "monto": "45800", "direccion": "Av. Corrientes 1234", "piso_depto": "3° B", "comentario": ""{{ "}" }}

# EJEMPLO 2: Solicitar reclamo
Input: "Tengo humedad en Rivadavia 222 piso 4B"
Output: {{ "{" }}"tipo_consulta": "SOLICITAR_SERVICIO", "tipo_servicio": "Filtracion/Humedad", "direccion_servicio": "Rivadavia 222 piso 4B", "detalle_servicio": "humedad"{{ "}" }}

Responde ÚNICAMENTE con JSON válido, sin texto adicional.
""")

NLU_DIRECCION_UNIDAD_PROMPT = Template(r"""
Sos un extractor de datos para administración de consorcios (Argentina).

Analiza este texto del usuario y separa:
1) "direccion_altura": SOLO calle/avenida + número (sin piso/depto/UF/cochera/oficina/local, sin barrio/ciudad/provincia).
2) Datos de "unidad" (piso/depto/UF/cochera/oficina/local), soportando múltiples valores.

Input:
"{{mensaje_usuario}}"

REGLAS CRÍTICAS:
- Respondé ÚNICAMENTE con JSON válido (sin texto, sin comillas triples, sin markdown).
- Conservadurismo: si no estás seguro, dejá el campo vacío o lista vacía.
- Si viene pegado sin espacio (ej: "Sarmiento1922 4toA"), igual inferí "Sarmiento 1922".
- Ignorá/quitá del output de dirección: barrio, ciudad, provincia, "CABA", "Recoleta", "Ciudad autónoma...", etc.
- Interpretá sinónimos:
  - piso: piso, p
  - depto: depto, dpto, dto, departamento
  - UF: uf, u.f., unidad funcional
  - cochera: cochera, garage, garaje
  - oficina: oficina, of, of., ofic, ofic. (por ejemplo: "of 1" = oficina 1)
  - local: local
- Múltiples: soportar "y", "," (ej: "UF 27 y 28", "oficina 8 y 10", "cochera 1, cochera 2").

DEVOLVÉ este JSON (usar "" / [] / false si no encontrás):
{
  "direccion_altura": "",
  "piso": "",
  "depto": "",
  "ufs": [],
  "cocheras": [],
  "oficinas": [],
  "es_local": false,
  "unidad_extra": ""
}

EJEMPLOS:
Input: "Sarmiento1922 4toA"
Output: {"direccion_altura":"Sarmiento 1922","piso":"4","depto":"A","ufs":[],"cocheras":[],"oficinas":[],"es_local":false,"unidad_extra":""}

Input: "Lavalle 1282 piso 1 oficina 8 y 10"
Output: {"direccion_altura":"Lavalle 1282","piso":"1","depto":"","ufs":[],"cocheras":[],"oficinas":["8","10"],"es_local":false,"unidad_extra":""}

Input: "Lavalle 1282 1 piso of 1"
Output: {"direccion_altura":"Lavalle 1282","piso":"1","depto":"","ufs":[],"cocheras":[],"oficinas":["1"],"es_local":false,"unidad_extra":""}

Input: "Lavalle 1282, uf 27, uf 28"
Output: {"direccion_altura":"Lavalle 1282","piso":"","depto":"","ufs":["27","28"],"cocheras":[],"oficinas":[],"es_local":false,"unidad_extra":""}

Input: "Guemes 3972 Piso 9o Dto B"
Output: {"direccion_altura":"Guemes 3972","piso":"9","depto":"B","ufs":[],"cocheras":[],"oficinas":[],"es_local":false,"unidad_extra":""}

Input: "Calle Paraguay 2957, departamento 7D. Barrios Recoleta, Ciudad autónoma de Buenos Aires"
Output: {"direccion_altura":"Paraguay 2957","piso":"","depto":"7D","ufs":[],"cocheras":[],"oficinas":[],"es_local":false,"unidad_extra":""}

Input: "Calle Sarmiento 1922 2° A Unidad funcional 6 a nombre de Diego Alberto Vicente"
Output: {"direccion_altura":"Sarmiento 1922","piso":"2","depto":"A","ufs":["6"],"cocheras":[],"oficinas":[],"es_local":false,"unidad_extra":"a nombre de Diego Alberto Vicente"}
""")

NLU_EXPENSAS_ED_COMBINED_PROMPT = Template(r"""
Sos un extractor de datos para pagos de expensas en Argentina.

Analiza este texto (respuesta del usuario en el paso de dirección ED) y extraé:
1) "direccion_altura": SOLO calle/avenida + número.
2) "piso_depto": unidad normalizada (ej: "2A", "7D", "Piso 10, Depto D", "Uf 6").
3) "fecha_pago": solo si es clara (preferir dd/mm/yyyy).
4) "monto": solo valor numérico (sin $ ni texto).
5) "comentario_extra": texto adicional relevante que no entra en los campos anteriores.

Input:
"{{mensaje_usuario}}"

REGLAS:
- Respondé ÚNICAMENTE JSON válido.
- Conservador: si no estás seguro, dejar campo en "".
- Ignorá barrio/ciudad/provincia al armar "direccion_altura".
- Si viene fecha en dd-mm-yyyy o dd.mm.yyyy, convertí a dd/mm/yyyy.
- Si hay "hoy" o "ayer" sin fecha explícita, dejar "fecha_pago" en "".
- Si hay múltiples números, separar dirección (altura) de monto cuando haya señal de pago/importe.

JSON esperado:
{
  "direccion_altura": "",
  "piso_depto": "",
  "fecha_pago": "",
  "monto": "",
  "comentario_extra": ""
}

EJEMPLOS:
Input: "Calle Sarmiento 1922 2° A Unidad funcional 6 a nombre de Diego Alberto Vicente"
Output: {"direccion_altura":"Sarmiento 1922","piso_depto":"2A, Uf 6","fecha_pago":"","monto":"","comentario_extra":"a nombre de Diego Alberto Vicente"}

Input: "Calle Paraguay 2957, departamento 7D. Barrios Recoleta, Ciudad autónoma de Buenos Aires"
Output: {"direccion_altura":"Paraguay 2957","piso_depto":"7D","fecha_pago":"","monto":"","comentario_extra":""}

Input: "Tte. Gral. Juan Domingo Perón 2250 Piso 10 Departamento D"
Output: {"direccion_altura":"Tte. Gral. Juan Domingo Perón 2250","piso_depto":"10D","fecha_pago":"","monto":"","comentario_extra":""}
""")



NLU_LOCATION_PROMPT=Template("""
Analiza esta dirección en Argentina: "{{direccion}}"

¿La dirección especifica claramente si es CABA o Provincia de Buenos Aires?

SINÓNIMOS CABA: CABA, Ciudad Autónoma, Capital, Capital Federal, C.A.B.A, Microcentro, Palermo, Recoleta, San Telmo, etc.
SINÓNIMOS PROVINCIA: Provincia, Prov, Buenos Aires, Bs As, GBA, Gran Buenos Aires, Zona Norte, Zona Oeste, Zona Sur, La Plata, etc.

Responde JSON:
- "ubicacion_detectada": "CABA", "PROVINCIA", o "UNCLEAR"
- "confianza": número del 1 al 10
- "razon": explicación breve

Ejemplos:
"Av. Corrientes 1234 CABA" → {{ "{" }}"ubicacion_detectada": "CABA", "confianza": 10, "razon": "menciona CABA explícitamente"{{ "}" }}
"Del valle centenera 3222" → {{ "{" }}"ubicacion_detectada": "UNCLEAR", "confianza": 2, "razon": "no especifica CABA o Provincia"{{ "}" }}
"La Plata centro" → {{ "{" }}"ubicacion_detectada": "PROVINCIA", "confianza": 9, "razon": "La Plata es ciudad de Provincia de Buenos Aires"{{ "}" }}

Responde solo JSON.
""")

# Templates para detección de consultas de contacto
CONTACT_INFO_DETECTION_PROMPT = Template("""
Analiza este mensaje del usuario: "{{mensaje_usuario}}"

¿El usuario está preguntando sobre información de contacto, datos o ubicación de la empresa?

TIPOS DE CONSULTAS DE CONTACTO:
- Teléfono: "cuál es su teléfono", "número de contacto", "como los llamo"
- Dirección: "dónde están ubicados", "cuál es su dirección", "donde los encuentro"
- Horarios: "qué horarios tienen", "cuándo abren", "hasta qué hora atienden"
- Email: "cuál es su email", "correo electrónico"
- Información general: "datos de contacto", "cómo los contacto"

Responde ÚNICAMENTE: CONTACTO o NO

Ejemplos:
"cuál es su teléfono?" → CONTACTO
"necesito un presupuesto" → NO
"dónde están ubicados?" → CONTACTO
"ok, pero cuándo abren?" → CONTACTO
""")

CONTACT_INFO_RESPONSE_PROMPT = Template("""
Responde de manera natural y amigable esta consulta sobre información de contacto de nuestra empresa:

Pregunta del usuario: "{{mensaje_usuario}}"

Información de la empresa {{company_name}}:
- Nombre: {{company_name}}
{% if company_public_phone and company_mobile_phone %}
- Teléfono fijo: {{company_public_phone}}
- Celular: {{company_mobile_phone}}
{% elif company_phone %}
- Teléfono: {{company_phone}}
{% endif %}
- Dirección: {{company_address}}
- Horarios: {{company_hours}}
- Email: {{company_email}}
{% if company_website %}- Web: {{company_website}}{% endif %}

Instrucciones:
1. Responde de manera conversacional y amigable
2. Proporciona la información específica que está pidiendo
3. Si la pregunta es general, da la información más relevante
4. Usa emojis apropiados para hacer la respuesta más visual
5. Mantén un tono profesional pero cercano

Genera una respuesta natural en español.
""")

PERSONALIZED_GREETING_PROMPT = Template("""
Genera un saludo personalizado para WhatsApp como {{bot_name}} de {{company_name}}.

Información del usuario:
- Nombre: {{user_name}}
- Es primera vez: {{is_first_time}}

Instrucciones:
1. Si tiene nombre, úsalo en el saludo
2. Si no tiene nombre, saluda de manera general  
3. Preséntate como {{bot_name}} de {{company_name}}
4. Usa un tono amigable y profesional
6. Incluye emojis apropiados
7. Invita a elegir una opción del menú

Genera un saludo natural en español.
""")
