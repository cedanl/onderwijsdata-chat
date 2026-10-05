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
)
from tools import store
from tools.store import KeyMeta

_PERSONEN = "Ingeschrevenen: van alle inschrijvingen op de peildatum 1 oktober worden de hoofdinschrijvingen bepaald."
_INSCHRIJVINGEN = "Inschrijvingen: voor de inschrijvingen op de peildatum 1 oktober worden zowel de hoofd- als ..."


@pytest.fixture(autouse=True)
def _keys():
    store.clear()
    store.put(
        "duo:p01hoinges:3",
        pd.DataFrame({"AANTAL": [26370]}),
        KeyMeta(bron="duo", dataset="p01hoinges", teldefinitie=_PERSONEN),
    )
    store.put(
        "duo:p03hoinschr:3",
        pd.DataFrame({"AANTAL": [28889]}),
        KeyMeta(bron="duo", dataset="p03hoinschr", teldefinitie=_INSCHRIJVINGEN),
    )
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
