import plotly.graph_objects as go


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
            if key not in groups:
                groups[key] = {"x": [], "y": []}
            groups[key]["x"].append(row.get(x))
            groups[key]["y"].append(row.get(y))

        for name, vals in groups.items():
            if chart_type == "bar":
                fig.add_trace(go.Bar(name=name, x=vals["x"], y=vals["y"]))
            elif chart_type == "line":
                fig.add_trace(go.Scatter(name=name, x=vals["x"], y=vals["y"], mode="lines+markers"))
            elif chart_type == "scatter":
                fig.add_trace(go.Scatter(name=name, x=vals["x"], y=vals["y"], mode="markers"))

        if chart_type == "bar":
            fig.update_layout(barmode="group")

    else:
        x_vals = [row.get(x) for row in data]
        y_vals = [row.get(y) for row in data]

        if chart_type == "bar":
            fig.add_trace(go.Bar(x=x_vals, y=y_vals))
        elif chart_type == "line":
            fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines+markers"))
        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="markers"))
        elif chart_type == "pie":
            fig.add_trace(go.Pie(labels=x_vals, values=y_vals))

    if chart_type != "pie":
        fig.update_layout(xaxis_title=x, yaxis_title=y)

    fig.update_layout(title=title, legend_title=color_by or "")

    return f"Grafiek '{title}' aangemaakt ({len(data)} datapunten).", fig
