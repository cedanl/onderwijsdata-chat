import json
from unittest.mock import patch

import pandas as pd

from agent.dashboard import (
    DashboardSpec,
    _collect_kpi,
    _validate_kpis,
    _build_recipe_from_store,
    _extract_json_object,
    build_dataset_context,
)


class TestBuildDatasetContext:
    def test_builds_context_from_session_turns(self):
        with patch("agent.dashboard.store") as mock_store:
            df = pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [100, 200], "NAAM": ["A", "B"]})
            mock_store.get.return_value = df
            mock_store.list_keys.return_value = ["duo:p01hoinges:0"]

            session = {
                "turns": [
                    {
                        "tool_calls": [
                            {"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges", "resource": 0}'},
                        ],
                    }
                ],
                "chat_settings": {"instelling": "Hogeschool Utrecht"},
            }

            context = build_dataset_context(session)

        assert len(context["datasets"]) == 1
        ds = context["datasets"][0]
        assert ds["data_key"] == "duo:p01hoinges:0"
        assert ds["row_count"] == 2
        assert len(ds["columns"]) == 3

    def test_unhashable_cells_do_not_break_context(self):
        with patch("agent.dashboard.store") as mock_store:
            df = pd.DataFrame({
                "code": ["30TX", "25DW"],
                "_links": [{"self": {"href": "a"}}, {"self": {"href": "b"}}],
                "tags": [["x"], ["y"]],
            })
            mock_store.get.return_value = df
            mock_store.list_keys.return_value = ["rio:erkenningen"]

            context = build_dataset_context({"turns": [], "chat_settings": {}})

        columns = {c["naam"]: c for c in context["datasets"][0]["columns"]}
        assert columns["_links"]["voorbeelden"] == ["{'self': {'href': 'a'}}", "{'self': {'href': 'b'}}"]
        assert columns["tags"]["voorbeelden"] == ["['x']", "['y']"]

    def test_empty_session_returns_empty(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = []

            session = {"turns": [], "chat_settings": {}}
            context = build_dataset_context(session)

        assert context["datasets"] == []

    def test_skips_missing_store_keys(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.get.return_value = None
            mock_store.list_keys.return_value = ["duo:p01hoinges:0"]

            session = {
                "turns": [
                    {"tool_calls": [{"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges"}'}]},
                ],
                "chat_settings": {},
            }
            context = build_dataset_context(session)

        assert context["datasets"] == []

    def test_includes_instelling(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = []

            session = {
                "turns": [],
                "chat_settings": {"instelling": "Hogeschool Utrecht"},
            }
            context = build_dataset_context(session)

        assert context["instelling"] == "Hogeschool Utrecht"

    def test_includes_conversation_topic(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = []

            session = {
                "turns": [{"question": "Hoeveel studenten heeft de HU?", "tool_calls": []}],
                "chat_settings": {},
                "messages": [{"role": "user", "content": "Hoeveel studenten heeft de HU?"}],
            }
            context = build_dataset_context(session)

        assert "HU" in context["topic"]


class TestBuildRecipeFromStore:
    def test_builds_recipe_from_store_keys(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = ["duo:p01hoinges:0", "cbs:85421NED"]
            recipe = _build_recipe_from_store()
        assert len(recipe) == 2
        assert recipe[0]["name"] == "get_duo_data"
        assert recipe[1]["name"] == "get_cbs_data"

    def test_empty_store(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = []
            assert _build_recipe_from_store() == []


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

_COMPUTED = json.dumps({
    "label": "Voltijd 2025/26",
    "value": "30.083",
    "raw": 30083.0,
    "trend": None,
    "trendDirection": None,
    "bron": {"data_key": "duo:t", "kolom": "AANTAL", "metric": "last"},
})


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
