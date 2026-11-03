"""
Tests voor CBS-07: _meetwaarden bevat officiële DataProperties-sleutels,
titel/eenheid/datatype staan apart in _meetwaarden_details.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "catalogus"))

import pytest
from helpers import meetwaarden_uit_properties
from onderwijsdata import catalog

PROPS_85423 = [
    {"Key": "Geslacht", "Title": "Geslacht", "Type": "Dimension"},
    {"Key": "Perioden", "Title": "Perioden", "Type": "TimeDimension"},
    {"Key": "", "Title": "Groep zonder sleutel", "Type": "TopicGroup"},
    {"Key": "TotaalIngeschrevenen_1", "Title": "Totaal ingeschrevenen", "Type": "Topic",
     "Unit": "aantal", "Description": "Ingeschrevenen in het hoger onderwijs.",
     "Datatype": "Long", "Decimals": 0},
]


class TestMeetwaardenUitProperties:
    def test_keys_zijn_officiele_sleutels_geen_titels(self):
        keys, _ = meetwaarden_uit_properties(PROPS_85423)
        assert keys == ["TotaalIngeschrevenen_1"]

    def test_details_bevatten_titel_eenheid_datatype_decimalen(self):
        _, details = meetwaarden_uit_properties(PROPS_85423)
        assert details["TotaalIngeschrevenen_1"] == {
            "title": "Totaal ingeschrevenen",
            "unit": "aantal",
            "description": "Ingeschrevenen in het hoger onderwijs.",
            "datatype": "Long",
            "decimals": 0,
        }

    def test_dimensies_en_topicgroups_zijn_geen_meetwaarden(self):
        keys, details = meetwaarden_uit_properties(PROPS_85423)
        assert "Geslacht" not in keys and "" not in keys
        assert set(details) == set(keys)

    def test_topic_zonder_key_wordt_overgeslagen(self):
        keys, details = meetwaarden_uit_properties(
            [{"Key": None, "Title": "Alleen titel", "Type": "Topic"}]
        )
        assert keys == [] and details == {}

    def test_ontbrekende_eenheid_blijft_lege_string(self):
        _, details = meetwaarden_uit_properties(
            [{"Key": "X_1", "Title": "X", "Type": "Topic"}]
        )
        assert details["X_1"]["unit"] == ""
        assert details["X_1"]["decimals"] is None


@pytest.fixture(scope="module", params=["enriched", "ai", "basis"])
def records(request):
    if request.param == "enriched":
        return catalog(ai=True)
    return catalog(ai=request.param == "ai")


class TestGeleverdeCatalogus:
    def test_alle_meetwaardesleutels_hebben_details(self, records):
        ontbrekend = [
            (r["_cbs_id"], k)
            for r in records
            for k in r.get("_meetwaarden", [])
            if k not in r.get("_meetwaarden_details", {})
        ]
        assert ontbrekend == []

    def test_details_hebben_geen_extra_sleutels(self, records):
        extra = [
            (r["_cbs_id"], k)
            for r in records
            for k in r.get("_meetwaarden_details", {})
            if k not in r.get("_meetwaarden", [])
        ]
        assert extra == []

    @pytest.mark.parametrize("cbs_id, key, titel", [
        ("85423NED", "TotaalIngeschrevenen_1", "Totaal ingeschrevenen"),
        ("85422NED", "Eerstejaarsstudenten_1", "Eerstejaarsstudenten"),
    ])
    def test_voorbeeldtabellen_leveren_officiele_keys(self, records, cbs_id, key, titel):
        rec = next(r for r in records if r["_cbs_id"] == cbs_id)
        assert key in rec["_meetwaarden"]
        assert titel not in rec["_meetwaarden"]
        assert rec["_meetwaarden_details"][key]["title"] == titel
        assert rec["_meetwaarden_details"][key]["unit"] == "aantal"


def test_enriched_kolommen_zijn_op_key_gevonden():
    """Definitielookup lukt nu: meetwaarde-kolommen dragen titel + eenheid."""
    rec = next(r for r in catalog(ai=True) if r["_cbs_id"] == "85423NED")
    assert rec["_kolommen"]["TotaalIngeschrevenen_1"] == "Totaal ingeschrevenen (aantal)"
    assert rec["_kolomtypes"]["TotaalIngeschrevenen_1"] == "meetwaarde (aantal)"
