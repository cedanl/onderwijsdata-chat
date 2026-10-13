"""Een grafiek met veel of lange categorieën blijft leesbaar in chat en rapport.

Testvraag 13-10: "Hoeveel gediplomeerden levert de VU af ten opzichte van de andere
universiteiten?" gaf staande staven voor 18 universiteiten. De namen (tot 38 tekens)
stonden 90° gedraaid onder een plotvlak van ~60px hoog, en een legenda met 18 grijze
vakjes (color_by was de x-kolom, alleen om de VU uit te lichten) nam een derde van de
breedte. Liggende staven met de naam als gewone tekst, een hoogte die meegroeit met het
aantal staven en geen legenda die de as herhaalt, lossen dat op.
"""

import plotly.graph_objects as go
import pytest

from tools.plot import create_plot, leesbare_titels

_UNIVERSITEITEN = [
    ("Universiteit van Amsterdam", 14773),
    ("Universiteit Utrecht", 12130),
    ("Erasmus Universiteit Rotterdam", 11211),
    ("Universiteit Leiden", 10728),
    ("Rijksuniversiteit Groningen", 10528),
    ("Vrije Universiteit Amsterdam", 10499),
    ("Universiteit Maastricht", 7717),
    ("Technische Universiteit Delft", 7119),
    ("Radboud Universiteit Nijmegen", 7047),
    ("Tilburg University", 6809),
    ("Wageningen University", 3886),
    ("Universiteit Twente", 3408),
    ("Technische Universiteit Eindhoven", 3405),
    ("transnationale Universiteit Limburg", 244),
    ("Universiteit voor Humanistiek", 137),
    ("Protestantse Theologische Universiteit", 56),
    ("Theologische Universiteit Apeldoorn", 20),
    ("Theologische Universiteit Utrecht", 18),
]
_ROWS = [{"INSTELLING": naam, "AANTAL": aantal} for naam, aantal in _UNIVERSITEITEN]
_VU = "Vrije Universiteit Amsterdam"


def _plot(rows=_ROWS, chart_type: str = "bar", x: str = "INSTELLING", **kwargs) -> go.Figure:
    _, fig = create_plot(rows, chart_type, x, "AANTAL", "T", **kwargs)
    assert fig is not None
    return fig


class TestLiggendeStaven:
    def test_veel_lange_categorieen_worden_liggende_staven(self):
        trace = _plot().data[0]
        assert trace.orientation == "h"
        assert list(trace.y) == [naam for naam, _ in _UNIVERSITEITEN]
        assert list(trace.x) == [aantal for _, aantal in _UNIVERSITEITEN]

    def test_eerste_rij_staat_bovenaan(self):
        # De agent sorteert de rijen; liggend zet Plotly de eerste categorie onderaan.
        assert _plot().layout.yaxis.autorange == "reversed"

    def test_de_waardeas_ligt_onder_en_de_namen_hebben_geen_astitel(self):
        fig = _plot()
        assert fig.layout.xaxis.title.text == "Aantal"
        assert fig.layout.xaxis.tickformat == ","  # de waardeas houdt de duizendtalpunt
        assert not fig.layout.yaxis.title.text

    def test_waardelabels_staan_in_de_staaf_als_ze_passen_en_worden_niet_afgesneden(self):
        trace = _plot(rows=_ROWS[:6]).data[0]
        assert trace.textposition == "auto"
        assert trace.insidetextanchor == "end"
        assert trace.cliponaxis is False

    def test_met_waardelabels_vervalt_de_waardeas(self):
        xaxis = _plot(rows=_ROWS[:6]).layout.xaxis
        assert xaxis.showticklabels is False
        assert xaxis.showgrid is False

    def test_zonder_waardelabels_blijft_de_waardeas(self):
        rows = [{"INSTELLING": f"Instelling nummer {i}", "AANTAL": i} for i in range(30)]
        assert _plot(rows=rows).layout.xaxis.showticklabels is not False

    def test_hoogte_groeit_mee_met_het_aantal_staven(self):
        laag = _plot(rows=_ROWS[:10]).layout.height
        hoog = _plot().layout.height
        assert laag >= 340
        assert hoog > laag

    def test_hoogte_heeft_een_plafond(self):
        rows = [{"INSTELLING": f"Instelling nummer {i}", "AANTAL": i} for i in range(200)]
        assert _plot(rows=rows).layout.height <= 1200

    def test_lange_labels_zijn_ook_bij_weinig_categorieen_liggend(self):
        trace = _plot(rows=_ROWS[:3]).data[0]
        assert trace.orientation == "h"

    def test_weinig_korte_categorieen_blijven_staand(self):
        rows = [{"GESLACHT": g, "AANTAL": n} for g, n in (("Man", 10), ("Vrouw", 12), ("Onbekend", 1))]
        fig = _plot(rows=rows, x="GESLACHT")
        assert fig.data[0].orientation in (None, "v")
        assert fig.layout.height is None

    def test_tijdas_blijft_staand(self):
        rows = [{"JAAR": str(2000 + i), "AANTAL": i} for i in range(20)]
        assert _plot(rows=rows, x="JAAR").data[0].orientation in (None, "v")

    def test_getallen_op_de_categorieas_blijven_staand(self):
        # Leeftijd, cohort, niveau als getal: een verdeling lees je van links naar rechts.
        rows = [{"LEEFTIJD": 16 + i, "AANTAL": i} for i in range(20)]
        assert _plot(rows=rows, x="LEEFTIJD").data[0].orientation in (None, "v")

    @pytest.mark.parametrize("chart_type", ["line", "scatter"])
    def test_alleen_staafgrafieken_liggen(self, chart_type):
        fig = _plot(chart_type=chart_type)
        assert fig.data[0].orientation in (None, "v")

    def test_gegroepeerde_staven_liggen_ook_en_krijgen_ruimte_per_groep(self):
        rows = [
            {"INSTELLING": naam, "AANTAL": aantal, "GESLACHT": g}
            for naam, aantal in _UNIVERSITEITEN[:10]
            for g in ("Man", "Vrouw")
        ]
        fig = _plot(rows=rows, color_by="GESLACHT")
        assert {t.orientation for t in fig.data} == {"h"}
        assert fig.layout.height > _plot(rows=_ROWS[:10]).layout.height


