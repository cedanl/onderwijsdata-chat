"""Een snippet noemt de versies waarmee hij is gemaakt en een installatieregel die werkt (#714, #888).

`onderwijsdata` en `riodata` staan sinds #885 in deze repo (`packages/`) en staan niet op PyPI. De herkomst van een
pakket is dus de commit van de chat-repo waarop de app draait; de installatieregel haalt het pakket uit een
subdirectory van de publieke GitHub-spiegel op die commit.
"""

import json
import tomllib
from importlib import metadata
from pathlib import Path

import pytest

from config import Config
from core import pakketherkomst
from tools import pakketversies, snippet
from tools.pakketversies import versiekop

_DUO = {"dataset_id": "p01hoinges", "resource": "x"}
_COMMIT = "7d3488aa0da386a087f6363b3f2ffa40049f604b"
_MIRROR = "https://github.com/cedanl/onderwijsdata-chat"
_ROOT = Path(__file__).resolve().parent.parent


def _installeer(monkeypatch, versies: dict[str, str]):
    def version(naam):
        if naam not in versies:
            raise metadata.PackageNotFoundError(naam)
        return versies[naam]

    monkeypatch.setattr(pakketherkomst.metadata, "version", version)


def _app(monkeypatch, versie: str | None, commit: str | None):
    monkeypatch.setattr(Config, "APP_VERSION", versie)
    monkeypatch.setattr(Config, "GIT_COMMIT", commit)


def test_de_kop_noemt_pakketversie_app_en_de_commit_waarop_de_app_draait(monkeypatch):
    _installeer(monkeypatch, {"riodata": "0.7.0"})
    _app(monkeypatch, "2.5.0", _COMMIT)

    kop = versiekop("from riodata import duo\n")

    assert kop[0] == "# Gemaakt met riodata 0.7.0, app 2.5.0, commit 7d3488aa."


def test_de_installatieregel_haalt_het_pakket_uit_een_subdirectory_van_de_spiegel_op_de_volledige_commit(monkeypatch):
    _installeer(monkeypatch, {"riodata": "0.7.0"})
    _app(monkeypatch, "2.5.0", _COMMIT)

    kop = versiekop("from riodata import duo\n")

    assert kop[1] == (
        f'# Dezelfde versies installeren: pip install "riodata @ git+{_MIRROR}@{_COMMIT}#subdirectory=packages/riodata"'
    )


def test_twee_pakketten_geven_een_pip_regel_met_beide_subdirectories(monkeypatch):
    _installeer(monkeypatch, {"riodata": "0.7.0", "onderwijsdata": "0.2.2"})
    _app(monkeypatch, None, _COMMIT)

    kop = versiekop("from onderwijsdata import data\nfrom riodata import duo\n")

    assert kop[0] == "# Gemaakt met onderwijsdata 0.2.2, riodata 0.7.0, commit 7d3488aa."
    assert f'"onderwijsdata @ git+{_MIRROR}@{_COMMIT}#subdirectory=packages/onderwijsdata"' in kop[1]
    assert f'"riodata @ git+{_MIRROR}@{_COMMIT}#subdirectory=packages/riodata"' in kop[1]


def test_zonder_bekende_commit_zegt_de_kop_dat_de_regel_de_nieuwste_versie_installeert(monkeypatch):
    # Lokaal, zonder build-arg: een versienummer pint niets (de pakketten staan niet op PyPI), dus geen schijnzekerheid.
    _installeer(monkeypatch, {"onderwijsdata": "0.2.2"})
    _app(monkeypatch, None, None)

    kop = versiekop("from onderwijsdata import data\n")

    assert kop[0] == "# Gemaakt met onderwijsdata 0.2.2."
    assert kop[1].startswith("# Commit onbekend, dus de nieuwste versie installeren: pip install ")
    assert f'"onderwijsdata @ git+{_MIRROR}#subdirectory=packages/onderwijsdata"' in kop[1]
    assert "==" not in kop[1]


def test_alleen_de_pakketten_die_de_snippet_gebruikt_staan_in_de_kop(monkeypatch):
    _installeer(monkeypatch, {"riodata": "0.7.0", "onderwijsdata": "0.2.2"})
    _app(monkeypatch, None, _COMMIT)

    kop = "\n".join(versiekop("from onderwijsdata import data\n"))

    assert "onderwijsdata 0.2.2" in kop and "riodata" not in kop


def test_zonder_bronpakket_in_de_snippet_of_in_de_omgeving_geen_kop(monkeypatch):
    _installeer(monkeypatch, {})

    assert versiekop("from riodata import duo\n") == []
    assert versiekop("import pandas as pd\n") == []


def test_elke_subdirectory_uit_de_installatieregel_bestaat_en_heet_zoals_het_pakket():
    # Bewaakt de afspraak met de spiegel: een hernoeming (#890) of verhuizing moet de regel meenemen.
    for naam in pakketversies._IMPORTS.values():
        pyproject = _ROOT / "packages" / naam / "pyproject.toml"
        assert tomllib.loads(pyproject.read_text())["project"]["name"] == naam
        assert pakketherkomst.installatiespec(naam, _COMMIT).endswith(f"#subdirectory=packages/{naam}")


def test_de_snippet_van_een_laadstap_begint_met_de_kop_en_noemt_de_geinstalleerde_versie(monkeypatch):
    _app(monkeypatch, "2.5.0", _COMMIT)

    tekst = snippet.generate("get_duo_data", _DUO)

    assert tekst is not None
    assert tekst.startswith("# Gemaakt met riodata " + metadata.version("riodata"))
    assert f"@{_COMMIT}#subdirectory=packages/riodata" in tekst
    assert "from riodata import duo" in tekst


def test_de_databewerking_blijft_het_eerste_wat_een_lezer_ziet():
    result = json.dumps({"databewerking": ["Sentinel -1 uitgesloten."]})

    regels = (snippet.generate("get_duo_data", _DUO, result) or "").splitlines()

    assert regels[:2] == ["# Databewerking in de app:", "# Sentinel -1 uitgesloten."]
    assert any(r.startswith("# Gemaakt met") for r in regels)


@pytest.mark.parametrize("naam", ["onderwijsdata", "riodata"])
def test_pakketversie_komt_uit_de_metadata_en_is_none_zonder_installatie(naam):
    assert pakketherkomst.pakketversie(naam) == metadata.version(naam)
    assert pakketherkomst.pakketversie("bestaat-niet-xyz") is None
