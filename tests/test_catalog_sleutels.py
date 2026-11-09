"""Relatielaag stap 2 (#958): het model ziet in search_catalog en dataset_details via welke sleutel een dataset koppelt,
zodat het een koppeling plant vóór het laadt. De sleutels komen uit het pakket (`onderwijsbronnen.sleutels`, per record
`_sleutels`); hier gaat het om de chat: elke dataset die de chat kan opvragen heeft ze, en het model krijgt ze te zien."""

import json

from tests.zoekuitkomst import treffers
from tools import catalog
from tools.catalog import dataset_details, search_catalog


def _hit(query: str, dataset_id: str) -> dict:
    return next(h for h in treffers(search_catalog(query, top_n=15)) if h.get("dataset_id") == dataset_id)


def test_elke_opvraagbare_dataset_en_elke_eigen_tool_heeft_sleutels_of_een_reden():
    getoetst = 0
    for entry in [*catalog._cbs(), *catalog._rio_duo()]:
        if catalog.status(entry) not in (catalog.STATUS_OPVRAAGBAAR, catalog.STATUS_VIA_TOOL):
            continue
        assert entry["_sleutels"] or entry.get("_sleutels_reden"), catalog._dataset_id(entry)
        getoetst += 1
    assert getoetst > 150  # 130 CBS, 15 DUO, 8 RIO, plus de eigen tools


def test_een_zoekhit_noemt_de_sleutels_kort():
    hit = _hit("eerstejaars hbo instelling", "p02ho1ejrs")
    assert hit["koppelbaar_via"] == "brin, croho, gemeente, provincie, schooljaar"  # namen niet: alleen codes


def test_namen_zijn_geen_sleutel_om_een_koppeling_op_te_plannen():
    """Besluit 09-11 (#958): instellingsnaam en gemeentenaam blijven in het record, maar het model plant niet op een naam."""
    record = next(e for e in catalog._rio_duo() if e.get("_ckan_id") == "p01hoinges")
    assert {"kolom": "GEMEENTENAAM", "sleutel": "gemeentenaam"} in record["_sleutels"]
    via = json.loads(dataset_details("p01hoinges"))["koppelbaar_via"]
    assert "naam" not in via.split(".")[0]
    zonder_codes = {**record, "_sleutels": [{"kolom": "Gemeentenaam", "sleutel": "gemeentenaam"}]}
    assert catalog.koppelbaar_via(zonder_codes).startswith("geen sleutel naar een andere bron")


def test_dataset_details_noemt_per_sleutel_de_kolom_en_hoe_te_koppelen():
    via = json.loads(dataset_details("p01hoinges"))["koppelbaar_via"]
    assert via.startswith("brin (INSTELLINGSCODE_ACTUEEL), croho (OPLEIDINGSCODE_ACTUEEL), gemeente (GEMEENTENUMMER)")
    assert "relatie" in via
    cbs = json.loads(dataset_details("85701NED"))["koppelbaar_via"]
    assert cbs.startswith("gemeente (Regiokenmerken), provincie (Regiokenmerken), schooljaar (Perioden).")


def test_zonder_sleutel_zegt_dataset_details_waarom():
    zonder = next(e for e in catalog._rio_duo() if e.get("_rio_resource") == "examenlicenties")
    via = json.loads(dataset_details("examenlicenties"))["koppelbaar_via"]
    assert via == f"geen sleutel naar een andere bron: {zonder['_sleutels_reden']}"


def test_een_eigen_tool_noemt_zijn_sleutel_ook():
    """De financiële verantwoording gaat per bestuur: dat zegt het detailrecord naast de verwijzing naar de tool."""
    details = json.loads(dataset_details("financien"))
    assert details["status"] == catalog.STATUS_VIA_TOOL
    assert details["koppelbaar_via"].startswith("bestuur (Bevoegd Gezag).")
