"""run_analysis weigert een merge, join of concat van twee keys en wijst naar koppel_data (#1014, optie B).

Reaudit C02/N07: het model koppelde de Studiekeuzedatabase en DUO per instelling in één run_analysis in plaats van met
koppel_data; Capabel ging verloren en Avans bleef zonder naam. Een promptregel hield dat niet tegen (#962, #988). Nu
weigert de AST-controle zo'n script vóór de sandbox, en noemt de melding de route die wel werkt: per bron aggregeren in
een eigen stap, dan koppel_data op die analysis-keys.
"""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent.stream import StreamResult
from tools import analysis, sandbox, scriptcontrole, store
from tools.koppel import KOPPELSTATUS, koppel_data
from tools.store import KeyMeta

_SKDB = "skdb:opleidingen:n07"
_DUO = "duo:p01hoinges:0:n07"


@pytest.fixture(autouse=True)
def tabellen():
    """De N07-vorm: NSE per opleiding (SKDB) en inschrijvingen per opleiding (DUO), elk met instellingen die de ander
    niet heeft."""
    skdb = pd.DataFrame(
        {
            "brin": ["25DW", "25DW", "07GR", "28DN"],
            "croho": [30020, 34139, 30020, 34139],
            "nse_oordeel": [3.8, 4.0, 3.6, 4.1],
        }
    )
    duo = pd.DataFrame(
        {
            "INSTELLINGSCODE": ["25DW", "25DW", "07GR", "30GB"],
            "CROHO": [30020, 34139, 30020, 30020],
            "AANTAL": [120, 80, 60, 40],
        }
    )
    store.put(_SKDB, skdb, KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase"))
    store.put(_DUO, duo, KeyMeta(bron="duo", dataset="p01hoinges", resource=0))


@pytest.fixture
def geen_sandbox(monkeypatch):
    monkeypatch.setattr(sandbox, "voer_uit", lambda *a, **k: pytest.fail("een geweigerd script draait niet"))


def _is_weigering(uit) -> bool:
    return isinstance(uit, str) and uit.startswith("Niet toegestaan in run_analysis") and "data_key" not in _json(uit)


def _json(tekst: str) -> dict:
    try:
        geladen = json.loads(tekst)
    except ValueError:
        return {}
    return geladen if isinstance(geladen, dict) else {}


# --- Criterium 1, 5: de N07-vorm en wat de data langs namen draagt, wordt geweigerd --------------------------------

_WEIGEREN = {
    "df_merge_store_get": (
        _SKDB,
        f"ander = store_get('{_DUO}')\n"
        "m = df.merge(ander, left_on=['brin', 'croho'], right_on=['INSTELLINGSCODE', 'CROHO'])\n"
        "result = m.to_dict(orient='records')",
    ),
    "pd_merge_twee_store_gets": (
        None,
        f"m = pd.merge(store_get('{_SKDB}'), store_get('{_DUO}'), left_on='brin', right_on='INSTELLINGSCODE')\n"
        "result = m.to_dict(orient='records')",
    ),
    "join": (
        None,
        f"a = store_get('{_SKDB}').groupby('brin')[['nse_oordeel']].mean()\n"
        f"b = store_get('{_DUO}').groupby('INSTELLINGSCODE')[['AANTAL']].sum()\n"
        "result = a.join(b).reset_index().to_dict(orient='records')",
    ),
    "concat": (
        _SKDB,
        f"b = store_get('{_DUO}').rename(columns={{'INSTELLINGSCODE': 'brin'}})\n"
        "result = pd.concat([df, b]).to_dict(orient='records')",
    ),
    "keten_van_namen": (
        None,
        f"a = store_get('{_SKDB}').groupby('brin').sum().reset_index()\n"
        "c = a\n"
        f"b = store_get('{_DUO}')\n"
        "result = c.merge(b, left_on='brin', right_on='INSTELLINGSCODE').to_dict(orient='records')",
    ),
    "append_in_een_lijst": (
        _SKDB,
        f"delen = [df]\ndelen.append(store_get('{_DUO}'))\nresult = pd.concat(delen).to_dict(orient='records')",
    ),
    "for_en_comprehension": (
        _SKDB,
        f"bronnen = (df, store_get('{_DUO}'))\n"
        "delen = [t.head(2) for t in bronnen]\n"
        "for t in delen:\n    laatste = t\n"
        "result = pd.concat([laatste, delen[0]]).to_dict(orient='records')",
    ),
    "kolom_toewijzing": (
        _SKDB,
        f"ander = store_get('{_DUO}')\n"
        "df['AANTAL'] = ander['AANTAL']\n"
        "result = pd.concat([df.head(1), df.tail(1)]).to_dict(orient='records')",
    ),
    "merge_asof": (
        _SKDB,
        f"result = pd.merge_asof(df, store_get('{_DUO}'), left_on='croho', right_on='CROHO').to_dict(orient='records')",
    ),
}


@pytest.mark.parametrize("data_key, code", _WEIGEREN.values(), ids=_WEIGEREN.keys())
def test_een_koppeling_van_twee_keys_in_een_script_wordt_geweigerd(geen_sandbox, data_key, code):
    voor = store.list_keys()

    uit = analysis.run_analysis(code=code, data_key=data_key)

    assert _is_weigering(uit), uit
    assert isinstance(uit, str)
    assert "koppel_data" in uit and "relatie(" in uit
    assert _SKDB in uit and _DUO in uit
    assert sorted(store.list_keys()) == sorted(voor)  # geen nieuwe key


def test_de_melding_noemt_de_keys_de_sleutel_en_de_toegestane_route(geen_sandbox):
    uit = analysis.run_analysis(code=_WEIGEREN["df_merge_store_get"][1], data_key=_SKDB)

    assert isinstance(uit, str)
    assert "'merge'" in uit
    assert f"relatie('{_SKDB}', '{_DUO}')" in uit
    assert f"koppel_data(data_key='{_SKDB}', andere_key='{_DUO}', sleutels=[...])" in uit
    # De sleutels die beide tabellen dragen, uit relaties.sleutelkolommen.
    assert "Beide tabellen hebben een kolom met sleutel brin, croho." in uit
    # Criterium 2: per bron aggregeren in een eigen stap met één key, dan koppel_data op die analysis-keys.
    assert "eigen run_analysis-stap: elke stap leest één key en geeft een eigen analysis:-key" in uit
    assert "Koppel daarna die analysis:-keys met koppel_data." in uit


def test_drie_keys_worden_stap_voor_stap_gekoppeld(geen_sandbox):
    store.put("rio:x:0", pd.DataFrame({"brin": ["25DW"], "naam": ["HU"]}), KeyMeta(bron="rio", dataset="x"))
    code = f"result = pd.concat([df, store_get('{_DUO}'), store_get('rio:x:0')]).to_dict(orient='records')"

    uit = analysis.run_analysis(code=code, data_key=_SKDB)

    assert isinstance(uit, str) and _is_weigering(uit)
    assert f"({_SKDB}, {_DUO}, rio:x:0)" in uit
    assert "stap voor stap" in uit


# --- Criterium 4, 5: geen vals alarm ----------------------------------------------------------------------------

_TOEGESTAAN = {
    "alleen_df": (_SKDB, "result = df.groupby('brin', as_index=False)['nse_oordeel'].mean().to_dict(orient='records')"),
    "een_store_get": (
        None,
        f"t = store_get('{_DUO}')\nresult = t.groupby('INSTELLINGSCODE', as_index=False)['AANTAL'].sum()"
        ".to_dict(orient='records')",
    ),
    "eigen_tabel": (
        _SKDB,
        "namen = pd.DataFrame({'brin': ['25DW', '07GR'], 'naam': ['HU', 'Hanze']})\n"
        "result = df.merge(namen, on='brin', how='left').to_dict(orient='records')",
    ),
    "eigen_dict": (
        _SKDB,
        "namen = pd.DataFrame.from_dict({'25DW': {'naam': 'HU'}}, orient='index')\n"
        "result = df.join(namen, on='brin').to_dict(orient='records')",
    ),
    "concat_van_delen_van_een_key": (
        _SKDB,
        "result = pd.concat([df[df.nse_oordeel > 3.9], df[df.nse_oordeel <= 3.9]]).to_dict(orient='records')",
    ),
    "string_join_over_twee_keys": (
        _SKDB,
        f"ander = store_get('{_DUO}')\n"
        "result = {'codes': ', '.join(sorted(set(df['brin']) | set(ander['INSTELLINGSCODE'])))}",
    ),
    "dezelfde_key_onder_twee_namen": (
        _SKDB,
        f"ander = store_get('{_SKDB}')\nresult = df.merge(ander, on=['brin', 'croho']).to_dict(orient='records')",
    ),
}


@pytest.mark.parametrize("data_key, code", _TOEGESTAAN.values(), ids=_TOEGESTAAN.keys())
def test_een_script_op_een_key_of_met_een_eigen_tabel_draait(data_key, code):
    uit = analysis.run_analysis(code=code, data_key=data_key)

    assert isinstance(uit, str)
    assert not uit.startswith(("Niet toegestaan", "Fout in script")), uit
    assert _json(uit), uit


def test_een_alias_van_dezelfde_key_telt_als_een_key():
    """Keys tellen na store.canoniek: DUO:… is dezelfde tabel als duo:…."""
    code = f"result = df.merge(store_get('{_DUO.upper()}'), on='CROHO').to_dict(orient='records')"
    script = scriptcontrole.ontleed(code, _DUO)

    assert [k.keys for k in script.koppelingen] == [frozenset({_DUO, _DUO.upper()})]  # zo noemt het script ze
    assert analysis._koppelweigering(script, _DUO) is None


@pytest.mark.parametrize(
    "code, data_key, verwacht",
    [
        ("result = len(df.merge(df))", "a", []),
        ("t = store_get('b')\nt = t.merge(df)\nresult = len(t)", "a", [{"a", "b"}]),
        ("x = store_get('b') if True else None\nresult = len(df.merge(x))", "a", [{"a", "b"}]),
        ("x = df\nx = store_get('b')\nresult = len(x.merge(x))", "a", [{"a", "b"}]),  # alle takken samen
        ("result = len(df.merge(store_get('b')))", None, []),  # zonder data_key draagt df geen key
        ("lookup = {}\nlookup[df.k.iloc[0]] = store_get('b').v.sum()\nresult = len(df.merge(df))", "a", []),
        ("s = ';'\nresult = s.join(list(df.k) + list(store_get('b').k))", "a", []),
    ],
)
def test_de_herkomst_volgt_de_namen(code, data_key, verwacht):
    script = scriptcontrole.ontleed(code, data_key)

    assert [set(k.keys) for k in script.koppelingen] == verwacht


# --- Criterium 6: een syntaxfout en de bestaande weigeringen gaan voor --------------------------------------------

_MERGE = f"result = df.merge(store_get('{_DUO}'), left_on='brin', right_on='INSTELLINGSCODE').to_dict()"


@pytest.mark.parametrize(
    "code, begin",
    [
        (f"{_MERGE}\nresult = (", "Fout in script"),
        (f"import os\n{_MERGE}", "Niet toegestaan in analyse-scripts: 'import'"),
        (f"x = df.__class__\n{_MERGE}", "Niet toegestaan in analyse-scripts: '__class__'"),
        (
            f"k = 'x'\nt = store_get(k)\n{_MERGE}",
            "Niet toegestaan in analyse-scripts: 'store_get met een berekende key",
        ),
        (f"x = [1, 2, 3, 4, 5, 6]\n{_MERGE}", "Script bevat een literal datastructuur"),
    ],
)
def test_een_eerdere_weigering_gaat_voor(geen_sandbox, code, begin):
    uit = analysis.run_analysis(code=code, data_key=_SKDB)

    assert isinstance(uit, str) and uit.startswith(begin), uit
    assert "koppel_data" not in uit


def test_een_script_zonder_data_houdt_zijn_melding(geen_sandbox):
    uit = analysis.run_analysis(code="result = len(pd.concat([pd.DataFrame(), pd.DataFrame()]))")

    assert isinstance(uit, str) and uit.startswith("Script leest geen data"), uit


# --- Criterium 3: de toegestane route ----------------------------------------------------------------------------

_PER_INSTELLING_SKDB = "result = df.groupby('brin', as_index=False)['nse_oordeel'].mean().to_dict(orient='records')"
_PER_INSTELLING_DUO = "result = df.groupby('INSTELLINGSCODE', as_index=False)['AANTAL'].sum().to_dict(orient='records')"


def _analysekey(code: str, data_key: str) -> str:
    uit = analysis.run_analysis(code=code, data_key=data_key)
    assert isinstance(uit, str), uit
    return json.loads(uit)["data_key"]


def test_per_bron_aggregeren_en_dan_koppel_data_geeft_een_koppelkey():
    nse, aantal = (_analysekey(code, key) for code, key in ((_PER_INSTELLING_SKDB, _SKDB), (_PER_INSTELLING_DUO, _DUO)))
    assert nse.startswith("analysis:") and aantal.startswith("analysis:")

    uit = json.loads(koppel_data(nse, aantal, sleutels=["brin"]))

    assert uit["data_key"].startswith("koppel:")
    gekoppeld = store.get(uit["data_key"])
    assert isinstance(gekoppeld, pd.DataFrame)
    # Elke instelling van beide kanten blijft: 28DN alleen in SKDB, 30GB alleen in DUO.
    status = dict(zip(gekoppeld["brin"], gekoppeld[KOPPELSTATUS], strict=True))
    assert status == {"25DW": "beide", "07GR": "beide", "28DN": "alleen SKDB", "30GB": "alleen DUO"}


# --- Criterium 7: een nagebootst model loopt tegen de weigering aan en neemt de route -------------------------------

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


def _toolresultaten(messages: list[dict]) -> list[str]:
    return [str(m["content"]) for m in messages if m.get("role") == "tool"]


def _aanroep(naam: str, id_: str, **args) -> dict:
    return {"id": id_, "name": naam, "arguments": json.dumps(args)}


def _stappen():
    """Het model: eerst de N07-vorm in één script, dan per bron aggregeren en koppel_data, dan een antwoord."""

    def n07(_):
        return [_aanroep("run_analysis", "n07", code=_WEIGEREN["df_merge_store_get"][1], data_key=_SKDB)]

    def per_bron(_):
        return [
            _aanroep("run_analysis", "nse", code=_PER_INSTELLING_SKDB, data_key=_SKDB),
            _aanroep("run_analysis", "aantal", code=_PER_INSTELLING_DUO, data_key=_DUO),
        ]

    def koppel(resultaten):
        nse, aantal = (json.loads(r)["data_key"] for r in resultaten[-2:])
        return [_aanroep("koppel_data", "koppel", data_key=nse, andere_key=aantal, sleutels=["brin"])]

    return [n07, per_bron, koppel, None]


def test_een_nagebootst_model_krijgt_de_weigering_en_koppelt_daarna_met_koppel_data(monkeypatch):
    stappen = _stappen()
    gezien: list[list[str]] = []

    async def fake_completion(*args, **kwargs):
        return kwargs["messages"]

    async def fake_accumulate(messages, stop_event=None, emit=None):
        resultaten = _toolresultaten(messages)
        gezien.append(resultaten)
        stap = stappen.pop(0)
        if stap is None:
            return StreamResult(text="De koppeling staat klaar, met de instellingen zonder match apart.", tool_calls=[])
        return StreamResult(text="", tool_calls=stap(resultaten))

    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings, eerder=(): None)
    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = [{"role": "user", "content": "Vergelijk per instelling de NSE-score met het aantal studenten."}]
    asyncio.run(run_module.run(vraag, {}, emit, asyncio.Event(), model="openai/gpt-4o"))

    assert not stappen, "het model kwam niet aan zijn antwoord toe"
    weigering = gezien[1][0]
    assert _is_weigering(weigering) and "koppel_data" in weigering
    koppeling = json.loads(gezien[-1][-1])
    assert koppeling["data_key"].startswith("koppel:")
    assert koppeling["telling"] == {"beide": 2, "alleen SKDB": 1, "alleen DUO": 1}
    eind = [e for e in events if e["type"] == "tool_end"]
    assert [e["name"] for e in eind] == ["run_analysis", "run_analysis", "run_analysis", "koppel_data"]
