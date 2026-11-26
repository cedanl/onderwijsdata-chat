"""Een dashboard zegt wat er misging: "bron niet beschikbaar" is geen "niet gevonden", en een gat staat in de payload.

Eerder gaven de ladingen bij een DUO-storing None, wat samenviel met een onbekende instelling: de gebruiker las
"niet gevonden … pas de naam aan". Onderdelen die niet laadden, verdwenen met alleen een WARNING in het log. Het
eindpunt had geen tijdsgrens en geen gelijktijdigheidslimiet (#901).
"""

import asyncio
import json
import logging
import re
import threading
import time

import pandas as pd
import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from onderwijsbronnen import duo

import data.dashboard as dashboard
import routes.instellingen
from core.gelijktijdig import DRUK, Runplaatsen
from data import arbeidsmarkt, vacatures_cbs

_LADERS = [
    dashboard.load_dashboard_regio,
    dashboard.load_dashboard_nationaal,
    dashboard.load_dashboard_rendement,
    dashboard.load_dashboard_arbeidsmarktmatch,
]

# Een rij per thema: een bestand zonder herkend prognose- of SIS-thema is een fout, geen lege tabel (#1091).
_ROA = pd.DataFrame(
    [
        {
            "regionaam": "Nederland",
            "thema": thema,
            "aggregatieniveau": "opleidingsniveau (ONR2019)",
            "detailniveau": "Bachelor",
            "onderwerp": onderwerp,
            "perc": perc,
            "aantal": None,
            "typering": typering,
            "versie": "2024",
        }
        for thema, onderwerp, perc, typering in (
            ("Schoolverlatersinformatie (SIS 2025)", "werkloosheid", 3.0, None),
            (
                "Risicoindicatoren en arbeidsmarktprognoses tot 2030, actualisering",
                "ITA toekomstige arbeidsmarktsituatie in 2030",
                None,
                "redelijk",
            ),
        )
    ]
)


@pytest.fixture
def storing_bij(duo_fixtures, cbs_vacatures, monkeypatch):
    """DUO uit de fixtures, behalve de datasets in de verzameling: die geven een verbindingsfout. De CBS-vacatures uit
    het opgenomen antwoord (fixture `cbs_vacatures`)."""
    fixture_load = duo.load
    uit: set[str] = set()

    def load(dataset_id, resource=0, **kwargs):
        if dataset_id in uit or "*" in uit:
            raise ConnectionError("DUO onbereikbaar")
        return fixture_load(dataset_id, resource, **kwargs)

    monkeypatch.setattr(duo, "load", load)
    monkeypatch.setattr(arbeidsmarkt, "_roa", lambda: _ROA)
    return uit


# ── Niet gevonden of bron niet beschikbaar ──


@pytest.mark.parametrize("lader", _LADERS, ids=lambda f: f.__name__)
def test_een_duo_storing_is_bron_niet_beschikbaar_en_geen_niet_gevonden(storing_bij, lader):
    storing_bij.add("*")

    with pytest.raises(dashboard.BronNietBeschikbaar, match="niet beschikbaar"):
        lader("Hogeschool Utrecht")


@pytest.mark.parametrize("lader", _LADERS, ids=lambda f: f.__name__)
def test_een_storing_in_de_andere_sector_raakt_een_gevonden_instelling_niet(storing_bij, lader):
    # De ho-bestanden liggen eruit, ROC Mondriaan staat in de mbo-bestanden: gevonden, geen storing.
    storing_bij.update({"p01hoinges", "p02ho1ejrs", "p04hogdipl"})

    assert lader("ROC Mondriaan")["gevonden"] is True


def test_een_storing_in_de_andere_sector_bij_een_onbekende_naam_is_wel_een_storing(storing_bij):
    # Of "Hogeschool Utrecht" in de ho-bestanden staat, is zonder die bestanden niet te zeggen.
    storing_bij.update({"p01hoinges", "p02ho1ejrs", "p04hogdipl"})

    with pytest.raises(dashboard.BronNietBeschikbaar):
        dashboard.load_dashboard_regio("Hogeschool Utrecht")


