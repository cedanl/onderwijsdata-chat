"""Een "niet beschikbaar"- of oorzaakclaim zonder dekking wordt teruggestuurd (#323, #225)."""

import json

import pandas as pd
import pytest

from agent import beweringen
from agent.beweringen import onbeschikbaar_zonder_zoekpad, ongedekte_oorzaak
from agent.probleem import meldingen
from tools import store
from tools.store import KeyMeta

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


# Formuleringen uit de antwoorden van 6 t/m 16 oktober waarop de regel onterecht afging: het voorbehoud stond
# er wel, in andere woorden (#619).
@pytest.mark.parametrize(
    "voorbehoud",
    [
        "**Mogelijke verklaring:** de data laat de oorzaak niet zien. Het verschil komt doordat studenten kiezen.",
        "Dit komt doordat studenten kiezen. Dit zijn vermoedens, de data toont de oorzaak niet.",
        "Het is denkbaar dat dit komt doordat studenten verhuizen.",
        "Dit zou kunnen samenhangen met het aantal opleidingen; het verschil komt mede door de instroom.",
        "Het verschil komt doordat studenten kiezen, maar dat is een vermoeden.",
        "De oorzaak is niet uit de data te halen.",
    ],
)
def test_oorzaak_met_voorbehoud_in_andere_woorden_is_eerlijk(voorbehoud):
    assert ongedekte_oorzaak(f"Het verschil is 571. {voorbehoud}", _DATA) == []


def test_oorzaak_naast_een_voorbehoud_in_een_andere_alinea_blijft_ongedekt():
    tekst = "Dit komt doordat studenten kiezen.\n\nOver de reden zijn alleen vermoedens bij andere opleidingen."
    assert len(ongedekte_oorzaak(tekst, _DATA)) == 1


def test_de_herhaalde_onderzoeksvraag_is_geen_bewering_van_het_model():
    tekst = "**Onderzoeksvraag:** Is het verschil te verklaren uit de locatie van de opleiding?\n\nHet verschil is 571."
    assert ongedekte_oorzaak(tekst, _DATA) == []


def test_een_oorzaak_in_de_alinea_na_de_onderzoeksvraag_blijft_ongedekt():
    tekst = (
        "**Onderzoeksvraag:** Is het verschil te verklaren uit de locatie?\n"
        "Dit komt doordat studenten kiezen voor een andere stad."
    )
    assert len(ongedekte_oorzaak(tekst, _DATA)) == 1


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


# --- een geladen bron met een eigen tool (#999): de store-meta schrijft `bron:id`, de catalogus het kale ID ---

_SKDB_VRAAG = "Wat zegt de Studiekeuzedatabase over het oordeel van studenten van HBO-ICT?"
_SKDB_TEKST = "De opleiding heeft geen oordeel in de Studiekeuzedatabase; dat cijfer is niet beschikbaar."
_SKDB_KEY = "skdb:opleidingen:a1b2"
_ZONDER_DRIE = "get_duo_data, get_cbs_data of get_rio_data"


@pytest.fixture
def _store():
    store.clear()
    yield
    store.clear()


def _geladen(key: str, bron: str, dataset: str) -> list[str]:
    store.put(key, pd.DataFrame({"aantal": [1]}), KeyMeta(bron=bron, dataset=dataset))
    return [json.dumps({"data_key": key})]


def test_een_geladen_studiekeuzedatabase_mag_een_afwezigheid_melden(monkeypatch, _store):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: ["studiekeuzedatabase"])
    resultaten = _geladen(_SKDB_KEY, "skdb", "skdb:studiekeuzedatabase")

    assert onbeschikbaar_zonder_zoekpad(_SKDB_VRAAG, _SKDB_TEKST, resultaten) == []


def test_een_niet_geladen_studiekeuzedatabase_noemt_haar_eigen_tool(monkeypatch, _store):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: ["studiekeuzedatabase"])

    [probleem] = onbeschikbaar_zonder_zoekpad(_SKDB_VRAAG, _SKDB_TEKST, _DATA)

    assert "studiekeuzedatabase" in probleem and "get_studiekeuze" in probleem
    assert _ZONDER_DRIE not in probleem


@pytest.mark.parametrize(
    ("genoemd", "tool"), [("85423NED", "get_cbs_data"), ("aangeboden-opleidingen", "get_rio_data")]
)
def test_een_niet_geladen_dataset_noemt_de_datatool_van_zijn_bron(monkeypatch, _store, genoemd, tool):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: [genoemd])

    [probleem] = onbeschikbaar_zonder_zoekpad(f"Wat zegt {genoemd}?", "Dat is niet beschikbaar.", _DATA)

    assert tool in probleem and _ZONDER_DRIE not in probleem


@pytest.mark.parametrize(
    ("genoemd", "bron", "dataset"),
    [
        ("studiekeuzedatabase", "skdb", "skdb:studiekeuzedatabase"),
        ("wopi", "unl", "unl:wopi"),
        ("financien", "duo", "duo:financien"),
        ("85423NED", "cbs", "cbs:85423ned"),
        ("85423NED", "cbs", "85423ned"),
        ("p01hoinges", "duo", "P01HOINGES"),
    ],
)
def test_genoemd_en_geladen_volgen_een_normalisatie(monkeypatch, _store, genoemd, bron, dataset):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: [genoemd])
    resultaten = _geladen(f"{bron}:x:0", bron, dataset)

    assert onbeschikbaar_zonder_zoekpad(f"Wat zegt {genoemd}?", "Dat is niet beschikbaar.", resultaten) == []


def test_een_andere_geladen_dataset_dekt_de_genoemde_niet(monkeypatch, _store):
    monkeypatch.setattr(beweringen, "genoemde_datasets", lambda vraag: ["p01hoinges"])
    resultaten = _geladen(_SKDB_KEY, "skdb", "skdb:studiekeuzedatabase")

    [probleem] = onbeschikbaar_zonder_zoekpad("Wat zegt p01hoinges?", "Dat is niet beschikbaar.", resultaten)

    assert "p01hoinges" in probleem and "get_duo_data" in probleem
