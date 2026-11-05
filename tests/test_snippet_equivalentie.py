"""Equivalentie per tool (#945): de snippet roept de bronlader aan met dezelfde argumenten als de app.

Een snippet hoort te reproduceren wat de app laadde. Bij DUO schreef hij het ruwe argument van het model over
(`duo.load("p04hogdipl", "4")`) terwijl de app index 4 laadde (#944); zo'n verschil zie je alleen als je de app en de
snippet naast elkaar aan het werk zet. Dat doet deze test, voor elke tool die een snippet maakt:

1. De echte laders van `onderwijsbronnen` (`duo.load`, `cbs.data`, `rio.fetch`, `uwv.load`, `roa.load`) zijn vervangen
   door een opnemer, overal waar de app of een snippet ze vandaan haalt. Hij noteert elke aanroep, met de argumenten
   gebonden aan de signatuur van de echte lader (positioneel of met naam maakt niet uit, tekst of getal wel), en geeft
   bevroren data terug: de fixtures van de gouden tests, zonder netwerk. Een DUO-resource kiest hij zoals het pakket
   (`duo.resource_schema`: index, ID, exacte naam, uniek naamdeel): `"4"` is daar een naam, geen index.
2. De app-tool draait via `tools.dispatch` met de ruwe argumenten van het model: tekst en getal, spellingvarianten van
   een ID, naam en index, een data_key in een andere spelling.
3. `snippet.generate` maakt de snippet zoals agent/loop.py, met de recepten zoals de sessie ze onthoudt
   (agent/session_data.py), en de snippet draait in een schone namespace.
4. De aanroepen van de snippet zijn precies die van de app (als multiset), en de snippet draait zonder fout.

Twee verschillen zijn bedoeld en staan hieronder met naam:
- `$top` bij CBS: de app vraagt hoogstens CBS_ROW_LIMIT rijen, de snippet de hele selectie (hij zegt bovenaan als de app
  afkapte, `_bewerkingsregels`).
- hulpbestanden (`_HULP`): de verrijking van een mbo-bestand met provincie en arbeidsmarktregio. De app haalt die uit
  het instellingenregister en de gebiedsindeling die ze voor alles gebruikt; de snippet laadt het mbo-adressenbestand en
  de CBS-indeling zelf.

Dekking: elke tool van de app (`tools._HANDLERS`) heeft hier een equivalentiegeval, een eigen equivalentietest in
`_EIGEN_TEST` (een bron met een eigen lader buiten deze vijf), of staat in `_ZONDER_LAADSTAP` met de reden. Een nieuwe tool zonder één van beide, of een nieuwe snippetgenerator of laadregel in tools/snippet.py zonder
geval, maakt `test_elke_tool_heeft_een_equivalentiegeval_of_een_reden` rood.
"""

from __future__ import annotations

import functools
import inspect
import io
import json
import sys
import urllib.request
from collections import Counter
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import pytest
from onderwijsbronnen import duo as ob_duo
from onderwijsbronnen import roa as ob_roa
from onderwijsbronnen import uwv as ob_uwv
from onderwijsbronnen.cbs import client as cbs_client
from onderwijsbronnen.rio import client as rio_client

import tools
from core.config import CBS_ROW_LIMIT
from data import arbeidsmarkt, arbeidsmarktregio
from tests import gouden
from tests.cbs_feed import maak_feed
from tools import duo_meta, herlaad, maten, plot, snippet, store
from tools.schemas import (
    TOOL_COMPUTE_KPI,
    TOOL_CREATE_CHOROPLETH_MAP,
    TOOL_CREATE_PLOT,
    TOOL_DATASET_COUNTS,
    TOOL_DATASET_DETAILS,
    TOOL_DATASET_PROFIEL,
    TOOL_GET_ACCREDITATIE,
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_CBS_DATA,
    TOOL_GET_CBS_DIMENSION,
    TOOL_GET_COLLEGEGELD,
    TOOL_GET_DUO_DATA,
    TOOL_GET_INSPECTIEOORDEEL,
    TOOL_GET_INSPECTIEOORDEEL_VO,
    TOOL_GET_MAAT,
    TOOL_GET_MBO_INDICATOREN,
    TOOL_GET_RIO_DATA,
    TOOL_GET_RIO_INSTELLING,
    TOOL_GET_ROA_BENCHMARK,
    TOOL_GET_UWV_VACATURES,
    TOOL_GET_WO_PERSONEEL,
    TOOL_QUERY_DATA,
    TOOL_RELATIE,
    TOOL_RUN_ANALYSIS,
    TOOL_SEARCH_CATALOG,
)

