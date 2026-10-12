import json
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go

from agent.replay import Reden, figuur_uitkomsten, recept_ids, replay_dashboard_figures, replay_data_calls
from tools import store


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
            mock_dispatch.side_effect = Exception("Dataset not found in /app/data/cache/x.parquet")
            results = replay_data_calls(calls)

        assert len(results) == 1
        assert results[0]["success"] is False
        # De ruwe uitzondering (met paden) blijft uit het resultaat: die gaat naar het log (#503).
        assert "parquet" not in results[0]["error"]
        assert results[0]["error"] == "herladen mislukt"

    def test_weigert_tools_buiten_de_allowlist(self):
        """#505: het recept komt van de client; alleen de load-tools mogen herhaald worden."""
        calls = [
            {"name": "run_analysis", "arguments": '{"code": "import os"}'},
            {"name": "onzin_tool", "arguments": "{}"},
        ]

        with patch("agent.replay.dispatch") as mock_dispatch:
            results = replay_data_calls(calls)

        mock_dispatch.assert_not_called()
        assert all(r["success"] is False for r in results)
        assert all(r["error"] == "tool niet toegestaan bij verversen" for r in results)

    def test_load_tools_blijven_toegestaan(self):
        for name in ("get_duo_data", "get_cbs_data", "get_rio_data"):
            with patch("agent.replay.dispatch") as mock_dispatch:
                mock_dispatch.return_value = ("{}", None)
                results = replay_data_calls([{"name": name, "arguments": "{}"}])
            assert results[0]["success"] is True

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


KEY = "duo:p01hoinges:0"
PLOT = {"chart_type": "bar", "x": "JAAR", "y": "AANTAL", "title": "Test"}
QUERY_RESULT = json.dumps({"totaal_rijen": 1, "rijen": [{"JAAR": "2023", "AANTAL": 100}]})


def _recept(key: str | None = KEY, titel: str = "Test") -> dict:
    query = {"data_key": key, "columns": ["JAAR", "AANTAL"]} if key else {}
    return {"query": query, "plot": {**PLOT, "title": titel}}


def _in_store(key: str = KEY) -> None:
    store.put(key, pd.DataFrame({"JAAR": ["2023"], "AANTAL": [100]}))


