"""Beweringen over wat er wel of niet te zeggen valt, zonder dat de data het draagt (#323, #225).

Getallen, labels en selecties worden elders gecontroleerd. Dit zijn twee uitspraken
die geen getal zijn en toch een claim: "die data is er niet" en "dit komt doordat ...".
"Die data is er niet" mag alleen met een zoekpad; een oorzaak alleen met voorbehoud, want
telreeksen tonen een verschil of samenhang, niet de reden ervan (#413). Anders gaat het model
terug naar de data of markeert het de uitspraak als niet vast te stellen.

Een vermoeden alleen als de gebruiker om een verklaring vroeg (#1036, `tools.verklaring_markers`): dan in een apart
blok "Niet uit de data", met hooguit drie toetsbare vragen. Zonder verzoek is elk vermoeden een probleem, ook met
voorbehoud.
"""

import json
import re

from tools import instelling, store
from tools.bron_ids import bron_id
from tools.catalog import genoemde_datasets, ophaaltool

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
    r"|\bniet\s+(?:met|uit)\s+deze\s+(?:data|gegevens)\b|\bmogelijk(?:e)?\b[^.\n]{0,40}\bniet\s+getoetst\b"
    # Het voorbehoud in andere woorden (#619): "de data laat de oorzaak niet zien", "vermoedens", "denkbaar".
    r"|\b(?:laat|laten|toont|tonen|geeft|geven)\b[^.\n]{0,40}\b(?:oorza(?:ak|ken)|reden(?:en)?)\b[^.\n]{0,20}\bniet\b"
    r"|\bvermoeden(?:s)?\b|\bdenkbaar\b|\bzou(?:den)?\s+(?:\w+\s+)?kunnen\s+samenhangen\b"
    # Het model zegt zelf dat het de oorzaak niet weet of niet naging (#1000): "Ik heb de oorzaak niet gecontroleerd",
    # "de oorzaak is niet onderzocht", "ik weet de oorzaak niet". Geen bredere uitzondering: "de oorzaak is niet X
    # maar Y" blijft een oorzaak.
    r"|\bde\s+oorzaak(?:\s+\w+){0,3}?\s+niet\s+(?:gecontroleerd|onderzocht|nagegaan|bekeken|vastgesteld)\b"
    r"|\bik\s+weet\s+(?:de\s+oorzaak\s+niet|niet\s+wat\s+de\s+oorzaak\s+is)\b",
    re.IGNORECASE,
)
# Een vermoeden, als zodanig gemarkeerd (#1036): zonder verzoek om een verklaring hoort het niet in het antwoord, met
# verzoek alleen in het blok "Niet uit de data".
_HYPOTHESE = re.compile(
    r"\bmogelijke\s+(?:verklaring(?:en)?|oorza(?:ak|ken))\b"
    r"|\bzou(?:den)?\s+(?:\w+\s+)?kunnen\s+(?:samenhangen\s+met|komen\s+doordat)\b"
    r"|\bhet\s+is\s+denkbaar\s+dat\b",
    re.IGNORECASE,
)
# De kop van het blok "Niet uit de data" (#1036): een markdown-kop of een vetgedrukte regel. Het blok loopt tot de
# volgende kop (markdown of een vetgedrukte regel) of het einde van de tekst. Tussen het kopteken en de woorden staat
# één witruimteklasse: twee naast elkaar geven kwadratisch terugzoeken op een kopregel vol spaties.
_BLOKKOP = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]|\*\*)[ \t*]*niet\s+uit\s+de\s+data[ \t*:]*$", re.IGNORECASE | re.MULTILINE
)
_KOP = re.compile(r"^[ \t]*(?:#{1,6}[ \t]|\*\*[^*\n]+\*\*[ \t:]*$)", re.MULTILINE)
# Een zin eindigt op . ? of !, eventueel gevolgd door opmaak of een sluitteken ("*Hangt dit samen met X?* Te toetsen").
_SLUITTEKENS = "*_)\"'”’"
_ZINSGRENS = re.compile(rf"(?<=[.?!])[{re.escape(_SLUITTEKENS)}]*\s+|\n+")
MAX_BLOKVRAGEN = 3
_BLOK = "het blok 'Niet uit de data'"
_HET_BLOK = "Het blok 'Niet uit de data'"
# De onderzoeksvraag herhaalt wat de gebruiker vroeg ("te verklaren uit locatie?"): geen bewering van het model.
_ONDERZOEKSVRAAG = re.compile(r"^\W*onderzoeksvraag\b.*$", re.IGNORECASE | re.MULTILINE)


