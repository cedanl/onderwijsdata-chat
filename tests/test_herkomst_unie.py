"""De herkomst van een eigen berekening is die van elke tabel die ze las, niet alleen van de eerste (#977).

Een koppeling van de Studiekeuzedatabase (LCSK) met DUO leidde haar key af van de eerste gelezen tabel. Stond DUO
vooraan en kwam SKDB via `store_get`, dan droeg het bestand alleen de DUO-regels: de verplichte zin van LCSK, de
versie en de link ontbraken, terwijl de rijen NSE-waarden bevatten. Er staat geen data van LCSK in de repo;
`onderwijsbronnen.skdb.proefbestand` bouwt een export met dezelfde vorm en verzonnen getallen.
"""

import json
from dataclasses import replace
from datetime import timedelta

import pandas as pd
import plotly.io as pio
import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from data import instellingen
from tools import store, studiekeuze
from tools.analysis import run_analysis
from tools.csv_export import naar_csv
from tools.exportnoten import ONVOLLEDIG_EXPORT, herkomstregels
from tools.plot import create_plot
from tools.query import query_data
from tools.store import KeyMeta

_DUO = "duo:p01hoinges:0"
_MD5 = "0123abcd" * 4
_DUO_BRON = "bron: DUO, dataset p01hoinges, resource 0"


