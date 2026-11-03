"""Wat de prompt over toollimieten zegt, is wat de code afdwingt (#52)."""

import re

from agent.run import _TOOL_LIMITS
from core.config import SEARCH_CATALOG_LIMIT
from prompts import SYSTEM_PROMPT


def test_prompt_noemt_de_zoeklimiet_die_de_code_afdwingt():
    assert _TOOL_LIMITS["search_catalog"] == SEARCH_CATALOG_LIMIT
    assert f"maximaal **{SEARCH_CATALOG_LIMIT} keer**" in SYSTEM_PROMPT
    assert f"na {SEARCH_CATALOG_LIMIT} zoekacties" in SYSTEM_PROMPT


def test_geen_open_plaatshouder_in_de_prompt():
    assert "{ZOEKLIMIET}" not in SYSTEM_PROMPT


def test_de_prompt_noemt_geen_ander_aantal_zoekpogingen():
    """#846: de prompt gaf vier stopcriteria; een getal bij zoekacties of pogingen is de grens uit de code."""
    aantallen = re.findall(r"(\d+)\s+(?:zoekacties|zoekpogingen|pogingen)", SYSTEM_PROMPT)
    assert aantallen and set(aantallen) == {str(SEARCH_CATALOG_LIMIT)}, aantallen
