"""De overgangsnamen `riodata` en `onderwijsdata` (#910): dezelfde objecten als in onderwijsbronnen, met een waarschuwing.

Een snippet of oude code die de oude naam gebruikt, moet tijdens de overgang precies hetzelfde krijgen als nieuwe code:
dezelfde module (dus ook dezelfde monkeypatch), dezelfde functies en dezelfde catalogus. Elke import in een eigen
interpreter, zoals een snippet draait: in dit proces hebben andere tests de modules al geladen.
"""

import importlib
import subprocess
import sys
import warnings

import pytest

import onderwijsbronnen


def _schoon(*regels: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-W", "error::DeprecationWarning:__main__", "-c", "\n".join(regels)],
                          capture_output=True, text=True, timeout=60)


def _importeer(naam):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return importlib.import_module(naam)


@pytest.mark.parametrize("naam", ["riodata", "onderwijsdata"])
def test_de_oude_naam_waarschuwt_bij_de_eerste_import(naam):
    uit = _schoon("import warnings", "warnings.simplefilter('always')",
                  "with warnings.catch_warnings(record=True) as w:",
                  f"    import {naam}",
                  "assert any(issubclass(x.category, DeprecationWarning) and 'onderwijsbronnen' in str(x.message)"
                  " for x in w), [str(x.message) for x in w]")
    assert uit.returncode == 0, uit.stderr


@pytest.mark.parametrize(
    ("oud", "nieuw"),
    [
        ("riodata.duo", "onderwijsbronnen.duo"),
        ("riodata.roa", "onderwijsbronnen.roa"),
        ("riodata.uwv", "onderwijsbronnen.uwv"),
        ("riodata.inspectie", "onderwijsbronnen.inspectie"),
        ("riodata.sbb", "onderwijsbronnen.sbb"),
        ("riodata.crebo", "onderwijsbronnen.sbb.crebo"),
        ("riodata.sbb_xml", "onderwijsbronnen.sbb.dossiers"),
        ("riodata.contract", "onderwijsbronnen.contract"),
        ("riodata.scope", "onderwijsbronnen.scope"),
        ("riodata.client", "onderwijsbronnen.rio.client"),
        ("riodata.overgangen", "onderwijsbronnen.rio.overgangen"),
        ("riodata.aanbieders", "onderwijsbronnen.rio.aanbieders"),
        ("riodata.duo_notes", "onderwijsbronnen.duo.notes"),
        ("riodata._catalog", "onderwijsbronnen._kern.verrijking"),
        ("riodata._filtercontract", "onderwijsbronnen.rio._filtercontract"),
        ("riodata._lezen", "onderwijsbronnen._kern.lezen"),
        ("riodata._resolutie", "onderwijsbronnen._kern.resolutie"),
        ("onderwijsdata", "onderwijsbronnen.cbs"),
        ("onderwijsdata.client", "onderwijsbronnen.cbs.client"),
        ("onderwijsdata.contract", "onderwijsbronnen.cbs.contract"),
        ("onderwijsdata.validatie", "onderwijsbronnen.cbs.validatie"),
    ],
)
def test_een_oude_module_is_de_nieuwe_module(oud, nieuw):
    """`import riodata.duo` laadt geen tweede kopie: een monkeypatch op de oude naam raakt wat de chat gebruikt."""
    assert _importeer(oud) is importlib.import_module(nieuw)


@pytest.mark.parametrize(
    ("naam", "nieuw"),
    [
        ("fetch", onderwijsbronnen.rio.fetch),
        ("get", onderwijsbronnen.rio.get),
        ("related", onderwijsbronnen.rio.related),
        ("filtercontract", onderwijsbronnen.rio.filtercontract),
        ("typewaarden", onderwijsbronnen.rio.typewaarden),
        ("valideer_filters", onderwijsbronnen.rio.valideer_filters),
        ("opvolgers", onderwijsbronnen.rio.opvolgers),
        ("voorgangers", onderwijsbronnen.rio.voorgangers),
        ("Stap", onderwijsbronnen.rio.Stap),
        ("onderwijsaanbieders", onderwijsbronnen.rio.onderwijsaanbieders),
        ("catalog", onderwijsbronnen.catalog),
        ("AmbigueResource", onderwijsbronnen.AmbigueResource),
        ("ResourceNietGevonden", onderwijsbronnen.ResourceNietGevonden),
        ("__version__", onderwijsbronnen.__version__),
    ],
)
def test_de_namen_van_riodata_zijn_die_van_onderwijsbronnen(naam, nieuw):
    assert getattr(_importeer("riodata"), naam) is nieuw


def test_riodata_heeft_dezelfde_publieke_namen_als_voorheen():
    assert set(_importeer("riodata").__all__) == {
        "fetch", "get", "related", "catalog", "filtercontract", "typewaarden", "valideer_filters", "duo", "roa", "uwv",
        "inspectie", "sbb", "crebo", "contract", "opvolgers", "voorgangers", "Stap", "onderwijsaanbieders", "AmbigueResource",
        "ResourceNietGevonden", "__version__",
    }


def test_een_monkeypatch_via_de_oude_naam_raakt_de_nieuwe_module(monkeypatch):
    _importeer("riodata")
    monkeypatch.setattr("riodata.duo.load", lambda *a, **k: "nep")
    assert onderwijsbronnen.duo.load() == "nep"


@pytest.mark.parametrize(
    "regels",
    [
        ["from riodata import duo", "assert callable(duo.load) and duo.__name__ == 'onderwijsbronnen.duo'"],
        ["from riodata import fetch", "import onderwijsbronnen.rio", "assert fetch is onderwijsbronnen.rio.fetch"],
        ["from riodata import roa, uwv", "assert callable(roa.load) and callable(uwv.load)"],
        ["import riodata", "assert len(riodata.catalog('all')) == 77"],
        # De bekende naambotsing (#909): vóór een catalogusaanroep is `data` de functie.
        ["from onderwijsdata import data", "import onderwijsbronnen.cbs.client as c", "assert data is c.data"],
        ["import onderwijsdata", "assert onderwijsdata.get_dataset('cbs:85423NED')['dataset_id'] == 'cbs:85423NED'"],
    ],
    ids=lambda r: r[0],
)
def test_een_snippetregel_met_de_oude_naam_werkt_in_een_schoon_proces(regels):
    uit = _schoon("import warnings", "warnings.simplefilter('ignore', DeprecationWarning)", *regels)
    assert uit.returncode == 0, uit.stderr
