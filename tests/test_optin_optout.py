#!/usr/bin/env python3

import os

from services.optin_service import optin_service


def main() -> None:
    if not optin_service.enabled:
        print("Opt-in deshabilitado (OPTIN_ENABLED=false).")
        return

    test_id = os.getenv("OPTIN_TEST_NUMBER", "").strip()
    if not test_id:
        print("Set OPTIN_TEST_NUMBER (ej: +5491112345678) para ejecutar este test manual.")
        return

    print("== OPT-IN PENDING ==")
    prompt = optin_service.start_optin("whatsapp", test_id)
    print(prompt or "No se pudo enviar el prompt.")

    print("\n== RESPUESTA SI ==")
    handled, reply = optin_service.handle_inbound_message(test_id, "SI")
    print(f"handled={handled} reply={reply}")

    print("\n== OPT-OUT BAJA ==")
    handled, reply = optin_service.handle_inbound_message(test_id, "BAJA")
    print(f"handled={handled} reply={reply}")

    print("\n== RE-SUSCRIPCION ALTA ==")
    handled, reply = optin_service.handle_inbound_message(test_id, "ALTA")
    print(f"handled={handled} reply={reply}")


if __name__ == "__main__":
    main()
