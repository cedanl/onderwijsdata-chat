"""Past de selectie waarop een antwoord rust bij wat de vraag noemt? (#187, #143)

Het model koos soms het jaar vóór het gevraagde schooljaar, of de code van een
andere instelling (30TX, Aeres, voor Hogeschool Utrecht). De getallen die het
daarna gaf staan wél in de tooluitvoer, dus de getalcontrole ziet het niet. Deze
controles vergelijken wat de vraag noemt met wat de selecties van de beurt
bevatten (KeyMeta, #193).
"""

import json

from tools import instelling, periode, store
from tools.store import KeyMeta


def _data_keys(tool_results: list[str]) -> list[str]:
    keys = []
    for result in tool_results:
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("data_key"), str):
            keys.append(parsed["data_key"])
    return keys


def _root(key: str) -> str:
    """De laadkey waar een afgeleide key uiteindelijk vandaan komt."""
    seen = {key}
    while (known := store.meta(key)) and known.afgeleid_van and known.afgeleid_van not in seen:
        key = known.afgeleid_van
        seen.add(key)
    return key


def _selecties(tool_results: list[str], veld: str) -> dict[str, set]:
    """Per laadkey: de waarden van `veld` over alle selecties van de beurt die het weten."""
    gekozen: dict[str, set] = {}
    for key in _data_keys(tool_results):
        known = store.meta(key)
        if known and known.afgeleid_van and getattr(known, veld) is not None:
            gekozen.setdefault(_root(key), set()).update(getattr(known, veld))
    return gekozen


def _bron(root: str, veld: str) -> KeyMeta | None:
    known = store.meta(root)
    return known if known and getattr(known, veld) else None


def ontbrekende_schooljaren(vraag: str, tool_results: list[str]) -> list[str]:
    """Gevraagde schooljaren die in de data staan maar in geen enkele selectie van de beurt."""
    gevraagd = periode.gevraagde_schooljaren(vraag)
    if not gevraagd:
        return []
    problemen = []
    for root, jaren in _selecties(tool_results, "schooljaren").items():
        if not (bron := _bron(root, "schooljaren")):
            continue
        for jaar in sorted(gevraagd & set(bron.schooljaren) - jaren):
            selectie = ", ".join(periode.labels(sorted(jaren))) or "geen schooljaar"
            problemen.append(
                f"Gevraagd schooljaar {periode.label(jaar)} staat in de data ({bron.dataset}), maar niet in de "
                f"selectie waarop het antwoord rust ({selectie}). Selecteer {periode.broncode(bron.bron, jaar)}."
            )
    return problemen


def ontbrekende_instellingen(vraag: str, tool_results: list[str]) -> list[str]:
    """Genoemde instellingen die in de data staan maar in geen enkele selectie van de beurt."""
    problemen = []
    for root, codes in _selecties(tool_results, "instellingen").items():
        if not (bron := _bron(root, "instellingen")):
            continue
        namen = instelling.namen(store.get(root), bron.instellingskolom)
        for code in sorted(instelling.genoemde(vraag, namen) - codes):
            selectie = ", ".join(f"{namen.get(c, c)} ({c})" for c in sorted(codes)) or "geen instelling"
            problemen.append(
                f"De vraag noemt {namen[code]} ({code}), maar de selectie waarop het antwoord rust bevat "
                f"{selectie}. Filter op {bron.instellingskolom}={code}."
            )
    return problemen
