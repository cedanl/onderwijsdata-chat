"""De provincie van de instelling bij mbo-bestanden zonder provinciekolom (#453).

"Gediplomeerden van ROC Midden Nederland tegenover de andere instellingen in Utrecht" kostte
een tweede bestand en een koppeling, omdat het diplomabestand geen provincie heeft. De
kolom komt nu uit DUO's adressenbestand op INSTELLINGSCODE; een onbekende code blijft leeg.
"""

import json
import sys
import types
from unittest.mock import patch

import pandas as pd
import pytest

from tools import instellingsprovincie, store
from tools.duo import column_definitions, get_duo_data
from tools.query import query_data
from tools.snippet import generate

_KOLOM = instellingsprovincie.KOLOM
_DIPLOMA = "gediplomeerde-mbo-studenten"

# Als data/instellingen.get_adres_lookup: code → adres, uit adressen_ho en adressen_mbo.
_ADRESSEN = {
    "25LH": {"provincie": "Utrecht", "arbeidsmarktregio": "Midden-Utrecht", "plaatsnaam": "UTRECHT"},
    "01OE": {"provincie": "Utrecht", "arbeidsmarktregio": "Midden-Utrecht", "plaatsnaam": "UTRECHT"},
    "00GT": {"provincie": "Zuid-Holland", "arbeidsmarktregio": "Rijnmond", "plaatsnaam": "ROTTERDAM"},
    "99ZZ": {"provincie": None, "arbeidsmarktregio": None, "plaatsnaam": None},
}

# Breed formaat zoals DUO het publiceert.
_DIPLOMAS = pd.DataFrame(
    {
        "INSTELLINGSCODE": ["25LH", "25LH", "01OE", "00GT", "12AB", "99ZZ"],
        "INSTELLINGSNAAM": ["ROC Midden Nederland"] * 2 + ["Grafisch Lyceum Utrecht", "Albeda", "Onbekend", "Leeg"],
        "PLAATSNAAM INSTELLING": ["UTRECHT", "UTRECHT", "UTRECHT", "ROTTERDAM", "ERGENS", "NERGENS"],
        "DIPMAN2025": [100, 50, 20, 300, 7, 8],
        "DIPVROUW2025": [80, 40, 10, 200, 5, 6],
    }
)


@pytest.fixture
def adressen():
    with patch("tools.instellingsprovincie.get_adres_lookup", return_value=_ADRESSEN):
        yield


def _laad(df: pd.DataFrame, dataset: str = _DIPLOMA, resource: int = 0) -> dict:
    with patch("tools.duo._duo.load", return_value=df.copy()):
        return json.loads(get_duo_data(dataset, resource))


def _provincies(dataset: str = _DIPLOMA) -> dict[str, object]:
    df = store.get(f"duo:{dataset}:0")
    assert df is not None
    return dict(zip(df["INSTELLINGSCODE"], df[_KOLOM], strict=True))


def test_roc_midden_nederland_ligt_in_utrecht(adressen):
    _laad(_DIPLOMAS)

    assert _provincies()["25LH"] == "Utrecht"
    assert _provincies()["00GT"] == "Zuid-Holland"


@pytest.mark.parametrize("code", ["12AB", "99ZZ"])
def test_onbekende_code_blijft_leeg(adressen, code):
    _laad(_DIPLOMAS)

    assert pd.isna(_provincies()[code])


def test_zonder_adressen_blijft_de_kolom_leeg():
    with patch("tools.instellingsprovincie.get_adres_lookup", return_value={}):
        _laad(_DIPLOMAS)

    assert _provincies().keys() == set(_DIPLOMAS["INSTELLINGSCODE"])
    assert all(pd.isna(p) for p in _provincies().values())


def test_de_kolom_noemt_zijn_herkomst(adressen):
    result = _laad(_DIPLOMAS)
    kolom = next(k for k in result["kolommen"] if k["kolom"] == _KOLOM)

    assert "adressen_mbo" in kolom["definitie"]
    assert "niet de woonprovincie" in kolom["definitie"]


