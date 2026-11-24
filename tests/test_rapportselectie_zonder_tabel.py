"""Een beurt met alleen een bron zonder tabel in de store telt in de checklist van het rapport (#1077).

`get_mbo_indicatoren` legt niets in de store: er is geen key die de beurt aan haar data bindt. Het bewijs (het
toolresultaat) draagt daarom het nummer van de vraag waarbij het ontstond. Het gesprek hieronder heeft:
1. de DUO-inschrijvingen (key `_UU`);
2. de diplomaresultaten van een roc (`get_mbo_indicatoren`, geen key);
3. een bedankje, zonder data.
"""

import json

import pytest

from agent import beurtbewijs, rapportselectie
from agent.rapportselectie import Keuze, beperk, beurten_met_data, kies
from agent.session_data import gebruikersvragen, record_rekenbewijs, rekenbewijs
from core.errors import Gebruikersfout
from tests.test_rapportselectie import _LAAD_UU, _UU, _antwoord, _frame, _laad, _vraag
from tests.test_rekenbewijs import _MBO, _MBO_CALL
from tools import store
from tools.store import KeyMeta

_V1 = "Hoeveel studenten heeft de UU?"
_V2 = "Hoe doen wij het qua diplomaresultaat vergeleken met de andere roc's?"
_V3 = "Dank!"
_MBO_BRON = "DUO · Indicatoren per instelling (jaardocument mbo), editie 2026, peildatum 1 oktober 2025"


@pytest.fixture
def sessie():
    store.put(_UU, _frame(300), KeyMeta("duo", "p01hoinges", resource=3))
    s: dict = {"username": "tester"}
    _vraag(s, _V1)
    _laad(s, _UU, _LAAD_UU)
    _antwoord(s, "Zie de tabel.")
    _vraag(s, _V2)
    record_rekenbewijs(s, _MBO, _MBO_CALL)
    _antwoord(s, "Het diplomaresultaat is 70,6%.")
    _vraag(s, _V3)
    _antwoord(s, "Graag gedaan.")
    return s


def test_de_checklist_toont_de_beurt_met_alleen_de_mbo_indicatoren_met_haar_bron(sessie):
    items = beurten_met_data(sessie)

    assert [i["beurt"] for i in items] == [1, 2]
    assert items[1] == {"beurt": 2, "vraag": _V2, "bronnen": [_MBO_BRON], "bouwt_voort_op": [], "figuren": []}


def test_een_beurt_met_een_key_en_de_mbo_indicatoren_noemt_beide_bronnen(sessie):
    _laad(sessie, "duo:p01hoinges:3:b", _LAAD_UU)
    store.put("duo:p01hoinges:3:b", _frame(10), KeyMeta("duo", "p01hoinges", resource=3))
    sessie["data_vraag"]["duo:p01hoinges:3:b"] = 2

    [_, tweede] = beurten_met_data(sessie)

    assert _MBO_BRON in tweede["bronnen"] and any("p01hoinges" in b for b in tweede["bronnen"])


def test_zonder_enige_key_geen_checklist(sessie):
    sessie["data_keys"], sessie["data_vraag"] = [], {}

    assert beurten_met_data(sessie) == []


def test_de_beurt_kan_worden_gekozen_en_afgewezen(sessie):
    assert kies(sessie, [1, 2]) == Keuze(None, ())
    assert kies(sessie, [2, 1]) == Keuze(None, ())
    assert kies(sessie, [1]) == Keuze(frozenset({1}))


def test_het_bewijs_van_een_gekozen_beurt_gaat_mee_en_dat_van_een_uitgezette_niet(sessie):
    mee = beperk(sessie, frozenset({1, 2}))
    zonder = beperk(sessie, frozenset({1}))

    assert [b["tool"] for b in rekenbewijs(mee)] == ["get_mbo_indicatoren"]
    assert rekenbewijs(zonder) == []
    assert _V2 not in json.dumps(zonder) and "Indicatoren" not in json.dumps(zonder)


def test_de_weergave_van_alleen_de_mbo_beurt_nummert_de_vragen_opnieuw(sessie):
    uitgave = beperk(sessie, frozenset({2}))

    assert gebruikersvragen(uitgave) == [_V2, _V3]
    assert uitgave["data_keys"] == []
    assert [b["vraag"] for b in rekenbewijs(uitgave)] == [1]


def test_een_item_zonder_geldig_nummer_hoort_bij_geen_beurt_en_gaat_niet_mee(sessie):
    sessie["rekenbewijs"][0].pop("vraag")

    assert [i["beurt"] for i in beurten_met_data(sessie)] == [1]
    assert rekenbewijs(beperk(sessie, frozenset({1}))) == []


def test_een_selectie_met_een_onbekende_beurt_wordt_geweigerd_ook_met_bewijs_zonder_tabel(sessie):
    with pytest.raises(Gebruikersfout, match=rapportselectie.VEROUDERDE_SELECTIE):
        kies(sessie, [1, 3])


# ── Heropenen ─────────────────────────────────────────────────────────────────


def test_heropenen_nummert_het_bewijs_zonder_tabel_naar_de_plaats_van_het_antwoord(sessie):
    """De geschiedenis kan korter zijn dan het gesprek: het nummer volgt de plaats van het antwoord, zoals data_vraag."""
    [item] = rekenbewijs(sessie)
    rij = {"lineage": {}, "rekenbewijs": [{**item, "vraag": 7}], "created_at": "t"}
    verse: dict = {
        "messages": [{"role": "user", "content": _V2}, {"role": "assistant", "content": "Het diplomaresultaat."}]
    }

    beurtbewijs.zet_terug(verse, {beurtbewijs.tekst_hash("Het diplomaresultaat."): rij})

    assert [b["vraag"] for b in rekenbewijs(verse)] == [1]


def test_heropenen_laat_het_nummer_weg_als_het_antwoord_de_geschiedenis_niet_haalt(sessie):
    [item] = rekenbewijs(sessie)
    rij = {"lineage": {}, "rekenbewijs": [{**item, "vraag": 7}], "created_at": "t"}
    verse: dict = {"messages": [{"role": "user", "content": "Iets anders"}, {"role": "assistant", "content": "Ja."}]}

    beurtbewijs.zet_terug(verse, {beurtbewijs.tekst_hash("Eerder antwoord."): rij})

    [terug] = rekenbewijs(verse)
    assert "vraag" not in terug and terug["tool"] == "get_mbo_indicatoren"
