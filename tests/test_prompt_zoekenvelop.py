"""Prompt en schema van search_catalog beschrijven dezelfde envelope als de code (#358, stap 2)."""

import re
from pathlib import Path

from tools import catalog
from tools.schemas import TOOL_SCHEMAS, TOOL_SEARCH_CATALOG

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "system.md").read_text(encoding="utf-8")
_STATUSSEN = (
    catalog.STATUS_CANDIDATES,
    catalog.STATUS_NO_MATCH,
    catalog.STATUS_NEEDS_CLARIFICATION,
    catalog.STATUS_OUT_OF_SCOPE,
    catalog.STATUS_METADATA_UNKNOWN,
    catalog.STATUS_SOURCE_UNAVAILABLE,
    catalog.STATUS_TOOL_ERROR,
)


def _schema_beschrijving() -> str:
    tool = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == TOOL_SEARCH_CATALOG)
    return tool["function"]["description"]


def test_de_prompt_noemt_elke_status_van_de_envelope():
    for status in _STATUSSEN:
        assert f"`{status}`" in _PROMPT, status


def test_het_schema_noemt_elke_status_van_de_envelope():
    beschrijving = _schema_beschrijving()
    for status in _STATUSSEN:
        assert status in beschrijving, status


def test_de_prompt_leert_het_dataset_id_van_de_kandidaat_en_niet_de_oude_idvelden():
    assert "`dataset_id`" in _PROMPT and "`geraakt`" in _PROMPT
    assert not re.search(r"`_(cbs|ckan)_id`", _PROMPT)


def test_de_envelope_van_een_miss_heeft_de_velden_uit_de_prompt():
    import json

    envelop = json.loads(catalog.search_catalog("zzzxxqqq"))

    assert envelop["status"] == catalog.STATUS_NO_MATCH
    assert {"catalogus", "melding", "vervolgstap", "kandidaten"} <= set(envelop)