class TestUitlichtenZonderLegenda:
    def test_color_by_gelijk_aan_x_geeft_een_reeks_zonder_legenda(self):
        fig = _plot(color_by="INSTELLING", highlight=_VU)
        assert len(fig.data) == 1
        assert fig.layout.showlegend is False

    def test_de_uitgelichte_staaf_krijgt_de_accentkleur_de_rest_grijs(self):
        kleuren = list(_plot(color_by="INSTELLING", highlight=_VU).data[0].marker.color)
        namen = [naam for naam, _ in _UNIVERSITEITEN]
        accent = kleuren[namen.index(_VU)]
        assert accent != "#B0B0B0"
        assert [k for i, k in enumerate(kleuren) if i != namen.index(_VU)] == ["#B0B0B0"] * 17

    def test_highlight_werkt_ook_zonder_color_by(self):
        fig = _plot(highlight=_VU)
        assert len(fig.data) == 1
        assert len(set(fig.data[0].marker.color)) == 2

    def test_color_by_gelijk_aan_x_zonder_highlight_is_een_kleur(self):
        fig = _plot(color_by="INSTELLING")
        assert len(fig.data) == 1
        assert isinstance(fig.data[0].marker.color, str)

    def test_echte_groepen_houden_hun_legenda(self):
        rows = [{"INSTELLING": "UvA", "AANTAL": 1, "GESLACHT": g} for g in ("Man", "Vrouw")]
        fig = _plot(rows=rows, color_by="GESLACHT")
        assert len(fig.data) == 2
        assert fig.layout.showlegend is not False

    def test_exportrijen_blijven_de_bronrijen(self):
        fig = _plot(color_by="INSTELLING", highlight=_VU)
        assert fig.layout.meta["data"] == _ROWS
        assert fig.layout.meta["x"] == "INSTELLING"


class TestLegendaOnder:
    """Rechts naast de grafiek kostte de legenda een derde van de breedte, op een telefoon bijna
    alles; boven botst hij met de titel. Onder de x-as krijgt het plotvlak de volle breedte."""

    def test_legenda_staat_horizontaal_onder_de_grafiek(self):
        rows = [{"JAAR": str(j), "AANTAL": j, "SECTOR": s} for j in (2023, 2024) for s in ("Zorg", "Techniek")]
        legend = _plot(rows=rows, chart_type="line", x="JAAR", color_by="SECTOR").layout.legend
        assert legend.orientation == "h"
        assert (legend.yref, legend.y, legend.yanchor) == ("container", 0, "bottom")

    def test_eigen_figuur_krijgt_de_legenda_ook_onder(self):
        fig = go.Figure([go.Scatter(x=[1, 2], y=[3, 4], name="a"), go.Scatter(x=[1, 2], y=[4, 5], name="b")])
        legend = leesbare_titels(fig, None).layout.legend
        assert legend.orientation == "h"
        assert legend.yref == "container"

    def test_eigen_figuur_met_een_eigen_legendaplek_houdt_die(self):
        fig = go.Figure([go.Scatter(x=[1, 2], y=[3, 4], name="a")], layout={"legend": {"x": 0.02, "y": 0.98}})
        legend = leesbare_titels(fig, None).layout.legend
        assert (legend.x, legend.y, legend.orientation) == (0.02, 0.98, None)
