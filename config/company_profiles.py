import os
from typing import Dict, Any

# Perfiles de empresas configurables
COMPANY_PROFILES = {
    "argenfuego": {
        "name": "Argenfuego",
        "bot_name": "Eva",
        "phone": {"public_phone":"4567-8900", "mobile_phone":"11-3906-1038", "emergency_phone":"11-3906-1038"},
        "address": "Av. Hipólito Yrigoyen 2020, El Talar, Provincia de Buenos Aires",
        "hours": "Lunes a Viernes de 8 a 17hs y Sábados de 9 a 13hs",
        "email": "argenfuego@yahoo.com.ar",
        "email_bot": "bot@argenfuego.com",
        "website": "www.argenfuego.com"
    },
    "empresa_ejemplo": {
        "name": "Empresa Ejemplo",
        "bot_name": "Asistente",
        "phone": "+54 11 0000-0000",
        "address": "Dirección ejemplo",
        "hours": "Horarios ejemplo",
        "email": "info@ejemplo.com",
        "email_bot": "bot@ejemplo.com",
        "website": "www.ejemplo.com"
    },
    "administracion-artuso": {
        "name": "Administracion Artuso",
        "bot_name": "Artu",
        "phone": "+54 11 0000-0000",
        "address": "Direccion pendiente",
        "hours": "Horarios pendientes",
        "email": "admin@artuso.com",
        "contact_message": (
            "Gracias por comunicarte con Administración Artuso.\n"
            "Podés contactarnos por los siguientes canales:\n"
            "\n"
            "📞 Teléfonos\n"
            "4953-3018 / 4953-0577\n"
            "🕘 Lunes a viernes de 11:00 a 13:00 y de 14:00 a 16:00\n"
            "\n"
            "📱 WhatsApp\n"
            "11-5348-8741\n"
            "🕘 Lunes a viernes de 11:00 a 16:00\n"
            "\n"
            "✉️ Correo electrónico\n"
            "• Para asuntos administrativos o reclamos: recepcion.adm.artuso@gmail.com\n"
            "• Para temas relacionados con pago de expensas: artusoexpensas2@gmail.com"
        ),
        "email_bot": "bot@argenfuego.com",
        "website": "",
        "expensas_address_map": {
            2: "Drago 438",
            3: "Güemes 3972",
            4: "Sarmiento 1922",
            7: "Mario Bravo 24",
            8: "Perón 1875",
            9: "Av. Córdoba 785",
            10: "Av. Entre Ríos 1005",
            11: "Paraguay 2957",
            13: "Paraguay 2640",
            14: "Lavalle 1282",
            15: "Charcas 3962",
            17: "Viel 247",
            20: "Amenabar 1415",
            21: "Perón 2248",
            22: "Formosa 6/10/14/16",
            23: "Paraguay 2949",
            25: "Aráoz 380",
            26: "Pueyrredón 873/75",
            27: "Paraguay 2975",
            29: "Lezica 4355",
            30: "Santa Fe 2647",
            31: "Perón 1617/21",
            32: "Paraguay 2943",
            33: "Billinghurst 2490",
            34: "Junín 1586",
            39: "Uruguay 361",
            40: "Ortiz de Ocampo 2561",
            41: "Boyacá 620",
            42: "Suipacha 1226",
            43: "Santa Fe 2638",
            44: "Rivadavia 4350",
            48: "Palestina 580",
        },
    }
}

def get_active_company_profile() -> Dict[str, Any]:
    """
    Obtiene el perfil de empresa activo desde variable de entorno
    """
    profile_name = os.getenv('COMPANY_PROFILE').lower()
    
    if profile_name not in COMPANY_PROFILES:
        raise ValueError(f"Perfil de empresa '{profile_name}' no encontrado. Perfiles disponibles: {list(COMPANY_PROFILES.keys())}")
    
    return COMPANY_PROFILES[profile_name]

def get_company_info_text() -> str:
    """
    Genera texto formateado con información de contacto de la empresa activa
    """
    profile = get_active_company_profile()
    
    # Manejar tanto formato de teléfono dict como string para compatibilidad
    phone_text = ""
    if isinstance(profile['phone'], dict):
        phone_parts = []
        if profile['phone'].get('public_phone'):
            phone_parts.append(f"📞 {profile['phone']['public_phone']}")
        if profile['phone'].get('mobile_phone'):
            phone_parts.append(f"📱 {profile['phone']['mobile_phone']}")
        phone_text = " | ".join(phone_parts)
    else:
        phone_text = f"📱 {profile['phone']}"
    
    info_text = f"""📞 *{profile['name']}* - Información de Contacto

🏢 *Empresa:* {profile['name']}
{phone_text}
📍 *Dirección:* {profile['address']}
🕒 *Horarios:* {profile['hours']}
📧 *Email:* {profile['email']}"""

    if profile.get('website'):
        info_text += f"\n🌐 *Web:* {profile['website']}"
    
    return info_text

def get_company_services_text() -> str:
    """
    Genera texto formateado con servicios de la empresa activa
    """
    profile = get_active_company_profile()
    
    services_text = f"🔧 *Nuestros Servicios:*\n\n"
    for i, service in enumerate(profile['services'], 1):
        services_text += f"{i}. {service}\n"
    
    return services_text.strip()

def get_urgency_redirect_message() -> str:
    """
    Genera mensaje de redirección inmediata para urgencias con números de teléfono
    """
    profile = get_active_company_profile()
    
    urgency_text = f"""🚨 *URGENCIA DETECTADA* 🚨

Para atención inmediata de urgencias, por favor comunícate directamente por teléfono:

📞 *Teléfono fijo:* {profile['phone']['public_phone']}
📱 *Celular de emergencias:* {profile['phone']['emergency_phone']}

🕒 *Horarios:* {profile['hours']}

⚡ *Para urgencias fuera de horario, llama al celular.*

Nuestro equipo técnico te atenderá de inmediato para resolver tu problema.

_Gracias por contactar a {profile['name']}_ 🔥"""
    
    return urgency_text
