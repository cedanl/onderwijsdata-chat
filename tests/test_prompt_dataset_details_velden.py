"""De prompt en de uitvoer van dataset_details noemen dezelfde velden (#542).

Sinds riodata 0.5.0 vallen voor grote DUO-datasets de voorbeeldwaarden (en soms de kolomtypes) weg
en zegt `kolomdetail_weggelaten` dat. De prompt beschreef `_kolommen` als altijd aanwezig: een regel
over "als _kolommen uitsluitend numerieke waarden toont" ging dan over een veld dat er niet is.
"""

import re
from pathlib import Path

from tests.test_details_budget import _ENTRY, _breed, _details

_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "system.md"


def _velden_in_prompt() -> set[str]:
    """De velden die de prompt onder 'Velden via dataset_details' opsomt (**`veld`**)."""
    tekst = _PROMPT.read_text(encoding="utf-8")
    sectie = tekst.split("### Velden via dataset_details", 1)[1].split("###", 1)[0]
    return set(re.findall(r"^- \*\*`([A-Za-z_]+)`\*\*", sectie, flags=re.MULTILINE))


def test_de_prompt_noemt_het_weggelaten_kolomdetail():
    velden = _velden_in_prompt()
    assert "kolomdetail_weggelaten" in velden
    assert {"_kolommen", "_kolomtypes", "_kolomdefinities", "_resources"} <= velden


def test_elk_genoemd_veld_komt_in_de_uitvoer_voor_met_of_zonder_kolomdetail():
    volledig = _details({**_ENTRY, "_kolomdefinities": {"LEERTRAJECT": "BOL of BBL"}})
    zonder = _details(_breed("tekst " + "y" * 120))

    assert "kolomdetail_weggelaten" in zonder and "_kolommen" not in zonder and "_kolomtypes" not in zonder
    assert "kolomdetail_weggelaten" not in volledig
    assert _velden_in_prompt() <= set(volledig) | set(zonder)


def test_de_melding_wijst_naar_get_duo_data_zoals_de_prompt_zegt():
    zonder = _details(_breed("tekst " + "y" * 120))
    assert "get_duo_data" in zonder["kolomdetail_weggelaten"]
    assert "_resources" in zonder["kolomdetail_weggelaten"]
