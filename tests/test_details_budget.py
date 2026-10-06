"""dataset_details houdt de kolom die de vraag noemt binnen het modelbudget (#395, testaudit L3).

'Wat betekent OPLEIDINGSVORM in mbo_opleidingsaanbod?' Details waren 16.138 tekens en
OPLEIDINGSVORM stond op positie 13.135. Het agentbudget kapte af op 12.000, dus het model
zag de cohortresource nooit en concludeerde dat de hele dataset de kolom mist.
"""

import json
import logging
from unittest.mock import patch

import pandas as pd

from agent.loop import _truncate
from agent.run import _MAX_TOOL_RESULT_CHARS
from tools import store
from tools.catalog import _DETAILS_BUDGET, dataset_details
from tools.query import query_data
from tools.store import KeyMeta

_VEEL = [f"code-{i:04d}-{'x' * 30}" for i in range(400)]

# Als de catalogus: _kolommen en _kolomtypes per resourcenaam, lange voorbeeldlijsten vooraan.
_ENTRY = {
    "leverancier": "DUO",
    "_ckan_id": "mbo_opleidingsaanbod",
    "bron": "Opleidingsaanbod mbo",
    "_resources": [
        {"naam": "mbo_opleidingsaanbod", "id": "uuid-basis"},
        {"naam": "mbo_opleidingsaanbod_cohorten", "id": "ac441b5c-f2a3-45f2-b8d1-a06a71a2a009"},
    ],
    "_kolommen": {
        "mbo_opleidingsaanbod": {"OPLEIDINGSEENHEIDCODE": _VEEL, "LEERTRAJECT": ["BOL", "BBL"]},
        "mbo_opleidingsaanbod_cohorten": {"AANGEBODEN_OPLEIDINGCODE": _VEEL, "OPLEIDINGSVORM": ["VT", "DT", "DU"]},
    },
    "_kolomtypes": {
        "mbo_opleidingsaanbod": {"OPLEIDINGSEENHEIDCODE": "categorie", "LEERTRAJECT": "categorie (2 waarden)"},
        "mbo_opleidingsaanbod_cohorten": {
            "AANGEBODEN_OPLEIDINGCODE": "categorie",
            "OPLEIDINGSVORM": "categorie (3 waarden)",
        },
    },
}


def _details(entry: dict = _ENTRY) -> dict:
    with (
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[entry]),
        patch("tools.duo_meta.metadata", return_value={}),
        patch("tools.duo_meta.kolomdekking", return_value={}),
        patch("tools.duo.geladen_profielen", return_value=None),
    ):
        return json.loads(dataset_details(str(entry["_ckan_id"])))


def test_de_resource_index_noemt_de_kolommen_van_elk_bestand():
    resources = _details()["_resources"]

    assert resources[1]["kolommen"] == ["AANGEBODEN_OPLEIDINGCODE", "OPLEIDINGSVORM"]
    assert resources[0]["kolommen"] == ["OPLEIDINGSEENHEIDCODE", "LEERTRAJECT"]


def test_de_resource_index_staat_voor_de_lange_voorbeeldlijsten():
    with (
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[_ENTRY]),
        patch("tools.duo_meta.metadata", return_value={}),
        patch("tools.duo_meta.kolomdekking", return_value={}),
        patch("tools.duo.geladen_profielen", return_value=None),
    ):
        tekst = dataset_details("mbo_opleidingsaanbod")

    assert tekst.find("OPLEIDINGSVORM") < tekst.find("code-0000")


def test_lange_voorbeeldlijsten_worden_ingekort_met_een_telling():
    waarden = _details()["_kolommen"]["mbo_opleidingsaanbod"]["OPLEIDINGSEENHEIDCODE"]

    assert len(waarden) < len(_VEEL)
    assert waarden[-1] == f"… (+{len(_VEEL) - len(waarden) + 1} meer in de steekproef)"
    assert _details()["_kolommen"]["mbo_opleidingsaanbod"]["LEERTRAJECT"] == ["BOL", "BBL"]


def test_een_dataset_met_een_kolommenlijst_zonder_resourcenamen_blijft_werken():
    entry = {**_ENTRY, "_kolommen": {"OPLEIDINGSVORM": _VEEL}, "_kolomtypes": {"OPLEIDINGSVORM": "categorie"}}
    details = _details(entry)

    assert "kolommen" not in details["_resources"][0]
    assert len(details["_kolommen"]["OPLEIDINGSVORM"]) < len(_VEEL)


def test_echte_mbo_opleidingsaanbod_past_binnen_het_agentbudget():
    tekst = dataset_details("mbo_opleidingsaanbod")

    assert len(tekst) <= _MAX_TOOL_RESULT_CHARS
    cohorten = next(r for r in json.loads(tekst)["_resources"] if r["naam"] == "mbo_opleidingsaanbod_cohorten")
    assert "OPLEIDINGSVORM" in cohorten["kolommen"]


def test_ontbrekende_kolom_wijst_naar_het_bestand_dat_hem_volgens_de_catalogus_heeft():
    # 'opleidingsvorm' staat niet in de naam van de cohortresource, wel in zijn kolommen.
    store.put(
        "duo:mbo_opleidingsaanbod:0",
        pd.DataFrame({"LEERTRAJECT": ["BOL"]}),
        KeyMeta(bron="duo", dataset="mbo_opleidingsaanbod", resource=0),
    )
    with patch("tools.catalog._rio_duo", return_value=[_ENTRY]):
        melding = query_data("duo:mbo_opleidingsaanbod:0", filters={"OPLEIDINGSVORM": "VT"})

    assert "get_duo_data('mbo_opleidingsaanbod', 1)" in melding


def test_afkapping_staat_in_de_log(caplog):
    with caplog.at_level(logging.WARNING, logger="agent.loop"):
        _truncate("x" * 50, 10, tool="dataset_details")

    assert "TOOL_AFGEKAPT tool=dataset_details tekens=50 limiet=10" in caplog.text


def test_afkapping_vertelt_het_model_dat_er_meer_is():
    tekst = _truncate("x" * 50, 10, tool="dataset_details")

    assert tekst.startswith("x" * 10)
    assert "afgekapt" in tekst
    assert "niet getoond" in tekst


def test_het_detailsbudget_ligt_onder_het_agentbudget():
    assert _DETAILS_BUDGET < _MAX_TOOL_RESULT_CHARS


def test_bij_te_veel_tekst_worden_de_voorbeelden_verder_ingekort():
    breed = {**_ENTRY, "_kolommen": {"mbo_opleidingsaanbod": {f"K{i}": _VEEL for i in range(80)}}}
    waarden = _details(breed)["_kolommen"]["mbo_opleidingsaanbod"]["K0"]

    assert len(waarden) == 3