def test_een_onbekende_naam_is_niet_gevonden_met_de_dichtstbijzijnde_namen(storing_bij):
    uit = dashboard.load_dashboard_regio("hogeschool utrect")

    assert uit["gevonden"] is False
    assert uit["beschikbare_instellingen"][0] == "Hogeschool Utrecht"
    assert len(uit["beschikbare_instellingen"]) <= 5
    assert "niet_beschikbaar" not in uit


def test_een_naam_die_op_geen_andere_lijkt_krijgt_geen_suggesties(storing_bij):
    # #1102: Horizon College is een roc die niet in het DUO-bestand staat. Namen als "Deltion College" lijken er alleen
    # door het woord "college" op en horen er niet bij: een suggestie hoort bij een tikfout.
    uit = dashboard.load_dashboard_regio("Horizon College")

    assert uit["gevonden"] is False
    assert uit["beschikbare_instellingen"] == []
    assert uit["geen_suggesties"]


def test_een_tikfout_in_een_mbo_naam_geeft_de_juiste_suggestie(storing_bij):
    uit = dashboard.load_dashboard_regio("ROC Mondrian")

    assert uit["beschikbare_instellingen"][0] == "ROC Mondriaan"


# ── Een onderdeel dat niet laadde ──


def test_een_onderdeel_dat_niet_laadde_staat_in_de_payload_met_de_reden(storing_bij, monkeypatch):
    monkeypatch.setattr(vacatures_cbs, "stand", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("CBS")))

    uit = dashboard.load_dashboard_regio("Hogeschool Utrecht")

    assert uit["gevonden"] is True
    assert uit["niet_beschikbaar"] == [
        {"onderdeel": "Vacatures (CBS)", "bron": "CBS", "reden": "de bron was niet bereikbaar"}
    ]
    # Geen vacaturegrafiek en geen 0: het dashboard noemt het gat (#901).
    assert uit["vacatureaanbod"] == {}


def test_een_volledige_lading_heeft_geen_gaten(storing_bij):
    uit = dashboard.load_dashboard_regio("Hogeschool Utrecht")

    assert "niet_beschikbaar" not in uit
    assert uit["vacatureaanbod"]["dataset"] == "83599NED"


def test_de_reden_noemt_nooit_de_fouttekst():
    # De fouttekst van httpx citeert de request-URL (#502).
    import httpx

    verzoek = httpx.Request("GET", "https://onderwijsdata.duo.nl/geheim?token=x")
    fouten = [
        httpx.ReadTimeout("https://onderwijsdata.duo.nl/geheim", request=verzoek),
        httpx.HTTPStatusError("https://…/geheim", request=verzoek, response=httpx.Response(503, request=verzoek)),
        httpx.ConnectError("https://…/geheim", request=verzoek),
        KeyError("INSTELLINGSNAAM"),
    ]

    redenen = [dashboard._reden(e) for e in fouten]

    assert redenen == [
        "de bron antwoordde niet op tijd",
        "de bron antwoordde met HTTP 503",
        "de bron was niet bereikbaar",
        "de data van de bron kon niet worden verwerkt",
    ]


def test_een_mislukte_hoofdlading_komt_niet_in_de_cache(storing_bij):
    storing_bij.add("*")
    with pytest.raises(dashboard.BronNietBeschikbaar):
        dashboard.load_dashboard_regio("Hogeschool Utrecht")

    storing_bij.clear()

    assert dashboard.load_dashboard_regio("Hogeschool Utrecht")["gevonden"] is True


# ── Het eindpunt: foutstatus, tijdsgrens en gelijktijdigheid ──


@pytest.fixture
def client(dashboards_aan, monkeypatch):
    import server
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    return TestClient(server.app)


def _nep_lader(monkeypatch, lader):
    monkeypatch.setattr(routes.instellingen, "load_dashboard_regio", lader)


def test_bron_niet_beschikbaar_geeft_503_met_de_melding(client, monkeypatch):
    def storing(instelling):
        raise dashboard.BronNietBeschikbaar

    _nep_lader(monkeypatch, storing)

    resp = client.get("/api/dashboard/regio", params={"instelling": "Hogeschool Utrecht"})

    assert resp.status_code == 503
    assert resp.json() == {"error": dashboard.BRON_NIET_BESCHIKBAAR}


