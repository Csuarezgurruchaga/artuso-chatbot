# ACCEPTANCE: Delete saved address from WhatsApp (Expensas)

- [ ] When the bot shows saved addresses + "Otra Direccion", it includes the line:
  - `Responde con el numero de la opcion o escribe "eliminar", para borrar una direccion.`

- [ ] If the user replies `eliminar` at that step, the bot:
  - enters delete mode without calling NLU
  - lists only saved addresses (no "Otra Direccion")
  - prompts: `Escribi el numero de la direccion que queres eliminar o "cancelar".`

- [ ] In delete mode:
  - [ ] `cancelar` or `volver` exits delete mode and returns to the normal address selection list.
  - [ ] Valid numbers delete the selected address by index.
  - [ ] Invalid input re-prompts with the same message.

- [ ] Deletion is persisted in Google Sheets "Expensas" -> tab `CLIENTES` by:
  - [ ] removing the selected object from the JSON array in `Direcciones_json`
  - [ ] updating `Update_at`

- [ ] After successful deletion the bot sends:
  - `Direccion eliminada: <direccion> (<piso_depto>)` (piso optional)
  - then returns to the updated selection list.

- [ ] If deletion leaves 0 saved addresses, the flow proceeds as if the user chose "Otra Direccion" (no empty list is shown).

- [ ] If the deleted address was selected in the current conversation, the selected fields are reset before continuing.

- [ ] On Sheets errors, the bot responds `No pude eliminarla ahora, intenta mas tarde` and returns to the selection list.

- [ ] A runnable test script exists and passes:
  - `python tests/test_delete_saved_address.py`
