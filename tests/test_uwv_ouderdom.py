"""Hoe oud de UWV-vacatures zijn, en vanaf wanneer ze verouderd heten (#1219).

De vacatures komen uit UWV Open Match, peildatum 16 mei 2023. De app noemde die datum wel, maar niet hoe oud ze is:
naast diplomajaren tot 2025 leek de app achter te lopen. Nu geven de dashboards, de chattool en de bronregels de
ouderdom in hele maanden mee, met `verouderd` boven `VACATURES_VEROUDERD_MAANDEN`. Elke test zet de klok vast
(`actualiteit.nu`); geen test hangt van de echte datum af.
"""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from core import actualiteit
from data import arbeidsmarkt, bronblok
from tools import arbeidsmarkt as tools_arbeidsmarkt
from tools import store
from tools.arbeidsmarkt import get_uwv_vacatures
from tools.schemas import TOOL_GET_UWV_VACATURES

_NU = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def klok(monkeypatch):
    monkeypatch.setattr(actualiteit, "nu", lambda: _NU)


# ── De ouderdom in maanden en de grens ───────────────────────────────────────


@pytest.mark.parametrize(
    ("peildatum", "maanden"),
    [
        ("2023-05-16", 42),
        ("2025-12-25", 11),
        ("2025-11-26", 11),  # een dag voor de twaalfde maand vol is
        ("2025-11-25", 12),
        ("2025-10-25", 13),
        ("2026-11-25", 0),
        ("2023-05-09, 2023-05-16", 42),  # meer peildata: de jongste telt
    ],
)
def test_de_ouderdom_is_het_aantal_hele_maanden_tot_nu(peildatum, maanden):
    assert arbeidsmarkt.peildatum_ouderdom_maanden(peildatum) == maanden


@pytest.mark.parametrize("peildatum", [None, "", "onbekend"])
def test_zonder_leesbare_peildatum_geen_ouderdom(peildatum):
    assert arbeidsmarkt.peildatum_ouderdom_maanden(peildatum) is None
    assert arbeidsmarkt.ouderdom(peildatum) == {"peildatum_ouderdom_maanden": None, "verouderd": False}


def test_een_peildatum_na_nu_is_niet_negatief_oud():
    assert arbeidsmarkt.peildatum_ouderdom_maanden("2027-01-01") == 0


@pytest.mark.parametrize(
    ("peildatum", "verouderd"), [("2025-12-25", False), ("2025-11-25", False), ("2025-10-25", True)]
)
def test_verouderd_boven_twaalf_maanden(peildatum, verouderd):
    assert arbeidsmarkt.VACATURES_VEROUDERD_MAANDEN == 12
    assert arbeidsmarkt.ouderdom(peildatum)["verouderd"] is verouderd


@pytest.mark.parametrize(
    ("maanden", "tekst"),
    [
        (0, "minder dan een maand"),
        (1, "1 maand"),
        (11, "11 maanden"),
        (12, "1 jaar"),
        (13, "ruim 1 jaar"),
        (24, "2 jaar"),
        (42, "ruim 3 jaar"),
    ],
)
def test_de_ouderdom_in_woorden(maanden, tekst):
    assert arbeidsmarkt.ouderdom_tekst(maanden) == tekst


def test_het_peilmoment_noemt_datum_en_ouderdom():
    assert arbeidsmarkt.uwv_peiltekst("2023-05-16") == "peildatum 16 mei 2023, ruim 3 jaar oud"
    assert (
        arbeidsmarkt.uwv_peiltekst("2023-05-09, 2023-05-16") == "peildatum 9 mei 2023 en 16 mei 2023, ruim 3 jaar oud"
    )
    assert arbeidsmarkt.uwv_peiltekst("onbekend") == "peildatum onbekend"


# ── De chat: toolresultaat en bronregel ──────────────────────────────────────

_UWV = pd.DataFrame(
    {
        "PEILDATUM": ["16-05-2023"] * 2,
        "PROVINCIE": ["Utrecht", "Utrecht"],
        "GEMEENTE": ["Utrecht", "Amersfoort"],
        "BEROEPENCLUSTER": ["Zorg en welzijn", "ICT"],
        "AANTAL": [900, 200],
    }
)


