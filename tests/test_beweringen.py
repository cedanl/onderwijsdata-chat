"""Een "niet beschikbaar"- of oorzaakclaim zonder dekking wordt teruggestuurd (#323, #225)."""

import json

import pytest

from agent import beweringen
from agent.beweringen import onbeschikbaar_zonder_zoekpad, ongedekte_oorzaak
from agent.probleem import meldingen

_DATA = [json.dumps({"data_key": "duo:p01hoinges:a", "rijen": []})]


@pytest.fixture(autouse=True)
def _instelling(monkeypatch):
    monkeypatch.setattr(beweringen.instelling, "noemt_instelling", lambda vraag: "delft" in vraag.lower())


def test_niet_beschikbaar_bij_instellingsvraag_zonder_data_wordt_afgekeurd():
    problemen = onbeschikbaar_zonder_zoekpad(
        "Hoeveel studenten heeft TU Delft?", "Er is geen dataset per instelling; exact aantal niet beschikbaar.", []
    )
    assert len(problemen) == 1 and "p01hoinges" in problemen[0]
    assert "p01hoinges" not in meldingen(problemen)[0]


def test_niet_beschikbaar_na_opgehaalde_data_blijft_toegestaan():
    assert onbeschikbaar_zonder_zoekpad("Hoeveel studenten heeft TU Delft?", "Dat is niet beschikbaar.", _DATA) == []


def test_vraag_zonder_instelling_mag_niet_via_de_chat_zeggen():
    assert (
        onbeschikbaar_zonder_zoekpad("Wat verdienen afgestudeerden bij ROA?", "Niet beschikbaar via de chat.", []) == []
    )


def test_oorzaak_zonder_voorbehoud_wordt_afgekeurd():
    tekst = "Het verschil is 571.\n\nDit komt doordat studenten meerdere opleidingen volgen."
    problemen = ongedekte_oorzaak(tekst, _DATA)
    assert len(problemen) == 1
    assert "meerdere opleidingen" in problemen[0] and "meerdere opleidingen" not in meldingen(problemen)[0]


def test_oorzaak_met_voorbehoud_is_eerlijk():
    tekst = "Het verschil is 571. De oorzaak is met deze gegevens niet vast te stellen."
    assert ongedekte_oorzaak(tekst, _DATA) == []


def test_zonder_data_zwijgt_de_oorzaakcontrole():
    assert ongedekte_oorzaak("Dat komt doordat het beleid veranderde.", []) == []
