"""Responses gaan gecomprimeerd over de lijn; de JS-bundel was 5,5 MB ongecomprimeerd (#110)."""

from fastapi.testclient import TestClient


def test_grote_response_is_gzip():
    import server

    resp = TestClient(server.app).get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"


def test_kleine_response_blijft_ongecomprimeerd():
    import server

    resp = TestClient(server.app).get("/health", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in resp.headers
