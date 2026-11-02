"""DUO-bestanden laden met encodingterugval en kolomdriftcontrole (#868).

Een cp1252-bestand faalde met een UnicodeDecodeError; een hernoemde kolom laadde stil, met een codekolom die numeriek
werd. Nu: een tweede poging in cp1252 (`DUO_ENCODING`) en een waarschuwing bij elke afwijking van de schema-snapshot
van riodata (`DUO_SCHEMA_DRIFT`).
"""

import json
import logging
from dataclasses import dataclass
from unittest.mock import patch

import pandas as pd
import pytest
from riodata import duo as riodata_duo

from tests.nepserver import Antwoord, Nepserver, nepserver
from tools import duo, duo_laden, store

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_DATASET = "p01hoinges"
_SCHEMA = riodata_duo.resource_schemas(_DATASET)[0]
_KOLOMMEN = [k["naam"] for k in _SCHEMA["kolommen"]]
_MD5 = "0123456789abcdef0123456789abcdef"
_CP1252 = "GEMEENTENAAM,AANTAL_INGESCHREVENEN\nSúdwest-Fryslân,12\n".encode("cp1252")


@dataclass
class _DuoBron:
    server: Nepserver
    bestand: bytes = b""

    def downloads(self) -> int:
        return sum(1 for pad in self.server.verzoeken if pad.startswith("/bestand.csv"))


@pytest.fixture
def duo_bron(monkeypatch):
    """riodata.duo.load tegen een nepserver: package_show met één CSV-resource, en dat bestand."""

    def antwoord(pad: str) -> Antwoord:
        if pad.startswith("/package_show"):
            resource = {"name": "bestand", "url": f"{bron.server.url}/bestand.csv", "format": "CSV", "id": "res-1"}
            body = {"success": True, "result": {"resources": [resource]}}
            return Antwoord(200, json.dumps(body).encode(), {"Content-Type": "application/json"})
        return Antwoord(200, bron.bestand, {"Content-Type": "text/csv"})

    with nepserver(antwoord) as server:
        bron = _DuoBron(server)
        monkeypatch.setattr(riodata_duo, "CKAN_BASE", server.url)
        yield bron


# --- encoding -------------------------------------------------------------------------------


def test_een_cp1252_bestand_laadt_met_de_terugval(duo_bron, caplog):
    duo_bron.bestand = _CP1252
    with caplog.at_level(logging.WARNING, logger="tools.duo_laden"):
        df = duo_laden.laad("testset", 0)
    assert df["GEMEENTENAAM"].tolist() == ["Súdwest-Fryslân"]
    assert "DUO_ENCODING dataset=testset resource=0 encoding=cp1252" in caplog.text
    assert duo_bron.downloads() == 2


def test_een_utf8_bestand_laadt_in_één_keer_zonder_terugval(duo_bron, caplog):
    duo_bron.bestand = _CP1252.decode("cp1252").encode("utf-8")
    with caplog.at_level(logging.WARNING, logger="tools.duo_laden"):
        df = duo_laden.laad("testset", 0)
    assert df["GEMEENTENAAM"].tolist() == ["Súdwest-Fryslân"]
    assert "DUO_ENCODING" not in caplog.text
    assert duo_bron.downloads() == 1


# --- kolomdrift -----------------------------------------------------------------------------


def test_gelijke_kolommen_zijn_geen_drift():
    assert duo_laden.kolomdrift(_DATASET, _SCHEMA["resource_id"], _KOLOMMEN) is None


def test_een_hernoemde_kolom_is_een_ontbrekende_en_een_nieuwe():
    kolommen = [k if k != _KOLOMMEN[1] else "NIEUWE_NAAM" for k in _KOLOMMEN]
    drift = duo_laden.kolomdrift(_DATASET, _SCHEMA["resource_id"], kolommen)
    assert drift == duo_laden.Kolomdrift(ontbrekend=(_KOLOMMEN[1],), nieuw=("NIEUWE_NAAM",))
    assert _KOLOMMEN[1] in drift.tekst() and "NIEUWE_NAAM" in drift.tekst()


