"""Past het antwoord bij de selectie waarop het rust? (#187, #143, #195)

Het model koos soms het jaar vóór het gevraagde schooljaar, of de code van een
andere instelling (30TX, Aeres, voor Hogeschool Utrecht). De getallen die het
daarna gaf staan wél in de tooluitvoer, dus de getalcontrole ziet het niet. Deze
controles vergelijken wat de vraag noemt met wat de selecties van de beurt
bevatten (KeyMeta, #193), en wat het antwoord concludeert met wat een onvolledige
selectie kan dragen.
"""

import json
import re

from tools import instelling, periode, store
from tools.store import KeyMeta


def data_keys(tool_results: list[str]) -> list[str]:
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
    for key in data_keys(tool_results):
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


# Een telling of afwezigheid is op een afgekapte pagina niet vast te stellen (#186).
# De zinnen hieronder erkennen dat; een zin die het getal zo benoemt is geen telling.
_AFWEZIG = re.compile(
    r"\b(?:niet (?:gevonden|aangetroffen|te vinden|vindbaar)|bestaat niet|bestaan niet"
    r"|komt niet voor|komen niet voor|ontbreekt|ontbreken)\b",
    re.IGNORECASE,
)
_ALS_PAGINA = re.compile(r"\b(?:eerste|opgehaald\w*|pagina|afgekapt|niet vastgesteld|onvolledig)\b", re.IGNORECASE)
_ZIN = re.compile(r"[^.!?\n]+")


def onvolledige_selecties(tekst: str, tool_results: list[str]) -> list[str]:
    """Tellingen en afwezigheidsclaims in `tekst` die rusten op een afgekapte selectie."""
    onvolledig = {
        key: known for key in data_keys(tool_results)
        if (known := store.meta(key)) and not known.volledig
    }
    if not onvolledig:
        return []
    datasets = ", ".join(sorted({known.dataset for known in onvolledig.values()}))
    rijen = {str(len(store.get(key))) for key in onvolledig}
    problemen = []
    for zin in (m.group(0).strip() for m in _ZIN.finditer(tekst)):
        if _ALS_PAGINA.search(zin):
            continue
        problemen.extend(
            f"'{zin}': {getal} is het aantal opgehaalde rijen van een afgekapte selectie ({datasets}), "
            "geen telling. Noem geen totaal, of zeg dat het met deze data niet vast te stellen is."
            for getal in sorted(rijen & set(re.findall(r"\b\d+\b", zin)))
        )
        if _AFWEZIG.search(zin):
            problemen.append(
                f"'{zin}': de selectie ({datasets}) is afgekapt, dus dat iets ontbreekt is niet vast te stellen. "
                "Zoek gericht met een filter, of zeg dat het met deze data niet vast te stellen is."
            )
    return problemen
