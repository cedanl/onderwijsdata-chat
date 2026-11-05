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
        soort="hbo",
        terugval=None,
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


# ─── #951: elke plaats van een hoofdvestiging staat op de kaart ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("duo_fixtures")
def test_elke_plaats_uit_de_duo_adressen_heeft_coordinaten():
    # Curio (Etten-Leur) stond niet op haar eigen kaart: de plaats ontbrak in _CITY_COORDS. De adressen zijn de
    # bevroren DUO-bestanden; komt er bij het verversen van de fixtures een plaats bij, dan faalt dit.
    from onderwijsbronnen import duo

    plaatsen = {
        str(p).strip().upper()
        for resource in ("adressen_ho", "adressen_mbo")
        for p in duo.load(resource, 1)["PLAATSNAAM"].dropna()
    }

    assert plaatsen - set(dashboard._CITY_COORDS) == set()


@pytest.mark.usefixtures("duo_fixtures")
def test_curio_staat_op_haar_eigen_kaart():
    ctx = dashboard._build_regio_context("Curio", "mbo")
    assert ctx is not None

    figuur = _build_kaart_figure(ctx, "Curio")
    assert figuur is not None
    meta = json.loads(figuur)["layout"]["meta"]

    assert meta["data"][0] == {"Instelling": "Curio", "Plaats": "Etten-Leur", "Rol": "eigen instelling"}
    assert "Curio" not in meta["zonder_locatie"]
