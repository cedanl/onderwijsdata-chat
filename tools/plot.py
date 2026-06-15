import json as _json
import urllib.request

import plotly.graph_objects as go

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


def create_plot(
    data: list[dict],
    chart_type: str,
    x: str,
    y: str,
    title: str,
    color_by: str | None = None,
) -> tuple[str, go.Figure]:
    fig = go.Figure()

    if color_by:
        groups: dict[str, dict] = {}
        for row in data:
            key = str(row.get(color_by, "onbekend"))
            groups.setdefault(key, {"x": [], "y": []})
            groups[key]["x"].append(row.get(x))
            groups[key]["y"].append(row.get(y))

        for i, (name, vals) in enumerate(groups.items()):
            color = _PALETTE[i % len(_PALETTE)]
            if chart_type == "bar":
                fig.add_trace(go.Bar(name=name, x=vals["x"], y=vals["y"], marker_color=color))
            elif chart_type == "line":
                fig.add_trace(go.Scatter(name=name, x=vals["x"], y=vals["y"], mode="lines+markers",
                                         line=dict(color=color, width=2), marker=dict(size=5)))
            elif chart_type == "scatter":
                fig.add_trace(go.Scatter(name=name, x=vals["x"], y=vals["y"], mode="markers",
                                         marker=dict(color=color, size=7)))
            elif chart_type == "histogram":
                fig.add_trace(go.Histogram(name=name, x=vals["x"], marker_color=color, opacity=0.7))

        if chart_type == "bar":
            fig.update_layout(barmode="group")
        elif chart_type == "histogram":
            fig.update_layout(barmode="overlay")

    else:
        x_vals = [row.get(x) for row in data]
        y_vals = [row.get(y) for row in data]
        color = _PALETTE[0]

        if chart_type == "bar":
            fig.add_trace(go.Bar(x=x_vals, y=y_vals, marker_color=color))
        elif chart_type == "line":
            fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines+markers",
                                     line=dict(color=color, width=2), marker=dict(size=5)))
        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="markers",
                                     marker=dict(color=color, size=7)))
        elif chart_type == "pie":
            fig.add_trace(go.Pie(labels=x_vals, values=y_vals,
                                 marker=dict(colors=_PALETTE), hole=0.3))
        elif chart_type == "histogram":
            fig.add_trace(go.Histogram(x=x_vals, marker_color=color, opacity=0.85))

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
    data: list[dict],
    location_col: str,
    value_col: str,
    title: str,
    level: str = "auto",
) -> tuple[str, go.Figure]:
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

    fig = go.Figure(go.Choropleth(
        geojson=geojson,
        locations=codes,
        z=values,
        locationmode="geojson-id",
        featureidkey="properties.statcode",
        colorscale="Blues",
        marker_line_color="white",
        marker_line_width=0.5,
        colorbar=dict(title=dict(text=value_col, side="right"), thickness=12, len=0.6),
    ))

    # Expliciete NL-bounds zijn betrouwbaarder dan fitbounds voor custom GeoJSON
    fig.update_geos(
        visible=False,
        lonaxis_range=[3.2, 7.3],
        lataxis_range=[50.7, 53.6],
        projection_type="mercator",
    )

    level_labels = {"provincie": "provincies", "gemeente": "gemeenten", "corop": "COROP-gebieden"}
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#222")),
        margin=dict(t=60, b=20, l=0, r=0),
        paper_bgcolor="white",
        font=dict(family="Inter, Arial, sans-serif", size=13),
        geo=dict(bgcolor="rgba(0,0,0,0)"),
    )

    return f"Kaart '{title}' aangemaakt ({len(cleaned)} {level_labels.get(detected, detected)}).", fig