class TestReplayDashboardFigures:
    def test_replays_query_and_plot(self):
        _in_store()  # wat de herlaadcall bij de bron ophaalt
        recipe = [{"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges", "resource": 0}'}]
        fig = go.Figure(go.Bar(x=["2023"], y=[100]))

        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [
                (json.dumps({"data_key": KEY}), None),  # data load
                (QUERY_RESULT, None),  # query_data
                ("Grafiek aangemaakt", fig),  # create_plot
            ]
            [uitkomst] = replay_dashboard_figures(recipe, [_recept()])

        assert uitkomst.figuur_json is not None and uitkomst.reden is None
        assert uitkomst.naam == "'Test'"
        assert mock_dispatch.call_count == 3

    def test_empty_figure_recipes(self):
        assert replay_dashboard_figures([], []) == []

    def test_een_uitkomst_per_recept_ook_als_het_mislukt(self):
        """#523: een mislukt recept valt niet weg; de lijst schuift dus niet."""
        _in_store()
        fig = go.Figure(go.Bar(x=["2023"], y=[100]))

        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [Exception("kapot"), (QUERY_RESULT, None), ("ok", fig)]
            uitkomsten = replay_dashboard_figures([], [_recept(titel="A"), _recept(titel="B")])

        assert [u.reden for u in uitkomsten] == [Reden.QUERY_MISLUKT, None]
        assert uitkomsten[0].figuur_json is None and uitkomsten[1].figuur_json is not None


class TestReden:
    """#523: per recept de echte reden, niet altijd "ontbrekend"."""

    def test_ontbrekende_key_is_data_ontbreekt(self):
        with patch("agent.replay.dispatch") as mock_dispatch:
            [uitkomst] = figuur_uitkomsten([_recept()])
        assert uitkomst.reden is Reden.DATA_ONTBREEKT
        mock_dispatch.assert_not_called()

    def test_recept_zonder_data_key_is_geen_databron(self):
        [zonder_key, zonder_query] = figuur_uitkomsten([_recept(key=None), {"query": None, "plot": PLOT}])
        assert zonder_key.reden is Reden.GEEN_DATABRON
        assert zonder_query.reden is Reden.GEEN_DATABRON

    def test_onleesbaar_recept_is_geen_databron(self):
        [uitkomst] = figuur_uitkomsten(["geen recept"])
        assert uitkomst.reden is Reden.GEEN_DATABRON

    def test_query_met_uitzondering_is_query_mislukt(self):
        _in_store()
        with patch("agent.replay.dispatch", side_effect=Exception("/app/data/cache/x.parquet")):
            [uitkomst] = figuur_uitkomsten([_recept()])
        assert uitkomst.reden is Reden.QUERY_MISLUKT

    def test_query_met_fouttekst_is_query_mislukt(self):
        _in_store()
        with patch("agent.replay.dispatch", return_value=("Kolommen niet gevonden: ['X'].", None)):
            [uitkomst] = figuur_uitkomsten([_recept()])
        assert uitkomst.reden is Reden.QUERY_MISLUKT

    def test_query_zonder_rijenveld_is_query_mislukt(self):
        _in_store()
        with patch("agent.replay.dispatch", return_value=(json.dumps({"fout": "x"}), None)):
            [uitkomst] = figuur_uitkomsten([_recept()])
        assert uitkomst.reden is Reden.QUERY_MISLUKT

    def test_lege_selectie_is_geen_rijen(self):
        _in_store()
        with patch("agent.replay.dispatch", return_value=(json.dumps({"rijen": [], "melding": "leeg"}), None)):
            [uitkomst] = figuur_uitkomsten([_recept()])
        assert uitkomst.reden is Reden.GEEN_RIJEN

    def test_plot_zonder_figuur_is_grafiek_niet_gemaakt(self):
        _in_store()
        with patch("agent.replay.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [(QUERY_RESULT, None), ("Geen grafiek gemaakt: één datapunt.", None)]
            [uitkomst] = figuur_uitkomsten([_recept()])
        assert uitkomst.reden is Reden.GEEN_GRAFIEK

    def test_naam_is_de_titel_of_de_positie(self):
        zonder_titel = {"query": {"data_key": KEY}, "plot": {**PLOT, "title": ""}}
        uitkomsten = figuur_uitkomsten([_recept(titel="Instroom"), zonder_titel])
        assert [u.naam for u in uitkomsten] == ["'Instroom'", "Grafiek 2"]


class TestReceptIds:
    def test_hetzelfde_recept_geeft_dezelfde_sleutel(self):
        assert recept_ids([_recept()]) == recept_ids([json.loads(json.dumps(_recept()))])

    def test_sleutel_hangt_niet_af_van_de_positie(self):
        a, b = _recept(titel="A"), _recept(titel="B")
        assert recept_ids([a, b]) == list(reversed(recept_ids([b, a])))

    def test_sleutel_hangt_niet_af_van_de_volgorde_van_de_velden(self):
        recept = _recept()
        omgekeerd = {"plot": dict(reversed(list(recept["plot"].items()))), "query": recept["query"]}
        assert recept_ids([recept]) == recept_ids([omgekeerd])

    def test_ander_recept_geeft_een_andere_sleutel(self):
        [a, b] = recept_ids([_recept(titel="A"), _recept(titel="B")])
        assert a != b

    def test_identieke_dubbelen_krijgen_een_volgnummer(self):
        ids = recept_ids([_recept(), _recept(), _recept()])
        assert len(set(ids)) == 3
        assert ids[1].startswith(ids[0]) and ids[2].startswith(ids[0])

    def test_uitkomst_draagt_de_sleutel_van_zijn_recept(self):
        recepten = [_recept(titel="A"), _recept(titel="B")]
        assert [u.recept_id for u in figuur_uitkomsten(recepten)] == recept_ids(recepten)
