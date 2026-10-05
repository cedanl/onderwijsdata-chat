import json as _json
import logging
import math
import urllib.request

import plotly.express as px
import plotly.graph_objects as go

from . import duo, store

logger = logging.getLogger(__name__)

# Okabe-Ito colorblind-friendly palette
_PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
_HIGHLIGHT_GREY = "#B0B0B0"

# Boven dit aantal punten overlappen waardelabels elkaar (#22).
_MAX_LABELED_POINTS = 20

_CHART_TYPE_LABELS = {
    "bar": "Staafgrafiek",
    "line": "Lijngrafiek",
    "scatter": "Spreidingsdiagram",
    "pie": "Taartdiagram",
    "histogram": "Histogram",
}

_LAYOUT_BASE = {
    "font": {"family": "Inter, Arial, sans-serif", "size": 13},
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
    "margin": {"t": 60, "b": 50, "l": 70, "r": 20},
    "legend": {"bgcolor": "rgba(255,255,255,0.8)", "bordercolor": "#ddd", "borderwidth": 1},
}

_AXIS_STYLE = {"showgrid": True, "gridcolor": "#f0f0f0", "linecolor": "#ccc", "zeroline": False}

_TIME_KEYWORDS = {
    "JAAR",
    "STUDIEJAAR",
    "PERIODE",
    "PERIODEN",
    "MAAND",
    "KWARTAAL",
    "DATUM",
    "DATE",
    "YEAR",
    "MONTH",
}


def _is_time_axis(col_name: str) -> bool:
    """Detect if column represents time, ook als label (STUDIEJAAR_LABEL, Perioden_label; #240)."""
    return col_name.upper().removesuffix("_LABEL") in _TIME_KEYWORDS


def _infer_chart_type(
    x: str,
    y: str,
    color_by: str | None,
    num_groups: int = 1,
    is_share: bool = False,
) -> str:
    """Infer chart type from data structure and intent.

    Decision tree:
    - Multiple groups + time axis → line (trend comparison)
    - Time axis only → line (trend)
    - Shares/proportions → pie (if ≤5 groups) else bar
    - Many groups → bar (comparison)
    - Default → bar
    """
    has_color = color_by is not None
    is_time = _is_time_axis(x)

    # Trend: time axis with or without groups
    if is_time:
        return "line"

    # Shares: proportions should be pie (if small) or bar (if many)
    if is_share:
        return "pie" if num_groups <= 5 else "bar"

    # Multiple groups → bar (categorical comparison)
    if has_color and num_groups > 1:
        return "bar"

    # Default for single series
    return "bar"


def resolve_chart_type(
    data: list[dict],
    chart_type: str,
    x: str,
    y: str,
    color_by: str | None = None,
    is_share: bool = False,
) -> str:
    """Het type dat create_plot tekent; de snippet leest het hier ook, zodat ze niet uiteenlopen (#245)."""
    if chart_type != "auto":
        return chart_type
    num_groups = len({row.get(color_by) for row in data}) if color_by else 1
    return _infer_chart_type(x, y, color_by, num_groups, is_share)


_GEOJSON_URLS = {
    "provincie": "https://cartomap.github.io/nl/wgs84/provincie_2024.geojson",
    "gemeente": "https://cartomap.github.io/nl/wgs84/gemeente_2024.geojson",
    "corop": "https://cartomap.github.io/nl/wgs84/coropgebied_2024.geojson",
}
_GEOJSON_CACHE: dict[str, dict] = {}


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _validate_axes(data: list[dict], x: str, y: str) -> str | None:
    """None als x/y bruikbaar zijn; anders een toolmelding in plaats van een lege figuur (#216)."""
    available = {k for row in data for k in row}
    missing = [col for col in (x, y) if col not in available]
    if missing:
        return f"Kolom(men) {missing} niet gevonden. Beschikbaar: {sorted(available)}."

    y_vals = [row.get(y) for row in data]
    aanwezig = [v for v in y_vals if not _is_missing(v)]
    if not aanwezig:
        return f"Kolom '{y}' bevat geen waarden om te tekenen (alleen ontbrekende cellen, mogelijk een DUO-sentinel)."
    if any(isinstance(v, str) for v in aanwezig):
        return f"Kolom '{y}' bevat tekst, geen getallen: gebruik een numerieke kolom voor de y-as."
    return None


def _dutch_number(v: float) -> str:
    """30083 -> '30.083', 2.1 -> '2,1' — punt voor duizendtallen, komma voor decimalen."""
    text = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    # translate() vervangt alle tekens in één doorgang, dus een directe wissel is veilig;
    # een tussenteken (NUL) zou nooit worden teruggezet (#378).
    return text.translate(str.maketrans({",": ".", ".": ","}))


