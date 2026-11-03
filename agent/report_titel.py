"""De rapporttitel uit code: de vraag van de gebruiker, niet een titel van het model (#416, CH-09).

Vijf keer hetzelfde rapport gaf vijf titels ("Instroom HU", "Eerstejaars Hogeschool Utrecht
2024/25", ...). De vraag staat vast; de titel volgt haar, met de ingestelde instelling erachter.

Een opdrachtzin ("Maak een grafiek van ...") wordt het onderwerp dat erachter staat, en de periode komt uit de data
van de figuren, niet uit het model (#893): "in het meest recente schooljaar" wordt het schooljaar, en een vraag zonder
jaar krijgt het schooljaar erachter.
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
# "in het meest recente schooljaar": relatief, en dus geen periode die een lezer later kan terugvinden.
_RELATIEF_SCHOOLJAAR = re.compile(
    r"\b(in\s+)?(?:het\s+)?(?:meest\s+recente|laatste|nieuwste|huidige)\s+(?:school|studie)jaar\b", re.IGNORECASE
)
_JAAR = re.compile(r"(?<!\d)20\d{2}(?!\d)")


def periodelabel(bereik: tuple[int, int]) -> str:
    """De startjaren als schooljaren: 2025/26, of 2020/21 tot 2024/25 met een streep bij een bereik."""
    van, tot = bereik
    return schooljaren.label(van) if van == tot else f"{schooljaren.label(van)}–{schooljaren.label(tot)}"


def _zonder_opdracht(tekst: str) -> str:
    """De vraag zonder haar opdrachtwoorden; een opdracht zonder onderwerp erachter blijft zoals ze was."""
    rest = _OPDRACHT.sub("", tekst, count=1)
    return rest[0].upper() + rest[1:] if rest else tekst


def _met_periode(tekst: str, bereik: tuple[int, int] | None) -> tuple[str, str]:
    """(tekst, achtervoegsel): een relatief schooljaar wordt het schooljaar uit de data, en een tekst zonder jaar
    krijgt de periode erachter. Zonder periode of met een jaar in de vraag verandert er niets."""
    if bereik is None:
        return tekst, ""
    label = periodelabel(bereik)
    if bereik[0] == bereik[1]:
        tekst = _RELATIEF_SCHOOLJAAR.sub(lambda m: f"{'in ' if m.group(1) else ''}{label}", tekst)
    return tekst, "" if _JAAR.search(tekst) else f" ({label})"


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
        tekst, achter = _met_periode(_zonder_opdracht(tekst[0].upper() + tekst[1:]), bereik)
        tekst = _ingekort(tekst, _MAX_TEKENS - len(achter)) + achter
    instelling = " ".join((instelling or "").split())
    if instelling and instelling.casefold() not in tekst.casefold():
        return f"{tekst} – {instelling}"
    return tekst
