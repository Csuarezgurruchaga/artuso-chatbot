from chatbot.rules import ChatbotRules


def test_match_service_option_synonyms():
    assert ChatbotRules._match_service_option("destapacion") == "Destapación"
    assert ChatbotRules._match_service_option("filtración") == "Filtracion/Humedad"
    assert ChatbotRules._match_service_option("humedad") == "Filtracion/Humedad"
    assert ChatbotRules._match_service_option("pintura") == "Pintura"
    assert ChatbotRules._match_service_option("pintar pared") == "Pintura"
    assert ChatbotRules._match_service_option("ruidos molestos") == "Ruidos Molestos"
    assert ChatbotRules._match_service_option("otro") == "Otro reclamo"
