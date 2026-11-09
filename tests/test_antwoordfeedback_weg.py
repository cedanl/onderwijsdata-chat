"""De duimpjes zijn weg (#983, besluit 09-11): geen eindpunt meer voor feedback per antwoord.

Rijen die al in `answer_feedback` staan, blijven tot de opschoning of tot de gebruiker al zijn gegevens verwijdert;
export en verwijderen nemen ze mee (tests/test_mijn_gegevens_export.py, tests/test_mijn_gegevens_verwijderen.py).
"""

import pytest
from fastapi.testclient import TestClient

import server


@pytest.mark.parametrize("methode", ["GET", "POST"])
def test_er_is_geen_eindpunt_voor_feedback_per_antwoord(methode):
    client = TestClient(server.app)
    # Vroeger: GET gaf de oordelen (200), POST zonder geldige body een 422.
    assert client.request(methode, "/api/answer-feedback", params={"conversation_id": "c1"}, json={}).status_code == 404
    # De vragenlijst op rapporten en de link Feedback blijven: daar bestaat de route, dus geen 404.
    assert client.post("/api/feedback", json={}).status_code != 404
    assert client.post("/api/feedback/algemeen", json={}).status_code != 404
