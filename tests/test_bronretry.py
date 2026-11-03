"""Herhaling met backoff voor een tijdelijke bronfout (#867).

Een 503 of een verbroken verbinding werd meteen een bronfout voor de gebruiker, terwijl dezelfde aanroep een
seconde later slaagde. Nu: hooguit twee herhalingen, alleen voor een GET, alleen op 5xx, 429 en verbindingsfouten,
binnen een budget. Een blijvende fout geeft dezelfde melding als zonder herhaling, ook de CBS-500 op een
haakjesgroep (#561).
"""

import json
import logging
from contextlib import ExitStack
from unittest.mock import patch
from urllib.parse import unquote_plus

import httpx
import onderwijsdata.client
import pandas as pd
import pytest

from tests.nepserver import Antwoord, Nepserver, nepserver, reeks
from tools import bronretry, cbs, duo, fouten, rio

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_RIJEN = {"value": [{"ID": 0, "Perioden": "2024JJ00", "Aantal": 12}]}


class _Klok:
    """Een klok die alleen loopt als de test of de slaap hem verzet."""

    def __init__(self):
        self.nu = 0.0
        self.geslapen: list[float] = []

    def __call__(self) -> float:
        return self.nu

    def slaap(self, s: float) -> None:
        self.geslapen.append(s)
        self.nu += s


def _beleid(klok: _Klok, **kw) -> bronretry.Beleid:
    return bronretry.Beleid(slaap=klok.slaap, klok=klok, toeval=lambda: 0.5, **kw)


def _status(code: int, methode: str = "GET", headers: dict | None = None) -> httpx.HTTPStatusError:
    verzoek = httpx.Request(methode, "https://bron.test/pad")
    antwoord = httpx.Response(code, request=verzoek, headers=headers)
    return httpx.HTTPStatusError(f"HTTP {code}", request=verzoek, response=antwoord)


class _Reeks:
    """Een `haal` die de uitkomsten in volgorde geeft of gooit, en telt hoe vaak hij liep."""

    def __init__(self, *uitkomsten):
        self.rest = list(uitkomsten)
        self.aanroepen = 0

    def __call__(self):
        self.aanroepen += 1
        uit = self.rest.pop(0)
        if isinstance(uit, Exception):
            raise uit
        return uit


# --- het beleid ------------------------------------------------------------------------


def test_een_503_en_dan_een_antwoord_geeft_het_antwoord(caplog):
    klok = _Klok()
    haal = _Reeks(_status(503), "rijen")
    with caplog.at_level(logging.WARNING, logger="tools.bronretry"):
        assert bronretry.haal_op_met_retry("CBS", haal, _beleid(klok)) == "rijen"
    assert haal.aanroepen == 2
    assert klok.geslapen == [0.75]  # 0,5 s × (1 + jitter 0,5)
    assert "BRON_RETRY bron=CBS poging=1/2 reden=HTTP 503" in caplog.text


def test_drie_keer_503_geeft_de_oorspronkelijke_fout_na_twee_herhalingen():
    klok = _Klok()
    laatste = _status(503)
    haal = _Reeks(_status(503), _status(503), laatste)
    with pytest.raises(httpx.HTTPStatusError) as fout:
        bronretry.haal_op_met_retry("DUO", haal, _beleid(klok))
    assert fout.value is laatste
    assert haal.aanroepen == 3
    assert klok.geslapen == [0.75, 1.5]  # de wachttijd verdubbelt


@pytest.mark.parametrize("code", [400, 401, 404, 410])
def test_een_4xx_wordt_niet_herhaald(code):
    klok = _Klok()
    haal = _Reeks(_status(code), "rijen")
    with pytest.raises(httpx.HTTPStatusError):
        bronretry.haal_op_met_retry("RIO", haal, _beleid(klok))
    assert haal.aanroepen == 1
    assert klok.geslapen == []


