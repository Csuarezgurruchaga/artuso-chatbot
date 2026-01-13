from chatbot.models import EstadoConversacion, TipoConsulta
from chatbot.rules import ChatbotRules
from chatbot.states import conversation_manager


def test_extraer_piso_depto_uf():
    direccion, piso = ChatbotRules._extraer_piso_depto_de_direccion(
        "Av entre rios 1202 UF 11"
    )
    assert direccion == "Av entre rios 1202"
    assert piso == "UF 11"


def test_reclamo_sugerencia_uf_en_ubicacion():
    numero = "messenger:test_uf"
    conversation_manager.reset_conversacion(numero)
    conversation_manager.set_tipo_consulta(numero, TipoConsulta.SOLICITAR_SERVICIO)
    conversation_manager.update_estado(numero, EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    conversation_manager.set_datos_temporales(numero, "tipo_servicio", "Pintura")

    respuesta = ChatbotRules._procesar_campo_secuencial(
        numero,
        "Av entre rios 1202 UF 11",
    )

    conversacion = conversation_manager.get_conversacion(numero)
    assert conversacion.datos_temporales.get("direccion_servicio") == "Av entre rios 1202"
    assert conversacion.datos_temporales.get("_piso_depto_sugerido") == "UF 11"
    assert "piso/depto: UF 11" in respuesta