# Tools die hun equivalentie in een eigen testbestand bewaken: tool → pad vanaf de repo-root. Voor een bron met een
# eigen lader (bijvoorbeeld `onderwijsbronnen.unl`, #936); dat bestand voert de snippet uit en vergelijkt met de tool.
_EIGEN_TEST: dict[str, str] = {
    TOOL_GET_WO_PERSONEEL: "tests/test_wo_personeel.py",
    # DUO's verantwoording uit XBRL (#935): test_de_snippet_rekent_met_dezelfde_pakketfunctie_als_de_tool.
    TOOL_GET_BESTUURSFINANCIEN: "tests/test_financien.py",
}

# Tools van de app zonder eigen laadstap in een snippet, met de reden. Een tool hier maakt geen snippet
# (`snippet._GENERATORS`) en zet geen key met een laadaanroep (`KeyMeta.laad`) in de store; een snippet op zijn key zegt
# eerlijk dat er geen laadstap bekend is (`snippet._laadregels`).
_ZONDER_LAADSTAP = {
    TOOL_SEARCH_CATALOG: "doorzoekt de catalogus, laadt geen data",
    TOOL_DATASET_DETAILS: "metadata uit de catalogus, laadt geen data",
    TOOL_DATASET_COUNTS: "telt de catalogus, laadt geen data",
    TOOL_DATASET_PROFIEL: "profileert een geladen key, laadt zelf niets",
    TOOL_GET_CBS_DIMENSION: "codes van een CBS-dimensie, geen tabel",
    TOOL_RELATIE: "relaties tussen geladen keys, laadt zelf niets",
    TOOL_GET_RIO_INSTELLING: "één instelling uit RIO, zonder laadaanroep in de store",
    TOOL_GET_INSPECTIEOORDEEL: "Inspectiebestand, zonder laadaanroep in de store",
    TOOL_GET_INSPECTIEOORDEEL_VO: "Inspectiebestand vo, zonder laadaanroep in de store",
    TOOL_GET_MBO_INDICATOREN: "mbo-indicatorenbestand, zonder laadaanroep in de store",
    TOOL_GET_ACCREDITATIE: "accreditatie uit DUO/NVAO, zonder laadaanroep in de store",
    TOOL_GET_COLLEGEGELD: "collegegeld uit DUO, zonder laadaanroep in de store",
}

# De bronladers: (bron, de echte functie). De opnemer vervangt elke verwijzing ernaar.
_LADERS: dict[str, Callable] = {
    "duo": ob_duo.load,
    "cbs": cbs_client.data,
    "rio": rio_client.fetch,
    "uwv": ob_uwv.load,
    "roa": ob_roa.load,
}
# Waar een snippet zijn lader vandaan haalt (`from onderwijsbronnen import duo`, `from onderwijsbronnen.cbs import
# data`): op het pakket, ook als dat attribuut al naar iets anders wees (zie onderwijsbronnen/cbs/__init__.py).
_SNIPPETPADEN = {
    "duo": ("onderwijsbronnen.duo", "load"),
    "cbs": ("onderwijsbronnen.cbs", "data"),
    "rio": ("onderwijsbronnen.rio", "fetch"),
    "uwv": ("onderwijsbronnen.uwv", "load"),
    "roa": ("onderwijsbronnen.roa", "load"),
}

# Hulpbestanden: (bron, eerste argument). Zie de moduledocstring.
_HULP = {
    ("duo", "adressen_mbo"),
    ("duo", "adressen_ho"),
    ("cbs", arbeidsmarktregio.bron()["tabel"]),
}


@dataclass(frozen=True)
class Aanroep:
    bron: str
    argumenten: str  # JSON met gesorteerde sleutels: 4 en "4" blijven verschillend

    @property
    def eerste(self) -> Any:
        return next(iter(json.loads(self.argumenten).values()), None)

    def __str__(self) -> str:
        return f"{self.bron}.{json.loads(self.argumenten)}"


