"""De datasetcontext van een rapport: datasets, herstel na een herstart en het herlaadrecept (#765: uit agent/dashboard.py)."""

import asyncio
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import recepten
from agent.datasetcontext import build_dataset_context, build_recipe, herstel_data
from agent.session_data import DATA_WEG
from core.errors import Gebruikersfout
from tools import store
from tools.store import KeyMeta


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

        with pytest.raises(Gebruikersfout, match="niet meer beschikbaar") as fout:
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

    def test_says_whether_each_dataset_is_the_whole_source(self):
        """#578: a report has to know that a key is one page of its source (#186)."""
        store.put("cbs:85425NED", pd.DataFrame({"a": [1, 2]}), KeyMeta(bron="cbs", dataset="85425NED", volledig=False))
        store.derive("cbs:85425NED", "cbs:85425NED:aa", pd.DataFrame({"a": [1]}))
        store.put("cbs:85423NED", pd.DataFrame({"a": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
        store.put("rio:erkenningen", pd.DataFrame({"a": [1]}))
        session = {"data_keys": ["cbs:85425NED", "cbs:85425NED:aa", "cbs:85423NED", "rio:erkenningen"]}

        volledig = {ds["data_key"]: ds["volledig"] for ds in build_dataset_context(session)["datasets"]}

        assert volledig == {
            "cbs:85425NED": False,
            "cbs:85425NED:aa": False,
            "cbs:85423NED": True,
            "rio:erkenningen": True,
        }

    def test_includes_instelling(self):
        context = build_dataset_context({"chat_settings": {"instelling": "Hogeschool Utrecht"}})
        assert context["instelling"] == "Hogeschool Utrecht"

    def test_includes_conversation_topic(self):
        session = {
            "turns": [{"question": "Hoeveel studenten heeft de HU?", "tool_calls": []}],
            "chat_settings": {},
        }
        assert "HU" in build_dataset_context(session)["topic"]

    def test_topic_is_the_first_question_after_reopening(self):
        """#732: een heropend gesprek begint met lege turns; de vraag erna werd het onderwerp."""
        session = {
            "messages": [
                {"role": "user", "content": "Hoe ontwikkelt het bachelorrendement in het wo zich?"},
                {"role": "assistant", "content": "Het rendement stijgt."},
                {"role": "user", "content": "Genereer een rapport dat ingaat op je laatste antwoord"},
            ],
            "turns": [{"question": "Genereer een rapport dat ingaat op je laatste antwoord", "tool_calls": []}],
        }
        assert build_dataset_context(session)["topic"] == "Hoe ontwikkelt het bachelorrendement in het wo zich?"

    def test_topic_is_the_question_not_the_clarification_choice(self):
        """#732: een vraag met een verduidelijkingskaart wordt geen beurt; de gekozen optie werd het onderwerp."""
        session = {
            "messages": [
                {"role": "user", "content": "Hoeveel studenten heeft de hogeschool in Utrecht?"},
                {"role": "assistant", "content": "Welke hogeschool bedoel je?"},
                {"role": "user", "content": "Hogeschool Utrecht"},
            ],
            "turns": [{"question": "Hogeschool Utrecht", "tool_calls": []}],
        }
        assert build_dataset_context(session)["topic"] == "Hoeveel studenten heeft de hogeschool in Utrecht?"


def _datasets(*keys, herkomst=None):
    return [{"data_key": k, **({"herkomst": herkomst[k]} if herkomst and k in herkomst else {})} for k in keys]


class TestHerstelData:
    """Vóór een rapport: wat een herstart uit de store wiste, komt terug uit zijn recept (#472)."""

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

        with pytest.raises(Gebruikersfout) as fout:
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

        with pytest.raises(Gebruikersfout) as fout:
            self._herstel(session)
        assert "eigen berekening (run_analysis)" in str(fout.value)
        assert "analysis:abc" in str(fout.value)
        assert "Stel je vraag opnieuw" in str(fout.value)

    def test_het_recept_van_een_ander_telt_niet(self, _db):
        _db.save_recipes("bob", "c1", {"rio:erkenningen": {"laad": ["get_rio_data", {"resource": "erkenningen"}]}})
        session = {"username": "alice", "data_keys": ["rio:erkenningen"], "chat_settings": {}}

        with pytest.raises(Gebruikersfout, match="niet meer beschikbaar"):
            self._herstel(session)
        assert store.get("rio:erkenningen") is None


class TestBuildRecipe:
    def test_builds_reload_calls_from_data_keys(self):
        recipe = build_recipe(_datasets("duo:p01hoinges:0", "cbs:85421NED", "query:abc"))
        assert [r["name"] for r in recipe] == ["get_duo_data", "get_cbs_data"]

    def test_no_keys(self):
        assert build_recipe([]) == []

    def test_derived_duo_key_reloads_its_source_resource(self):
        [call] = build_recipe(_datasets("duo:p01hoinges:3:74a5c5e2"))
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

        recipe = build_recipe(datasets)

        assert recipe == [{"name": "get_cbs_data", "arguments": json.dumps(load["arguments"])}]
