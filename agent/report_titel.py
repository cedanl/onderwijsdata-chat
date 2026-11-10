"""De rapporttitel uit code: de vraag van de gebruiker, niet een titel van het model (#416, CH-09).

Vijf keer hetzelfde rapport gaf vijf titels ("Instroom HU", "Eerstejaars Hogeschool Utrecht
2024/25", ...). De vraag staat vast; de titel volgt haar, met de ingestelde instelling erachter.

Een opdrachtzin ("Maak een grafiek van ...") wordt het onderwerp dat erachter staat, en de periode komt uit de data
van de figuren, niet uit het model (#893): "in het meest recente schooljaar" wordt het schooljaar, en een vraag zonder
jaar krijgt het schooljaar erachter. Of er een jaar in staat, telt na het inkorten: een jaar dat de grens van 80 tekens
wegkapt, is er voor de lezer niet (#1003).
"""

import re

from core import persoonsgegevens
from tools import periode as schooljaren

_MAX_TEKENS = 80
_AFKAPPING = "…"
_SLOTTEKENS = "?!.: \t\n"
# De titel staat in het werkboek, de export, de browsertab en de geschiedenis: nooit met een BSN,
# e-mailadres of telefoonnummer uit de vraag erin (#478).
TITEL_ZONDER_PERSOONSGEGEVENS = "Rapport (persoonsgegevens weggelaten)"


# De onderzoeksvraag die de gebruiker bevestigde (#750) staat voluit in het rapport, ook zonder persoonsgegevens.
VRAAG_ZONDER_PERSOONSGEGEVENS = "Onderzoeksvraag weggelaten: ze bevatte persoonsgegevens."


def rapportvraag(vraag: str) -> str:
    """De bevestigde onderzoeksvraag zoals het rapport haar toont: één regel, zonder BSN, e-mailadres of telefoonnummer."""
    tekst = " ".join((vraag or "").split())
    return VRAAG_ZONDER_PERSOONSGEGEVENS if persoonsgegevens.bevat(tekst) else tekst


# "Maak een grafiek van", "Geef me een overzicht van", "Toon een staafgrafiek over": de opdracht is geen onderwerp.
_OPDRACHT = re.compile(
    r"^(?:maak|geef|toon|genereer)\s+(?:(?:me|mij|ons)\s+)?(?:een\s+|het\s+|de\s+)?"
    r"(?:staaf|lijn|taart)?(?:grafiek|diagram|overzicht|rapport|visualisatie|tabel|kaart)\s+(?:van|over|met|voor)\s+",
    re.IGNORECASE,
)
# "in het meest recente schooljaar": relatief, en dus geen periode die een lezer later kan terugvinden. Noemt de vraag
# het jaar er als bijstelling achter ("studiejaar, 2025/2026,"), dan gaat dat mee: anders staat het jaar er twee keer.
_RELATIEF_SCHOOLJAAR = re.compile(
    r"\b(in\s+)?(?:het\s+)?(?:meest\s+recente|laatste|nieuwste|huidige)\s+(?:school|studie)jaar\b"
    r"(?:,\s*20\d{2}(?:/(?:20)?\d{2})?(?:,|$))?",
    re.IGNORECASE,
)
# "(ingeschreven personen, hoofdinschrijvingen)": een definitie, geen onderwerp. Valt weg als de titel te lang is (#1003);
# een tussenzin met een getal (een jaar, een code) blijft.
_TUSSENZIN = re.compile(r"\s*\([^()\d]*\)")
_JAAR = re.compile(r"(?<!\d)20\d{2}(?!\d)")


def periodelabel(bereik: tuple[int, int]) -> str:
    """De startjaren als schooljaren: 2025/26, of 2020/21 tot 2024/25 met een streep bij een bereik."""
    van, tot = bereik
    return schooljaren.label(van) if van == tot else f"{schooljaren.label(van)}–{schooljaren.label(tot)}"


def _zonder_opdracht(tekst: str) -> str:
    """De vraag zonder haar opdrachtwoorden; een opdracht zonder onderwerp erachter blijft zoals ze was."""
    rest = _OPDRACHT.sub("", tekst, count=1)
    return rest[0].upper() + rest[1:] if rest else tekst


def _vast_schooljaar(tekst: str, bereik: tuple[int, int] | None) -> str:
    """Een relatief schooljaar wordt het schooljaar uit de data, als de data één schooljaar is."""
    if bereik is None or bereik[0] != bereik[1]:
        return tekst
    label = periodelabel(bereik)
    return _RELATIEF_SCHOOLJAAR.sub(lambda m: f"{'in ' if m.group(1) else ''}{label}", tekst)


def _achtervoegsel(tekst: str, label: str | None) -> str:
    return "" if label is None or _JAAR.search(tekst) else f" ({label})"


def _zonder_tussenzin(tekst: str, label: str | None) -> str:
    """Past de titel niet, met de periode erachter als er geen jaar in staat, dan valt eerst een tussenzin weg."""
    if len(tekst) + len(_achtervoegsel(tekst, label)) <= _MAX_TEKENS:
        return tekst
    return _TUSSENZIN.sub("", tekst).strip() or tekst


def _met_periode(tekst: str, label: str | None) -> str:
    """De tekst binnen de grens, met de periode erachter als er na het inkorten geen jaar meer in staat (#893, #1003).
    De inkorting houdt dan ruimte voor de periode; een jaar dat de grens overleeft, komt er niet nog eens bij."""
    kort = _ingekort(tekst)
    if not (achter := _achtervoegsel(kort, label)):
        return kort
    return _ingekort(tekst, _MAX_TEKENS - len(achter)) + achter


def _ingekort(tekst: str, ruimte: int = _MAX_TEKENS) -> str:
    """Hoogstens `ruimte` tekens, afgebroken op een woordgrens, met een beletselteken."""
    if len(tekst) <= ruimte:
        return tekst
    kort = tekst[: ruimte - len(_AFKAPPING) + 1]
    # Valt de grens midden in een woord, dan gaat dat woord eraf; een te lang woord wordt afgekapt.
    kort = kort.rsplit(" ", 1)[0] if " " in kort else kort[:-1]
    return kort.rstrip(_SLOTTEKENS + ",;") + _AFKAPPING


def rapporttitel(vraag: str, instelling: str | None, bereik: tuple[int, int] | None = None) -> str:
    """De vraag als titel: één regel, zonder opdrachtwoorden of slotteken, met hoofdletter, met het schooljaar uit de
    data (`bereik`, startjaren) als de vraag geen jaar noemt, en met de instelling als de vraag haar niet noemt."""
    tekst = " ".join((vraag or "").split()).rstrip(_SLOTTEKENS)
    if not tekst:
        return "Rapport"
    if persoonsgegevens.bevat(tekst):
        tekst = TITEL_ZONDER_PERSOONSGEGEVENS
    else:
        label = periodelabel(bereik) if bereik else None
        tekst = _vast_schooljaar(_zonder_opdracht(tekst[0].upper() + tekst[1:]), bereik)
        tekst = _met_periode(_zonder_tussenzin(tekst, label), label)
    instelling = " ".join((instelling or "").split())
    if instelling and instelling.casefold() not in tekst.casefold():
        return f"{tekst} – {instelling}"
    return tekst