def _aanroep(bron: str, args: tuple, kwargs: dict) -> Aanroep:
    """De aanroep zoals de echte lader hem ziet: gebonden aan zijn signatuur, met de standaardwaarden ingevuld."""
    signatuur = inspect.signature(_LADERS[bron])
    gebonden = signatuur.bind(*args, **kwargs)
    gebonden.apply_defaults()
    argumenten: dict = {}
    for naam, waarde in gebonden.arguments.items():
        if signatuur.parameters[naam].kind is inspect.Parameter.VAR_KEYWORD:
            argumenten.update(waarde)
        else:
            argumenten[naam] = waarde
    if bron == "cbs" and argumenten.get("$top") == CBS_ROW_LIMIT:
        del argumenten["$top"]  # de paginagrens van de app, zie de moduledocstring
    return Aanroep(bron, json.dumps(argumenten, sort_keys=True, ensure_ascii=False, default=repr))


@dataclass
class Opnemer:
    """Noteert de aanroepen van de laders; `aan` staat uit terwijl de opzet het register opbouwt."""

    aanroepen: list[Aanroep] = field(default_factory=list)
    aan: bool = True

    def neem_op(self, bron: str, data: Callable) -> Callable:
        def lader(*args, **kwargs):
            if self.aan:
                self.aanroepen.append(_aanroep(bron, args, kwargs))
            return data(*args, **kwargs)

        return lader

    def wis(self) -> list[Aanroep]:
        aanroepen, self.aanroepen = self.aanroepen, []
        return aanroepen


def _vervang_overal(monkeypatch, echt: Callable, nep: Callable) -> None:
    """Elke module-attribuut dat naar de echte lader wijst (`from onderwijsbronnen.rio import fetch` in tools/rio.py)."""
    for module in list(sys.modules.values()):
        naam = getattr(module, "__name__", "") or ""
        if not naam.startswith(("onderwijsbronnen", "tools", "data", "agent", "core", "routes")):
            continue
        for attribuut, waarde in list(vars(module).items()):
            if waarde is echt:
                monkeypatch.setattr(module, attribuut, nep)


# --- de bevroren bronnen achter de opnemer ---


def _duo_bestanden(dataset_id: str) -> list[dict]:
    """De bestanden van een DUO-dataset uit de catalogus van de app, zoals `duo.resources` ze live geeft."""
    return list(duo_meta.record(dataset_id).get("_resources") or [])


def _duo_index(bestanden: list[dict], dataset_id: str, resource: int | str) -> int:
    """Het bestand dat `duo.load` kiest, met de publieke resolutie van het pakket (dezelfde regel als in `load`)."""
    if isinstance(resource, int):
        if not 0 <= resource < len(bestanden):
            raise IndexError(f"Dataset '{dataset_id}' heeft geen resource {resource}.")
        return resource
    resource_id = ob_duo.resource_schema(dataset_id, resource)["resource_id"]
    return next(i for i, bestand in enumerate(bestanden) if bestand.get("id") == resource_id)


def _duo_data(fixturelader: Callable) -> Callable:
    """`duo.load` zoals het pakket kiest (index, ID, exacte naam, uniek naamdeel), met de data van de fixtures."""

    def load(dataset_id: str, resource: int | str = 0, skiprows=None, **kwargs) -> pd.DataFrame:
        bestanden = _duo_bestanden(dataset_id)
        if not bestanden and isinstance(resource, int):
            return fixturelader(dataset_id, resource)  # een hulpbestand buiten de catalogus (adressen)
        if not bestanden:
            raise ValueError(f"Dataset '{dataset_id}' heeft geen downloadbare resources.")
        index = _duo_index(bestanden, dataset_id, resource)
        try:
            return fixturelader(dataset_id, index)
        except AssertionError:
            # Geen fixture van dit bestand: de vorm van een ander bestand van de dataset is genoeg om te laden.
            for andere in range(len(bestanden)):
                try:
                    return fixturelader(dataset_id, andere)
                except AssertionError:
                    continue
            raise

    return load


