from __future__ import annotations

import contextvars
import difflib
import functools
import logging
import numbers
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pandas as pd
from riodata import duo

from core import actualiteit, brongebruik
from core.logging_util import foutkenmerk, tekst_kenmerk
from core.sentinels import mask_sentinels

from . import arbeidsmarkt, bronblok
from .instellingen import get_adres_lookup, resolve_alias
from .instellingen import get_all as get_all_instellingen

logger = logging.getLogger(__name__)

_INSTROOM_MBO = "INSTROOM MBO"
_BOL_VOLTIJD = "BOL voltijd"
_BOL_DEELTIJD = "BOL deeltijd"


# ─── Wat er niet laadde (#901) ───────────────────────────────────────────────

BRON_NIET_BESCHIKBAAR = "De DUO-data is nu niet beschikbaar. Probeer het over een paar minuten opnieuw."


@dataclass(frozen=True)
class _Onderdeel:
    """Een onderdeel dat een dashboard kan missen: de naam zoals de gebruiker hem leest, en de bron erachter. Aan de
    bron ziet de frontend welke gaten bij welk dashboard horen: /api/dashboard/regio dient er twee."""

    naam: str
    bron: str


_ONDERDEEL_KAART = _Onderdeel("Kaart", "DUO")
_ONDERDEEL_HOOFDGROEPEN = _Onderdeel("Ingeschrevenen per hoofdgroep", "DUO")
_ONDERDEEL_EERSTEJAARS = _Onderdeel("Eerstejaars", "DUO")
_ONDERDEEL_GEDIPLOMEERDEN = _Onderdeel("Gediplomeerden", "DUO")
_ONDERDEEL_INSTROOM = _Onderdeel("Instroom per jaar", "DUO")
_ONDERDEEL_RENDEMENT_REGIO = _Onderdeel("Rendement van de regio", "DUO")
_ONDERDEEL_VACATURES = _Onderdeel("Vacatures (UWV)", "UWV")
_ONDERDEEL_ROA_SCHOOLVERLATERS = _Onderdeel("Arbeidsmarktpositie schoolverlaters (ROA)", "ROA")
_ONDERDEEL_ROA_PROGNOSE = _Onderdeel("Arbeidsmarktprognose (ROA)", "ROA")


class BronNietBeschikbaar(Exception):
    """De instelling is niet te vinden omdat een hoofdbron niet laadde: dat is geen "niet gevonden" (#901)."""

    def __init__(self) -> None:
        super().__init__(BRON_NIET_BESCHIKBAAR)


@dataclass
class _Gaten:
    """Wat er tijdens één dashboardlading niet laadde: onderdeel → reden, en of een hoofdbron uitviel."""

    onderdelen: dict[_Onderdeel, str] = field(default_factory=dict)
    hoofdbron_mislukt: bool = False


# Per lading, in de thread die laadt: de onderdelen hieronder melden hun gat zonder dat elke aanroep een lijst
# doorgeeft. Buiten een dashboardlading (een test die een onderdeel los aanroept) is er geen verzameling.
_gaten: contextvars.ContextVar[_Gaten | None] = contextvars.ContextVar("dashboard_gaten", default=None)


def _reden(e: Exception) -> str:
    """Waarom een onderdeel ontbreekt, in woorden voor de gebruiker; nooit de fouttekst zelf (#502)."""
    if isinstance(e, (TimeoutError, httpx.TimeoutException)):
        return "de bron antwoordde niet op tijd"
    if isinstance(e, httpx.HTTPStatusError):
        return f"de bron antwoordde met HTTP {e.response.status_code}"
    if isinstance(e, (OSError, httpx.TransportError)):
        return "de bron was niet bereikbaar"
    return "de data van de bron kon niet worden verwerkt"


def _niet_beschikbaar(
    e: Exception, bericht: str, *args, onderdeel: _Onderdeel | None = None, instelling: str | None = None
) -> None:
    """Een onderdeel dat niet laadt: op WARNING het type en een kenmerk, de traceback op DEBUG (#819).

    Met `onderdeel` komt het gat ook in de payload (`niet_beschikbaar`), zodat het dashboard het noemt in plaats van
    het onderdeel stil weg te laten (#901). De fouttekst van httpx citeert de request-URL, een traceback de waarden
    in de aanroep (#502): die gaan niet mee. De gevraagde `instelling` is een ongevalideerde queryparameter, dus
    gebruikerstekst: op WARNING alleen haar lengte en hash, de naam zelf op DEBUG (#907).
    """
    if instelling is None:
        logger.warning(bericht + ": %s", *args, foutkenmerk(e))
        logger.debug(bericht, *args, exc_info=e)
    else:
        logger.warning(bericht + " (%s): %s", *args, tekst_kenmerk(instelling, "instelling_"), foutkenmerk(e))
        logger.debug(bericht + " voor %s", *args, instelling, exc_info=e)
    gaten = _gaten.get()
    if gaten is not None and onderdeel is not None:
        gaten.onderdelen.setdefault(onderdeel, _reden(e))


def _hoofdbron_niet_beschikbaar(e: Exception, bericht: str, instelling: str) -> None:
    """De lading die zegt of de instelling bestaat, mislukte: wordt ze nergens gevonden, dan is dat een storing."""
    _niet_beschikbaar(e, bericht, instelling=instelling)
    gaten = _gaten.get()
    if gaten is not None:
        gaten.hoofdbron_mislukt = True


def _dashboardlading(laad: Callable[[str], dict]) -> Callable[[str], dict]:
    """Een dashboard-eindpunt: verzamelt wat er niet laadde en zet het in de payload (#901).

    - Niet gevonden terwijl een hoofdbron uitviel: BronNietBeschikbaar, geen `gevonden: False` met "pas de naam aan".
    - Gevonden met gaten: `niet_beschikbaar` = [{onderdeel, bron, reden}], in de volgorde waarin ze uitvielen.
    - Gevonden: `bronnen`, het bronblok van wat de lading gebruikte (#904, data/bronblok.py).
    """

    @functools.wraps(laad)
    def binnen(instelling: str) -> dict:
        gaten = _Gaten()
        token = _gaten.set(gaten)
        try:
            with brongebruik.verzamel() as gebruikt:
                result = laad(instelling)
        finally:
            _gaten.reset(token)
        if not result.get("gevonden") and gaten.hoofdbron_mislukt:
            raise BronNietBeschikbaar
        if result.get("gevonden"):
            result["bronnen"] = bronblok.blok(gebruikt)
        if gaten.onderdelen:
            result["niet_beschikbaar"] = [
                {"onderdeel": o.naam, "bron": o.bron, "reden": r} for o, r in gaten.onderdelen.items()
            ]
        return result

    return binnen


def _poging(laad: Callable[..., dict | None], *args) -> dict | None:
    """Zoek de instelling in één sector. Vindt de poging haar niet, dan tellen de bestanden die ze daarvoor laadde
    niet als gebruikt: een mbo-dashboard rust niet op p01hoinges omdat de ho-poging daar de naam zocht (#904)."""
    with brongebruik.verzamel() as gebruikt:
        uit = laad(*args)
    if uit:
        brongebruik.meld(*gebruikt)
    return uit


_MAX_VACATURE_CLUSTERS = 8
_MAX_SUGGESTIONS = 5  # zoveel toont het dashboard
# Waarom een onbekende instelling geen suggesties heeft, en waar ze wel op te vinden is (#929).
_GEEN_SUGGESTIES = "Geen instellingsnaam lijkt hierop. Zoek op de naam, een afkorting of de instellingscode (BRIN)."
# De leerwegkolommen van mbo-studenten-per-instelling met hun naam in het dashboard. Samen zijn ze het totaal
# ingeschrevenen; een verdeling die er één weglaat, telt niet op tot dat totaal (Extraneus, #899).
_MBO_LEERWEGEN = {"BBL": "BBL", _BOL_VOLTIJD: "BOLVT", _BOL_DEELTIJD: "BOLDT", "Extraneus": "EX"}
_MBO_LEERWEG_COLS = list(_MBO_LEERWEGEN.values())
# TOTAAL MBO in instromende-mbo-studenten telt de ingeschrevenen, nieuw of niet: geen instroom en geen diploma's
# (domeinregel mbo-instroom-totaal-mbo, #899).
_MBO_INGESCHREVEN_KOLOM = "TOTAAL MBO"
_HOOFDGROEP = "HOOFDGROEP NAAM"
_SECTOR_GEMIDDELD_JAREN = 3  # de aanbodzijde van de arbeidsmarktmatch: gediplomeerden, gemiddeld over 3 jaar
_MATCH_DREMPEL = 1.2  # verhouding vacatures/diploma's waarboven schaarste resp. overaanbod

# Handgemaakte referentielijsten met datum en bron (#316); zie tests/test_referentielijsten.py.
REFERENTIELIJSTEN: dict[str, dict[str, str]] = {
    "_CITY_COORDS": {"bijgewerkt": "2026-07-30", "bron": "handmatig: benaderde coördinaten van onderwijssteden"},
}

