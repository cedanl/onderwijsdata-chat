"""Eerlijke grafiekregels voor elke figuur, create_plot en eigen figuren (#1264).

Staven vanaf nul, geen tweede y-as op één plotvlak, de afgekapte-astitel op een lijn die niet bij nul begint, overlay
alleen doorschijnend, en een vaste kleur per reeks die het WCAG-contrast haalt.
"""

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pytest
from plotly.subplots import make_subplots

from tools import grafiekregels, plot, store, trendbreuken
from tools.analysis import run_analysis
from tools.store import KeyMeta

_KEY = "test:grafiek"


@pytest.fixture(autouse=True)
def _schone_store():
    store.clear()
    yield
    store.clear()


def _bron(rows: list[dict]) -> str:
    store.put(_KEY, pd.DataFrame(rows), KeyMeta(bron="test", dataset=_KEY, volledig=True))
    return _KEY


_REEKS = [{"JAAR": j, "N": 150 + 10 * i} for i, j in enumerate(range(2019, 2024))]
_GROEPEN = [
    {"JAAR": j, "BRIN": brin, "N": n}
    for j in (2022, 2023)
    for brin, n in (("21PB", 500), ("00IC", 400), ("25LG", 300), ("30RA", 200))
]


# ── 1. staven vanaf nul ──


def test_eigen_staafgrafiek_met_range_zonder_nul_gaat_naar_nul_met_een_noot():
    fig = go.Figure(go.Bar(x=["a", "b"], y=[150, 180]))
    fig.update_layout(yaxis={"range": [100, 200]})
    plot.eigen_figuurregels(fig, [])
    assert tuple(fig.layout.yaxis.range) == (0, 200)
    assert grafiekregels.NOOT_NUL in fig.layout.meta["figuurnoten"]


def test_liggende_staven_corrigeren_de_x_as():
    fig = go.Figure(go.Bar(y=["a", "b"], x=[150, 180], orientation="h"))
    fig.update_layout(xaxis={"range": [100, 200]})
    grafiekregels.controleer(fig)
    assert tuple(fig.layout.xaxis.range) == (0, 200)


def test_run_analysis_corrigeert_de_staven_en_zegt_het_in_het_toolresultaat():
    _bron(_REEKS)
    uit = run_analysis(
        code="figure = px.bar(df, x='JAAR', y='N')\nfigure.update_yaxes(range=[100, 200])\nresult = {'ok': True}",
        data_key=_KEY,
    )
    assert isinstance(uit, tuple), uit
    text, fig = uit
    assert min(fig.layout.yaxis.range) == 0
    assert grafiekregels.NOOT_NUL in json.loads(text)["grafiek"]


# ── 2. geen tweede y-as ──


def test_eigen_figuur_met_een_tweede_y_as_wordt_geweigerd_met_de_vaste_melding():
    fig = go.Figure([go.Scatter(x=[1, 2], y=[1, 2]), go.Bar(x=[1, 2], y=[300, 400], yaxis="y2")])
    fig.update_layout(yaxis2={"overlaying": "y", "side": "right"})
    with pytest.raises(grafiekregels.TweeAssen) as fout:
        plot.eigen_figuurregels(fig, [])
    assert "twee grafieken naast elkaar" in str(fout.value)


def test_yaxis2_op_hetzelfde_plotvlak_zonder_overlaying_wordt_ook_geweigerd():
    fig = go.Figure([go.Scatter(x=[1, 2], y=[1, 2]), go.Scatter(x=[1, 2], y=[3, 4], yaxis="y2")])
    fig.update_layout(yaxis2={"side": "right"})
    assert grafiekregels.twee_y_assen(fig)


@pytest.mark.parametrize(("rijen", "kolommen"), [(2, 1), (1, 2)])
def test_subplots_onder_of_naast_elkaar_mogen(rijen, kolommen):
    fig = make_subplots(rows=rijen, cols=kolommen)
    fig.add_trace(go.Bar(x=[1, 2], y=[1, 2]), row=1, col=1)
    fig.add_trace(go.Bar(x=[1, 2], y=[3, 4]), row=rijen, col=kolommen)
    assert not grafiekregels.twee_y_assen(fig)


def test_run_analysis_met_een_tweede_y_as_geeft_geen_figuur_maar_de_melding():
    _bron(_REEKS)
    code = (
        "figure = go.Figure([go.Scatter(x=df['JAAR'], y=df['N']), go.Bar(x=df['JAAR'], y=df['N'], yaxis='y2')])\n"
        "figure.update_layout(yaxis2=dict(overlaying='y', side='right'))\nresult = {'ok': True}"
    )
    uit = run_analysis(code=code, data_key=_KEY)
    assert isinstance(uit, str)
    assert grafiekregels.TWEE_ASSEN in json.loads(uit)["grafiek"]


# ── 3. vaste kleur per reeks ──


def _kleuren(rows: list[dict], **kwargs) -> dict[str, str]:
    _, fig = plot.create_plot(
        chart_type="line", x="JAAR", y="N", title="T", color_by="BRIN", data_key=_bron(rows), **kwargs
    )
    assert fig is not None
    return {t.name: t.line.color for t in fig.data}


def test_dezelfde_instelling_houdt_haar_kleur_in_een_andere_reeksvolgorde():
    voor = _kleuren(_GROEPEN)
    na = _kleuren(list(reversed(_GROEPEN)))
    assert voor == na
    assert len(set(voor.values())) == len(voor), "twee reeksen met dezelfde kleur"


