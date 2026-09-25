"""Past de selectie waarop een antwoord rust bij het gevraagde schooljaar? (#187)

Het model vertaalde "2025/26" soms naar het jaar ervoor, gaf het getal van dat
jaar en schreef dat 2025/26 niet beschikbaar was. Dat getal staat wél in de
tooluitvoer, dus de getalcontrole ziet het niet. Deze controle vergelijkt de
schooljaren uit de vraag met wat de selecties van de beurt bevatten (#193).
"""

import json

from tools import periode, store


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


def ontbrekende_schooljaren(vraag: str, tool_results: list[str]) -> list[str]:
    """Gevraagde schooljaren die in de data staan maar in geen enkele selectie van de beurt."""
    gevraagd = periode.gevraagde_schooljaren(vraag)
    if not gevraagd:
        return []

    # Per laadkey: de schooljaren van de selecties die eruit zijn afgeleid.
    gekozen: dict[str, set[int]] = {}
    for key in _data_keys(tool_results):
        known = store.meta(key)
        if known and known.afgeleid_van and known.schooljaren is not None:
            gekozen.setdefault(_root(key), set()).update(known.schooljaren)

    problemen = []
    for root, jaren in gekozen.items():
        bron = store.meta(root)
        if not bron or not bron.schooljaren:
            continue
        for jaar in sorted(gevraagd & set(bron.schooljaren) - jaren):
            selectie = ", ".join(periode.labels(sorted(jaren))) or "geen schooljaar"
            problemen.append(
                f"Gevraagd schooljaar {periode.label(jaar)} staat in de data ({bron.dataset}), maar niet in de "
                f"selectie waarop het antwoord rust ({selectie}). Selecteer {periode.broncode(bron.bron, jaar)}."
            )
    return problemen
