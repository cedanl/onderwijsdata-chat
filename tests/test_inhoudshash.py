"""Een hash van de brontabel achter een publicatie (#715): in het manifest, het log en de CSV-kop."""

import hashlib
import logging

import pandas as pd
import pytest

from agent import manifest, publicatie
from tools import csv_export, store
from tools.inhoudshash import bronkey, hash_van, inhoudshash
from tools.store import KeyMeta

_BRON = pd.DataFrame({"JAAR": [2022, 2023], "AANTAL": [10, 12]})


def _rekenbaar(df: pd.DataFrame) -> str:
    """Zoals een onderzoeker hem narekent."""
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:12]


@pytest.fixture(autouse=True)
def _schone_store():
    store.clear()
    yield
    store.clear()


def _bron(key: str, bron: str, df: pd.DataFrame = _BRON) -> None:
    store.put(key, df, KeyMeta(bron=bron, dataset="x"))


def test_de_hash_is_na_te_rekenen_met_de_csv_vorm():
    assert inhoudshash(_BRON) == _rekenbaar(_BRON)
    assert len(inhoudshash(_BRON)) == 12


def test_dezelfde_data_geeft_dezelfde_hash_en_andere_data_een_andere():
    assert inhoudshash(_BRON) == inhoudshash(_BRON.copy())
    assert inhoudshash(_BRON) != inhoudshash(_BRON.assign(AANTAL=[10, 13]))


@pytest.mark.parametrize("bron", ["cbs", "rio"])
def test_cbs_en_rio_krijgen_een_hash(bron):
    _bron(f"{bron}:x", bron)

    assert hash_van(f"{bron}:x") == _rekenbaar(_BRON)


@pytest.mark.parametrize("bron", ["duo", "uwv", "roa"])
def test_duo_en_momentopnamen_krijgen_geen_eigen_hash(bron):
    _bron(f"{bron}:x", bron)

    assert hash_van(f"{bron}:x") is None


def test_een_afgeleide_key_geeft_de_hash_van_zijn_bron_niet_van_de_selectie():
    _bron("cbs:x", "cbs")
    store.derive("cbs:x", "cbs:x:sel", _BRON.head(1), stap="eerste rij")

    assert bronkey("cbs:x:sel") == "cbs:x"
    assert hash_van("cbs:x:sel") == _rekenbaar(_BRON)


def test_een_bron_die_uit_de_store_is_verdwenen_geeft_geen_hash_en_geen_fout(monkeypatch):
    _bron("cbs:x", "cbs")
    store.derive("cbs:x", "cbs:x:sel", _BRON.head(1))
    echte_get = store.get
    monkeypatch.setattr(store, "get", lambda key: None if key == "cbs:x" else echte_get(key))

    assert hash_van("cbs:x:sel") is None


def test_het_manifest_noemt_de_hash_per_dataset_zonder_dubbelen():
    _bron("cbs:x", "cbs")
    store.derive("cbs:x", "cbs:x:a", _BRON.head(1))
    store.derive("cbs:x", "cbs:x:b", _BRON.tail(1))

    (dataset,) = manifest._data_as_of(["cbs:x:a", "cbs:x:b"])

    assert dataset["inhoudshash"] == [_rekenbaar(_BRON)]


def test_het_manifest_noemt_geen_hash_bij_duo():
    _bron("duo:x:0", "duo")

    (dataset,) = manifest._data_as_of(["duo:x:0"])

    assert "inhoudshash" not in dataset


def test_de_gepubliceerd_regel_noemt_de_hash_van_een_bron_en_niet_van_een_selectie(caplog):
    _bron("cbs:x", "cbs")
    store.derive("cbs:x", "cbs:x:sel", _BRON.head(1))
    caplog.set_level(logging.INFO, logger="agent.publicatie")

    publicatie.log_publicatie(publicatie.ANTWOORD, ["cbs:x", "cbs:x:sel"])

    regel = next(r.getMessage() for r in caplog.records if "GEPUBLICEERD" in r.getMessage())
    assert regel.count("inhoudshash=") == 1
    assert f"key=cbs:x volledig=ja inhoudshash={_rekenbaar(_BRON)}" in regel


def test_de_csv_van_een_selectie_noemt_de_hash_van_de_brontabel():
    _bron("rio:x", "rio")
    store.derive("rio:x", "rio:x:sel", _BRON.head(1), stap="eerste rij")

    csv = csv_export.naar_csv("rio:x:sel")
    assert csv is not None
    kop = [r for r in csv.splitlines() if r.startswith("#")]

    assert any(f"inhoudshash van de brontabel: {_rekenbaar(_BRON)}" in r for r in kop), kop
