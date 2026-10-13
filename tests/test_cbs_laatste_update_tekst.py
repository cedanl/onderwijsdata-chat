"""De CBS-datum in een antwoord is de dag van de laatste bijwerking, niet het einde van de cijfers (#496, F-03).

Het model schreef "Deze dataset is actueel tot 9 april 2026": die zin stond in de systeemprompt. De datum
is `laatste_update` uit `get_cbs_data`, de `_laatste_update` van de catalogus (TableInfos.Modified van CBS
bij de build van de package). Welke jaren de cijfers beslaan, staat in de perioden van de data.
"""

import json
import re
from unittest.mock import patch

import pytest

from prompts import SYSTEM_PROMPT
from tools.catalog import catalogus_laatste_update
from tools.cbs import get_cbs_data

_DEFS = {
    "Perioden": {"type": "TimeDimension"},
    "Studenten_1": {"type": "Topic"},
}
_ROWS = [{"Perioden": "2024SJ00", "Studenten_1": 500000}]
# Een live TableInfos.Modified die afwijkt van de catalogus: de chatdatum komt er niet uit.
_LIVE_MODIFIED = "2026-10-01T00:00:00"


def _get(dataset_id, endpoint, **params):
    if endpoint == "TableInfos":
        return [{"Description": "", "Modified": _LIVE_MODIFIED}]
    return []


def _load(dataset_id: str) -> dict:
    """get_cbs_data zonder netwerk: data, metadata en TableInfos staan vast, de catalogus is de echte."""
    with (
        patch("tools.cbs.data", return_value=_ROWS),
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=_get),
    ):
        return json.loads(get_cbs_data(dataset_id))


def _cbs_datumregel() -> str:
    return next(regel for regel in SYSTEM_PROMPT.splitlines() if '"laatste_update"' in regel)


@pytest.mark.parametrize("dataset_id", ["85352NED", "85353NED", "85354NED"])
def test_laatste_update_is_de_catalogusdatum(dataset_id):
    verwacht = catalogus_laatste_update(dataset_id)
    assert verwacht and re.fullmatch(r"\d{4}-\d{2}-\d{2}", verwacht)
    assert _load(dataset_id)["laatste_update"] == verwacht


def test_zonder_catalogusdatum_geen_laatste_update():
    with patch("tools.cbs.catalogus_laatste_update", return_value=None):
        assert "laatste_update" not in _load("85353NED")


def test_prompt_noemt_de_datum_als_laatste_bijwerking():
    assert "actueel tot" not in SYSTEM_PROMPT.lower()
    regel = _cbs_datumregel()
    assert "CBS heeft deze tabel voor het laatst bijgewerkt op [datum]" in regel
    assert "9 april 2026" in regel  # de datum in het Nederlands, niet als ISO-string
    assert "periode" in regel.lower()  # wat de cijfers beslaan, staat in de perioden


def test_prompt_heeft_geen_open_plaatshouder():
    assert re.search(r"\{[A-Z_]+\}", SYSTEM_PROMPT) is None
