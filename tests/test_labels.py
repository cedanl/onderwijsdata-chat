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
    [probleem] = verkeerde_opleidingsvormen("Reikwijdte: Deeltijd (DU), 2021–2025.", _beurt("duo:p01hoinges:3"))
    assert "DU" in probleem and "duaal" in probleem and "DT" in probleem


def test_code_gevolgd_door_verkeerde_uitleg():
    assert verkeerde_opleidingsvormen("DT = duaal onderwijs", _beurt("duo:p01hoinges:3"))


def test_juiste_codes_zijn_goed():
    assert (
        verkeerde_opleidingsvormen(
            "Voltijd (VT), deeltijd (DT) en duaal (DU); DT = deeltijd.", _beurt("duo:p01hoinges:3")
        )
        == []
    )


def test_codes_buiten_de_ho_datasets_worden_niet_gecontroleerd():
    # mbo_opleidingsaanbod kent KLASSIKAAL/COACHING, geen VT/DT/DU (#371).
    store.put(
        "duo:mbo_opleidingsaanbod:0",
        pd.DataFrame({"OPLEIDINGSVORM": ["KLASSIKAAL"]}),
        KeyMeta(bron="duo", dataset="mbo_opleidingsaanbod"),
    )
    assert verkeerde_opleidingsvormen("DT = duaal onderwijs", _beurt("duo:mbo_opleidingsaanbod:0")) == []
    assert verkeerde_opleidingsvormen("DT = duaal onderwijs", []) == []


# --- dataset-ID ---


def test_dataset_id_dat_niet_in_de_catalogus_staat():
    with patch("agent.labels.catalogus_titel", side_effect=lambda d: "Ingeschrevenen" if d == "p01hoinges" else d):
        [probleem] = onbekende_datasets("Bron: DUO p01hoenges, resource 3.")
    assert "p01hoenges" in probleem


def test_bekende_dataset_ids_zijn_goed():
    with patch("agent.labels.catalogus_titel", side_effect=lambda d: f"titel {d}"):
        assert onbekende_datasets("Bronnen: p01hoinges en CBS 85423NED.") == []


_BEKEND = patch("agent.labels.catalogus_titel", side_effect=lambda d: f"titel {d}")
# Alleen p01hoinges en 85354NED staan in de catalogus: wat daarbuiten staat, bestaat niet.
_ALLEEN_ECHTE = patch(
    "agent.labels.catalogus_titel", side_effect=lambda d: f"titel {d}" if d in {"p01hoinges", "85354NED"} else d
)


def test_melding_noemt_een_id_met_streepje_zoals_het_in_de_tekst_staat():
    """#1085: de regex stopte bij het streepje en meldde "p09mbo" in plaats van "p09mbo-fantasie"."""
    with _ALLEEN_ECHTE:
        [probleem] = onbekende_datasets("Zie ook DUO-bestand p09mbo-fantasie.")
    assert probleem.melding == "Dataset p09mbo-fantasie bestaat niet in de catalogus."


@pytest.mark.parametrize("tekst", ["Bron: p01hoinges, resource 3.", "(zie p01hoinges).", "Bron: p01hoinges."])
def test_een_echt_id_met_leesteken_erachter_geeft_geen_melding(tekst):
    with _ALLEEN_ECHTE:
        assert onbekende_datasets(tekst) == []


def test_een_echt_id_met_een_streepje_en_een_woord_erachter_is_het_echte_id():
    with _ALLEEN_ECHTE:
        assert onbekende_datasets("Het p01hoinges-bestand van DUO.") == []


def test_een_echt_id_met_een_streepje_in_de_bronnensectie_is_het_echte_id():
    tekst = "**Bronnen**\n- DUO (p01hoinges-bestand)"
    with _ALLEEN_ECHTE:
        assert ongebruikte_bronnen(tekst, _beurt("duo:p01hoinges:3")) == []


_NIET_GEVONDEN = json.dumps({"fout": "Dataset '99999NED' staat niet in de catalogus. Zoek met search_catalog."})


def test_een_id_uit_de_vraag_geeft_geen_melding():
    """#1088: het antwoord zegt terecht dat de tabel van de gebruiker niet bestaat."""
    with _ALLEEN_ECHTE:
        assert (
            onbekende_datasets("CBS-tabel 99999NED staat niet in de catalogus.", "Wat staat in tabel 99999NED?") == []
        )


def test_een_id_uit_een_toolresultaat_geeft_geen_melding():
    with _ALLEEN_ECHTE:
        assert onbekende_datasets("CBS-tabel 99999NED staat niet in de catalogus.", _NIET_GEVONDEN) == []


def test_een_id_in_andere_hoofdletters_uit_de_vraag_geeft_geen_melding():
    with _ALLEEN_ECHTE:
        assert onbekende_datasets("Tabel 99999NED bestaat niet.", "wat staat er in 99999ned?") == []


def test_een_verzonnen_id_buiten_vraag_en_toolresultaat_wordt_nog_steeds_gemeld():
    with _ALLEEN_ECHTE:
        [probleem] = onbekende_datasets(
            "Volgens CBS-tabel 85999NED telde het mbo 475.550 studenten.", "Hoeveel mbo-studenten?\n" + _NIET_GEVONDEN
        )
    assert "85999NED" in probleem.melding


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
