import asyncio
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import recepten
from agent.dashboard import (
    DashboardSpec,
    _build_recipe,
    _collect_kpi,
    _extract_json_object,
    _validate_kpis,
    build_dataset_context,
    herstel_data,
)
from agent.session_data import DATA_WEG
from tools import store


class TestBuildDatasetContext:
    def test_describes_the_datasets_of_this_conversation(self):
        store.put("cbs:85423NED", pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [100, 200], "NAAM": ["A", "B"]}))
        session = {"data_keys": ["cbs:85423NED"], "chat_settings": {"instelling": "Hogeschool Utrecht"}}

        context = build_dataset_context(session)

        assert len(context["datasets"]) == 1
        ds = context["datasets"][0]
        assert ds["data_key"] == "cbs:85423NED"
        assert ds["row_count"] == 2
        assert len(ds["columns"]) == 3

    def test_data_die_niet_meer_in_de_store_staat_geeft_een_uitleg_met_vervolgactie(self):
        """CH-44 (#466): na een herstart is de store leeg. Een rapport op de rest van de data, of de
        algemene 'Probeer het opnieuw', helpt de gebruiker niet: de vraag moet opnieuw."""
        store.put("cbs:85423NED", pd.DataFrame({"a": [1]}))
        session = {"data_keys": ["cbs:85423NED", "duo:weg:0"], "chat_settings": {}}

        with pytest.raises(ValueError, match="niet meer beschikbaar") as fout:
            build_dataset_context(session)
        assert "Stel je vraag opnieuw" in str(fout.value)

    def test_excludes_data_loaded_by_other_conversations(self):
        store.put("cbs:85423NED", pd.DataFrame({"a": [1]}))
        store.put("rio:erkenningen", pd.DataFrame({"b": [2]}))

        context = build_dataset_context({"data_keys": ["cbs:85423NED"], "chat_settings": {}})

        assert [d["data_key"] for d in context["datasets"]] == ["cbs:85423NED"]

    def test_unhashable_cells_do_not_break_context(self):
        store.put(
            "rio:erkenningen",
            pd.DataFrame(
                {
                    "code": ["30TX", "25DW"],
                    "_links": [{"self": {"href": "a"}}, {"self": {"href": "b"}}],
                    "tags": [["x"], ["y"]],
                }
            ),
        )

        context = build_dataset_context({"data_keys": ["rio:erkenningen"], "chat_settings": {}})

        columns = {c["naam"]: c for c in context["datasets"][0]["columns"]}
        assert columns["_links"]["voorbeelden"] == ["{'self': {'href': 'a'}}", "{'self': {'href': 'b'}}"]
        assert columns["tags"]["voorbeelden"] == ["['x']", "['y']"]

    def test_new_conversation_has_no_datasets(self):
        store.put("cbs:85423NED", pd.DataFrame({"a": [1]}))
        assert build_dataset_context({"chat_settings": {}})["datasets"] == []

    def test_includes_the_lineage_of_each_dataset(self):
        store.put("cbs:85423NED:aa", pd.DataFrame({"a": [1]}))
        call = {"name": "get_cbs_data", "arguments": {"dataset_id": "85423NED", "filters": {"$filter": "x"}}}
        session = {"data_keys": ["cbs:85423NED:aa"], "data_provenance": {"cbs:85423NED:aa": call}}

        [ds] = build_dataset_context(session)["datasets"]

        assert ds["herkomst"] == [call]

    def test_includes_instelling(self):
        context = build_dataset_context({"chat_settings": {"instelling": "Hogeschool Utrecht"}})
        assert context["instelling"] == "Hogeschool Utrecht"

    def test_includes_conversation_topic(self):
        session = {
            "turns": [{"question": "Hoeveel studenten heeft de HU?", "tool_calls": []}],
            "chat_settings": {},
        }
        assert "HU" in build_dataset_context(session)["topic"]


def _datasets(*keys, herkomst=None):
    return [{"data_key": k, **({"herkomst": herkomst[k]} if herkomst and k in herkomst else {})} for k in keys]


