"""Trendbreuken in de grafiek: CBS-definitiebreuken en fusies als gestippelde lijn met label en bron (#1262).

CBS-fixture: een reeks 2018-2022 met een definitiebreuk "vanaf 2020" in de tabeltoelichting (cbs_meta.metadata,
gepatcht). DUO-fixture: Firda (08PG) met de fusie van Friesland College per 1-8-2023, de stap uit #728; de vaste regel
komt uit `fusies.in_reeks` met een gepatchte RIO, zoals bij het afleiden van de selectie.
"""

import pandas as pd
import pytest
from onderwijsbronnen.rio import Stap

from tools import cbs_meta, fusies, plot, store, trendbreuken
from tools.store import KeyMeta

_CBS = "cbs:85701NED:0"
_DUO = "duo:p01hoinges:0"
_BREUK = "Vanaf 2020 telt CBS ook de studenten aan private instellingen mee."
_FRIESLAND = Stap(
    "25LG", "Regionaal Opleidingen Centrum Friesland College", "volledig", "2023-08-01", via="08PG", wet="WEB"
)


@pytest.fixture(autouse=True)
def _schone_store():
    store.clear()
    yield
    store.clear()


def _cbs_reeks(monkeypatch, passages: list[str], jaren=range(2018, 2023)) -> str:
    monkeypatch.setattr(cbs_meta, "metadata", lambda dataset_id: {"methodiek": {"definitiebreuken": passages}})
    df = pd.DataFrame({"Perioden": list(jaren), "Studenten": [100 + 10 * i for i, _ in enumerate(jaren)]})
    store.put(_CBS, df, KeyMeta(bron="cbs", dataset="85701NED", resource=0))
    return _CBS


def _duo_reeks(monkeypatch, jaren=(2021, 2022, 2023, 2024)) -> str:
    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: [_FRIESLAND])
    fusies._voorgangers.cache_clear()
    regels = fusies.in_reeks({"08PG": "Firda"}, tuple(jaren))
    df = pd.DataFrame({"STUDIEJAAR": list(jaren), "AANTAL": [9000 + i for i, _ in enumerate(jaren)]})
    store.put(_DUO, df, KeyMeta(bron="duo", dataset="p01hoinges", resource=0, fusies=regels))
    return _DUO


def _lijn(key: str, x: str, y: str):
    _, fig = plot.create_plot(chart_type="line", x=x, y=y, title="Reeks", data_key=key)
    assert fig is not None
    return fig


def _breuklijnen(fig) -> list:
    return [s for s in fig.layout.shapes if s.name == trendbreuken.NAAM]


def _breuklabels(fig) -> list:
    return [a for a in fig.layout.annotations if a.name == trendbreuken.NAAM]


def _bronnen_kloppen(fig) -> None:
    """Elke lijn heeft een breuk in de meta, met bron en passage: geen lijn zonder bron."""
    meta = {b["x"]: b for b in fig.layout.meta.get("trendbreuken", []) if "x" in b}
    for lijn in _breuklijnen(fig):
        assert lijn.x0 in meta, f"lijn op {lijn.x0} zonder bron in de meta"
        assert meta[lijn.x0]["bron"] and meta[lijn.x0]["passage"]


def test_cbs_definitiebreuk_geeft_een_gestippelde_lijn_met_label_en_de_passage_in_de_noot(monkeypatch):
    fig = _lijn(_cbs_reeks(monkeypatch, [_BREUK]), "Perioden", "Studenten")
    [lijn] = _breuklijnen(fig)
    assert lijn.x0 == lijn.x1 == 2020
    assert lijn.line.dash == "dot" and lijn.yref == "paper"
    [label] = _breuklabels(fig)
    assert label.x == 2020 and "definitiebreuk 2020" in label.text
    assert any(_BREUK in noot for noot in fig.layout.meta["figuurnoten"])
    _bronnen_kloppen(fig)


