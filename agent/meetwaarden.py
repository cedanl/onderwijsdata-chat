"""Welke getallen een toolresultaat als meetwaarde levert (#415).

De getalcontrole (grounding) vraagt alleen of een getal ergens in de tooluitvoer staat:
een opleidingscode 36201, een rijtelling of een stuk van een data_key telt daar mee.
Voor een citatie is dat te zwak; die moet zeggen uit welke cel een getal komt. Hier
staan alleen getypeerde meetwaarden: getallen in een meetkolom van een rij, de uitkomst
van een KPI en het resultaat van een analyse. Codes, identificaties en metadata vallen af.
"""

import json
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace

from tools import TOOL_RUN_ANALYSIS
from tools.analysis import SCRIPTCONSTANTEN
from tools.arbeidsmarkt import ROA_ID, UWV_ID
from tools.kolomlabel import kolomlabel

# Een kolom die iets aanwijst in plaats van meet: OPLEIDINGSCODE, BRIN_NUMMER, CBS' ID.
_IDENTIFICATIE = re.compile(r"code|nummer|brin|(?:^|[_\s])(?:id|nr|key)(?:$|[_\s])", re.IGNORECASE)
# Een jaartal in een periodekolom (STUDIEJAAR 2023) zegt welke rij het is, niet hoeveel.
_PERIODE = re.compile(r"jaar|periode", re.IGNORECASE)
_JAREN = range(1900, 2101)
_LABEL = "_label"
_RIJEN = ("rijen", "preview")
# Zoveel cellen van de rij beschrijven de selectie; meer maakt de uitleg onleesbaar.
_MAX_CELLEN = 6


@dataclass(frozen=True)
class Meetwaarde:
    """Eén getypeerde waarde: onder welke cijfers een tekst haar schrijft, en waar ze staat."""

    cijfers: frozenset[str]
    maat: str
    selectie: tuple[str, ...] = ()  # de andere cellen van haar rij, in woorden
    data_key: str | None = None
    eenheid: str | None = None
    bron: str | None = None  # zonder data_key: de bron in woorden (UWV, ROA)
    rij: int | None = None  # positie in de rijen van de tabel achter data_key (CH-07)


def _getal(waarde) -> frozenset[str] | None:
    """De gehele cijfers van een getal zoals een tekst ze schrijft: afgekapt of afgerond, zonder teken."""
    if isinstance(waarde, bool) or not isinstance(waarde, int | float):
        return None
    try:
        if not math.isfinite(waarde):
            return None
    except OverflowError:  # een int van 309+ cijfers past niet in een float: geen meetwaarde, geen crash
        return None
    n = abs(waarde)
    return frozenset({str(math.trunc(n)), str(round(n))})


def _meetkolom(kolom: str, waarde) -> bool:
    if _getal(waarde) is None or _IDENTIFICATIE.search(kolom):
        return False
    return not (_PERIODE.search(kolom) and waarde in _JAREN)


def _selectie(rij: dict, maat: str) -> tuple[str, ...]:
    """De cellen naast de meetwaarde die zeggen welke rij het is; een label wint van zijn code."""
    gelabeld = {k.upper() for k in rij}
    cellen = [
        f"{kolomlabel(kolom.removesuffix(_LABEL))}: {waarde}"
        for kolom, waarde in rij.items()
        if kolom != maat
        and waarde is not None
        and kolom.upper() != "ID"
        and f"{kolom}{_LABEL}".upper() not in gelabeld
        and not _meetkolom(kolom, waarde)
    ]
    return tuple(cellen[:_MAX_CELLEN])


def _uit_rijen(rijen, data_key: str | None) -> Iterator[Meetwaarde]:
    for positie, rij in enumerate(rijen if isinstance(rijen, list) else ()):
        if not isinstance(rij, dict):
            continue
        for kolom, waarde in rij.items():
            if _meetkolom(kolom, waarde) and (cijfers := _getal(waarde)):
                yield Meetwaarde(cijfers, kolom, _selectie(rij, kolom), data_key, rij=positie)


def _uit_kpi(kpi: dict) -> Iterator[Meetwaarde]:
    bron = kpi["bron"]
    cijfers = _getal(kpi.get("raw"))
    if cijfers is None:
        return
    geschreven = re.sub(r"[^\d,]", "", str(kpi.get("value", ""))).split(",")[0]
    selectie = [f"Berekening: {bron.get('metric')} van {kolomlabel(str(bron.get('kolom')))}"]
    if isinstance(periode := kpi.get("periode"), dict):
        selectie.append(f"Periode: {periode.get('van')} – {periode.get('tot')}")
    yield Meetwaarde(
        cijfers | ({geschreven} if geschreven else set()),
        str(kpi.get("label") or bron.get("kolom")),
        tuple(selectie),
        bron.get("data_key") if isinstance(bron.get("data_key"), str) else None,
        "%" if bron.get("metric") == "pct_change" else None,
    )


