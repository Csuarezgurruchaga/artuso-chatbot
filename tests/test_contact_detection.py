import os

from config.company_profiles import get_active_company_profile, get_company_info_text
from services.nlu_service import NLUService


def _set_profile(name: str):
    previous = os.environ.get("COMPANY_PROFILE")
    os.environ["COMPANY_PROFILE"] = name
    return previous


def _restore_profile(previous):
    if previous is None:
        os.environ.pop("COMPANY_PROFILE", None)
    else:
        os.environ["COMPANY_PROFILE"] = previous


def test_contact_detection_keywords():
    service = NLUService()
    assert service.detectar_consulta_contacto("información de contacto")
    assert service.detectar_consulta_contacto("telefono de la administracion")
    assert service.detectar_consulta_contacto("quiero llamar")
    assert service.detectar_consulta_contacto("tienen wsp?")
    assert service.detectar_consulta_contacto("cual es el mail?")
    assert service.detectar_consulta_contacto("numero de contacto")
    assert service.detectar_consulta_contacto("email de contacto")
    assert service.detectar_consulta_contacto("numero para comunicarme")


def test_contact_detection_exclusions():
    service = NLUService()
    assert not service.detectar_consulta_contacto("numero de reclamo 123")
    assert not service.detectar_consulta_contacto("nro. de cuenta")
    assert not service.detectar_consulta_contacto("n° de expensas")


def test_contact_requires_channel_when_contact_word():
    service = NLUService()
    assert not service.detectar_consulta_contacto("contacto?")
    assert not service.detectar_consulta_contacto("necesito contacto")
    assert service.detectar_consulta_contacto("contacto por whatsapp")


def test_comunicarme_routes_to_handoff_without_channel():
    service = NLUService()
    assert service.detectar_solicitud_humano("quiero comunicarme")
    assert not service.detectar_consulta_contacto("quiero comunicarme")
    assert not service.detectar_solicitud_humano("quiero comunicarme por whatsapp")
    assert service.detectar_consulta_contacto("quiero comunicarme por whatsapp")


def test_human_intent_priority_patterns():
    service = NLUService()
    assert service.detectar_solicitud_humano("quiero hablar con una persona")


def test_contact_response_uses_contact_message():
    previous = _set_profile("administracion-artuso")
    try:
        service = NLUService()
        expected = get_active_company_profile()["contact_message"]
        assert service.generar_respuesta_contacto("cual es el telefono?") == expected
    finally:
        _restore_profile(previous)


def test_contact_response_fallback():
    previous = _set_profile("empresa_ejemplo")
    try:
        service = NLUService()
        assert service.generar_respuesta_contacto("cual es el telefono?") == get_company_info_text()
    finally:
        _restore_profile(previous)
