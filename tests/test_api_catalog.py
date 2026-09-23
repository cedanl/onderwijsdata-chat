from fastapi.testclient import TestClient

import server


def test_catalog_counts_endpoint_is_public():
    resp = TestClient(server.app).get("/api/catalog/counts")
    assert resp.status_code == 200
    counts = resp.json()
    assert set(counts) == {"CBS", "DUO", "RIO"}
    assert all(isinstance(n, int) and n > 0 for n in counts.values())
