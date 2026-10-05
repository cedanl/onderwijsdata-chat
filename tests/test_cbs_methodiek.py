"""CBS-methodiek en teldefinitie in dataset_details, uit het packagecontract (#383).

Ketenaudit A1: dataset_details('85423NED') gaf alleen kolommen. Dat CBS op tientallen
afrondt en dat hbo + wo samen meer is dan het HO-totaal (dubbeltelling), stond wel in
het contract van de gepinde CBS-package, maar het model zag het niet vóór het rekende.
De DUO-routes (teldefinitie, publicatieregels, dataset-gebonden glossary) zijn al
gedekt in test_duo_teldefinitie.py en test_duo_kolomdefinities.py.
"""

import json
from unittest.mock import patch

from tools import cbs_meta
from tools.catalog import dataset_details

_ENTRY = {"_cbs_id": "85423NED", "bron": "Hoger onderwijs; ingeschrevenen", "_kolommen": {"x": {}}}


def _details(entry: dict) -> dict:
    with patch("tools.catalog._cbs", return_value=[entry]), patch("tools.catalog._rio_duo", return_value=[]):
        return json.loads(dataset_details(entry["_cbs_id"]))


def test_details_noemen_afronding_dubbeltelling_en_teldefinitie():
    """Tegen het echte contract van de gelockte package, niet tegen een mock."""
    details = _details(_ENTRY)

    methodiek = details["methodiek"]
    assert any("10-tallen" in p for p in methodiek["afronding"])
    assert any("lager dan de som" in p for p in methodiek["additiviteit"])
    assert "voorlopig" in methodiek["publicatiestatus"]
    assert details["teldefinitie"][0]["term"] == "Ingeschrevenen"


def test_alleen_wat_de_bron_vermeldt():
    contract = {
        "teldefinitie": {"status": "unknown"},
        "methodiek": {
            "status": "supported",
            "afronding": {"status": "niet_vermeld"},
            "additiviteit": {"status": "gevonden", "passages": ["Som wijkt af."], "aanwijzingen": [{"x": 1}]},
            "definitiebreuken": {"status": "niet_vermeld"},
            "publicatie": {"status": "niet_vermeld"},
            "methoden": [{"url": "https://cbs.nl"}],
        },
    }
    with patch("tools.cbs_meta._contract.get_dataset", return_value=contract):
        assert cbs_meta.metadata("X") == {"methodiek": {"additiviteit": ["Som wijkt af."]}}


def test_een_dataset_buiten_het_contract_krijgt_niets():
    assert cbs_meta.metadata("BESTAATNIET") == {}


def test_methodiek_blijft_compact():
    """Tokenbudget: geen URL's, extractiedetails of dubbele aanwijzingen."""
    tekst = json.dumps(cbs_meta.metadata("85423NED"), ensure_ascii=False)
    assert len(tekst) < 2000
    assert "http" not in tekst
    assert "extractie" not in tekst
