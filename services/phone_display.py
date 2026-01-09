from typing import Optional


def format_phone_for_agent(phone: Optional[str]) -> Optional[str]:
    """
    Formatea el numero para mostrarlo al agente.
    - Remueve +54 y el 9 de moviles.
    - Si es CABA (11 + 8 digitos), usa formato "11 1234-5678".
    """
    if not phone:
        return phone

    if phone.startswith("messenger:"):
        return phone

    digits = "".join(char for char in phone if char.isdigit())
    if not digits:
        return phone

    if digits.startswith("54") and len(digits) > 10:
        digits = digits[2:]

    if digits.startswith("9") and len(digits) > 10:
        digits = digits[1:]

    if len(digits) == 10 and digits.startswith("11"):
        return f"{digits[:2]} {digits[2:6]}-{digits[6:]}"

    return digits
