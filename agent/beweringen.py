"""Beweringen over wat er wel of niet te zeggen valt, zonder dat de data het draagt (#323, #225).

Getallen, labels en selecties worden elders gecontroleerd. Dit zijn twee uitspraken
die geen getal zijn en toch een claim: "die data is er niet" en "dit komt doordat ...".
Beide zijn alleen toegestaan met een zoekpad of brondekking; anders gaat het model
terug naar de data of markeert het de uitspraak als niet vast te stellen.
"""

import re

from tools import instelling

from .probleem import Probleem
from .selectie import data_keys

_ONBESCHIKBAAR = re.compile(
    r"\b(?:niet|geen)\s+(?:beschikbaar|opvraagbaar)\b"
    r"|\bgeen\s+(?:dataset|data|gegevens|cijfers)\b[^.\n]{0,60}\b(?:per|van)\s+instelling\b"
    r"|\bniet\s+(?:in|uit)\s+de\s+(?:beschikbare\s+)?(?:data|gegevens)\b",
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


def onbeschikbaar_zonder_zoekpad(vraag: str, tekst: str, tool_results: list[str]) -> list[str]:
    """Een instellingsvraag mag niet "niet beschikbaar" krijgen zonder dat er data is opgehaald.

    De DUO-instellingsbestanden (p01hoinges, p01hoinschr, ...) beantwoorden elke vraag naar een
    instelling; wie na enkele zoekacties "geen dataset per instelling" zegt, heeft niet goed gezocht.
    Vragen zonder instelling (ROA, UWV) vallen er niet onder: daar blijft "niet via de chat" een eerlijk antwoord.
    """
    if data_keys(tool_results) or not _ONBESCHIKBAAR.search(tekst) or not instelling.noemt_instelling(vraag):
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
