# Acceptance: input-validation-rate-limit

## Acceptance criteria
1. Fecha accepts dd/mm/yyyy and also dd-mm-yyyy or dd.mm.yyyy; stored format uses "/" and "hoy/ayer" remain valid for expensas.
2. Monto accepts thousands + decimals; if both "." and "," appear, the last separator is decimal; normalized output uses "." as decimal and no thousands.
3. Monto is rejected if non-numeric, <= 0, or > 2,000,000.
4. Direccion fields (expensas and servicio) require at least one letter and one number and allow only letters, numbers, spaces, and ".,#/-º°".
5. A phone can start at most 20 flows per Argentina calendar day; the check occurs at flow start.
6. When limit exceeded, system blocks and shows: "Por hoy ya alcanzaste el máximo de 20 interacciones 😊 Mañana podés volver a usar el servicio sin problema!" and no handoff is triggered.
7. Rate-limit counters persist across restarts via a RATE_LIMIT sheet in Google Sheets.
