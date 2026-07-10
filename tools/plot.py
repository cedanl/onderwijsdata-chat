import json as _json
import urllib.request

import plotly.express as px
import plotly.graph_objects as go

from . import store

# Okabe-Ito colorblind-friendly palette
_PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]

_LAYOUT_BASE = dict(
    font=dict(family="Inter, Arial, sans-serif", size=13),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(t=60, b=50, l=70, r=20),
    legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#ddd", borderwidth=1),
)

_AXIS_STYLE = dict(showgrid=True, gridcolor="#f0f0f0", linecolor="#ccc", zeroline=False)

_GEOJSON_URLS = {
    "provincie": "https://cartomap.github.io/nl/wgs84/provincie_2024.geojson",
    "gemeente":  "https://cartomap.github.io/nl/wgs84/gemeente_2024.geojson",
    "corop":     "https://cartomap.github.io/nl/wgs84/coropgebied_2024.geojson",
}
_GEOJSON_CACHE: dict[str, dict] = {}


def _group_by_color(data: list[dict], x: str, y: str, color_by: str) -> dict[str, dict]:
    """Group data rows by the *color_by* column."""
    groups: dict[str, dict] = {}
    for row in data:
        key = str(row.get(color_by, "onbekend"))
        groups.setdefault(key, {"x": [], "y": []})
        groups[key]["x"].append(row.get(x))
        groups[key]["y"].append(row.get(y))
    return groups


def _add_trace(fig: go.Figure, chart_type: str, x_vals: list, y_vals: list,
               color: str, name: str | None = None) -> None:
    """Add a single trace to the figure based on *chart_type*."""
    common = {"name": name} if name else {}
    if chart_type == "bar":
        fig.add_trace(go.Bar(x=x_vals, y=y_vals, marker_color=color, **common))
    elif chart_type == "line":
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines+markers",
                                  line=dict(color=color, width=2), marker=dict(size=5), **common))
    elif chart_type == "scatter":
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="markers",
                                  marker=dict(color=color, size=7), **common))
    elif chart_type == "histogram":
        fig.add_trace(go.Histogram(x=x_vals, marker_color=color,
                                    opacity=0.7 if name else 0.85, **common))
    elif chart_type == "pie" and not name:
        fig.add_trace(go.Pie(labels=x_vals, values=y_vals,
                              marker=dict(colors=_PALETTE), hole=0.3))


def create_plot(
    data: list[dict] | None = None,
    chart_type: str = "bar",
    x: str = "",
    y: str = "",
    title: str = "",
    color_by: str | None = None,
    data_key: str | None = None,
) -> tuple[str, go.Figure]:
    if data_key:
        df = store.get(data_key)
        if df is None:
            return f"Geen data gevonden voor '{data_key}'.", None
        data = df.to_dict(orient="records")
    if not data:
        return "Geen data opgegeven. Gebruik data_key of data parameter.", None

    fig = go.Figure()

    if color_by:
        groups = _group_by_color(data, x, y, color_by)
        for i, (name, vals) in enumerate(groups.items()):
            _add_trace(fig, chart_type, vals["x"], vals["y"],
                       _PALETTE[i % len(_PALETTE)], name=name)

        if chart_type == "bar":
            fig.update_layout(barmode="group")
        elif chart_type == "histogram":
            fig.update_layout(barmode="overlay")

    else:
        x_vals = [row.get(x) for row in data]
        y_vals = [row.get(y) for row in data]
        _add_trace(fig, chart_type, x_vals, y_vals, _PALETTE[0])

    layout = dict(
        title=dict(text=title, font=dict(size=16, color="#222")),
        legend_title=color_by or "",
        **_LAYOUT_BASE,
    )

    if chart_type not in ("pie",):
        layout["xaxis"] = dict(title=x, **_AXIS_STYLE)
        layout["yaxis"] = dict(title=y, tickformat=",", **_AXIS_STYLE)

    fig.update_layout(**layout)
    fig.update_layout(meta={"data": data, "x": x, "y": y, "chart_type": chart_type, "color_by": color_by})

    return f"Grafiek '{title}' aangemaakt ({len(data)} datapunten).", fig


def _load_geojson(level: str) -> dict:
    url = _GEOJSON_URLS[level]
    if url not in _GEOJSON_CACHE:
        with urllib.request.urlopen(url, timeout=15) as resp:
            _GEOJSON_CACHE[url] = _json.loads(resp.read())
    return _GEOJSON_CACHE[url]


def _detect_level(codes: list[str]) -> str:
    for code in codes:
        c = code.strip().upper()
        if c.startswith("GM"):
            return "gemeente"
        if c.startswith("CR"):
            return "corop"
        if c.startswith("PV"):
            return "provincie"
    return "provincie"


def create_choropleth_map(
    data: list[dict] | None = None,
    location_col: str = "",
    value_col: str = "",
    title: str = "",
    level: str = "auto",
    data_key: str | None = None,
) -> tuple[str, go.Figure]:
    if data_key:
        df = store.get(data_key)
        if df is None:
            return f"Geen data gevonden voor '{data_key}'.", None
        data = df.to_dict(orient="records")
    if not data:
        return "Geen data om op kaart te tonen.", None

    cleaned = [
        {**row, location_col: str(row.get(location_col, "")).strip()}
        for row in data
        if str(row.get(location_col, "")).strip() and row.get(value_col) is not None
    ]
    if not cleaned:
        return f"Kolommen '{location_col}' of '{value_col}' zijn leeg of niet gevonden.", None

    codes = [row[location_col] for row in cleaned]
    detected = _detect_level(codes) if level == "auto" else level

    try:
        geojson = _load_geojson(detected)
    except Exception as exc:
        return f"GeoJSON laden mislukt ({detected}): {exc}", None

    try:
        values = [float(row[value_col]) for row in cleaned]
    except (TypeError, ValueError):
        return f"Kolom '{value_col}' bevat geen getal-waarden.", None

    import pandas as pd
    df = pd.DataFrame(cleaned)

    # Use px.choropleth_map (Plotly 6 maplibre renderer) — more reliable than geo projection
    # featureidkey='id' matches against the top-level GeoJSON feature id (e.g. 'PV20')
    fig = px.choropleth_map(
        df,
        geojson=geojson,
        locations=location_col,
        color=value_col,
        featureidkey="id",
        center={"lat": 52.3, "lon": 5.3},
        zoom=6,
        map_style="white-bg",
        color_continuous_scale="Blues",
        title=title,
    )
    fig.update_layout(
        font=dict(family="Inter, Arial, sans-serif", size=13),
        paper_bgcolor="white",
        margin=dict(t=60, b=0, l=0, r=0),
        meta={
            "type": "choropleth",
            "geojson_url": _GEOJSON_URLS.get(detected, ""),
            "location_col": location_col,
            "value_col": value_col,
            "data": cleaned,
        },
    )

    level_labels = {"provincie": "provincies", "gemeente": "gemeenten", "corop": "COROP-gebieden"}
    return f"Kaart '{title}' aangemaakt ({len(cleaned)} {level_labels.get(detected, detected)}).", fig
