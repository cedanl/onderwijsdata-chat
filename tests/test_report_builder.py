from datetime import date
from unittest.mock import patch

from agent.report import ReportSpec, _nl_datum, _parse_spec_from_response


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
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = ["duo:p01hoinges:0"]

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
        assert spec.bronnen == ["DUO — Instroom in het mbo"]

        assert len(spec.visualisaties) == 1
        vis = spec.visualisaties[0]
        assert vis["titel"] == "Instroom per jaar"
        assert "stijgt gestaag" in vis["toelichting"]
        assert vis["figure_json"] == '{"data":[],"layout":{}}'

    def test_visualisaties_pair_with_figures_in_order(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = []

            spec = _parse_spec_from_response(
                '{"title": "T", "onderzoeksvraag": "Vraag", "visualisaties": [{"titel": "Eerste"}, {"titel": "Tweede"}]}',
                figures_json=["fig1", "fig2"],
                context={"topic": "Vraag"},
            )

        assert [v["titel"] for v in spec.visualisaties] == ["Eerste", "Tweede"]
        assert spec.visualisaties[0]["figure_json"] == "fig1"
        assert spec.visualisaties[1]["figure_json"] == "fig2"

    def test_falls_back_when_response_has_no_json(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = []

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

    def test_sources_fall_back_to_recipe(self):
        with patch("agent.dashboard.store") as mock_store:
            mock_store.list_keys.return_value = ["duo:p01hoinges:0", "cbs:85421NED"]

            spec = _parse_spec_from_response(
                '{"title": "T", "onderzoeksvraag": "V"}',
                figures_json=[],
                context={"topic": "V"},
            )

        assert spec.bronnen == ["DUO — p01hoinges", "CBS — 85421NED"]


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