def test_het_rijnummer_van_een_datastore_dump_is_geen_nieuwe_kolom():
    """Een dump van de CKAN-datastore begint met `_id`; de snapshot kent die kolom niet, en dat is geen drift."""
    assert duo_laden.kolomdrift(_DATASET, _SCHEMA["resource_id"], ["_id", *_KOLOMMEN]) is None


def test_een_bestand_buiten_de_snapshot_heeft_niets_om_mee_te_vergelijken():
    assert duo_laden.kolomdrift(_DATASET, "onbekende-resource", ["A"]) is None
    assert duo_laden.kolomdrift(_DATASET, None, ["A"]) is None


def _geladen(kolommen: list[str], md5: str | None = _MD5) -> pd.DataFrame:
    df = pd.DataFrame([dict.fromkeys(kolommen, "1")])
    df["STUDIEJAAR"] = 2024
    df.attrs["bron"] = {"dataset_id": _DATASET, "resource_id": _SCHEMA["resource_id"], "md5": md5}
    return df


def _get_duo_data(df: pd.DataFrame) -> dict:
    with patch.object(duo._duo, "load", return_value=df):
        return json.loads(duo.get_duo_data(_DATASET, 2))


def test_een_hernoemde_kolom_geeft_de_waarschuwing_in_het_resultaat(caplog):
    kolommen = [k if k != _KOLOMMEN[1] else "NIEUWE_NAAM" for k in _KOLOMMEN]
    with caplog.at_level(logging.WARNING, logger="tools.duo_laden"):
        uit = _get_duo_data(_geladen(kolommen, md5=None))
    assert "NIEUWE_NAAM" in uit["waarschuwing"]
    assert f"ontbreekt: {_KOLOMMEN[1]}" in uit["waarschuwing"]
    assert "DUO_SCHEMA_DRIFT dataset=p01hoinges" in caplog.text


def test_dezelfde_kolommen_geven_geen_waarschuwing(caplog):
    with caplog.at_level(logging.WARNING, logger="tools.duo_laden"):
        uit = _get_duo_data(_geladen(_KOLOMMEN, md5=None))
    assert "waarschuwing" not in uit
    assert "DUO_SCHEMA_DRIFT" not in caplog.text


def test_wie_het_bestand_uit_de_store_haalt_krijgt_dezelfde_waarschuwing():
    """De store is gedeeld: een tweede gesprek laadt niet opnieuw en moet de afwijking toch zien."""
    kolommen = [*_KOLOMMEN, "EXTRA"]
    eerste = _get_duo_data(_geladen(kolommen))
    with patch.object(duo._duo, "load", side_effect=AssertionError("niet opnieuw downloaden")):
        tweede = json.loads(duo.get_duo_data(_DATASET, 2))
    assert store.get(eerste["data_key"]) is not None
    assert tweede["waarschuwing"] == eerste["waarschuwing"]


# --- alleen de kopregel (voor de bron-ping, #869) ---------------------------------------------


def test_de_kopregel_leest_alleen_de_eerste_regel():
    body = b'"STUDIEJAAR","INSTELLINGSCODE_ACTUEEL"\r\n' + b"2024,21PB\r\n" * 50_000
    with nepserver(lambda pad: Antwoord(200, body, {"Content-Type": "text/csv"})) as bron:
        assert duo_laden.kolommen_uit_kop(f"{bron.url}/bestand.csv") == ["STUDIEJAAR", "INSTELLINGSCODE_ACTUEEL"]


def test_de_kopregel_valt_terug_op_cp1252(caplog):
    with caplog.at_level(logging.WARNING, logger="tools.duo_laden"):
        assert duo_laden.lees_kop("SCHOOLJAAR,ÉÉN_KOLOM\n1,2\n".encode("cp1252"), "x") == ["SCHOOLJAAR", "ÉÉN_KOLOM"]
    assert "DUO_ENCODING kopregel=x" in caplog.text
