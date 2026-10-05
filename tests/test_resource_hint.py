"""Een ontbrekende kolom wijst naar de resource die hem wél heeft (#173, Live-audit 5).

get_duo_data("p01hoinges") laadt resource 0 (geslacht, geen OPLEIDINGSVORM). Zonder hint
concludeerde het model dat de data niet bestaat; resource 3 had de kolom.
"""

import json
from unittest.mock import patch

import pandas as pd

from tools import store
from tools.catalog import dataset_details
from tools.query import query_data
from tools.store import KeyMeta

_ENTRY = {
    "leverancier": "DUO",
    "_ckan_id": "p01hoinges",
    "bron": "Ingeschrevenen hoger onderwijs",
    "_resources": [
        {"naam": "Ingeschrevenen hbo inclusief geslacht"},
        {"naam": "Ingeschrevenen wo inclusief geslacht"},
        {"naam": "Ingeschrevenen hbo niveau opleiding"},
        {"naam": "Ingeschrevenen hbo inclusief opleidingsvorm"},
    ],
}


def _query(resource: int, **filters) -> str:
    store.put(
        "duo:p01hoinges:0",
        pd.DataFrame({"GESLACHT": ["M"], "AANTAL": [1]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=resource),
    )
    with patch("tools.catalog._rio_duo", return_value=[_ENTRY]):
        return query_data("duo:p01hoinges:0", filters=filters)


def test_missing_column_points_to_the_resource_that_names_it():
    melding = _query(0, OPLEIDINGSVORM="VT")

    assert "Kolom 'OPLEIDINGSVORM' bestaat niet" in melding
    assert "resource 3" in melding
    assert "get_duo_data('p01hoinges', 3)" in melding


def test_no_matching_sibling_leaves_the_message_as_it_was():
    melding = _query(0, SECTOR="Techniek")

    assert melding == "Kolom 'SECTOR' bestaat niet. Beschikbare kolommen: ['GESLACHT', 'AANTAL']"


def test_the_resource_itself_is_never_suggested():
    assert "resource 3" not in _query(3, OPLEIDINGSVORM="VT")


def test_non_duo_keys_get_no_hint():
    store.put("cbs:85423NED", pd.DataFrame({"X": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    assert "resource" not in query_data("cbs:85423NED", filters={"OPLEIDINGSVORM": "VT"})


def test_dataset_details_gives_each_resource_its_index():
    with (
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[_ENTRY]),
    ):
        resources = json.loads(dataset_details("p01hoinges"))["_resources"]

    assert [r["index"] for r in resources] == [0, 1, 2, 3]
    assert resources[3]["naam"] == "Ingeschrevenen hbo inclusief opleidingsvorm"
