"""De twee herhaalmodi van #346: ververs en reproduceer.

- reproduceer rendert uit de data in de store, zonder netwerk, en is byte-identiek.
- ververs haalt opnieuw op en benoemt de gewijzigde waarden en bron-ankers.
- een mislukte figuur wordt met haar echte reden gemeld en vervangt niets (#523).
"""

import asyncio
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import server
from agent import replay
from agent.dashboard import DashboardSpec
from agent.replay import (
    Reden,
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


def _recept(titel: str, **query) -> dict:
    """Een recept op dezelfde, aanwezige key; `query` vervangt delen van de query van RECEPT."""
    return {"query": {**RECEPT["query"], **query}, "plot": {**RECEPT["plot"], "title": titel}}


# Faalt terwijl de key wel in de store staat: de query vraagt een kolom die er niet is.
RECEPT_FOUT = _recept("Uitstroom", columns=["Perioden", "bestaat_niet"])
# Bewaarde figuur van RECEPT_FOUT: zelfde categorieën als RECEPT, andere waarden.
BEWAARD_FOUT = json.dumps(
    {"data": [{"type": "bar", "x": ["2023", "2024"], "y": [1, 9]}], "layout": {"title": {"text": "Uitstroom"}}}
)


def _laad(waarden: list[int]) -> None:
    df = pd.DataFrame({"Perioden": ["2023", "2024"], "aantal": waarden})
    store.put(KEY, df, KeyMeta(bron="cbs", dataset="85423NED"))


def _figuren(figure_recipes: list[dict]) -> list[str]:
    """De figuren die ververs nu uit de store maakt, zoals een bewaard dashboard ze heeft."""
    figuren = [u.figuur_json for u in replay_dashboard_figures([], figure_recipes)]
    assert all(figuren)
    return [f for f in figuren if f is not None]


class TestReproduceer:
    def test_reproduceer_is_byte_identiek(self):
        """Acceptatiecriterium: reproduceer geeft een byte-identieke uitkomst."""
        _laad([475460, 478660])
        eerste = reproduceer_figures([RECEPT])
        tweede = reproduceer_figures([RECEPT])

        assert eerste.figures_json and not eerste.ontbrekend
        assert eerste.figures_json == tweede.figures_json
        # En identiek aan wat de ververs-route uit dezelfde data maakt.
        assert eerste.figures_json == _figuren([RECEPT])

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
        figures = _figuren([RECEPT])
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
        oud = _figuren([RECEPT])
        _laad([475460, 478660])  # de bron is intussen herzien

        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}
        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="ververs"))

        assert nieuw.figures_json != oud
        assert info is not None
        assert "wijziging" in info
        assert any("2024" in v and "475.460" in v and "478.660" in v for v in veranderingen)

    def test_ververs_zonder_wijziging_zegt_dat(self):
        _laad([475460, 478660])
        oud = _figuren([RECEPT])

        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}
        _, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="ververs"))

        assert veranderingen == []
        assert info is not None
        assert "geen wijzigingen" in info

    def test_ververs_is_de_standaardmodus(self):
        _laad([475460, 478660])
        oud = _figuren([RECEPT])
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

    @pytest.mark.parametrize("mode", [["ververs"], {"a": 1}, 5])
    def test_onhashbare_of_niet_tekst_modus_geeft_400_in_plaats_van_500(self, mode):
        resp = TestClient(server.app).post("/api/dashboard/refresh", json={"mode": mode})
        assert resp.status_code == 400
        assert "modus" in resp.json()["error"].lower()

    def test_ververs_respons_bevat_melding_en_veranderingen(self):
        _laad([475460, 478660])
        oud = _figuren([RECEPT])
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


class TestWebSocketModus:
    @pytest.mark.parametrize("mode", ["replay", ["ververs"], {"a": 1}, 5])
    def test_ongeldige_modus_geeft_een_foutmelding_en_start_niets(self, mode):
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        async def scenario():
            msg = {"action": "refresh_dashboard", "mode": mode}
            return await chat.ACTIES["refresh_dashboard"](msg, chat._new_session(), emit, None)

        taak = asyncio.run(scenario())

        assert taak is None
        assert [e["type"] for e in events] == ["error"]
        assert "modus" in events[0]["message"].lower()