@pytest.mark.parametrize("dataset", ["instromende-mbo-studenten", "mbo-studenten-per-instelling"])
def test_ook_de_andere_mbo_bestanden(adressen, dataset):
    _laad(_DIPLOMAS[["INSTELLINGSCODE", "INSTELLINGSNAAM", "DIPMAN2025"]], dataset)

    assert _provincies(dataset)["25LH"] == "Utrecht"


def test_een_provinciekolom_van_duo_blijft_staan(adressen):
    eigen = pd.DataFrame({"INSTELLINGSCODE": ["25LH"], "INSTELLINGSNAAM": ["ROC MN"], _KOLOM: ["Door DUO"]})
    _laad(eigen, "mbo-studenten-per-instelling")

    assert _provincies("mbo-studenten-per-instelling")["25LH"] == "Door DUO"


def test_ho_bestanden_krijgen_geen_kolom(adressen):
    ho = pd.DataFrame({"INSTELLINGSCODE": ["25LH"], "INSTELLINGSNAAM": ["x"], "AANTAL": [1]})
    _laad(ho, "p01hoinges")

    assert _KOLOM not in store.get("duo:p01hoinges:0").columns


def test_definitie_alleen_bij_de_mbo_bestanden():
    assert _KOLOM in column_definitions([_KOLOM], _DIPLOMA)
    assert _KOLOM not in column_definitions([_KOLOM], "p01hoinges")


def test_de_vraag_uit_453_is_een_selectie_na_het_laden(adressen):
    """De vraag uit #453 in één query_data na het laden, zonder tweede bestand of koppeling."""
    key = _laad(_DIPLOMAS)["data_key"]
    result = json.loads(
        query_data(
            key,
            filters={_KOLOM: "Utrecht"},
            group_by=["INSTELLINGSNAAM"],
            aggregate={"DIPMAN2025": "sum", "DIPVROUW2025": "sum"},
        )
    )

    per_instelling = {r["INSTELLINGSNAAM"]: r["DIPMAN2025"] + r["DIPVROUW2025"] for r in result["rijen"]}
    assert per_instelling == {"ROC Midden Nederland": 270, "Grafisch Lyceum Utrecht": 30}


def test_snippet_leidt_de_kolom_op_dezelfde_manier_af(monkeypatch):
    """Een snippet die op de provincie filtert, moet buiten de app dezelfde kolom hebben (#131)."""
    adressen_mbo = pd.DataFrame({"INSTELLINGSCODE": ["25LH", "00GT"], "PROVINCIE": ["Utrecht", "Zuid-Holland"]})
    bestanden = {(_DIPLOMA, 0): _DIPLOMAS, ("adressen_mbo", 1): adressen_mbo}

    def fake_load(dataset_id, resource=0, **kwargs):
        return bestanden[(dataset_id, resource)].copy()

    duo_module = types.SimpleNamespace(load=fake_load)
    riodata = types.SimpleNamespace(duo=duo_module)
    monkeypatch.setitem(sys.modules, "riodata", riodata)
    monkeypatch.setitem(sys.modules, "riodata.duo", duo_module)

    snippet = generate("get_duo_data", {"dataset_id": _DIPLOMA, "resource": 0})
    assert snippet is not None
    namespace: dict = {}
    exec(snippet, namespace)

    df = namespace["df"]
    assert dict(zip(df["INSTELLINGSCODE"], df[_KOLOM], strict=True))["25LH"] == "Utrecht"
    assert df.loc[df["INSTELLINGSCODE"] == "12AB", _KOLOM].isna().all()


def test_snippet_van_een_ho_bestand_laadt_geen_adressen():
    snippet = generate("get_duo_data", {"dataset_id": "p01hoinges", "resource": 0})

    assert snippet is not None
    assert "adressen_mbo" not in snippet
