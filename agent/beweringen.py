"""Beweringen over wat er wel of niet te zeggen valt, zonder dat de data het draagt (#323, #225).

Getallen, labels en selecties worden elders gecontroleerd. Dit zijn twee uitspraken
die geen getal zijn en toch een claim: "die data is er niet" en "dit komt doordat ...".
Beide zijn alleen toegestaan met een zoekpad of brondekking; anders gaat het model
terug naar de data of markeert het de uitspraak als niet vast te stellen.
"""

import json
import re

from tools import instelling, store
from tools.catalog import genoemde_datasets

from .probleem import Probleem
from .selectie import data_keys

# Letterlijke formuleringen uit live antwoorden staan in tests/test_beweringen.py (#396).
_ONBESCHIKBAAR = re.compile(
    r"\b(?:niet|geen)\s+(?:beschikbaar|opvraagbaar)\b"
    r"|\bgeen\s+(?:dataset|data|gegevens|cijfers)\b[^.\n]{0,60}\b(?:per|van)\s+instelling\b"
    r"|\bniet\s+(?:in|uit)\s+de\s+(?:beschikbare\s+)?(?:data|gegevens)\b"
    r"|\bgeen\s+(?:beschikbare\s+|openbare\s+)?[\w-]*data-?set\b"
    r"|\bniet\s+in\s+de\s+catalogus\b"
    r"|\bpubliceert\s+(?:\w+\s+)?geen\b|\b(?:wordt|worden)\s+niet\s+gepubliceerd\b"
    r"|\bbestaat\s+niet\b",
    re.IGNORECASE,
)

# "komt doordat", "als gevolg van", "te verklaren door": een oorzaak, geen waarneming.
_OORZAAK = re.compile(
    r"\bkomt\s+(?:waarschijnlijk\s+|vooral\s+|mede\s+)?(?:door|doordat|omdat)\b"
    r"|\b(?:is|zijn)\s+(?:waarschijnlijk\s+|mede\s+)?(?:het\s+)?gevolg\s+van\b"
    r"|\bals\s+gevolg\s+van\b"
    r"|\bte\s+verklaren\s+(?:door|uit)\b"
    r"|\bverklaard\s+(?:door|worden\s+door)\b"
    r"|\bde\s+oorzaak\b|\bdit\s+(?:komt|duidt\s+op)\b"
    r"|\bhangt\s+samen\s+met\b",
    re.IGNORECASE,
)
_VOORBEHOUD = re.compile(
    r"\bniet\s+(?:vast\s+te\s+stellen|af\s+te\s+leiden|te\s+herleiden|uit\s+(?:deze|de)\s+(?:data|gegevens))\b"
    r"|\bniet\s+(?:met|uit)\s+deze\s+(?:data|gegevens)\b|\bmogelijk(?:e)?\b[^.\n]{0,40}\bniet\s+getoetst\b",
    re.IGNORECASE,
)


def geladen_datasets(tool_results: list[str]) -> set[str]:
    return {known.dataset.lower() for key in data_keys(tool_results) if (known := store.meta(key))}


def _resultaten(tool_results: list[str]) -> list[dict]:
    parsed = []
    for result in tool_results:
        try:
            item = json.loads(result)
        except (TypeError, ValueError):
            continue
        if isinstance(item, dict):
            parsed.append(item)
    return parsed


def onbeschikbaar_zonder_zoekpad(vraag: str, tekst: str, tool_results: list[str]) -> list[str]:
    """'Die data is er niet' mag alleen na een broncontrole in code, niet op trefwoorden (#323, #396).

    De tooluitkomsten van de beurt bepalen wat het antwoord over afwezigheid mag zeggen:
    - niet ontsloten: dataset_details gaf `opvraagbaar: false`; "niet via de chat" is eerlijk.
    - niet gevonden: de vraag noemt een catalogus-ID dat niet is opgehaald, of een instelling
      zonder dat er data is opgehaald; de DUO-instellingsbestanden (p01hoinges, ...) beantwoorden
      elke instellingsvraag.
    - verkeerde selectie: een filter gaf 0 rijen; dat bewijst niets over de bron.
    - werkelijk niet beschikbaar: wat overblijft. Vragen zonder instelling (ROA, UWV) vallen
      eronder: daar blijft "niet via de chat" een eerlijk antwoord.
    """
    if not _ONBESCHIKBAAR.search(tekst):
        return []
    resultaten = _resultaten(tool_results)
    if any(r.get("opvraagbaar") is False for r in resultaten):
        return []
    geladen = geladen_datasets(tool_results)
    if ontbrekend := [d for d in genoemde_datasets(vraag) if d.lower() not in geladen]:
        return [
            Probleem(
                f"Het antwoord zegt dat de gegevens er niet zijn, maar dataset {ontbrekend[0]} uit de vraag "
                "staat in de catalogus en is niet opgehaald.",
                f"Haal {ontbrekend[0]} op (get_duo_data, get_cbs_data of get_rio_data, volgens de bron in "
                "dataset_details) en beantwoord daarmee de vraag.",
            )
        ]
    if leeg := next((r for r in resultaten if r.get("rijen") == [] and "suggesties" in r), None):
        return [
            Probleem(
                "Het antwoord zegt dat de gegevens niet beschikbaar zijn, maar alleen een filter gaf 0 rijen: "
                "dat is een selectie zonder treffers, geen afwezige bron.",
                f"Bestaande waarden in die kolommen: {json.dumps(leeg['suggesties'], ensure_ascii=False)}. "
                "Controleer de code in dataset_details en filter opnieuw. Lukt dat niet, zeg dan dat de selectie "
                "geen rijen gaf, niet dat de data niet bestaat.",
            )
        ]
    if data_keys(tool_results) or not instelling.noemt_instelling(vraag):
        return []
    return [
        Probleem(
            "Het antwoord zegt dat de gegevens niet beschikbaar zijn, maar er is geen data van een instellingsbestand opgehaald.",
            "Zoek een DUO-instellingsbestand (bijv. p01hoinges voor ingeschrevenen per instelling), haal het op "
            "met get_duo_data en beantwoord daarmee de vraag. Zeg alleen dat het er niet is als dat bestand het niet bevat.",
        )
    ]


def ongedekte_oorzaak(tekst: str, tool_results: list[str]) -> list[str]:
    """Een oorzaak of duiding die niet uit de data volgt, moet als zodanig gemarkeerd zijn.

    Zonder opgehaalde data zwijgt de controle (een algemene vraag mag uitleg geven). Met data
    bewijzen de aggregaten een verschil, niet de reden ervan. Per alinea: staat er een
    voorbehoud ("niet vast te stellen met deze gegevens") bij de oorzaak, dan is het eerlijk.
    """
    if not data_keys(tool_results):
        return []
    ongedekt = [
        alinea.strip()
        for alinea in re.split(r"\n\s*\n", tekst)
        if _OORZAAK.search(alinea) and not _VOORBEHOUD.search(alinea)
    ]
    if not ongedekt:
        return []
    return [
        Probleem(
            "Het antwoord geeft een oorzaak of verklaring die niet uit de opgehaalde data volgt.",
            f"Betreft: {ongedekt[0][:160]!r}. Laat de verklaring weg, of schrijf erbij dat de oorzaak "
            "met deze gegevens niet vast te stellen is. Een verklaring mag alleen met een dataset die haar aantoont.",
        )
    ]
