"""De twee herhaalmodi van #346: ververs en reproduceer.

- reproduceer rendert uit de data in de store, zonder netwerk, en is byte-identiek.
- ververs haalt opnieuw op en benoemt de gewijzigde waarden en bron-ankers.
- een mislukte figuur wordt met haar echte reden gemeld en vervangt niets (#523).
"""

import asyncio
import json
import socket
import threading

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
from tools import cbs, store
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


CBS_CALL = {"name": "get_cbs_data", "arguments": json.dumps({"dataset_id": "85423NED"})}
DUO_CALL = {"name": "get_duo_data", "arguments": json.dumps({"dataset_id": "p01hoinges", "resource": 0})}


class GeenNetwerk(AssertionError):
    pass


@pytest.fixture
def geen_netwerk(monkeypatch):
    """Elke netwerkverbinding faalt: wie toch de bron raadpleegt, laat de test vallen (#524)."""

    def weiger(*args, **kwargs):
        raise GeenNetwerk("netwerkverbinding geopend")

    monkeypatch.setattr(socket.socket, "connect", weiger)
    monkeypatch.setattr(socket.socket, "connect_ex", weiger)
    monkeypatch.setattr(socket, "create_connection", weiger)


def _laad_bij_bron(monkeypatch, waarden: list[int]) -> None:
    """De load-tools geven `waarden` terug zoals de bron dat zou doen; query en plot blijven echt."""
    echte = replay.dispatch

    def dispatch(name, args):
        if name in replay.REPLAYABLE_TOOLS:
            _laad(waarden)
            return json.dumps({"data_key": KEY}), None
        return echte(name, args)

    monkeypatch.setattr(replay, "dispatch", dispatch)


def _figuren(figure_recipes: list[dict]) -> list[str]:
    """De figuren die ververs nu uit de store maakt, zoals een bewaard dashboard ze heeft."""
    figuren = [u.figuur_json for u in replay_dashboard_figures([], figure_recipes).uitkomsten]
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

    def test_reproduceer_na_ververs_met_cbs_recept_is_byte_identiek(self, monkeypatch, geen_netwerk):
        """#524: ook met een get_cbs_data-call in het recept (gemockte load) en een data_key per figuur."""
        _laad_bij_bron(monkeypatch, [475460, 478660])
        _laad([475460, 478660])
        bewaard = {"figures_json": _figuren([RECEPT]), "recipe": [CBS_CALL], "figure_recipes": [RECEPT]}

        vers, _, _ = asyncio.run(chat._do_refresh([CBS_CALL], [RECEPT], bewaard, mode="ververs"))
        opgeslagen = vers.to_dict()
        eerste, info, veranderingen = asyncio.run(
            chat._do_refresh([CBS_CALL], [RECEPT], opgeslagen, mode="reproduceer")
        )
        tweede, _, _ = asyncio.run(chat._do_refresh([CBS_CALL], [RECEPT], opgeslagen, mode="reproduceer"))

        assert eerste.figures_json == tweede.figures_json == opgeslagen["figures_json"]
        assert veranderingen == []
        assert info is not None and "identiek" in info

    def test_reproduceer_raakt_de_bron_niet(self, monkeypatch, geen_netwerk):
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

    def test_netwerkwacht_vangt_een_verbinding(self, geen_netwerk):
        """De wacht van de test hierboven werkt: een verbinding faalt."""
        with pytest.raises(GeenNetwerk):
            socket.create_connection(("127.0.0.1", 9))
        with pytest.raises(GeenNetwerk):
            socket.socket().connect(("127.0.0.1", 9))

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