class TestReproduceerReden:
    """#523: een mislukte figuur heet niet altijd "ontbrekend"; de reden is de echte."""

    def test_falende_query_met_aanwezige_key_is_niet_ontbrekend(self):
        _laad([475460, 478660])

        repro = reproduceer_figures([RECEPT_FOUT])

        assert repro.ontbrekend == []
        [mislukt] = repro.mislukt
        assert mislukt.reden is Reden.QUERY_MISLUKT
        assert mislukt.naam == "'Uitstroom'"

    def test_onbekende_filterkolom_is_query_mislukt(self):
        _laad([475460, 478660])
        [mislukt] = reproduceer_figures([_recept("X", filters={"bestaat_niet": "1"})]).mislukt
        assert mislukt.reden is Reden.QUERY_MISLUKT

    def test_recept_zonder_data_key_wordt_gemeld(self):
        _laad([475460, 478660])
        zonder_key = {"query": {"columns": ["Perioden"]}, "plot": RECEPT["plot"]}

        repro = reproduceer_figures([RECEPT, zonder_key])

        assert [m.reden for m in repro.mislukt] == [Reden.GEEN_DATABRON]

    def test_lege_selectie_is_geen_rijen(self):
        _laad([475460, 478660])
        [mislukt] = reproduceer_figures([_recept("Leeg", filters={"aantal": 1})]).mislukt
        assert mislukt.reden is Reden.GEEN_RIJEN

    def test_een_datapunt_is_grafiek_niet_gemaakt(self):
        _laad([475460, 478660])
        lijn = {**_recept("Eén punt", filters={"aantal": 478660}), "plot": {**RECEPT["plot"], "chart_type": "line"}}

        [mislukt] = reproduceer_figures([lijn]).mislukt

        assert mislukt.reden is Reden.GEEN_GRAFIEK

    def test_do_refresh_noemt_de_echte_reden_zonder_verwijzing_naar_ververs(self):
        _laad([475460, 478660])
        spec = {"figures_json": [*_figuren([RECEPT]), BEWAARD_FOUT], "figure_recipes": [RECEPT, RECEPT_FOUT]}

        with pytest.raises(chat.RefreshError) as exc_info:
            asyncio.run(chat._do_refresh([], [RECEPT, RECEPT_FOUT], spec, mode="reproduceer"))

        melding = str(exc_info.value)
        assert "'Uitstroom' (query mislukt)" in melding
        assert "niet meer in het geheugen" not in melding
        assert "ververs" not in melding.lower()

    def test_do_refresh_noemt_beide_categorieen(self):
        _laad([475460, 478660])
        elders = {**RECEPT, "query": {**RECEPT["query"], "data_key": "cbs:83539NED"}}
        spec = {"figures_json": [], "figure_recipes": [elders, RECEPT_FOUT]}

        with pytest.raises(chat.RefreshError) as exc_info:
            asyncio.run(chat._do_refresh([], [elders, RECEPT_FOUT], spec, mode="reproduceer"))

        melding = str(exc_info.value)
        assert "niet meer in het geheugen" in melding and "Ververs" in melding
        assert "'Uitstroom' (query mislukt)" in melding

    def test_mislukte_reproductie_vervangt_het_dashboard_niet(self):
        _laad([475460, 478660])
        spec = {"figures_json": [BEWAARD_FOUT], "figure_recipes": [RECEPT_FOUT]}

        resp = TestClient(server.app).post(
            "/api/dashboard/refresh",
            json={"mode": "reproduceer", "figure_recipes": [RECEPT_FOUT], "spec": spec},
        )

        assert resp.status_code == 400
        assert "spec" not in resp.json()
        assert "query mislukt" in resp.json()["error"]


