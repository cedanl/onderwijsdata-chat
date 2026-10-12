"""Het CBS-datasetcontract in de chat (#370).

De CBS-package levert per tabel een contract (populatie, teldefinitie, methodiek, periodecodes,
geografie, scopeprofiel) en noemt een tabel `cbs:85423NED`. De chat sprak alleen `catalog()`
aan en matchte kale ID's: dataset_details toonde van dat contract alleen de methodiek (#383),
en `cbs:85423NED` kende geen enkele tool. Hier: één ID-spelling aan de toolgrens, de
contractvelden in dataset_details en het catalogusmanifest in /version.
"""

import importlib
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core import catalogusversie
from tools import canoniek, cbs_meta
from tools.catalog import cbs_bron_id, dataset_details
from tools.cbs import get_cbs_data, get_cbs_dimension

# ── Eén ID-spelling (#370, sluit aan op #356) ──────────────────────────────────────────


@pytest.mark.parametrize("spelling", ["cbs:85423NED", "CBS_85423ned", "cbs/85423NED", " cbs:85423NED "])
def test_zonder_cbs_prefix_haalt_alleen_het_voorvoegsel_weg(spelling):
    assert canoniek.zonder_cbs_prefix(spelling) == spelling.strip()[4:]


@pytest.mark.parametrize("spelling", ["85423NED", "cbs:85423NED", "CBS_85423ned", "85423ned", " cbs/85423NED "])
def test_cbs_bron_id_brengt_elke_spelling_terug_tot_de_catalogusspelling(spelling):
    """Tegen de echte CBS-inventaris: 85423NED staat erin, in hoofdletters."""
    assert cbs_bron_id(spelling) == "85423NED"


def test_cbs_bron_id_volgt_de_spelling_van_de_catalogus_niet_een_hoofdletterregel():
    """CBS schrijft 85423NED naast 80040ned: de catalogus beslist, niet upper()."""
    with patch("tools.catalog._cbs_alles", return_value=[{"_cbs_id": "80040ned"}]):
        assert cbs_bron_id("cbs:80040NED") == "80040ned"
        assert cbs_bron_id("80040ned") == "80040ned"


@pytest.mark.parametrize("ander", ["p01hoinges", "cbs:foo", "mbo-studenten-per-instelling", "uwv-open-match-data", ""])
def test_cbs_bron_id_laat_een_ander_of_onbekend_id_met_rust(ander):
    assert cbs_bron_id(ander) == canoniek.zonder_cbs_prefix(ander)


_ENTRY = {"_cbs_id": "85423NED", "bron": "Hoger onderwijs; ingeschrevenen", "_kolommen": {"x": {}}}


def _details(dataset_id: str) -> dict:
    with patch("tools.catalog._cbs", return_value=[_ENTRY]), patch("tools.catalog._rio_duo", return_value=[]):
        return json.loads(dataset_details(dataset_id))


def test_details_onder_het_contract_id_en_het_bron_id_zijn_dezelfde_tabel():
    assert _details("cbs:85423NED") == _details("85423NED")
    assert _details("85423ned")["bron"] == "Hoger onderwijs; ingeschrevenen"


def test_get_cbs_data_laadt_onder_het_bron_id(zonder_scopegrens):
    rows = [{"Perioden": "2024SJ00", "TotaalIngeschrevenen_1": 10}]
    with (
        patch("tools.cbs.data", return_value=rows) as data,
        patch("tools.cbs.definitions", return_value={}),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = json.loads(get_cbs_data("cbs:85423ned"))
    assert result["data_key"] == "cbs:85423NED"
    assert data.call_args.args[0] == "85423NED"


def test_get_cbs_dimension_onder_het_contract_id(zonder_scopegrens):
    with patch("tools.cbs._dimension_rows", return_value=({"Key": "T001038", "Title": "Totaal"},)) as rows:
        result = json.loads(get_cbs_dimension("cbs:85423NED", "Geslacht"))
    assert result == {"T001038": "Totaal"}
    assert rows.call_args.args[0] == "85423NED"


# ── Contractvelden in dataset_details ─────────────────────────────────────────────────────


def test_details_noemen_populatie_sectoren_periodecodes_en_geografie():
    """Tegen het echte contract van de gelockte package; de methodiek van #383 blijft erbij."""
    details = _details("85423NED")
    assert "ingeschreven studenten" in details["populatie"][0]
    assert details["sectoren"] == ["hbo", "wo"]
    assert details["perioden"]["eerste"] == "2011/'12"
    assert details["perioden"]["codes"]["2011SJ00"] == "2011/'12"
    assert details["geografie"] == {"niveaus": ["landelijk"], "dekking": "Nederland"}
    assert details["teldefinitie"][0]["term"] == "Ingeschrevenen"
    assert any("10-tallen" in p for p in details["methodiek"]["afronding"])


def test_periodecodes_compact_met_de_status_alleen_als_die_niet_definitief_is():
    perioden = {
        "status": "supported",
        "frequentie": "Jaarlijks",
        "eerste": "2023/'24",
        "laatste": "2024/'25",
        "codes": {
            "status": "supported",
            "codes": [
                {"code": "2023SJ00", "titel": "2023/'24", "status": "Definitief", "toelichting": None},
                {"code": "2024SJ00", "titel": "2024/'25", "status": "Voorlopig", "toelichting": "x"},
            ],
        },
    }
    assert cbs_meta._perioden(perioden) == {
        "frequentie": "Jaarlijks",
        "eerste": "2023/'24",
        "laatste": "2024/'25",
        "codes": {"2023SJ00": "2023/'24", "2024SJ00": "2024/'25 (voorlopig)"},
    }


def test_alleen_wat_het_contract_vastlegt():
    contract = {
        "populatie": {"status": "unknown"},
        "scopeprofiel": {"mbo": "supported", "hbo": "unsupported", "wo": "unknown"},
        "perioden": {"status": "unknown", "reden": "niet vastgelegd"},
        "geografie": {"status": "supported", "niveaus": ["gemeente"], "dekking": None},
        "teldefinitie": {"status": "unknown"},
        "methodiek": {"status": "unknown"},
    }
    with patch("tools.cbs_meta._contract.get_dataset", return_value=contract):
        assert cbs_meta.metadata("X") == {"sectoren": ["mbo"], "geografie": {"niveaus": ["gemeente"]}}


# ── Het manifest in /version ──────────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import server

    importlib.reload(server)
    return TestClient(server.app)


def test_version_noemt_het_manifest_van_de_meegebouwde_cbs_catalogus(client):
    catalogus = client.get("/version").json()["catalogus"]
    manifest = next(p for p in catalogus if p["pakket"] == "onderwijsdata")["manifest"]
    assert manifest["consistent"] is True
    assert manifest["catalogusrevisie"] and manifest["aantal"] > 0
    assert set(manifest["versheid"]) >= {"oudste_controle", "afleiding_verouderd", "perioden_verouderd"}
    assert manifest["laatste_succesvolle_controle"]


def test_version_blijft_werken_zonder_manifest():
    with patch("onderwijsdata.catalog_manifest", side_effect=RuntimeError("geen artefact")):
        assert catalogusversie._cbs_manifest() is None
