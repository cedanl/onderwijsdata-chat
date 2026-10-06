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


# Letterlijke formuleringen uit de testaudit van 2026-10-06 (L2) en audit 14 §3.3 (#396).
_HU = (
    "Er is geen beschikbare DUO-open-data-set die het totaal aantal hoofdinschrijvingen in het "
    "hoger beroepsonderwijs voor Hogeschool Utrecht publiceert."
)
_MBO = "De dataset mbo-studenten-per-instelling staat niet in de catalogus, dus ik kan dit niet beantwoorden."
_VO = "Het aantal leerlingen in havo-3 en vwo-3 is niet beschikbaar op provinciaal niveau."
_LEEG_FILTER = json.dumps(
    {
        "data_key": "cbs:85702NED:a",
        "rijen": [],
        "melding": "Het filter leverde 0 rijen op.",
        "suggesties": {"Onderwijssoort": ["A041922", "A041923"]},
    }
)


def test_hu_formulering_zonder_data_wordt_afgekeurd(monkeypatch):
    monkeypatch.setattr(beweringen.instelling, "noemt_instelling", lambda vraag: True)
    vraag = "Hoeveel hoofdinschrijvingen heeft Hogeschool Utrecht?"
    assert len(onbeschikbaar_zonder_zoekpad(vraag, _HU, [])) == 1


def test_dataset_uit_de_vraag_die_bestaat_mag_niet_ontkend_worden(monkeypatch):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: ["mbo-studenten-per-instelling"])
    vraag = "Hoeveel studenten heeft ROC Midden Nederland volgens mbo-studenten-per-instelling?"
    problemen = onbeschikbaar_zonder_zoekpad(vraag, _MBO, [])

    assert len(problemen) == 1
    assert "mbo-studenten-per-instelling" in problemen[0] and "get_duo_data" in problemen[0]


def test_dataset_uit_de_vraag_die_is_opgehaald_mag_een_afwezigheid_melden(monkeypatch):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: ["p01hoinges"])
    monkeypatch.setattr(beweringen, "geladen_datasets", lambda tool_results: {"p01hoinges"})
    assert onbeschikbaar_zonder_zoekpad("Wat zegt p01hoinges over Utrecht?", "Dat is niet beschikbaar.", _DATA) == []


def test_niet_beschikbaar_na_een_leeg_filter_is_een_selectieprobleem():
    problemen = onbeschikbaar_zonder_zoekpad("Hoeveel leerlingen havo-3 per provincie?", _VO, [_LEEG_FILTER])

    assert len(problemen) == 1
    assert "0 rijen" in problemen[0] and "A041922" in problemen[0]


def test_een_niet_ontsloten_bron_mag_niet_beschikbaar_heten(monkeypatch):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: ["roa-schoolverlaters"])
    details = json.dumps({"bron": "ROA", "opvraagbaar": False, "melding": "niet op te vragen"})
    assert (
        onbeschikbaar_zonder_zoekpad("Wat zegt roa-schoolverlaters?", "Niet beschikbaar via de chat.", [details]) == []
    )


@pytest.mark.parametrize(
    "tekst", [_HU, _MBO, _VO, "DUO publiceert geen cijfers per locatie.", "Die bron bestaat niet."]
)
def test_afwezigheidsformuleringen_worden_herkend(tekst):
    assert beweringen._ONBESCHIKBAAR.search(tekst)


@pytest.mark.parametrize("tekst", ["Er zijn 36.201 inschrijvingen.", "Geen enkele instelling groeide sneller."])
def test_gewone_zinnen_zijn_geen_afwezigheidsclaim(tekst):
    assert not beweringen._ONBESCHIKBAAR.search(tekst)