def test_een_429_wacht_de_retry_after_van_de_bron():
    klok = _Klok()
    haal = _Reeks(_status(429, headers={"Retry-After": "3"}), "rijen")
    assert bronretry.haal_op_met_retry("CBS", haal, _beleid(klok)) == "rijen"
    assert klok.geslapen == [3.0]


@pytest.mark.parametrize("fout", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError])
def test_een_verbindingsfout_bij_een_get_wordt_herhaald(fout):
    klok = _Klok()
    haal = _Reeks(fout("weg", request=httpx.Request("GET", "https://bron.test/")), "rijen")
    assert bronretry.haal_op_met_retry("RIO", haal, _beleid(klok)) == "rijen"
    assert haal.aanroepen == 2


def test_alleen_een_get_wordt_herhaald():
    klok = _Klok()
    haal = _Reeks(_status(503, methode="POST"), "rijen")
    with pytest.raises(httpx.HTTPStatusError):
        bronretry.haal_op_met_retry("CBS", haal, _beleid(klok))
    assert haal.aanroepen == 1


def test_een_fout_zonder_verzoek_of_buiten_httpx_wordt_niet_herhaald():
    klok = _Klok()
    haal = _Reeks(httpx.ReadTimeout("geen verzoek bekend"), ValueError("geen resource 'x'"))
    with pytest.raises(httpx.ReadTimeout):
        bronretry.haal_op_met_retry("RIO", haal, _beleid(klok))
    with pytest.raises(ValueError):
        bronretry.haal_op_met_retry("RIO", haal, _beleid(klok))
    assert haal.aanroepen == 2


def test_geen_herhaling_als_de_eerste_poging_het_budget_al_opmaakte():
    """Een aanroep die tegen de timeout van het pakket liep, laat de tool niet nog eens zo lang wachten."""
    klok = _Klok()
    eerste = _status(504)

    def haal():
        klok.nu += 29.5  # zo lang duurde de mislukte aanroep
        raise eerste

    with pytest.raises(httpx.HTTPStatusError):
        bronretry.haal_op_met_retry("CBS", haal, _beleid(klok, budget_s=30.0))
    assert klok.geslapen == []


def test_de_wachttijd_heeft_jitter_binnen_de_grenzen():
    beleid = bronretry.Beleid(toeval=lambda: 0.0)
    assert beleid.wachttijd(0, _status(503)) == 0.5
    assert bronretry.Beleid(toeval=lambda: 0.999).wachttijd(1, _status(503)) == pytest.approx(2.0, abs=0.01)


# --- het CBS-ophaalpad tegen een nepserver ------------------------------------------------


class _CbsBron:
    """`tools.cbs._haal` met de echte `onderwijsdata.data` tegen een nepserver, zonder echte wachttijd."""

    def __init__(self, monkeypatch, servers: ExitStack):
        self.klok = _Klok()
        self._monkeypatch = monkeypatch
        self._servers = servers
        monkeypatch.setattr(bronretry, "STANDAARD", _beleid(self.klok))

    def __call__(self, antwoord) -> Nepserver:
        bron = self._servers.enter_context(nepserver(antwoord))
        self._monkeypatch.setattr(onderwijsdata.client, "BASE_FEED", bron.url)
        return bron


@pytest.fixture
def cbs_bron(monkeypatch):
    with ExitStack() as servers:
        yield _CbsBron(monkeypatch, servers)


def _bronfout(filters: dict) -> str:
    uit = cbs._haal("85423NED", filters, vo_context=False)
    assert isinstance(uit, str), uit
    return uit


def _json(status: int, body: dict | None = None) -> Antwoord:
    return Antwoord(status, json.dumps(body or {"odata.error": "fout"}).encode(), {"Content-Type": "application/json"})


def test_cbs_eerst_503_dan_200_geeft_rijen_zonder_bronfout(cbs_bron):
    bron = cbs_bron(reeks(_json(503), _json(200, _RIJEN)))
    opgehaald = cbs._haal("85423NED", {"$filter": "trim(Perioden) eq '2024JJ00'"}, vo_context=False)
    assert not isinstance(opgehaald, str), opgehaald
    assert opgehaald.rows == _RIJEN["value"]
    assert len(bron.verzoeken) == 2


