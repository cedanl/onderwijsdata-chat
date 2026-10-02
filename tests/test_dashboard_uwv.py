"""Vacatureclusters voor de arbeidsmarktmatch: geen stille terugval op alle clusters (#229)."""

from unittest.mock import patch

import data.dashboard as dashboard

_CLUSTERS = {"Zorg en welzijn": 900, "ICT": 300, "Techniek": 200}


def _met_clusters(sectoren):
    with patch.object(dashboard, "_uwv_raw_clusters", return_value=(1400, "mei 2023", _CLUSTERS)), \
         patch.object(dashboard, "_SECTOR_CLUSTER_MAP", {"GEZONDHEIDSZORG": ["Zorg en welzijn"], "ONBEKEND": ["Bestaat niet"]}):
        return dashboard._uwv_clusters_voor_sectoren("Utrecht", sectoren)


def test_sector_met_clustermatch_geeft_alleen_die_clusters():
    assert _met_clusters(("GEZONDHEIDSZORG",)) == {"Zorg en welzijn": 900}


def test_sector_zonder_clustermatch_geeft_geen_clusters():
    # Met alle clusters als terugval kreeg elke sector vacature-aandeel 0: "overaanbod".
    assert _met_clusters(("ONBEKEND",)) == {}