def _value_labels(y_vals: list, enabled: bool) -> list[str] | None:
    if not enabled or len(y_vals) > _MAX_LABELED_POINTS:
        return None
    return ["" if _is_missing(v) else _dutch_number(v) for v in y_vals]


def _group_by_color(data: list[dict], x: str, y: str, color_by: str) -> dict[str, dict]:
    """Group data rows by the *color_by* column."""
    groups: dict[str, dict] = {}
    for row in data:
        key = str(row.get(color_by, "onbekend"))
        groups.setdefault(key, {"x": [], "y": []})
        groups[key]["x"].append(row.get(x))
        groups[key]["y"].append(row.get(y))
    return groups


def _add_trace(
    fig: go.Figure,
    chart_type: str,
    x_vals: list,
    y_vals: list,
    color: str,
    name: str | None = None,
    text: list[str] | None = None,
) -> None:
    """Add a single trace to the figure based on *chart_type*."""
    common = {"name": name} if name else {}
    if chart_type == "bar":
        fig.add_trace(
            go.Bar(
                x=x_vals, y=y_vals, marker_color=color, text=text, textposition="outside" if text else None, **common
            )
        )
    elif chart_type == "line":
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers" + ("+text" if text else ""),
                text=text,
                textposition="top center",
                line={"color": color, "width": 2},
                marker={"size": 5},
                **common,
            )
        )
    elif chart_type == "scatter":
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="markers", marker={"color": color, "size": 7}, **common))
    elif chart_type == "histogram":
        fig.add_trace(go.Histogram(x=x_vals, marker_color=color, opacity=0.7 if name else 0.85, **common))
    elif chart_type == "pie" and not name:
        fig.add_trace(go.Pie(labels=x_vals, values=y_vals, marker={"colors": _PALETTE}, hole=0.3))


def create_plot(
    data: list[dict] | None = None,
    chart_type: str = "auto",
    x: str = "",
    y: str = "",
    title: str = "",
    color_by: str | None = None,
    highlight: str | None = None,
    data_key: str | None = None,
    is_share: bool = False,
) -> tuple[str, go.Figure | None]:
    if data_key:
        df = store.get(data_key)
        if df is None:
            return f"Geen data gevonden voor '{data_key}'.", None
        data = df.to_dict(orient="records")
        if duo.is_prognose(store.meta(data_key)):
            # Dezelfde afronding als in de tekst, zodat grafiek en CSV hele personen tonen (#328).
            data = [{k: duo.json_waarde(v, afronden=True) for k, v in row.items()} for row in data]
    elif data:
        # data staat niet meer in het tool-schema: alleen interne aanroepen
        # (zoals de replay in agent/replay.py) komen hier nog langs.
        logger.info("create_plot zonder data_key aangeroepen, %d rijen", len(data))
    if not data:
        return "Geen data opgegeven. Geef de data_key van een query_data-resultaat mee.", None
    if err := _validate_axes(data, x, y):
        return err, None
    if len(data) == 1 and chart_type != "bar":
        # One point shows nothing a sentence cannot; let the answer state the value.
        # An explicit bar is what the user asked for, so it is drawn (#199).
        value = data[0].get(y, "")
        return (
            f"Geen grafiek gemaakt: de data bevat één datapunt ({x}={data[0].get(x, '')}, {y}={value}). "
            "Noem de waarde in je antwoord."
        ), None

    chart_type = resolve_chart_type(data, chart_type, x, y, color_by, is_share)

    fig = go.Figure()
    show_labels = chart_type in ("bar", "line") and len(data) <= _MAX_LABELED_POINTS

    if color_by:
        groups = _group_by_color(data, x, y, color_by)
        for i, (name, vals) in enumerate(groups.items()):
            if highlight:
                color = _PALETTE[0] if name == highlight else _HIGHLIGHT_GREY
            else:
                color = _PALETTE[i % len(_PALETTE)]
            _add_trace(
                fig, chart_type, vals["x"], vals["y"], color, name=name, text=_value_labels(vals["y"], show_labels)
            )

        if chart_type == "bar":
            fig.update_layout(barmode="group")
        elif chart_type == "histogram":
            fig.update_layout(barmode="overlay")

    else:
        x_vals = [row.get(x) for row in data]
        y_vals = [row.get(y) for row in data]
        _add_trace(fig, chart_type, x_vals, y_vals, _PALETTE[0], text=_value_labels(y_vals, show_labels))

    layout = {
        "title": {"text": title, "font": {"size": 16, "color": "#222"}},
        "legend_title": color_by or "",
        "separators": ",.",  # Nederlandse notatie: punt voor duizendtallen, komma voor decimalen (#22)
        **_LAYOUT_BASE,
    }

    if chart_type != "pie":
        layout["xaxis"] = {"title": x, **_AXIS_STYLE}
        if _is_time_axis(x):
            # Jaartallen als categorie: geen 2.023,5-tussenticks met duizendtalpunt (#240).
            layout["xaxis"].update(type="category", categoryorder="category ascending")
        layout["yaxis"] = {"title": y, "tickformat": ",", **_AXIS_STYLE}

    fig.update_layout(**layout)
    fig.update_layout(
        meta={
            "data": data,
            "x": x,
            "y": y,
            "chart_type": chart_type,
            "color_by": color_by,
            "herkomst": store.herkomst(data_key) if data_key else [],
        }
    )

    chart_label = _CHART_TYPE_LABELS.get(chart_type, "Grafiek")
    return f"{chart_label} '{title}' aangemaakt ({len(data)} datapunten).", fig


