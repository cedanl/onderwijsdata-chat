"""Een snippet noemt de versies waarmee hij is gemaakt en een installatieregel die werkt (#714, #888).

`onderwijsbronnen` (tot #910 `onderwijsdata` en `riodata`) staat sinds #885 in deze repo (`packages/`) en niet op
PyPI. De herkomst van het pakket is dus de commit van de chat-repo waarop de app draait; de installatieregel haalt het pakket uit een
subdirectory van de publieke GitHub-spiegel op die commit.
"""

import json
import tomllib
from importlib import metadata
from pathlib import Path

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
    _installeer(monkeypatch, {"onderwijsbronnen": "0.8.0"})
    _app(monkeypatch, "2.5.0", _COMMIT)

    kop = versiekop("from onderwijsbronnen import duo\n")

    assert kop[0] == "# Gemaakt met onderwijsbronnen 0.8.0, app 2.5.0, commit 7d3488aa."


def test_de_installatieregel_haalt_het_pakket_uit_een_subdirectory_van_de_spiegel_op_de_volledige_commit(monkeypatch):
    _installeer(monkeypatch, {"onderwijsbronnen": "0.8.0"})
    _app(monkeypatch, "2.5.0", _COMMIT)

    kop = versiekop("from onderwijsbronnen import duo\n")

    assert kop[1] == (
        "# Dezelfde versies installeren: pip install "
        f'"onderwijsbronnen[analyse] @ git+{_MIRROR}@{_COMMIT}#subdirectory=packages/onderwijsbronnen"'
    )


def test_cbs_en_duo_in_een_snippet_geven_een_pakket_en_een_pip_regel(monkeypatch):
    """Sinds #910 één pakket: CBS (`onderwijsbronnen.cbs`) en DUO komen uit dezelfde installatie."""
    _installeer(monkeypatch, {"onderwijsbronnen": "0.8.0"})
    _app(monkeypatch, None, _COMMIT)

    kop = versiekop("from onderwijsbronnen.cbs import data\nfrom onderwijsbronnen import duo\n")

    assert kop[0] == "# Gemaakt met onderwijsbronnen 0.8.0, commit 7d3488aa."
    assert kop[1].count("pip install") == 1 and kop[1].count("onderwijsbronnen[analyse] @") == 1


def test_zonder_bekende_commit_zegt_de_kop_dat_de_regel_de_nieuwste_versie_installeert(monkeypatch):
    # Lokaal, zonder build-arg: een versienummer pint niets (het pakket staat niet op PyPI), dus geen schijnzekerheid.
    _installeer(monkeypatch, {"onderwijsbronnen": "0.8.0"})
    _app(monkeypatch, None, None)

    kop = versiekop("from onderwijsbronnen.cbs import data\n")

    assert kop[0] == "# Gemaakt met onderwijsbronnen 0.8.0."
    assert kop[1].startswith("# Commit onbekend, dus de nieuwste versie installeren: pip install ")
    assert f'"onderwijsbronnen[analyse] @ git+{_MIRROR}#subdirectory=packages/onderwijsbronnen"' in kop[1]
    assert "==" not in kop[1]


def test_een_oude_importregel_krijgt_geen_kop(monkeypatch):
    """`riodata`/`onderwijsdata` zijn geen distributies meer; een snippet van de app gebruikt ze niet (#910)."""
    _installeer(monkeypatch, {"onderwijsbronnen": "0.8.0"})
    _app(monkeypatch, None, _COMMIT)

    assert versiekop("from riodata import duo\n") == []
    assert versiekop("from onderwijsdata import data\n") == []


def test_zonder_bronpakket_in_de_snippet_of_in_de_omgeving_geen_kop(monkeypatch):
    _installeer(monkeypatch, {})

    assert versiekop("from onderwijsbronnen import duo\n") == []
    assert versiekop("import pandas as pd\n") == []


def test_elke_subdirectory_uit_de_installatieregel_bestaat_en_heet_zoals_het_pakket():
    # Bewaakt de afspraak met de spiegel: een hernoeming (#890) of verhuizing moet de regel meenemen.
    for naam in pakketversies._IMPORTS.values():
        pyproject = _ROOT / "packages" / naam / "pyproject.toml"
        assert tomllib.loads(pyproject.read_text())["project"]["name"] == naam
        assert pakketherkomst.installatiespec(naam, _COMMIT).endswith(f"#subdirectory=packages/{naam}")


def test_de_extras_van_de_regel_geven_pandas_en_openpyxl():
    """#971: zonder extras installeerde de regel alleen httpx en defusedxml; elke snippet importeert pandas, en de
    financiën van DUO en de crebolijst van SBB lezen Excel met openpyxl."""
    for naam in pakketversies._IMPORTS.values():
        extras = pakketversies._EXTRAS.get(naam, ())
        optioneel = tomllib.loads((_ROOT / "packages" / naam / "pyproject.toml").read_text())["project"][
            "optional-dependencies"
        ]
        vereist = {eis.split(">")[0].split("=")[0].strip() for extra in extras for eis in optioneel[extra]}
        assert {"pandas", "openpyxl"} <= vereist


def test_een_snippet_met_een_grafiek_installeert_plotly_erbij(monkeypatch):
    # plotly hangt niet aan het bronpakket; zonder deze toevoeging faalde `import plotly.express` (#971).
    _installeer(monkeypatch, {"onderwijsbronnen": "0.8.0"})
    _app(monkeypatch, None, _COMMIT)

    met = versiekop("from onderwijsbronnen import duo\nimport plotly.express as px\n")
    zonder = versiekop("from onderwijsbronnen import duo\n")

    assert met[1].endswith('#subdirectory=packages/onderwijsbronnen" plotly')
    assert "plotly" not in zonder[1]


def test_de_snippet_van_een_laadstap_begint_met_de_kop_en_noemt_de_geinstalleerde_versie(monkeypatch):
    _app(monkeypatch, "2.5.0", _COMMIT)

    tekst = snippet.generate("get_duo_data", _DUO)

    assert tekst is not None
    assert tekst.startswith("# Gemaakt met onderwijsbronnen " + metadata.version("onderwijsbronnen"))
    assert f"@{_COMMIT}#subdirectory=packages/onderwijsbronnen" in tekst
    assert '"onderwijsbronnen[analyse] @ git+' in tekst
    assert "from onderwijsbronnen import duo" in tekst


def test_de_databewerking_blijft_het_eerste_wat_een_lezer_ziet():
    result = json.dumps({"databewerking": ["Sentinel -1 uitgesloten."]})

    regels = (snippet.generate("get_duo_data", _DUO, result) or "").splitlines()

    assert regels[:2] == ["# Databewerking in de app:", "# Sentinel -1 uitgesloten."]
    assert any(r.startswith("# Gemaakt met") for r in regels)


def test_pakketversie_komt_uit_de_metadata_en_is_none_zonder_installatie():
    assert pakketherkomst.pakketversie("onderwijsbronnen") == metadata.version("onderwijsbronnen")
    assert pakketherkomst.pakketversie("riodata") is None  # de shim is geen eigen distributie (#910)
    assert pakketherkomst.pakketversie("bestaat-niet-xyz") is None