class TestReproduceerAfwijking:
    """#524: reproduceer toont wat afwijkt, per figuur, naast de melding."""

    def test_afwijkende_reproductie_noemt_de_waarden(self):
        _laad([475460, 475460])
        bewaard = _figuren([RECEPT])
        _laad([475460, 478660])  # de opgeslagen data wijkt af van wat het dashboard toont
        spec = {"figures_json": bewaard, "figure_recipes": [RECEPT]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="reproduceer"))

        [regel] = veranderingen
        assert regel.startswith("'Instroom'") and "2024" in regel and "475.460 → 478.660" in regel
        assert info is not None and "wijkt af" in info and "niet aangepast" in info
        assert "identiek" not in info
        assert nieuw.figures_json != bewaard

    def test_afwijking_per_recept_ook_bij_twee_figuren(self):
        _laad([475460, 475460])
        lijn = {**RECEPT, "plot": {**RECEPT["plot"], "chart_type": "line", "title": "Lijn"}}
        bewaard = _figuren([RECEPT, lijn])
        _laad([475460, 478660])
        spec = {"figures_json": bewaard, "figure_recipes": [RECEPT, lijn]}

        _, _, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT, lijn], spec, mode="reproduceer"))

        assert [v.split(",")[0] for v in veranderingen] == ["'Instroom'", "'Lijn'"]

    def test_niet_passend_bewaard_dashboard_geeft_geen_regels(self):
        _laad([475460, 478660])
        lijn = {**RECEPT, "plot": {**RECEPT["plot"], "chart_type": "line", "title": "Lijn"}}
        spec = {"figures_json": [BEWAARD_FOUT], "figure_recipes": [RECEPT, lijn]}

        _, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT, lijn], spec, mode="reproduceer"))

        assert veranderingen == []
        assert info is not None and "niet per grafiek te vergelijken" in info and "niet aangepast" in info

    def test_alleen_opmaak_anders_zegt_dat_de_waarden_gelijk_zijn(self):
        _laad([475460, 478660])
        [vers] = _figuren([RECEPT])
        opmaak = json.loads(vers)
        opmaak["layout"]["height"] = 999
        spec = {"figures_json": [json.dumps(opmaak)], "figure_recipes": [RECEPT]}

        _, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="reproduceer"))

        assert veranderingen == []
        assert info is not None and "opmaak" in info and "identiek" not in info

    def test_melding_biedt_de_reproductie_niet_aan(self):
        """De reproductie wordt niet bewaard; de melding wekt die indruk ook niet."""
        _laad([475460, 475460])
        bewaard = _figuren([RECEPT])
        _laad([475460, 478660])
        spec = {"figures_json": bewaard, "figure_recipes": [RECEPT]}

        _, info, _ = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="reproduceer"))

        assert info is not None
        for woord in ("bekijk", "bewaar de", "opslaan", "vervang"):
            assert woord not in info.lower()

    def test_endpoint_geeft_de_afwijkingen_terug(self):
        _laad([475460, 475460])
        bewaard = _figuren([RECEPT])
        _laad([475460, 478660])
        spec = {"figures_json": bewaard, "figure_recipes": [RECEPT]}

        resp = TestClient(server.app).post(
            "/api/dashboard/refresh", json={"mode": "reproduceer", "figure_recipes": [RECEPT], "spec": spec}
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "reproduceer"
        assert any("475.460 → 478.660" in v for v in body["veranderingen"])
        assert "wijkt af" in body["melding"]


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
        assert "niets opgehaald" in info.lower()  # de ververs-route, niet reproduceer (#528: zonder datarecept)

    # #528: "Data ververst" alleen als er bij de bron iets is opgehaald.
    def test_ververs_zonder_datarecept_zegt_dat_de_bron_niet_geraakt_is(self):
        _laad([475460, 475460])
        oud = _figuren([RECEPT])
        _laad([475460, 478660])
        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([], [RECEPT], spec, mode="ververs"))

        assert info is not None
        assert info.startswith("Bij de bron is niets opgehaald: dit dashboard heeft geen datarecept")
        assert "Data ververst" not in info
        assert "1 wijziging(en)" in info and nieuw.figures_json != oud and veranderingen

    def test_ververs_met_datarecept_meldt_data_ververst(self, monkeypatch):
        _laad([475460, 478660])
        oud = _figuren([RECEPT])
        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}
        opgehaald = []
        echte = replay.dispatch

        def dispatch(name, args):
            if name != "get_cbs_data":
                return echte(name, args)  # de figuurrecepten (query_data) lopen gewoon door
            opgehaald.append(name)
            _laad([475460, 478660])
            return "ok", None

        monkeypatch.setattr(replay, "dispatch", dispatch)
        recipe = [{"name": "get_cbs_data", "arguments": json.dumps({"dataset_id": "85423NED"})}]

        _, info, _ = asyncio.run(chat._do_refresh(recipe, [RECEPT], spec, mode="ververs"))

        assert opgehaald == ["get_cbs_data"]
        assert info is not None and info.startswith("Data ververst; geen wijzigingen")

    def test_zonder_datarecept_komt_de_melding_als_waarschuwing_in_de_chat(self):
        """Niets opgehaald is geen succes: de toast is een waarschuwing, geen 'info'."""
        _laad([475460, 478660])
        oud = _figuren([RECEPT])
        spec = {"figures_json": oud, "figure_recipes": [RECEPT]}
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        asyncio.run(chat._refresh_dashboard([], [RECEPT], spec, chat._new_session(), emit, None, "ververs"))

        [toast] = [e for e in events if e.get("type") == "toast" and "niets opgehaald" in e.get("message", "")]
        assert toast["level"] == "warning"


