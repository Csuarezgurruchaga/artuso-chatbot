# PLAN: Delete saved address from WhatsApp (Expensas)

1) Identify the address-selection step in the expensas flow and extend the prompt copy to advertise `eliminar`.

2) Add a new conversation state for delete mode (e.g. `ELIMINANDO_DIRECCION_GUARDADA`) and route inbound messages:
   - If user sends `eliminar` while in the address-selection step, enter delete mode.
   - In delete mode, accept a number or `cancelar`/`volver`.

3) Implement deletion against Google Sheets tab `CLIENTES`:
   - Load the saved addresses JSON for the phone.
   - Delete by index.
   - Write back JSON and update `Update_at`.

4) After delete:
   - Confirm deletion.
   - If deleted address matches the currently selected one, reset conversation fields.
   - Return to updated address-selection list; if 0 remain, proceed as "Otra Direccion".

5) Add a runnable test script (no pytest) that exercises:
   - entering delete mode
   - deleting one address
   - cancel flow
   - invalid input re-prompt

6) Run the test script(s) and report results.