def _uit_analyse(resultaat, data_key: str | None) -> Iterator[Meetwaarde]:
    """Wat een analyse teruggaf: een los getal, een dict met uitkomsten of rijen."""
    if (cijfers := _getal(resultaat)) is not None:
        yield Meetwaarde(cijfers, "resultaat", (), data_key)
    # De rijen van een analyse zijn niet die van de tabel achter data_key: geen positie.
    elif isinstance(resultaat, list):
        yield from (replace(w, rij=None) for w in _uit_rijen(resultaat, data_key))
    elif isinstance(resultaat, dict):
        yield from (replace(w, rij=None) for w in _uit_rijen([resultaat], data_key))


# Het sectorgetal telt clusters die deze app aan de sector toewees, naar rato (#449, #460): geen UWV-cijfer.
_UWV_GEWOGEN = "Vacatures in de sector, lokaal gewogen"


def _blok(parsed: dict, naam: str) -> dict:
    blok = parsed.get(naam)
    return blok if isinstance(blok, dict) else {}


def _uit_uwv(parsed: dict) -> Iterator[Meetwaarde]:
    """UWV-vacatures (CH-39): het totaal, de sector en elk beroepencluster, op plaats en peildatum.

    Met een sector staan de clusters in `uwv_broncijfer` en het sectorgetal in `gewogen_aandeel`
    (#460); dat getal is onze weging over onze clustertoewijzing, en de maat zegt dat."""
    bron = f"{parsed.get('bron')}, {parsed.get('peildatum')}"  # de toolbron noemt UWV al
    plaats = tuple(
        f"{label}: {parsed[k]}" for k, label in (("provincie", "Provincie"), ("gemeente", "Gemeente")) if parsed.get(k)
    )
    naam_sector = _blok(parsed, "lokale_classificatie").get("sector")
    sector = (f"Sector: {naam_sector}",) if naam_sector else ()
    gewogen = _blok(parsed, "gewogen_aandeel").get("vacatures_sector")
    for waarde, maat, selectie in (
        (parsed.get("totaal_vacatures"), "Vacatures", plaats),
        (gewogen, _UWV_GEWOGEN, plaats + sector),
    ):
        if (cijfers := _getal(waarde)) is not None:
            yield Meetwaarde(cijfers, maat, selectie, bron=bron)
    clusters = (_blok(parsed, "uwv_broncijfer") or parsed).get("clusters")
    for naam, aantal in clusters.items() if isinstance(clusters, dict) else ():
        if (cijfers := _getal(aantal)) is not None:
            yield Meetwaarde(cijfers, "Vacatures", (*plaats, *sector, f"Beroepencluster: {naam}"), bron=bron)


_ROA_ONDERDELEN = {"schoolverlaters_sis_2024": "Schoolverlaters (SIS 2024)", "prognose_tot_2030": "Prognose tot 2030"}


def _uit_roa(parsed: dict) -> Iterator[Meetwaarde]:
    """ROA per onderdeel, opleiding en indicator (CH-39); de regio per onderdeel uit `herkomst`,
    zodat een landelijke terugval landelijk heet."""
    bron = f"{parsed.get('bron')} ({parsed.get('versie')})"  # "ROA, AIS tot 2030"
    gegeven = parsed.get("herkomst")
    herkomst: dict = gegeven if isinstance(gegeven, dict) else {}
    for onderdeel, naam in _ROA_ONDERDELEN.items():
        regio = herkomst.get(onderdeel) or parsed.get("regio")
        opleidingen = parsed.get(onderdeel)
        for opleiding, indicatoren in opleidingen.items() if isinstance(opleidingen, dict) else ():
            for indicator, waarden in indicatoren.items() if isinstance(indicatoren, dict) else ():
                for soort, waarde in waarden.items() if isinstance(waarden, dict) else ():
                    if (cijfers := _getal(waarde)) is not None:
                        selectie = (f"Opleiding: {opleiding}", f"Regio: {regio}", naam)
                        yield Meetwaarde(
                            cijfers, indicator, selectie, eenheid="%" if soort == "perc" else None, bron=bron
                        )


_ARBEIDSMARKT = {UWV_ID: _uit_uwv, ROA_ID: _uit_roa}