def _axis_name(fig: go.Figure, axis: str, default: str) -> str:
    title = fig.layout[axis].title.text
    return title or default


def with_export_rows(fig: go.Figure) -> go.Figure:
    """Zet de getekende punten als rijen in layout.meta.data (#217).

    De CSV-export leest die rijen als de stabiele route; zonder vallen figuren uit
    run_analysis terug op de traces, waar Plotly arrays binair serialiseert.
    Een figuur waarvan x en y niet gelijk zijn, krijgt geen rijen: de export weigert
    hem dan met een reden in plaats van een CSV naast een kapotte grafiek.
    Bij een heatmap staan de waarden in z, niet in y: die krijgt een rij per cel.
    """
    if fig.layout.meta and fig.layout.meta.get("data"):
        return fig
    if any(getattr(t, "z", None) is not None for t in fig.data):
        if len(fig.data) == 1 and fig.data[0].type == "heatmap":
            fig.update_layout(meta={"data": _heatmap_rows(fig, fig.data[0])})
        return fig
    traces = [t for t in fig.data if getattr(t, "x", None) is not None and getattr(t, "y", None) is not None]
    if not traces or any(len(t.x) != len(t.y) or len(t.y) == 0 for t in traces):
        return fig

    x_name = _axis_name(fig, "xaxis", "categorie")
    y_name = _axis_name(fig, "yaxis", "waarde")
    grouped = len(traces) > 1
    rows = []
    for trace in traces:
        for x_val, y_val in zip(trace.x, trace.y, strict=True):
            row = {"reeks": trace.name or ""} if grouped else {}
            rows.append({**row, x_name: _plain(x_val), y_name: _plain(y_val)})
    fig.update_layout(meta={"data": rows, "x": x_name, "y": y_name})
    return fig


def _heatmap_rows(fig: go.Figure, trace) -> list[dict]:
    """Eén rij per cel: rij- en kolomlabel plus de waarde uit z. Zonder labels telt de positie."""
    rij_naam = _axis_name(fig, "yaxis", "rij")
    kolom_naam = _axis_name(fig, "xaxis", "kolom")
    rijen = list(trace.y) if trace.y is not None else None
    kolommen = list(trace.x) if trace.x is not None else None
    return [
        {
            rij_naam: _plain(rijen[i]) if rijen is not None else i,
            kolom_naam: _plain(kolommen[j]) if kolommen is not None else j,
            "waarde": _plain(waarde),
        }
        for i, rij in enumerate(trace.z)
        for j, waarde in enumerate(rij)
    ]


def _plain(value):
    """numpy-scalar naar gewone Python-waarde, NaN naar None."""
    if hasattr(value, "item"):
        value = value.item()
    return None if isinstance(value, float) and math.isnan(value) else value


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
) -> tuple[str, go.Figure | None]:
    if data_key:
        df = store.get(data_key)
        if df is None:
            return f"Geen data gevonden voor '{data_key}'.", None
        data = df.to_dict(orient="records")
        if duo.is_prognose(store.meta(data_key)):
            # Dezelfde afronding als in de tekst, zodat grafiek en CSV hele personen tonen (#328).
            data = [{k: duo.json_waarde(v, afronden=True) for k, v in row.items()} for row in data]
    elif data:
        logger.info("create_choropleth_map zonder data_key aangeroepen, %d rijen", len(data))
    if not data:
        return "Geen data om op kaart te tonen. Geef de data_key van een query_data-resultaat mee.", None

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
        for row in cleaned:
            float(row[value_col])
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
        font={"family": "Inter, Arial, sans-serif", "size": 13},
        paper_bgcolor="white",
        margin={"t": 60, "b": 0, "l": 0, "r": 0},
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