# Approximate coordinates for Dutch educational cities (PLAATSNAAM uppercase → lat/lon).
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "AMSTERDAM": (52.374, 4.899),
    "ROTTERDAM": (51.922, 4.480),
    "'S-GRAVENHAGE": (52.081, 4.313),
    "DEN HAAG": (52.081, 4.313),
    "HAAG": (52.081, 4.313),
    "UTRECHT": (52.091, 5.114),
    "EINDHOVEN": (51.438, 5.480),
    "GRONINGEN": (53.222, 6.568),
    "TILBURG": (51.560, 5.090),
    "ALMERE": (52.370, 5.215),
    "BREDA": (51.588, 4.776),
    "NIJMEGEN": (51.842, 5.853),
    "ENSCHEDE": (52.222, 6.897),
    "HAARLEM": (52.381, 4.637),
    "ARNHEM": (51.985, 5.899),
    "AMERSFOORT": (52.157, 5.389),
    "'S-HERTOGENBOSCH": (51.696, 5.304),
    "DEN BOSCH": (51.696, 5.304),
    "MAASTRICHT": (50.852, 5.691),
    "LEIDEN": (52.160, 4.494),
    "DORDRECHT": (51.810, 4.668),
    "ZWOLLE": (52.508, 6.090),
    "LEEUWARDEN": (53.201, 5.799),
    "ALKMAAR": (52.631, 4.750),
    "DELFT": (52.012, 4.357),
    "APELDOORN": (52.217, 5.967),
    "DEVENTER": (52.254, 6.163),
    "VENLO": (51.370, 6.173),
    "EDE": (52.048, 5.665),
    "ZAANDAM": (52.438, 4.819),
    "WAGENINGEN": (51.968, 5.665),
    "MEPPEL": (52.698, 6.196),
    "ROOSENDAAL": (51.530, 4.461),
    "DRACHTEN": (53.107, 6.099),
    "ROERMOND": (51.194, 5.987),
    "SITTARD": (51.001, 5.870),
    "HEERLEN": (50.889, 5.979),
    "MIDDELBURG": (51.499, 3.614),
    "VLISSINGEN": (51.453, 3.573),
    "LELYSTAD": (52.517, 5.469),
    "EMMEN": (52.785, 6.899),
    "ASSEN": (52.992, 6.563),
    "ZUTPHEN": (52.138, 6.197),
    "HELMOND": (51.482, 5.665),
    "DOETINCHEM": (51.963, 6.296),
    "HARDERWIJK": (52.340, 5.619),
    "KAMPEN": (52.554, 5.914),
    "ALMELO": (52.358, 6.664),
    "HENGELO": (52.265, 6.792),
    "ZOETERMEER": (52.059, 4.500),
    "ALPHEN AAN DEN RIJN": (52.132, 4.659),
    "PURMEREND": (52.503, 4.954),
    "SNEAK": (53.033, 5.659),
    "SNEEK": (53.033, 5.659),
    "VENRAY": (51.527, 5.978),
    "SITTARD-GELEEN": (51.001, 5.870),
    "GOES": (51.505, 3.889),
    "TERNEUZEN": (51.335, 3.830),
    "BERGEN OP ZOOM": (51.495, 4.287),
    "WOERDEN": (52.088, 4.887),
    "NIEUWEGEIN": (52.033, 5.083),
    "HOUTEN": (52.031, 5.168),
    "ZEIST": (52.088, 5.229),
    "BUSSUM": (52.274, 5.163),
    "HILVERSUM": (52.224, 5.179),
    "ZAANSTAD": (52.438, 4.819),
    "GOUDA": (52.017, 4.707),
    "SCHIEDAM": (51.916, 4.387),
    "SPIJKENISSE": (51.845, 4.331),
    "HOOFDDORP": (52.302, 4.692),
    "AMSTERDAM-ZUIDOOST": (52.317, 4.966),
    "DIEMEN": (52.336, 4.949),
    "WEESP": (52.308, 5.040),
}


# ─── Regio context ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RegioContext:
    """Benchmark regio voor een instelling: arbeidsmarktregio (voorkeur) of provincie (fallback)."""

    regio_naam: str  # Naam van de benchmark-regio
    regio_type: str  # "arbeidsmarktregio" | "provincie"
    provincie: str | None  # Altijd de provincie (voor UWV-data en display)
    self_code: str  # BRIN-code van de target-instelling
    peer_codes: frozenset  # BRIN-codes van peers in dezelfde regio (excl. zichzelf)


def _build_regio_context(instelling_naam: str, onderwijs_type: str) -> RegioContext | None:
    """
    Bouw een RegioContext voor benchmarking.

    onderwijs_type: "ho" (hbo + wo samen) of "mbo"

    Probeert arbeidsmarktregio; valt terug op provincie als er < 1 peer is.
    Retourneert None als er geen bruikbare context gevonden kan worden.
    """
    adres = get_adres_lookup()
    registry = get_all_instellingen()

    target = next((i for i in registry if i["naam"].lower() == instelling_naam.lower()), None)
    if not target:
        return None

    self_code = target.get("instellingscode")
    if not self_code or self_code not in adres:
        return None

    self_info = adres[self_code]
    provincie = self_info.get("provincie")
    arbeidsmarktregio = self_info.get("arbeidsmarktregio")

    peer_types = {"hbo", "wo"} if onderwijs_type == "ho" else {"mbo"}
    code_to_type = {inst["instellingscode"]: inst["type"] for inst in registry if inst.get("instellingscode")}

    # WO research universities are distributed nationally, not clustered in one
    # arbeidsmarktregio. Use all WO institutions as peers for a meaningful benchmark.
    if target.get("type") == "wo":
        wo_peers = frozenset(
            inst["instellingscode"]
            for inst in registry
            if inst.get("type") == "wo"
            and inst.get("instellingscode") != self_code
            and inst.get("instellingscode") in adres
        )
        if wo_peers:
            return RegioContext(
                regio_naam="Nationaal (WO)",
                regio_type="nationaal",
                provincie=provincie,
                self_code=self_code,
                peer_codes=wo_peers,
            )

    def _peers_for_regio(regio_key: str, regio_value: str) -> frozenset:
        return frozenset(
            code
            for code, info in adres.items()
            if info.get(regio_key) == regio_value and code != self_code and code_to_type.get(code) in peer_types
        )

    if arbeidsmarktregio:
        peers = _peers_for_regio("arbeidsmarktregio", arbeidsmarktregio)
        if peers:
            return RegioContext(
                regio_naam=arbeidsmarktregio,
                regio_type="arbeidsmarktregio",
                provincie=provincie,
                self_code=self_code,
                peer_codes=peers,
            )

    if provincie:
        peers = _peers_for_regio("provincie", provincie)
        if peers:
            return RegioContext(
                regio_naam=provincie,
                regio_type="provincie",
                provincie=provincie,
                self_code=self_code,
                peer_codes=peers,
            )

    return None


# ─── Sommen met onderdrukte en ontbrekende cellen (#902) ─────────────────────
# _duo_load maskeert DUO's -1 tot een lege cel; een cel kan ook in het bestand leeg zijn. Een som telt een lege cel
# niet mee en is dan een ondergrens ("ten minste"): elke lader meldt daarom per reeks hoeveel lege cellen erin vallen
# (`onderdrukt`). Een groep met alleen lege cellen krijgt geen waarde (een gat in de reeks), geen 0. Zo houdt het
# dashboard "ontbreekt" gescheiden van 0, zoals de chat (core/sentinels.py).

Kolommen = str | list[str]


def _als_lijst(kolommen: Kolommen) -> list[str]:
    return [kolommen] if isinstance(kolommen, str) else list(kolommen)


def _som(df: pd.DataFrame, by, kolommen: Kolommen) -> pd.Series:
    """Som per groep over de telkolommen; NaN als elke cel van de groep leeg is."""
    return df.groupby(by)[_als_lijst(kolommen)].sum(min_count=1).sum(axis=1, min_count=1)


def _leeg(df: pd.DataFrame, by, kolommen: Kolommen) -> pd.Series:
    """Per groep het aantal lege cellen in de telkolommen."""
    return df.assign(_leeg=df[_als_lijst(kolommen)].isna().sum(axis=1)).groupby(by)["_leeg"].sum()


def _sleutel(k) -> int | str:
    """Een jaar als int, een sector of instelling als str (pandas geeft numpy-getallen)."""
    return int(k) if isinstance(k, numbers.Number) else str(k)


def _ints(series: pd.Series) -> dict:
    """{sleutel: int} zonder de groepen zonder waarde, op volgorde van de sleutel."""
    return {_sleutel(k): int(v) for k, v in series.dropna().sort_index().items()}


def _alleen_leeg(series: pd.Series) -> dict:
    """Alleen de groepen met minstens één lege cel."""
    return {_sleutel(k): int(v) for k, v in series.items() if v}


def _reeks(df: pd.DataFrame, jaar_col: str, kolommen: Kolommen) -> tuple[dict[int, int], dict[int, int]]:
    """({jaar: som}, {jaar: lege cellen}): een jaar met alleen lege cellen ontbreekt, een jaar met lege cellen is een
    ondergrens."""
    return _ints(_som(df, jaar_col, kolommen)), _alleen_leeg(_leeg(df, jaar_col, kolommen))


def _genest(df: pd.DataFrame, buiten: str, binnen: str, kolommen: Kolommen) -> tuple[dict, dict]:
    """({buiten: {binnen: som}}, {buiten: {binnen: lege cellen}}), zonder lege groepen."""

    def nest(series: pd.Series) -> dict:
        uit: dict = {}
        for sleutel, v in series.items():
            b, j = sleutel  # ty: ignore[not-iterable] — de index is (buiten, binnen)
            uit.setdefault(_sleutel(b), {})[int(j)] = int(v)
        return uit

    leeg = _leeg(df, [buiten, binnen], kolommen)
    return nest(_som(df, [buiten, binnen], kolommen).dropna()), nest(leeg[leeg > 0])


def _met_onderdrukt(result: dict, sleutel: str, leeg: dict) -> None:
    """Zet de lege cellen van een reeks onder result["onderdrukt"][sleutel], alleen als er een is."""
    if leeg:
        result.setdefault("onderdrukt", {})[sleutel] = leeg


# ─── Benchmark helpers ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _PeerReeks:
    """Eén reeks over de peers van een regio, alleen over de peers met gegevens (#903, #925).

    Een peer met in elk jaar 0 of een lege cel (BBO de Schalm: elk jaar 0 en een onderdrukte cel) heeft geen gegevens.
    Hij telt niet mee in het gemiddelde, het aantal peers, het totaal en de lege cellen; hij staat in `geen_gegevens`,
    zodat de lijst en het aantal niet stil uiteenlopen. Een peer met één echt nuljaar en verder waarden telt wel mee.
    """

    gemiddelde: dict[int, float]  # {jaar: gemiddelde over de peers met een waarde in dat jaar}
    n_per_jaar: dict[int, int]  # {jaar: aantal peers achter dat gemiddelde}; niet elke peer heeft elk jaar een waarde
    per_peer: dict[str, dict[int, int]]  # {naam: {jaar: waarde}}; een jaar met alleen lege cellen ontbreekt
    leeg: dict[int, int]  # {jaar: lege cellen}: het gemiddelde en het totaal van zo'n jaar zijn een ondergrens
    totaal: dict[int, int]  # {jaar: som over de peers}
    geen_gegevens: list[str]  # de peers zonder één waarde boven 0, op naam


