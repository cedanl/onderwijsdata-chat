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

    return f"Grafiek '{title}' aangemaakt ({len(data)} datapunten).", fig
