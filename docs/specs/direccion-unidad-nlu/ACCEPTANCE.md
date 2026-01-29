# ACCEPTANCE — direccion-unidad-nlu

- Dado `Lavalle 1282 piso 1 oficina 8 y 10` en la pregunta de dirección:
  - `direccion` queda como `Lavalle 1282`
  - `_piso_depto_sugerido` queda como `Piso 1, Oficina 8 y 10`
- Dado `Lavalle 1282, uf 27, uf 28`:
  - `direccion` queda como `Lavalle 1282`
  - `_piso_depto_sugerido` queda como `UF 27 y 28`
- Dado `Sarmiento1922 4toA`:
  - `direccion` queda como `Sarmiento 1922`
  - `_piso_depto_sugerido` queda como `Piso 4, Depto A`
- Si `OPENAI_API_KEY` no está configurada o el JSON del LLM es inválido, el flujo no se rompe (fallback a regex actual).

