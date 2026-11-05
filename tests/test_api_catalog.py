from fastapi.testclient import TestClient

import server
from tools.catalog import catalogus_aantallen


def test_catalog_counts_endpoint_is_public():
    resp = TestClient(server.app).get("/api/catalog/counts")
    assert resp.status_code == 200
    counts = resp.json()
    # De datatoolbronnen altijd; een bron met een eigen tool alleen waar die tool hier antwoord geeft (#956).
    assert {"CBS", "DUO", "RIO"} <= set(counts) and counts == catalogus_aantallen()
    assert all(isinstance(n, int) and n > 0 for n in counts.values())