def _peer_reeks(
    df: pd.DataFrame,
    code_col: str,
    inst_col: str,
    peer_codes: frozenset,
    jaar_col: str,
    kolommen: Kolommen,
) -> _PeerReeks:
    """De reeks van de peers in `peer_codes` (waarden van code_col), met hun naam uit inst_col."""
    subset = df[df[code_col].isin(peer_codes)]
    namen = subset.groupby(code_col)[inst_col].first()
    per_inst = _som(subset, [code_col, jaar_col], kolommen).dropna()
    met_gegevens = per_inst[per_inst > 0].index.unique(level=code_col)
    subset = subset[subset[code_col].isin(met_gegevens)]
    per_inst = per_inst[per_inst.index.get_level_values(code_col).isin(met_gegevens)]
    per_jaar = per_inst.groupby(level=jaar_col)
    return _PeerReeks(
        gemiddelde={int(k): round(float(v), 1) for k, v in per_jaar.mean().items()},
        n_per_jaar=_ints(per_jaar.count()),
        per_peer={str(namen[c]): _ints(r.droplevel(code_col)) for c, r in per_inst.groupby(level=code_col)},
        leeg=_alleen_leeg(_leeg(subset, jaar_col, kolommen)),
        totaal=_ints(_som(subset, jaar_col, kolommen)),
        geen_gegevens=sorted(str(namen[c]) for c in namen.index.difference(met_gegevens)),
    )


def _met_aantal_peers(bm: dict, sleutel: str, n_per_jaar: dict[int, int]) -> None:
    """Zet het aantal peers achter het gemiddelde per jaar onder bm["n_per_jaar"][sleutel]; `n_instellingen` is dat
    aantal in het laatste jaar met ingeschrevenen, niet het aantal instellingen in het register van de regio (#903)."""
    bm.setdefault("n_per_jaar", {})[sleutel] = n_per_jaar
    if sleutel == "ingeschrevenen":
        bm["n_instellingen"] = n_per_jaar[max(n_per_jaar)] if n_per_jaar else 0


def _met_geen_gegevens(bm: dict, sleutel: str, reeks: _PeerReeks) -> None:
    if reeks.geen_gegevens:
        bm.setdefault("geen_gegevens", {})[sleutel] = reeks.geen_gegevens


def _met_gemiddelde(bm: dict, sleutel: str, reeks: _PeerReeks) -> None:
    """Het regiogemiddelde van een reeks in de benchmark: per jaar, met het aantal peers en de lege cellen erachter."""
    bm[sleutel] = reeks.gemiddelde
    _met_aantal_peers(bm, sleutel, reeks.n_per_jaar)
    _met_onderdrukt(bm, sleutel, reeks.leeg)
    _met_geen_gegevens(bm, sleutel, reeks)


def _met_peers(bm: dict, sleutel: str, reeks: _PeerReeks) -> None:
    """De peers van een reeks in de benchmark: wie meetelt onder `peers`, wie geen gegevens heeft onder `geen_gegevens`."""
    bm.setdefault("peers", {})[sleutel] = reeks.per_peer
    _met_geen_gegevens(bm, sleutel, reeks)


# ─── Een mbo-instelling over al haar codes (#923) ────────────────────────────
# mbo-studenten-per-instelling kent een instelling met meer codes (Curio: 21CY en 25LX); de instroom- en
# diplomabestanden tellen per code. Elke mbo-telling per instelling loopt daarom over de naam die
# mbo-studenten-per-instelling bij de code geeft, zoals de ingeschrevenen: eigen reeks, peers en rendement.

_INSTELLING = "INSTELLING"


def _mbo_code_naam(df_mbo: pd.DataFrame) -> dict[str, str]:
    """{instellingscode: instellingsnaam} uit mbo-studenten-per-instelling."""
    rijen = df_mbo.drop_duplicates("INSTELLINGSCODE")
    return dict(zip(rijen["INSTELLINGSCODE"].astype(str), rijen["INSTELLINGSNAAM"].astype(str), strict=True))


def _mbo_per_instelling(df: pd.DataFrame, code_naam: dict[str, str]) -> pd.DataFrame:
    """df met de kolom INSTELLING: de naam bij de code. Een code buiten mbo-studenten-per-instelling hoort bij niemand."""
    return df.assign(**{_INSTELLING: df["INSTELLINGSCODE"].astype(str).map(code_naam)})


def _mbo_peernamen(ctx: RegioContext, code_naam: dict[str, str], eigen: str) -> frozenset[str]:
    """De peers op naam. De regiocontext noemt één code per instelling (die van het register); de naam brengt de andere
    codes mee. De eigen instelling valt eruit, ook onder een tweede code."""
    return frozenset(code_naam[c] for c in ctx.peer_codes if c in code_naam) - {eigen}


def _mbo_instroom(df: pd.DataFrame | None, code_naam: dict[str, str]) -> pd.DataFrame:
    """De eerstejaars mbo (INSTROOM MBO = J) uit instromende-mbo-studenten, met hun instelling."""
    if df is None or df.empty:
        df = pd.DataFrame(columns=["INSTELLINGSCODE", "JAAR", "AANTAL", _INSTROOM_MBO])
    return _mbo_per_instelling(df[df[_INSTROOM_MBO] == "J"], code_naam)


def _mbo_eerstejaars(instroom: pd.DataFrame, naam: str) -> tuple[dict[int, int], dict[int, int]]:
    """({jaar: eerstejaars}, {jaar: lege cellen}) van één instelling, over al haar codes."""
    return _reeks(instroom[instroom[_INSTELLING] == naam], "JAAR", "AANTAL")


def _benchmark_label(ctx: RegioContext) -> str:
    if ctx.regio_type == "nationaal":
        return "Nationaal WO gemiddelde (excl. eigen instelling)"
    type_label = "Arbeidsmarktregio" if ctx.regio_type == "arbeidsmarktregio" else "Provincie"
    return f"{type_label} gemiddelde ({ctx.regio_naam}, excl. eigen instelling)"


# ─── Regiodashboard ──────────────────────────────────────────────────────────