MISLUKTE_CALLS = ["niet toegestaan", "uitzondering", "cbs onbereikbaar"]


class TestHerladenMislukt:
    """#524: ververs meldt alleen "ververst" als elke dataoproep echt herlaadde."""

    @staticmethod
    def _recipe_met_falende_call(monkeypatch, soort: str) -> list[dict]:
        echte = replay.dispatch

        def dispatch(name, args):
            if name == "get_duo_data":
                if soort == "uitzondering":
                    raise ValueError("/app/data/cache/geheim.parquet: Expecting value")
                if soort == "cbs onbereikbaar":
                    raise ConnectionError("opendata.cbs.nl: Name or service not known")
            if name in replay.REPLAYABLE_TOOLS:
                _laad([475460, 478660])
                return json.dumps({"data_key": KEY}), None
            return echte(name, args)

        monkeypatch.setattr(replay, "dispatch", dispatch)
        falend = {"name": "run_analysis", "arguments": "{}"} if soort == "niet toegestaan" else DUO_CALL
        return [CBS_CALL, falend]

    @pytest.mark.parametrize("soort", MISLUKTE_CALLS)
    @pytest.mark.parametrize("met_figuurrecepten", [True, False])
    def test_do_refresh_weigert_bij_een_mislukte_call(self, monkeypatch, soort, met_figuurrecepten):
        _laad([475460, 478660])
        recipe = self._recipe_met_falende_call(monkeypatch, soort)
        figure_recipes = [RECEPT] if met_figuurrecepten else []
        spec = {"figures_json": _figuren([RECEPT]), "recipe": recipe, "figure_recipes": figure_recipes}

        with pytest.raises(chat.RefreshError) as exc_info:
            asyncio.run(chat._do_refresh(recipe, figure_recipes, spec))

        melding = str(exc_info.value)
        assert "niet opnieuw opgehaald" in melding and "1 van de 2" in melding
        assert "ververst" not in melding.lower() and "herladen." not in melding.lower()
        for ruw in ("parquet", "Expecting value", "cbs.nl", "ValueError", "ConnectionError", "run_analysis"):
            assert ruw not in melding

    @pytest.mark.parametrize("soort", MISLUKTE_CALLS)
    def test_endpoint_geeft_400_zonder_spec(self, monkeypatch, soort):
        _laad([475460, 478660])
        recipe = self._recipe_met_falende_call(monkeypatch, soort)
        spec = {"figures_json": _figuren([RECEPT]), "recipe": recipe, "figure_recipes": [RECEPT]}

        resp = TestClient(server.app).post(
            "/api/dashboard/refresh",
            json={"mode": "ververs", "recipe": recipe, "figure_recipes": [RECEPT], "spec": spec},
        )

        assert resp.status_code == 400
        body = resp.json()
        assert "spec" not in body
        assert "1 van de 2" in body["error"] and "Data ververst" not in body["error"]
        assert "parquet" not in body["error"] and "cbs.nl" not in body["error"]

    @pytest.mark.parametrize("met_figuurrecepten", [True, False])
    def test_websocket_geeft_een_fout_en_geen_dashboard(self, monkeypatch, met_figuurrecepten):
        _laad([475460, 478660])
        recipe = self._recipe_met_falende_call(monkeypatch, "uitzondering")
        figure_recipes = [RECEPT] if met_figuurrecepten else []
        spec = {"figures_json": _figuren([RECEPT]), "recipe": recipe, "figure_recipes": figure_recipes}
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        asyncio.run(chat._refresh_dashboard(recipe, figure_recipes, spec, chat._new_session(), emit, None))

        assert [e["type"] for e in events] == ["dashboard_generating", "error"]
        assert "1 van de 2" in events[-1]["message"]

    def test_alle_calls_geslaagd_ververst_als_voorheen(self, monkeypatch):
        _laad([475460, 475460])
        bewaard = _figuren([RECEPT])
        _laad_bij_bron(monkeypatch, [475460, 478660])
        spec = {"figures_json": bewaard, "recipe": [CBS_CALL, DUO_CALL], "figure_recipes": [RECEPT]}

        _, info, veranderingen = asyncio.run(chat._do_refresh([CBS_CALL, DUO_CALL], [RECEPT], spec))

        assert info is not None and info.startswith("Data ververst")
        assert any("475.460 → 478.660" in v for v in veranderingen)

    def test_legacy_pad_zonder_mislukking_meldt_herladen(self, monkeypatch):
        _laad_bij_bron(monkeypatch, [475460, 478660])

        _, info, _ = asyncio.run(chat._do_refresh([CBS_CALL], [], {"recipe": [CBS_CALL]}))

        assert info is not None and info.startswith("Data herladen")


