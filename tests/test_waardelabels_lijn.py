"""Waardelabels van een lijn vallen niet weg aan de rand van het plotvlak (#579, restpunt 5).

Het label van het hoogste punt viel boven het plotvlak weg ("2.350" half afgeknipt naast de tick
"2.500"), en een label op de eerste of laatste x-waarde werd aan de zijkant afgeknipt. De waardeas
loopt door tot boven het hoogste label, en een lijnlabel mag een paar pixels buiten het plotvlak staan.
"""

import pytest

from tools.plot import create_plot, kopruimte


def _lijn(rijen: list[dict], x: str = "JAAR", **kwargs):
    _, fig = create_plot(data=rijen, chart_type="line", x=x, y="N", title="T", **kwargs)
    assert fig is not None
    return fig


JAREN = [{"JAAR": j, "N": n} for j, n in zip(range(2019, 2024), (2350, 2060, 1820, 1560, 1270), strict=True)]


def test_de_waardeas_loopt_door_tot_boven_het_hoogste_label():
    fig = _lijn(JAREN)

    hoog, laag = 2350, 1270
    assert fig.layout.yaxis.autorangeoptions.include == (pytest.approx(hoog + 0.15 * (hoog - laag)),)


def test_de_kopruimte_geldt_voor_alle_reeksen_samen():
    rijen = [{**r, "MAAT": "studenten"} for r in JAREN] + [
        {"JAAR": j, "N": 500, "MAAT": "gediplomeerden"} for j in range(2020, 2024)
    ]
    fig = _lijn(rijen, color_by="MAAT")

    assert fig.layout.yaxis.autorangeoptions.include == (pytest.approx(2350 + 0.15 * (2350 - 500)),)


def test_een_lijnlabel_wordt_aan_de_rand_niet_afgeknipt():
    fig = _lijn(JAREN)

    assert fig.data[0].cliponaxis is False


def test_een_vlakke_lijn_krijgt_ook_ruimte_boven_het_label():
    fig = _lijn([{"JAAR": j, "N": 400} for j in range(2019, 2023)])

    assert fig.layout.yaxis.autorangeoptions.include[0] > 400


def test_zonder_waardelabels_blijft_de_as_zoals_plotly_hem_kiest():
    """Boven twintig punten vervallen de labels (#22)."""
    fig = _lijn([{"JAAR": j, "N": j} for j in range(2000, 2025)])

    assert fig.data[0].text is None
    assert fig.layout.yaxis.autorangeoptions.include is None
    assert fig.data[0].cliponaxis is None


def test_staven_houden_hun_eigen_as():
    _, fig = create_plot(data=JAREN, chart_type="bar", x="JAAR", y="N", title="T")
    assert fig is not None

    assert fig.layout.yaxis.autorangeoptions.include is None


def test_alleen_reeksen_met_labels_tellen():
    kop = kopruimte([{"y": [5, 99], "text": None}, {"y": [1, 9], "text": ["1", "9"]}])

    assert kop == pytest.approx(9 + 0.15 * 8)


def test_zonder_getallen_geen_kopruimte():
    assert kopruimte([{"y": [None, float("nan")], "text": ["", ""]}]) is None
    assert kopruimte([]) is None
