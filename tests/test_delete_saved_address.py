import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from chatbot.models import EstadoConversacion, TipoConsulta
from chatbot.rules import ChatbotRules
from chatbot.states import conversation_manager
from services.clients_sheet_service import clients_sheet_service


def _setup(phone: str, direcciones: list[dict]):
    conversation_manager.reset_conversacion(phone)
    conv = conversation_manager.get_conversacion(phone)
    conv.estado = EstadoConversacion.RECOLECTANDO_SECUENCIAL
    conv.tipo_consulta = TipoConsulta.PAGO_EXPENSAS
    conversation_manager.set_datos_temporales(phone, "_direccion_seleccion_contexto", "expensas")
    conversation_manager.set_datos_temporales(phone, "_direcciones_guardadas", direcciones)
    return conv


class _ClientsPatch:
    def __init__(self, initial: list[dict]):
        self.store = {"direcciones": list(initial)}
        self._orig_get = clients_sheet_service.get_direcciones
        self._orig_remove = clients_sheet_service.remove_direccion

    def __enter__(self):
        def fake_get(_telefono: str):
            return list(self.store["direcciones"])

        def fake_remove(_telefono: str, idx: int):
            if idx < 0 or idx >= len(self.store["direcciones"]):
                return False
            self.store["direcciones"].pop(idx)
            return True

        clients_sheet_service.get_direcciones = fake_get
        clients_sheet_service.remove_direccion = fake_remove
        return self

    def __exit__(self, exc_type, exc, tb):
        clients_sheet_service.get_direcciones = self._orig_get
        clients_sheet_service.remove_direccion = self._orig_remove


def test_delete_from_selection_returns_updated_list():
    phone = "+5491100000001"
    initial = [
        {"direccion": "Av San Juan 1100", "piso_depto": "2A"},
        {"direccion": "Av Entre Rios 177", "piso_depto": "2E"},
    ]
    _setup(phone, list(initial))

    with _ClientsPatch(initial):
        prompt = ChatbotRules._procesar_seleccion_direccion_text(phone, "eliminar")
        assert 'Escribi el numero de la direccion que queres eliminar o "cancelar".' in prompt

        resp = ChatbotRules._procesar_eliminar_direccion_text(phone, "1")
        assert resp is not None
        assert resp.startswith("Direccion eliminada:")
        assert "Av San Juan 1100" in resp
        # Should return to selection list with remaining address + "Otra Direccion"
        assert "Av Entre Rios 177" in resp
        assert "Otra Direccion" in resp
        assert 'o escribe "eliminar"' in resp


def test_cancel_returns_to_selection():
    phone = "+5491100000002"
    initial = [{"direccion": "Cochabamba 123", "piso_depto": ""}]
    _setup(phone, list(initial))

    with _ClientsPatch(initial):
        prompt = ChatbotRules._procesar_seleccion_direccion_text(phone, "eliminar")
        assert prompt is not None

        resp = ChatbotRules._procesar_eliminar_direccion_text(phone, "cancelar")
        assert resp is not None
        assert "Tengo estas direcciones guardadas:" in resp
        assert "Cochabamba 123" in resp
        assert "Otra Direccion" in resp


def test_invalid_input_repompts_delete_prompt():
    phone = "+5491100000003"
    initial = [{"direccion": "Rivadavia 4350", "piso_depto": ""}]
    _setup(phone, list(initial))

    with _ClientsPatch(initial):
        prompt = ChatbotRules._procesar_seleccion_direccion_text(phone, "eliminar")
        assert prompt is not None

        resp = ChatbotRules._procesar_eliminar_direccion_text(phone, "hola")
        assert resp is not None
        assert 'Escribi el numero de la direccion que queres eliminar o "cancelar".' in resp

        resp = ChatbotRules._procesar_eliminar_direccion_text(phone, "9")
        assert resp is not None
        assert 'Escribi el numero de la direccion que queres eliminar o "cancelar".' in resp


def test_delete_last_address_goes_to_manual_input():
    phone = "+5491100000004"
    initial = [{"direccion": "Av Corrientes 1234", "piso_depto": ""}]
    _setup(phone, list(initial))

    with _ClientsPatch(initial):
        prompt = ChatbotRules._procesar_seleccion_direccion_text(phone, "eliminar")
        assert prompt is not None

        resp = ChatbotRules._procesar_eliminar_direccion_text(phone, "1")
        assert resp is not None
        # When no saved addresses remain, continue as "Otra Direccion" (ask for address).
        assert "¿A qué dirección corresponde el pago?" in resp


if __name__ == "__main__":
    test_delete_from_selection_returns_updated_list()
    test_cancel_returns_to_selection()
    test_invalid_input_repompts_delete_prompt()
    test_delete_last_address_goes_to_manual_input()
    print("OK")

