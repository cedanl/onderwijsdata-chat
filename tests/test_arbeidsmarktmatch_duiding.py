"""De arbeidsmarktmatch zegt waar haar score op rust (#900): peildatum, drempel, jaren, ROA-versie en mapping.

De tegels zeiden "schaarste", "evenwicht" of "overaanbod" zonder bron, peildatum, drempel of definitie, terwijl de chat
de peildatum (#577) en de herkomst van de sectorindeling (#460) wel noemt.
"""

import pytest

import data.dashboard as dashboard
from data import arbeidsmarkt

_HU = "Hogeschool Utrecht"
_MONDRIAAN = "ROC Mondriaan"


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_de_match_noemt_peildatum_drempel_jaren_roa_versie_en_mapping():
    result = dashboard.load_dashboard_arbeidsmarktmatch(_HU)

    duiding = result["match_duiding"]
    assert duiding["drempel"] == dashboard._MATCH_DREMPEL == 1.2
    # De peildatum uit de data, zoals de bronregel van de chat en de UWV-grafiek van het dashboard.
    stand = arbeidsmarkt.uwv_stand(result["provincie"])
    assert stand is not None
    assert duiding["vacatures_peildatum"] == stand.peildatum == "2023-05-16"
    assert duiding["roa_versie"] == "v20251218"
    assert duiding["min_gediplomeerden"] == dashboard._MATCH_MIN_GEDIPLOMEERDEN == 30
    assert duiding["sectormapping"]["herkomst"] == "LLM-classificatie, niet van UWV"
    # F3 (#951): wat de mapping niet vastlegt, belooft de payload niet ("model": "onbekend" stond erin).
    vastgelegd = {k: v for k, v in arbeidsmarkt.SECTOR_MANIFEST.items() if v != arbeidsmarkt.ONBEKEND}
    assert duiding["sectormapping"] == vastgelegd
    assert arbeidsmarkt.ONBEKEND not in duiding["sectormapping"].values()
    if arbeidsmarkt.SECTOR_MANIFEST["model"] == arbeidsmarkt.ONBEKEND:
        assert "model" not in duiding["sectormapping"]
    # Drie diplomajaren, de laatste die het bestand heeft: het aanbod is daar het gemiddelde van.
    assert len(duiding["diplomajaren"]) == dashboard._SECTOR_GEMIDDELD_JAREN
    assert duiding["diplomajaren"] == sorted(duiding["diplomajaren"])
    assert all(isinstance(j, int) for j in duiding["diplomajaren"])
    assert "diplomajaren" not in result  # alleen in de duiding, niet los naast de score


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_de_mbo_match_noemt_de_diplomajaren_van_de_hoofdgroepen():
    duiding = dashboard.load_dashboard_arbeidsmarktmatch(_MONDRIAAN)["match_duiding"]

    assert duiding["diplomajaren"] == [2023, 2024, 2025]
    assert duiding["vacatures_peildatum"] == "2023-05-16"


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_zonder_uwv_geen_peildatum_en_geen_nieuwe_poging(monkeypatch):
    monkeypatch.setattr(arbeidsmarkt, "uwv_stand", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("UWV")))
    peildatum_gevraagd = []
    monkeypatch.setattr(dashboard, "_uwv_peildatum", lambda provincie: peildatum_gevraagd.append(provincie))

    result = dashboard.load_dashboard_arbeidsmarktmatch(_HU)

    assert result["match_duiding"]["vacatures_peildatum"] is None
    assert result["match_duiding"]["drempel"] == 1.2  # de definitie blijft, ook zonder score
    # De score probeerde UWV al en meldde het gat; de duiding haalt UWV niet nog eens op.
    assert peildatum_gevraagd == []
    assert {g["bron"] for g in result["niet_beschikbaar"]} == {"UWV"}


@pytest.mark.parametrize(
    ("dipl_aandeel", "vac_aandeel", "label"),
    [
        (0.5, 0.6, "evenwicht"),  # precies 1,2 keer: nog evenwicht
        (0.5, 0.6001, "schaarste"),  # net erboven
        (0.6, 0.5, "evenwicht"),
        (0.6001, 0.5, "overaanbod"),
        (0.5, 0.5, "evenwicht"),
        (0.5, 0.0, "overaanbod"),  # een sector met clusters maar zonder vacatures
    ],
)
def test_de_drempelgrenzen_van_het_label(dipl_aandeel, vac_aandeel, label):
    assert dashboard._match_label(dipl_aandeel, vac_aandeel) == label
