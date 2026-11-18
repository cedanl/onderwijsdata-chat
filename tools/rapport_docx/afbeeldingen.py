"""De grafieken bij "Download als Word" (#1038): PNG's die de browser met Plotly.toImage maakte.

Het lichaam van het verzoek is multipart/form-data met alleen afbeeldingen: één deel per grafiek, met de naam
`grafiek-<n>`, n de plek van de visualisatie in het rapport (vanaf 0). Tekst komt nooit uit het verzoek, alleen uit
het bewaarde rapport. Een afbeelding komt alleen in het eigen document van de gebruiker, dus de controle is op vorm:
een PNG (magische bytes, een leesbare kop), niet groter dan MAX_BYTES, hooguit MAX_AANTAL, elke plek één keer en binnen
het aantal visualisaties. Het lichaam wordt in het geheugen gelezen (begrensd door de Verzoeklimiet van de app); niets
ervan gaat naar schijf of de database: Starlettes eigen formulierlezer zet een deel boven 1 MiB in een tijdelijk
bestand, daarom leest deze module het zelf met python-multipart.
"""

import re
from dataclasses import dataclass

from docx.image.image import Image
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

MAX_BYTES = 2 * 1024 * 1024
MAX_AANTAL = 20
MAX_PIXELS = 10_000

PNG_HANDTEKENING = b"\x89PNG\r\n\x1a\n"
_VELDNAAM = re.compile(r'(?:^|;)\s*name="grafiek-(\d{1,3})"')

GEEN_FORMULIER = "Stuur de grafieken als multipart/form-data."
ONBEKEND_DEEL = "Het verzoek mag alleen grafieken bevatten (grafiek-0, grafiek-1, …)."
TE_VEEL = f"Te veel grafieken: hooguit {MAX_AANTAL}."
TE_GROOT = f"Een grafiek is groter dan {MAX_BYTES // (1024 * 1024)} MiB."
GEEN_PNG = "Een grafiek is geen geldige PNG-afbeelding."
VERKEERDE_PLEK = "Een grafiek hoort niet bij een visualisatie in dit rapport."
DUBBEL = "Een grafiek staat er twee keer in."


class AfbeeldingFout(Exception):
    def __init__(self, status: int, melding: str) -> None:
        super().__init__(melding)
        self.status = status
        self.melding = melding


@dataclass(frozen=True)
class Grafiek:
    png: bytes
    breedte_px: int
    hoogte_px: int


@dataclass
class _Deel:
    kopregels: list[tuple[bytes, bytes]]
    data: bytearray


def _delen(content_type: str, lichaam: bytes) -> list[_Deel]:
    """De delen van een multipart-lichaam, in het geheugen. Ongeldig multipart geeft een AfbeeldingFout (400)."""
    soort, opties = parse_options_header(content_type)
    grens = opties.get(b"boundary")
    if soort != b"multipart/form-data" or not grens:
        raise AfbeeldingFout(400, GEEN_FORMULIER)
    delen: list[_Deel] = []
    veld = bytearray()
    waarde = bytearray()
    klaar = False

    def begin() -> None:
        if len(delen) == MAX_AANTAL:
            raise AfbeeldingFout(400, TE_VEEL)
        delen.append(_Deel(kopregels=[], data=bytearray()))

    def kopveld(data: bytes, start: int, eind: int) -> None:
        veld.extend(data[start:eind])

    def kopwaarde(data: bytes, start: int, eind: int) -> None:
        waarde.extend(data[start:eind])

    def kopeinde() -> None:
        delen[-1].kopregels.append((bytes(veld).lower(), bytes(waarde)))
        veld.clear()
        waarde.clear()

    def data(data: bytes, start: int, eind: int) -> None:
        delen[-1].data.extend(data[start:eind])
        if len(delen[-1].data) > MAX_BYTES:
            raise AfbeeldingFout(413, TE_GROOT)

    def einde() -> None:
        nonlocal klaar
        klaar = True

    parser = MultipartParser(
        grens,
        {
            "on_part_begin": begin,
            "on_header_field": kopveld,
            "on_header_value": kopwaarde,
            "on_header_end": kopeinde,
            "on_part_data": data,
            "on_end": einde,
        },
    )
    try:
        parser.write(lichaam)
        parser.finalize()
    except MultipartParseError as exc:
        raise AfbeeldingFout(400, GEEN_FORMULIER) from exc
    if not klaar:
        raise AfbeeldingFout(400, GEEN_FORMULIER)
    return delen


def _plek(deel: _Deel) -> int:
    dispositie = next((w for k, w in deel.kopregels if k == b"content-disposition"), b"")
    gevonden = _VELDNAAM.search(dispositie.decode("latin-1"))
    if not dispositie.lower().startswith(b"form-data") or not gevonden:
        raise AfbeeldingFout(400, ONBEKEND_DEEL)
    return int(gevonden.group(1))


def grafiek(png: bytes) -> Grafiek:
    """Een PNG als Grafiek, na controle van de handtekening en de kop (python-docx leest dezelfde kop bij het plaatsen)."""
    if len(png) > MAX_BYTES:
        raise AfbeeldingFout(413, TE_GROOT)
    if not png.startswith(PNG_HANDTEKENING):
        raise AfbeeldingFout(400, GEEN_PNG)
    try:
        beeld = Image.from_blob(png)
    except Exception as exc:
        raise AfbeeldingFout(400, GEEN_PNG) from exc
    if beeld.content_type != "image/png" or not (
        0 < beeld.px_width <= MAX_PIXELS and 0 < beeld.px_height <= MAX_PIXELS
    ):
        raise AfbeeldingFout(400, GEEN_PNG)
    return Grafiek(png=png, breedte_px=beeld.px_width, hoogte_px=beeld.px_height)


def lees_grafieken(content_type: str | None, lichaam: bytes, aantal_visualisaties: int) -> dict[int, Grafiek]:
    """De grafieken uit het verzoek per plek van de visualisatie. Een leeg lichaam is: geen grafieken."""
    if not lichaam:
        return {}
    grafieken: dict[int, Grafiek] = {}
    for deel in _delen(content_type or "", lichaam):
        plek = _plek(deel)
        if plek >= aantal_visualisaties:
            raise AfbeeldingFout(400, VERKEERDE_PLEK)
        if plek in grafieken:
            raise AfbeeldingFout(400, DUBBEL)
        grafieken[plek] = grafiek(bytes(deel.data))
    return grafieken
