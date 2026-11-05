"""De caches van de dashboards: geen fout of onvolledige lading erin, en na de TTL opnieuw van de bron (#901).

De klok staat stil: `actualiteit.nu` wordt verzet, niet afgewacht.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from core import actualiteit
from data import arbeidsmarkt

_START = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


@pytest.fixture
def klok(monkeypatch):
    moment = [_START]
    monkeypatch.setattr(actualiteit, "nu", lambda: moment[0])

    def verzet(**delta):
        moment[0] += timedelta(**delta)

    return verzet


@pytest.fixture(autouse=True)
def lege_caches():
    def leeg():
        for module in (dashboard, arbeidsmarkt):
            for functie in vars(module).values():
                if hasattr(functie, "cache_clear"):
                    functie.cache_clear()

    leeg()
    yield
    leeg()


def _instromend(jaar: int) -> pd.DataFrame:
    return pd.DataFrame({"JAAR": [jaar], "INSTELLINGSCODE": ["25LH"], "INSTROOM MBO": ["J"], "AANTAL": [10]})


def test_een_ontbrekende_instroompartitie_geeft_een_fout_en_geen_onvolledige_cache(klok):
    # Eerder slikte de lader de fout per partitie: drie van de vier jaren, tot de pod herstartte.
    storing = {5}

    def load(dataset_id, resource=0, **kwargs):
        if resource in storing:
            raise ConnectionError("DUO onbereikbaar")
        return _instromend(2020 + resource)

    with patch.object(dashboard.duo, "load", side_effect=load):
        with pytest.raises(ConnectionError):
            dashboard._load_instromende_mbo_historisch()
        storing.clear()
        jaren = dashboard._load_instromende_mbo_historisch()["JAAR"].tolist()

    assert jaren == [2020 + i for i in dashboard._INSTROMENDE_MBO_HISTORISCH]


def test_de_duo_ladingen_verlopen_na_de_ttl(klok):
    versie = [2024]

    def load(dataset_id, resource=0, **kwargs):
        return pd.DataFrame({"JAAR": [versie[0]], "INSTELLINGSNAAM": ["ROC"]})

    with patch.object(dashboard.duo, "load", side_effect=load):
        assert dashboard._load_mbo_studenten()["JAAR"].tolist() == [2024]
        versie[0] = 2025
        klok(hours=23)
        assert dashboard._load_mbo_studenten()["JAAR"].tolist() == [2024]
        klok(hours=1)
        assert dashboard._load_mbo_studenten()["JAAR"].tolist() == [2025]


_ROA = pd.DataFrame(
    [
        {
            "regionaam": "Nederland",
            "thema": "Risicoindicatoren en arbeidsmarktprognoses tot 2030",
            "aggregatieniveau": "opleidingsniveau (ONR2019)",
            "detailniveau": "Mbo4",
            "onderwerp": "ITA toekomstige arbeidsmarktsituatie in 2030",
            "perc": None,
            "aantal": None,
            "typering": "redelijk",
            "versie": "2024",
        }
    ]
)


def test_roa_na_een_storing_geeft_bij_herstel_weer_data(klok):
    # functools.cache op _roa_prognose hield de `{}` van één storing tot de herstart.
    with patch("riodata.roa.load", side_effect=ConnectionError("ROA onbereikbaar")):
        assert dashboard._roa_prognose("mbo") == {}
    with patch("riodata.roa.load", return_value=_ROA):
        assert dashboard._roa_prognose("mbo") == {"Mbo4": {"ITA toekomstige arbeidsmarktsituatie in 2030": "redelijk"}}


def test_uwv_en_roa_verlopen_na_de_ttl(klok):
    with patch("riodata.roa.load", return_value=_ROA) as roa:
        arbeidsmarkt.roa_versie()
        klok(hours=23)
        arbeidsmarkt.roa_versie()
        assert roa.call_count == 1
        klok(hours=1)
        arbeidsmarkt.roa_versie()
        assert roa.call_count == 2
