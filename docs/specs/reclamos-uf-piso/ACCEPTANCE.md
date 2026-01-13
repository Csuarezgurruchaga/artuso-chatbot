# Acceptance criteria: Reclamos with piso/depto/UF step

1. Reclamo flow asks for `piso/depto/UF` after `direccion_servicio` and before `detalle_servicio`.
2. The prompt text is "¿Cuál es el piso/departamento/UF?"
3. The value is stored in `datos_temporales["piso_depto"]` and is mandatory.
4. If the user includes "UF 11" (or similar) in ubicación, the bot:
   - Splits it from the address,
   - Suggests the unit,
   - Asks for confirmation before continuing.
5. Saved address selection fills both `direccion_servicio` and `piso_depto` and skips the unit prompt.
6. Reclamo summary includes a separate line for "Piso/Departamento/UF".
7. Reclamo email includes the unit as a separate field.
8. Correction menu includes an option to edit `piso/depto/UF`.