def verklaringsblok(tekst: str) -> tuple[str, str]:
    """De tekst buiten het blok "Niet uit de data" en de inhoud van het blok, zonder kop; zonder blok (tekst, "").

    Markdown lezen is een heuristiek: een `###`-kop en een vetgedrukte kopregel tellen allebei."""
    kop = _BLOKKOP.search(tekst)
    if not kop:
        return tekst, ""
    rest = tekst[kop.end() :]
    volgende = _KOP.search(rest)
    eind = volgende.start() if volgende else len(rest)
    return tekst[: kop.start()] + rest[eind:], rest[:eind]


def zonder_blokkop(tekst: str) -> str:
    """De tekst zonder de kop "Niet uit de data": die kop zegt niet dat er data ontbreekt."""
    return _BLOKKOP.sub("", tekst)


def _catalogus_id(dataset_id: str) -> str:
    """Eén normalisatie voor beide kanten van de vergelijking: het `bron:id`-contract, in kleine letters (#999).

    De store-meta schrijft `skdb:studiekeuzedatabase`, `unl:wopi` of `duo:financien`, de catalogus `studiekeuzedatabase`,
    `wopi` en `financien`; een CBS-ID staat in de ene spelling of de andere."""
    return bron_id(dataset_id).lower()


def geladen_datasets(tool_results: list[str]) -> set[str]:
    return {_catalogus_id(known.dataset) for key in data_keys(tool_results) if (known := store.meta(key))}


