import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.nlu_service import nlu_service, NLUService


EXAMPLES = [
    "Av entre Ríos 2020 2E unidad funcional 2"
    # "Sarmiento1922 4toA",
    # "Lavalle 1282 piso 1 oficina 8 y 10",
    # "Lavalle 1282 1 piso of 1",
    # "Lavalle 1282, uf 27, uf 28 y",
    # "Calle Sarmiento 1922 2° A Unidad funcional 6 a nombre de Diego Alberto Vicente",
    # "Calle Paraguay 2957, departamento 7D. Barrios Recoleta, Ciudad autónoma de Buenos Aires,",
    # "Guemes 3972 Piso 9o Dto B",
    # "Av.Santa Fe 2647 .. piso 2 depto D",
    # "Ortiz de Ocampo 2561, 2 A.",
]


def _require_env() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing env var OPENAI_API_KEY.")

    # Informative only (default exists in code).
    model = os.getenv("OPENAI_NLU_MODEL", "gpt-4o-mini")
    print(f"Using OPENAI_NLU_MODEL={model}")


def main() -> None:
    _require_env()

    for i, text in enumerate(EXAMPLES, start=1):
        parsed = nlu_service.extraer_direccion_unidad(text)
        direccion_altura = (parsed.get("direccion_altura") or "").strip()
        unidad = NLUService.construir_unidad_sugerida(parsed)

        print("=" * 80)
        print(f"[{i}] INPUT: {text}")
        print(f"direccion_altura: {direccion_altura!r}")
        print(f"unidad_sugerida:  {unidad!r}")
        print(f"raw_json: {parsed}")


if __name__ == "__main__":
    main()

