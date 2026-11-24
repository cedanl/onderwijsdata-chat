"""Welke bronnen nu niet live zijn (#1057): de probe, de herpoging, de lijst en het eindpunt."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

import server
from core import bronstatus


@pytest.fixture(autouse=True)
def schone_stand(monkeypatch):
    """Elke test begint zonder stand en zonder wachttijd tussen twee pogingen."""
    monkeypatch.setattr(bronstatus, "_stand", {})
    monkeypatch.setattr(bronstatus, "HERPOGING_PAUZE_S", 0)


def _client(antwoorden):
    """Een httpx-client die per host het antwoord geeft dat `antwoorden` noemt: een statuscode of een uitzondering."""
    teller = {}

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        teller[host] = teller.get(host, 0) + 1
        antwoord = antwoorden.get(host, 200)
        if isinstance(antwoord, list):  # per poging een ander antwoord
            antwoord = antwoord[min(teller[host], len(antwoord)) - 1]
        if isinstance(antwoord, Exception):
            raise antwoord
        return httpx.Response(antwoord)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), teller


def _controleer(antwoorden):
    client, teller = _client(antwoorden)

    async def loop():
        async with client:
            await bronstatus.controleer(client)

    asyncio.run(loop())
    return teller


DUO = "onderwijsdata.duo.nl"


def test_zonder_controle_is_er_niets_te_melden():
    assert bronstatus.niet_live() == []


def test_alle_bronnen_live_geeft_een_lege_lijst():
    _controleer({})
    assert bronstatus.niet_live() == []


def test_een_bron_die_een_serverfout_geeft_staat_in_de_lijst():
    _controleer({DUO: 503})
    lijst = bronstatus.niet_live()
    assert [b["bron"] for b in lijst] == ["duo"]
    assert lijst[0]["naam"] == "DUO"
    assert "DUO" in lijst[0]["tekst"]


def test_een_verwijderde_api_telt_niet_als_live():
    """RIO v2 gaf op 19-10 HTTP 410 op elke aanroep: bereikbaar, maar niet live."""
    _controleer({"lod.onderwijsregistratie.nl": 410})
    assert [b["bron"] for b in bronstatus.niet_live()] == ["rio"]


def test_een_time_out_of_verbindingsfout_telt_niet_als_live():
    _controleer({DUO: httpx.ConnectTimeout("te traag"), "opendata.cbs.nl": httpx.ConnectError("geen route")})
    assert sorted(b["bron"] for b in bronstatus.niet_live()) == ["cbs", "duo"]


def test_een_enkele_mislukking_telt_niet_dankzij_de_herpoging():
    teller = _controleer({DUO: [503, 200]})
    assert bronstatus.niet_live() == []
    assert teller[DUO] == 2


def test_pas_na_twee_mislukte_pogingen_achter_elkaar_niet_live():
    teller = _controleer({DUO: 503})
    assert teller[DUO] == 2
    assert [b["bron"] for b in bronstatus.niet_live()] == ["duo"]


def test_een_live_bron_wordt_één_keer_gevraagd():
    teller = _controleer({})
    assert set(teller.values()) == {1}


def test_een_bron_die_terug_is_verdwijnt_uit_de_lijst():
    _controleer({DUO: 503})
    assert bronstatus.niet_live()
    _controleer({})
    assert bronstatus.niet_live() == []


def test_laatst_live_blijft_staan_zolang_de_bron_uitvalt():
    _controleer({})
    _controleer({DUO: 503})
    eerste = bronstatus.niet_live()[0]["laatst_live"]
    _controleer({DUO: 503})
    assert eerste is not None
    assert bronstatus.niet_live()[0]["laatst_live"] == eerste


def test_een_bron_die_nooit_live_was_heeft_geen_laatst_live():
    _controleer({DUO: 503})
    assert bronstatus.niet_live()[0]["laatst_live"] is None


def test_het_antwoord_heeft_alleen_de_bekende_velden():
    """Geen URL, geen foutklasse, geen interne key (#1053)."""
    _controleer({DUO: httpx.ConnectError("[Errno 111] Connection refused naar https://intern.example/x")})
    (melding,) = bronstatus.niet_live()
    assert set(melding) == {"bron", "naam", "tekst", "laatst_live"}
    tekst = " ".join(str(v) for v in melding.values())
    assert "ConnectError" not in tekst
    assert "http" not in tekst
    assert "Errno" not in tekst


def test_een_probe_wacht_niet_langer_dan_de_time_out():
    assert 0 < bronstatus.TIMEOUT_S <= 10


def test_de_probes_gebruiken_de_basis_url_van_de_bronpakketten():
    from onderwijsbronnen.cbs.client import BASE_API
    from onderwijsbronnen.duo import CKAN_BASE

    urls = {b.naam: b.url for b in bronstatus.BRONNEN}
    assert urls["cbs"].startswith(BASE_API)
    assert urls["duo"].startswith(CKAN_BASE)


def test_de_bewaking_staat_uit_met_interval_nul():
    async def loop():
        async with bronstatus.bewaking(0) as taak:
            return taak

    assert asyncio.run(loop()) is None


def test_de_bewaking_draait_een_ronde_en_stopt_bij_het_afsluiten(monkeypatch):
    rondes = []

    async def controleer(client):
        rondes.append(client)

    monkeypatch.setattr(bronstatus, "controleer", controleer)

    async def loop():
        async with bronstatus.bewaking(3600) as taak:
            assert taak is not None
            await asyncio.sleep(0.05)
            assert not taak.done()
        return taak

    taak = asyncio.run(loop())
    assert len(rondes) == 1
    assert taak is not None
    assert taak.done()


def test_een_fout_in_een_ronde_stopt_de_bewaking_niet(monkeypatch):
    """Wacht op de tweede ronde, niet op de klok (#1195); de time-out is alleen een vangnet tegen hangen."""
    rondes = []

    async def loop():
        tweede = asyncio.Event()

        async def controleer(client):
            rondes.append(1)
            if len(rondes) >= 2:
                tweede.set()
            if len(rondes) == 1:
                raise RuntimeError("onverwacht")

        monkeypatch.setattr(bronstatus, "controleer", controleer)
        async with bronstatus.bewaking(0.01):
            await asyncio.wait_for(tweede.wait(), timeout=5)

    asyncio.run(loop())
    assert len(rondes) >= 2


def test_het_eindpunt_geeft_een_lege_lijst_als_alles_live_is():
    resp = TestClient(server.app).get("/api/bronstatus")
    assert resp.status_code == 200
    assert resp.json() == {"niet_live": []}


def test_het_eindpunt_noemt_een_bron_die_niet_live_is():
    _controleer({DUO: 503})
    resp = TestClient(server.app).get("/api/bronstatus")
    (melding,) = resp.json()["niet_live"]
    assert melding["bron"] == "duo"
    assert resp.headers["Cache-Control"] == "no-store"


def test_het_eindpunt_vraagt_geen_inlog():
    """De lijst bevat alleen of een openbare bron antwoordt; ook het loginscherm mag hem lezen."""
    resp = TestClient(server.app).get("/api/bronstatus")
    assert resp.status_code != 401
