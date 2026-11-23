"""Een opslagquotum per gebruiker voor gesprekken en werkboeken (S24, #682).

`PUT /api/conversations/{id}` en `PUT /api/workbooks/{id}` hadden een grens per verzoek (4 MiB, core/verzoeklimiet.py),
maar niet per gebruiker: één account kon de database blijven vullen. Nu telt de server per gebruiker het aantal
gesprekken, het aantal werkboeken en hun totale grootte; erboven komt een 507 met een melding, en wat er al staat blijft.
Een bestaand gesprek bijwerken telt alleen het verschil in grootte.
"""

import pytest

from core import opslagquotum


@pytest.fixture
def anna(app_client, monkeypatch):
    c = app_client(users="anna:wachtwoord,bob:wachtwoord")
    from core import auth

    c.headers["Authorization"] = f"Bearer {auth.make_token('anna')}"
    monkeypatch.setattr(opslagquotum, "MAX_GESPREKKEN", 3)
    monkeypatch.setattr(opslagquotum, "MAX_WERKBOEKEN", 2)
    monkeypatch.setattr(opslagquotum, "MAX_OPSLAG_BYTES", 10_000)
    return c


def _gesprek(tekst="hoi"):
    return {"title": "Gesprek", "timestamp": 1000, "messages": [{"role": "user", "content": tekst}]}


def _werkboek(html="<p>rapport</p>"):
    return {"title": "Rapport", "description": "", "htmlContent": html, "createdAt": "2026-11-19"}


def test_onder_het_quotum_gaat_alles_door(anna):
    for i in range(3):
        assert anna.put(f"/api/conversations/c{i}", json=_gesprek()).status_code == 200
    for i in range(2):
        assert anna.put(f"/api/workbooks/w{i}", json=_werkboek()).status_code == 200


def test_een_gesprek_te_veel_geeft_507_met_een_melding(anna):
    for i in range(3):
        anna.put(f"/api/conversations/c{i}", json=_gesprek())
    antwoord = anna.put("/api/conversations/c3", json=_gesprek())
    assert antwoord.status_code == 507
    assert "gesprekken" in antwoord.json()["detail"] and "verwijder" in antwoord.json()["detail"].lower()
    assert [c["id"] for c in anna.get("/api/conversations").json()].count("c3") == 0


def test_een_bestaand_gesprek_bijwerken_mag_ook_bij_het_maximum(anna):
    for i in range(3):
        anna.put(f"/api/conversations/c{i}", json=_gesprek())
    bijgewerkt = _gesprek()
    bijgewerkt["messages"].append({"role": "assistant", "content": "antwoord"})
    assert anna.put("/api/conversations/c0", json=bijgewerkt).status_code == 200


def test_een_werkboek_te_veel_geeft_507(anna):
    for i in range(2):
        anna.put(f"/api/workbooks/w{i}", json=_werkboek())
    antwoord = anna.put("/api/workbooks/w2", json=_werkboek())
    assert antwoord.status_code == 507
    assert "rapporten" in antwoord.json()["detail"]


def test_de_totale_grootte_telt_gesprekken_en_werkboeken_samen(anna):
    assert anna.put("/api/workbooks/w0", json=_werkboek("x" * 6_000)).status_code == 200
    antwoord = anna.put("/api/conversations/c0", json=_gesprek("y" * 6_000))
    assert antwoord.status_code == 507
    assert "ruimte" in antwoord.json()["detail"]


def test_bijwerken_telt_alleen_het_verschil(anna):
    assert anna.put("/api/conversations/c0", json=_gesprek("y" * 6_000)).status_code == 200
    # Hetzelfde gesprek iets groter: 6.000 oud eraf, 7.000 nieuw erbij, binnen 10.000.
    groter = _gesprek("y" * 6_000)
    groter["messages"].append({"role": "assistant", "content": "z" * 1_000})
    assert anna.put("/api/conversations/c0", json=groter).status_code == 200


def test_ruimte_maken_helpt(anna):
    for i in range(3):
        anna.put(f"/api/conversations/c{i}", json=_gesprek())
    assert anna.put("/api/conversations/c3", json=_gesprek()).status_code == 507
    anna.delete("/api/conversations/c0")
    assert anna.put("/api/conversations/c3", json=_gesprek()).status_code == 200


def test_het_quotum_is_per_gebruiker(anna):
    from core import auth

    for i in range(3):
        anna.put(f"/api/conversations/c{i}", json=_gesprek())
    anna.headers["Authorization"] = f"Bearer {auth.make_token('bob')}"
    assert anna.put("/api/conversations/c0", json=_gesprek()).status_code == 200


def test_een_grens_van_nul_staat_uit(anna, monkeypatch):
    monkeypatch.setattr(opslagquotum, "MAX_GESPREKKEN", 0)
    for i in range(5):
        assert anna.put(f"/api/conversations/c{i}", json=_gesprek()).status_code == 200
