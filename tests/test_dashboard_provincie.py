"""Waar de provincie van een dashboard vandaan komt (#904, regiovoorbehoud).

Regio en provincie volgen het adres van de hoofdvestiging in het DUO-adressenbestand. Zonder adres viel het dashboard
stil terug op de provincie die het vaakst bij de instelling in het DUO-bestand staat, en toonde die even stellig. Nu
zegt de payload welke van de twee het is (`provincie_herkomst`), zodat de pagina het erbij kan zeggen.
"""

import pandas as pd
import pytest

import data.dashboard as dashboard

pytestmark = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")

_HU = "Hogeschool Utrecht"
_MONDRIAAN = "ROC Mondriaan"
_LADERS = [dashboard.load_dashboard_regio, dashboard.load_dashboard_arbeidsmarktmatch]


@pytest.mark.parametrize("lader", _LADERS)
@pytest.mark.parametrize("instelling", [_HU, _MONDRIAAN])
def test_met_adres_komt_de_provincie_uit_het_adres_van_de_hoofdvestiging(lader, instelling):
    result = lader(instelling)

    assert result["provincie_herkomst"] == "adres"
    assert result["provincie"] not in (None, "Onbekend")


@pytest.mark.parametrize("lader", _LADERS)
@pytest.mark.parametrize("instelling", [_HU, _MONDRIAAN])
def test_zonder_adres_zegt_de_payload_dat_de_provincie_uit_de_inschrijvingen_komt(monkeypatch, lader, instelling):
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: {})

    result = lader(instelling)

    assert result["provincie_herkomst"] == "inschrijvingen"
    assert result["provincie"] not in (None, "Onbekend")


def test_zonder_adres_en_zonder_provincie_in_het_bestand_is_er_geen_herkomst(monkeypatch):
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: {})

    assert dashboard._provincie(None, "00XX", pd.Series([None, None])) == (None, None)


def test_een_adres_gaat_voor_de_meest_voorkomende_provincie(monkeypatch):
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: {"00XX": {"provincie": "Utrecht"}})

    assert dashboard._provincie(None, "00XX", pd.Series(["Gelderland", "Gelderland"])) == ("Utrecht", "adres")
