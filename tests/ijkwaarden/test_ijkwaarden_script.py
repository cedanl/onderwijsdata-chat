"""scripts/ijkwaarden.py: één bron die niet antwoordt blokkeert het rapport over de andere niet (#627)."""

import functools
import json
from datetime import date

import pytest

from scripts import ijkwaarden as script
from tests.ijkwaarden import harnas


def _waarde(bron: str, waarde: int) -> dict:
    return {"bron": bron, "waarde": waarde}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    """Een vastgelegde stand met één CBS-, één DUO- en één RIO-waarde, in een eigen bestand."""
    pad = tmp_path / "ijkwaarden.json"
    harnas.schrijf(
        {"cbs-a": _waarde("cbs", 10), "duo-a": _waarde("duo", 20), "rio-a": _waarde("rio", 30)},
        pad,
        vandaag=date(2026, 10, 1),
    )
    # lees() en schrijf() binden hun standaardpad bij het definiëren: zonder deze twee patches raakt een test
    # de echte tests/e2e/ijkwaarden.json.
    monkeypatch.setattr(harnas, "FIXTURE", pad)
    monkeypatch.setattr(harnas, "lees", functools.partial(harnas.lees, pad))
    monkeypatch.setattr(harnas, "schrijf", functools.partial(harnas.schrijf, pad=pad))
    monkeypatch.setattr(script, "ROOT", tmp_path)  # het script toont het pad van de fixture relatief aan de repo
    return pad


def _live(monkeypatch, live: dict, fouten: dict | None = None):
    monkeypatch.setattr(harnas, "haal_alles", lambda bronnen=None: (live, fouten or {}))


def _vastgelegd(pad) -> dict:
    return json.loads(pad.read_text(encoding="utf-8"))["waarden"]


def test_een_falende_bron_staat_in_het_rapport_en_de_andere_bronnen_worden_vergeleken(fixture, monkeypatch, capsys):
    _live(
        monkeypatch,
        {"cbs-a": _waarde("cbs", 10), "duo-a": _waarde("duo", 21)},
        {"rio-a": "HTTPError: RIO weigerde de aanvraag (HTTP 410)"},
    )
    assert script.main([]) == 1
    uit = capsys.readouterr().out
    assert "rio-a" in uit and "HTTP 410" in uit  # de bron die niet antwoordt, met de fout
    assert "duo-a" in uit and "20" in uit and "21" in uit  # het verschil van DUO wordt wel getoond
    assert "verdwenen" not in uit and "niet meer in de lijst" not in uit  # een bronfout is geen verdwenen waarde


def test_een_falende_bron_zonder_verschil_elders_geeft_toch_exitcode_1(fixture, monkeypatch, capsys):
    _live(monkeypatch, {"cbs-a": _waarde("cbs", 10), "duo-a": _waarde("duo", 20)}, {"rio-a": "HTTPError: 410"})
    assert script.main([]) == 1
    assert "Geen verschil" in capsys.readouterr().out


def test_zonder_fouten_en_zonder_verschil_blijft_het_groen(fixture, monkeypatch):
    _live(monkeypatch, {"cbs-a": _waarde("cbs", 10), "duo-a": _waarde("duo", 20), "rio-a": _waarde("rio", 30)})
    assert script.main([]) == 0


def test_schrijf_bewaart_de_vastgelegde_waarde_van_wat_niet_antwoordde(fixture, monkeypatch, capsys):
    _live(
        monkeypatch,
        {"cbs-a": _waarde("cbs", 11), "duo-a": _waarde("duo", 21)},
        {"rio-a": "HTTPError: 410"},
    )
    assert script.main(["--schrijf"]) == 1  # niet volledig: de stand is bijgewerkt voor wat antwoordde
    assert _vastgelegd(fixture) == {
        "cbs-a": _waarde("cbs", 11),
        "duo-a": _waarde("duo", 21),
        "rio-a": _waarde("rio", 30),  # ongewijzigd: de bron gaf geen antwoord
    }
    assert "rio-a" in capsys.readouterr().out


def test_alleen_een_bron_die_faalt_laat_de_rest_van_de_fixture_staan(fixture, monkeypatch):
    _live(monkeypatch, {}, {"rio-a": "HTTPError: 410"})
    assert script.main(["--alleen", "rio", "--schrijf"]) == 1
    assert _vastgelegd(fixture)["cbs-a"] == _waarde("cbs", 10)
    assert _vastgelegd(fixture)["rio-a"] == _waarde("rio", 30)


def test_haal_alles_verzamelt_de_fout_per_ijkpunt_in_plaats_van_te_stoppen(monkeypatch):
    def rio_faalt(punt):
        raise RuntimeError("RIO weigerde de aanvraag (HTTP 410)")

    monkeypatch.setitem(harnas._HALERS, "rio", rio_faalt)
    monkeypatch.setitem(harnas._HALERS, "cbs", lambda punt: {"waarde": 1})
    monkeypatch.setitem(harnas._HALERS, "duo", lambda punt: {"waarde": 2})
    live, fouten = harnas.haal_alles()
    assert {p.id for p in harnas.IJKPUNTEN if p.bron != "rio"} == set(live)
    assert {p.id for p in harnas.IJKPUNTEN if p.bron == "rio"} == set(fouten)
    assert all("HTTP 410" in tekst and "RuntimeError" in tekst for tekst in fouten.values())