def _cbs_tabellen() -> dict[str, dict]:
    """Per CBS-tabel de definities, de metadata en de rijen: de gouden opnames, 85701NED en de gebiedsindeling."""
    tabellen = {}
    for dataset_id in gouden.g.CBS_AANROEPEN:
        opname = gouden.g.lees_json_gz(gouden.g.cbs_bestand(dataset_id))
        tabellen[dataset_id] = {"definitions": opname["definitions"], "get": opname["get"], "rijen": opname["rijen"]}
    entree = json.loads((gouden.g.ROOT / "tests" / "fixtures" / "cbs" / "85701NED_entree_2023.json").read_text())
    tabellen["85701NED"] = {"definitions": entree["definitions"], "get": {}, "rijen": entree["rows"]}
    indeling = arbeidsmarktregio.bron()
    tabellen[indeling["tabel"]] = {
        "definitions": {},
        "get": {},
        "rijen": [{"RegioS": f"GM{code}", indeling["kolom"]: r} for code, r in arbeidsmarktregio.gemeenten().items()],
    }
    return tabellen


def _cbs_data(feeds: dict[str, Callable]) -> Callable:
    """`cbs.data` zoals CBS antwoordt: de rijen bij de `$filter`, met alleen de kolommen van `$select`."""

    def data(dataset_id: str, **params) -> list[dict]:
        rijen = feeds[dataset_id](dataset_id, **params)
        if select := params.get("$select"):
            kolommen = {"ID", *(k.strip() for k in str(select).split(","))}
            rijen = [{k: v for k, v in rij.items() if k in kolommen} for rij in rijen]
        return rijen

    return data


def _rio_data(resource: str, **params) -> list[dict]:
    return [
        {"code": "100A352", "naam": "Graafschap College", "plaatsnaam": "Doetinchem"},
        {"code": "100A354", "naam": "Mondriaan", "plaatsnaam": "Den Haag"},
    ]


_PROVINCIES = {
    "PV20": "Groningen", "PV21": "Fryslân", "PV22": "Drenthe", "PV23": "Overijssel", "PV24": "Flevoland",
    "PV25": "Gelderland", "PV26": "Utrecht", "PV27": "Noord-Holland", "PV28": "Zuid-Holland", "PV29": "Zeeland",
    "PV30": "Noord-Brabant", "PV31": "Limburg",
}  # fmt: skip
_VORM = {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]}


def _urlopen(url, timeout=None):
    """De provinciekaart voor app en snippet (BytesIO is zelf een contextmanager)."""
    features = [
        {"type": "Feature", "id": code, "properties": {"statnaam": naam}, "geometry": _VORM}
        for code, naam in _PROVINCIES.items()
    ]
    return io.BytesIO(json.dumps({"type": "FeatureCollection", "features": features}).encode())


def _wis_arbeidsmarkt() -> None:
    for lader in (arbeidsmarkt._uwv, arbeidsmarkt._roa):
        if hasattr(lader, "cache_clear"):
            lader.cache_clear()