class TestNietOpDeEventLoop:
    """#524: de ankers (netwerk) en het herladen draaien in een thread, niet op de event loop."""

    def test_ververs_figuren_vraagt_ankers_buiten_de_loop(self, monkeypatch):
        _laad([475460, 478660])
        threads: dict[str, int] = {}

        def ankers(recipe, vorige=None):
            threads["ankers"] = threading.get_ident()
            return {}

        echte_replay = chat.replay_dashboard_figures

        def replay_dashboard_figures(recipe, figure_recipes):
            threads["replay"] = threading.get_ident()
            return echte_replay(recipe, figure_recipes)

        monkeypatch.setattr(chat, "ankers_van_recipe", ankers)
        monkeypatch.setattr(chat, "replay_dashboard_figures", replay_dashboard_figures)
        spec = {"figures_json": _figuren([RECEPT]), "figure_recipes": [RECEPT]}

        async def scenario():
            threads["loop"] = threading.get_ident()
            await chat._do_refresh([], [RECEPT], spec)

        asyncio.run(scenario())

        assert threads["ankers"] != threads["loop"]
        assert threads["replay"] != threads["loop"]

    def test_legacy_pad_herlaadt_buiten_de_loop(self, monkeypatch):
        threads: dict[str, int] = {}

        def replay_data_calls(recipe):
            threads["replay"] = threading.get_ident()
            return [{"name": "get_cbs_data", "arguments": "{}", "success": True, "output": "{}"}]

        monkeypatch.setattr(chat, "replay_data_calls", replay_data_calls)

        async def scenario():
            threads["loop"] = threading.get_ident()
            await chat._do_refresh([CBS_CALL], [], {})

        asyncio.run(scenario())

        assert threads["replay"] != threads["loop"]


