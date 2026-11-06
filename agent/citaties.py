"""Uit welke cel komt een getal in het antwoord? (#365, #415)

Elk gecontroleerd getal in een dataantwoord krijgt een citatie, zodat hetzelfde antwoord
altijd hetzelfde aantal heeft. Een getal dat als meetwaarde in een toolstap staat, linkt
naar die stap: bron, maat, eenheid en de rij waarin het staat, in woorden. Staat het in
meer selecties, dan wijst de zin er een aan (CH-08, agent/claimbinding.py). Staat
het alleen als code, rijtelling of stuk van een key in de uitvoer, of nergens, dan zegt de
citatie dat de herkomst niet is vastgesteld. Het model schrijft zelf geen markering.

Een getal met een decimale komma valt buiten de getalcontrole. Geeft een bron afgeronde decimalen als meetwaarde
(de financien en WOPI, #956: solvabiliteit 0,69, 6.184,36 fte), dan krijgt zo'n getal een citatie als het als
waarde van een meetwaarde in een stap staat; een ander getal met komma blijft zonder citatie, zoals tot nu toe.

Een geheel getal onder 1.000 valt ook buiten de getalcontrole. Bij dezelfde bronnen (financien, WOPI en de
Studiekeuzedatabase, #963: capaciteit 71) krijgt het een citatie onder drie voorwaarden: het is exact de waarde van
een meetwaarde, de zin of tabelrij noemt haar selectie in woorden (opleiding, instelling, bestuur) en bij twijfel gaat
die alleen tussen rijen van dezelfde maat. Een klein getal is vaak toeval ("2 opleidingen", "15 januari"); zo bindt
het alleen waar de zin zegt waarover het gaat. En elk voorkomen van dat getal in de tekst moet zo binden, anders geen
enkel: de frontend geeft het k-de voorkomen van een getal de k-de citatie met dat getal (frontend/src/citations.js).
"""

from collections import defaultdict

from tools import LABELS, store
from tools.kolomlabel import kolomlabel

from .binding import zin_op
from .claimbinding import betekenis, kenmerken, kies, noemt_selectie
from .grounding import decimalen_met_positie, getallen_met_positie, kleine_getallen_met_positie
from .meetwaarden import Meetwaarde, eenheden, meetwaarden, schrijft
from .selectie import SCHEIDING as _SCHEIDING
from .selectie import bron_in_woorden, data_keys, keten, laadkey


def _bron(data_key: str | None, tool: str) -> str:
    """De bron in woorden: DUO · <catalogustitel>; zonder bekende key het label van de stap."""
    known = store.meta(laadkey(data_key)) if data_key else None
    if known is None:
        return LABELS.get(tool, tool)
    return bron_in_woorden(known)


def _citatie(geschreven: str, stap: int, tool: str, waarde: Meetwaarde, eenheid: dict[str, str]) -> dict:
    return {
        "getal": geschreven,
        "vastgesteld": True,
        "stap": stap,
        "tool": tool,
        "label": LABELS.get(tool, tool),
        "bron": waarde.bron or _bron(waarde.data_key, tool),
        "maat": kolomlabel(waarde.maat),
        **({"eenheid": e} if (e := waarde.eenheid or eenheid.get(waarde.maat)) else {}),
        **({"selectie": _SCHEIDING.join(waarde.selectie)} if waarde.selectie else {}),
        **({"data_key": waarde.data_key} if waarde.data_key else {}),
    }


def _dichtst_bij_de_bron(kandidaten: list[tuple[int, str, Meetwaarde]]) -> tuple[int, str, Meetwaarde] | None:
    """Bronhiërarchie bij twijfel (CH-38): staan alle kandidaten in één afleidingsketen, dan
    wint de stap die het dichtst bij de bron zit, zoals de selectie onder een analyse.
    Losse selecties (instelling A en B) blijven twijfel: daar beslist de zin (CH-08)."""
    for kandidaat in kandidaten:
        if (key := kandidaat[2].data_key) and all((ander := k[2].data_key) and key in keten(ander) for k in kandidaten):
            return kandidaat
    return None


