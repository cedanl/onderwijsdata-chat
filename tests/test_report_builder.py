from datetime import date
from unittest.mock import patch

from agent.report import ReportSpec, _build_system_prompt, _nl_datum, _parse_spec_from_response


class TestNlDatum:
    def test_formats_dutch_date(self):
        assert _nl_datum(date(2026, 9, 1)) == "1 september 2026"

    def test_defaults_to_today(self):
        assert _nl_datum() == _nl_datum(date.today())


class TestParseSpecFromResponse:
    def test_parses_full_report(self):
        response = """```json
{
  "title": "Instroom ROC van Flevoland 2018-2024",
  "onderzoeksvraag": "Hoe ontwikkelt de eerstejaars instroom zich?",
  "definities": [
    {"begrip": "Eerstejaars", "definitie": "Student die voor het eerst staat ingeschreven"}
  ],
  "beantwoordt": ["De jaarlijkse ontwikkeling van de instroom"],
  "beantwoordt_niet": ["Arbeidsmarktuitstroom van gediplomeerden"],
  "visualisaties": [
    {"titel": "Instroom per jaar", "toelichting": "De instroom stijgt gestaag."}
  ],
  "conclusie": "De instroom is met 18% gestegen.",
  "bronnen": ["DUO — Instroom in het mbo"]
}
```"""
        spec = _parse_spec_from_response(
            response,
            figures_json=['{"data":[],"layout":{}}'],
            context={
                "topic": "Hoe ontwikkelt de eerstejaars instroom zich?",
                "instelling": "ROC van Flevoland",
            },
            author="jansen",
        )

        assert spec.title == "Instroom ROC van Flevoland 2018-2024"
        assert spec.auteur == "jansen"
        assert spec.datum == _nl_datum()
        assert len(spec.definities) == 1
        assert spec.definities[0]["begrip"] == "Eerstejaars"
        assert spec.beantwoordt == ["De jaarlijkse ontwikkeling van de instroom"]
        assert spec.beantwoordt_niet == ["Arbeidsmarktuitstroom van gediplomeerden"]
        assert spec.conclusie == "De instroom is met 18% gestegen."
        assert "18%" in spec.conclusie
        # Bronnen komen uit het recept, niet uit het model (#196); hier geen datasets.
        assert spec.bronnen == []

        assert len(spec.visualisaties) == 1
        vis = spec.visualisaties[0]
        assert vis["titel"] == "Instroom per jaar"
        assert "stijgt gestaag" in vis["toelichting"]
        assert vis["figure_json"] == '{"data":[],"layout":{}}'

    def test_visualisaties_pair_with_figures_in_order(self):
        spec = _parse_spec_from_response(
            '{"title": "T", "onderzoeksvraag": "Vraag", "visualisaties": [{"titel": "Eerste"}, {"titel": "Tweede"}]}',
            figures_json=["fig1", "fig2"],
            context={"topic": "Vraag"},
        )

        assert [v["titel"] for v in spec.visualisaties] == ["Eerste", "Tweede"]
        assert spec.visualisaties[0]["figure_json"] == "fig1"
        assert spec.visualisaties[1]["figure_json"] == "fig2"

    def test_falls_back_when_response_has_no_json(self):
        spec = _parse_spec_from_response(
            "Geen bruikbare output",
            figures_json=[],
            context={"topic": "Mijn onderzoeksvraag"},
            author="jan",
        )

        assert spec.title == "Mijn onderzoeksvraag"
        assert spec.onderzoeksvraag == "Mijn onderzoeksvraag"
        assert spec.auteur == "jan"
        assert spec.visualisaties == []
        assert spec.bronnen == []

    def test_sources_come_from_the_recipe_with_the_catalog_title(self):
        # Live-audit 8: het model schreef "Inschrijvingen in het hoger onderwijs; instellingen,
        # opleidingen (85423NED)". Het ID klopte, de titel was verzonnen (#196).
        titels = {"p01hoinges": "Ingeschrevenen hoger onderwijs", "85423NED": "Hoger onderwijs; ingeschrevenen"}
        with patch("agent.dashboard.catalogus_titel", side_effect=lambda d: titels.get(d, d)), \
             patch("agent.dashboard.resource_titel", return_value="Ingeschrevenen hbo"):
            spec = _parse_spec_from_response(
                '{"title": "T", "onderzoeksvraag": "V", "bronnen": ["CBS — Inschrijvingen; instellingen (85423NED)"]}',
                figures_json=[],
                context={"topic": "V", "datasets": [{"data_key": "duo:p01hoinges:0"}, {"data_key": "cbs:85423NED"}]},
            )

        assert spec.bronnen == [
            "DUO — Ingeschrevenen hoger onderwijs (p01hoinges), Ingeschrevenen hbo",
            "CBS — Hoger onderwijs; ingeschrevenen (85423NED)",
        ]

    def test_source_without_catalog_title_keeps_its_id(self):
        with patch("agent.dashboard.catalogus_titel", side_effect=lambda d: d), \
             patch("agent.dashboard.resource_titel", return_value=None):
            spec = _parse_spec_from_response(
                '{"title": "T"}', figures_json=[], context={"topic": "V", "datasets": [{"data_key": "cbs:99999NED"}]},
            )

        assert spec.bronnen == ["CBS — 99999NED"]


class TestReportSpec:
    def test_serialization(self):
        spec = ReportSpec(
            title="Test",
            onderzoeksvraag="Vraag",
            visualisaties=[{"titel": "V1", "toelichting": "x", "figure_json": "{}"}],
            auteur="jan",
            datum="1 september 2026",
        )
        data = spec.to_dict()
        assert data["title"] == "Test"
        assert len(data["visualisaties"]) == 1
        assert data["auteur"] == "jan"
        assert data["datum"] == "1 september 2026"


class TestSystemPromptHerkomst:
    def test_names_the_selection_the_conversation_made(self):
        # #174 regressie: GPT vond in de chat de HU/VT-reeks, het rapport meldde daarna
        # "geen rijen voor 25DW" omdat het de selectie opnieuw moest raden.
        load = {"name": "get_duo_data", "arguments": {"dataset_id": "p01hoinges", "resource": 3}}
        query = {"name": "query_data", "arguments": {
            "data_key": "duo:p01hoinges:3",
            "filters": {"INSTELLINGSCODE_ACTUEEL": "25DW", "OPLEIDINGSVORM": "VT"},
            "group_by": ["STUDIEJAAR"], "aggregate": {"AANTAL": "sum"},
        }}
        context = {"datasets": [{
            "data_key": "duo:p01hoinges:3:74a5c5e2", "row_count": 5,
            "columns": [{"naam": "STUDIEJAAR", "type": "int64", "voorbeelden": ["2021"]}],
            "herkomst": [load, query],
        }]}

        prompt = _build_system_prompt(context)

        assert '"INSTELLINGSCODE_ACTUEEL": "25DW"' in prompt
        assert '"OPLEIDINGSVORM": "VT"' in prompt
        assert "get_duo_data" in prompt

    def test_dataset_without_herkomst_is_marked_as_such(self):
        context = {"datasets": [{"data_key": "cbs:85423NED", "row_count": 1, "columns": [], "herkomst": []}]}
        assert "Herkomst: onbekend" in _build_system_prompt(context)
