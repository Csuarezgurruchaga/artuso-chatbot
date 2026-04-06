import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.expensas_sheet_service import ExpensasSheetService

PROFILE_NAME = "administracion-artuso"


def _set_profile(profile_name: str = PROFILE_NAME):
    previous_profile = os.environ.get("COMPANY_PROFILE")
    os.environ["COMPANY_PROFILE"] = profile_name
    return previous_profile


def _restore_profile(previous_profile):
    if previous_profile is None:
        os.environ.pop("COMPANY_PROFILE", None)
    else:
        os.environ["COMPANY_PROFILE"] = previous_profile


def test_av_santa_fe_maps_to_santa_fe_code():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service._resolve_address_code("Santa Fe 2647") == 30
        assert service._resolve_address_code("Av Santa Fe 2647") == 30
        assert service._resolve_address_code("Av. Santa Fe 2647") == 30
        assert service._resolve_address_code("Av. Santa Fe 2647, CABA") == 30
    finally:
        _restore_profile(previous_profile)


def test_missing_av_prefix_still_maps():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service._resolve_address_code("Córdoba 785") == 9
        assert service._resolve_address_code("Av. Córdoba 785") == 9
    finally:
        _restore_profile(previous_profile)


def test_lavalle_1284_maps_to_code_14():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service._resolve_address_code("Lavalle 1284") == 14
    finally:
        _restore_profile(previous_profile)


def test_compact_street_number_maps_after_direct_match_fails():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service._resolve_address_code("Guemes3972") == 3
    finally:
        _restore_profile(previous_profile)


def test_address_synonyms_map_to_same_code():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        synonyms = {
            2: ["Drago 438", "Luis María Drago 438"],
            30: ["Av Santa Fe 2647", "Av. Santa Fe 2647", "Santa Fe 2647"],
            43: [
                "Santa Fe 2638",
                "Santa Fe 2636",
                "Santafe 2638",
                "Av Santa Fe 2638",
                "Av. Santa fe 2638",
                "Av.Santa Fe 2638",
            ],
            40: [
                "Ortiz de Ocampo 2561",
                "Ocampo 2561",
                "Ocampo2561",
            ],
            48: ["Palestina 580", "Estado de Palestina 580"],
            9: ["Av Cordoba 785", "Av. Córdoba 785", "Córdoba 785"],
            20: ["Amenabar 1415", "Amenabar 1421"],
            10: [
                "Av Entre Rios 1005",
                "Av. Entre Ríos 1005",
                "Entre Ríos 1005",
                "Entre Rios 1005",
            ],
            44: ["Rivadavia 4350", "Av Rivadavia 4350", "Av. Rivadavia 4350"],
            8: [
                "Perón 1875",
                "Tte. Gral. Juan Domingo Perón 1875",
                "Juan domingo Perón 1875",
                "J D Perón 1875",
                "J. D. Perón 1875",
                "Teniente Gral. Juan Domingo Perón 1875",
                "tte gral j d peron 1875",
            ],
            31: [
                "Perón 1617/21",
                "Tte. Gral. Juan Domingo Perón 1617",
                "Juan domingo Perón 1617",
                "J D Perón 1617",
                "J. D. Perón 1617",
                "Teniente Gral. Juan Domingo Perón 1617",
                "tte gral j d peron 1617",
                "Tte. Gral. Juan Domingo Perón 1621",
                "Juan domingo Perón 1621",
                "J D Perón 1621",
                "J. D. Perón 1621",
                "Teniente Gral. Juan Domingo Perón 1621",
                "tte gral j d peron 1621",
                "Tte. Gral. Juan Domingo Perón 1617/1621",
                "Juan domingo Perón 1617/1621",
                "J D Perón 1617/1621",
                "J. D. Perón 1617/1621",
                "Teniente Gral. Juan Domingo Perón 1617/1621",
                "tte gral j d peron 1617/1621",
            ],
            39: ["Uruguay 361", "Uruguay 369", "Uruguay 361/69"],
        }

        for code, variants in synonyms.items():
            for variant in variants:
                assert service._resolve_address_code(variant) == code
    finally:
        _restore_profile(previous_profile)


def test_canonical_addresses_are_explicit():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service.get_canonical_address(8) == "Tte. Gral. Juan Domingo Perón 1875"
        assert service.get_canonical_address(21) == "Tte. Gral. Juan Domingo Perón 2248/50"
        assert service.get_canonical_address(26) == "Av. Pueyrredón 873/75"
        assert service.get_canonical_address(30) == "Av. Santa Fe 2647"
        assert service.get_canonical_address(31) == "Tte. Gral. Juan Domingo Perón 1617/21"
        assert service.get_canonical_address(39) == "Uruguay 361/69"
        assert service.get_canonical_address(43) == "Av. Santa Fe 2636/38"
        assert service.get_canonical_address(44) == "Av. Rivadavia 4350"
    finally:
        _restore_profile(previous_profile)


def test_fuzzy_suggestions_use_only_canonical_addresses():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service.get_fuzzy_address_suggestions("Peorn 1875") == [
            "Tte. Gral. Juan Domingo Perón 1875"
        ]
        assert service.get_fuzzy_address_suggestions("Gueemes 3972") == [
            "Güemes 3972"
        ]
    finally:
        _restore_profile(previous_profile)


def test_fuzzy_suggestions_require_exact_number_overlap():
    previous_profile = _set_profile()
    try:
        service = ExpensasSheetService()
        assert service.get_fuzzy_address_suggestions("Peron 1877") == []
        assert service.get_fuzzy_address_suggestions("Peron 1621") == [
            "Tte. Gral. Juan Domingo Perón 1617/21"
        ]
    finally:
        _restore_profile(previous_profile)


if __name__ == "__main__":
    test_av_santa_fe_maps_to_santa_fe_code()
    test_missing_av_prefix_still_maps()
    test_lavalle_1284_maps_to_code_14()
    test_compact_street_number_maps_after_direct_match_fails()
    test_address_synonyms_map_to_same_code()
    test_canonical_addresses_are_explicit()
    test_fuzzy_suggestions_use_only_canonical_addresses()
    test_fuzzy_suggestions_require_exact_number_overlap()
    print("OK")
