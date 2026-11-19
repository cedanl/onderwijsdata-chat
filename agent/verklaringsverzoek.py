"""Verklaringen alleen op verzoek (#1036): wat het model per beurt hoort over oorzaken en vermoedens.

Een niet onderbouwde oorzaak stuurt de lezer (seminarfeedback). Code beslist of de gebruiker om een verklaring vroeg
(`tools.verklaring_markers.vraagt_verklaring`); deze module zet die uitkomst om in een korte beurtinstructie, en
`ongedekte_oorzaak` toetst het antwoord erop. Geen extra modelstap.
"""

_GEVRAAGD = (
    "**Verklaring gevraagd.** De gebruiker vraagt naar een oorzaak of reden. Past het bij de vraag, zet dan aan het "
    "eind van je antwoord een apart blok met de kop `### Niet uit de data`: hooguit 3 toetsbare vragen, elk als "
    'vraag geschreven ("Hangt de daling samen met ...? Te toetsen met <dataset-ID uit de catalogus>."), met per '
    'vraag een bron uit de catalogus of "hiervoor is geen bron in deze app". Noem een oorzaak nooit als vaststaand, '
    "en zet geen vermoeden buiten dat blok."
)
_NIET_GEVRAAGD = (
    '**Geen verklaring gevraagd.** Geef geen oorzaken, verklaringen of vermoedens (ook niet als "een mogelijke '
    'verklaring is") en geen blok "Niet uit de data": beschrijf alleen wat de data laat zien. Een methodische '
    "toelichting uit de metadata van de bron (zoals afronding bij CBS) mag wel."
)


def verklaringinstructie(gevraagd: bool) -> str:
    """De beurtinstructie over verklaringen: het blok "Niet uit de data" bij een verzoek, anders geen vermoedens."""
    return _GEVRAAGD if gevraagd else _NIET_GEVRAAGD
