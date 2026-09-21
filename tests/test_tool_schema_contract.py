"""Bewaakt dat tool-schema, prompt en code hetzelfde zeggen.

#50 ging hier mis: de prompt instrueerde `chart_type="auto"` en de code accepteerde dat,
maar het tool-schema liet de waarde niet toe. Bij een provider met strikte schema-validatie
wordt zo'n aanroep geweigerd; bij een soepele provider glipt hij erdoor en werkt het bij
toeval. Precies de modelafhankelijkheid die #50 moest wegnemen.

De beslisboom zelf staat in test_chart_type_auto.py. Hier gaat het om de naden.
"""

import inspect
import re
from pathlib import Path

import pytest

from tools import _HANDLERS
from tools.plot import _infer_chart_type
from tools.schemas import TOOL_CLARIFY_SCOPE, TOOL_CREATE_PLOT, TOOL_SCHEMAS

_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "system.md"

# Tools die agent/run.py zelf afvangt vóór dispatch(): UI-interactie, geen data-tool.
# Expliciet opgesomd, zodat een écht vergeten handler alsnog opvalt.
_AGENT_AFGEVANGEN = {TOOL_CLARIFY_SCOPE}


def _schema(naam: str) -> dict:
    return next(s for s in TOOL_SCHEMAS if s["function"]["name"] == naam)


def _params(naam: str) -> dict:
    return _schema(naam)["function"]["parameters"]


@pytest.mark.parametrize("schema", TOOL_SCHEMAS, ids=lambda s: s["function"]["name"])
def test_elke_schemaparameter_wordt_door_de_handler_geaccepteerd(schema):
    """dispatch() doet handler(**tool_input), dus een onbekende parameter is een TypeError."""
    naam = schema["function"]["name"]
    if naam not in _HANDLERS:
        assert naam in _AGENT_AFGEVANGEN, f"{naam} heeft geen handler en wordt ook niet afgevangen"
        pytest.skip(f"{naam} wordt door de agent-loop afgevangen")

    signatuur = inspect.signature(_HANDLERS[naam]).parameters

    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signatuur.values()):
        pytest.skip(f"{naam} accepteert **kwargs")

    aangeboden = schema["function"]["parameters"]["properties"].keys()
    onbekend = [p for p in aangeboden if p not in signatuur]

    assert not onbekend, f"{naam}: schema biedt {onbekend} aan, maar de functie accepteert dat niet"


@pytest.mark.parametrize("schema", TOOL_SCHEMAS, ids=lambda s: s["function"]["name"])
def test_verplichte_parameters_staan_ook_in_properties(schema):
    params = schema["function"]["parameters"]
    ontbrekend = [p for p in params.get("required", []) if p not in params["properties"]]

    assert not ontbrekend, f"{schema['function']['name']}: {ontbrekend} verplicht maar niet beschreven"


class TestChartTypeContract:
    def test_auto_is_een_toegestane_waarde(self):
        """De code heeft 'auto' als default; het schema moet die keuze toelaten."""
        assert "auto" in _params(TOOL_CREATE_PLOT)["properties"]["chart_type"]["enum"]

    def test_is_share_staat_in_het_schema(self):
        """Zonder dit is de pie-tak van de beslisboom onbereikbaar voor het model."""
        assert "is_share" in _params(TOOL_CREATE_PLOT)["properties"]

    def test_elke_uitkomst_van_de_beslisboom_is_ook_expliciet_kiesbaar(self):
        toegestaan = set(_params(TOOL_CREATE_PLOT)["properties"]["chart_type"]["enum"])
        uitkomsten = {
            _infer_chart_type(x, "AANTAL", kleur, groepen, aandeel)
            for x in ("JAAR", "INSTELLING")
            for kleur in (None, "GESLACHT")
            for groepen in (1, 3, 9)
            for aandeel in (False, True)
        }

        assert uitkomsten <= toegestaan, f"beslisboom kan {uitkomsten - toegestaan} opleveren"

    def test_prompt_noemt_geen_charttype_dat_het_schema_verbiedt(self):
        """De directe regressietest voor #50."""
        toegestaan = set(_params(TOOL_CREATE_PLOT)["properties"]["chart_type"]["enum"])
        genoemd = set(re.findall(r"""chart_type=["']([a-z_]+)["']""", _PROMPT.read_text()))

        assert genoemd, "geen chart_type-voorbeelden in de prompt gevonden — is de regex nog goed?"
        assert genoemd <= toegestaan, f"prompt instrueert {genoemd - toegestaan}, schema staat dat niet toe"
