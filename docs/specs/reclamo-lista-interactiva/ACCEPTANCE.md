# Acceptance criteria: Reclamo list interactive (tipo de reclamo)

1. All prompts that ask for `tipo_servicio` send a WhatsApp interactive list (not buttons).
2. The list button text is "Elegir opción".
3. The list options appear in this exact order and labels:
   - Destapación
   - Filtracion/Humedad
   - Pintura
   - Ruidos Molestos
   - Otro reclamo
4. Selecting an option stores the exact label in `tipo_servicio`.
5. Free-text inputs map to the correct option:
   - "destapación" -> Destapación
   - "humedad" / "filtración" -> Filtracion/Humedad
   - "pintura" -> Pintura
   - "ruidos molestos" -> Ruidos Molestos
   - "otro" -> Otro reclamo
6. All user-facing messages that list reclamo options are updated to the new list.
7. If the interactive list fails to send, the fallback text includes the updated options.
