"""get_maat tegen de echte bronnen (#188, AC2): de ijkwaarden van #190, niet in elke CI-run.

Draait alleen met ONDERWIJSDATA_LIVE=1: `ONDERWIJSDATA_LIVE=1 .venv/bin/python -m pytest tests/test_maten_ijk.py`.
De verwachte waarden komen uit tests/e2e/ijkwaarden.json (rechtstreeks bij CBS en DUO opgehaald, buiten tools/ om).
"""

import json
import os
from pathlib import Path

import pytest

from tools import cbs_standaard
from tools.maten import get_maat

pytestmark = pytest.mark.skipif(not os.getenv("ONDERWIJSDATA_LIVE"), reason="live bronnen: zet ONDERWIJSDATA_LIVE=1")

_IJK = json.loads((Path(__file__).resolve().parent / "e2e" / "ijkwaarden.json").read_text())["waarden"]
_HU = "Hogeschool Utrecht"


def _rij(uitkomst: str, kolom: str, jaar) -> int:
    uit = json.loads(uitkomst)
    assert "data_key" in uit, uit
    return next(int(r[uit["waardekolom"]]) for r in uit["rijen"] if str(r[kolom]).startswith(str(jaar)))


@pytest.mark.parametrize("jaar", [2021, 2022, 2023, 2024, 2025])
def test_hu_voltijd_personen(jaar):
    uit = get_maat("ingeschreven_personen_ho", _HU, vorm="voltijd", schooljaren=[f"{jaar}/{(jaar + 1) % 100:02d}"])
    assert _rij(uit, "STUDIEJAAR", jaar) == _IJK[f"duo-hu-voltijd-{jaar}"]["waarde"]


@pytest.mark.parametrize("jaar", [2024, 2025])
def test_hu_deeltijd_personen(jaar):
    uit = get_maat("ingeschreven_personen_ho", _HU, vorm="deeltijd", schooljaren=[str(jaar)])
    assert _rij(uit, "STUDIEJAAR", jaar) == _IJK[f"duo-hu-deeltijd-{jaar}"]["waarde"]


@pytest.mark.parametrize("jaar", [2021, 2025])
def test_hu_eerstejaars_voltijd(jaar):
    uit = get_maat("eerstejaars_ho", _HU, vorm="voltijd", schooljaren=[str(jaar)])
    assert _rij(uit, "STUDIEJAAR", jaar) == _IJK[f"duo-hu-eerstejaars-voltijd-{jaar}"]["waarde"]


@pytest.mark.parametrize("jaar", [2021, 2022, 2023, 2024, 2025])
def test_hu_inschrijvingen_voltijd(jaar):
    uit = get_maat("inschrijvingen_ho", _HU, vorm="voltijd", schooljaren=[str(jaar)])
    assert _rij(uit, "STUDIEJAAR", jaar) == _IJK[f"duo-hu-inschrijvingen-voltijd-{jaar}"]["waarde"]


@pytest.mark.parametrize(
    ("id", "sector", "vorm", "jaar"),
    [
        ("cbs-hbo-voltijd-2024", "hbo", "voltijd", 2024),
        ("cbs-hbo-voltijd-2025", "hbo", "voltijd", 2025),
        ("cbs-hbo-totaal-2024", "hbo", "alle", 2024),
        ("cbs-wo-totaal-2024", "wo", "alle", 2024),
    ],
)
def test_landelijk_cbs(id, sector, vorm, jaar):
    uit = get_maat("deelnemers_ho_landelijk", sector=sector, vorm=vorm, schooljaren=[str(jaar)])
    assert _rij(uit, "Perioden", jaar) == _IJK[id]["waarde"]


# Vmbo → mbo (#667): rechtstreeks bij CBS nagerekend op 22-10-2026 (85569NED, 2025SJ00, A041923 + A041922).
_VMBO_MBO_2025 = {"incl": 39940 + 43080, "excl": 39740 + 43040}


def test_doorstroom_vmbo_mbo_inclusief_extranei():
    with cbs_standaard.gesprek(["Hoeveel leerlingen stromen door van het vmbo naar het mbo?"]):
        uit = get_maat("doorstroom_vmbo_mbo", schooljaren=["2025/26"])
    assert _rij(uit, "Perioden", 2025) == _VMBO_MBO_2025["incl"] == 83020


def test_doorstroom_vmbo_mbo_zonder_extranei():
    with cbs_standaard.gesprek(["Hoeveel leerlingen stromen door van het vmbo naar het mbo, zonder extranei?"]):
        uit = get_maat("doorstroom_vmbo_mbo", schooljaren=["2025/26"])
    assert _rij(uit, "Perioden", 2025) == _VMBO_MBO_2025["excl"] == 82780


# Mbo-studenten landelijk (#805): CBS 85354NED, dezelfde ijkpunten als de eval ijk-mbo-studenten-landelijk.
@pytest.mark.parametrize(
    ("vraag", "id"),
    [
        ("Hoeveel mbo-studenten waren er in 2024/25?", "cbs-mbo-totaal-2024"),
        ("Hoeveel mbo-studenten waren er in 2024/25, zonder extranei?", "cbs-mbo-totaal-excl-extranei-2024"),
    ],
)
def test_mbo_studenten_landelijk(vraag, id):
    with cbs_standaard.gesprek([vraag]):
        uit = get_maat("mbo_studenten_landelijk", schooljaren=["2024/25"])
    assert _rij(uit, "Perioden", 2024) == _IJK[id]["waarde"]
