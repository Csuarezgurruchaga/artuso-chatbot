# SPEC — NLU para separar Dirección vs Unidad (expensas)

## Summary
Cuando el usuario responde la pregunta de dirección con texto “todo junto” (dirección + piso/depto/UF/cochera/oficina/local + extras), el bot debe:
1) Guardar en `direccion` / `direccion_servicio` únicamente **calle + altura**.
2) Construir una sugerencia **normalizada** para `piso_depto` (unidad) con el resto de la información detectada.

Se implementa con enfoque **híbrido reglas→LLM**: primero regex (actual), y solo si se detectan señales claras de unidad se llama a OpenAI.

## Goals
- Aumentar la tasa de captura correcta de `direccion` y sugerencia de `piso_depto` en inputs reales ruidosos (ej: “Lavalle 1282 piso 1 oficina 8 y 10”, “Sarmiento1922 4toA”).
- Mantener cambios mínimos: no cambia el flujo ni el data model (seguimos usando `direccion` y `piso_depto`).
- Soportar múltiples unidades en la sugerencia (ej: “UF 27 y 28”, “Oficina 8 y 10”, “Cochera 1 y 2”).

## Non-goals
- No se agrega UI nueva para seleccionar una unidad (solo sugerencia prellenada).
- No se normaliza/valida con geocoding externo.
- No se modifica el esquema de Google Sheets ni modelos persistidos.

## Inputs & Outputs

### Input (usuario)
Texto libre recibido como respuesta a:
- “🏠 ¿A qué dirección corresponde el pago?”
- “¿En qué lugar se presenta el problema?” (reclamos)

### Output (persistencia/conversación)
- `datos_temporales["direccion"]` o `datos_temporales["direccion_servicio"]`: `"<calle> <altura>"`
- `datos_temporales["_piso_depto_sugerido"]`: string normalizado para sugerir en la pregunta “🚪¿Cuál es tu unidad?”

## Trigger (cuándo llamar a OpenAI)
Solo se llama a OpenAI si `ChatbotRules._parece_direccion_con_unidad(texto)` detecta señales claras de “unidad” (keywords o patrones de piso/depto/UF/cochera/oficina/local).

## OpenAI
- Variable de entorno para el modelo: `OPENAI_NLU_MODEL`
- Default si no está seteada: `gpt-4o-mini`

## LLM Contract (JSON)
El LLM responde **solo JSON válido**:
```json
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
```

## Normalización de sugerencia de unidad
Se construye en este orden (solo si existe):
1) Piso: `Piso <X>`
2) Depto: `Depto <Y>`
3) UF: `UF <a> y <b> ...`
4) Cochera: `Cochera <a> y <b> ...`
5) Oficina: `Oficina <a> y <b> ...`
6) Local: `Local`
7) Extra: `(<unidad_extra>)`

Separador principal: `, `. Conector de listas: ` y `.

## Failure modes
- Si OpenAI falla (sin API key, timeout, JSON inválido): fallback a regex actual.
- Si `direccion_altura` no pasa validación local (`_direccion_valida`): no se reemplaza la dirección base; solo se usa la sugerencia si existe.

