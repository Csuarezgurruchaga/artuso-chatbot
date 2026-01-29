# SPEC: Delete saved address from WhatsApp (Expensas)

## Summary

Allow a user to delete a previously saved address from the WhatsApp expensas flow.

When the bot shows the list of saved addresses (plus "Otra Direccion"), the prompt will additionally offer the keyword `eliminar`. If the user writes `eliminar`, the bot enters a delete mode where it lists only saved addresses, asks for the number to delete (or `cancelar`/`volver`), deletes the selected saved address from Google Sheets (tab `CLIENTES`, column `Direcciones_json`), confirms deletion, and then returns to the address-selection step with the updated list.

## Goals

- Enable deletion of a saved address from the address-selection step in the expensas flow.
- Keep UX simple: `eliminar` -> pick number -> confirmation -> return to updated selection list.
- Persist deletion in Google Sheets:
  - Spreadsheet: "Expensas"
  - Tab: `CLIENTES`
  - Key column: `Telefono`
  - JSON column: `Direcciones_json`
  - Updated timestamp column: `Update_at`
- Avoid calling NLU/OpenAI for handling the `eliminar` keyword.
- Add a runnable test script (no pytest dependency).

## Non-goals

- Adding a global "delete" command usable in any chatbot state.
- Supporting additional delete keywords beyond the exact `eliminar`.
- Soft-delete or audit trails inside the sheet JSON.
- Changing the underlying data model stored in `Direcciones_json`.

## Current behavior

- If the user has saved addresses, the bot shows something like:

  "Tengo estas direcciones guardadas:\n1. <direccion-guardada>\n2. Otra Direccion\n\nResponde con el numero de la opcion."

- The user can respond with a number to pick a saved address, or choose "Otra Direccion".

## Proposed behavior

### 1) Address selection prompt copy

When showing saved addresses + "Otra Direccion", change the final instruction to:

`Responde con el numero de la opcion o escribe "eliminar", para borrar una direccion.`

### 2) Enter delete mode

Trigger: user message is exactly `eliminar` (case-insensitive, trimmed) and the conversation is currently at the address-selection step.

Behavior:
- Do not call NLU.
- Show ONLY saved addresses (exclude "Otra Direccion" per Q4=C).
- Prompt:

`Escribi el numero de la direccion que queres eliminar o "cancelar".`

Accepted inputs in delete mode:
- A number 1..N
- `cancelar` or `volver` (case-insensitive, trimmed)

Invalid inputs:
- Any other text or out-of-range numbers -> re-send the same prompt.

### 3) Delete operation (Google Sheets)

Data is stored per phone number in the "Expensas" spreadsheet, tab `CLIENTES`.

Columns:
- `Telefono`: string, e.g. `+5491124881898`
- `Direcciones_json`: JSON array of objects:

  ```json
  [
    {
      "direccion": "Av San Juan 1100",
      "piso_depto": "2A",
      "created_at": "2026-01-29T00:13:31.040107+00:00",
      "last_used": "2026-01-29T00:13:31.040107+00:00"
    }
  ]
  ```

- `Update_at`: ISO timestamp string

Deletion semantics:
- Delete by index of the list the user sees (Q13=A, Q29=A).
- Remove that object from the JSON array.
- Write back the updated JSON into `Direcciones_json`.
- Update `Update_at` to the current timestamp.

### 4) Confirmation and return to flow

After a successful delete:
- Send:

`Direccion eliminada: <direccion> (<piso_depto>)`

(If `piso_depto` is empty, omit it from the confirmation string.)

Then:
- If the deleted address was currently selected in the conversation, reset the related fields (direccion/piso_depto) (Q27=C).
- Return to the address-selection step and show the updated list (plus "Otra Direccion").
- If 0 saved addresses remain, skip the list and proceed as if the user selected "Otra Direccion" (Q20=B).

### 5) Error handling

If Sheets deletion fails:
- Respond: `No pude eliminarla ahora, intenta mas tarde`
- Return to the address selection list (unchanged).

### 6) Logging

Log in application logs (info level): phone number, deleted address string, timestamp (Q14=A).

## Open questions

None.
