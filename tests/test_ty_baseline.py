"""De ty-poort faalt alleen op diagnostics die niet in de baseline staan (#230)."""

from collections import Counter
from datetime import date

from scripts.ty_baseline import AFBOUWPLAN, doel, nieuwe, sleutels, voortgang

UITVOER = """\
agent/loop.py:88:67: warning[invalid-argument-type] Argument to function `to_thread` is incorrect
agent/loop.py:91:44: warning[invalid-argument-type] Argument to function `to_thread` is incorrect
agent/grounding.py:68:52: error[invalid-parameter-default] Default value of type `tuple[()]`
Found 3 diagnostics
"""


def test_sleutel_zonder_regelnummer():
    # Een regel erboven toevoegen verschuift het regelnummer; dat mag geen nieuwe diagnostic zijn.
    assert sleutels(UITVOER) == Counter(
        {
            "agent/loop.py: warning[invalid-argument-type] Argument to function `to_thread` is incorrect": 2,
            "agent/grounding.py: error[invalid-parameter-default] Default value of type `tuple[()]`": 1,
        }
    )


def test_samenvattingsregel_telt_niet():
    assert "Found 3 diagnostics" not in " ".join(sleutels(UITVOER))


def test_gelijk_aan_baseline_is_niets_nieuw():
    assert nieuwe(sleutels(UITVOER), sleutels(UITVOER)) == []


def test_extra_exemplaar_van_bekende_diagnostic_is_nieuw():
    baseline = sleutels(UITVOER)
    huidig = baseline + Counter(
        {"agent/grounding.py: error[invalid-parameter-default] Default value of type `tuple[()]`": 1}
    )
    assert nieuwe(huidig, baseline) == [
        "agent/grounding.py: error[invalid-parameter-default] Default value of type `tuple[()]`"
    ]


def test_opgeloste_diagnostic_is_niet_nieuw():
    baseline = sleutels(UITVOER)
    huidig = Counter(baseline)
    del huidig["agent/grounding.py: error[invalid-parameter-default] Default value of type `tuple[()]`"]
    assert nieuwe(huidig, baseline) == []


# ── Afbouwplan (#391) ────────────────────────────────────────────────────────


def test_afbouwplan_daalt_naar_nul():
    datums = [d for d, _ in AFBOUWPLAN]
    plafonds = [n for _, n in AFBOUWPLAN]
    assert datums == sorted(datums)
    assert plafonds == sorted(plafonds, reverse=True)
    assert plafonds[-1] == 0


def test_doel_is_het_eerstvolgende_plafond():
    eerste, tweede = AFBOUWPLAN[0], AFBOUWPLAN[1]
    assert doel(date(2026, 10, 5)) == eerste
    assert doel(eerste[0]) == eerste
    assert doel(date.fromordinal(eerste[0].toordinal() + 1)) == tweede
    assert doel(date(2099, 1, 1)) is None


def test_voortgang_noemt_wat_er_nog_af_moet():
    datum, plafond = AFBOUWPLAN[0]
    regel = voortgang(plafond + 29, date(2026, 10, 5))
    assert f"≤{plafond}" in regel
    assert datum.isoformat() in regel
    assert "nog 29" in regel


def test_voortgang_onder_het_plafond():
    _, plafond = AFBOUWPLAN[0]
    assert "nog" not in voortgang(plafond, date(2026, 10, 5))