@pytest.fixture
def uwv():
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=_UWV),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
    ):
        yield


def test_het_toolresultaat_noemt_ouderdom_en_verouderd(uwv):
    uit = json.loads(get_uwv_vacatures("Utrecht"))

    assert uit["peildatum"] == "2023-05-16"
    assert uit["peildatum_ouderdom_maanden"] == 42
    assert uit["verouderd"] is True
    # De woorden voor het antwoord, en waar de actuele kwartaalcijfers staan; de app laadt die niet.
    assert "ruim 3 jaar" in uit["ouderdom_toelichting"]
    assert "sinds mei 2023" in uit["ouderdom_toelichting"]
    assert "83599NED" in uit["ouderdom_toelichting"] and "Vacaturemarkt" in uit["ouderdom_toelichting"]


def test_een_jonge_stand_is_niet_verouderd_en_draagt_geen_waarschuwing():
    jong = _UWV.assign(PEILDATUM="25-10-2026")
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=jong),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
    ):
        uit = json.loads(get_uwv_vacatures("Utrecht"))

    assert (uit["peildatum_ouderdom_maanden"], uit["verouderd"]) == (1, False)
    assert "ouderdom_toelichting" not in uit


def test_de_bronregel_onder_het_antwoord_noemt_de_ouderdom(uwv):
    get_uwv_vacatures("Utrecht")

    assert tools_arbeidsmarkt.peilmoment(TOOL_GET_UWV_VACATURES) == "peildatum 16 mei 2023, ruim 3 jaar oud"
    known = store.meta("uwv:utrecht")
    assert known is not None and known.peilmoment == "peildatum 16 mei 2023, ruim 3 jaar oud"


# ── De dashboards: payload en bronblok ───────────────────────────────────────


def test_het_vacatureaanbod_draagt_ouderdom_en_verouderd():
    stand = arbeidsmarkt.UwvStand(1100, "2023-05-16", {"Zorg en welzijn": 900, "ICT": 200}, "Utrecht")
    with patch.object(arbeidsmarkt, "uwv_stand", return_value=stand):
        vac = dashboard._uwv_vacatures_provincie("Utrecht")

    assert (vac["peildatum"], vac["peildatum_ouderdom_maanden"], vac["verouderd"]) == ("2023-05-16", 42, True)


def test_de_matchduiding_draagt_ouderdom_en_verouderd():
    stand = arbeidsmarkt.UwvStand(1100, "2023-05-16", {"ICT": 1100}, "Utrecht")
    with patch.object(arbeidsmarkt, "uwv_stand", return_value=stand):
        duiding = dashboard._match_duiding("Utrecht", [2025], vacatures_geladen=True, roa_geladen=False)

    assert duiding["vacatures_peildatum"] == "2023-05-16"
    assert (duiding["peildatum_ouderdom_maanden"], duiding["verouderd"]) == (42, True)


def test_de_matchduiding_zonder_uwv_noemt_geen_ouderdom():
    duiding = dashboard._match_duiding("Utrecht", [2025], vacatures_geladen=False, roa_geladen=False)

    assert (duiding["peildatum_ouderdom_maanden"], duiding["verouderd"]) == (None, False)


def test_het_bronblok_noemt_bij_uwv_de_ouderdom():
    [regel] = bronblok.blok(
        [{"bron": "UWV", "dataset": "uwv-open-match-data", "peildatum": "2023-05-16", "opgehaald_op": _NU.isoformat()}]
    )

    assert regel["peildatum"] == "2023-05-16"
    assert regel["peilmoment"] == "peildatum 16 mei 2023, ruim 3 jaar oud"
    assert (regel["peildatum_ouderdom_maanden"], regel["verouderd"]) == (42, True)


def test_de_periode_van_de_catalogus_voor_een_lege_uwv_sectie():
    # Uit uwv_resources.json, zonder netwerk: de lege staat noemt geen vaste maand.
    assert arbeidsmarkt.uwv_periode() == "2019-11-26 t/m 2023-05-16 (wekelijkse snapshots)"
