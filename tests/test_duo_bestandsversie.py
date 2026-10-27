"""De versie en de md5 van een geladen DUO-bestand (#717): uit df.attrs["bron"] van riodata naar de bronregel, het
manifest, de logregel GEPUBLICEERD en de CSV-kop. Zonder die velden (datastore-dump, oudere riodata) geen fout."""

import json
import logging
from unittest.mock import patch

import pandas as pd
import pytest

from agent import figuurbron, manifest, publicatie
from tools import bestandsversie, csv_export, duo, store

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

MD5 = "5200c7c449dc0b95f786ed7cfcfca542"
BESTAND = {
    "dataset_id": "p01hoinges",
    "resource_id": "7761bd6a-b87b-4389-a943-829872116f92",
    "last_modified": "2026-04-08T12:51:36.650779",
    "hash": MD5,
    "etag": '"1775652696.7191002-782095-2030899828"',
    "md5": MD5,
}


@pytest.fixture(autouse=True)
def _schone_store():
    store.clear()
    yield
    store.clear()


def _laad(attrs: dict | None) -> str:
    """get_duo_data met een nagebootste riodata-load; geeft de data_key."""
    df = pd.DataFrame({"STUDIEJAAR": [2024, 2025], "AANTAL_INGESCHREVENEN": [10, 12]})
    if attrs is not None:
        df.attrs["bron"] = attrs
    with patch.object(duo._duo, "load", return_value=df):
        return json.loads(duo.get_duo_data("p01hoinges", 2))["data_key"]


def _meta(key: str) -> store.KeyMeta:
    known = store.meta(key)
    assert known is not None
    return known


@pytest.mark.parametrize(
    ("waarde", "verwacht"),
    [
        ("2026-04-08T12:51:36.650779", "versie van 08-04-2026"),
        ("2026-07-10T11:34:51", "versie van 10-07-2026"),
        (None, None),
        ("", None),
        ("gisteren", None),
        (20260408, None),
    ],
)
def test_peilmoment_is_de_dag_waarop_duo_het_bestand_verving(waarde, verwacht):
    assert bestandsversie.peilmoment({"last_modified": waarde}) == verwacht


@pytest.mark.parametrize("waarde", [None, "", "abc", MD5.upper(), MD5 + "0", "z" * 32])
def test_bronhash_is_alleen_een_md5(waarde):
    assert bestandsversie.bronhash({"md5": waarde}) is None


def test_get_duo_data_legt_versie_en_md5_vast_ook_op_een_selectie():
    key = _laad(BESTAND)
    known = _meta(key)
    assert known.peilmoment == "versie van 08-04-2026"
    assert known.bronhash == MD5

    store.derive(key, f"{key}:sel", store.get(key).head(1), stap="eerste rij")
    afgeleid = _meta(f"{key}:sel")
    assert (afgeleid.peilmoment, afgeleid.bronhash) == ("versie van 08-04-2026", MD5)


@pytest.mark.parametrize(
    ("attrs", "bronhash"),
    [
        (None, None),  # geen attrs
        ({"dataset_id": "p01hoinges", "schema_sha256": None}, None),  # riodata vóór 0.7.0
        ({**BESTAND, "last_modified": None, "hash": None, "etag": None}, MD5),  # datastore-dump: alleen md5
    ],
)
def test_een_dump_of_oudere_riodata_geeft_geen_versie_en_geen_fout(attrs, bronhash):
    known = _meta(_laad(attrs))
    assert known.peilmoment is None
    assert known.bronhash == bronhash


def test_de_bronregel_noemt_de_versie_van_het_bestand():
    key = _laad(BESTAND)
    regel = figuurbron.figuurbron(key)
    assert regel is not None
    assert "versie van 08-04-2026" in regel["tekst"]


def test_het_manifest_noemt_versie_en_md5_per_dataset():
    key = _laad(BESTAND)
    store.derive(key, f"{key}:sel", store.get(key).head(1))

    (dataset,) = manifest._data_as_of([key, f"{key}:sel"])

    assert dataset["peilmoment"] == "versie van 08-04-2026"
    assert dataset["bronhash"] == [MD5]
    assert "inhoudshash" not in dataset, "DUO heeft de md5 van de bron, geen eigen hash (#715)"


def test_de_gepubliceerd_regel_noemt_de_md5_bij_de_bron(caplog):
    key = _laad(BESTAND)
    store.derive(key, f"{key}:sel", store.get(key).head(1))
    caplog.set_level(logging.INFO, logger="agent.publicatie")

    publicatie.log_publicatie(publicatie.ANTWOORD, [key, f"{key}:sel"])

    regel = next(r.getMessage() for r in caplog.records if "GEPUBLICEERD" in r.getMessage())
    assert regel.count("bronhash=") == 1
    assert f"key={key} volledig=ja bronhash={MD5}" in regel


def test_de_csv_noemt_de_md5_van_het_bestand():
    key = _laad(BESTAND)
    store.derive(key, f"{key}:sel", store.get(key).head(1), stap="eerste rij")

    csv = csv_export.naar_csv(f"{key}:sel")
    assert csv is not None
    kop = [r for r in csv.splitlines() if r.startswith("#")]

    assert any(f"md5 van het DUO-bestand: {MD5}" in r for r in kop), kop
    assert not any("inhoudshash" in r for r in kop)
