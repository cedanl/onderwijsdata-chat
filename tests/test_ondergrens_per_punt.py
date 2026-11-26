"""De ondergrens per rij en per punt: in de data-CSV, de grafiek-CSV, de marker, de hover en de figuur (#1257, #1261).

DUO-fixture: twee instellingen over drie jaar, B in 2020 onderdrukt (-1). Opgeteld per jaar is alleen 2020 een
ondergrens. CBS-fixture: hetzelfde met een lege cel ('.', in de tabel NaN). Elke test zet de store zelf op.
"""

import io
import json

import pandas as pd
import pytest

from tools import cbs, duo, fusies, ondergrens, plot, store
from tools.csv_export import naar_csv
from tools.query import query_data
from tools.store import KeyMeta

_DUO = "duo:p01hoinges:0"
_CBS = "cbs:85701NED:0"


@pytest.fixture(autouse=True)
def _schone_store(monkeypatch):
    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: [])
    # De CBS-fixture heeft geen dimensies: elke lege cel is dan onderdrukt (store._cbs_lege_cellen).
    monkeypatch.setitem(cbs._dimensies, "85701NED", [])
    fusies._voorgangers.cache_clear()
    store.clear()
    yield
    store.clear()


def _per_jaar(key: str, bron: str, df: pd.DataFrame) -> str:
    store.put(key, df, KeyMeta(bron=bron, dataset=key.split(":")[1], resource=0, periodekolom="STUDIEJAAR"))
    return json.loads(query_data(key, group_by=["STUDIEJAAR"], aggregate={"AANTAL": "sum"}))["data_key"]


def _duo_per_jaar() -> str:
    df = pd.DataFrame(
        {
            "STUDIEJAAR": [2019, 2019, 2020, 2020, 2021, 2021],
            "INSTELLING": ["A", "B"] * 3,
            "AANTAL": [1000, 234, 1100, -1, 1200, 300],
        }
    )
    return _per_jaar(_DUO, "duo", df)


def _cbs_per_jaar() -> str:
    """Een geladen CBS-reeks met in 2020 een lege cel ('.'): CBS telt over een dimensie niet op, dus de reeks zelf."""
    df = pd.DataFrame({"STUDIEJAAR": ["2019SJ00", "2020SJ00", "2021SJ00"], "AANTAL": [1234.0, None, 1500.0]})
    store.put(_CBS, df, KeyMeta(bron="cbs", dataset="85701NED", resource=0, periodekolom="STUDIEJAAR"))
    return _CBS


def _csv_tabel(tekst: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(tekst), sep=";", comment="#")


# ── #1257: de kolom ondergrens en de '#'-regels in de data-CSV ──


def test_data_csv_heeft_ondergrens_ja_alleen_op_de_rij_met_een_onderdrukte_cel():
    tabel = _csv_tabel(naar_csv(_duo_per_jaar()) or "")
    assert list(tabel.columns) == ["STUDIEJAAR", "AANTAL", "ondergrens"]
    assert dict(zip(tabel["STUDIEJAAR"], tabel["ondergrens"], strict=True)) == {2019: "nee", 2020: "ja", 2021: "nee"}


def test_data_csv_noemt_de_kolom_in_een_kopregel_en_pandas_leest_de_tabel_ongewijzigd():
    tekst = naar_csv(_duo_per_jaar()) or ""
    assert f"# {ondergrens.KOLOMREGEL}" in tekst.splitlines()
    tabel = _csv_tabel(tekst)
    assert tabel["AANTAL"].tolist() == [1234, 1100, 1500]


def test_een_tabel_zonder_onderdrukte_cel_krijgt_geen_extra_kolom():
    store.put(_DUO, pd.DataFrame({"STUDIEJAAR": [2019, 2020], "AANTAL": [5, 6]}), KeyMeta(bron="duo", dataset="x"))
    tekst = naar_csv(_DUO) or ""
    assert "ondergrens" not in tekst


# ── #1261: per punt in de grafiek ──


@pytest.mark.parametrize("maak", [_duo_per_jaar, _cbs_per_jaar], ids=["duo -1", "cbs ."])
@pytest.mark.parametrize("soort", ["line", "bar"])
def test_alleen_het_punt_met_een_onderdrukte_cel_heeft_een_marker(maak, soort):
    key = maak()
    _, fig = plot.create_plot(chart_type=soort, x="STUDIEJAAR", y="AANTAL", title="Studenten", data_key=key)
    assert fig is not None
    cellen = duo.sentinel_cells(key)
    assert cellen is not None
    verwacht = cellen["AANTAL"].reindex(store.get(key).index, fill_value=0).gt(0).tolist()
    trace = fig.data[0]
    if soort == "line":
        gemarkeerd = [s == "circle-open" for s in trace.marker.symbol]
    else:
        gemarkeerd = [bool(s) for s in trace.marker.pattern.shape]
    assert gemarkeerd == verwacht == [False, True, False]


def test_de_hover_zegt_ten_minste_en_het_label_een_groter_dan_of_gelijk():
    _, fig = plot.create_plot(chart_type="line", x="STUDIEJAAR", y="AANTAL", title="T", data_key=_duo_per_jaar())
    assert fig is not None
    trace = fig.data[0]
    assert trace.hovertext[1] == "2020: ten minste 1.100 (onderdrukte cellen)"
    assert trace.hovertext[0] == "2019: 1.234"
    assert list(trace.text) == ["1.234", "≥ 1.100", "1.500"]


def test_de_exportrijen_en_meta_dragen_de_ondergrens():
    _, fig = plot.create_plot(chart_type="line", x="STUDIEJAAR", y="AANTAL", title="T", data_key=_duo_per_jaar())
    assert fig is not None
    meta = fig.layout.meta
    assert [r["ondergrens"] for r in meta["data"]] == ["nee", "ja", "nee"]
    assert meta["ondergrens_rijen"] == [1]
    assert ondergrens.KOLOMREGEL in meta["herkomst"]


def test_een_grafiek_zonder_onderdrukte_cel_heeft_geen_marker_en_geen_kolom():
    store.put(_DUO, pd.DataFrame({"STUDIEJAAR": [2019, 2020], "AANTAL": [5, 6]}), KeyMeta(bron="duo", dataset="x"))
    _, fig = plot.create_plot(chart_type="line", x="STUDIEJAAR", y="AANTAL", title="T", data_key=_DUO)
    assert fig is not None
    assert fig.data[0].marker.symbol is None
    assert "ondergrens" not in fig.layout.meta["data"][0]
    assert "ondergrens_rijen" not in fig.layout.meta


def test_de_bronregel_voor_afdruk_en_rapport_zegt_ten_minste():
    _, fig = plot.create_plot(chart_type="line", x="STUDIEJAAR", y="AANTAL", title="T", data_key=_duo_per_jaar())
    assert fig is not None
    regel = fig.layout.meta["bronregel"]
    assert regel.startswith("Bron: DUO, dataset p01hoinges") and "ten minste" in regel


def test_een_eigen_figuur_op_onderdrukte_data_zegt_dat_de_ondergrens_niet_per_punt_bekend_is():
    import plotly.graph_objects as go

    key = _duo_per_jaar()
    fig = go.Figure(go.Scatter(x=[2019, 2020, 2021], y=[1, 2, 3], mode="lines"))
    plot.eigen_figuurregels(fig, [key])
    assert f"{ondergrens.NIET_PER_PUNT}." in fig.layout.meta["figuurnoten"]
