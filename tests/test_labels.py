"""Kloppen de namen bij de getallen? (#196, Live-audit 8)

De getallen in de audit klopten; de woorden erbij niet: "Deeltijd (DU)" terwijl DU
duaal is, "Voltijds inschrijvingen" boven personen uit p01hoinges, en p01hoenges in
plaats van p01hoinges.
"""
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.labels import (
    onbekende_datasets,
    ongebruikte_bronnen,
    verkeerde_opleidingsvormen,
    verkeerde_teleenheid,
)
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


_BEKEND = patch("agent.labels.catalogus_titel", side_effect=lambda d: f"titel {d}")


def test_bron_die_bestaat_maar_niet_gebruikt_is_wordt_gemeld():
    """Audit 9: het antwoord noemde een bestaand ID dat niets met de bewering te maken had (#213)."""
    tekst = "In 2025 waren het 26.370 personen.\n\n**Bronnen**\n- DUO (**p03hoinschr**)\n"
    with _BEKEND:
        [probleem] = ongebruikte_bronnen(tekst, _beurt("duo:p01hoinges:3"))
    assert "p03hoinschr" in probleem


def test_bron_uit_deze_beurt_is_goed():
    tekst = "**Bronnen**\n- DUO (**p01hoinges**), CBS 85423NED\n\n**Definities**\n- p03hoinschr telt anders"
    store.derive("duo:p01hoinges:3", "query:1", pd.DataFrame({"AANTAL": [1]}))
    store.put("cbs:85423NED", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    with _BEKEND:
        assert ongebruikte_bronnen(tekst, _beurt("query:1", "cbs:85423NED")) == []


def test_id_als_context_buiten_de_bronnensectie_is_goed():
    tekst = "DUO publiceert ook p03hoinschr.\n\n**Bronnen**\n- DUO (**p01hoinges**)"
    with _BEKEND:
        assert ongebruikte_bronnen(tekst, _beurt("duo:p01hoinges:3")) == []


def test_niet_bestaande_bron_meldt_alleen_onbekende_datasets():
    tekst = "**Bronnen**\n- DUO (**p01hoenges**)"
    with patch("agent.labels.catalogus_titel", side_effect=lambda d: d):
        assert ongebruikte_bronnen(tekst, _beurt("duo:p01hoinges:3")) == []


def test_zonder_data_in_de_beurt_geen_melding():
    # Een vervolgvraag mag de bron van een eerdere beurt noemen.
    with _BEKEND:
        assert ongebruikte_bronnen("**Bronnen**\n- DUO (**p03hoinschr**)", []) == []


# --- teleenheid ---

def test_inschrijvingen_boven_personen_is_verkeerd():
    [probleem] = verkeerde_teleenheid("Voltijds inschrijvingen HU 2021–2025", _beurt("duo:p01hoinges:3"))
    assert "personen" in probleem and "p01hoinges" in probleem


def test_personen_boven_inschrijvingen_is_verkeerd():
    assert verkeerde_teleenheid("In 2025 waren het 28.889 personen.", _beurt("duo:p03hoinschr:3"))


def test_hoofdinschrijvingen_bij_personen_is_goed():
    # p01 telt hoofdinschrijvingen als personen; dat woord hoort erbij.
    assert verkeerde_teleenheid("Geteld als hoofdinschrijvingen.", _beurt("duo:p01hoinges:3")) == []


@pytest.mark.parametrize("tekst", [
    "Het zijn geen inschrijvingen maar personen.",
    "Het gaat hier niet om inschrijvingen maar om personen.",
    "p01 telt personen, niet inschrijvingen. In 2025 waren het 24.169 personen.",
])
def test_ontkenning_van_het_verkeerde_woord_is_toelichting(tekst):
    # #214: een correcte weerlegging kreeg de waarschuwing toch.
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3")) == []


@pytest.mark.parametrize("tekst", [
    # Audit 10: letterlijke DUO-tekst, ontkenning ná het woord.
    "De inschrijvingen behorende bij opleidingen aan aangewezen instellingen worden niet meegeteld.",
    "Inschrijvingen bij aangewezen instellingen worden niet meegeteld, en masters evenmin.",
    "Inschrijvingen aan aangewezen instellingen blijven buiten beschouwing.",
])
def test_uitsluiting_na_het_woord_is_toelichting(tekst):
    # #239: #214 keek alleen vóór het woord.
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3")) == []


def test_citaat_van_de_teldefinitie_is_geen_toeschrijving():
    # #239: wie de DUO-definitie letterlijk aanhaalt, gebruikt de teleenheid goed.
    tekst = "In 2025 waren het 26.370 personen. DUO: van alle inschrijvingen op de peildatum 1 oktober worden de hoofdinschrijvingen bepaald."
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3")) == []


def test_naast_een_citaat_blijft_een_toeschrijving_een_probleem():
    tekst = "In 2025 waren het 26.370 inschrijvingen. Van alle inschrijvingen op de peildatum 1 oktober worden de hoofdinschrijvingen bepaald."
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3"))


@pytest.mark.parametrize("tekst", [
    "p01 telt hier 24.169 inschrijvingen.",
    "Dat zijn geen cijfers van vorig jaar. p01 telt hier 24.169 inschrijvingen.",
    "Het zijn niet personen maar inschrijvingen.",
    "Er waren 24.169 inschrijvingen, masters niet meegeteld.",  # de uitsluiting hoort bij een andere bijzin
])
def test_toeschrijving_van_het_verkeerde_woord_blijft_een_probleem(tekst):
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3"))


def test_vergelijking_van_beide_teleenheden_is_goed():
    tekst = "26.370 personen tegenover 28.889 inschrijvingen."
    assert verkeerde_teleenheid(tekst, _beurt("duo:p01hoinges:3", "duo:p03hoinschr:3")) == []


def test_afgeleide_key_erft_de_teleenheid():
    store.derive("duo:p01hoinges:3", "duo:p01hoinges:3:abc", pd.DataFrame({"AANTAL": [26370]}))
    assert verkeerde_teleenheid("Voltijdinschrijvingen", _beurt("duo:p01hoinges:3:abc"))
