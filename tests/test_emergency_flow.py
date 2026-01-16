#!/usr/bin/env python3
import os

from chatbot.models import EstadoConversacion, TipoConsulta
from chatbot.rules import ChatbotRules
from chatbot.states import conversation_manager


TEST_NUMBER = "+5491100000000"


def _reset(phone: str):
    conversation_manager.reset_conversacion(phone)
    conversation_manager.recently_finalized.pop(phone, None)
    if phone in conversation_manager.handoff_queue:
        conversation_manager.handoff_queue.remove(phone)
    if conversation_manager.active_handoff == phone:
        conversation_manager.active_handoff = None


def test_emergency_initial_flow():
    os.environ["HANDOFF_EMERGENCY_WHATSAPP_NUMBER"] = "+5491156096511"
    _reset(TEST_NUMBER)
    resp = ChatbotRules.procesar_mensaje(TEST_NUMBER, "emergencia", "")
    assert "11-5609-6511" in (resp or "")
    assert TEST_NUMBER in conversation_manager.recently_finalized


def test_emergency_midflow_pause_and_resume():
    os.environ["HANDOFF_EMERGENCY_WHATSAPP_NUMBER"] = "+5491156096511"
    _reset(TEST_NUMBER)
    conversation_manager.update_estado(TEST_NUMBER, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    conversation_manager.set_tipo_consulta(TEST_NUMBER, TipoConsulta.PAGO_EXPENSAS)
    conversation_manager.set_datos_temporales(TEST_NUMBER, "direccion", "Av. Test 123")

    resp = ChatbotRules.procesar_mensaje(TEST_NUMBER, "urgencia", "")
    assert "11-5609-6511" in (resp or "")

    conv = conversation_manager.get_conversacion(TEST_NUMBER)
    assert conv.datos_temporales.get("_emergency_paused") is True
    assert conv.datos_temporales.get("direccion") == "Av. Test 123"

    resp_again = ChatbotRules.procesar_mensaje(TEST_NUMBER, "cualquier cosa", "")
    assert "11-5609-6511" in (resp_again or "")

    resp_resume = ChatbotRules.procesar_mensaje(TEST_NUMBER, "CONTINUAR", "")
    assert "Retomamos" in (resp_resume or "")
    conv = conversation_manager.get_conversacion(TEST_NUMBER)
    assert conv.datos_temporales.get("_emergency_paused") is False
    assert conv.estado == EstadoConversacion.RECOLECTANDO_SECUENCIAL


def test_number_three_midflow_is_not_emergency():
    os.environ["HANDOFF_EMERGENCY_WHATSAPP_NUMBER"] = "+5491156096511"
    _reset(TEST_NUMBER)
    conversation_manager.update_estado(TEST_NUMBER, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    conversation_manager.set_tipo_consulta(TEST_NUMBER, TipoConsulta.PAGO_EXPENSAS)
    resp = ChatbotRules.procesar_mensaje(TEST_NUMBER, "3", "")
    # Should not be treated as emergency; stay in flow (no finalize, no pause flag)
    conv = conversation_manager.get_conversacion(TEST_NUMBER)
    assert conv.estado == EstadoConversacion.RECOLECTANDO_SECUENCIAL
    assert conv.datos_temporales.get("_emergency_paused") is not True
    # Response is the normal prompt for that flow; ensure emergency text not present
    assert not resp or "Emergencia detectada" not in resp


def test_emergency_missing_number_no_response():
    _reset(TEST_NUMBER)
    os.environ.pop("HANDOFF_EMERGENCY_WHATSAPP_NUMBER", None)
    resp = ChatbotRules.procesar_mensaje(TEST_NUMBER, "emergencia", "")
    assert not resp
    conv = conversation_manager.get_conversacion(TEST_NUMBER)
    assert conv.estado == EstadoConversacion.ESPERANDO_OPCION or conv.estado == EstadoConversacion.INICIO


def test_emergency_while_in_handoff_keeps_queue():
    os.environ["HANDOFF_EMERGENCY_WHATSAPP_NUMBER"] = "+5491156096511"
    _reset(TEST_NUMBER)
    conversation_manager.update_estado(TEST_NUMBER, EstadoConversacion.ATENDIDO_POR_HUMANO)
    conv = conversation_manager.get_conversacion(TEST_NUMBER)
    conv.atendido_por_humano = True
    conversation_manager.handoff_queue.append(TEST_NUMBER)

    resp = ChatbotRules.procesar_mensaje(TEST_NUMBER, "emergencia", "")
    assert "11-5609-6511" in (resp or "")
    assert TEST_NUMBER in conversation_manager.handoff_queue


if __name__ == "__main__":
    test_emergency_initial_flow()
    test_emergency_midflow_pause_and_resume()
    test_emergency_missing_number_no_response()
    test_emergency_while_in_handoff_keeps_queue()
    print("Emergency tests passed.")