def _ophaalopdracht(dataset_id: str) -> str:
    """Welke tool de dataset ophaalt, uit de catalogus; zonder bekende tool de drie datatools."""
    if tool := ophaaltool(dataset_id):
        return f"Haal {dataset_id} op met {tool} en beantwoord daarmee de vraag."
    return (
        f"Haal {dataset_id} op (get_duo_data, get_cbs_data of get_rio_data, volgens de bron in dataset_details) "
        "en beantwoord daarmee de vraag."
    )


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
    # De kop van het blok "Niet uit de data" (#1036) is geen bewering over afwezige data.
    if not _ONBESCHIKBAAR.search(zonder_blokkop(tekst)):
        return []
    resultaten = _resultaten(tool_results)
    if any(r.get("opvraagbaar") is False for r in resultaten):
        return []
    geladen = geladen_datasets(tool_results)
    if ontbrekend := [d for d in genoemde_datasets(vraag) if _catalogus_id(d) not in geladen]:
        return [
            Probleem(
                f"Het antwoord zegt dat de gegevens er niet zijn, maar dataset {ontbrekend[0]} uit de vraag "
                "staat in de catalogus en is niet opgehaald.",
                _ophaalopdracht(ontbrekend[0]),
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


def _heeft_data(tool_results: list[str]) -> bool:
    """Is er data opgehaald: een toolresultaat of de datasetcontext van het rapport noemt een data_key."""
    for item in _resultaten(tool_results):
        onderdelen = [item, *(d for d in item.get("datasets") or [] if isinstance(d, dict))]
        if any(isinstance(deel.get("data_key"), str) for deel in onderdelen):
            return True
    return False


def _alineas(tekst: str) -> list[str]:
    return [alinea.strip() for alinea in re.split(r"\n\s*\n", tekst) if alinea.strip()]


def _zinnen(tekst: str) -> list[str]:
    return [zin.strip() for zin in _ZINSGRENS.split(tekst) if zin.strip()]


def _is_vraag(zin: str) -> bool:
    return zin.rstrip(_SLUITTEKENS + " \t").endswith("?")


def _gestelde_oorzaak(alineas: list[str]) -> list[Probleem]:
    """Een oorzaak zonder voorbehoud in dezelfde alinea (#225, #413)."""
    ongedekt = [alinea for alinea in alineas if _OORZAAK.search(alinea) and not _VOORBEHOUD.search(alinea)]
    if not ongedekt:
        return []
    return [
        Probleem(
            "Het antwoord geeft een oorzaak of verklaring die niet uit de opgehaalde data volgt.",
            f"Betreft: {ongedekt[0][:160]!r}. Laat de verklaring weg, of schrijf erbij dat de oorzaak "
            "met deze gegevens niet vast te stellen is. Twee telreeksen naast elkaar tonen samenhang, geen oorzaak.",
        )
    ]


def _ongevraagde_verklaring(alineas: list[str], blok: str) -> list[Probleem]:
    """Zonder verzoek om een verklaring: geen vermoeden, ook niet met voorbehoud, en geen blok (#1036)."""
    problemen = []
    if blok:
        problemen.append(
            Probleem(
                f"Het antwoord heeft {_BLOK}, maar de gebruiker vroeg niet om een verklaring.",
                "Laat dat blok weg: beschrijf alleen wat de data laat zien.",
            )
        )
    if vermoeden := next((alinea for alinea in alineas if _HYPOTHESE.search(alinea)), None):
        problemen.append(
            Probleem(
                "Het antwoord geeft een vermoedelijke verklaring waar de gebruiker niet om vroeg.",
                f"Betreft: {vermoeden[:160]!r}. Laat oorzaken, verklaringen en vermoedens weg: "
                "beschrijf alleen wat de data laat zien.",
            )
        )
    return problemen


def _verklaring_buiten_blok(alineas: list[str]) -> list[Probleem]:
    """Met een verzoek om een verklaring hoort elk vermoeden in het blok "Niet uit de data" (#1036)."""
    vermoeden = next((alinea for alinea in alineas if _HYPOTHESE.search(alinea)), None)
    if vermoeden is None:
        return []
    return [
        Probleem(
            f"Het antwoord geeft een vermoeden buiten {_BLOK}.",
            f"Betreft: {vermoeden[:160]!r}. Zet het als toetsbare vraag in het blok '### Niet uit de data', "
            "of laat het weg.",
        )
    ]


def _blokproblemen(blok: str) -> list[Probleem]:
    """In het blok staan vragen, geen vastgestelde oorzaken, en hooguit drie (#1036)."""
    zinnen = _zinnen(blok)
    problemen = []
    if gesteld := next((zin for zin in zinnen if not _is_vraag(zin) and _OORZAAK.search(zin)), None):
        problemen.append(
            Probleem(
                f"{_HET_BLOK} stelt een oorzaak als feit.",
                f'Betreft: {gesteld[:160]!r}. Schrijf elk punt als vraag ("Hangt de daling samen met ...?"), '
                "met een dataset-ID uit de catalogus of 'hiervoor is geen bron in deze app'.",
            )
        )
    if (vragen := sum(_is_vraag(zin) for zin in zinnen)) > MAX_BLOKVRAGEN:
        problemen.append(
            Probleem(
                f"{_HET_BLOK} heeft {vragen} vragen; er mogen er hooguit {MAX_BLOKVRAGEN} in.",
                f"Houd de {MAX_BLOKVRAGEN} vragen die het best te toetsen zijn.",
            )
        )
    return problemen


def ongedekte_oorzaak(
    tekst: str, tool_results: list[str], verklaring_gevraagd: bool = True, alleen_in_blok: bool = False
) -> list[str]:
    """Een oorzaak of duiding die niet uit de data volgt, moet als zodanig gemarkeerd zijn.

    Zonder opgehaalde data zwijgt de controle (een algemene vraag mag uitleg geven). Met data
    bewijzen de aggregaten een verschil, niet de reden ervan. Ook een getal uit een tweede
    telbron bewijst geen oorzaak: twee telreeksen naast elkaar zijn samenhang, geen verklaring
    (#413). Per alinea: staat er een voorbehoud ("niet vast te stellen met deze gegevens") bij
    de oorzaak, dan is het eerlijk.

    `verklaring_gevraagd` (#1036): zonder verzoek is elk vermoeden een probleem, ook met voorbehoud, en ook een blok
    "Niet uit de data". Met verzoek mag een vermoeden alleen als vraag in dat blok staan: in de chat
    (`alleen_in_blok`, gezet door `antwoordcontrole`) is een vermoeden erbuiten altijd een probleem, ook als het blok
    ontbreekt. Het rapport (`report_checks`, de standaard) kent geen blok: daar is een vermoeden buiten een blok alleen
    een probleem als de tekst toch een blok heeft, en verder geldt de regel van het voorbehoud zoals voorheen.
    """
    if not _heeft_data(tool_results):
        return []
    buiten, blok = verklaringsblok(_ONDERZOEKSVRAAG.sub("", tekst))
    alineas = _alineas(buiten)
    problemen: list[str] = [*_gestelde_oorzaak(alineas)]
    if not verklaring_gevraagd:
        return [*problemen, *_ongevraagde_verklaring(alineas, blok)]
    if blok or alleen_in_blok:
        problemen += _verklaring_buiten_blok(alineas)
    return problemen + _blokproblemen(blok)
