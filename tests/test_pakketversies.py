"""Een snippet noemt de pakketversies waarmee hij is gemaakt (#714)."""

import json
from importlib import metadata

import pytest

from config import Config
from tools import pakketversies, snippet
from tools.pakketversies import versiekop

_DUO = {"dataset_id": "p01hoinges", "resource": "x"}


class _Dist:
    def __init__(self, version: str, direct_url: dict | None):
        self.version = version
        self._direct = direct_url

    def read_text(self, naam: str):
        return None if self._direct is None else json.dumps(self._direct)


@pytest.fixture(autouse=True)
def _schone_cache():
    pakketversies._pakket.cache_clear()
    yield
    pakketversies._pakket.cache_clear()


def _installeer(monkeypatch, pakketten: dict[str, _Dist]):
    def distribution(naam):
        if naam not in pakketten:
            raise metadata.PackageNotFoundError(naam)
        return pakketten[naam]

    monkeypatch.setattr(pakketversies.metadata, "distribution", distribution)


def test_een_git_installatie_noemt_versie_revisie_en_de_exacte_commit(monkeypatch):
    direct = {
        "url": "https://github.com/cedanl/rio-onderwijsdata.git",
        "vcs_info": {
            "vcs": "git",
            "commit_id": "ef7f92fa98432ee07e8417066cd8d78d002005de",
            "requested_revision": "ef7f92fa",
        },
    }
    _installeer(monkeypatch, {"riodata": _Dist("0.6.0", direct)})
    monkeypatch.setattr(Config, "APP_VERSION", "2.5.0")

    kop = versiekop("from riodata import duo\n")

    assert kop[0] == "# Gemaakt met riodata 0.6.0 (ef7f92fa), app 2.5.0."
    assert kop[1] == (
        '# Dezelfde versies installeren: pip install "riodata @ '
        'git+https://github.com/cedanl/rio-onderwijsdata.git@ef7f92fa98432ee07e8417066cd8d78d002005de"'
    )


def test_een_pypi_installatie_pint_op_het_versienummer(monkeypatch):
    _installeer(monkeypatch, {"onderwijsdata": _Dist("0.2.2", None)})
    monkeypatch.setattr(Config, "APP_VERSION", None)

    kop = versiekop("from onderwijsdata import data\n")

    assert kop == [
        "# Gemaakt met onderwijsdata 0.2.2.",
        '# Dezelfde versies installeren: pip install "onderwijsdata==0.2.2"',
    ]


def test_alleen_de_pakketten_die_de_snippet_gebruikt_staan_in_de_kop(monkeypatch):
    _installeer(monkeypatch, {"riodata": _Dist("0.6.0", None), "onderwijsdata": _Dist("0.2.2", None)})

    kop = "\n".join(versiekop("from onderwijsdata import data\n"))

    assert "onderwijsdata 0.2.2" in kop and "riodata" not in kop


def test_zonder_bronpakket_in_de_snippet_of_in_de_omgeving_geen_kop(monkeypatch):
    _installeer(monkeypatch, {})

    assert versiekop("from riodata import duo\n") == []
    assert versiekop("import pandas as pd\n") == []


def test_de_snippet_van_een_laadstap_begint_met_de_kop_en_noemt_de_geinstalleerde_versie():
    tekst = snippet.generate("get_duo_data", _DUO)

    assert tekst is not None
    assert tekst.startswith("# Gemaakt met riodata " + metadata.version("riodata"))
    assert "from riodata import duo" in tekst


def test_de_databewerking_blijft_het_eerste_wat_een_lezer_ziet():
    result = json.dumps({"databewerking": ["Sentinel -1 uitgesloten."]})

    regels = (snippet.generate("get_duo_data", _DUO, result) or "").splitlines()

    assert regels[:2] == ["# Databewerking in de app:", "# Sentinel -1 uitgesloten."]
    assert any(r.startswith("# Gemaakt met") for r in regels)