@pytest.fixture
def opnemer(duo_fixtures, monkeypatch) -> Generator[Opnemer, None, None]:
    """De opnemer op elke bronlader, met de bevroren data erachter; het instellingenregister staat al klaar."""
    import tools.cbs

    gouden._duo(monkeypatch)  # duo.load leest nu de DUO-fixtures van #766 en de gouden bestanden
    fixturelader = ob_duo.load
    tabellen = _cbs_tabellen()
    feeds = {dataset_id: maak_feed(tabel["rijen"]) for dataset_id, tabel in tabellen.items()}
    # Met cache_clear, zoals de echte: de actualiteitsklok van de CBS-metadata leegt hem (tools/cbs.py).
    definities = functools.cache(lambda dataset_id: tabellen[dataset_id]["definitions"])
    monkeypatch.setattr(tools.cbs, "definitions", definities)
    monkeypatch.setattr(
        tools.cbs, "get", lambda dataset_id, endpoint, **params: tabellen[dataset_id]["get"].get(endpoint, [])
    )
    monkeypatch.setattr(ob_duo, "resources", _duo_bestanden)
    uwv = pd.read_csv(gouden.g.MAP / gouden.g.UWV, dtype={"PEILDATUM": str})
    roa = pd.read_csv(gouden.g.MAP / gouden.g.ROA, dtype={"versie": str})
    data = {
        "duo": _duo_data(fixturelader),
        "cbs": _cbs_data(feeds),
        "rio": _rio_data,
        "uwv": lambda *a, **k: uwv.copy(),
        "roa": lambda *a, **k: roa.copy(),
    }
    nemer = Opnemer()
    for bron, echt in _LADERS.items():
        nep = nemer.neem_op(bron, data[bron])
        _vervang_overal(monkeypatch, echt, nep)
        _vervang_overal(monkeypatch, getattr(sys.modules[_SNIPPETPADEN[bron][0]], _SNIPPETPADEN[bron][1]), nep)
        monkeypatch.setattr(sys.modules[_SNIPPETPADEN[bron][0]], _SNIPPETPADEN[bron][1], nep)
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(plot, "_GEOJSON_CACHE", {})
    monkeypatch.setattr(go.Figure, "show", lambda self, *a, **k: None)
    _wis_arbeidsmarkt()
    # Het register (instellingsnamen voor get_maat) laadt DUO-bestanden; dat is geen laadstap van een antwoord.
    from data import instellingen

    nemer.aan = False
    instellingen.get_all()
    nemer.aan = True
    yield nemer
    _wis_arbeidsmarkt()


# --- de gevallen ---


@dataclass(frozen=True)
class Vorige:
    """De data_key van de vorige stap, eventueel in een andere spelling (zoals het model hem soms schrijft)."""

    vorm: Callable[[str], str] = str


@dataclass(frozen=True)
class Geval:
    naam: str
    stappen: tuple[tuple[str, dict], ...]
    # Vergelijk ook de kolommen van `df` in de snippet met de tabel van de app (alleen waar de app de bronkolommen houdt).
    kolommen: bool = False


def _p01_bestand(index: int) -> dict:
    return _duo_bestanden("p01hoinges")[index]


