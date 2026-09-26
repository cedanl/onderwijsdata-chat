"""Kloppen de namen bij de getallen? (#196, Live-audit 8)

De getallen in de audit klopten; de woorden erbij niet: "Deeltijd (DU)" terwijl DU
duaal is, "Voltijds inschrijvingen" boven personen uit p01hoinges, en p01hoenges in
plaats van p01hoinges.
"""
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.labels import onbekende_datasets, verkeerde_opleidingsvormen, verkeerde_teleenheid
from tools import store
from tools.store import KeyMeta

_PERSONEN = "Ingeschrevenen: van alle inschrijvingen op de peildatum 1 oktober worden de hoofdinschrijvingen bepaald."
_INSCHRIJVINGEN = "Inschrijvingen: voor de inschrijvingen op de peildatum 1 oktober worden zowel de hoofd- als ..."


@pytest.fixture(autouse=True)
def _keys():
    store.clear()
    store.put("duo:p01hoinges:3", pd.DataFrame({"AANTAL": [26370]}),
              KeyMeta(bron="duo", dataset="p01hoinges", teldefinitie=_PERSONEN))
    store.put("duo:p03hoinschr:3", pd.DataFrame({"AANTAL": [28889]}),
              KeyMeta(bron="duo", dataset="p03hoinschr", teldefinitie=_INSCHRIJVINGEN))
    yield
    store.clear()


def _beurt(*keys: str) -> list[str]:
    return [json.dumps({"data_key": k}) for k in keys]


# --- opleidingsvorm ---

def test_deeltijd_met_code_du_is_verkeerd():
    [probleem] = verkeerde_opleidingsvormen("Reikwijdte: Deeltijd (DU), 2021–2025.")
    assert "DU" in probleem and "duaal" in probleem and "DT" in probleem


def test_code_gevolgd_door_verkeerde_uitleg():
    assert verkeerde_opleidingsvormen("DT = duaal onderwijs")


def test_juiste_codes_zijn_goed():
    assert verkeerde_opleidingsvormen("Voltijd (VT), deeltijd (DT) en duaal (DU); DT = deeltijd.") == []


# --- dataset-ID ---

def test_dataset_id_dat_niet_in_de_catalogus_staat():
    with patch("agent.labels.catalogus_titel", side_effect=lambda d: "Ingeschrevenen" if d == "p01hoinges" else d):
        [probleem] = onbekende_datasets("Bron: DUO p01hoenges, resource 3.")
    assert "p01hoenges" in probleem


def test_bekende_dataset_ids_zijn_goed():
    with patch("agent.labels.catalogus_titel", side_effect=lambda d: f"titel {d}"):
        assert onbekende_datasets("Bronnen: p01hoinges en CBS 85423NED.") == []


# --- teleenheid ---

def test_inschrijvingen_boven_personen_is_verkeerd():
    [probleem] = verkeerde_teleenheid("Voltijds inschrijvingen HU 2021–2025", _beurt("duo:p01hoinges:3"))
    assert "personen" in probleem and "p01hoinges" in probleem


def test_personen_boven_inschrijvingen_is_verkeerd():
    assert verkeerde_teleenheid("In 2025 waren het 28.889 personen.", _beurt("duo:p03hoinschr:3"))


def test_hoofdinschrijvingen_bij_personen_is_goed():
    # p01 telt hoofdinschrijvingen als personen; dat woord hoort erbij.
    assert verkeerde_teleenheid("Geteld als hoofdinschrijvingen.", _beurt("duo:p01hoinges:3")) == []


def test_vergelijking_van_beide_teleenheden_is_goed():
    tekst = "26.370 personen tegenover 28.889 inschrijvingen."
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3", "duo:p03hoinschr:3")) == []


def test_afgeleide_key_erft_de_teleenheid():
    store.derive("duo:p01hoinges:3", "duo:p01hoinges:3:abc", pd.DataFrame({"AANTAL": [26370]}))
    assert verkeerde_teleenheid("Voltijdinschrijvingen", _beurt("duo:p01hoinges:3:abc"))
