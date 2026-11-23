"""De onderdelen van de regiokaart van Mijn instelling (#906, #1079): een ondergrond met provinciegrenzen, één punt per
plaats met het aantal instellingen erin, en de ster van de eigen instelling.

`provincies.geojson` heeft de provinciegrenzen van 2024 (CBS en Kadaster, via cartomap, CC BY 4.0), sterk vereenvoudigd
en op vier decimalen afgerond: genoeg om te zien in welke provincie een punt ligt, klein genoeg voor elke lading. De
kaart zit in de figuur zelf, dus de browser haalt niets van buiten (CSP, #486).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import NamedTuple

import plotly.graph_objects as go

_PROVINCIES = Path(__file__).with_name("provincies.geojson")
# Dezelfde kleuren als het land en de landsgrenzen van de kaart (frontend kaart-figuur.js zet ze per thema).
_LAND = "#F8FAFC"
_GRENS = "#94A3B8"
# Eén instelling is een stip; een plaats met meer instellingen een grotere, met het aantal ernaast. De ster (16) valt
# op een grotere stip dan een ring te zien, zodat de eigen plaats niet verdwijnt (#1079).
_STIP = 10
_GROEP = 22


class Groep(NamedTuple):
    """De instellingen in één plaats (op één coördinaat), op naam gesorteerd."""

    coords: tuple[float, float]
    plaats: str
    namen: tuple[str, ...]


def groepeer(punten: Iterable[tuple[tuple[float, float], str, str]]) -> list[Groep]:
    """(coördinaat, plaats, naam) per instelling → één groep per coördinaat, op de eerste naam van de groep gesorteerd.
    Plaatsen die dezelfde coördinaat delen ('s-Gravenhage en Den Haag) zijn één plaats."""
    per_plek: dict[tuple[float, float], list[tuple[str, str]]] = defaultdict(list)
    for coords, plaats, naam in punten:
        per_plek[coords].append((naam, plaats))
    groepen = [
        Groep(coords, leden[0][1], tuple(naam for naam, _ in leden))
        for coords, leden in ((c, sorted(leden)) for c, leden in per_plek.items())
    ]
    return sorted(groepen, key=lambda g: g.namen[0])


def _vlakken(coordinaten) -> Iterable[tuple[float, float]]:
    """Alle (lon, lat)-paren van een geometrie, hoe diep ze ook genest zijn."""
    if coordinaten and isinstance(coordinaten[0], (int, float)):
        yield coordinaten[0], coordinaten[1]
    else:
        for deel in coordinaten:
            yield from _vlakken(deel)


def _oppervlak(ring: list[list[float]]) -> float:
    """De getekende oppervlakte van een ring (veterstrengformule): positief tegen de klok in."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True)) / 2


def _draai(polygoon: list[list[list[float]]]) -> list[list[list[float]]]:
    """Buitenrand met de klok mee, gaten tegen de klok in. Plotly tekent met d3-geo, dat een ring tegen de klok in
    (de volgorde van de GeoJSON-standaard) leest als de rest van de wereld: dan kleurt het vlak alles behalve de
    provincie (#1079)."""
    return [ring if (_oppervlak(ring) < 0) == (i == 0) else ring[::-1] for i, ring in enumerate(polygoon)]


def _met_de_klok_mee(geometrie: dict) -> dict:
    if geometrie["type"] == "Polygon":
        return {**geometrie, "coordinates": _draai(geometrie["coordinates"])}
    return {**geometrie, "coordinates": [_draai(polygoon) for polygoon in geometrie["coordinates"]]}


@cache
def _provincies() -> tuple[tuple[dict, tuple[float, float, float, float]], ...]:
    """De provincies met hun omhullende (lat_min, lat_max, lon_min, lon_max)."""
    features = [
        {**f, "geometry": _met_de_klok_mee(f["geometry"])}
        for f in json.loads(_PROVINCIES.read_text(encoding="utf-8"))["features"]
    ]
    uit = []
    for feature in features:
        paren = list(_vlakken(feature["geometry"]["coordinates"]))
        lons, lats = [p[0] for p in paren], [p[1] for p in paren]
        uit.append((feature, (min(lats), max(lats), min(lons), max(lons))))
    return tuple(uit)


def ondergrond(lat_range: list[float], lon_range: list[float]) -> go.Choropleth | None:
    """De provincies die in beeld komen, als vlak met een grens; None als er geen in beeld is."""
    in_beeld = [
        feature
        for feature, (lat_min, lat_max, lon_min, lon_max) in _provincies()
        if lat_min <= lat_range[1] and lat_max >= lat_range[0] and lon_min <= lon_range[1] and lon_max >= lon_range[0]
    ]
    if not in_beeld:
        return None
    return go.Choropleth(
        geojson={"type": "FeatureCollection", "features": in_beeld},
        featureidkey="id",
        locations=[f["id"] for f in in_beeld],
        z=[0] * len(in_beeld),
        colorscale=[[0, _LAND], [1, _LAND]],
        showscale=False,
        marker={"line": {"color": _GRENS, "width": 1}},
        hoverinfo="skip",
        showlegend=False,
        name="Provincies",
    )


def concurrenten(groepen: list[Groep]) -> go.Scattergeo:
    """Eén punt per plaats. Een plaats met meer instellingen krijgt een grotere stip met het aantal ernaast, en haar
    tooltip noemt ze allemaal: anders liggen ze op elkaar en is er maar één te zien (#1079)."""
    teksten, tooltips, groottes = [], [], []
    for groep in groepen:
        aantal = len(groep.namen)
        teksten.append("" if aantal == 1 else str(aantal))
        tooltips.append(
            groep.namen[0]
            if aantal == 1
            else f"{aantal} instellingen in {groep.plaats}:<br>" + "<br>".join(groep.namen)
        )
        groottes.append(_STIP if aantal == 1 else _GROEP)
    return go.Scattergeo(
        lon=[g.coords[1] for g in groepen],
        lat=[g.coords[0] for g in groepen],
        text=teksten,
        hovertext=tooltips,
        mode="markers+text",
        textposition="middle right",
        textfont={"size": 13, "color": "#1F2937"},
        # 3:1 tegen het land in beide thema's (#905); #94A3B8 haalde 2,5:1.
        marker={"size": groottes, "color": "#64748B", "line": {"width": 1, "color": "white"}},
        hovertemplate="%{hovertext}<extra></extra>",
        name="Concurrenten",
        meta="aantal",
    )


def eigen_instelling(
    coords: tuple[float, float], naam: str, plaats: str, anderen: tuple[str, ...], label: str
) -> go.Scattergeo:
    """De ster van de eigen instelling. `anderen` zijn de peers in dezelfde plaats: de tooltip noemt ze, want hun stip
    ligt onder de ster. `label` is de plek van de naam ten opzichte van de ster (zie `labelpositie`)."""
    tooltip = f"{naam}<br>Ook in {plaats}: {', '.join(anderen)}" if anderen else naam
    return go.Scattergeo(
        lon=[coords[1]],
        lat=[coords[0]],
        text=[naam],
        hovertext=[tooltip],
        mode="markers+text",
        textposition=label,
        textfont={"size": 12, "color": "#1E40AF"},
        marker={"size": 16, "color": "#2563EB", "symbol": "star", "line": {"width": 1.5, "color": "white"}},
        hovertemplate="%{hovertext}<extra></extra>",
        name=naam,
        meta="eigen",
    )


def labelpositie(lon: float, lon_range: list[float]) -> str:
    """De naam naast de ster staat rechts, tenzij de ster in de rechterhelft ligt: dan loopt de naam van het scherm,
    zeker op een telefoon (#1079)."""
    deel = (lon - lon_range[0]) / (lon_range[1] - lon_range[0])
    return "top left" if deel > 0.6 else "top right"


# Plotly houdt de verhouding van de kaart vast: bij een vierkant bereik is het kader op een telefoon half zo breed als het
# scherm, en een label bij de ster loopt dan tegen de rand (#1079). Het bereik is daarom minstens zo veel keer zo breed
# (in graden) als hoog; op de kaart van een regio is dat een telefoonbreed kader, op een breder scherm blijft het kader
# even hoog.
_BREEDTE_T_O_V_HOOGTE = 2.0


def bereik(punten: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """(lat_range, lon_range) om de punten heen met ruimte erbij, of heel Nederland zonder punten."""
    if not punten:
        return [50.3, 53.9], [3.0, 7.8]
    lats, lons = [p[0] for p in punten], [p[1] for p in punten]
    lat_spread = max(max(lats) - min(lats), 0.25)
    lon_spread = max(max(lons) - min(lons), 0.35)
    lat_range = [min(lats) - lat_spread * 0.65, max(lats) + lat_spread * 0.65]
    lon_range = [min(lons) - lon_spread * 0.65, max(lons) + lon_spread * 0.65]
    breed = max(lat_range[1] - lat_range[0], 0) * _BREEDTE_T_O_V_HOOGTE
    midden, tekort = sum(lon_range) / 2, breed - (lon_range[1] - lon_range[0])
    if tekort > 0:
        lon_range = [midden - breed / 2, midden + breed / 2]
    return lat_range, lon_range