def test_een_lading_over_de_tijdsgrens_geeft_504_en_houdt_haar_plaats_tot_ze_klaar_is(dashboards_aan, monkeypatch):
    door, klaar = threading.Event(), threading.Event()

    def traag(instelling):
        door.wait(timeout=5)
        klaar.set()
        return {"gevonden": True}

    monkeypatch.setattr(routes.instellingen, "DASHBOARD_TIMEOUT_S", 0.05)

    async def scenario():
        monkeypatch.setattr(routes.instellingen, "_dashboardplaatsen", Runplaatsen(max_tegelijk=1, wacht_s=0.01))
        eerste = await routes.instellingen._laad_dashboard(traag, "HU")
        # De thread laadt nog: zijn plaats is niet vrij, dus een tweede lading krijgt "druk" in plaats van een thread.
        tweede = await routes.instellingen._laad_dashboard(traag, "HU")
        door.set()
        await asyncio.gather(*list(routes.instellingen._uitlopend))
        return eerste, tweede

    eerste, tweede = asyncio.run(scenario())

    assert eerste.status_code == 504
    assert "kwam niet binnen" in json.loads(eerste.body)["error"]
    assert tweede.status_code == 503
    assert json.loads(tweede.body) == {"error": DRUK}
    assert klaar.is_set()
    assert not routes.instellingen._uitlopend


# ── #1166: een trage lading staat met eindpunt en duur in het log ──


def _traag_regio(instelling):
    time.sleep(0.03)
    return {"gevonden": True}


_traag_regio.__name__ = "load_dashboard_regio"


def _meldingen(caplog):
    return [r for r in caplog.records if r.getMessage().startswith("DASHBOARD traag")]


def test_een_lading_boven_de_drempel_schrijft_een_info_regel_met_eindpunt_en_duur(dashboards_aan, monkeypatch, caplog):
    monkeypatch.setattr(routes.instellingen, "DASHBOARD_TRAAG_S", 0.01)

    with caplog.at_level(logging.INFO, logger="routes.instellingen"):
        asyncio.run(routes.instellingen._laad_dashboard(_traag_regio, "Instelling Die Niet In Het Log Hoort"))

    [regel] = _meldingen(caplog)
    assert regel.levelno == logging.INFO
    assert re.fullmatch(r"DASHBOARD traag: eindpunt=load_dashboard_regio duur=\d+\.\d s", regel.getMessage())
    # De gevraagde instelling is gebruikerstekst en komt niet in het log.
    assert "Niet In Het Log" not in caplog.text


def test_een_snelle_lading_schrijft_niets(dashboards_aan, caplog):
    with caplog.at_level(logging.INFO, logger="routes.instellingen"):
        asyncio.run(routes.instellingen._laad_dashboard(_traag_regio, "HU"))

    assert _meldingen(caplog) == []


def test_een_trage_lading_die_faalt_staat_ook_in_het_log(dashboards_aan, monkeypatch, caplog):
    monkeypatch.setattr(routes.instellingen, "DASHBOARD_TRAAG_S", 0.01)

    def faalt(instelling):
        time.sleep(0.03)
        raise dashboard.BronNietBeschikbaar

    with caplog.at_level(logging.INFO, logger="routes.instellingen"):
        resp = asyncio.run(routes.instellingen._laad_dashboard(faalt, "HU"))

    assert isinstance(resp, JSONResponse) and resp.status_code == 503
    assert len(_meldingen(caplog)) == 1


def test_geen_plaats_binnen_de_wachttijd_geeft_503_druk(dashboards_aan, monkeypatch):
    geladen = []

    def lader(instelling):
        geladen.append(instelling)
        return {"gevonden": True}

    async def vol():
        plaatsen = Runplaatsen(max_tegelijk=1, wacht_s=0.01)
        monkeypatch.setattr(routes.instellingen, "_dashboardplaatsen", plaatsen)
        async with plaatsen.plaats():
            return await routes.instellingen._laad_dashboard(lader, "HU")

    resp = asyncio.run(vol())

    assert resp.status_code == 503
    assert geladen == []


def test_binnen_de_grenzen_gewoon_de_data(client, monkeypatch):
    _nep_lader(monkeypatch, lambda instelling: {"gevonden": True, "instelling": instelling})

    resp = client.get("/api/dashboard/regio", params={"instelling": "VU"})

    assert resp.status_code == 200
    assert resp.json() == {"gevonden": True, "instelling": "VU"}