class TestVerversPerRecept:
    """#523: ververs koppelt per recept; een mislukt recept houdt zijn bewaarde figuur."""

    def test_mislukt_recept_houdt_zijn_bewaarde_figuur(self):
        _laad([475460, 475460])
        oud_a = _figuren([RECEPT])[0]
        _laad([475460, 478660])  # alleen A verandert bij de bron
        spec = {"figures_json": [oud_a, BEWAARD_FOUT], "figure_recipes": [RECEPT, RECEPT_FOUT]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT, RECEPT_FOUT], spec))

        assert len(nieuw.figures_json) == len(spec["figure_recipes"])
        assert nieuw.figures_json[1] == BEWAARD_FOUT
        assert nieuw.figures_json[0] != oud_a
        [verandering] = veranderingen
        assert verandering.startswith("'Instroom'") and "475.460 → 478.660" in verandering
        assert info is not None
        assert "'Uitstroom' (query mislukt)" in info
        assert "niet bijgewerkt" in info

    def test_eerste_recept_mislukt_geeft_geen_verzonnen_wijziging(self):
        """De reproductie uit #523: op positie werd de verse A met de bewaarde B vergeleken."""
        _laad([475460, 478660])
        oud_a = _figuren([RECEPT])[0]
        spec = {"figures_json": [BEWAARD_FOUT, oud_a], "figure_recipes": [RECEPT_FOUT, RECEPT]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT_FOUT, RECEPT], spec))

        assert veranderingen == []
        assert nieuw.figures_json == [BEWAARD_FOUT, oud_a]
        assert info is not None
        assert "geen wijzigingen" in info and "'Uitstroom' (query mislukt)" in info

    def test_alle_recepten_mislukt_laat_de_spec_ongewijzigd(self):
        _laad([475460, 478660])
        recepten = [RECEPT_FOUT, _recept("Leeg", filters={"aantal": 1})]
        spec = {"figures_json": [BEWAARD_FOUT, "{}"], "figure_recipes": recepten, "ankers": {"85423NED": "2025-01-01"}}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], recepten, spec))

        assert info == "Grafieken konden niet bijgewerkt worden, bestaande data behouden."
        assert nieuw == DashboardSpec.from_dict(spec)
        assert veranderingen == []

    def test_bewaard_dashboard_dat_niet_past_wordt_niet_per_figuur_vergeleken(self):
        """Een ouder dashboard uit de oude ververs-route: minder figuren dan recepten."""
        _laad([475460, 478660])
        lijn = {**RECEPT, "plot": {**RECEPT["plot"], "chart_type": "line", "title": "Lijn"}}
        spec = {"figures_json": [BEWAARD_FOUT], "figure_recipes": [RECEPT, lijn]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT, lijn], spec))

        assert nieuw.figures_json == _figuren([RECEPT, lijn])
        assert veranderingen == []
        assert info is not None and "niet bij zijn recept" in info

    def test_niet_passend_en_mislukt_vervangt_niets(self):
        _laad([475460, 478660])
        spec = {"figures_json": [BEWAARD_FOUT], "figure_recipes": [RECEPT, RECEPT_FOUT]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT, RECEPT_FOUT], spec))

        assert nieuw.figures_json == [BEWAARD_FOUT]
        assert veranderingen == []
        assert info is not None
        assert "past niet bij zijn recept" in info and "'Uitstroom' (query mislukt)" in info

    def test_meer_dan_drie_mislukt_wordt_samengevat(self):
        _laad([475460, 478660])
        mislukt = [_recept(f"Fout {i}", columns=["bestaat_niet"]) for i in range(1, 6)]
        recepten = [RECEPT, *mislukt]
        spec = {"figures_json": _figuren([RECEPT]) + [BEWAARD_FOUT] * 5, "figure_recipes": recepten}

        _, info, _ = asyncio.run(chat._do_refresh([], recepten, spec))

        assert info is not None
        assert "'Fout 1'" in info and "'Fout 3'" in info and "'Fout 4'" not in info
        assert "en nog 2 andere" in info

    def test_mislukking_geeft_een_waarschuwing_in_de_chat(self):
        _laad([475460, 478660])
        spec = {"figures_json": [*_figuren([RECEPT]), BEWAARD_FOUT], "figure_recipes": [RECEPT, RECEPT_FOUT]}
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        asyncio.run(chat._refresh_dashboard([], [RECEPT, RECEPT_FOUT], spec, chat._new_session(), emit, None))

        [eerste_toast] = [e for e in events if e["type"] == "toast"][:1]
        assert eerste_toast["level"] == "warning"
        assert "'Uitstroom' (query mislukt)" in eerste_toast["message"]
        assert events[-1]["type"] == "dashboard_ready"


def test_meldingen_bevatten_geen_ruwe_fouttekst(monkeypatch):
    """#503: de reden is een vaste zin; de uitzondering zelf gaat alleen naar het log."""
    _laad([475460, 478660])
    oud = _figuren([RECEPT])
    echte = replay.dispatch

    def kapot_voor_uitstroom(name, args):
        if args.get("columns") == RECEPT_FOUT["query"]["columns"]:
            raise RuntimeError("/app/data/cache/geheim.parquet: Expecting value")
        return echte(name, args)

    monkeypatch.setattr(replay, "dispatch", kapot_voor_uitstroom)
    recepten = [RECEPT, RECEPT_FOUT]
    spec = {"figures_json": [*oud, BEWAARD_FOUT], "figure_recipes": recepten}

    _, info, veranderingen = asyncio.run(chat._do_refresh([], recepten, spec))
    with pytest.raises(chat.RefreshError) as exc_info:
        asyncio.run(chat._do_refresh([], recepten, spec, mode="reproduceer"))

    meldingen = [info or "", *veranderingen, str(exc_info.value)]
    for tekst in meldingen:
        assert "parquet" not in tekst and "Expecting value" not in tekst and "RuntimeError" not in tekst
    assert "'Uitstroom' (query mislukt)" in meldingen[0]
    assert "'Uitstroom' (query mislukt)" in meldingen[-1]