def _uit(parsed, analyse: bool) -> Iterator[Meetwaarde]:
    if isinstance(parsed, dict) and (vertaler := _ARBEIDSMARKT.get(parsed.get("dataset"))):
        yield from vertaler(parsed)
        return
    if not isinstance(parsed, dict):
        if analyse:
            yield from _uit_analyse(parsed, None)
        return
    if "bron" in parsed and parsed["bron"] is None:  # las geen data (#201)
        return
    data_key = parsed.get("data_key") if isinstance(parsed.get("data_key"), str) else None
    if isinstance(parsed.get("bron"), dict) and "raw" in parsed:
        yield from _uit_kpi(parsed)
        return
    for naam in _RIJEN:
        yield from _uit_rijen(parsed.get(naam), data_key)
    if "resultaat" in parsed:
        gelezen = [k for k in parsed.get("gelezen") or () if isinstance(k, str)]
        yield from _uit_analyse(parsed["resultaat"], data_key or next(iter(gelezen), None))
    elif analyse and not data_key and not any(naam in parsed for naam in _RIJEN):
        yield from _uit_analyse(parsed, None)


def _onafhankelijk(parsed) -> set[frozenset[str]]:
    """De getallen van een analyse die niet van de data afhangen (CH-27): geen meetwaarde."""
    waarden = parsed.get(SCRIPTCONSTANTEN) if isinstance(parsed, dict) else None
    return {c for w in waarden if (c := _getal(w)) is not None} if isinstance(waarden, list) else set()


def meetwaarden(result: str, tool: str | None = None) -> list[Meetwaarde]:
    """De getypeerde meetwaarden van één toolresultaat; leeg bij een fout, metadata of een bronloze uitkomst."""
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return []
    eigen = _onafhankelijk(parsed)
    return [w for w in _uit(parsed, tool == TOOL_RUN_ANALYSIS) if w.cijfers not in eigen]


def _codecijfers(waarde) -> str | None:
    """Een code zoals een tekst haar schrijft: 50800, ook als JSON-tekst of als 50800.0 van pandas."""
    if isinstance(waarde, str):
        return waarde if waarde.isascii() and waarde.isdigit() else None
    if isinstance(waarde, float) and waarde.is_integer():
        waarde = int(waarde)
    return str(abs(waarde)) if isinstance(waarde, int) and not isinstance(waarde, bool) else None


def _sleutelwaarden(parsed) -> Iterator[tuple[str, object]]:
    """(sleutel, waarde) op elke diepte; een lijst geeft elk element onder haar eigen sleutel.

    RIO zet een bestuurscode in bevoegd_gezag.code en kandidaten[].code, niet in een rij.
    Met een stapel, niet recursief: een diep genest analyseresultaat haalt de stacklimiet niet."""
    stapel: list[tuple[str | None, object]] = [(None, parsed)]
    while stapel:
        sleutel, waarde = stapel.pop()
        if isinstance(waarde, dict):
            stapel.extend(waarde.items())
        elif isinstance(waarde, list):
            stapel.extend((sleutel, w) for w in waarde)
        elif sleutel is not None:
            yield sleutel, waarde


def _schemacellen(parsed: dict) -> Iterator[tuple[str, object]]:
    """(kolom, waarde) uit het kolomschema van een laadstap: de waardenlijst en de voorbeelden."""
    kolommen = parsed.get("kolommen")
    for k in kolommen if isinstance(kolommen, list) else ():
        if isinstance(k, dict) and isinstance(kolom := k.get("kolom"), str):
            for soort in ("waarden", "voorbeelden"):
                waarden = k.get(soort)
                yield from ((kolom, w) for w in (waarden if isinstance(waarden, list) else ()))


def identificaties(result: str) -> set[str]:
    """De cijfers onder een identificatiesleutel, waar ook in één toolresultaat: OPLEIDINGSCODE 50800 is een code.

    CBS' kolom ID telt niet mee: dat is een rijnummer, geen code die een tekst noemt."""
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return set()
    if not isinstance(parsed, dict):
        return set()
    return {
        cijfers
        for kolom, waarde in (*_sleutelwaarden(parsed), *_schemacellen(parsed))
        if kolom.upper() != "ID" and _IDENTIFICATIE.search(kolom) and (cijfers := _codecijfers(waarde))
    }


def eenheden(result: str) -> dict[str, str]:
    """Kolom → eenheid uit het schema van een laadstap (CBS geeft die per meetkolom)."""
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return {}
    kolommen = parsed.get("kolommen") if isinstance(parsed, dict) else None
    return {
        k["kolom"]: k["eenheid"]
        for k in kolommen or ()
        if isinstance(k, dict) and isinstance(k.get("kolom"), str) and isinstance(k.get("eenheid"), str)
    }
