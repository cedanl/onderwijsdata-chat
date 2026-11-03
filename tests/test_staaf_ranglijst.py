"""Een staafgrafiek van een ranglijst sorteert op waarde en tekent geen lege categorie (#894).

Testrapport 03-11, vraag 5 ("welke sector is het grootst"): de categorieën stonden in CBS-codevolgorde, de grootste
staaf (109.500) op rij 4, en "Onderwijsrichting onbekend" (0) als lege rij onderaan.
"""

import plotly.graph_objects as go

from tools.plot import create_plot

_SECTOREN = [
    ("01 Onderwijs", 69780),
    ("02 Vormgeving", 36540),
    ("03 Journalistiek", 25320),
    ("04 Recht en handel", 109500),
    ("05 Wiskunde", 6940),
    ("Onderwijsrichting onbekend", 0),
]


def _plot(paren, x="SECTOR", chart_type="bar", **kwargs) -> tuple[str, go.Figure]:
    rows = [{x: naam, "AANTAL": waarde} for naam, waarde in paren]
    tekst, fig = create_plot(rows, chart_type, x, "AANTAL", "T", **kwargs)
    assert fig is not None
    return tekst, fig


def _waarden(fig: go.Figure) -> list:
    trace = fig.data[0]
    return list(trace.x if trace.orientation == "h" else trace.y)


def _namen(fig: go.Figure) -> list:
    trace = fig.data[0]
    return list(trace.y if trace.orientation == "h" else trace.x)


def test_staven_over_onderwijsrichtingen_staan_aflopend_op_waarde():
    _, fig = _plot(_SECTOREN)

    assert _waarden(fig) == [109500, 69780, 36540, 25320, 6940]
    assert _namen(fig)[0] == "04 Recht en handel"


def test_een_categorie_met_nul_krijgt_geen_rij_en_de_uitkomst_zegt_het():
    tekst, fig = _plot(_SECTOREN)

    assert "Onderwijsrichting onbekend" not in _namen(fig)
    assert "Weggelaten" in tekst and "Onderwijsrichting onbekend" in tekst
    assert "5 datapunten" in tekst


def test_de_exportrijen_houden_ook_de_weggelaten_categorie():
    _, fig = _plot(_SECTOREN)

    assert len(fig.layout.meta["data"]) == len(_SECTOREN)


def test_een_lege_waarde_krijgt_ook_geen_rij():
    _, fig = _plot([("A", 5), ("B", None), ("C", 9)])

    assert _namen(fig) == ["C", "A"]


def test_een_tijdreeks_behoudt_zijn_volgorde_en_zijn_nul():
    paren = [("2021/22", 5), ("2022/23", 0), ("2023/24", 9)]
    for chart_type in ("line", "bar"):
        _, fig = _plot(paren, x="STUDIEJAAR", chart_type=chart_type)
        assert _namen(fig) == ["2021/22", "2022/23", "2023/24"]


def test_schooljaren_onder_een_andere_kolomnaam_behouden_hun_volgorde():
    paren = [("2021/22", 5), ("2022/23", 0), ("2023/24", 9)]
    _, fig = _plot(paren, x="PERIODE_TEKST")

    assert _namen(fig) == ["2021/22", "2022/23", "2023/24"]


def test_leeftijdsgroepen_behouden_hun_volgorde():
    paren = [("Jonger dan 20 jaar", 5), ("20 tot 25 jaar", 90), ("25 tot 30 jaar", 40), ("30 jaar of ouder", 0)]
    _, fig = _plot(paren, x="GROEP")

    assert _namen(fig) == [naam for naam, _ in paren]


def test_een_kolomnaam_met_leeftijd_behoudt_zijn_volgorde():
    paren = [("Klein", 5), ("Midden", 90), ("Groot", 40)]
    _, fig = _plot(paren, x="LEEFTIJD")

    assert _namen(fig) == ["Klein", "Midden", "Groot"]


def test_gegroepeerde_staven_blijven_zoals_ze_waren():
    rows = [
        {"SECTOR": "A", "AANTAL": 1, "GESLACHT": "Man"},
        {"SECTOR": "B", "AANTAL": 9, "GESLACHT": "Man"},
        {"SECTOR": "A", "AANTAL": 0, "GESLACHT": "Vrouw"},
        {"SECTOR": "B", "AANTAL": 4, "GESLACHT": "Vrouw"},
    ]
    _, fig = create_plot(rows, "bar", "SECTOR", "AANTAL", "T", color_by="GESLACHT")
    assert fig is not None

    assert [list(t.x) for t in fig.data] == [["A", "B"], ["A", "B"]]


def test_een_uitgelichte_staaf_houdt_zijn_kleur_na_het_sorteren():
    _, fig = _plot([("A", 1), ("B", 9), ("C", 4)], highlight="A")

    kleuren = dict(zip(_namen(fig), fig.data[0].marker.color, strict=True))
    assert kleuren["A"] != kleuren["B"]
    assert kleuren["B"] == kleuren["C"]


def test_alleen_nullen_blijven_getekend():
    _, fig = _plot([("A", 0), ("B", 0)])

    assert sorted(_namen(fig)) == ["A", "B"]