def _onbepaald(geschreven: str, kandidaten: list) -> dict:
    """Geen herkomst: het getal staat niet als meetwaarde in de data, of meer dan eens zonder dat de zin kiest."""
    return {"getal": geschreven, "vastgesteld": False, "reden": "meerdere" if kandidaten else "geen_meetwaarde"}


def citaties(tekst: str, steps: list[tuple[str, str]]) -> list[dict]:
    """Per voorkomen van een gecontroleerd getal in `tekst` een citatie, in tekstvolgorde; leeg als de
    beurt geen data las. Hetzelfde getal in twee zinnen kan twee bronnen hebben (CH-08)."""
    results = [result for _, result in steps]
    waarden = [(stap, tool, meetwaarden(result, tool)) for stap, (tool, result) in enumerate(steps, 1)]
    if not data_keys(results) and not any(w for _, _, w in waarden):
        return []
    eenheid = {k: v for result in results for k, v in eenheden(result).items()}
    gevonden: list[tuple[int, dict]] = []
    for geschreven, cijfers, positie in getallen_met_positie(tekst):
        # Niet de eerste stap met dit getal: de zin wijst de selectie aan (CH-08).
        kandidaten = [(s, t, w) for s, t, ws in waarden for w in ws if cijfers in w.cijfers]
        gevonden.append((positie, _gebonden(geschreven, kandidaten, tekst, positie, eenheid)))
    for geschreven, decimaal, positie in decimalen_met_positie(tekst):
        if kandidaten := [(s, t, w) for s, t, ws in waarden for w in ws if schrijft(w, decimaal)]:
            gevonden.append((positie, _gebonden(geschreven, kandidaten, tekst, positie, eenheid)))
    gevonden += _klein(tekst, waarden, eenheid)
    return [citatie for _, citatie in sorted(gevonden, key=lambda g: g[0])]


def _een_maat(kandidaten: list[tuple[int, str, Meetwaarde]]) -> tuple[int, str, Meetwaarde] | None:
    """Twijfel bij een klein getal: alleen tussen rijen van dezelfde maat beslist de bronhiërarchie (71 plaatsen in
    2026 en in 2027); tussen twee maten (40 studenten, 40 eerstejaars) is het toeval."""
    return _dichtst_bij_de_bron(kandidaten) if len({k[2].maat for k in kandidaten}) == 1 else None


def _klein(tekst: str, waarden: list, eenheid: dict[str, str]) -> list[tuple[int, dict]]:
    """De citaties van gehele getallen onder 1.000 (#963): exact een meetwaarde met `decimaal`, de selectie in de zin,
    en voor elk voorkomen van hetzelfde getal, of voor geen."""
    per_getal: dict[str, list[tuple[int, dict | None]]] = defaultdict(list)
    for geschreven, cijfers, positie in kleine_getallen_met_positie(tekst):
        exact = int(cijfers)
        kandidaten = [(s, t, w) for s, t, ws in waarden for w in ws if w.decimaal is not None and w.decimaal == exact]
        zin = zin_op(tekst, positie)
        bron = kies(kandidaten, lambda k: betekenis(k[2]), lambda k: kenmerken(k[2]), zin, voorkeur=_een_maat)
        citatie = _citatie(geschreven, *bron, eenheid) if bron and noemt_selectie(zin, bron[2]) else None
        per_getal[geschreven].append((positie, citatie))
    return [(p, c) for groep in per_getal.values() if all(c for _, c in groep) for p, c in groep if c]


def _gebonden(geschreven: str, kandidaten: list, tekst: str, positie: int, eenheid: dict[str, str]) -> dict:
    """De citatie van één voorkomen: de kandidaat die de zin aanwijst, of de herkomst is niet vastgesteld."""
    bron = kies(
        kandidaten,
        lambda k: betekenis(k[2]),
        lambda k: kenmerken(k[2]),
        zin_op(tekst, positie),
        voorkeur=_dichtst_bij_de_bron,
    )
    return _citatie(geschreven, *bron, eenheid) if bron else _onbepaald(geschreven, kandidaten)