def test_de_kleur_hangt_aan_de_code_niet_aan_de_plek():
    alleen_twee = [r for r in _GROEPEN if r["BRIN"] in ("21PB", "25LG")]
    assert plot.reekskleuren(["21PB", "25LG"]) == plot.reekskleuren(["25LG", "21PB"])
    assert set(_kleuren(alleen_twee).values()) <= set(plot._REEKSPALET)


def test_de_eigen_instelling_houdt_de_accentkleur():
    kleuren = _kleuren(_GROEPEN, highlight="25LG")
    assert kleuren["25LG"] == plot._ACCENT
    assert plot._ACCENT not in plot._REEKSPALET
    assert {k for k, v in kleuren.items() if v == plot._ACCENT} == {"25LG"}


# ── 4. betrouwbaarheid: een set figuren volgt de regels ──


def _create_plot_figuren() -> list[go.Figure]:
    figuren = []
    lange_namen = [{"NAAM": f"Instelling met een lange naam {i}", "N": i + 1} for i in range(12)]
    opgaven: list[tuple[str, list[dict], str | None, bool | None]] = [
        ("bar", _REEKS, None, None),
        ("line", _REEKS, None, None),
        ("line", _REEKS, None, False),
        ("line", _GROEPEN, "BRIN", None),
        ("bar", _GROEPEN, "BRIN", None),
        ("bar", lange_namen, None, None),
    ]
    for soort, rows, groep, vanaf_nul in opgaven:
        x = "NAAM" if "NAAM" in rows[0] else "JAAR"
        _, fig = plot.create_plot(
            chart_type=soort, x=x, y="N", title="T", data_key=_bron(rows), color_by=groep, y_vanaf_nul=vanaf_nul
        )
        assert fig is not None
        figuren.append(fig)
    return figuren


def _eigen_figuren() -> list[go.Figure]:
    df = pd.DataFrame(_REEKS)
    bar = px.bar(df, x="JAAR", y="N")
    bar.update_yaxes(range=[100, 200])
    lijn = px.line(df, x="JAAR", y="N")
    lijn_range = px.line(df, x="JAAR", y="N")
    lijn_range.update_yaxes(range=[140, 200])
    overlay = go.Figure([go.Bar(x=[1, 2], y=[3, 4]), go.Bar(x=[1, 2], y=[2, 5])])
    overlay.update_layout(barmode="overlay")
    figuren = [bar, lijn, lijn_range, overlay]
    for fig in figuren:
        plot.eigen_figuurregels(plot.leesbare_titels(plot.with_export_rows(fig), None), [])
    return figuren


def test_elke_figuur_volgt_de_grafiekregels():
    for fig in [*_create_plot_figuren(), *_eigen_figuren()]:
        assert grafiekregels.overtredingen(fig) == [], fig.layout.title.text


@pytest.mark.parametrize(
    ("maak", "fout"),
    [
        (lambda: go.Figure(go.Bar(x=[1], y=[5]), layout={"yaxis": {"range": [2, 9]}}), "staven zonder nul"),
        (lambda: go.Figure(go.Scatter(x=[1, 2], y=[5, 6], mode="lines")), "afgekapte lijnas"),
        (
            lambda: go.Figure([go.Bar(x=[1], y=[1]), go.Bar(x=[1], y=[2])], layout={"barmode": "overlay"}),
            "overlay",
        ),
        (
            lambda: go.Figure(
                [go.Scatter(x=[1], y=[1]), go.Scatter(x=[1], y=[2], yaxis="y2")], layout={"yaxis2": {"overlaying": "y"}}
            ),
            "twee y-assen",
        ),
    ],
)
def test_de_controle_vindt_een_overtreding(maak, fout):
    """De controle zelf faalt niet stil: elke overtreding wordt gevonden (anders test de lus hierboven niets)."""
    assert any(fout in o for o in grafiekregels.overtredingen(maak()))


def test_overlay_met_doorschijnende_staven_blijft_overlay():
    fig = go.Figure([go.Histogram(x=[1, 2], opacity=0.6), go.Histogram(x=[2, 3], opacity=0.6)])
    fig.update_layout(barmode="overlay")
    assert grafiekregels.controleer(fig) == [] and fig.layout.barmode == "overlay"


# ── 5. contrast in licht en donker ──


def _luminantie(kleur: str) -> float:
    kanalen = [int(kleur[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineair = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in kanalen]
    return 0.2126 * lineair[0] + 0.7152 * lineair[1] + 0.0722 * lineair[2]


def _contrast(a: str, b: str) -> float:
    licht, donker = sorted((_luminantie(a), _luminantie(b)), reverse=True)
    return (licht + 0.05) / (donker + 0.05)


# Licht: de chat (#fff) en het rapport (#F9FAFB); donker: de chat (#1E293B, figureLayout.js) en het rapport (#111827).
_ACHTERGRONDEN = ["#FFFFFF", "#F9FAFB", "#1E293B", "#111827"]


@pytest.mark.parametrize("kleur", [*plot._PALETTE, plot._HIGHLIGHT_GREY, trendbreuken.KLEUR])
@pytest.mark.parametrize("achtergrond", _ACHTERGRONDEN)
def test_elke_grafiekkleur_haalt_3_op_1_contrast(kleur, achtergrond):
    """WCAG 2.2 AA, 1.4.11 (niet-tekstueel contrast): 3:1 tegen de achtergrond, in licht en donker."""
    assert _contrast(kleur, achtergrond) >= 3, f"{kleur} op {achtergrond}: {_contrast(kleur, achtergrond):.2f}"
