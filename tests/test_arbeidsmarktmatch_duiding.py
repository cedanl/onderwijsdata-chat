"""De arbeidsmarktmatch zegt waar haar score op rust (#900, #1225): bron en kwartalen, drempel, jaren, ROA-versie,
koppeltabel en dat de score indicatief is.

De tegels zeiden "schaarste", "evenwicht" of "overaanbod" zonder bron, periode, drempel of definitie. Sinds #1225 rust
de score op CBS 83599NED (vacatures per bedrijfstak, gemiddeld over vier kwartalen) en de koppeltabel van
data/sbi_onderwijssector.csv; de vacatures in de fixture zijn het opgenomen antwoord van CBS (tests/cbs_83599ned.py).
"""

from datetime import UTC, datetime

import pytest

import data.dashboard as dashboard
from core import actualiteit
from data import sbi_koppeling, vacatures_cbs

_HU = "Hogeschool Utrecht"
_MONDRIAAN = "ROC Mondriaan"
_VIER = ["2025 4e kwartaal", "2026 1e kwartaal", "2026 2e kwartaal", "2026 3e kwartaal"]


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_de_match_noemt_bron_kwartalen_drempel_jaren_roa_versie_en_koppeltabel():
    result = dashboard.load_dashboard_arbeidsmarktmatch(_HU)

    duiding = result["match_duiding"]
    assert duiding["drempel"] == dashboard._MATCH_DREMPEL == 1.2
    vacatures = duiding["vacatures"]
    assert (vacatures["bron"], vacatures["dataset"], vacatures["licentie"]) == ("CBS", "83599NED", "CC BY 4.0")
    assert vacatures["url"] == vacatures_cbs.STATLINE_URL
    # Het gemiddelde van de laatste vier kwartalen, en CBS noemt ze voorlopig.
    assert vacatures["perioden"] == _VIER and vacatures["kwartalen"] == 4
    assert vacatures["periode"] == "2025 4e kwartaal t/m 2026 3e kwartaal"
    assert vacatures["voorlopig"] is True
    assert duiding["roa_versie"] == "v20260901"  # editie 2026 (#1091)
    assert duiding["min_gediplomeerden"] == dashboard._MATCH_MIN_GEDIPLOMEERDEN == 30
    assert duiding["koppeltabel"] == {"herkomst": sbi_koppeling.HERKOMST, "bijgewerkt": sbi_koppeling.BIJGEWERKT}
    assert "taalmodel" in sbi_koppeling.HERKOMST and "hand" in sbi_koppeling.HERKOMST
    # Drie diplomajaren, de laatste die het bestand heeft: het aanbod is daar het gemiddelde van.
    assert len(duiding["diplomajaren"]) == dashboard._SECTOR_GEMIDDELD_JAREN
    assert duiding["diplomajaren"] == sorted(duiding["diplomajaren"])
    assert all(isinstance(j, int) for j in duiding["diplomajaren"])
    assert "diplomajaren" not in result  # alleen in de duiding, niet los naast de score


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_de_uitleg_zegt_bedrijfstak_en_indicatief():
    duiding = dashboard.load_dashboard_arbeidsmarktmatch(_HU)["match_duiding"]

    assert duiding["indicatief"] is True
    assert "bedrijfstak" in duiding["uitleg"] and "niet per beroep" in duiding["uitleg"]
    assert "indicatief" in duiding["uitleg"]
    # Niets meer van UWV: geen peildatum van een momentopname en geen LLM-sectorindeling.
    assert "vacatures_peildatum" not in duiding and "sectormapping" not in duiding


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_de_mbo_match_noemt_de_diplomajaren_van_de_hoofdgroepen():
    result = dashboard.load_dashboard_arbeidsmarktmatch(_MONDRIAAN)
    duiding = result["match_duiding"]

    assert duiding["diplomajaren"] == [2023, 2024, 2025]
    assert duiding["vacatures"]["perioden"] == _VIER
    # Mbo-hoofdgroepen via de mbo-kolom van de koppeltabel; Entree hoort bewust bij geen bedrijfstak.
    assert result["niveau"] == "mbo"
    if "Entree" in result["gediplomeerden_per_sector"]:
        assert result["match_weggelaten"]["Entree"] == dashboard._MATCH_GEEN_KOPPELING


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
@pytest.mark.parametrize(
    ("nu", "maanden", "verouderd"),
    [(datetime(2026, 11, 26, tzinfo=UTC), 1, False), (datetime(2027, 11, 1, tzinfo=UTC), 13, True)],
)
def test_de_ouderdom_van_het_laatste_kwartaal(monkeypatch, nu, maanden, verouderd):
    # Het laatste kwartaal eindigt op 30 september 2026: nu jong, maar stopt CBS met de tabel, dan waarschuwt het
    # dashboard na twaalf maanden zoals bij UWV (#1219).
    monkeypatch.setattr(actualiteit, "nu", lambda: nu)

    duiding = dashboard.load_dashboard_arbeidsmarktmatch(_HU)["match_duiding"]

    assert (duiding["peildatum_ouderdom_maanden"], duiding["verouderd"]) == (maanden, verouderd)


@pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
def test_zonder_cbs_geen_kwartalen_en_het_gat_staat_erin(monkeypatch):
    def storing(provincie):
        raise ConnectionError("CBS")

    monkeypatch.setattr(vacatures_cbs, "stand", storing)

    result = dashboard.load_dashboard_arbeidsmarktmatch(_HU)

    vacatures = result["match_duiding"]["vacatures"]
    assert vacatures["perioden"] == [] and vacatures["periode"] is None and vacatures["voorlopig"] is False
    assert vacatures["dataset"] == "83599NED"  # de bron blijft genoemd
    assert result["match_duiding"]["drempel"] == 1.2  # de definitie blijft, ook zonder score
    assert result["match_duiding"]["verouderd"] is False
    assert {g["bron"] for g in result["niet_beschikbaar"]} == {"CBS"}


@pytest.mark.parametrize(
    ("dipl_aandeel", "vac_aandeel", "label"),
    [
        (0.5, 0.6, "evenwicht"),  # precies 1,2 keer: nog evenwicht
        (0.5, 0.6001, "schaarste"),  # net erboven
        (0.6, 0.5, "evenwicht"),
        (0.6001, 0.5, "overaanbod"),
        (0.5, 0.5, "evenwicht"),
        (0.5, 0.0, "overaanbod"),  # een sector met bedrijfstakken maar zonder vacatures
    ],
)
def test_de_drempelgrenzen_van_het_label(dipl_aandeel, vac_aandeel, label):
    assert dashboard._match_label(dipl_aandeel, vac_aandeel) == label
