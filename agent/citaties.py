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

Een getal in een tabelcel duidt niet de rij maar de kolomkop en de labelcellen van de rij ("Bachelor", "2020/21";
agent/mdtabel.Cel, #1002), zoals in de tabelcontrole (agent/tabelbinding.py). Wijzen die er niet één aan, dan geldt
eerst de bronhiërarchie en daarna de maat die de tekst vóór de tabel het laatst noemt.

Een draaitabel van run_analysis (kolom Bachelor) staat naast de selectie waaruit ze komt, vaak als zusje op dezelfde
lading (M01). Is haar kolom een selectiecel van een rij uit dezelfde lading (Diplomasoort: Bachelor) en noemt ze niets
dat die rij niet ook noemt, dan is het die rij, gedraaid: de rij wint, zoals een selectie wint van de analyse erop
(CH-38). Een totaal met toevallig dezelfde waarde als een rij blijft twijfel.
"""

from bisect import bisect_right
from collections import defaultdict
from functools import partial

from tools import LABELS, store
from tools.kolomlabel import kolomlabel

from .binding import zin_op
from .claimbinding import betekenis, kenmerken, kies, laatst_genoemde_maat, noemt_selectie, selectiecellen
from .grounding import decimalen_met_positie, getallen_met_positie, kleine_getallen_met_positie
from .mdtabel import Cel, tabelcellen
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


def _in_een_keten(kandidaten: list[tuple[int, str, Meetwaarde]]) -> tuple[int, str, Meetwaarde] | None:
    if len(kandidaten) == 1:
        return kandidaten[0]
    for kandidaat in kandidaten:
        if (key := kandidaat[2].data_key) and all((ander := k[2].data_key) and key in keten(ander) for k in kandidaten):
            return kandidaat
    return None


def _zelfde_lading(a: Meetwaarde, b: Meetwaarde) -> bool:
    return bool(a.data_key and b.data_key) and laadkey(a.data_key) == laadkey(b.data_key)


def _draaitabelcel_van(cel: Meetwaarde, rij: Meetwaarde) -> bool:
    """`cel` is `rij`, gedraaid (#1002): uit dezelfde lading, haar kolom is een selectiecel van de rij (Bachelor uit
    Diplomasoort: Bachelor) en ze noemt niets wat de rij niet ook noemt. Een totaal (2020, Aantal) naast een rij
    (Hogeschool A, 2020, Aantal) is geen draaitabelcel: zijn kolom is de maat, geen selectiecel."""
    return kolomlabel(cel.maat) in selectiecellen(rij) and kenmerken(cel) < kenmerken(rij) and _zelfde_lading(cel, rij)


def _zonder_draaitabelcellen(kandidaten: list[tuple[int, str, Meetwaarde]]) -> list[tuple[int, str, Meetwaarde]]:
    """Zonder de draaitabelcellen van een andere kandidaat: de cel met kolom Bachelor (2020/'21, Bachelor) naast de
    rij (Diplomasoort: Bachelor, 2020/'21, Gediplomeerden). Losse selecties (instelling A en B) en een totaal naast
    een rij met toevallig dezelfde waarde blijven allemaal."""
    return [k for k in kandidaten if not any(_draaitabelcel_van(k[2], a[2]) for a in kandidaten)]


def _dichtst_bij_de_bron(kandidaten: list[tuple[int, str, Meetwaarde]]) -> tuple[int, str, Meetwaarde] | None:
    """Bronhiërarchie bij twijfel (CH-38): staan alle kandidaten in één afleidingsketen, dan
    wint de stap die het dichtst bij de bron zit, zoals de selectie onder een analyse. Anders wint
    de rij van wie een andere kandidaat een draaitabelcel uit dezelfde lading is (#1002).
    Losse selecties (instelling A en B) blijven twijfel: daar beslist de zin (CH-08)."""
    return _in_een_keten(kandidaten) or _in_een_keten(_zonder_draaitabelcellen(kandidaten))


def _in_tabel(kandidaten: list[tuple[int, str, Meetwaarde]], ervoor: str) -> tuple[int, str, Meetwaarde] | None:
    """Twijfel in een tabelcel: de bronhiërarchie, anders de maat die de tekst vóór de tabel het laatst noemt
    (agent/tabelbinding.py, #1002)."""
    if bron := _dichtst_bij_de_bron(kandidaten):
        return bron
    genoemd = laatst_genoemde_maat(kandidaten, lambda k: kolomlabel(k[2].maat), ervoor)
    return _dichtst_bij_de_bron(genoemd) if len(genoemd) < len(kandidaten) else None


def _onbepaald(geschreven: str, kandidaten: list) -> dict:
    """Geen herkomst: het getal staat niet als meetwaarde in de data, of meer dan eens zonder dat de zin kiest."""
    return {"getal": geschreven, "vastgesteld": False, "reden": "meerdere" if kandidaten else "geen_meetwaarde"}


def _cel_op(cellen: list[Cel], positie: int) -> Cel | None:
    """De cel om `positie`; de cellen staan in tekstvolgorde en overlappen niet."""
    i = bisect_right(cellen, positie, key=lambda cel: cel.begin) - 1
    return cellen[i] if i >= 0 and positie < cellen[i].einde else None


def _duiding(tekst: str, cellen: list[Cel], positie: int) -> tuple[str, Cel | None]:
    """Wat het getal op `positie` duidt: in een tabelcel de kop en labels van die cel, anders de zin (CH-08)."""
    cel = _cel_op(cellen, positie)
    return (cel.context, cel) if cel else (zin_op(tekst, positie), None)


def citaties(tekst: str, steps: list[tuple[str, str]]) -> list[dict]:
    """Per voorkomen van een gecontroleerd getal in `tekst` een citatie, in tekstvolgorde; leeg als de
    beurt geen data las. Hetzelfde getal in twee zinnen kan twee bronnen hebben (CH-08)."""
    results = [result for _, result in steps]
    waarden = [(stap, tool, meetwaarden(result, tool)) for stap, (tool, result) in enumerate(steps, 1)]
    if not data_keys(results) and not any(w for _, _, w in waarden):
        return []
    eenheid = {k: v for result in results for k, v in eenheden(result).items()}
    cellen = tabelcellen(tekst)
    gevonden: list[tuple[int, dict]] = []
    for geschreven, cijfers, positie in getallen_met_positie(tekst):
        # Niet de eerste stap met dit getal: de zin of de tabelcel wijst de selectie aan (CH-08, #1002).
        kandidaten = [(s, t, w) for s, t, ws in waarden for w in ws if cijfers in w.cijfers]
        gevonden.append((positie, _gebonden(geschreven, kandidaten, _duiding(tekst, cellen, positie), eenheid)))
    for geschreven, decimaal, positie in decimalen_met_positie(tekst):
        if kandidaten := [(s, t, w) for s, t, ws in waarden for w in ws if schrijft(w, decimaal)]:
            gevonden.append((positie, _gebonden(geschreven, kandidaten, _duiding(tekst, cellen, positie), eenheid)))
    gevonden += _klein(tekst, cellen, waarden, eenheid)
    return [citatie for _, citatie in sorted(gevonden, key=lambda g: g[0])]


def _een_maat(kandidaten: list[tuple[int, str, Meetwaarde]]) -> tuple[int, str, Meetwaarde] | None:
    """Twijfel bij een klein getal: alleen tussen rijen van dezelfde maat beslist de bronhiërarchie (71 plaatsen in
    2026 en in 2027); tussen twee maten (40 studenten, 40 eerstejaars) is het toeval."""
    return _dichtst_bij_de_bron(kandidaten) if len({k[2].maat for k in kandidaten}) == 1 else None


def _klein(tekst: str, cellen: list[Cel], waarden: list, eenheid: dict[str, str]) -> list[tuple[int, dict]]:
    """De citaties van gehele getallen onder 1.000 (#963): exact een meetwaarde met `decimaal`, de selectie in de zin
    of in de kop en labels van de tabelcel, en voor elk voorkomen van hetzelfde getal, of voor geen."""
    per_getal: dict[str, list[tuple[int, dict | None]]] = defaultdict(list)
    for geschreven, cijfers, positie in kleine_getallen_met_positie(tekst):
        exact = int(cijfers)
        kandidaten = [(s, t, w) for s, t, ws in waarden for w in ws if w.decimaal is not None and w.decimaal == exact]
        zin, _ = _duiding(tekst, cellen, positie)
        bron = kies(kandidaten, lambda k: betekenis(k[2]), lambda k: kenmerken(k[2]), zin, voorkeur=_een_maat)
        citatie = _citatie(geschreven, *bron, eenheid) if bron and noemt_selectie(zin, bron[2]) else None
        per_getal[geschreven].append((positie, citatie))
    return [(p, c) for groep in per_getal.values() if all(c for _, c in groep) for p, c in groep if c]


def _gebonden(geschreven: str, kandidaten: list, duiding: tuple[str, Cel | None], eenheid: dict[str, str]) -> dict:
    """De citatie van één voorkomen: de kandidaat die de zin of tabelcel aanwijst, of de herkomst is niet vastgesteld."""
    zin, cel = duiding
    voorkeur = partial(_in_tabel, ervoor=cel.ervoor) if cel else _dichtst_bij_de_bron
    bron = kies(kandidaten, lambda k: betekenis(k[2]), lambda k: kenmerken(k[2]), zin, voorkeur=voorkeur)
    return _citatie(geschreven, *bron, eenheid) if bron else _onbepaald(geschreven, kandidaten)