@pytest.fixture(autouse=True)
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(
        instellingen,
        "instellingsprofiel",
        lambda naam: (
            {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"}
            if naam.lower() in ("hu", "hogeschool utrecht")
            else None
        ),
    )
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


def _skdb() -> str:
    """De NSE van HU-ICT voltijd: één rij met brin 25DW en croho 30020."""
    return json.loads(studiekeuze.get_studiekeuze(instelling="HU", opleiding="ICT", vorm="voltijd"))["data_key"]


def _duo() -> str:
    df = pd.DataFrame({"INSTELLINGSCODE": ["25DW", "21PD"], "CROHO": [30020, 30020], "AANTAL": [120, 80]})
    store.put(_DUO, df, KeyMeta(bron="duo", dataset="p01hoinges", resource=0, bronhash=_MD5))
    return _DUO


def _meta(key: str) -> KeyMeta:
    known = store.meta(key)
    assert known is not None, key
    return known


def _analyse(code: str, data_key: str | None = None) -> str:
    uit = run_analysis(code=code, data_key=data_key)
    assert isinstance(uit, str), uit
    return json.loads(uit)["data_key"]


_KOPPELKOLOMMEN = {"skdb": "['brin', 'croho']", "duo": "['INSTELLINGSCODE', 'CROHO']"}


def _koppeling(eerst: str, dan: str) -> str:
    """De koppeling met `eerst` als df en `dan` via store_get, zoals het model haar schrijft."""
    links, rechts = (_KOPPELKOLOMMEN[_meta(k).bron] for k in (eerst, dan))
    code = (
        f"ander = store_get('{dan}')\n"
        f"m = df.merge(ander, left_on={links}, right_on={rechts})\n"
        "result = m[['brin', 'croho', 'nse_oordeel', 'AANTAL']].to_dict(orient='records')"
    )
    return _analyse(code, eerst)


def _lcsk(regels: list[str]) -> list[str]:
    return [r for r in regels if skdb.VERPLICHTE_ZIN in r]


def _draagt_beide_bronnen(regels: list[str], skdb_key: str) -> None:
    (skdb_bron,) = store.herkomst(skdb_key)[:1]
    (lcsk,) = _lcsk(regels)  # precies één keer, ook als de tabel langs twee wegen gelezen is
    assert lcsk == skdb_bron
    assert "versie 26.6" in lcsk and skdb.DOCUMENTATIE in lcsk
    assert regels.count(_DUO_BRON) == 1
    assert sum(_MD5 in r for r in regels) == 1


@pytest.mark.parametrize("volgorde", ["skdb_eerst", "duo_eerst"])
def test_een_koppeling_draagt_de_herkomst_van_beide_bronnen(volgorde):
    skdb_key, duo_key = _skdb(), _duo()
    eerst, dan = (skdb_key, duo_key) if volgorde == "skdb_eerst" else (duo_key, skdb_key)

    key = _koppeling(eerst, dan)

    regels = herkomstregels(key)
    _draagt_beide_bronnen(regels, skdb_key)
    assert "selectie: eigen berekening (run_analysis)" in regels
    # Twee brontabellen: elke hash zegt bij welke dataset hij hoort.
    assert any(r.startswith("md5 van het DUO-bestand (p01hoinges): ") for r in regels)
    assert any(r.startswith(f"inhoudshash van de brontabel ({studiekeuze.DATASET}): ") for r in regels)


def test_een_koppeling_die_alles_via_store_get_leest():
    skdb_key, duo_key = _skdb(), _duo()
    code = (
        f"duo = store_get('{duo_key}')\nnse = store_get('{skdb_key}')\n"
        "m = duo.merge(nse, left_on=['INSTELLINGSCODE', 'CROHO'], right_on=['brin', 'croho'])\n"
        "result = m[['brin', 'croho', 'nse_oordeel', 'AANTAL']].to_dict(orient='records')"
    )

    _draagt_beide_bronnen(herkomstregels(_analyse(code)), skdb_key)


def test_de_csv_van_de_koppeling_noemt_lcsk_ook_als_duo_vooraan_staat():
    skdb_key = _skdb()
    csv = naar_csv(_koppeling(_duo(), skdb_key)) or ""

    kop = [r.removeprefix("# ") for r in csv.splitlines() if r.startswith("# ")]
    _draagt_beide_bronnen(kop, skdb_key)


def test_een_bestand_met_alleen_skdb_inhoud_en_een_duo_kop_noemt_lcsk():
    """De rijen zijn NSE-waarden, de key is afgeleid van DUO: de kop van het bestand is niet de bron van de inhoud."""
    skdb_key, duo_key = _skdb(), _duo()
    code = (
        f"nse = store_get('{skdb_key}')\n"
        "m = df.merge(nse, left_on=['INSTELLINGSCODE', 'CROHO'], right_on=['brin', 'croho'])\n"
        "result = m[['nse_oordeel', 'nse_oordeel_landelijk']].to_dict(orient='records')"
    )
    key = _analyse(code, duo_key)

    assert _meta(key).bron == "duo"
    assert _lcsk(herkomstregels(key)) == _lcsk(store.herkomst(skdb_key))


def test_meer_dan_een_afgeleide_stap_houdt_elke_bron_en_elke_selectie():
    """Een selectie op SKDB, een koppeling met DUO vooraan, een selectie daarop en nog een berekening."""
    skdb_key, duo_key = _skdb(), _duo()
    nse_sel = json.loads(query_data(skdb_key, filters={"brin": "25DW"}))["data_key"]
    koppeling = _koppeling(duo_key, nse_sel)
    sel = json.loads(query_data(koppeling, filters={"AANTAL__gte": 100}))["data_key"]
    som = _analyse("result = df.groupby('brin', as_index=False)['AANTAL'].sum().to_dict(orient='records')", sel)

    regels = herkomstregels(som)
    _draagt_beide_bronnen(regels, skdb_key)
    assert 'selectie: filters {"brin": "25DW"}' in regels
    assert 'selectie: filters {"AANTAL__gte": 100}' in regels
    assert regels.count("selectie: eigen berekening (run_analysis)") == 2
    # Oudste eerst: elke bron vóór de stappen die erop volgen, de laatste berekening als laatste stap.
    assert regels.index(_DUO_BRON) < regels.index('selectie: filters {"AANTAL__gte": 100}')
    assert regels.index(_lcsk(regels)[0]) < regels.index('selectie: filters {"brin": "25DW"}')
    stappen = [r for r in regels if r.startswith("selectie: ")]
    assert stappen[-1] == "selectie: eigen berekening (run_analysis)"


def test_de_grafiek_en_de_antwoordselectie_op_een_koppeling_noemen_lcsk():
    skdb_key = _skdb()
    koppeling = _koppeling(_duo(), skdb_key)
    selectie = json.loads(query_data(koppeling, columns=["brin", "nse_oordeel"]))["data_key"]

    _, fig = create_plot(chart_type="bar", x="brin", y="nse_oordeel", title="NSE", data_key=selectie)
    grafiek = json.loads(pio.to_json(fig))["layout"]["meta"]["herkomst"]

    assert grafiek == herkomstregels(selectie)
    _draagt_beide_bronnen(grafiek, skdb_key)
    assert _lcsk([r.removeprefix("# ") for r in (naar_csv(selectie) or "").splitlines()])


def test_een_afgekapte_tweede_bron_maakt_de_koppeling_onvolledig():
    """Alleen de eerste bron telde ook voor de afkap: een berekening op een afgekapte pagina zei niets."""
    skdb_key = _skdb()
    store.put(
        "rio:x:0", pd.DataFrame({"brin": ["25DW"], "naam": ["HU"]}), KeyMeta(bron="rio", dataset="x", volledig=False)
    )
    code = (
        "rio = store_get('rio:x:0')\n"
        "result = df.merge(rio, on='brin')[['brin', 'naam', 'nse_oordeel']].to_dict(orient='records')"
    )
    key = _analyse(code, skdb_key)

    assert not store.volledig(key)
    assert ONVOLLEDIG_EXPORT in herkomstregels(key)


def test_een_koppeling_is_zo_oud_als_haar_oudste_bron():
    """De store laat een key na de TTL gaan (#864); een koppeling mag haar oudste bron niet overleven, anders verliest
    haar herkomst die bron."""
    skdb_key, duo_key = _skdb(), _duo()
    oud = _meta(skdb_key)
    store.put(skdb_key, store.get(skdb_key), replace(oud, opgehaald_op=oud.opgehaald_op - timedelta(hours=3)))

    key = _koppeling(duo_key, skdb_key)

    assert _meta(key).opgehaald_op == _meta(skdb_key).opgehaald_op


def test_een_enkele_keten_houdt_haar_herkomst():
    """Zonder tweede bron verandert er niets: bron, stappen oudste eerst, de md5 één keer."""
    duo_key = _duo()
    sel = json.loads(query_data(duo_key, filters={"INSTELLINGSCODE": "25DW"}))["data_key"]

    assert herkomstregels(sel) == [
        _DUO_BRON,
        'selectie: filters {"INSTELLINGSCODE": "25DW"}',
        f"md5 van het DUO-bestand: {_MD5} (zoals DUO het levert, na te rekenen met md5sum; zie docs/reproducibility.md)",
    ]