_DUO = (TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": 1})
_CBS_SELECTIE = {
    "dimensies": {"Geslacht": "T001038", "Onderwijssoort": "*", "Opleidingsfase": "*", "Opleidingsvorm": "T001228"},
    "periode": "*",
}
_RIO_MBO = {"type": "MBOOPLEIDINGSERKENNING"}
_PEILDAG = "2025-09-01"
_PER_JAAR = (
    TOOL_QUERY_DATA,
    {"data_key": Vorige(), "group_by": ["STUDIEJAAR"], "aggregate": {"AANTAL_INGESCHREVENEN": "sum"}},
)
_MBO = (TOOL_GET_DUO_DATA, {"dataset_id": "mbo-studenten-per-instelling", "resource": 0})
_MBO_PER_PROVINCIE = (
    TOOL_QUERY_DATA,
    {"data_key": Vorige(), "group_by": ["PROVINCIE INSTELLING"], "aggregate": {"BBL": "sum"}},
)

GEVALLEN = [
    # DUO: index, tekst-getal (#944), naam, naamdeel, resource-ID, geen resource, en spellingvarianten van de dataset.
    Geval("duo_index", (_DUO,), kolommen=True),
    Geval("duo_tekstgetal", ((TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": "4"}),), kolommen=True),
    Geval("duo_tekstgetal_spaties", ((TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": " 1 "}),)),
    Geval("duo_zonder_resource", ((TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges"}),)),
    Geval("duo_naam", ((TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": _p01_bestand(1)["naam"]}),)),
    Geval(
        "duo_naamdeel",
        (
            (
                TOOL_GET_DUO_DATA,
                {"dataset_id": "p01hoinges", "resource": "wetenschappelijk onderwijs inclusief geslacht"},
            ),
        ),
    ),
    Geval("duo_resource_id", ((TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": _p01_bestand(1)["id"]}),)),
    Geval("duo_bron_id", ((TOOL_GET_DUO_DATA, {"dataset_id": "duo:p01hoinges", "resource": 1}),)),
    Geval("duo_hoofdletters", ((TOOL_GET_DUO_DATA, {"dataset_id": "P01HOINGES", "resource": 1}),)),
    Geval("duo_mbo_met_provincie_en_regio", (_MBO,), kolommen=True),
    # CBS: een gesloten selectie, ID-spellingen, alleen onderwerpen ($select), de sector naast de selectie (#891),
    # bewaarde filters, en een tabel over meer onderwijssoorten (sectorselectie, CH-03).
    Geval("cbs_selectie", ((TOOL_GET_CBS_DATA, {"dataset_id": "85423NED", "selectie": _CBS_SELECTIE}),)),
    Geval("cbs_bron_id", ((TOOL_GET_CBS_DATA, {"dataset_id": "cbs:85423ned", "selectie": _CBS_SELECTIE}),)),
    Geval(
        "cbs_onderwerpen",
        (
            (
                TOOL_GET_CBS_DATA,
                {"dataset_id": "85423NED", "selectie": {**_CBS_SELECTIE, "onderwerpen": ["TotaalIngeschrevenen_1"]}},
            ),
        ),
    ),
    Geval(
        "cbs_sector_naast_selectie",
        ((TOOL_GET_CBS_DATA, {"dataset_id": "85423NED", "selectie": _CBS_SELECTIE, "sector": "hbo"}),),
    ),
    Geval(
        "cbs_filters",
        ((TOOL_GET_CBS_DATA, {"dataset_id": "85423NED", "filters": {"$filter": "trim(Geslacht) eq 'T001038'"}}),),
    ),
    Geval(
        "cbs_sectorselectie",
        (
            (
                TOOL_GET_CBS_DATA,
                {
                    "dataset_id": "85701NED",
                    "selectie": {
                        "dimensies": {"Geslacht": "*", "Onderwijssoort": "*", "Regiokenmerken": "*"},
                        "periode": ["2023/24"],
                    },
                },
            ),
        ),
    ),
    # RIO: de peildag die de app zet (#718), de bron-ID en een getal als filterwaarde.
    Geval("rio", ((TOOL_GET_RIO_DATA, {"resource": "opleidingserkenningen", "filters": _RIO_MBO}),), kolommen=True),
    Geval("rio_bron_id", ((TOOL_GET_RIO_DATA, {"resource": "rio:opleidingserkenningen", "filters": _RIO_MBO}),)),
    Geval(
        "rio_eigen_peildag",
        (
            (
                TOOL_GET_RIO_DATA,
                {"resource": "opleidingserkenningen", "filters": {**_RIO_MBO, "datumGeldigOp": _PEILDAG}},
            ),
        ),
    ),
    Geval(
        "rio_getal_als_filter",
        (
            (
                TOOL_GET_RIO_DATA,
                {
                    "resource": "opleidingserkenningen",
                    "filters": {"type": "MBOOPLEIDINGSERKENNING", "erkendeopleidingscode": 25295},
                },
            ),
        ),
    ),
    # UWV en ROA maken zelf geen snippet; de selectie op hun tabel wel (#577).
    Geval(
        "uwv",
        ((TOOL_GET_UWV_VACATURES, {"provincie": "flevoland"}), (TOOL_QUERY_DATA, {"data_key": Vorige()})),
        kolommen=True,
    ),
    Geval(
        "uwv_gemeente",
        (
            (TOOL_GET_UWV_VACATURES, {"provincie": "Flevoland", "gemeente": "Almere"}),
            (TOOL_QUERY_DATA, {"data_key": Vorige()}),
        ),
    ),
    Geval("roa", ((TOOL_GET_ROA_BENCHMARK, {}), (TOOL_QUERY_DATA, {"data_key": Vorige()}))),
    Geval(
        "roa_ho",
        (
            (TOOL_GET_ROA_BENCHMARK, {"regio": "Groningen", "onderdeel": "ECONOMIE"}),
            (TOOL_QUERY_DATA, {"data_key": Vorige()}),
        ),
    ),
    # De tools op een geladen key: een selectie, een key in een andere spelling (#331), een selectie op een selectie,
    # een KPI, een eigen berekening, een grafiek en een kaart.
    Geval("query_data", (_DUO, (TOOL_QUERY_DATA, {"data_key": Vorige(), "filters": {"GESLACHT": "vrouw"}}))),
    Geval("query_data_key_spelling", (_DUO, (TOOL_QUERY_DATA, {"data_key": Vorige(str.upper)}))),
    Geval(
        "query_data_op_selectie",
        (
            _DUO,
            (TOOL_QUERY_DATA, {"data_key": Vorige(), "filters": {"GESLACHT": "vrouw"}}),
            _PER_JAAR,
        ),
    ),
    Geval(
        "compute_kpi",
        (
            _DUO,
            _PER_JAAR,
            (
                TOOL_COMPUTE_KPI,
                {"data_key": Vorige(), "value_column": "AANTAL_INGESCHREVENEN", "metric": "last", "van": 2022},
            ),
        ),
    ),
    Geval(
        "run_analysis",
        (_DUO, (TOOL_RUN_ANALYSIS, {"data_key": Vorige(), "code": "result = int(df['AANTAL_INGESCHREVENEN'].sum())"})),
    ),
    Geval(
        "create_plot",
        (
            _DUO,
            _PER_JAAR,
            (TOOL_CREATE_PLOT, {"data_key": Vorige(), "x": "STUDIEJAAR", "y": "AANTAL_INGESCHREVENEN", "title": "t"}),
        ),
    ),
    Geval(
        "create_choropleth_map",
        (
            _MBO,
            _MBO_PER_PROVINCIE,
            (
                TOOL_CREATE_CHOROPLETH_MAP,
                {"data_key": Vorige(), "location_col": "PROVINCIE INSTELLING", "value_col": "BBL", "title": "t"},
            ),
        ),
    ),
    # Vaste maten: DUO per instelling, CBS landelijk, en de CBS-som (#667).
    Geval("get_maat_duo", ((TOOL_GET_MAAT, {"maat": maten.PERSONEN_HO, "instelling": "Universiteit Utrecht"}),)),
    Geval("get_maat_cbs", ((TOOL_GET_MAAT, {"maat": maten.DEELNEMERS_HO_LANDELIJK, "sector": "hbo"}),)),
    Geval("get_maat_cbs_mbo", ((TOOL_GET_MAAT, {"maat": maten.MBO_STUDENTEN_LANDELIJK, "vorm": "bol"}),)),
    Geval("get_maat_cbs_som", ((TOOL_GET_MAAT, {"maat": maten.DOORSTROOM_VMBO_MBO}),)),
]


def _invullen(args: dict, vorige: str | None) -> dict:
    uit = {}
    for naam, waarde in args.items():
        if isinstance(waarde, Vorige):
            assert vorige, "een stap met Vorige() heeft een eerdere stap met een data_key nodig"
            waarde = waarde.vorm(vorige)
        uit[naam] = waarde
    return uit


def _data_key(result: str) -> str | None:
    try:
        data = json.loads(result)
    except ValueError:
        return None
    return data.get("data_key") if isinstance(data, dict) else None


def _eindstap(tool: str) -> bool:
    """Een KPI, berekening, grafiek of kaart: de response noemt geen eigen data_key."""
    return tool in (TOOL_COMPUTE_KPI, TOOL_CREATE_PLOT, TOOL_CREATE_CHOROPLETH_MAP, TOOL_RUN_ANALYSIS)


def _draai(code: str) -> tuple[dict, BaseException | None]:
    namespace: dict = {}
    try:
        exec(compile(code, "<snippet>", "exec"), namespace)
    except Exception as e:  # de fout hoort in de melding van de test
        return namespace, e
    return namespace, None


def _zonder_hulp(aanroepen: list[Aanroep]) -> Counter:
    return Counter(a for a in aanroepen if (a.bron, a.eerste) not in _HULP)


def _verschil(app: Counter, snip: Counter) -> str:
    alleen_app = "\n".join(f"  app:     {a}" for a in (app - snip).elements())
    alleen_snippet = "\n".join(f"  snippet: {a}" for a in (snip - app).elements())
    return "\n".join(filter(None, [alleen_app, alleen_snippet]))


@pytest.mark.parametrize("geval", GEVALLEN, ids=lambda g: g.naam)
def test_de_snippet_laadt_wat_de_app_laadde(opnemer, geval: Geval):
    recepten: dict[str, dict] = {}
    app: list[Aanroep] = []
    vorige: str | None = None
    gecontroleerd = 0
    for tool, ruw in geval.stappen:
        args = _invullen(ruw, vorige)
        result, _ = tools.dispatch(tool, args)
        app += opnemer.wis()
        key = _data_key(result)
        assert key or _eindstap(tool), f"{tool} gaf geen data_key: {result[:300]}"
        # Zoals agent/loop.py: de snippet uit de ruwe argumenten van het model, de response en de recepten van de sessie.
        code = snippet.generate(tool, args, result, recept_van=recepten.get)
        # Zoals agent/session_data.py: het recept van de key, voor de snippets van de stappen hierna.
        if key and (recept := herlaad.recept(key, {"name": tool, "arguments": args})) is not None:
            recepten.setdefault(key, recept)
        vorige = key or vorige
        if code is None:
            continue
        namespace, fout = _draai(code)
        uit_snippet = opnemer.wis()
        verschil = _verschil(_zonder_hulp(app), _zonder_hulp(uit_snippet))
        assert not verschil, f"{tool} {ruw}: de snippet laadt iets anders dan de app\n{verschil}\n\n{code}"
        assert fout is None, f"{tool} {ruw}: de snippet faalt met {fout!r}\n\n{code}"
        if geval.kolommen and key:
            assert list(namespace["df"].columns) == list(store.get(key).columns), code
        gecontroleerd += 1
    assert gecontroleerd, f"{geval.naam}: geen stap maakte een snippet"
    assert app, f"{geval.naam}: de app laadde niets"
    # Elke laadaanroep in de store heeft laadregels in de snippet; anders faalt elke snippet op die key.
    laders = {known.laad[0] for k in store.list_keys() if (known := store.meta(k)) and known.laad}
    assert laders <= set(snippet._LAADREGELS), f"laadaanroep zonder laadregels in tools/snippet.py: {laders}"


def _ongedekt(handlers, generators, laadregels, gevallen) -> list[str]:
    """De tools zonder equivalentiegeval: met een snippet of laadregels, of zonder reden in _ZONDER_LAADSTAP."""
    gedekt = {tool for geval in gevallen for tool, _ in geval.stappen} | set(_EIGEN_TEST)
    met_snippet = set(generators) | set(laadregels)
    return sorted((met_snippet - gedekt) | (set(handlers) - gedekt - set(_ZONDER_LAADSTAP)))


def test_elke_tool_heeft_een_equivalentiegeval_of_een_reden():
    ongedekt = _ongedekt(tools._HANDLERS, snippet._GENERATORS, snippet._LAADREGELS, GEVALLEN)
    assert not ongedekt, (
        f"tools zonder equivalentiegeval (#945): {ongedekt}. Maakt de tool een snippet of zet hij een laadaanroep in de "
        "store (KeyMeta.laad), voeg dan een Geval toe in dit bestand (of zijn eigen test in _EIGEN_TEST); laadt hij geen data, zet hem met de reden in "
        "_ZONDER_LAADSTAP."
    )
    met_snippet = set(snippet._GENERATORS) | set(snippet._LAADREGELS)
    assert not (set(_ZONDER_LAADSTAP) & met_snippet), "een tool met snippet hoort niet in _ZONDER_LAADSTAP"
    assert not (set(_ZONDER_LAADSTAP) - set(tools._HANDLERS)), "_ZONDER_LAADSTAP noemt een tool die niet bestaat"
    for tool, pad in _EIGEN_TEST.items():
        assert (gouden.g.ROOT / pad).is_file(), f"{tool}: de eigen equivalentietest {pad} bestaat niet"


@pytest.mark.parametrize("waar", ["handler", "generator", "laadregels"])
def test_een_nieuwe_tool_zonder_geval_is_rood(waar):
    """Zoals een nieuwe bron met een eigen tool (#935, #936): zonder Geval noemt de dekkingstest hem."""
    nieuw = {"get_nieuwe_bron": None}
    handlers = {**tools._HANDLERS, **(nieuw if waar == "handler" else {})}
    generators = {**snippet._GENERATORS, **(nieuw if waar == "generator" else {})}
    laadregels = {**snippet._LAADREGELS, **(nieuw if waar == "laadregels" else {})}
    assert _ongedekt(handlers, generators, laadregels, GEVALLEN) == ["get_nieuwe_bron"]
