"""De systeemprompt vraagt om kern eerst en koppen of lijsten bij een lang antwoord (#618)."""

import re
from pathlib import Path

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "system.md").read_text(encoding="utf-8")


def _sectie(kop: str) -> str:
    """De tekst onder een `## `- of `### `-kop, tot de volgende kop van gelijk of hoger niveau."""
    niveau = re.search(rf"^(#+) {re.escape(kop)}\s*$", _PROMPT, flags=re.MULTILINE)
    assert niveau, kop
    rest = _PROMPT[niveau.end() :]
    volgende = re.search(rf"^#{{1,{len(niveau.group(1))}}} ", rest, flags=re.MULTILINE)
    return rest[: volgende.start()] if volgende else rest


def test_een_lang_antwoord_begint_met_de_kern_en_krijgt_koppen_of_een_lijst():
    stijl = _sectie("Toon en stijl")
    regel = next(r for r in stijl.splitlines() if "kern" in r)

    assert "drie of meer onderdelen" in regel and "600 tekens" in regel
    assert "één of twee zinnen" in regel
    assert "`###`-kop" in regel and "lijst" in regel


def test_een_kort_antwoord_blijft_een_alinea_zonder_kop():
    regel = next(r for r in _sectie("Toon en stijl").splitlines() if "kern" in r)

    assert "blijft één alinea zonder kop" in regel


def test_de_getalregels_gelden_ook_in_koppen_en_lijsten():
    regel = next(r for r in _sectie("Toon en stijl").splitlines() if "kern" in r)

    assert "elk getal" in regel and "uit de data" in regel


def test_de_onderzoeksvraag_staat_bij_een_lang_antwoord_na_de_kern():
    tekst = _sectie("Onderzoeksvraag formalisering")

    assert "eerst de kern" in tekst
    assert "**Onderzoeksvraag:**" in tekst


def test_de_onderzoeksvraag_is_geen_citaatblok():
    """Een `>`-regel midden in het antwoord blijft een citaatblok; alleen een eerste blok wordt omgezet (#405)."""
    regels = [r for r in _sectie("Onderzoeksvraag formalisering").splitlines() if "Onderzoeksvraag:" in r]

    assert regels and not any(r.lstrip().startswith(">") for r in regels)
