"""De twee herhaalmodi van #346: ververs en reproduceer.

- reproduceer rendert uit de data in de store, zonder netwerk, en is byte-identiek.
- ververs haalt opnieuw op en benoemt de gewijzigde waarden en bron-ankers.
"""

import asyncio
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import server
from agent import replay
from agent.replay import (
    anker_verschillen,
    ankers_van_recipe,
    replay_dashboard_figures,
    reproduceer_figures,
)
from routes import chat
from tools import store
from tools.store import KeyMeta

KEY = "cbs:85423NED"

RECEPT = {
    "query": {"data_key": KEY, "columns": ["Perioden", "aantal"]},
    "plot": {"chart_type": "bar", "x": "Perioden", "y": "aantal", "title": "Instroom"},
}


def _laad(waarden: list[int]) -> None:
    df = pd.DataFrame({"Perioden": ["2023", "2024"], "aantal": waarden})
    store.put(KEY, df, KeyMeta(bron="cbs", dataset="85423NED"))


class TestReproduceer:
    def test_reproduceer_is_byte_identiek(self):
        """Acceptatiecriterium: reproduceer geeft een byte-identieke uitkomst."""
        _laad([475460, 478660])
        eerste = reproduceer_figures([RECEPT])
        tweede = reproduceer_figures([RECEPT])

        assert eerste.figures_json and not eerste.ontbrekend
        assert eerste.figures_json == tweede.figures_json
        # En identiek aan wat de ververs-route uit dezelfde data maakt.
        assert eerste.figures_json == replay_dashboard_figures([], [RECEPT])

    def test_reproduceer_raakt_de_bron_niet(self, monkeypatch):
        _laad([475460, 478660])
        aangeroepen: list[str] = []
        echte = replay.dispatch

        def spion(name, args):
            aangeroepen.append(name)
            return echte(name, args)

        monkeypatch.setattr(replay, "dispatch", spion)
        repro = reproduceer_figures([RECEPT])

        assert repro.figures_json
        assert not set(aangeroepen) & replay.REPLAYABLE_TOOLS

    def test_ontbrekende_key_komt_in_ontbrekend(self):
        repro = reproduceer_figures([RECEPT])
        assert repro.figures_json == []
        assert repro.ontbrekend == [KEY]

    def test_do_refresh_weigert_zonder_data_met_verwijzing_naar_ververs(self):
        spec = {"figures_json": [], "figure_recipes": [RECEPT]}
        with pytest.raises(chat.RefreshError, match="niet meer in het geheugen"):
            asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="reproduceer"))

    def test_do_refresh_meldt_identieke_reproductie(self):
        _laad([475460, 478660])
        figures = replay_dashboard_figures([], [RECEPT])
        spec = {"figures_json": figures, "figure_recipes": [RECEPT]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="reproduceer"))

        assert nieuw.figures_json == figures
        assert info is not None
        assert "identiek" in info
        assert veranderingen == []


class TestVervers:
    def test_ververs_meldt_een_gewijzigde_waarde(self):
        """Acceptatiecriterium: na een bronmutatie benoemt ververs oude en nieuwe waarde."""
        _laad([475460, 475460])
        oud = replay_dashboard_figures([], [RECEPT])
        _laad([475460, 478660])  # de bron is intussen herzien

        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}
        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="ververs"))

        assert nieuw.figures_json != oud
        assert info is not None
        assert "wijziging" in info
        assert any("2024" in v and "475.460" in v and "478.660" in v for v in veranderingen)

    def test_ververs_zonder_wijziging_zegt_dat(self):
        _laad([475460, 478660])
        oud = replay_dashboard_figures([], [RECEPT])

        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}
        _, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="ververs"))

        assert veranderingen == []
        assert info is not None
        assert "geen wijzigingen" in info

    def test_ververs_is_de_standaardmodus(self):
        _laad([475460, 478660])
        oud = replay_dashboard_figures([], [RECEPT])
        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}

        _, info, _ = asyncio.run(chat._do_refresh([], [RECEPT], spec))

        assert info is not None
        assert "ververst" in info.lower()


class TestAnkers:
    def test_ankers_van_recipe_alleen_cbs(self, monkeypatch):
        monkeypatch.setattr(replay, "catalogus_laatste_update", lambda ds: {"85423NED": "2026-01-15"}.get(ds))
        recipe = [
            {"name": "get_cbs_data", "arguments": json.dumps({"dataset_id": "85423NED"})},
            {"name": "get_duo_data", "arguments": json.dumps({"dataset_id": "p01hoinges"})},
            {"name": "get_cbs_data", "arguments": "geen json"},
        ]
        assert ankers_van_recipe(recipe) == {"85423NED": "2026-01-15"}

    def test_anker_verschillen_meldt_bijgewerkte_bron(self):
        meldingen = anker_verschillen({"85423NED": "2025-04-14"}, {"85423NED": "2026-01-15"})
        assert meldingen == ["CBS-tabel 85423NED is bij de bron bijgewerkt op 2026-01-15 (was 2025-04-14)."]

    def test_zonder_bewaard_anker_geen_melding(self):
        assert anker_verschillen({}, {"85423NED": "2026-01-15"}) == []


class TestEndpoint:
    def test_onbekende_modus_geeft_400(self):
        resp = TestClient(server.app).post("/api/dashboard/refresh", json={"mode": "replay"})
        assert resp.status_code == 400
        assert "modus" in resp.json()["error"].lower()

    def test_ververs_respons_bevat_melding_en_veranderingen(self):
        _laad([475460, 478660])
        oud = replay_dashboard_figures([], [RECEPT])
        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}

        resp = TestClient(server.app).post(
            "/api/dashboard/refresh",
            json={"mode": "ververs", "figure_recipes": [RECEPT], "spec": spec},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "ververs"
        assert "melding" in body and "veranderingen" in body
        assert body["spec"]["figures_json"] == oud
