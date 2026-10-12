"""Determinisme als CI-eigenschap (#347): plan-invariantie, golden stand, herstelgraad.

Draait zonder netwerk en zonder model. De golden stand (`gevallen.json`) wijzigt
alleen via een expliciete update: `uv run python scripts/meet_determinisme.py
--schrijf-golden`, met een verantwoording in de MR.
"""

import pytest

from . import harnas

_UPDATE = "draai `uv run python scripts/meet_determinisme.py --schrijf-golden` en verantwoord de wijziging in de MR"


@pytest.fixture(autouse=True)
def _fixtures(clear_store):
    harnas.fixtures()


def _golden_gevallen() -> dict:
    return {geval["id"]: geval for geval in harnas.golden()["gevallen"]}


@pytest.mark.parametrize(("naam", "tool", "args"), [(g[0], g[2], g[3]) for g in harnas.GEVALLEN], ids=lambda v: str(v))
def test_plan_invariantie_spellingen_delen_een_digest(naam, tool, args):
    """N willekeurige gelijkwaardige spellingen → 1 plan-digest (PoC: 500 runs → 1 digest)."""
    digests = harnas.digests_van_varianten(tool, args)
    assert len(digests) == 1, f"{naam}: {len(digests)} unieke digests voor dezelfde selectie: {sorted(digests)}"


def test_verschillende_gevallen_delen_geen_digest():
    from tools import canoniek

    per_geval = {naam: canoniek.digest(tool, args) for naam, _, tool, args in harnas.GEVALLEN}
    assert len(set(per_geval.values())) == len(per_geval), per_geval


def test_plan_digests_zijn_de_golden_stand():
    golden = _golden_gevallen()
    from tools import canoniek

    for naam, _, tool, args in harnas.GEVALLEN:
        assert naam in golden, f"geval {naam} ontbreekt in gevallen.json; {_UPDATE}"
        assert canoniek.digest(tool, args) == golden[naam]["plan_digest"], (
            f"plan-digest van {naam} wijkt af van de golden stand; {_UPDATE}"
        )


def test_compilaat_is_de_golden_stand():
    golden = _golden_gevallen()
    for naam, _, tool, args in harnas.GEVALLEN:
        verwacht = golden.get(naam, {}).get("compilaat")
        if verwacht is None:
            continue
        assert harnas._compilaat(tool, args) == verwacht, f"compilaat van {naam} wijkt af; {_UPDATE}"


def test_uitkomsten_zijn_de_golden_stand():
    golden = _golden_gevallen()
    for naam, _, tool, args in harnas.GEVALLEN:
        verwacht = golden.get(naam, {}).get("uitkomst_digest")
        if verwacht is None:
            continue
        assert harnas._uitkomst_digest(tool, args) == verwacht, f"uitkomst van {naam} wijkt af; {_UPDATE}"


def test_herstelroute_doet_wat_de_sample_verwacht():
    """De reparatie-/weigeringsgraad is meetbaar én klopt per geval (#342-route)."""
    graad = harnas.herstelgraad()
    for naam, _key, _filters, verwacht in harnas.HERSTEL_SAMPLE:
        assert graad["per_geval"][naam] == verwacht, (naam, graad["per_geval"][naam])
    assert graad["herstel"] >= 1 and graad["weigering"] >= 1


def test_scorekaart_is_gekoppeld_aan_prompt_en_model():
    """Rapportage per model en promptversie: de golden stand draagt zijn herkomst."""
    stand = harnas.golden()
    for sleutel in ("prompt_hash", "model", "schema_digest", "gemeten_op"):
        assert stand.get(sleutel), f"gevallen.json mist {sleutel}"
