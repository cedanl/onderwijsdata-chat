import json
from unittest.mock import patch

from agent.replay import replay_dashboard_figures, replay_data_calls


class TestReplayDataCalls:
    def test_replays_duo_call_successfully(self):
        calls = [{"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges", "resource": 0}'}]
        mock_result = json.dumps({"data_key": "duo:p01hoinges:0", "totaal_rijen": 100})

        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.return_value = (mock_result, None)
            results = replay_data_calls(calls)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["name"] == "get_duo_data"

    def test_handles_failure_gracefully(self):
        calls = [{"name": "get_duo_data", "arguments": '{"dataset_id": "nonexistent"}'}]

        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = Exception("Dataset not found")
            results = replay_data_calls(calls)

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "Dataset not found" in results[0]["error"]

    def test_partial_success(self):
        calls = [
            {"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges"}'},
            {"name": "get_duo_data", "arguments": '{"dataset_id": "nonexistent"}'},
        ]

        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [
                (json.dumps({"data_key": "duo:p01hoinges:0"}), None),
                Exception("Not found"),
            ]
            results = replay_data_calls(calls)

        assert results[0]["success"] is True
        assert results[1]["success"] is False

    def test_empty_calls(self):
        results = replay_data_calls([])
        assert results == []


class TestReplayDashboardFigures:
    def test_replays_query_and_plot(self):
        recipe = [{"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges", "resource": 0}'}]
        figure_recipes = [
            {
                "query": {"data_key": "duo:p01hoinges:0", "filters": {"JAAR": "2023"}, "columns": ["JAAR", "AANTAL"]},
                "plot": {"chart_type": "bar", "x": "JAAR", "y": "AANTAL", "title": "Test"},
            }
        ]
        query_result = json.dumps({"totaal_rijen": 1, "rijen": [{"JAAR": "2023", "AANTAL": 100}]})
        import plotly.graph_objects as go

        fig = go.Figure(go.Bar(x=["2023"], y=[100]))

        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [
                (json.dumps({"data_key": "duo:p01hoinges:0"}), None),  # data load
                (query_result, None),  # query_data
                ("Grafiek aangemaakt", fig),  # create_plot
            ]
            result = replay_dashboard_figures(recipe, figure_recipes)

        assert len(result) == 1
        assert mock_dispatch.call_count == 3

    def test_empty_figure_recipes(self):
        result = replay_dashboard_figures([], [])
        assert result == []

    def test_skips_failed_query(self):
        figure_recipes = [
            {"query": {"data_key": "duo:missing:0"}, "plot": {"chart_type": "bar", "x": "a", "y": "b", "title": "t"}},
        ]
        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = Exception("Not found")
            result = replay_dashboard_figures([], figure_recipes)
        assert result == []

    def test_skips_recipe_without_query(self):
        figure_recipes = [
            {"query": None, "plot": {"chart_type": "bar", "x": "a", "y": "b", "title": "t"}},
        ]
        result = replay_dashboard_figures([], figure_recipes)
        assert result == []
