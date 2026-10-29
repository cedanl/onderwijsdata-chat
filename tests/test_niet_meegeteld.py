"""Wat een telling niet meetelt, bovenaan het antwoord, uit code (#743).

"Er zijn beslissingen genomen obv bron die niet helder zijn in [de] tekst. Voorbeeld is dat alle instroom wordt
gevraagd en dat na doorvragen blijkt dat de masters missen." De teldefinitie van p02ho1ejrs zei het wel, maar midden
in een DUO-alinea onder het antwoord. Nu staat het in één regel onder het Uitgangspunt.
"""

import importlib
import json

import pandas as pd
import pytest

from agent.niet_meegeteld import KOP, NIET_MEEGETELD, met_niet_meegeteld, regel
from tools import duo_meta, store
from tools.store import KeyMeta

# agent.run is ook de naam van een functie in agent/__init__.py.
run = importlib.import_module("agent.run")

# Per dataset de woorden uit de teldefinitie van DUO waar elke uitsluiting op rust: geen uitsluiting die DUO niet noemt.
_IN_DE_TELDEFINITIE = {
    "p01hoinges": ["hoofdinschrijvingen bepaald", "aangewezen instellingen worden niet meegeteld"],
    "p02ho1ejrs": [
        "die voor het eerst in het domein hoger onderwijs voorkomen",
        "master inschrijvingen in het hoger beroepsonderwijs zijn eveneens buiten beschouwing gelaten",
        "aangewezen instellingen worden niet meegeteld",
    ],
    "p04hogdipl": ["propedeuse diploma's, postinitiële diploma’s en diploma's behaald door uitwisselingsstudenten"],
}


def _stap(key: str, dataset: str, bron: str = "duo") -> str:
    store.put(key, pd.DataFrame({"STUDIEJAAR": [2025], "AANTAL": [345]}), KeyMeta(bron, dataset, resource=5))
    return json.dumps({"data_key": key, "rijen": [{"STUDIEJAAR": 2025, "AANTAL": 345}]})


def test_bij_eerstejaars_ho_staat_vooraan_dat_masters_niet_meetellen():
    tekst = met_niet_meegeteld("De HvA had 7.000 eerstejaars.", [_stap("duo:p02ho1ejrs:5:hva", "p02ho1ejrs")])

    eerste, rest = tekst.split("\n\n", 1)
    assert eerste.startswith(KOP) and "master" in eerste and "eerder in het hoger onderwijs" in eerste
    assert rest == "De HvA had 7.000 eerstejaars."


def test_twee_tellingen_noemen_elk_hun_bron():
    uit = regel([_stap("duo:p02ho1ejrs:5:a", "p02ho1ejrs"), _stap("duo:p01hoinges:3:b", "p01hoinges")])

    assert uit is not None and uit.count(": ") >= 2
    assert NIET_MEEGETELD["p02ho1ejrs"] in uit and NIET_MEEGETELD["p01hoinges"] in uit


@pytest.mark.parametrize(
    ("bron", "dataset"),
    [("duo", "p03hoinschr"), ("cbs", "85423NED"), ("duo", "mbo-studenten-per-instelling")],
)
def test_zonder_bekende_uitsluiting_geen_regel(bron, dataset):
    tekst = "Het waren er 345."
    assert met_niet_meegeteld(tekst, [_stap(f"{bron}:{dataset}:x", dataset, bron)]) == tekst


def test_zonder_data_of_zonder_tekst_geen_regel():
    assert met_niet_meegeteld("Hallo.", []) == "Hallo."
    assert met_niet_meegeteld("", [_stap("duo:p02ho1ejrs:5:c", "p02ho1ejrs")]) == ""


@pytest.mark.parametrize("dataset", sorted(NIET_MEEGETELD))
def test_elke_uitsluiting_staat_in_de_teldefinitie_van_duo(dataset):
    definitie = duo_meta.teldefinitie(duo_meta.record(dataset)) or ""
    for woorden in _IN_DE_TELDEFINITIE[dataset]:
        assert woorden in definitie, (dataset, woorden)


def test_de_regel_staat_onder_het_uitgangspunt_en_boven_het_antwoord(monkeypatch):
    monkeypatch.setattr(run, "met_uitgangspunt", lambda tekst, vraag, steps: f"**Uitgangspunt:** HvA\n\n{tekst}")
    monkeypatch.setattr(run, "interpretatie_bij", lambda *a, **k: None)
    stap = ("get_maat", _stap("duo:p02ho1ejrs:5:d", "p02ho1ejrs"))
    messages = [{"role": "user", "content": "Wat is de instroom van de HvA?"}]

    tekst = run._met_kopregels("Het waren er 7.000.", messages, {}, [stap])

    regels = tekst.split("\n\n")
    assert regels[0] == "**Uitgangspunt:** HvA"
    assert regels[1].startswith(KOP)
    assert regels[2] == "Het waren er 7.000."