def _build_kaart_figure(ctx: RegioContext, instelling_naam: str) -> str | None:
    """Return Plotly Scattergeo figure JSON for instelling locations in the benchmark regio.

    De punten staan op benaderde stadscoördinaten (_CITY_COORDS). Wie in een plaats buiten die lijst zit, valt van de
    kaart; layout.meta noemt die instellingen (zonder_locatie) en geeft de punten als rijen (data), zodat de app ze
    kan melden en de kaart als tabel kan tonen als ze niet tekent (#906).
    """
    try:
        import plotly.graph_objects as go
        import plotly.io as pio

        adres = get_adres_lookup()
        registry = get_all_instellingen()
        code_to_naam = {inst["instellingscode"]: inst["naam"] for inst in registry if inst.get("instellingscode")}

        def _plaats(code: str) -> str:
            return (adres.get(code, {}).get("plaatsnaam") or "").upper()

        def _coords(code: str) -> tuple[float, float] | None:
            return _CITY_COORDS.get(_plaats(code))

        def _rij(code: str, naam: str, rol: str) -> dict[str, str]:
            return {"Instelling": naam, "Plaats": _plaats(code).title(), "Rol": rol}

        fig = go.Figure()
        rijen: list[dict[str, str]] = []
        zonder_locatie: list[str] = []

        peer_lons, peer_lats, peer_texts = [], [], []
        for code in sorted(ctx.peer_codes, key=lambda c: code_to_naam.get(c, c)):
            naam = code_to_naam.get(code, code)
            c = _coords(code)
            if c:
                peer_lats.append(c[0])
                peer_lons.append(c[1])
                peer_texts.append(naam)
                rijen.append(_rij(code, naam, "concurrent"))
            else:
                zonder_locatie.append(naam)

        if peer_lons:
            fig.add_trace(
                go.Scattergeo(
                    lon=peer_lons,
                    lat=peer_lats,
                    text=peer_texts,
                    mode="markers",
                    # 3:1 tegen het land in beide thema's (#905); #94A3B8 haalde 2,5:1.
                    marker={"size": 10, "color": "#64748B", "line": {"width": 1, "color": "white"}},
                    hovertemplate="%{text}<extra></extra>",
                    name="Concurrenten",
                )
            )

        own = _coords(ctx.self_code)
        if not own:
            zonder_locatie.insert(0, instelling_naam)
        else:
            rijen.insert(0, _rij(ctx.self_code, instelling_naam, "eigen instelling"))
            fig.add_trace(
                go.Scattergeo(
                    lon=[own[1]],
                    lat=[own[0]],
                    text=[instelling_naam],
                    mode="markers+text",
                    textposition="top right",
                    textfont={"size": 12, "color": "#1E40AF"},
                    marker={"size": 16, "color": "#2563EB", "symbol": "star", "line": {"width": 1.5, "color": "white"}},
                    hovertemplate="%{text}<extra></extra>",
                    name=instelling_naam,
                )
            )

        # Dynamic bounding box: zoom to the actual cluster of locations
        all_lats = peer_lats + ([own[0]] if own else [])
        all_lons = peer_lons + ([own[1]] if own else [])
        if all_lats:
            lat_min, lat_max = min(all_lats), max(all_lats)
            lon_min, lon_max = min(all_lons), max(all_lons)
            lat_spread = max(lat_max - lat_min, 0.25)
            lon_spread = max(lon_max - lon_min, 0.35)
            lat_range = [lat_min - lat_spread * 0.65, lat_max + lat_spread * 0.65]
            lon_range = [lon_min - lon_spread * 0.65, lon_max + lon_spread * 0.65]
        else:
            lat_range = [50.3, 53.9]
            lon_range = [3.0, 7.8]

        fig.update_layout(
            meta={"data": rijen, "zonder_locatie": zonder_locatie},
            showlegend=True,
            legend={
                "x": 0,
                "y": 1,
                "bgcolor": "rgba(255,255,255,0.9)",
                "bordercolor": "#E2E8F0",
                "borderwidth": 1,
                "font": {"size": 11},
            },
            margin={"t": 10, "b": 10, "l": 10, "r": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            height=340,
            geo={
                "scope": "europe",
                "resolution": 50,
                "showcountries": True,
                "countrycolor": "#CBD5E1",
                "showcoastlines": False,
                "showland": True,
                "landcolor": "#F8FAFC",
                "showocean": True,
                "oceancolor": "#EFF6FF",
                "showlakes": False,
                "lataxis": {"range": lat_range},
                "lonaxis": {"range": lon_range},
                "bgcolor": "rgba(0,0,0,0)",
            },
        )
        return pio.to_json(fig)
    except Exception as e:
        _niet_beschikbaar(e, "kaart-figure: kon Plotly-kaart niet bouwen", onderdeel=_ONDERDEEL_KAART)
        return None


def _duo_load(dataset_id: str, resource: int) -> pd.DataFrame:
    """DUO-data met -1 gemaskeerd, zoals de chat-tools hem zien (#228).

    Elke DUO-lading van de dashboards loopt hierlangs: anders tellen onderdrukte
    cellen als -1 mee (BBO de Schalm: -1 studenten; Grafisch Lyceum 2377 i.p.v. 2379).
    Het bestand meldt zich met zijn versie van riodata voor het bronblok (#904, #717).
    """
    df = duo.load(dataset_id, resource)
    versie = df.attrs.get("bron") or {}
    brongebruik.meld(
        {
            "bron": "DUO",
            "dataset": dataset_id,
            "resource": resource,
            "resource_id": versie.get("resource_id"),
            "last_modified": versie.get("last_modified"),
            "opgehaald_op": actualiteit.nu().isoformat(),
        }
    )
    return mask_sentinels(df)[0]


@actualiteit.Lading
def _load_mbo_studenten() -> pd.DataFrame:
    return _duo_load("mbo-studenten-per-instelling", 0)


@actualiteit.Lading
def _load_mbo_gediplomeerden() -> pd.DataFrame:
    return _duo_load("gediplomeerde-mbo-studenten", 0)


# De resources van instromende-mbo-studenten met JAAR + INSTELLINGSCODE + INSTROOM MBO (J/N) + AANTAL: per jaar het
# bestand "met soorten instroom" (2021 tot en met 2025). Het andere bestand van elk jaar (0, 2, …) is per hoofdgroep,
# zonder JAAR. Vast, net als de fixtures (scripts/duo_testfixtures.py): ze opvragen kost een live CKAN-aanroep per
# lading, en de pytest-job draait zonder netwerk. Publiceert DUO een jaar, dan wordt de ping duo-instroom-mbo van
# scripts/bronping.py rood (instromende_mbo_afwijkingen) tot het jaar hier en in de fixtures staat (#924).
_INSTROMENDE_MBO = "instromende-mbo-studenten"
_INSTROMENDE_MBO_HISTORISCH = (1, 3, 5, 7, 9)
_INSTROMENDE_MBO_SOORT = "met-soorten-instroom"  # in de resourcenaam bij CKAN
# Het bestand per hoofdgroep van het laatste jaar (TOTAAL MBO per HOOFDGROEP NAAM), met dat jaar. Het bestand heeft geen
# JAAR-kolom: het jaar staat alleen vooraan in de resourcenaam ("2025 nieuw-instromende-…-hoofdgroep-…"). Vast om
# dezelfde reden als de lijst hierboven, en dezelfde ping wordt rood zodra CKAN een nieuwer hoofdgroep-bestand heeft.
# Tot #934 laadden de dashboards hier bestand 0, dat van 2021, als "laatste jaar".
_INSTROMENDE_MBO_HOOFDGROEP = 8
_INSTROMENDE_MBO_HOOFDGROEP_JAAR = 2025
_INSTROMENDE_MBO_HOOFDGROEP_SOORT = "-hoofdgroep-"  # in de resourcenaam bij CKAN


def instromende_mbo_afwijkingen() -> list[str]:
    """Waar de CKAN-lijst van instromende-mbo-studenten afwijkt van de vaste bestanden van de dashboards (live).

    Een bestand met soorten instroom dat de dashboards niet laden (DUO publiceerde een jaar), of een index in
    _INSTROMENDE_MBO_HISTORISCH die geen zo'n bestand meer is (DUO verschoof de volgorde) (#924). En een nieuwste
    hoofdgroep-bestand dat niet _INSTROMENDE_MBO_HOOFDGROEP van _INSTROMENDE_MBO_HOOFDGROEP_JAAR is (#934). Leeg als
    ze overeenkomen.
    """
    namen = [r.get("naam", "") for r in duo.resources(_INSTROMENDE_MBO)]
    return _soorten_afwijkingen(namen) + _hoofdgroep_afwijkingen(namen)


def _soorten_afwijkingen(namen: list[str]) -> list[str]:
    soorten = {i for i, naam in enumerate(namen) if _INSTROMENDE_MBO_SOORT in naam}
    nieuw = [
        f"bestand {i} ({namen[i]}) staat niet in _INSTROMENDE_MBO_HISTORISCH (data/dashboard.py)"
        for i in sorted(soorten - set(_INSTROMENDE_MBO_HISTORISCH))
    ]
    weg = [
        f"bestand {i} uit _INSTROMENDE_MBO_HISTORISCH is bij CKAN geen bestand met soorten instroom"
        for i in _INSTROMENDE_MBO_HISTORISCH
        if i not in soorten
    ]
    return nieuw + weg


def _hoofdgroep_afwijkingen(namen: list[str]) -> list[str]:
    """Het nieuwste hoofdgroep-bestand bij CKAN, naar het jaar vooraan in de naam, tegen het bestand dat we laden."""
    jaren = {i: int(naam[:4]) for i, naam in enumerate(namen) if _INSTROMENDE_MBO_HOOFDGROEP_SOORT in naam}
    vast = (_INSTROMENDE_MBO_HOOFDGROEP, _INSTROMENDE_MBO_HOOFDGROEP_JAAR)
    if not jaren:
        return ["CKAN heeft geen hoofdgroep-bestand meer (_INSTROMENDE_MBO_HOOFDGROEP, data/dashboard.py)"]
    nieuwste = max(jaren, key=lambda i: (jaren[i], i))
    if (nieuwste, jaren[nieuwste]) == vast:
        return []
    return [
        f"het nieuwste hoofdgroep-bestand bij CKAN is bestand {nieuwste} ({jaren[nieuwste]}), niet bestand {vast[0]} "
        f"({vast[1]}) uit _INSTROMENDE_MBO_HOOFDGROEP (data/dashboard.py)"
    ]


@actualiteit.Lading
def _load_instromende_mbo_historisch() -> pd.DataFrame:
    """Alle jaren samen, of een fout: een ontbrekende resource gaf eerder stil minder jaren, en dat bleef in de
    cache tot de pod herstartte (#901)."""
    return pd.concat([_duo_load(_INSTROMENDE_MBO, i) for i in _INSTROMENDE_MBO_HISTORISCH], ignore_index=True)


@actualiteit.Lading
def _load_instromende_mbo_hoofdgroep() -> pd.DataFrame:
    """INSTELLINGSNAAM + HOOFDGROEP NAAM + TOTAAL MBO in _INSTROMENDE_MBO_HOOFDGROEP_JAAR (#934)."""
    return _duo_load(_INSTROMENDE_MBO, _INSTROMENDE_MBO_HOOFDGROEP)


def _mbo_leerwegen(rij: pd.Series) -> dict[str, int]:
    """De ingeschrevenen van één jaar per leerweg, Extraneus inbegrepen: samen het totaal ingeschrevenen (#899)."""
    return {naam: int(rij[kolom]) for naam, kolom in _MBO_LEERWEGEN.items() if pd.notna(rij[kolom])}


def _mbo_sectoren(rij: pd.Series) -> dict[str, int]:
    """De leerwegen van het laatste jaar als verdeling, aflopend, zonder lege leerweg. Eén regel voor regio- en
    instellingsdashboard: eerder liet het regiodashboard Extraneus weg en telde het totaal hem wel mee (#899)."""
    return {k: v for k, v in sorted(_mbo_leerwegen(rij).items(), key=lambda x: -x[1]) if v > 0}


def _mbo_ingeschrevenen_per_hoofdgroep(instelling: str) -> tuple[dict[str, int], dict[str, int]]:
    """({hoofdgroep: ingeschrevenen}, {hoofdgroep: lege cellen}) in _INSTROMENDE_MBO_HOOFDGROEP_JAAR, het laatste jaar
    van instromende-mbo-studenten.

    TOTAAL MBO telt wie in het mbo ingeschreven staat, nieuw of niet: geen eerstejaars en geen gediplomeerden
    (domeinregel mbo-instroom-totaal-mbo, #899). Het is een ander DUO-bestand dan mbo-studenten-per-instelling: de
    som per hoofdgroep wijkt af van het totaal ingeschrevenen daaruit.
    """
    try:
        df = _load_instromende_mbo_hoofdgroep()
        rows = df[df["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
        if rows.empty:
            return {}, {}
        counts = _som(rows, _HOOFDGROEP, _MBO_INGESCHREVEN_KOLOM).dropna().sort_values(ascending=False)
        som = {str(k): int(v) for k, v in counts.items() if v > 0}
        return som, _alleen_leeg(_leeg(rows, _HOOFDGROEP, _MBO_INGESCHREVEN_KOLOM))
    except Exception as e:
        _niet_beschikbaar(e, "mbo-hoofdgroepen: niet beschikbaar", onderdeel=_ONDERDEEL_HOOFDGROEPEN)
        return {}, {}


def _mbo_dipl_lang(df_dipl: pd.DataFrame) -> pd.DataFrame:
    """Het brede bestand gediplomeerde-mbo-studenten (DIPMAN2021, DIPVROUW2021, …) als rijen met JAAR en AANTAL."""
    dip_cols = [c for c in df_dipl.columns if c.startswith("DIP")]
    sleutels = [c for c in df_dipl.columns if c not in dip_cols]
    lang = df_dipl.melt(id_vars=sleutels, value_vars=dip_cols, var_name="_KOLOM", value_name="AANTAL")
    lang["JAAR"] = lang["_KOLOM"].str[-4:].astype(int)
    return lang.drop(columns="_KOLOM")


def _gemiddeld_per_sector(df: pd.DataFrame, jaar_col: str, sector_col: str, waarde_col: str) -> dict[str, int]:
    """Gediplomeerden per sector, gemiddeld over de laatste _SECTOR_GEMIDDELD_JAREN jaren; sectoren zonder weg."""
    jaren = sorted(df[jaar_col].dropna().unique())[-_SECTOR_GEMIDDELD_JAREN:]
    recent = df[df[jaar_col].isin(jaren)]
    gem = recent.groupby([jaar_col, sector_col])[waarde_col].sum().groupby(sector_col).mean()
    return {str(k): int(round(v)) for k, v in gem.items() if v > 0}  # noqa: RUF046 — round(numpy.float64) is geen int


@actualiteit.Lading
def _load_ho_dataset(dataset_id: str) -> pd.DataFrame:
    """hbo (resource 0) en wo (resource 1) van één ho-dataset samen. Per dataset een eigen lading: een dashboard dat
    alleen de ingeschrevenen gebruikt, laadt en noemt in zijn bronblok de andere twee niet (#904)."""
    return pd.concat([_duo_load(dataset_id, 0), _duo_load(dataset_id, 1)], ignore_index=True)


def _load_ho_ingeschrevenen() -> pd.DataFrame:
    return _load_ho_dataset("p01hoinges")


def _load_ho_gediplomeerden() -> pd.DataFrame:
    return _load_ho_dataset("p04hogdipl")


def _load_ho_full() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return _load_ho_ingeschrevenen(), _load_ho_dataset("p02ho1ejrs"), _load_ho_gediplomeerden()


def _mode_str(series: pd.Series) -> str | None:
    vals = series.dropna()
    if vals.empty:
        return None
    return str(vals.mode().iloc[0])


def _uwv_vacatures_provincie(provincie: str, sectoren: tuple[str, ...] = ()) -> dict:
    """Top-N vacatures per provincie, optioneel gefilterd op instellingssectoren.

    Bedoeld voor weergave-overzichten (UwvSection). Gebruik
    arbeidsmarkt.vacatures_per_sector voor supply-demand berekeningen.
    """
    try:
        stand = arbeidsmarkt.uwv_stand(provincie)
    except Exception as e:
        _niet_beschikbaar(
            e, "uwv: vacatureclusters voor %s niet beschikbaar", provincie, onderdeel=_ONDERDEEL_VACATURES
        )
        return {}
    if not stand:
        return {}

    if sectoren:
        gefilterd = arbeidsmarkt.relevante_clusters(stand.clusters, sectoren)
        if gefilterd:
            top = dict(sorted(gefilterd.items(), key=lambda x: -x[1])[:_MAX_VACATURE_CLUSTERS])
            return {
                "totaal": stand.totaal,
                "peildatum": stand.peildatum,
                "clusters": top,
                "gefilterd_op": sorted(sectoren),
            }

    top = dict(list(stand.clusters.items())[:_MAX_VACATURE_CLUSTERS])
    return {
        "totaal": stand.totaal,
        "peildatum": stand.peildatum,
        "clusters": top,
        "gefilterd_op": [],
    }


def _uwv_clusters_voor_sectoren(provincie: str, sectoren: tuple[str, ...]) -> dict[str, int]:
    try:
        return arbeidsmarkt.clusters_voor_sectoren(provincie, sectoren)
    except Exception as e:
        _niet_beschikbaar(
            e, "uwv: vacatureclusters voor %s niet beschikbaar", provincie, onderdeel=_ONDERDEEL_VACATURES
        )
        return {}


def _uwv_vacatures_per_sector(provincie: str, sectoren: tuple[str, ...]) -> dict[str, int]:
    try:
        return arbeidsmarkt.vacatures_per_sector(provincie, sectoren)
    except Exception as e:
        _niet_beschikbaar(
            e, "uwv: vacatures per sector voor %s niet beschikbaar", provincie, onderdeel=_ONDERDEEL_VACATURES
        )
        return {}


# Zonder eigen cache: de ROA-tabel zelf staat in arbeidsmarkt._roa (met TTL), dit filtert er alleen uit. Met
# functools.cache bleef de `{}` na één storing voorgoed staan (#901).
def _roa_prognose(onderwijs_type: str) -> dict:
    """ROA arbeidsmarktprognoses tot 2030 per opleidingsniveau (typering), landelijk."""
    try:
        waarden = arbeidsmarkt.roa_prognose(arbeidsmarkt.ROA_NIVEAUS[onderwijs_type])
    except Exception as e:
        _niet_beschikbaar(e, "roa: prognose %s niet beschikbaar", onderwijs_type, onderdeel=_ONDERDEEL_ROA_PROGNOSE)
        return {}
    uit = {n: {o: w["typering"] for o, w in ow.items() if "typering" in w} for n, ow in waarden.items()}
    return {n: ow for n, ow in uit.items() if ow}


def _roa_schoolverlaters(onderwijs_type: str) -> dict:
    """ROA-schoolverlatersinformatie (SIS 2024) per opleidingsniveau, in hele procenten, landelijk."""
    try:
        waarden = arbeidsmarkt.roa_schoolverlaters(arbeidsmarkt.ROA_NIVEAUS[onderwijs_type])
    except Exception as e:
        _niet_beschikbaar(
            e, "roa: schoolverlaters %s niet beschikbaar", onderwijs_type, onderdeel=_ONDERDEEL_ROA_SCHOOLVERLATERS
        )
        return {}
    uit = {n: {o: round(w["perc"]) for o, w in ow.items() if "perc" in w} for n, ow in waarden.items()}
    return {n: ow for n, ow in uit.items() if ow}


def _geslacht(df: pd.DataFrame) -> dict[str, int]:
    """Ingeschrevenen per geslacht: altijd VROUW en MAN, en elke andere waarde die het bestand heeft (ONBEKEND)."""
    per = df.groupby("GESLACHT")["AANTAL_INGESCHREVENEN"].sum()
    return {g: int(per.get(g, 0)) for g in dict.fromkeys(["VROUW", "MAN", *map(str, per.index)])}


def _ho_kern(hu_inges: pd.DataFrame, hu_ej: pd.DataFrame, hu_dipl: pd.DataFrame) -> dict:
    """De reeksen van één ho-instelling op het regiodashboard (#899, #902)."""
    result: dict = {}
    result["ingeschrevenen"], leeg = _reeks(hu_inges, "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    _met_onderdrukt(result, "ingeschrevenen", leeg)
    laatste_jaar = max(result["ingeschrevenen"], default=int(hu_inges["STUDIEJAAR"].max()))
    result["laatste_jaar"] = laatste_jaar
    laatste = hu_inges[hu_inges["STUDIEJAAR"] == laatste_jaar]
    result["geslacht"] = _geslacht(laatste)
    sectoren = _som(laatste, "ONDERDEEL", "AANTAL_INGESCHREVENEN").dropna().sort_values(ascending=False)
    result["sectoren"] = {str(k): int(v) for k, v in sectoren.items()}
    _met_onderdrukt(result, "sectoren", _alleen_leeg(_leeg(laatste, "ONDERDEEL", "AANTAL_INGESCHREVENEN")))
    for sleutel, df, jaar_col, kolom in (
        ("eerstejaars", hu_ej, "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"),
        ("gediplomeerden", hu_dipl, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"),
    ):
        reeks, leeg = _reeks(df, jaar_col, kolom)
        if reeks:
            result[sleutel] = reeks
            _met_onderdrukt(result, sleutel, leeg)
    return result


def _ho_regio_benchmark(ctx, df_inges, df_ej, df_dipl, code_col, inst_col) -> dict:
    reeksen = {
        "ingeschrevenen": (df_inges, "STUDIEJAAR", "AANTAL_INGESCHREVENEN"),
        "eerstejaars": (df_ej, "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"),
        "gediplomeerden": (df_dipl, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"),
    }
    bm: dict = {"label": _benchmark_label(ctx), "regio_type": ctx.regio_type, "peers": {}}
    for sleutel, (df, jaar_col, kolom) in reeksen.items():
        reeks = _peer_reeks(df, code_col, inst_col, ctx.peer_codes, jaar_col, kolom)
        _met_gemiddelde(bm, sleutel, reeks)
        if sleutel == "ingeschrevenen":
            bm["totaal_ingeschrevenen"] = reeks.totaal
        if sleutel != "eerstejaars":
            _met_peers(bm, sleutel, reeks)
    return bm


def _load_dashboard_regio_ho(instelling: str) -> dict | None:
    try:
        df_inges, df_ej, df_dipl = _load_ho_full()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "regio-ho: data laden mislukt", instelling)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    code_col = "INSTELLINGSCODE_ACTUEEL"

    hu_inges = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu_inges.empty:
        return None

    ctx = _build_regio_context(instelling, "ho")
    provincie = ctx.provincie if ctx else _mode_str(hu_inges["PROVINCIENAAM"])

    _self_code_ho = str(hu_inges[code_col].iloc[0])
    _self_amr = get_adres_lookup().get(_self_code_ho, {}).get("arbeidsmarktregio")

    result: dict = {"type": "ho"}
    result["provincie"] = provincie or "Onbekend"
    result["arbeidsmarktregio"] = _self_amr

    hu_ej = df_ej[df_ej[inst_col].str.lower() == instelling.lower()]
    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    result.update(_ho_kern(hu_inges, hu_ej, hu_dipl))
    laatste = hu_inges[hu_inges["STUDIEJAAR"] == result["laatste_jaar"]]

    result["geslacht_trend"] = {int(jaar): _geslacht(grp) for jaar, grp in hu_inges.groupby("STUDIEJAAR")}
    result["geslacht_per_sector"] = {str(onderdeel): _geslacht(grp) for onderdeel, grp in laatste.groupby("ONDERDEEL")}
    # Sector trend: per onderdeel per studiejaar (stacked area frontend). Een jaar zonder waarde blijft een gat.
    result["sectoren_trend"], leeg = _genest(hu_inges, "ONDERDEEL", "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    _met_onderdrukt(result, "sectoren_trend", leeg)

    if ctx:
        result["benchmark"] = _ho_regio_benchmark(ctx, df_inges, df_ej, df_dipl, code_col, inst_col)
        result["kaart_figure_json"] = _build_kaart_figure(ctx, instelling)

    result["arbeidsmarkt_roa"] = _roa_schoolverlaters("ho")
    result["arbeidsmarkt_prognose"] = _roa_prognose("ho")
    ho_sectoren = tuple(sorted(result.get("sectoren", {}).keys()))
    result["vacatureaanbod"] = _uwv_vacatures_provincie(provincie, ho_sectoren) if provincie else {}
    return result


def _mbo_regio_benchmark(ctx, df_mbo, instroom, df_dipl_mbo, code_naam, eigen) -> dict:
    """De regiovergelijking van een mbo-instelling: elke peer op naam, over al zijn codes (#923). Gediplomeerden
    alleen per peer, zonder gemiddelde."""
    peers = _mbo_peernamen(ctx, code_naam, eigen)

    def reeks(df: pd.DataFrame, kolommen: Kolommen) -> _PeerReeks:
        return _peer_reeks(df, _INSTELLING, _INSTELLING, peers, "JAAR", kolommen)

    bm: dict = {"label": _benchmark_label(ctx), "regio_type": ctx.regio_type, "peers": {}}
    ingeschrevenen = reeks(_mbo_per_instelling(df_mbo, code_naam), _MBO_LEERWEG_COLS)
    eerstejaars = reeks(instroom, "AANTAL")
    for sleutel, r in (("ingeschrevenen", ingeschrevenen), ("eerstejaars", eerstejaars)):
        _met_gemiddelde(bm, sleutel, r)
        _met_peers(bm, sleutel, r)
    bm["totaal_ingeschrevenen"] = ingeschrevenen.totaal
    if df_dipl_mbo is not None:
        _met_peers(bm, "gediplomeerden", reeks(_mbo_per_instelling(_mbo_dipl_lang(df_dipl_mbo), code_naam), "AANTAL"))
    return bm


_Reeks = tuple[dict[int, int], dict[int, int]]


def _mbo_load_gediplomeerden(inst_col: str, instelling: str) -> tuple[pd.DataFrame | None, _Reeks]:
    try:
        df = _load_mbo_gediplomeerden()
        return df, _mbo_dipl_reeks(df, inst_col, instelling)
    except Exception as e:
        _niet_beschikbaar(e, "regio-mbo: gediplomeerden niet beschikbaar", onderdeel=_ONDERDEEL_GEDIPLOMEERDEN)
        return None, ({}, {})


def _mbo_load_eerstejaars(code_naam: dict[str, str], eigen: str) -> tuple[pd.DataFrame, _Reeks]:
    """(de eerstejaars van alle instellingen, de reeks van de eigen instelling); leeg als de bron niet laadde."""
    try:
        instroom = _mbo_instroom(_load_instromende_mbo_historisch(), code_naam)
    except Exception as e:
        _niet_beschikbaar(e, "regio-mbo: eerstejaars niet beschikbaar", onderdeel=_ONDERDEEL_EERSTEJAARS)
        instroom = _mbo_instroom(None, code_naam)
    return instroom, _mbo_eerstejaars(instroom, eigen)


def _mbo_kern(rows: pd.DataFrame) -> dict:
    """De ingeschrevenen van één mbo-instelling per jaar en per leerweg, op het regiodashboard (#899, #902)."""
    result: dict = {}
    result["ingeschrevenen"], leeg = _reeks(rows, "JAAR", _MBO_LEERWEG_COLS)
    _met_onderdrukt(result, "ingeschrevenen", leeg)
    per_jaar = rows.groupby("JAAR")[_MBO_LEERWEG_COLS].sum(min_count=1).sort_index()
    laatste_jaar = max(result["ingeschrevenen"], default=int(per_jaar.index.max()))
    result["laatste_jaar"] = laatste_jaar
    result["leerwegen"] = {int(jaar): _mbo_leerwegen(row) for jaar, row in per_jaar.iterrows()}
    result["sectoren"] = _mbo_sectoren(per_jaar.loc[laatste_jaar])
    return result


def _load_dashboard_regio_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "regio-mbo: data laden mislukt", instelling)
        return None

    inst_col = "INSTELLINGSNAAM"
    code_col = "INSTELLINGSCODE"
    rows = df_mbo[df_mbo[inst_col].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    ctx = _build_regio_context(instelling, "mbo")
    provincie = ctx.provincie if ctx else _mode_str(rows["PROVINCIE INSTELLING"])
    self_code = str(rows[code_col].iloc[0])
    self_amr = get_adres_lookup().get(self_code, {}).get("arbeidsmarktregio")

    result: dict = {
        "type": "mbo",
        "provincie": provincie or "Onbekend",
        "arbeidsmarktregio": self_amr,
    }

    result.update(_mbo_kern(rows))

    per_hoofdgroep, leeg = _mbo_ingeschrevenen_per_hoofdgroep(instelling)
    if per_hoofdgroep:
        result["ingeschrevenen_per_hoofdgroep"] = per_hoofdgroep
        result["ingeschrevenen_per_hoofdgroep_jaar"] = _INSTROMENDE_MBO_HOOFDGROEP_JAAR  # niet in het bestand (#934)
        _met_onderdrukt(result, "ingeschrevenen_per_hoofdgroep", leeg)

    df_dipl_mbo, (dipl, leeg_dipl) = _mbo_load_gediplomeerden(inst_col, instelling)
    if dipl:
        result["gediplomeerden"] = dipl
        _met_onderdrukt(result, "gediplomeerden", leeg_dipl)

    code_naam = _mbo_code_naam(df_mbo)
    eigen = str(rows[inst_col].iloc[0])
    instroom, (eerstejaars, leeg_ej) = _mbo_load_eerstejaars(code_naam, eigen)
    if eerstejaars:
        result["eerstejaars"] = eerstejaars
        _met_onderdrukt(result, "eerstejaars", leeg_ej)

    if ctx:
        result["benchmark"] = _mbo_regio_benchmark(ctx, df_mbo, instroom, df_dipl_mbo, code_naam, eigen)
        result["kaart_figure_json"] = _build_kaart_figure(ctx, instelling)

    result["arbeidsmarkt_roa"] = _roa_schoolverlaters("mbo")
    result["arbeidsmarkt_prognose"] = _roa_prognose("mbo")
    result["vacatureaanbod"] = _uwv_vacatures_provincie(provincie) if provincie else {}
    return result


def _beschikbare_instellingen(instelling: str, df_ho: pd.DataFrame, df_mbo: pd.DataFrame) -> list[str]:
    """De suggesties bij een onbekende instelling: de ho- en mbo-namen die er het dichtst bij liggen, hooguit
    _MAX_SUGGESTIONS, hoofdletterongevoelig. Met difflib, zoals de bronpakketten bij een onbekende waarde; eerder
    waren het de eerste namen van het alfabet (#901)."""
    namen = {
        str(n).lower(): str(n)
        for n in (*df_ho["INSTELLINGSNAAM_ACTUEEL"].dropna(), *df_mbo["INSTELLINGSNAAM"].dropna())
    }
    dichtst = difflib.get_close_matches(instelling.lower(), list(namen), n=_MAX_SUGGESTIONS, cutoff=0.5)
    return [namen[n] for n in dichtst]


@_dashboardlading
def load_dashboard_regio(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    ho = _poging(_load_dashboard_regio_ho, instelling)
    if ho:
        result["gevonden"] = True
        result.update(ho)
        return result

    mbo = _load_dashboard_regio_mbo(instelling)
    if mbo:
        result["gevonden"] = True
        result.update(mbo)
        return result

    try:
        df_ho = _load_ho_ingeschrevenen()
        result["beschikbare_instellingen"] = _beschikbare_instellingen(instelling, df_ho, _load_mbo_studenten())
        if not result["beschikbare_instellingen"]:
            result["geen_suggesties"] = _GEEN_SUGGESTIES
    except Exception as e:
        _niet_beschikbaar(e, "load_dashboard_regio: beschikbare instellingen niet laden")

    return result


# ─── Nationaal Marktaandeel ───────────────────────────────────────────────────


# Landelijke cijfers (#903). Het landelijke dashboard rangschikt instellingen en rekent aandelen per sector, dus het
# telt het DUO-bestand per instelling op. De chat geeft een landelijk aantal uit een vaste CBS-maat (tools/maten.py,
# #805): een andere telling. Het dashboard neemt die maat niet over (CBS kent geen instellingen en niet dezelfde
# sectoren), maar zegt welke som het is en welke maat de chat gebruikt; tests/test_dashboard_cijfers.py legt de namen
# vast tegen tools/maten.py.
_LANDELIJK = {
    "ho": {"dataset": "p01hoinges", "chat_maat": "deelnemers_ho_landelijk", "chat_dataset": "85423NED"},
    "mbo": {
        "dataset": "mbo-studenten-per-instelling",
        "chat_maat": "mbo_studenten_landelijk",
        "chat_dataset": "85354NED",
    },
}


def _landelijk_definitie(sector: str) -> dict[str, str]:
    """Wat "landelijk" in dit dashboard telt, en waarom de chat een ander getal kan geven."""
    bron = _LANDELIJK[sector]
    return {
        "maat": "duo_som_per_instelling",
        **bron,
        "definitie": (
            f"de som van DUO {bron['dataset']} over alle instellingen; onderdrukte cellen tellen niet mee, dus een "
            "totaal kan een ondergrens zijn"
        ),
        "verschil_met_chat": (
            f"De chat geeft het landelijke aantal uit de CBS-tabel {bron['chat_dataset']}. "
            "Dat is een andere telling: het kan van deze som afwijken."
        ),
    }


def _nationaal_cijfers(
    df: pd.DataFrame, eigen: pd.DataFrame, kol: dict[str, str], laatste_jaar: int, typen: Callable[[str], str]
) -> dict:
    """Landelijke sectortotalen, eigen sectoren, ranking en positie per sector: één berekening voor ho en mbo.

    `kol` noemt de kolommen: instelling, sector, jaar en waarde. Een som over lege cellen is een ondergrens en staat in
    `onderdrukt`; een positie waarin een onderdrukte cel meetelt, staat er ook in, want die kan verschuiven (#902).
    Een sector waarin de instelling in het laatste jaar geen waarde heeft, krijgt geen positie en staat in
    `positie_weggelaten`.
    """
    inst_col, sector_col, jaar_col, waarde_col = kol["instelling"], kol["sector"], kol["jaar"], kol["waarde"]
    uit: dict = {}
    for sleutel, bron in (("sectoren_landelijk", df), ("eigen_sectoren", eigen)):
        uit[sleutel], leeg = _genest(bron, sector_col, jaar_col, waarde_col)
        _met_onderdrukt(uit, sleutel, leeg)

    laatste = df[df[jaar_col] == laatste_jaar]
    per_inst = _som(laatste, inst_col, waarde_col).dropna().sort_values(ascending=False, kind="stable")
    leeg_inst = _leeg(laatste, inst_col, waarde_col)
    uit["alle_instellingen"] = [
        {"naam": str(naam), "ingeschrevenen": int(aant), "type": typen(str(naam))}
        | ({"onderdrukt": int(leeg_inst[naam])} if leeg_inst.get(naam) else {})
        for naam, aant in per_inst.items()
    ]

    eigen_naam = eigen[inst_col].iloc[0]
    positie: dict[str, int] = {}
    onzeker: dict[str, int] = {}
    weggelaten: list[str] = []
    for sector in eigen[sector_col].drop_duplicates():  # ook een sector met alleen lege cellen
        in_sector = laatste[laatste[sector_col] == sector]
        sommen = _som(in_sector, inst_col, waarde_col).dropna()
        eigen_waarde = sommen.get(eigen_naam)
        if eigen_waarde is None or eigen_waarde <= 0:
            weggelaten.append(str(sector))
            continue
        positie[sector] = 1 + int((sommen > eigen_waarde).sum())
        if n := int(_leeg(in_sector, inst_col, waarde_col).sum()):
            onzeker[sector] = n
    uit["eigen_positie"] = positie
    uit["positie_weggelaten"] = weggelaten
    _met_onderdrukt(uit, "eigen_positie", onzeker)
    return uit


def _nationaal_ho(instelling: str, result: dict) -> dict | None:
    try:
        df_inges = _load_ho_ingeschrevenen()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "nationaal-ho: ranking niet beschikbaar", instelling)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    hu = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu.empty:
        return None

    result["gevonden"] = True
    result["type"] = "ho"
    laatste_jaar = int(hu["STUDIEJAAR"].max())
    result["laatste_jaar"] = laatste_jaar
    result["landelijk"] = _landelijk_definitie("ho")

    naam_to_type = {i["naam"].lower(): i["type"] for i in get_all_instellingen()}
    kol = {"instelling": inst_col, "sector": "ONDERDEEL", "jaar": "STUDIEJAAR", "waarde": "AANTAL_INGESCHREVENEN"}
    result.update(
        _nationaal_cijfers(df_inges, hu, kol, laatste_jaar, lambda naam: naam_to_type.get(naam.lower(), "ho"))
    )
    return result


def _mbo_per_leerweg(df: pd.DataFrame) -> pd.DataFrame:
    """mbo-studenten-per-instelling met de leerwegen als rijen (LEERWEG, AANTAL), zoals de ONDERDEEL-rijen van het ho."""
    return df.melt(
        id_vars=["JAAR", "INSTELLINGSNAAM"], value_vars=_MBO_LEERWEG_COLS, var_name="LEERWEG", value_name="AANTAL"
    )


def _nationaal_mbo(instelling: str, result: dict) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "nationaal-mbo: ranking niet beschikbaar", instelling)
        return None

    inst_col_mbo = "INSTELLINGSNAAM"
    rows = df_mbo[df_mbo[inst_col_mbo].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result["gevonden"] = True
    result["type"] = "mbo"
    laatste_jaar = int(df_mbo["JAAR"].max())
    result["laatste_jaar"] = laatste_jaar
    result["landelijk"] = _landelijk_definitie("mbo")

    kol = {"instelling": inst_col_mbo, "sector": "LEERWEG", "jaar": "JAAR", "waarde": "AANTAL"}
    result.update(
        _nationaal_cijfers(_mbo_per_leerweg(df_mbo), _mbo_per_leerweg(rows), kol, laatste_jaar, lambda _: "mbo")
    )
    return result


@_dashboardlading
def load_dashboard_nationaal(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}
    return _poging(_nationaal_ho, instelling, result) or _nationaal_mbo(instelling, result) or result


# ─── Rendementsmonitor ────────────────────────────────────────────────────────


def _pseudo_cohorten(instroom: dict[int, int], dipl: dict[int, int]) -> list[dict]:
    """Per instroomjaar de gediplomeerden 3, 4 en 5 jaar later; None als dat diplomajaar er (nog) niet is, geen 0 (#902)."""
    return [
        {
            "instroom_jaar": int(jaar),
            "instroom": instroom[jaar],
            "gediplomeerden_t3": dipl.get(jaar + 3),
            "gediplomeerden_t4": dipl.get(jaar + 4),
            "gediplomeerden_t5": dipl.get(jaar + 5),
        }
        for jaar in sorted(instroom)
    ]


def _rendement_per_jaar(cohorten: list[dict]) -> dict[int, float]:
    # Ratio > 1 indicates total-diplomas-per-year vs eerstejaars mismatch (common at WO
    # with many masters graduates); skip those cohorts as the value is not meaningful.
    return {
        c["instroom_jaar"]: round(c["gediplomeerden_t3"] / c["instroom"], 4)
        for c in cohorten
        if c["instroom"] > 0 and c["gediplomeerden_t3"] is not None and 0 < c["gediplomeerden_t3"] <= c["instroom"]
    }


def _benchmark_from_peer_rendements(peer_lists: list[dict[int, float]]) -> dict[int, float]:
    if not peer_lists:
        return {}
    all_jaren: set[int] = set().union(*[set(r.keys()) for r in peer_lists])
    bm: dict[int, float] = {}
    for jaar in sorted(all_jaren):
        vals = [r[jaar] for r in peer_lists if jaar in r]
        if vals:
            bm[jaar] = round(sum(vals) / len(vals), 4)
    return bm


def _mbo_dipl_reeks(df_dipl: pd.DataFrame, filter_col: str, filter_val: str) -> _Reeks:
    """({diplomajaar: gediplomeerden}, {jaar: lege cellen}) voor de rijen met filter_col == filter_val."""
    rows = df_dipl[df_dipl[filter_col].str.lower() == filter_val.lower()]
    if rows.empty:
        return {}, {}
    return _reeks(_mbo_dipl_lang(rows), "JAAR", "AANTAL")


def _mbo_dipl_per_jaar(df_dipl: pd.DataFrame, filter_col: str, filter_val: str) -> dict[int, int]:
    return _mbo_dipl_reeks(df_dipl, filter_col, filter_val)[0]


@_dashboardlading
def load_dashboard_rendement(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    ho_result = _poging(_rendement_ho, instelling)
    if ho_result:
        return ho_result

    mbo_result = _rendement_mbo(instelling)
    if mbo_result:
        return mbo_result

    return result


def _sector_rendement_ho(
    df_inges: pd.DataFrame, df_dipl: pd.DataFrame, inst_col: str, instelling: str
) -> dict[str, float]:
    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    if hu_dipl.empty or "ONDERDEEL" not in hu_dipl.columns:
        return {}
    hu_inges = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    out: dict[str, float] = {}
    for onderdeel in hu_inges["ONDERDEEL"].unique():
        d = int(hu_dipl[hu_dipl["ONDERDEEL"] == onderdeel]["AANTAL_GEDIPLOMEERDEN"].sum())
        i = int(hu_inges[hu_inges["ONDERDEEL"] == onderdeel]["AANTAL_INGESCHREVENEN"].sum())
        if i > 0 and d > 0:
            out[onderdeel] = round(d / i, 4)
    return out


def _ho_peer_rendement(df_ej: pd.DataFrame, df_dipl: pd.DataFrame, code_col: str, code: str) -> dict[int, float]:
    p_ej = df_ej[df_ej[code_col] == code]
    if p_ej.empty:
        return {}
    p_dipl = df_dipl[df_dipl[code_col] == code]
    p_instroom = p_ej.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
    p_dipl_series = (
        p_dipl.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum() if not p_dipl.empty else pd.Series(dtype=int)
    )
    rend: dict[int, float] = {}
    for jaar in p_instroom.index:
        iv = int(p_instroom[jaar])
        dt3 = int(p_dipl_series.get(jaar + 3, 0))
        if iv > 0 and dt3 > 0:
            rend[int(jaar)] = round(dt3 / iv, 4)
    return rend


def _rendement_ho(instelling: str) -> dict | None:
    try:
        df_inges, df_ej, df_dipl = _load_ho_full()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "rendement-ho: niet beschikbaar", instelling)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    code_col = "INSTELLINGSCODE_ACTUEEL"
    hu_ej = df_ej[df_ej[inst_col].str.lower() == instelling.lower()]
    if hu_ej.empty:
        return None

    result: dict = {"instelling": instelling, "gevonden": True, "type": "ho"}
    result["laatste_jaar"] = int(df_ej["STUDIEJAAR"].max())

    instroom, _ = _reeks(hu_ej, "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN")
    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    dipl, _ = _reeks(hu_dipl, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN")

    cohorten = _pseudo_cohorten(instroom, dipl)
    result["pseudo_cohorten"] = cohorten
    result["rendement_per_jaar"] = _rendement_per_jaar(cohorten)

    result["sector_rendement"] = _sector_rendement_ho(df_inges, df_dipl, inst_col, instelling)

    # benchmark & peers
    ctx = _build_regio_context(instelling, "ho")
    peers_rendement: dict[str, dict[int, float]] = {}
    peer_rend_lists: list[dict[int, float]] = []
    if ctx:
        for code in ctx.peer_codes:
            rend = _ho_peer_rendement(df_ej, df_dipl, code_col, code)
            if rend:
                naam = df_ej[df_ej[code_col] == code][inst_col].iloc[0]
                peers_rendement[naam] = rend
                peer_rend_lists.append(rend)

    result["benchmark_rendement"] = _benchmark_from_peer_rendements(peer_rend_lists)
    result["peers_rendement"] = peers_rendement
    return result


def _mbo_peer_rendement(instroom: dict[int, int], dipl: dict[int, int]) -> dict[int, float]:
    """{instroomjaar: gediplomeerden drie jaar later / eerstejaars} van één peer."""
    return {
        jaar: round(dipl[jaar + 3] / iv, 4) for jaar, iv in instroom.items() if iv > 0 and dipl.get(jaar + 3, 0) > 0
    }


def _mbo_peers_rendement(ctx, df_dipl_mbo, code_naam: dict[str, str], eigen: str) -> dict[str, dict[int, float]]:
    """Het rendement per peer, op naam en over al zijn codes (#923)."""
    if not ctx:
        return {}
    try:
        instroom = _mbo_instroom(_load_instromende_mbo_historisch(), code_naam)
    except Exception as e:
        _niet_beschikbaar(e, "rendement-mbo: peer rendement niet beschikbaar", onderdeel=_ONDERDEEL_RENDEMENT_REGIO)
        return {}
    dipl = _mbo_per_instelling(df_dipl_mbo, code_naam) if df_dipl_mbo is not None else None
    peers_rendement: dict[str, dict[int, float]] = {}
    for naam in sorted(_mbo_peernamen(ctx, code_naam, eigen)):
        p_instroom, _ = _mbo_eerstejaars(instroom, naam)
        p_dipl = _mbo_dipl_per_jaar(dipl, _INSTELLING, naam) if dipl is not None else {}
        if rend := _mbo_peer_rendement(p_instroom, p_dipl):
            peers_rendement[naam] = rend
    return peers_rendement


def _rendement_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
        df_dipl_mbo = _load_mbo_gediplomeerden()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "rendement-mbo: niet beschikbaar", instelling)
        return None

    inst_col = "INSTELLINGSNAAM"
    rows = df_mbo[df_mbo[inst_col].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result: dict = {"instelling": instelling, "gevonden": True, "type": "mbo"}
    result["laatste_jaar"] = int(rows["JAAR"].max())
    code_naam = _mbo_code_naam(df_mbo)
    eigen = str(rows[inst_col].iloc[0])

    # instroom, over alle codes van de instelling (#923)
    instroom_per_jaar: dict[int, int] = {}
    try:
        instroom_per_jaar, _ = _mbo_eerstejaars(_mbo_instroom(_load_instromende_mbo_historisch(), code_naam), eigen)
    except Exception as e:
        _niet_beschikbaar(e, "rendement-mbo: instroom per jaar niet beschikbaar", onderdeel=_ONDERDEEL_INSTROOM)

    dipl_per_jaar = _mbo_dipl_per_jaar(df_dipl_mbo, inst_col, instelling) if df_dipl_mbo is not None else {}

    cohorten = _pseudo_cohorten(instroom_per_jaar, dipl_per_jaar)
    result["pseudo_cohorten"] = cohorten
    result["rendement_per_jaar"] = _rendement_per_jaar(cohorten)
    result["sector_rendement"] = {}

    # benchmark & peers
    ctx = _build_regio_context(instelling, "mbo")
    peers_rendement = _mbo_peers_rendement(ctx, df_dipl_mbo, code_naam, eigen)
    result["benchmark_rendement"] = _benchmark_from_peer_rendements(list(peers_rendement.values()))
    result["peers_rendement"] = peers_rendement
    return result


# ─── Arbeidsmarktmatch ────────────────────────────────────────────────────────


def _arbeidsmarktmatch_ho(instelling: str) -> dict | None:
    try:
        df_inges, df_dipl = _load_ho_ingeschrevenen(), _load_ho_gediplomeerden()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "arbeidsmarktmatch-ho: niet beschikbaar", instelling)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    hu = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu.empty:
        return None

    ctx = _build_regio_context(instelling, "ho")
    self_code = str(hu["INSTELLINGSCODE_ACTUEEL"].iloc[0])
    provincie = ctx.provincie if ctx else _mode_str(hu["PROVINCIENAAM"])

    gps: dict[str, int] = {}
    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    if not hu_dipl.empty and "ONDERDEEL" in hu_dipl.columns:
        gps = _gemiddeld_per_sector(hu_dipl, "DIPLOMAJAAR", "ONDERDEEL", "AANTAL_GEDIPLOMEERDEN")

    return {
        "type": "ho",
        "provincie": provincie or "Onbekend",
        "arbeidsmarktregio": get_adres_lookup().get(self_code, {}).get("arbeidsmarktregio"),
        "laatste_jaar": int(hu["STUDIEJAAR"].max()),
        "gediplomeerden_per_sector": gps,
    }


def _arbeidsmarktmatch_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception as e:
        _hoofdbron_niet_beschikbaar(e, "arbeidsmarktmatch-mbo: niet beschikbaar", instelling)
        return None

    rows = df_mbo[df_mbo["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    ctx = _build_regio_context(instelling, "mbo")
    self_code = str(rows["INSTELLINGSCODE"].iloc[0])
    provincie = ctx.provincie if ctx else _mode_str(rows["PROVINCIE INSTELLING"])

    # De aanbodzijde: gediplomeerden per hoofdgroep, gemiddeld over 3 jaar zoals bij het ho. Eerder stond hier TOTAAL
    # MBO uit instromende-mbo-studenten: ingeschrevenen, geen gediplomeerden (#899).
    gps: dict[str, int] = {}
    try:
        df_dipl = _load_mbo_gediplomeerden()
        dipl = df_dipl[df_dipl["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
        if not dipl.empty:
            gps = _gemiddeld_per_sector(_mbo_dipl_lang(dipl), "JAAR", _HOOFDGROEP, "AANTAL")
    except Exception as e:
        _niet_beschikbaar(
            e,
            "arbeidsmarktmatch-mbo: gediplomeerden per hoofdgroep niet beschikbaar",
            onderdeel=_ONDERDEEL_GEDIPLOMEERDEN,
        )

    return {
        "type": "mbo",
        "provincie": provincie or "Onbekend",
        "arbeidsmarktregio": get_adres_lookup().get(self_code, {}).get("arbeidsmarktregio"),
        "laatste_jaar": int(rows["JAAR"].max()),
        "gediplomeerden_per_sector": gps,
    }


@_dashboardlading
def load_dashboard_arbeidsmarktmatch(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    detect = _poging(_arbeidsmarktmatch_ho, instelling) or _arbeidsmarktmatch_mbo(instelling)
    if not detect:
        return result

    result["gevonden"] = True
    result.update(detect)
    onderwijs_type = detect["type"]
    provincie = detect["provincie"]
    sectoren_tuple = tuple(sorted(detect["gediplomeerden_per_sector"].keys()))

    # vacatures_per_cluster: alle matching clusters zonder cap, ongewogen
    result["vacatures_per_cluster"] = _uwv_clusters_voor_sectoren(provincie, sectoren_tuple) if provincie else {}
    # vacatures_per_sector: gedeelde clusters naar rato, zoals de chat (#455)
    result["vacatures_per_sector"] = _uwv_vacatures_per_sector(provincie, sectoren_tuple) if provincie else {}

    # roa_per_niveau
    roa_raw = _roa_schoolverlaters(onderwijs_type)
    result["roa_per_niveau"] = {
        niveau: {
            "werkloosheid": data.get("werkloosheid"),
            "vast_dienstverband": data.get("vast dienstverband"),
            "buiten_vakrichting": data.get("buiten de vakrichting"),
        }
        for niveau, data in roa_raw.items()
    }

    # sector_cluster_mapping
    gps_final = result.get("gediplomeerden_per_sector", {})
    result["sector_cluster_mapping"] = {s: arbeidsmarkt.SECTOR_CLUSTER_MAP.get(s, []) for s in gps_final}

    result["match_score"] = _match_scores(gps_final, result["vacatures_per_sector"], result["sector_cluster_mapping"])
    return result


def _match_label(dipl_aandeel: float, vac_aandeel: float) -> str:
    if vac_aandeel > dipl_aandeel * _MATCH_DREMPEL:
        return "schaarste"
    if dipl_aandeel > vac_aandeel * _MATCH_DREMPEL:
        return "overaanbod"
    return "evenwicht"


def _match_scores(
    gps: dict[str, int], vacatures_per_sector: dict[str, int], scm: dict[str, list[str]]
) -> dict[str, str | None]:
    """Per sector het diploma-aandeel tegenover het vacature-aandeel.

    De vacatures per sector zijn gewogen (#455), dus hun som is het totaal en tellen beide aandelen
    op tot 1. Een sector zonder clusters in de mapping krijgt None, net als elke sector zonder vacatures.
    """
    totaal_dipl = sum(gps.values())
    totaal_vac = sum(vacatures_per_sector.values())
    if not totaal_dipl or not totaal_vac:
        return dict.fromkeys(gps)
    return {
        sector: _match_label(n / totaal_dipl, vacatures_per_sector.get(sector, 0) / totaal_vac)
        if scm.get(sector)
        else None
        for sector, n in gps.items()
    }
