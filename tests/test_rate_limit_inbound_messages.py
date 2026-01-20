import os
import sys

os.environ.setdefault("META_WA_ACCESS_TOKEN", "test_token")
os.environ.setdefault("META_WA_PHONE_NUMBER_ID", "123456789")
os.environ.setdefault("META_WA_APP_SECRET", "test_secret")
os.environ.setdefault("META_WA_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("HANDOFF_WHATSAPP_NUMBER", "+5491111111111")
os.environ.setdefault("COMPANY_PROFILE", "administracion-artuso")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.models import ConversacionData, EstadoConversacion
from main import _should_count_rate_limit


def _build_conv(state: EstadoConversacion, atendido: bool = False) -> ConversacionData:
    return ConversacionData(
        numero_telefono="test",
        estado=state,
        atendido_por_humano=atendido,
    )


def test_start_counts_first_message_non_hola():
    conv = _build_conv(EstadoConversacion.INICIO)
    assert _should_count_rate_limit(conv, "Necesito ayuda", True, False)


def test_hola_counts_en_esperando_opcion():
    conv = _build_conv(EstadoConversacion.ESPERANDO_OPCION)
    assert _should_count_rate_limit(conv, "hola", True, False)

def test_hola_con_puntuacion_cuenta():
    conv = _build_conv(EstadoConversacion.ESPERANDO_OPCION)
    assert _should_count_rate_limit(conv, "hola!", True, False)
    assert _should_count_rate_limit(conv, "¡hola!", True, False)

def test_saludos_abreviados_cuentan():
    conv = _build_conv(EstadoConversacion.ESPERANDO_OPCION)
    for msg in ["h", "alo", "ola", "holi", "holis"]:
        assert _should_count_rate_limit(conv, msg, True, False)


def test_typos_de_hola_cuentan():
    conv = _build_conv(EstadoConversacion.ESPERANDO_OPCION)
    for msg in ["hol", "holaa", "holaaa", "hloa", "hoal", "holá", "hola!!"]:
        assert _should_count_rate_limit(conv, msg, True, False)


def test_similares_no_cuentan():
    conv = _build_conv(EstadoConversacion.ESPERANDO_OPCION)
    assert not _should_count_rate_limit(conv, "hora", True, False)


def test_hola_mid_flujo_cuenta():
    conv = _build_conv(EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    assert _should_count_rate_limit(conv, "hola", True, False)


def test_mensaje_en_flujo_no_cuenta():
    conv = _build_conv(EstadoConversacion.RECOLECTANDO_SECUENCIAL)
    assert not _should_count_rate_limit(conv, "Av. Corrientes 1234", True, False)


def test_post_finalizado_no_cuenta():
    conv = _build_conv(EstadoConversacion.INICIO)
    assert not _should_count_rate_limit(conv, "hola", True, True)


def test_media_sin_caption_cuenta_inicio():
    conv = _build_conv(EstadoConversacion.INICIO)
    assert _should_count_rate_limit(conv, "", True, False)


def test_handoff_no_cuenta():
    conv = _build_conv(EstadoConversacion.RECOLECTANDO_SECUENCIAL, atendido=True)
    assert not _should_count_rate_limit(conv, "hola", True, False)


def test_volver_menu_no_cuenta():
    conv = _build_conv(EstadoConversacion.INICIO)
    assert not _should_count_rate_limit(conv, "volver al menu", True, False)


def test_no_whatsapp_no_cuenta():
    conv = _build_conv(EstadoConversacion.INICIO)
    assert not _should_count_rate_limit(conv, "hola", False, False)