class TestAnkers:
    def test_ankers_van_recipe_alleen_cbs(self, monkeypatch):
        monkeypatch.setattr(replay, "catalogus_laatste_update", lambda ds: {"85423NED": "2026-01-15"}.get(ds))
        recipe = [
            {"name": "get_cbs_data", "arguments": json.dumps({"dataset_id": "85423NED"})},
            {"name": "get_duo_data", "arguments": json.dumps({"dataset_id": "p01hoinges"})},
            {"name": "get_cbs_data", "arguments": "geen json"},
        ]
        assert ankers_van_recipe(recipe) == {"85423NED": "2026-01-15"}

    def test_ankers_zien_een_bijgewerkte_tabel_zonder_herstart(self, monkeypatch):
        """#524: de catalogus is een momentopname; het anker vraagt CBS per aanroep."""
        bron = {"Modified": "2026-04-10T02:00:00"}
        gevraagd: list[tuple[str, str]] = []

        def get(dataset_id, endpoint, **params):
            gevraagd.append((dataset_id, endpoint))
            return [dict(bron)]

        monkeypatch.setattr(cbs, "get", get)

        assert ankers_van_recipe([CBS_CALL]) == {"85423NED": "2026-04-10"}
        bron["Modified"] = "2026-10-01T02:00:00"  # CBS werkt de tabel bij terwijl de server draait
        assert ankers_van_recipe([CBS_CALL]) == {"85423NED": "2026-10-01"}
        assert gevraagd == [("85423NED", "TableInfos")] * 2

    def test_ververs_meldt_een_bij_de_bron_bijgewerkte_tabel(self, monkeypatch):
        _laad_bij_bron(monkeypatch, [475460, 478660])
        _laad([475460, 478660])
        monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: [{"Modified": "2026-10-01T02:00:00"}])
        spec = {"figures_json": _figuren([RECEPT]), "figure_recipes": [RECEPT], "ankers": {"85423NED": "2026-04-10"}}

        nieuw, _, veranderingen = asyncio.run(chat._do_refresh([CBS_CALL], [RECEPT], spec))

        assert nieuw.ankers == {"85423NED": "2026-10-01"}
        assert "CBS-tabel 85423NED is bij de bron bijgewerkt op 2026-10-01 (was 2026-04-10)." in veranderingen

    def test_cbs_onbereikbaar_houdt_het_bewaarde_anker(self, monkeypatch):
        def onbereikbaar(dataset_id, endpoint, **params):
            raise ConnectionError("opendata.cbs.nl onbereikbaar")

        monkeypatch.setattr(cbs, "get", onbereikbaar)

        assert ankers_van_recipe([CBS_CALL], {"85423NED": "2026-09-01"}) == {"85423NED": "2026-09-01"}
        # Zonder bewaard anker blijft de catalogusdatum over.
        assert ankers_van_recipe([CBS_CALL]) == {"85423NED": "2026-04-10"}

    def test_ververs_faalt_niet_op_een_onbereikbaar_anker(self, monkeypatch):
        _laad_bij_bron(monkeypatch, [475460, 478660])
        _laad([475460, 478660])

        def onbereikbaar(dataset_id, endpoint, **params):
            raise ConnectionError("opendata.cbs.nl onbereikbaar")

        monkeypatch.setattr(cbs, "get", onbereikbaar)
        spec = {"figures_json": _figuren([RECEPT]), "figure_recipes": [RECEPT], "ankers": {"85423NED": "2026-09-01"}}

        nieuw, info, veranderingen = asyncio.run(chat._do_refresh([CBS_CALL], [RECEPT], spec))

        assert nieuw.ankers == {"85423NED": "2026-09-01"}
        assert veranderingen == []
        assert info is not None and info.startswith("Data ververst")

    @pytest.mark.parametrize("dataset", ["onbekend", "../../ODataCatalog/Tables", "p01hoinges"])
    def test_bron_wordt_alleen_voor_cbs_tabellen_uit_de_catalogus_gevraagd(self, monkeypatch, dataset):
        gevraagd: list[str] = []
        monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: gevraagd.append(dataset_id) or [])

        assert cbs.bron_laatste_update(dataset) is None
        assert gevraagd == []

    @pytest.mark.parametrize("antwoord", [[], [{}], [{"Modified": None}], [{"Modified": "gisteren"}], ["geen dict"]])
    def test_onbruikbaar_antwoord_is_geen_datum(self, monkeypatch, antwoord):
        monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: antwoord)
        assert cbs.bron_laatste_update("85423NED") is None

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
