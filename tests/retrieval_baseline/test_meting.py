"""Het rekenwerk van de retrieval-baseline op synthetische rangen, met de hand nagerekend (#359)."""

import pytest

from tests.retrieval_baseline import meting


def test_rangen_geeft_de_plaats_van_elk_id_en_none_als_het_ontbreekt():
    assert meting.rangen(["a", "b", "c"], ["c", "x", "a"]) == {"c": 3, "x": None, "a": 1}


def test_rangen_kijkt_alleen_naar_de_eerste_top_n():
    ranking = [f"d{i}" for i in range(1, 21)]
    assert meting.rangen(ranking, ["d15", "d16"]) == {"d15": 15, "d16": None}
    assert meting.rangen(ranking, ["d5", "d6"], top_n=5) == {"d5": 5, "d6": None}


def test_eerste_rang_is_de_beste_gevonden_rang():
    assert meting.eerste_rang({"a": None, "b": 4, "c": 2}) == 2
    assert meting.eerste_rang({"a": None}) is None
    assert meting.eerste_rang({}) is None


def test_reciproke_rang():
    assert meting.reciproke_rang(1) == 1.0
    assert meting.reciproke_rang(4) == 0.25
    assert meting.reciproke_rang(None) == 0.0


def test_recall_bij_5_telt_vragen_met_een_treffer_in_de_top_5():
    # rang 5 telt mee, rang 6 en geen rang niet: 2 van 4.
    assert meting.recall_bij([1, 5, 6, None]) == 0.5


def test_mrr_is_het_gemiddelde_van_de_reciproke_eerste_rang():
    # (1 + 1/2 + 0 + 1/4) / 4
    assert meting.mrr([1, 2, None, 4]) == pytest.approx(0.4375)


def test_lege_cel_heeft_geen_recall_en_geen_mrr():
    assert meting.recall_bij([]) is None
    assert meting.mrr([]) is None


def test_wilson_bij_n_0_is_het_hele_bereik():
    assert meting.wilson(0, 0) == (0.0, 1.0)


def test_wilson_bij_alle_treffers():
    # ondergrens n / (n + z²) = 10 / 13,8415; bovengrens precies 1.
    laag, hoog = meting.wilson(10, 10)
    assert laag == pytest.approx(0.72246, abs=1e-5)
    assert hoog == 1.0


def test_wilson_bij_geen_treffers():
    # bovengrens z² / (n + z²) = 3,8415 / 13,8415.
    laag, hoog = meting.wilson(0, 10)
    assert laag == 0.0
    assert hoog == pytest.approx(0.27754, abs=1e-5)


def test_wilson_bij_de_helft_van_6_is_ongeveer_plus_min_0_3():
    # midden 0,5; marge 1,96 * sqrt(0,25/6 + z²/144) / (1 + z²/6) = 0,31239.
    laag, hoog = meting.wilson(3, 6)
    assert laag == pytest.approx(0.18761, abs=1e-5)
    assert hoog == pytest.approx(0.81239, abs=1e-5)


def test_bootstrap_bij_n_0_is_het_hele_bereik():
    assert meting.bootstrap_mrr([]) == (0.0, 1.0)


def test_bootstrap_bij_alle_treffers_op_rang_1():
    assert meting.bootstrap_mrr([1, 1, 1, 1]) == (1.0, 1.0)


def test_bootstrap_bij_alle_missers():
    assert meting.bootstrap_mrr([None, None, None]) == (0.0, 0.0)


def test_bootstrap_is_reproduceerbaar_en_omsluit_de_mrr():
    eerste = [1, 2, None, 4, 1, None, 3]
    laag, hoog = meting.bootstrap_mrr(eerste)
    waarde = meting.mrr(eerste)
    assert waarde is not None
    assert meting.bootstrap_mrr(eerste) == (laag, hoog)
    assert 0.0 <= laag <= waarde <= hoog <= 1.0
    assert laag < hoog


def test_kwantiel_interpoleert_lineair():
    waarden = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert meting.kwantiel(waarden, 0.5) == 2.0
    assert meting.kwantiel(waarden, 0.25) == 1.0
    assert meting.kwantiel(waarden, 0.1) == pytest.approx(0.4)
    assert meting.kwantiel([7.0], 0.95) == 7.0


def test_verboden_in_top_geeft_alleen_de_verboden_ids_in_de_top_5():
    ranking = ["a", "b", "c", "d", "e", "f"]
    assert meting.verboden_in_top(ranking, ["f", "b", "x"]) == {"b": 2}
    assert meting.verboden_in_top(ranking, []) == {}


def test_samenvatting_van_een_cel():
    cel = meting.samenvatten([1, 6, None, 2])
    assert cel.n == 4
    assert cel.recall == 0.5
    assert cel.recall_interval == meting.wilson(2, 4)
    assert cel.mrr == pytest.approx((1 + 1 / 6 + 0 + 1 / 2) / 4)
    assert cel.mrr_interval == meting.bootstrap_mrr([1, 6, None, 2])


def test_samenvatting_van_een_lege_cel():
    cel = meting.samenvatten([])
    assert (cel.n, cel.recall, cel.mrr) == (0, None, None)
    assert cel.recall_interval == cel.mrr_interval == (0.0, 1.0)


def test_aandeel():
    assert meting.aandeel([True, False, True, True]) == 0.75
    assert meting.aandeel([]) is None
