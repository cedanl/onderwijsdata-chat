"""Labels en waardegetallen van staven blijven leesbaar (#895).

Testrapport 03-11: namen waren afgekapt op circa 35 tekens ("04 Recht, administratie, handel en za…"; de bron zelf
doet dat, zie test_cbs_volledige_titel.py) en bij een korte staaf zette Plotly het getal gedraaid in de staaf.
"""

import plotly.graph_objects as go

from tools.plot import create_plot

_NAAM_45 = "Landbouw, diergeneeskunde en dierverzorging X"
_NAAM_54 = "Landbouw, diergeneeskunde en dierverzorging en bosbouw"
_NAAM_95 = "Landbouw, diergeneeskunde, dierverzorging, bosbouw, visserij en aanverwante gebieden van de sector"


def _plot(namen) -> go.Figure:
    rows = [{"NAAM": naam, "AANTAL": 100 * (len(namen) - i)} for i, naam in enumerate(namen)]
    _, fig = create_plot(rows, "bar", "NAAM", "AANTAL", "T")
    assert fig is not None
    return fig


def test_een_naam_van_40_tot_60_tekens_blijft_staan_zoals_hij_is():
    for naam in (_NAAM_45, _NAAM_54):
        assert 40 <= len(naam) <= 60
        fig = _plot([naam, "Kort"])
        assert naam in fig.data[0].y
        assert fig.data[0].hovertext is None


def test_een_naam_boven_de_grens_breekt_op_een_woordgrens_af_met_de_volledige_naam_in_de_hover():
    fig = _plot([_NAAM_95, "Kort"])
    trace = fig.data[0]
    getoond = next(n for n in trace.y if n.startswith("Landbouw"))
    kop = getoond.removesuffix("…")

    assert getoond.endswith("…") and len(getoond) <= 61
    assert _NAAM_95.startswith(kop)
    assert _NAAM_95[len(kop)] in " ,"  # niet midden in een woord
    assert any(_NAAM_95 in tekst for tekst in trace.hovertext)
    assert trace.hoverinfo == "text"


def test_de_exportrijen_houden_de_volledige_naam():
    fig = _plot([_NAAM_95, "Kort"])

    assert _NAAM_95 in [rij["NAAM"] for rij in fig.layout.meta["data"]]


def test_twee_namen_die_na_afkappen_gelijk_zouden_zijn_blijven_volledig():
    een, twee = _NAAM_95 + " en meer", _NAAM_95 + " en minder"
    fig = _plot([een, twee])

    assert sorted(fig.data[0].y) == sorted([een, twee])


def test_zonder_lange_namen_geen_hovertekst():
    fig = _plot(["Kort", "Ook kort"])

    assert fig.data[0].hovertext is None


def test_een_liggende_staaf_toont_zijn_waarde_nooit_gedraaid():
    fig = _plot([f"Een lange instellingsnaam nummer {i}" for i in range(12)])

    assert fig.data[0].orientation == "h"
    assert fig.data[0].textangle == 0
