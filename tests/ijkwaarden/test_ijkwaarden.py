"""De ijkwaarden-mechaniek zonder netwerk (#190): de DUO-regel, de vergelijking en de koppeling met de evals."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.ijkwaarden import harnas

_E2E = Path(__file__).resolve().parent.parent / "e2e"


def _hu(jaar: int, vorm: str, *aantallen: int) -> list[dict]:
    return [
        {"INSTELLINGSCODE_ACTUEEL": "25DW", "OPLEIDINGSVORM": vorm, "STUDIEJAAR": jaar, "AANTAL": n} for n in aantallen
    ]


_SELECTIE = {"instelling": "25DW", "opleidingsvorm": "VT", "studiejaar": 2021, "kolom": "AANTAL"}


def test_duo_som_telt_alleen_de_eigen_rijen():
    df = pd.DataFrame([*_hu(2021, "VT", 100, 200), *_hu(2021, "DT", 50), *_hu(2022, "VT", 999)])
    assert harnas.duo_som(df, _SELECTIE) == (300, 0)


def test_duo_som_laat_een_onderdrukte_cel_weg_en_telt_haar():
    """Audit 8: HU voltijd eerstejaars 2021/22 = 5.943 over 14 rijen, waarvan één -1."""
    df = pd.DataFrame(_hu(2021, "VT", *([457] * 13), -1))
    assert harnas.duo_som(df, _SELECTIE) == (457 * 13, 1)


def test_duo_som_leest_codes_met_spaties_en_jaren_als_tekst():
    df = pd.DataFrame(
        [{"INSTELLINGSCODE_ACTUEEL": "25DW ", "OPLEIDINGSVORM": "vt", "STUDIEJAAR": "2021", "AANTAL": "7"}]
    )
    assert harnas.duo_som(df, _SELECTIE) == (7, 0)


def test_cbs_filter_gebruikt_trim_en_een_vaste_volgorde():
    """CBS vult sleutels op tot één breedte ('4000   '); zonder trim matcht een korte code niets (#531)."""
    f = harnas.cbs_filter({"Geslacht": "4000", "Regio": "NL01"}, "2021SJ00")
    assert f == "trim(Geslacht) eq '4000' and trim(Regio) eq 'NL01' and trim(Perioden) eq '2021SJ00'"


def test_vestigingsplaats_staat_achter_de_puntkomma():
    assert harnas.vestigingsplaats("Aeres  Hogeschool; Ede") == "Ede"
    assert harnas.vestigingsplaats("Aeres Hogeschool") == "Aeres Hogeschool"


def test_vergelijk_meldt_afwijking_nieuw_en_verdwenen():
    oud = {"a": {"waarde": 1, "status": "Voorlopig"}, "weg": {"waarde": 9}}
    nieuw = {"a": {"waarde": 1, "status": "Definitief"}, "erbij": {"waarde": 2}}
    verschillen = harnas.vergelijk(oud, nieuw)
    assert [(v.id, v.soort, v.veld) for v in verschillen] == [
        ("a", "afwijking", "status"),
        ("erbij", "nieuw", None),
        ("weg", "verdwenen", None),
    ]
    assert verschillen[0].vastgelegd == "Voorlopig" and verschillen[0].live == "Definitief"


def test_vergelijk_negeert_de_ophaaldatum_en_de_brondatum():
    oud = {"a": {"waarde": 1, "bron_gewijzigd": "2026-01-01", "url": "x"}}
    nieuw = {"a": {"waarde": 1, "bron_gewijzigd": "2026-04-10", "url": "y"}}
    assert harnas.vergelijk(oud, nieuw) == []


def test_schrijf_en_lees_zijn_elkaars_spiegel(tmp_path):
    pad = tmp_path / "ijk.json"
    harnas.schrijf({"b": {"waarde": 2}, "a": {"waarde": 1}}, pad, vandaag=harnas.date(2026, 10, 13))
    gelezen = harnas.lees(pad)
    assert gelezen["opgehaald_op"] == "2026-10-13"
    assert list(gelezen["waarden"]) == ["a", "b"]


def test_ids_zijn_uniek_en_de_bron_is_bekend():
    ids = [p.id for p in harnas.IJKPUNTEN]
    assert len(ids) == len(set(ids))
    assert {p.bron for p in harnas.IJKPUNTEN} <= set(harnas._HALERS)


# --- de vastgelegde stand en de evals ----------------------------------------------------


@pytest.fixture(scope="module")
def fixture() -> dict:
    return harnas.lees()["waarden"]


def test_de_fixture_dekt_precies_de_lijst_ijkpunten(fixture):
    assert set(fixture) == {p.id for p in harnas.IJKPUNTEN}
    for punt in harnas.IJKPUNTEN:
        w = fixture[punt.id]
        assert w["bron"] == punt.bron and w["selectie"] == punt.selectie, punt.id
        assert "waarde" in w and w["url"].startswith("https://"), punt.id


def test_elke_ijkverwijzing_in_de_evals_bestaat_en_is_een_getal(fixture):
    evals = json.loads((_E2E / "evaluations.json").read_text(encoding="utf-8"))["evaluations"]
    verwijzingen = [
        (ev["label"], sleutel, id)
        for ev in evals
        for sleutel, id in (ev["expected"].get("data_points", {}).get("ijkwaarden") or {}).items()
    ]
    assert verwijzingen, "geen enkele eval verwijst naar een ijkwaarde"
    for label, sleutel, id in verwijzingen:
        assert id in fixture, f"{label}: {sleutel} → {id} staat niet in ijkwaarden.json"
        assert isinstance(fixture[id]["waarde"], int), f"{label}: {id} is geen getal"


def test_een_eval_met_ijkwaarden_heeft_geen_eigen_referentiewaarden():
    """Eén bron van waarheid: de waarde staat in ijkwaarden.json, niet nog eens in de eval."""
    evals = json.loads((_E2E / "evaluations.json").read_text(encoding="utf-8"))["evaluations"]
    for ev in evals:
        dp = ev["expected"].get("data_points") or {}
        if dp.get("ijkwaarden"):
            assert "reference_values" not in dp, ev["label"]
            assert dp.get("tolerance_pct", 0) == 0, f"{ev['label']}: een ijkwaarde is exact, geen tolerantie"
