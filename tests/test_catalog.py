import json
from unittest.mock import patch

from tools.catalog import search_catalog


# --- Fix #37: archief-filter ---


def test_archief_entries_excluded_when_active_entries_exist():
    cbs_entries = [
        {"identifier": "actief", "title": "actief dataset", "_archief": False},
        {"identifier": "archief", "title": "archief dataset", "_archief": True},
    ]
    with patch("tools.catalog._cbs", return_value=cbs_entries), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = search_catalog("dataset", source="cbs")
    data = json.loads(result)
    identifiers = [e.get("identifier") for e in data]
    assert "actief" in identifiers
    assert "archief" not in identifiers


def test_archief_entries_returned_as_fallback_when_no_active_results():
    cbs_entries = [
        {"identifier": "archief", "title": "historisch dataset", "_archief": True},
    ]
    with patch("tools.catalog._cbs", return_value=cbs_entries), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = search_catalog("historisch", source="cbs")
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["identifier"] == "archief"


def test_active_entries_rank_before_archive_via_separate_sort():
    # active and archive are sorted independently, active comes first
    cbs_entries = [
        {"identifier": "archief-hi", "title": "onderwijs mbo data extra", "_archief": True},
        {"identifier": "actief-lo", "title": "onderwijs", "_archief": False},
        {"identifier": "actief-hi", "title": "onderwijs mbo data", "_archief": False},
    ]
    with patch("tools.catalog._cbs", return_value=cbs_entries), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = search_catalog("onderwijs mbo data", source="cbs")
    data = json.loads(result)
    identifiers = [e.get("identifier") for e in data]
    # archive entries excluded; active entries appear sorted by score
    assert "archief-hi" not in identifiers
    assert identifiers[0] == "actief-hi"


def test_no_archief_field_treated_as_active():
    cbs_entries = [
        {"identifier": "geen-veld", "title": "dataset zonder archief veld"},
    ]
    with patch("tools.catalog._cbs", return_value=cbs_entries), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = search_catalog("dataset", source="cbs")
    data = json.loads(result)
    assert data[0]["identifier"] == "geen-veld"


# --- Fix #38: leverancier-filter ---


def test_unsupported_leveranciers_excluded():
    rio_entries = [
        {"identifier": "rio-entry", "title": "rio data", "leverancier": "RIO"},
        {"identifier": "duo-entry", "title": "duo data", "leverancier": "DUO"},
        {"identifier": "roa-entry", "title": "roa data", "leverancier": "ROA"},
        {"identifier": "sbb-entry", "title": "sbb data", "leverancier": "SBB"},
        {"identifier": "uwv-entry", "title": "uwv data", "leverancier": "UWV"},
        {"identifier": "inspectie-entry", "title": "inspectie data", "leverancier": "Inspectie"},
    ]
    with patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=rio_entries):
        result = search_catalog("data", source="rio")
    data = json.loads(result)
    identifiers = {e.get("identifier") for e in data}
    assert "rio-entry" in identifiers
    assert "duo-entry" in identifiers
    assert "roa-entry" not in identifiers
    assert "sbb-entry" not in identifiers
    assert "uwv-entry" not in identifiers
    assert "inspectie-entry" not in identifiers


def test_leverancier_filter_case_insensitive():
    rio_entries = [
        {"identifier": "rio-lower", "title": "rio data", "leverancier": "rio"},
        {"identifier": "duo-mixed", "title": "duo data", "leverancier": "Duo"},
        {"identifier": "roa-entry", "title": "roa data", "leverancier": "roa"},
    ]
    with patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=rio_entries):
        result = search_catalog("data", source="rio")
    data = json.loads(result)
    identifiers = {e.get("identifier") for e in data}
    assert "rio-lower" in identifiers
    assert "duo-mixed" in identifiers
    assert "roa-entry" not in identifiers
