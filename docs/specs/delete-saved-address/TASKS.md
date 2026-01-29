# TASKS: Delete saved address from WhatsApp (Expensas)

- [ ] Extend the address-selection prompt copy to include: "Responde con el numero de la opcion o escribe \"eliminar\", para borrar una direccion."

- [ ] Add a new conversation state for delete mode and wire routing:
  - [ ] Detect exact keyword `eliminar` (case-insensitive) at the address-selection step (no NLU).
  - [ ] In delete mode, show only saved addresses and prompt for number or `cancelar`/`volver`.
  - [ ] Validate inputs; re-prompt on invalid/out-of-range.

- [ ] Implement Sheets deletion for tab `CLIENTES`:
  - [ ] Read `Direcciones_json` for `Telefono`.
  - [ ] Delete entry by index.
  - [ ] Write updated JSON and update `Update_at`.
  - [ ] Log deletion (phone, address, timestamp).

- [ ] Post-delete behavior:
  - [ ] Send confirmation message: "Direccion eliminada: <direccion> (<piso_depto>)" (omit piso if empty).
  - [ ] Reset conversation selected fields if the deleted address was selected.
  - [ ] Return to updated list; if no saved addresses remain, proceed as if "Otra Direccion".

- [ ] Error handling:
  - [ ] On Sheets failure, respond "No pude eliminarla ahora, intenta mas tarde" and return to selection list.

- [ ] Tests:
  - [ ] Add `tests/test_delete_saved_address.py` runnable via `python tests/test_delete_saved_address.py` (no pytest).
  - [ ] Run `python tests/test_delete_saved_address.py`.
