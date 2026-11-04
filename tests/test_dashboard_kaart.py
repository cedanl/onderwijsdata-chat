"""De kaart van het regiodashboard (#906): wie op de kaart staat, en wie niet omdat de plaats onbekend is."""

import json
from dataclasses import replace

import pytest

from data import dashboard
from data.dashboard import RegioContext, _build_kaart_figure


@pytest.fixture
def regio(monkeypatch):
    adres = {
        "EIGEN": {"plaatsnaam": "UTRECHT"},
        "PEER1": {"plaatsnaam": "AMSTERDAM"},
        "PEER2": {"plaatsnaam": "WAGENINGEN-NOORD"},  # niet in de lijst met stadscoördinaten
        "PEER3": {},
    }
    registry = [
        {"instellingscode": "EIGEN", "naam": "Hogeschool Utrecht"},
        {"instellingscode": "PEER1", "naam": "Hogeschool van Amsterdam"},
        {"instellingscode": "PEER2", "naam": "Hogeschool Ergens"},
        {"instellingscode": "PEER3", "naam": "Hogeschool Zonder Adres"},
    ]
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: adres)
    monkeypatch.setattr(dashboard, "get_all_instellingen", lambda: registry)
    return RegioContext(
        regio_naam="Midden-Utrecht",
        regio_type="arbeidsmarktregio",
        provincie="Utrecht",
        self_code="EIGEN",
        peer_codes=frozenset({"PEER1", "PEER2", "PEER3"}),
    )


def _meta(regio):
    figuur = _build_kaart_figure(regio, "Hogeschool Utrecht")
    assert figuur is not None
    return json.loads(figuur)["layout"]["meta"]


def test_kaart_noemt_de_instellingen_zonder_bekende_plaats(regio):
    assert _meta(regio)["zonder_locatie"] == ["Hogeschool Ergens", "Hogeschool Zonder Adres"]


def test_kaart_geeft_haar_punten_als_rijen_voor_de_tabel(regio):
    rijen = _meta(regio)["data"]
    assert rijen == [
        {"Instelling": "Hogeschool Utrecht", "Plaats": "Utrecht", "Rol": "eigen instelling"},
        {"Instelling": "Hogeschool van Amsterdam", "Plaats": "Amsterdam", "Rol": "concurrent"},
    ]


def test_kaart_zonder_ontbrekende_plaats_heeft_een_lege_lijst(regio):
    assert _meta(replace(regio, peer_codes=frozenset({"PEER1"})))["zonder_locatie"] == []