class TestHerstelData:
    """Vóór rapport en dashboard: wat een herstart uit de store wiste, komt terug uit zijn recept (#472)."""

    @pytest.fixture(autouse=True)
    def _db(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
        from persistence import db

        db.init_db()
        return db

    @staticmethod
    def _herstel(session: dict) -> list[dict]:
        events: list[dict] = []

        async def emit(ev):
            events.append(ev)

        asyncio.run(herstel_data(session, emit))
        return events

    def test_zonder_recept_de_melding_van_voor_de_recepten(self):
        session = {"username": "alice", "data_keys": ["duo:weg:0"], "chat_settings": {}}

        with pytest.raises(ValueError) as fout:
            self._herstel(session)
        assert str(fout.value) == DATA_WEG

    def test_haalt_terug_uit_de_database_en_meldt_het(self, _db):
        _db.save_recipes("alice", "c1", {"rio:erkenningen": {"laad": ["get_rio_data", {"resource": "erkenningen"}]}})
        session = {"username": "alice", "data_keys": ["rio:erkenningen"], "chat_settings": {}}

        with (
            patch("tools.rio.scope_blokkade", return_value=None),
            patch("tools.rio.scopeprofiel.sectorfilter_ontbreekt", return_value=None),
            patch("tools.rio.fetch", return_value=[{"code": "30TX"}]),
        ):
            events = self._herstel(session)

        [toast] = events
        assert toast["type"] == "toast"
        assert "opnieuw opgehaald op" in toast["message"]
        assert "de bron kan intussen zijn gewijzigd" in toast["message"]
        assert [d["data_key"] for d in build_dataset_context(session)["datasets"]] == ["rio:erkenningen"]

    def test_alles_nog_in_het_geheugen_geeft_geen_melding(self):
        store.put("cbs:85423NED", pd.DataFrame({"a": [1]}))
        assert self._herstel({"username": "alice", "data_keys": ["cbs:85423NED"]}) == []

    def test_een_eigen_berekening_noemt_de_stap_en_de_key(self):
        recept = {"afgeleid_van": "duo:x:0", "stap": "eigen berekening (run_analysis)", "herlaadbaar": False}
        recepten.onthoud("alice", "analysis:abc", recept)
        session = {"username": "alice", "data_keys": ["analysis:abc"], "chat_settings": {}}

        with pytest.raises(ValueError) as fout:
            self._herstel(session)
        assert "eigen berekening (run_analysis)" in str(fout.value)
        assert "analysis:abc" in str(fout.value)
        assert "Stel je vraag opnieuw" in str(fout.value)

    def test_het_recept_van_een_ander_telt_niet(self, _db):
        _db.save_recipes("bob", "c1", {"rio:erkenningen": {"laad": ["get_rio_data", {"resource": "erkenningen"}]}})
        session = {"username": "alice", "data_keys": ["rio:erkenningen"], "chat_settings": {}}

        with pytest.raises(ValueError, match="niet meer beschikbaar"):
            self._herstel(session)
        assert store.get("rio:erkenningen") is None


class TestBuildRecipe:
    def test_builds_reload_calls_from_data_keys(self):
        recipe = _build_recipe(_datasets("duo:p01hoinges:0", "cbs:85421NED", "query:abc"))
        assert [r["name"] for r in recipe] == ["get_duo_data", "get_cbs_data"]

    def test_no_keys(self):
        assert _build_recipe([]) == []

    def test_derived_duo_key_reloads_its_source_resource(self):
        [call] = _build_recipe(_datasets("duo:p01hoinges:3:74a5c5e2"))
        assert json.loads(call["arguments"]) == {"dataset_id": "p01hoinges", "resource": 3}

    def test_reload_call_keeps_the_recorded_cbs_filters(self):
        # #174: zonder de filters herlaadt het recept een andere selectie dan de chat gebruikte.
        load = {
            "name": "get_cbs_data",
            "arguments": {"dataset_id": "85423NED", "filters": {"$filter": "Perioden eq '2024SJ00'"}},
        }
        query = {"name": "query_data", "arguments": {"data_key": "cbs:85423NED:aa", "columns": ["Perioden"]}}
        datasets = _datasets(
            "cbs:85423NED:aa",
            "cbs:85423NED:aa:bb",
            herkomst={"cbs:85423NED:aa": [load], "cbs:85423NED:aa:bb": [load, query]},
        )

        recipe = _build_recipe(datasets)

        assert recipe == [{"name": "get_cbs_data", "arguments": json.dumps(load["arguments"])}]


class TestExtractJsonObject:
    def test_fenced_json(self):
        text = '```json\n{"title": "Test", "kpis": [{"label": "X"}]}\n```'
        result = _extract_json_object(text)
        assert result["title"] == "Test"
        assert len(result["kpis"]) == 1

    def test_raw_json(self):
        result = _extract_json_object('{"title": "Raw"}')
        assert result["title"] == "Raw"

    def test_no_json(self):
        assert _extract_json_object("geen json") == {}

    def test_raw_newline_in_a_string_value_is_read(self):
        # #166: "Invalid control character" — the content is intact, only the escape is missing.
        result = _extract_json_object('{"title": "T", "conclusie": "regel een\nregel twee"}')
        assert result["conclusie"] == "regel een\nregel twee"
        fenced = _extract_json_object('```json\n{"title": "T", "conclusie": "a\tb"}\n```')
        assert fenced["conclusie"] == "a\tb"


class TestDashboardSpec:
    def test_serialization(self):
        spec = DashboardSpec(
            title="Test Dashboard",
            description="Test",
            narrative="Samenvatting",
            kpis=[{"label": "Studenten", "value": "1.000"}],
            figures_json=["{}"],
            sources=["DUO — p01hoinges"],
            recipe=[{"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges"}'}],
        )
        data = spec.to_dict()
        assert data["title"] == "Test Dashboard"
        assert len(data["kpis"]) == 1
        assert len(data["figures_json"]) == 1
        assert len(data["recipe"]) == 1

    def test_from_dict(self):
        raw = {
            "title": "Test",
            "description": "Desc",
            "narrative": "N",
            "kpis": [],
            "figures_json": [],
            "sources": [],
            "recipe": [],
        }
        spec = DashboardSpec.from_dict(raw)
        assert spec.title == "Test"

    def test_from_dict_with_missing_fields(self):
        raw = {"title": "Minimal"}
        spec = DashboardSpec.from_dict(raw)
        assert spec.title == "Minimal"
        assert spec.kpis == []
        assert spec.figures_json == []


# --- KPI-validatie: geen getal in een dashboard dat niet uit compute_kpi komt ---

_COMPUTED = json.dumps(
    {
        "label": "Voltijd 2025/26",
        "value": "30.083",
        "raw": 30083.0,
        "trend": None,
        "trendDirection": None,
        "bron": {"data_key": "duo:t", "kolom": "AANTAL", "metric": "last"},
    }
)


def _computed_dict():
    computed: dict = {}
    _collect_kpi(computed, _COMPUTED)
    return computed


def test_kpi_uit_compute_kpi_wordt_doorgelaten():
    kpis = _validate_kpis([{"label": "Voltijd 2025/26", "value": "30.083"}], _computed_dict())
    assert len(kpis) == 1
    assert kpis[0]["value"] == "30.083"
    assert kpis[0]["bron"]["metric"] == "last"


def test_verzonnen_kpi_wordt_geweigerd():
    kpis = _validate_kpis([{"label": "Instroom", "value": "4.084", "trend": "+5%"}], _computed_dict())
    assert kpis == []


def test_trend_van_het_model_wordt_overschreven_door_de_tool():
    """Het model mag het label bepalen, de tool bepaalt het getal en de trend."""
    kpis = _validate_kpis(
        [{"label": "Eigen label", "value": "30.083", "trend": "+12%", "trendDirection": "up"}],
        _computed_dict(),
    )
    assert kpis[0]["label"] == "Eigen label"
    assert kpis[0]["trend"] is None
    assert kpis[0]["trendDirection"] is None


def test_notatieverschil_blokkeert_een_terechte_kpi_niet():
    kpis = _validate_kpis([{"label": "L", "value": "30083"}], _computed_dict())
    assert len(kpis) == 1


def test_zonder_compute_kpi_blijven_er_geen_kpis_over():
    kpis = _validate_kpis([{"label": "L", "value": "30.083"}], {})
    assert kpis == []


def test_generate_links_each_figure_to_the_query_before_it(monkeypatch):
    """Een dashboardgrafiek bewaart de query waarop hij rust, voor de replay (#192)."""
    import asyncio

    from agent import loop as loop_module
    from agent.dashboard import generate
    from agent.stream import StreamResult

    store.clear()
    store.put("cbs:85423NED", pd.DataFrame({"JAAR": ["2021", "2022"], "AANTAL": [10, 20]}))
    query = {"data_key": "cbs:85423NED", "columns": ["JAAR", "AANTAL"]}
    steps = [
        StreamResult(text="", tool_calls=[{"id": "q", "name": "query_data", "arguments": json.dumps(query)}]),
        StreamResult(
            text="",
            tool_calls=[
                {
                    "id": "p",
                    "name": "create_plot",
                    "arguments": json.dumps(
                        {"data_key": "cbs:85423NED", "chart_type": "line", "x": "JAAR", "y": "AANTAL", "title": "Reeks"}
                    ),
                }
            ],
        ),
        StreamResult(text='{"title": "Dashboard", "narrative": "Twee jaren."}', tool_calls=[]),
    ]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    spec = asyncio.run(generate({"data_keys": ["cbs:85423NED"]}, emit, model="openai/gpt-4o"))
    store.clear()

    assert len(spec.figures_json) == 1
    assert spec.figure_recipes == [
        {
            "query": query,
            "plot": {"data_key": "cbs:85423NED", "chart_type": "line", "x": "JAAR", "y": "AANTAL", "title": "Reeks"},
        }
    ]
    assert [e["type"] for e in events].count("figure") == 1
