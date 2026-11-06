"""Jaar- en diplomaresultaat en nieuwe vsv'ers per mbo-instelling, uit DUO's indicatoren per instelling (#727).

DUO publiceert elk voorjaar de indicatoren van het geïntegreerd jaardocument mbo als
`{editie}-indicatoren-per-instelling.xlsx`, met de sheets `JR en DR`, `VSV` en `Financieel`. Elke indicator staat per
schooljaar naast de waarde van de vergelijkingsgroep: alle roc's (ROC) of alle beroepscolleges (BER), een gewogen
gemiddelde op deelnemersaantallen. De code leest alleen de nieuwste editie en alleen de eerste twee sheets (besluit
30-10): de financiële kengetallen gelden per bestuur en horen bij #725, en edities mengen geeft andere cijfers voor
hetzelfde schooljaar, omdat DUO herberekent en voorlopige vsv-cijfers definitief worden.

De pagina `indicatoren.jsp` noemt de edities met hun peildatum; de nieuwste wint. Een ontbrekend bestand geeft bij DUO
HTTP 200 met een HTML-foutpagina (soft 404): alleen een antwoord dat geen tekst is en met de zip-handtekening begint,
telt als bestand.

De kolommen komen uit de drie koprijen (indicator, schooljaar, Inst. of Vgl Grp), met de samengevoegde cellen
doorgevuld, niet uit vaste posities. Een onbekende kop, sheet, BRIN of groep laat de tool weigeren in plaats van
gokken. Een lege cel en een exacte 0 zijn "geen cijfer": de editie 2026 gaf 0 bij twee fusie-instellingen waar de
editie 2025 nog 6,44% en 6,39% gaf. Binnen een groep is de groepswaarde per kolom exact gelijk; een afwijking wijst op
verwisselde kolommen.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

import httpx
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from data import instellingen

from . import fouten
from .buiten_de_bron import ALLEEN_AANBIEDEN

BASIS = "https://duo.nl"
PAGINA = f"{BASIS}/open_onderwijsdata/middelbaar-beroepsonderwijs/indicatoren/indicatoren.jsp"
_TIMEOUT_S = 60
_HEADERS = {"User-Agent": "openEDUdata+ (onderwijsdata-chat)"}

_BESTAND = re.compile(r'href="(/open_onderwijsdata/images/(20\d{2})-indicatoren-per-instelling\.xlsx)"')
# Na de link volgen in dezelfde tabelrij de cellen peildatum en publicatiedatum.
_CEL = re.compile(r"<td[^>]*>\s*([^<]*?)\s*</td>")
_DATUM = re.compile(r"\d{1,2} [a-z]+ 20\d{2}")
_RIJBREEDTE = 600

# Per sheet de indicatoren in rij 1, met hun sleutel in de uitkomst. `Financieel` is bekend maar wordt niet gelezen.
SHEETS = {
    "JR en DR": {"Jaarresultaat": "jaarresultaat", "Diplomaresultaat": "diplomaresultaat"},
    "VSV": {"Percentage nieuwe VSV-ers": "nieuwe_vsv"},
}
_BEKENDE_SHEETS = {*SHEETS, "Financieel"}
VSV = "nieuwe_vsv"
_CODE, _GROEP = "Instellingscode", "Vgl Groep"
_OVERIGE_KOPPEN = {"Naam Instelling", "Soort Instelling", "Straat", "Huisnr", "Postcode", "Plaats"}
_KOP_INSTELLING, _KOP_GROEP = "Inst.", "Vgl Grp"
_KOPRIJEN = 3

GROEPEN = {"ROC": "roc's (ROC en ROCV)", "BER": "beroepscolleges (BER en BERV)"}
_BRIN = re.compile(r"\d\d[A-Z]{2}")
_SCHOOLJAAR = re.compile(r"(20\d{2})\s*-\s*(20\d{2})")


class IndicatorenOnbereikbaar(RuntimeError):
    """De pagina noemt geen xlsx-editie, of DUO geeft geen bestand (fout of soft 404)."""


class IndicatorenAfwijkend(RuntimeError):
    """Het bestand wijkt af van de bekende opbouw: de code weigert in plaats van te gokken."""


@dataclass(frozen=True)
class Instelling:
    brin: str
    naam: str  # zoals in het bestand, soms afgekapt ("Mediacollege Amsterdam Ma")
    groep: str  # ROC of BER
    waarden: dict[tuple[str, str], float | None]  # (indicator, schooljaar) → fractie; None = geen cijfer


@dataclass(frozen=True)
class Editie:
    jaar: int
    url: str
    peildatum: str | None  # zoals DUO hem schrijft: 1 oktober 2025
    instellingen: dict[str, Instelling]
    groepswaarden: dict[tuple[str, str, str], float | None]  # (indicator, schooljaar, groep) → fractie
    schooljaren: dict[str, tuple[str, ...]]  # indicator → schooljaren, oud naar nieuw


@dataclass(frozen=True)
class _Kolom:
    indicator: str
    schooljaar: str
    van_groep: bool


def _tekst(waarde) -> str:
    """Een kop- of sleutelcel als tekst, zonder opvulspaties; een jaartal als float (2016.0) wordt 2016."""
    if waarde is None:
        return ""
    if isinstance(waarde, float) and waarde.is_integer():
        waarde = int(waarde)
    return " ".join(str(waarde).split())


def schooljaar(kop: str) -> str | None:
    """`2024-2025` of `2024 - 2025` → `2024/25`; None als het geen schooljaar van twee opeenvolgende jaren is."""
    m = _SCHOOLJAAR.fullmatch(kop)
    if m is None or int(m.group(2)) != int(m.group(1)) + 1:
        return None
    return f"{m.group(1)}/{m.group(2)[2:]}"


def aandeel(waarde) -> float | None:
    """Een percentage als fractie; None bij een lege cel of een exacte 0 (besluit 30-10: geen cijfer)."""
    if waarde is None or (isinstance(waarde, str) and not waarde.strip()):
        return None
    if isinstance(waarde, bool) or not isinstance(waarde, int | float):
        raise IndicatorenAfwijkend(f"geen getal maar {waarde!r}")
    if waarde == 0:
        return None
    if not 0 < waarde <= 1:
        raise IndicatorenAfwijkend(f"percentage {waarde!r} ligt niet tussen 0 en 1")
    return float(waarde)


def _koprijen(blad) -> list[list[str]]:
    """De drie koprijen als tekst, met de waarde van een samengevoegde cel in elke kolom die hij beslaat."""
    rijen = [[_tekst(blad.cell(r, k).value) for k in range(1, blad.max_column + 1)] for r in range(1, _KOPRIJEN + 1)]
    for bereik in blad.merged_cells.ranges:
        if bereik.min_row > _KOPRIJEN:
            continue
        waarde = _tekst(blad.cell(bereik.min_row, bereik.min_col).value)
        for r in range(bereik.min_row, min(bereik.max_row, _KOPRIJEN) + 1):
            for k in range(bereik.min_col, bereik.max_col + 1):
                rijen[r - 1][k - 1] = waarde
    return rijen


def kolommen(sheet: str, koprijen: list[list[str]]) -> tuple[dict[str, int], dict[int, _Kolom]]:
    """De sleutelkolommen en de datakolommen van een sheet, uit de koppen; een onbekende kop is een weigering."""
    indicatoren = SHEETS[sheet]
    sleutels: dict[str, int] = {}
    data: dict[int, _Kolom] = {}
    for k, (boven, midden, kop) in enumerate(zip(*koprijen, strict=True)):
        if not kop:
            continue
        if kop in {_CODE, _GROEP, *_OVERIGE_KOPPEN}:
            if kop in sleutels:
                raise IndicatorenAfwijkend(f"sheet {sheet!r} heeft de kop {kop!r} twee keer")
            sleutels[kop] = k
            continue
        if kop not in (_KOP_INSTELLING, _KOP_GROEP):
            raise IndicatorenAfwijkend(f"onbekende kop {kop!r} in sheet {sheet!r}")
        if boven not in indicatoren or (jaar := schooljaar(midden)) is None:
            raise IndicatorenAfwijkend(f"kolom {kop!r} in sheet {sheet!r} staat onder {boven!r} / {midden!r}")
        kolom = _Kolom(indicatoren[boven], jaar, kop == _KOP_GROEP)
        if kolom in data.values():
            raise IndicatorenAfwijkend(f"sheet {sheet!r} heeft {boven} {jaar} {kop} twee keer")
        data[k] = kolom
    if ontbreekt := {_CODE, _GROEP} - set(sleutels):
        raise IndicatorenAfwijkend(f"sheet {sheet!r} mist de kolom(men) {sorted(ontbreekt)}")
    for indicator in indicatoren.values():
        eigen = {k.schooljaar for k in data.values() if k.indicator == indicator and not k.van_groep}
        groep = {k.schooljaar for k in data.values() if k.indicator == indicator and k.van_groep}
        if not eigen or eigen != groep:
            raise IndicatorenAfwijkend(f"sheet {sheet!r}: {indicator} heeft geen paar Inst./Vgl Grp per schooljaar")
    return sleutels, data


def _lees_sheet(blad, sheet: str, instellingen_: dict[str, Instelling], groepen: dict[tuple, set[float]]) -> None:
    sleutels, data = kolommen(sheet, _koprijen(blad))
    gezien: set[str] = set()
    for rij in blad.iter_rows(min_row=_KOPRIJEN + 1, values_only=True):
        brin = _tekst(rij[sleutels[_CODE]])
        if not brin:
            if any(_tekst(rij[k]) for k in data):
                raise IndicatorenAfwijkend(f"sheet {sheet!r} heeft cijfers in een rij zonder instellingscode")
            continue
        if not _BRIN.fullmatch(brin) or brin in gezien:
            raise IndicatorenAfwijkend(f"sheet {sheet!r}: instellingscode {brin!r} is geen unieke BRIN")
        gezien.add(brin)
        groep = _tekst(rij[sleutels[_GROEP]])
        if groep not in GROEPEN:
            raise IndicatorenAfwijkend(f"sheet {sheet!r}: {brin} heeft de onbekende vergelijkingsgroep {groep!r}")
        naam = _tekst(rij[sleutels["Naam Instelling"]]) if "Naam Instelling" in sleutels else ""
        bekend = instellingen_.setdefault(brin, Instelling(brin, naam, groep, {}))
        if bekend.groep != groep:
            raise IndicatorenAfwijkend(f"{brin} heeft per sheet een andere vergelijkingsgroep")
        for k, kolom in data.items():
            waarde = aandeel(rij[k])
            if kolom.van_groep:
                if waarde is not None:
                    groepen.setdefault((kolom.indicator, kolom.schooljaar, groep), set()).add(waarde)
            else:
                bekend.waarden[(kolom.indicator, kolom.schooljaar)] = waarde


def _groepswaarden(groepen: dict[tuple, set[float]]) -> dict[tuple[str, str, str], float | None]:
    """Eén waarde per groep en kolom; meer dan één wijst op verwisselde kolommen (swap-alarm)."""
    for (indicator, jaar, groep), waarden in groepen.items():
        if len(waarden) > 1:
            raise IndicatorenAfwijkend(
                f"de groepswaarde van {indicator} {jaar} verschilt binnen {groep}: kolommen verwisseld?"
            )
    return {sleutel: next(iter(waarden)) for sleutel, waarden in groepen.items()}


def lees_xlsx(inhoud: bytes) -> tuple[dict[str, Instelling], dict[tuple, float | None], dict[str, tuple[str, ...]]]:
    """De instellingen, de groepswaarden en de schooljaren per indicator uit `JR en DR` en `VSV`."""
    try:
        boek = openpyxl.load_workbook(io.BytesIO(inhoud), data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, ValueError, OSError) as e:
        raise IndicatorenAfwijkend(f"geen leesbaar xlsx-bestand ({type(e).__name__})") from e
    if onbekend := set(boek.sheetnames) - _BEKENDE_SHEETS:
        raise IndicatorenAfwijkend(f"onbekende sheet(s) {sorted(onbekend)}")
    if ontbreekt := set(SHEETS) - set(boek.sheetnames):
        raise IndicatorenAfwijkend(f"de sheet(s) {sorted(ontbreekt)} ontbreken")
    gelezen: dict[str, Instelling] = {}
    groepen: dict[tuple, set[float]] = {}
    for sheet in SHEETS:
        _lees_sheet(boek[sheet], sheet, gelezen, groepen)
    schooljaren: dict[str, set[str]] = {}
    for indicator, jaar in (k for i in gelezen.values() for k in i.waarden):
        schooljaren.setdefault(indicator, set()).add(jaar)
    return gelezen, _groepswaarden(groepen), {i: tuple(sorted(j)) for i, j in schooljaren.items()}


def _xlsx(antwoord: httpx.Response) -> bytes:
    """De inhoud als het een bestand is; een HTML-foutpagina met HTTP 200 (soft 404) is een melding."""
    soort = antwoord.headers.get("content-type", "")
    if soort.startswith("text/") or not antwoord.content.startswith(b"PK"):
        raise IndicatorenOnbereikbaar(f"DUO gaf geen xlsx-bestand maar {soort or 'onbekende inhoud'} (soft 404?)")
    return antwoord.content


def nieuwste_editie(pagina: str) -> tuple[int, str, str | None]:
    """Jaar, URL en peildatum van de nieuwste xlsx-editie op de indicatorenpagina."""
    edities = sorted((int(m.group(2)), m.group(1), m.end()) for m in _BESTAND.finditer(pagina))
    if not edities:
        raise IndicatorenOnbereikbaar("de indicatorenpagina van DUO noemt geen xlsx-editie")
    jaar, pad, eind = edities[-1]
    cellen = _CEL.findall(pagina, eind, eind + _RIJBREEDTE)
    peildatum = cellen[0] if cellen and _DATUM.fullmatch(cellen[0]) else None
    return jaar, BASIS + pad, peildatum


def haal_editie(client: httpx.Client | None = None) -> Editie:
    """De nieuwste editie, gelezen; zonder `client` een eigen verbinding met timeout en herkenbare naam."""
    eigen = client is None
    client = client or httpx.Client(headers=_HEADERS, timeout=_TIMEOUT_S, follow_redirects=True)
    try:
        pagina = client.get(PAGINA)
        pagina.raise_for_status()
        jaar, url, peildatum = nieuwste_editie(pagina.text)
        bestand = client.get(url)
        bestand.raise_for_status()
        inhoud = _xlsx(bestand)
    except httpx.HTTPError as e:
        raise IndicatorenOnbereikbaar(f"DUO antwoordde niet ({type(e).__name__})") from e
    finally:
        if eigen:
            client.close()
    gelezen, groepswaarden, schooljaren = lees_xlsx(inhoud)
    return Editie(jaar, url, peildatum, gelezen, groepswaarden, schooljaren)


@lru_cache(maxsize=1)
def _editie_van(dag: str) -> Editie:
    return haal_editie()


def editie() -> Editie:
    """De nieuwste editie, één keer per dag opgehaald: DUO publiceert één keer per jaar."""
    return _editie_van(date.today().isoformat())


BRONNAAM = "DUO"
BRONTITEL = "Indicatoren per instelling (jaardocument mbo)"
GEEN_CIJFER = "geen cijfer"
_PROCENT = Decimal("0.1")
DEFINITIES = {
    "jaarresultaat": (
        "Aandeel met een diploma onder de deelnemers die in het jaar een diploma haalden of de instelling zonder "
        "diploma verlieten; entree telt niet mee."
    ),
    "diplomaresultaat": (
        "Aandeel met een diploma onder de deelnemers die de instelling in het jaar verlieten; entree telt niet mee."
    ),
    "nieuwe_vsv": (
        "Percentage nieuwe voortijdig schoolverlaters: jonger dan 22 bij de start, op 1 oktober bekostigd "
        "ingeschreven, een jaar later niet ingeschreven in vo, mbo, vavo of hbo en zonder startkwalificatie. Niet "
        "vergelijkbaar met het landelijke vsv-cijfer van CBS (andere definitie en populatie)."
    ),
}


def _procent(fractie: float | None) -> Decimal | None:
    return None if fractie is None else (Decimal(repr(fractie)) * 100).quantize(_PROCENT, rounding=ROUND_HALF_UP)


def _regel(jaar: str, eigen: float | None, groep: float | None, voorlopig: bool) -> dict:
    """Eén schooljaar: instelling en groep in procenten op één decimaal, en het verschil van die afgeronde waarden."""
    inst, vgl = _procent(eigen), _procent(groep)
    uit: dict = {
        "schooljaar": jaar,
        "instelling": None if inst is None else float(inst),
        "vergelijkingsgroep": None if vgl is None else float(vgl),
    }
    if inst is not None and vgl is not None:
        uit["verschil_procentpunt"] = float(inst - vgl)
    else:
        uit["uitleg"] = GEEN_CIJFER
    if voorlopig:
        uit["voorlopig"] = True
    return uit


def _uitkomst(profiel: dict, inst: Instelling, e: Editie) -> dict:
    voorlopig = e.schooljaren.get(VSV, ())[-1:]

    def reeks(indicator: str) -> list[dict]:
        return [
            _regel(
                jaar,
                inst.waarden.get((indicator, jaar)),
                e.groepswaarden.get((indicator, jaar, inst.groep)),
                voorlopig=indicator == VSV and jaar in voorlopig,
            )
            for jaar in e.schooljaren.get(indicator, ())
        ]

    reeksen = {indicator: reeks(indicator) for indicator in DEFINITIES}
    uit: dict = {
        "instelling": {"naam": profiel["naam"], "instellingscode": inst.brin},
        "vergelijkingsgroep": {"code": inst.groep, "omschrijving": GROEPEN[inst.groep]},
        "eenheid": "procent; verschil = instelling min vergelijkingsgroep, in procentpunt",
        **reeksen,
        "definities": DEFINITIES,
        "betekenis": (
            "Cijfers per instelling (BRIN), niet per opleiding, vestiging of bestuur. De vergelijkingsgroep is het "
            f"gewogen gemiddelde van alle {GROEPEN[inst.groep]}, naar deelnemersaantal."
        ),
        "bron": {"naam": f"{BRONNAAM}, {BRONTITEL}", "url": e.url, "editie": e.jaar, "peildatum": e.peildatum},
    }
    noten = []
    if voorlopig:
        noten.append(f"Het vsv-cijfer van {voorlopig[0]} is voorlopig: zeg dat.")
    if any(r.get("uitleg") for rs in reeksen.values() for r in rs):
        noten.append(
            f"Een waarde null is '{GEEN_CIJFER}': DUO gaf voor dat jaar geen cijfer (een lege cel of 0). Noem geen "
            "getal en schat er geen."
        )
    andere = sorted(i.brin for i in e.instellingen.values() if i.naam and i.naam == inst.naam and i.brin != inst.brin)
    if andere:
        noten.append(
            f"Onder dezelfde naam staat ook {', '.join(andere)} in het bestand, met eigen cijfers. Deze cijfers gelden "
            f"alleen voor {inst.brin}: tel of middel ze nooit met die van een andere BRIN."
        )
    if noten:
        uit["noot"] = " ".join(noten)
    return uit


def get_mbo_indicatoren(instelling: str) -> str:
    """Jaarresultaat, diplomaresultaat en nieuwe vsv'ers van een mbo-instelling, met vergelijkingsgroep (#727)."""
    profiel = instellingen.instellingsprofiel(str(instelling or ""))
    if profiel is None:
        return (
            f"Onbekende instelling {instelling!r}: het register kent deze naam of alias niet. Geen gok; controleer de "
            "naam, bijvoorbeeld met get_rio_instelling."
        )
    if profiel.get("sector") != "mbo":
        return (
            f"{profiel['naam']} is een {profiel.get('sector')}-instelling. DUO publiceert jaarresultaat, "
            "diplomaresultaat en vsv per instelling alleen voor het mbo; voor het hoger onderwijs zit zo'n bron niet "
            f"in deze app. {ALLEEN_AANBIEDEN}"
        )
    try:
        gelezen = editie()
    except IndicatorenOnbereikbaar as e:
        oorzaak = e.__cause__ if isinstance(e.__cause__, Exception) else e
        return fouten.bronfout(BRONNAAM, oorzaak, f" Indicatoren per instelling, instelling '{profiel['naam']}'.")
    except IndicatorenAfwijkend as e:
        return fouten.melding(
            fouten.Fout.BRON_FOUT,
            f"{BRONNAAM}: het bestand met indicatoren per instelling wijkt af van de bekende opbouw ({e}). Geen "
            "cijfers; noem geen schatting.",
        )
    inst = gelezen.instellingen.get(profiel["instellingscode"])
    if inst is None:
        return (
            f"{profiel['naam']} ({profiel['instellingscode']}) staat niet in DUO's indicatoren per instelling, editie "
            f"{gelezen.jaar}. Noem geen cijfers. {ALLEEN_AANBIEDEN}"
        )
    return json.dumps(_uitkomst(profiel, inst, gelezen), ensure_ascii=False, separators=(",", ":"))
