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
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from onderwijsbronnen.duo.financien import KENGETALLEN

from tools import TOOL_RUN_ANALYSIS, financien, studiekeuze, wo_personeel
from tools.analysis import SCRIPTCONSTANTEN
from tools.arbeidsmarkt import ROA_ID, ROA_ONDERDELEN, UWV_ID, roa_blokken
from tools.kolomlabel import kolomlabel

from . import kpi_bron

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
    # De bron in woorden: zonder data_key (een UWV- of ROA-resultaat van vóór #577), of een voorgeschreven bronregel
    # (WOPI) en een vaste waarde van een andere bron dan de tabel (de signaleringswaarden van de Inspectie, #956).
    bron: str | None = None
    rij: int | None = None  # positie in de rijen van de tabel achter data_key (CH-07)
    # De waarde zonder teken, voor een getal met decimale komma in de tekst (0,69; 2,0 %; `schrijft`): alleen van een
    # bron die afgeronde decimalen geeft (financien, WOPI; #956). Een getal met komma krijgt alleen zo een citatie.
    decimaal: Decimal | None = None


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


def _uit_kpi(kpi: kpi_bron.Kpi) -> Iterator[Meetwaarde]:
    """Een KPI is één meetwaarde: het getal zelf, en de cijfers zoals de tool het schreef (#420)."""
    bron = kpi.bron or {}
    cijfers = _getal(kpi.raw)
    if cijfers is None:
        return
    geschreven = re.sub(r"[^\d,]", "", kpi.waarde).split(",")[0]
    selectie = [f"Berekening: {bron.get('metric')} van {kolomlabel(str(bron.get('kolom')))}"]
    if kpi.periode is not None:
        selectie.append(f"Periode: {kpi.periode.get('van')} – {kpi.periode.get('tot')}")
    yield Meetwaarde(
        cijfers | ({geschreven} if geschreven else set()),
        str(kpi.label or bron.get("kolom")),
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


def _arbeidsmarktbron(parsed: dict, tekst: str) -> tuple[str | None, str | None]:
    """(data_key, bron): met een data_key wijst de citatie naar de tabel in de store, die de bron en de
    peildatum of versie zelf kent (#577); een ouder resultaat zonder key houdt de bron in woorden."""
    data_key = parsed.get("data_key") if isinstance(parsed.get("data_key"), str) else None
    return data_key, None if data_key else tekst


def _uit_uwv(parsed: dict) -> Iterator[Meetwaarde]:
    """UWV-vacatures (CH-39): het totaal, de sector en elk beroepencluster, op plaats en peildatum.

    Met een sector staan de clusters in `uwv_broncijfer` en het sectorgetal in `gewogen_aandeel`
    (#460); dat getal is onze weging over onze clustertoewijzing, en de maat zegt dat."""
    data_key, bron = _arbeidsmarktbron(
        parsed, f"{parsed.get('bron')}, {parsed.get('peildatum')}"
    )  # de toolbron noemt UWV al
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
            yield Meetwaarde(cijfers, maat, selectie, data_key, bron=bron)
    clusters = (_blok(parsed, "uwv_broncijfer") or parsed).get("clusters")
    for naam, aantal in clusters.items() if isinstance(clusters, dict) else ():
        if (cijfers := _getal(aantal)) is not None:
            yield Meetwaarde(cijfers, "Vacatures", (*plaats, *sector, f"Beroepencluster: {naam}"), data_key, bron=bron)


def _uit_roa(parsed: dict) -> Iterator[Meetwaarde]:
    """ROA per onderdeel, opleiding en indicator (CH-39); de regio per onderdeel uit `herkomst`,
    zodat een landelijke terugval landelijk heet. Bij een ho-onderdeel ook de gekoppelde categorieën en de
    opleidingstypen (#745), elk met hun eigen herkomst."""
    data_key, bron = _arbeidsmarktbron(parsed, f"{parsed.get('bron')} ({parsed.get('versie')})")  # "ROA, AIS tot 2030"
    for blok in roa_blokken(parsed):
        gegeven = blok.get("herkomst")
        herkomst: dict = gegeven if isinstance(gegeven, dict) else {}
        for onderdeel, naam in ROA_ONDERDELEN.items():
            regio = herkomst.get(onderdeel) or blok.get("regio")
            opleidingen = blok.get(onderdeel)
            for opleiding, indicatoren in opleidingen.items() if isinstance(opleidingen, dict) else ():
                for indicator, waarden in indicatoren.items() if isinstance(indicatoren, dict) else ():
                    for soort, waarde in waarden.items() if isinstance(waarden, dict) else ():
                        if (cijfers := _getal(waarde)) is not None:
                            selectie = (f"Opleiding: {opleiding}", f"Regio: {regio}", naam)
                            eenheid = "%" if soort == "perc" else None
                            yield Meetwaarde(cijfers, indicator, selectie, data_key, eenheid, bron)


_AFRONDINGEN = (ROUND_HALF_UP, ROUND_HALF_EVEN)


def schrijft(waarde: Meetwaarde, geschreven: Decimal) -> bool:
    """Schrijft een tekst deze waarde als `geschreven` (zonder teken): dezelfde waarde op de decimalen van de tekst,
    half naar boven of half naar even afgerond. 0,50 is 0,5 maar niet 0,57; 3,2 is 3,17 en 3,24."""
    if waarde.decimaal is None:
        return False
    exponent = geschreven.as_tuple().exponent
    if not isinstance(exponent, int):  # oneindig of NaN: geen getal uit een tekst
        return False
    stap = Decimal(1).scaleb(exponent)
    return any(waarde.decimaal.quantize(stap, wijze) == geschreven for wijze in _AFRONDINGEN)


def _afgerond(waarde, maat: str, selectie: tuple[str, ...], data_key, eenheid=None, bron=None) -> Iterator[Meetwaarde]:
    """Eén waarde zoals een tool met een eigen resultaatvorm haar afgerond geeft, met haar decimale waarde (#956)."""
    if (cijfers := _getal(waarde)) is not None:
        decimaal = abs(Decimal(repr(waarde)))
        yield Meetwaarde(cijfers, maat, selectie, data_key, eenheid, bron, decimaal=decimaal)


def _sleutel(parsed: dict) -> str | None:
    return parsed.get("data_key") if isinstance(parsed.get("data_key"), str) else None


# De kengetallen onder hun naam in de uitkomst van get_bestuursfinancien (rentabiliteit in procent), met de naam zoals
# een zin hem noemt: "liquiditeit", niet "Liquiditeit (current ratio)".
_KENGETALLEN = {
    ("rentabiliteit_procent" if k.sleutel == "rentabiliteit" else k.sleutel): k.naam.split(" (")[0] for k in KENGETALLEN
}


def _uit_jaar(jaar: dict, eenheid: dict, sector: str, data_key, inspectie: str) -> Iterator[Meetwaarde]:
    """De getallen van één verslagjaar van één eenheid: per kengetal bestuur, sectorcijfer en verschil; rijksbijdragen
    en de signaleringswaarden van de Inspectie (met die bron, niet die van DUO).

    De maat is het kengetal; wat het getal ervan is (het sectorcijfer, het verschil, de signaleringswaarde) staat als
    cel in de selectie, zodat een zin die "sector" of "signaleringswaarde" zegt de juiste kandidaat aanwijst (CH-08)."""
    verslagjaar = f"Verslagjaar: {jaar.get('verslagjaar')}"
    bestuur = (f"Bestuur: {eenheid.get('naam')}", verslagjaar, f"Variant: {jaar.get('variant')}")
    rollen = {
        "bestuur": bestuur,
        "sector": (f"Sectorcijfer: {sector}", verslagjaar),
        "verschil": (*bestuur, f"Verschil met de sector: {sector}"),
    }
    for sleutel, naam in _KENGETALLEN.items():
        waarden = _blok(jaar, sleutel)
        procent = "%" if sleutel == "rentabiliteit_procent" else None
        for rol, selectie in rollen.items():
            yield from _afgerond(waarden.get(rol), naam, selectie, data_key, procent)
    yield from _afgerond(jaar.get("rijksbijdragen_eur"), "Rijksbijdragen", bestuur, data_key, "€")
    yield from _afgerond(jaar.get("rijksbijdragen_mln_eur"), "Rijksbijdragen", bestuur, data_key, "€ mln")
    yield from _afgerond(jaar.get("werkplaatsfunctie_eur"), "Rijksbijdrage werkplaatsfunctie", bestuur, data_key, "€")
    grenzen = {"liquiditeit": jaar.get("liquiditeit_signaleringswaarde")}
    for signaal in jaar.get("signaleringen") or ():
        if isinstance(signaal, dict) and signaal.get("kengetal") in _KENGETALLEN:
            grenzen.setdefault(signaal["kengetal"], signaal.get("signaleringswaarde"))
    for kengetal, grens in grenzen.items():
        selectie = (*bestuur, "Grens: signaleringswaarde")
        yield from _afgerond(grens, _KENGETALLEN[kengetal], selectie, data_key, bron=inspectie)


def _uit_financien(parsed: dict) -> Iterator[Meetwaarde]:
    """get_bestuursfinancien (#935, #956): per eenheid en verslagjaar de kengetallen van het bestuur, het sectorcijfer
    en het verschil, de rijksbijdragen en de signaleringswaarden; en het aantal eenheden in het sectorcijfer."""
    data_key = _sleutel(parsed)
    sectorcijfer = _blok(parsed, "sectorcijfer")
    sector = str(sectorcijfer.get("sector"))
    waarden = _blok(parsed, "signaleringswaarden")
    inspectie = f"{waarden.get('bron')} ({waarden.get('jaar')})"
    for eenheid in parsed.get("eenheden") or ():
        reeks = eenheid.get("reeks") if isinstance(eenheid, dict) else None
        for jaar in reeks if isinstance(reeks, list) else ():
            if isinstance(jaar, dict):
                yield from _uit_jaar(jaar, eenheid, sector, data_key, inspectie)
    for jaar, aantal in _blok(sectorcijfer, "eenheden_per_jaar").items():
        per_kengetal = aantal.items() if isinstance(aantal, dict) else [(None, aantal)]
        for kengetal, n in per_kengetal:
            selectie = (
                f"Sectorcijfer: {sector}",
                f"Verslagjaar: {jaar}",
                *([f"Kengetal: {kengetal}"] if kengetal else []),
            )
            yield from _afgerond(n, "Eenheden", selectie, data_key)


# De kolommen van get_wo_personeel die geen functie, aanstelling of leeftijdsklasse zijn, in woorden.
_WOPI_MATEN = {
    "totaal": "Personeel",
    "wetenschappelijk_personeel": "Wetenschappelijk personeel",
    "obp": "Ondersteunend en beheerspersoneel (OBP)",
    "vrouwen": "Vrouwen",
    "aandeel_vrouwen_procent": "Aandeel vrouwen",
    "aandeel_tijdelijk_procent": "Aandeel tijdelijk",
}
_WOPI_GROEP = {"vast_tijdelijk": "Aanstelling", "leeftijd": "Leeftijd"}


def _wopi_maat(kolom: str, uitsplitsing: str) -> str:
    if maat := _WOPI_MATEN.get(kolom) or wo_personeel.FUNCTIES.get(kolom):
        return maat
    return f"{_WOPI_GROEP[uitsplitsing]} {kolom}" if uitsplitsing in _WOPI_GROEP else kolom


def _uit_wopi(parsed: dict) -> Iterator[Meetwaarde]:
    """get_wo_personeel (#936, #956): elk getal van elk jaar, in fte of personen; een aandeel in procent. De citatie
    noemt de voorgeschreven bronregel, met de GEZO-variant."""
    data_key = _sleutel(parsed)
    instelling = parsed.get("instelling")
    naam = instelling.get("naam") if isinstance(instelling, dict) else "landelijk"
    regel = _blok(parsed, "bron").get("regel")
    gezo = wo_personeel.GEZO_KORT.get(str(parsed.get("gezo")), str(parsed.get("gezo")))
    for rij in parsed.get("cijfers") or ():
        if not isinstance(rij, dict):
            continue
        selectie = (f"Instelling: {naam}", f"Peildatum: {rij.get('peildatum')}", f"Variant: {gezo}")
        for kolom, waarde in rij.items():
            if kolom in ("jaar", "peildatum"):
                continue
            eenheid = "%" if kolom.endswith("_procent") else parsed.get("eenheid")
            maat = _wopi_maat(kolom, str(parsed.get("uitsplitsing")))
            yield from _afgerond(waarde, maat, selectie, data_key, eenheid, regel if isinstance(regel, str) else None)


# De velden van een rij van get_studiekeuze die zeggen waar de rij over gaat (#957), in woorden; een code is geen maat.
_SKDB_SELECTIE = {
    "instelling": "Instelling",
    "opleiding": "Opleiding",
    "studie": "Studie",
    "bachelor": "Bachelor",
    "master": "Master",
    "mbo_opleiding": "Mbo-opleiding",
    "hbo_studie": "Hbo-studie",
    "vorm": "Vorm",
    "plaats": "Plaats",
    "voertaal": "Voertaal",
    "studiejaar": "Studiejaar",
}
_SKDB_GEEN_MAAT = {
    "croho",
    "studiecode",
    "master_studiecode",
    "master_croho",
    "rang",
    "numerus_fixus_studiejaar",
    "keren_meedoen",
}


def _skdb_eenheid(kolom: str) -> str | None:
    if kolom.endswith("_pct"):
        return "%"
    return "€" if kolom.startswith("salaris") else None


def _uit_skdb(parsed: dict) -> Iterator[Meetwaarde]:
    """get_studiekeuze (#957): elk getal van elke getoonde rij, met instelling, opleiding en vorm als selectie en de
    voorgeschreven bronregel van LCSK."""
    data_key = _sleutel(parsed)
    regel = _blok(parsed, "bron").get("regel")
    for rij in parsed.get("rijen") or ():
        if not isinstance(rij, dict):
            continue
        selectie = tuple(
            f"{label}: {rij[veld]}" for veld, label in _SKDB_SELECTIE.items() if rij.get(veld) not in (None, "")
        )
        for kolom, waarde in rij.items():
            if kolom in _SKDB_SELECTIE or kolom in _SKDB_GEEN_MAAT:
                continue
            yield from _afgerond(
                waarde,
                kolomlabel(kolom),
                selectie,
                data_key,
                _skdb_eenheid(kolom),
                regel if isinstance(regel, str) else None,
            )


# Per dataset de vertaler van een tool met een eigen resultaatvorm: arbeidsmarkt (CH-39), financien en WOPI (#956), de
# Studiekeuzedatabase (#957).
_EIGEN_VORM = {
    UWV_ID: _uit_uwv,
    ROA_ID: _uit_roa,
    financien.DATASET: _uit_financien,
    wo_personeel.DATASET: _uit_wopi,
    studiekeuze.DATASET: _uit_skdb,
}


def _uit(parsed, analyse: bool) -> Iterator[Meetwaarde]:
    if isinstance(parsed, dict) and (vertaler := _EIGEN_VORM.get(parsed.get("dataset"))):
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
        if (kpi := kpi_bron.kpi(parsed)) is not None:
            yield from _uit_kpi(kpi)
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
