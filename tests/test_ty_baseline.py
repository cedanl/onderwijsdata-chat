"""De ty-poort faalt alleen op diagnostics die niet in de baseline staan (#230)."""

from collections import Counter

from scripts.ty_baseline import nieuwe, sleutels

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