def test_de_breuk_staat_als_regel_in_de_herkomst_dus_in_de_csv_kop(monkeypatch):
    fig = _lijn(_cbs_reeks(monkeypatch, [_BREUK]), "Perioden", "Studenten")
    assert any(r.startswith("Trendbreuk vanaf 2020 (CBS") and _BREUK in r for r in fig.layout.meta["herkomst"])


def test_fusie_geeft_een_lijn_bij_het_eerste_jaar_na_de_fusie_met_de_voorganger(monkeypatch):
    fig = _lijn(_duo_reeks(monkeypatch), "STUDIEJAAR", "AANTAL")
    [lijn] = _breuklijnen(fig)
    # Per 1-8-2023: de telling van 1-10-2023 is de eerste na de fusie; 2021 en 2022 tellen de voorganger mee.
    assert lijn.x0 == 2023
    [label] = _breuklabels(fig)
    assert "Friesland College" in label.text and "25LG" in label.text
    _bronnen_kloppen(fig)


@pytest.mark.parametrize(("passage", "jaren"), [(_BREUK, range(2021, 2024)), (_BREUK, range(2015, 2020))])
def test_een_breuk_buiten_de_reeks_krijgt_geen_lijn(monkeypatch, passage, jaren):
    """Ook niet op het eerste jaar: dan begint de reeks na de breuk en verandert er binnen de reeks niets."""
    fig = _lijn(_cbs_reeks(monkeypatch, [passage], jaren), "Perioden", "Studenten")
    assert _breuklijnen(fig) == []
    assert "figuurnoten" not in fig.layout.meta


def test_een_fusie_buiten_de_reeks_krijgt_geen_lijn(monkeypatch):
    fig = _lijn(_duo_reeks(monkeypatch, (2024, 2025)), "STUDIEJAAR", "AANTAL")
    assert _breuklijnen(fig) == []


def test_een_breuk_zonder_jaar_staat_alleen_in_de_noot(monkeypatch):
    passage = "De definitie van een student is gewijzigd."
    fig = _lijn(_cbs_reeks(monkeypatch, [passage]), "Perioden", "Studenten")
    assert _breuklijnen(fig) == []
    assert any(passage in noot for noot in fig.layout.meta["figuurnoten"])


def test_een_passage_over_voorlopige_cijfers_is_geen_breuk(monkeypatch):
    passage = "De cijfers over de studiejaren vanaf 2019/'20 zijn definitief en die over 2021/'22 zijn voorlopig."
    fig = _lijn(_cbs_reeks(monkeypatch, [passage]), "Perioden", "Studenten")
    assert _breuklijnen(fig) == []
    assert "figuurnoten" not in fig.layout.meta


def test_elke_breuk_in_de_reeks_heeft_een_lijn(monkeypatch):
    """Twee breuken in één passage (85701NED: vanaf 2015/'16 en vanaf 2016/'17): elk een lijn, geen ontbreekt."""
    passage = "De gegevens zijn vanaf 2019/'20 inclusief X en vanaf 2021/'22 ook inclusief Y."
    fig = _lijn(_cbs_reeks(monkeypatch, [passage]), "Perioden", "Studenten")
    assert sorted(lijn.x0 for lijn in _breuklijnen(fig)) == [2019, 2021]
    _bronnen_kloppen(fig)


def test_een_staafgrafiek_per_instelling_krijgt_geen_lijn(monkeypatch):
    _cbs_reeks(monkeypatch, [_BREUK])
    df = pd.DataFrame({"Instelling": ["A", "B"], "Studenten": [1, 2]})
    store.put("cbs:85701NED:1", df, KeyMeta(bron="cbs", dataset="85701NED", resource=1))
    _, fig = plot.create_plot(chart_type="bar", x="Instelling", y="Studenten", title="T", data_key="cbs:85701NED:1")
    assert fig is not None and _breuklijnen(fig) == []
