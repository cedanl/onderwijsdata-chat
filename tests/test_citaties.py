"""Gecontroleerde getallen linken naar de toolstap waar ze vandaan komen (#365)."""

import json

from agent.citaties import citaties

_CBS = json.dumps({"data_key": "cbs:1", "bron": "CBS 85423NED", "rijen": [{"Totaal": 378490}]})
_DUO = json.dumps({"data_key": "duo:2", "bron": "DUO", "rijen": [{"aantal": 27135}]})
_BRONLOOS = json.dumps({"bron": None, "waarde": 55555})


def test_getal_krijgt_de_eerste_stap_waarin_het_staat():
    steps = [("get_cbs_data", _CBS), ("get_duo_data", _DUO)]
    result = citaties("Er zijn 378.490 en 27.135 studenten.", steps)
    assert [(c["getal"], c["tool"], c["data_key"]) for c in result] == [
        ("378.490", "get_cbs_data", "cbs:1"),
        ("27.135", "get_duo_data", "duo:2"),
    ]


def test_ongecontroleerd_getal_krijgt_geen_citatie():
    assert citaties("Het waren 99.999 studenten.", [("get_cbs_data", _CBS)]) == []


def test_bronloos_resultaat_is_geen_bewijs():
    assert citaties("Het waren 55.555 studenten.", [("run_analysis", _BRONLOOS)]) == []


def test_jaartallen_en_kleine_getallen_krijgen_er_geen():
    assert citaties("In 2024 waren er 12 van 378490.", [("get_cbs_data", _CBS)])[0]["getal"] == "378490"


def test_zelfde_getal_twee_keer_geeft_een_citatie():
    assert len(citaties("378.490 is 378.490.", [("get_cbs_data", _CBS)])) == 1
