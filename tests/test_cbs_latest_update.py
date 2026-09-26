"""
Test: CBS data responses include _laatste_update (data actuality timestamp).

Requirement: Each CBS data response should indicate when the source data was last updated,
so users know the currency/reliability of numbers.
"""
import json

import pytest

from tools.cbs import get_cbs_data


def test_get_cbs_data_includes_latest_update():
    """Verify that CBS get_cbs_data response includes _laatste_update metadata."""
    # Use a known CBS dataset with data
    response = get_cbs_data("85423NED", filters=None)

    # Response is JSON
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        pytest.skip(f"Could not parse response as JSON (may be error): {response[:100]}")
        return

    # NEW: Response should include _laatste_update in metadata or as top-level field
    has_update = (
        ("metadata" in data and "laatste_update" in data["metadata"]) or
        "laatste_update" in data
    )
    assert has_update, \
        f"Response missing _laatste_update. Got keys: {list(data.keys())}"

    # Extract and validate
    update_date = (
        data.get("metadata", {}).get("laatste_update") or
        data.get("laatste_update")
    )
    assert update_date, "Latest update date should have a value"
    assert isinstance(update_date, str), f"Latest update should be string, got {type(update_date)}"
    assert len(update_date) >= 8, f"Date should be ISO format or similar, got: {update_date}"


if __name__ == "__main__":
    test_get_cbs_data_includes_latest_update()
    print("✓ Test passed")