def _zonder_herhaling(monkeypatch, filters: dict) -> str:
    monkeypatch.setattr(bronretry, "STANDAARD", bronretry.Beleid(herhalingen=0))
    return _bronfout(filters)


def test_cbs_drie_keer_503_geeft_dezelfde_bronfout_als_zonder_herhaling(cbs_bron, monkeypatch):
    filters = {"$filter": "trim(Perioden) eq '2024JJ00'"}
    bron = cbs_bron(reeks(_json(503)))
    met_herhaling = _bronfout(filters)
    assert len(bron.verzoeken) == 3
    assert met_herhaling == _zonder_herhaling(monkeypatch, filters)
    assert fouten.code(met_herhaling) == fouten.Fout.BRON_ONBEREIKBAAR
    assert "HTTP 503" in met_herhaling


@pytest.mark.parametrize("code", [400, 404])
def test_cbs_een_400_of_404_gaat_één_keer_naar_de_bron(cbs_bron, code):
    bron = cbs_bron(reeks(_json(code)))
    uit = _bronfout({"$filter": "trim(Perioden) eq '2024JJ00'"})
    assert fouten.code(uit) == fouten.Fout.BRON_WEIGERT
    assert len(bron.verzoeken) == 1
    assert cbs_bron.klok.geslapen == []


def test_cbs_500_op_een_haakjesgroep_blijft_een_500_en_staat_in_het_log(cbs_bron, monkeypatch, caplog):
    """#561: CBS geeft HTTP 500 op `(A or B) and (X and Y)`. De herhaling verbergt dat niet en verandert de melding niet."""

    def zoals_cbs(pad: str) -> Antwoord:
        # Zoals CBS: een haakjesgroep naast een andere haakjesgroep in de $filter is een serverfout, elke keer.
        return _json(500) if ") and (" in unquote_plus(pad) else _json(200, _RIJEN)

    filters = {
        "$filter": "(trim(Geslacht) eq 'T001038' or trim(Geslacht) eq '3000') and (trim(Perioden) eq '2024JJ00')"
    }
    bron = cbs_bron(zoals_cbs)
    with caplog.at_level(logging.WARNING, logger="tools.bronretry"):
        uit = _bronfout(filters)
    assert fouten.code(uit) == fouten.Fout.BRON_ONBEREIKBAAR
    assert "HTTP 500" in uit
    assert len(bron.verzoeken) == 3
    assert len(set(bron.verzoeken)) == 1, "elke poging stuurt dezelfde $filter, niets wordt herschreven"
    assert caplog.text.count("BRON_RETRY bron=CBS") == 2
    assert uit == _zonder_herhaling(monkeypatch, filters)


# --- de andere aanroeppunten ----------------------------------------------------------------


@pytest.fixture
def zonder_wachten(monkeypatch):
    monkeypatch.setattr(bronretry, "STANDAARD", _beleid(_Klok()))


@pytest.mark.usefixtures("zonder_wachten")
def test_duo_load_wordt_herhaald_na_een_503():
    df = pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL_INGESCHREVENEN": [10]})
    with patch.object(duo._duo, "load", side_effect=[_status(503), df]) as load:
        uit = json.loads(duo.get_duo_data("p01hoinges", 2))
    assert uit["totaal_rijen"] == 1
    assert load.call_count == 2


@pytest.mark.usefixtures("zonder_wachten")
def test_rio_fetch_wordt_herhaald_na_een_verbindingsfout():
    fout = httpx.ConnectError("reset", request=httpx.Request("GET", "https://rio.test/"))
    with patch("tools.rio.fetch", side_effect=[fout, [{"code": "1"}]]) as fetch:
        uit = rio.get_rio_data("opleidingen")
    assert fouten.code(uit) is None, uit
    assert fetch.call_count == 2
