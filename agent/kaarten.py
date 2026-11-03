"""De kaarten die een beurt van het gesprek tekende, zoals het rapport ze noemt (#648, ADR-009).

Een beurt bewaart wat het model vroeg (`tool_calls`) en de figuren die lukten. Hieruit volgt per data_key de kaart
met alleen de velden van de kaartregel: niet de titel (tekst van het model) en niet `data` (rijen buiten de store),
want het rapport zou ze herhalen en via zijn toolresultaat telden ze dan toch als bewijs (#211). Dezelfde velden gaan
per beurt naar `beurtbewijs`, zodat een heropend gesprek zijn kaarten terugkrijgt.
"""

import json

from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP

KAARTREGEL_ARGUMENTEN = ("data_key", "location_col", "value_col", "level")


def kaartregel_argumenten(kaart: dict) -> dict:
    """Van een kaartaanroep alleen wat de kaartregel van het rapport noemt."""
    return {k: kaart[k] for k in KAARTREGEL_ARGUMENTEN if k in kaart}


def kaarten_van_beurt(turn: dict) -> dict[str, dict]:
    """Per data_key de laatste kaart die deze beurt tekende (#648).

    Een onleesbare aanroep slaat ze over, en ook een aanroep die geen kaart opleverde: de beurt bewaart wat het
    model vroeg, niet wat lukte. Of een kaart lukte blijkt uit de layout.meta van haar figuren.
    """
    getekend = _getekende_kaarten(turn)
    kaarten: dict[str, dict] = {}
    for call in turn.get("tool_calls") or []:
        if call.get("name") != TOOL_CREATE_CHOROPLETH_MAP:
            continue
        try:
            args = json.loads(call.get("arguments") or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(args, dict) or not isinstance(args.get("data_key"), str):
            continue
        if (args.get("location_col"), args.get("value_col")) in getekend:
            kaarten[args["data_key"]] = kaartregel_argumenten(args)
    return kaarten


def _getekende_kaarten(turn: dict) -> set[tuple]:
    """(location_col, value_col) van elke kaart die deze beurt tekende, uit de layout.meta van haar figuren."""
    getekend: set[tuple] = set()
    for figuur in turn.get("figures") or []:
        meta = getattr(getattr(figuur, "layout", None), "meta", None)
        if isinstance(meta, dict) and meta.get("type") == "choropleth":
            getekend.add((meta.get("location_col"), meta.get("value_col")))
    return getekend


def kaarten_in_gesprek(session: dict) -> dict[str, dict]:
    """Per data_key de laatste kaart van het gesprek: eerst die uit een heropend gesprek, dan die van de beurten.

    De herkomst van een dataset noemt alleen de aanroepen die de data maakten, niet de kaart erop; zonder deze regel
    weet het rapport niet dat er een kaart was, of met welke kolommen."""
    kaarten = dict(session.get("kaarten") or {})
    for turn in session.get("turns") or []:
        kaarten.update(kaarten_van_beurt(turn))
    return kaarten
