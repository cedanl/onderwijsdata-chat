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


# ─── #1079: ondergrond, instellingen in dezelfde plaats, legenda onder de kaart ─────────────────────────────────────


@pytest.fixture
def samen(monkeypatch):
    """Een eigen instelling in Utrecht met drie peers in dezelfde plaats, twee in Houten en één in Amsterdam."""
    plaatsen = {
        "EIGEN": "UTRECHT",
        "U1": "UTRECHT",
        "U2": "UTRECHT",
        "U3": "UTRECHT",
        "H1": "HOUTEN",
        "H2": "HOUTEN",
        "A1": "AMSTERDAM",
    }
    adres = {code: {"plaatsnaam": plaats} for code, plaats in plaatsen.items()}
    registry = [{"instellingscode": code, "naam": f"Instelling {code}"} for code in plaatsen]
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: adres)
    monkeypatch.setattr(dashboard, "get_all_instellingen", lambda: registry)
    return RegioContext(
        regio_naam="Midden-Utrecht",
        regio_type="arbeidsmarktregio",
        provincie="Utrecht",
        self_code="EIGEN",
        peer_codes=frozenset(plaatsen) - {"EIGEN"},
        soort="mbo",
        terugval=None,
    )


def _figuur(ctx, naam="Instelling EIGEN"):
    figuur = _build_kaart_figure(ctx, naam)
    assert figuur is not None
    return json.loads(figuur)


def _trace(figuur, naam):
    return next(t for t in figuur["data"] if t["name"] == naam)


def test_kaart_heeft_een_ondergrond_van_provinciegrenzen_onder_de_punten(samen):
    figuur = _figuur(samen)

    ondergrond = figuur["data"][0]
    assert ondergrond["type"] == "choropleth"
    assert ondergrond["showlegend"] is False and ondergrond["hoverinfo"] == "skip"
    # Alleen de provincies in beeld: Utrecht, Noord-Holland en hun buren, niet Limburg of Groningen.
    ids = set(ondergrond["locations"])
    assert {"PV26", "PV27"} <= ids
    assert not ids & {"PV31", "PV20"}
    assert {f["id"] for f in ondergrond["geojson"]["features"]} == ids
    assert [t["type"] for t in figuur["data"][1:]] == ["scattergeo", "scattergeo"]


def test_kaart_zet_instellingen_in_dezelfde_plaats_op_een_punt_met_hun_aantal(samen):
    concurrenten = _trace(_figuur(samen), "Concurrenten")

    per_plaats = dict(zip(concurrenten["text"], concurrenten["hovertext"], strict=True))
    assert per_plaats["3"].startswith("3 instellingen in Utrecht:")
    assert all(f"Instelling U{n}" in per_plaats["3"] for n in (1, 2, 3))
    assert per_plaats["2"].startswith("2 instellingen in Houten:")
    # Eén instelling in een plaats houdt haar naam en krijgt geen getal.
    assert per_plaats[""] == "Instelling A1"
    grootte = dict(zip(concurrenten["text"], concurrenten["marker"]["size"], strict=True))
    assert grootte[""] < grootte["2"] == grootte["3"]
    assert len(concurrenten["lat"]) == 3


def test_de_ster_noemt_de_andere_instellingen_in_haar_plaats(samen):
    ster = _trace(_figuur(samen), "Instelling EIGEN")

    assert ster["hovertext"] == ["Instelling EIGEN<br>Ook in Utrecht: Instelling U1, Instelling U2, Instelling U3"]
    assert ster["text"] == ["Instelling EIGEN"]


def test_de_ster_zonder_andere_instellingen_in_haar_plaats_houdt_alleen_haar_naam(regio):
    ster = _trace(_figuur(regio, "Hogeschool Utrecht"), "Hogeschool Utrecht")

    assert ster["hovertext"] == ["Hogeschool Utrecht"]


def test_de_rijen_blijven_een_rij_per_instelling(samen):
    rijen = _meta(samen)["data"]

    assert len(rijen) == 7
    assert sum(r["Plaats"] == "Utrecht" for r in rijen) == 4


def test_de_legenda_staat_onder_de_kaart_en_het_label_van_de_ster_binnen_beeld(samen):
    figuur = _figuur(samen)

    legenda = figuur["layout"]["legend"]
    assert legenda["orientation"] == "h" and legenda["yanchor"] == "top" and legenda["y"] == 0
    assert figuur["layout"]["margin"]["b"] >= 50
    ster = _trace(figuur, "Instelling EIGEN")
    assert ster["textposition"] in {"top right", "top left"}


def test_de_ster_aan_de_rechterrand_zet_haar_naam_links(monkeypatch):
    adres = {"EIGEN": {"plaatsnaam": "ENSCHEDE"}, "P": {"plaatsnaam": "ZWOLLE"}}
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: adres)
    monkeypatch.setattr(dashboard, "get_all_instellingen", lambda: [{"instellingscode": c, "naam": c} for c in adres])
    ctx = RegioContext(
        regio_naam="Twente",
        regio_type="arbeidsmarktregio",
        provincie="Overijssel",
        self_code="EIGEN",
        peer_codes=frozenset({"P"}),
        soort="mbo",
        terugval=None,
    )

    assert _trace(_figuur(ctx, "EIGEN"), "EIGEN")["textposition"] == "top left"


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
