import json as _json
import re
from datetime import date
import html as html_module

import markdown as md
import plotly.graph_objects as go
import plotly.io as pio


def _source_hint_from_turn(turn: dict) -> str:
    """Extract dataset IDs from a turn's tool calls and answer text."""
    sources: list[str] = []
    for tc in (turn.get("tool_calls") or []):
        try:
            args = _json.loads(tc.get("arguments") or "{}")
        except Exception:
            args = {}
        for key in ("dataset_id", "table_id", "bron", "source"):
            if key in args and isinstance(args[key], str) and args[key] not in sources:
                sources.append(args[key])
                break
    for ref in re.findall(r"\b\d{5}[A-Z]{3}\b", turn.get("answer") or ""):
        if ref not in sources:
            sources.append(ref)
    return ", ".join(sources)


def _figure_to_code(fig: go.Figure, source_hint: str = "") -> str:
    """Generate self-contained reproducible Python code from a Plotly figure."""

    def _to_py(val):
        if hasattr(val, "item"):
            return val.item()
        if hasattr(val, "tolist"):
            return val.tolist()
        return val

    lines = ["import plotly.graph_objects as go"]
    if source_hint:
        lines += ["", f"# Bron: {source_hint}"]
    lines.append("")

    layout = fig.layout
    title_text = getattr(getattr(layout, "title", None), "text", None)
    barmode = getattr(layout, "barmode", None)

    meta = getattr(layout, "meta", None)
    if isinstance(meta, dict) and meta.get("data"):
        # Structured path: use original data + column names stored at create_plot time
        raw_data = meta["data"]
        x_col = meta.get("x", "x")
        y_col = meta.get("y", "y")
        chart_type = meta.get("chart_type", "line")
        color_by = meta.get("color_by")

        clean_data = [{k: _to_py(v) for k, v in row.items()} for row in raw_data]

        lines.append("data = [")
        for row in clean_data:
            lines.append(f"    {row!r},")
        lines.append("]")
        lines.append("")
        lines.append(f"x_col = {x_col!r}")
        lines.append(f"y_col = {y_col!r}")
        if color_by:
            lines.append(f"color_col = {color_by!r}")
        lines.append("")

        if color_by:
            lines.append("fig = go.Figure()")
            lines.append("for group in sorted(set(row[color_col] for row in data)):")
            lines.append("    rows = [row for row in data if row[color_col] == group]")
            if chart_type == "bar":
                lines.append("    fig.add_trace(go.Bar(name=group, x=[r[x_col] for r in rows], y=[r[y_col] for r in rows]))")
            elif chart_type == "histogram":
                lines.append("    fig.add_trace(go.Histogram(name=group, x=[r[x_col] for r in rows]))")
            else:
                mode = "lines+markers" if chart_type == "line" else "markers"
                lines.append(f"    fig.add_trace(go.Scatter(name=group, x=[r[x_col] for r in rows], y=[r[y_col] for r in rows], mode={mode!r}))")
        elif chart_type == "pie":
            lines += [
                "fig = go.Figure(data=[go.Pie(",
                "    labels=[row[x_col] for row in data],",
                "    values=[row[y_col] for row in data],",
                ")])",
            ]
        elif chart_type == "histogram":
            lines.append("fig = go.Figure(data=[go.Histogram(x=[row[x_col] for row in data])])")
        elif chart_type == "bar":
            lines += [
                "fig = go.Figure(data=[go.Bar(",
                "    x=[row[x_col] for row in data],",
                "    y=[row[y_col] for row in data],",
                ")])",
            ]
        else:
            mode = "lines+markers" if chart_type == "line" else "markers"
            lines += [
                "fig = go.Figure(data=[go.Scatter(",
                "    x=[row[x_col] for row in data],",
                "    y=[row[y_col] for row in data],",
                f"    mode={mode!r},",
                ")])",
            ]

        lu: list[str] = []
        if title_text:
            lu.append(f"title={title_text!r}")
        if chart_type != "pie":
            lu.append("xaxis_title=x_col")
            lu.append("yaxis_title=y_col")
        if barmode and barmode not in ("", "overlay"):
            lu.append(f"barmode={barmode!r}")
        if lu:
            lines.append("fig.update_layout(")
            for item in lu:
                lines.append(f"    {item},")
            lines.append(")")

    else:
        # Fallback: reconstruct from figure traces (choropleth or legacy figures)
        def _arr(seq) -> list:
            return [_to_py(v) for v in seq] if seq is not None else []

        all_xs = [_arr(getattr(t, "x", None)) for t in fig.data if getattr(t, "x", None) is not None]
        shared_x = all_xs[0] if all_xs and all(a == all_xs[0] for a in all_xs) else None

        if shared_x:
            lines.append(f"x = {shared_x!r}")
            lines.append("")

        trace_strs: list[str] = []
        for t in fig.data:
            ttype = t.type
            kw: list[str] = []

            name = getattr(t, "name", None)
            if name:
                kw.append(f"name={name!r}")

            if ttype == "pie":
                vals = _arr(getattr(t, "values", None))
                lbls = _arr(getattr(t, "labels", None))
                if vals:
                    kw.append(f"values={vals!r}")
                if lbls:
                    kw.append(f"labels={lbls!r}")
            else:
                if shared_x:
                    kw.append("x=x")
                else:
                    xs = _arr(getattr(t, "x", None))
                    if xs:
                        kw.append(f"x={xs!r}")
                ys = _arr(getattr(t, "y", None))
                if ys:
                    kw.append(f"y={ys!r}")

            mode = getattr(t, "mode", None)
            if mode:
                kw.append(f"mode={mode!r}")

            line_obj = getattr(t, "line", None)
            line_color = getattr(line_obj, "color", None) if line_obj else None
            if isinstance(line_color, str):
                kw.append(f"line=dict(color={line_color!r})")

            marker_obj = getattr(t, "marker", None)
            marker_color = getattr(marker_obj, "color", None) if marker_obj else None
            if isinstance(marker_color, str) and not line_color:
                kw.append(f"marker_color={marker_color!r}")

            cls = {
                "scatter": "go.Scatter", "bar": "go.Bar", "pie": "go.Pie",
                "histogram": "go.Histogram", "choropleth": "go.Choropleth",
            }.get(ttype, "go.Scatter")

            if len(kw) <= 3:
                trace_strs.append(f"    {cls}({', '.join(kw)}),")
            else:
                pad = "        "
                trace_strs.append(f"    {cls}(\n{pad}{(','+chr(10)+pad).join(kw)},\n    ),")

        lines.append("fig = go.Figure(data=[")
        lines.extend(trace_strs)
        lines.append("])")

        lu: list[str] = []
        if title_text:
            lu.append(f"title={title_text!r}")
        xtitle = getattr(getattr(getattr(layout, "xaxis", None), "title", None), "text", None)
        if xtitle:
            lu.append(f"xaxis_title={xtitle!r}")
        ytitle = getattr(getattr(getattr(layout, "yaxis", None), "title", None), "text", None)
        if ytitle:
            lu.append(f"yaxis_title={ytitle!r}")
        if barmode and barmode != "overlay":
            lu.append(f"barmode={barmode!r}")

        if lu:
            if len(lu) == 1:
                lines.append(f"fig.update_layout({lu[0]})")
            else:
                lines.append("fig.update_layout(")
                for item in lu:
                    lines.append(f"    {item},")
                lines.append(")")

    lines.append("fig.show()")
    return "\n".join(lines)


def generate_dashboard(turns: list[dict], meta: dict, selected: list[int] | None = None) -> str:
    """
    Standalone interactive HTML dashboard.
    Embeds Plotly figures via pio.to_html and uses Plotly.restyle to toggle
    trace visibility — no data reconstruction, no empty charts.
    Includes a collapsible code block under each chart.
    """
    if selected is None:
        selected = list(range(len(turns)))
    selected = [i for i in selected if 0 <= i < len(turns)] or list(range(len(turns)))

    title = html_module.escape(meta.get("title") or "Dashboard")
    narrative_html = md.markdown(meta.get("narrative") or "", extensions=["nl2br"])
    findings: list[str] = meta.get("key_findings") or []

    charts: list[dict] = []
    first_plotly_js = True
    for idx in selected:
        turn = turns[idx]
        source_hint = _source_hint_from_turn(turn)
        for j, fig in enumerate((turn.get("figures") or [])):
            cid = f"chart-{idx}-{j}"
            trace_names = [getattr(t, "name", None) or "" for t in fig.data]
            fig_html = pio.to_html(
                fig,
                include_plotlyjs="cdn" if first_plotly_js else False,
                full_html=False,
                div_id=cid,
            )
            first_plotly_js = False
            code = _figure_to_code(fig, source_hint)
            code_block = (
                '<details class="code-details">'
                "<summary>Reproduceerbare code</summary>"
                f"<pre><code>{html_module.escape(code)}</code></pre>"
                "</details>"
            )
            charts.append({"id": cid, "html": fig_html, "trace_names": trace_names, "code": code_block})

    # trace_map: name → [{id, ti}] — only for charts with multiple named traces
    trace_map: dict[str, list[dict]] = {}
    for chart in charts:
        names = chart["trace_names"]
        if len(names) < 2:
            continue
        for i, name in enumerate(names):
            if name:
                trace_map.setdefault(name, []).append({"id": chart["id"], "ti": i})

    filter_panel_html = ""
    if trace_map:
        pills = "".join(
            f'<button class="pill active" data-trace="{html_module.escape(n)}">{html_module.escape(n)}</button>'
            for n in trace_map
        )
        filter_panel_html = (
            f'<div class="pills">{pills}</div>'
            '<div class="filter-btns">'
            '<button id="all-btn" class="filter-btn">Alles</button>'
            '<button id="none-btn" class="filter-btn">Niets</button>'
            "</div>"
        )

    # Collect unique dataset sources across all selected turns
    all_sources: list[str] = []
    for idx in selected:
        for src in _source_hint_from_turn(turns[idx]).split(", "):
            if src and src not in all_sources:
                all_sources.append(src)

    sources_html = ""
    if all_sources:
        items = "".join(f"<li><code>{html_module.escape(s)}</code></li>" for s in all_sources)
        sources_html = f'<div class="sources"><h2>Bronnen</h2><ul>{items}</ul></div>'

    findings_html = ""
    if findings:
        items = "".join(f"<li>{html_module.escape(f)}</li>" for f in findings)
        findings_html = f'<section class="findings"><h3>Kernbevindingen</h3><ul>{items}</ul></section>'

    chart_grid_html = "".join(
        f'<div class="chart-card">{c["html"]}{c["code"]}</div>' for c in charts
    )

    sidebar_style = "" if (trace_map or all_sources) else "display:none"
    trace_map_json = _json.dumps(trace_map, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #f4f6fb; color: #1a1a2e; }}
#header {{ background: #fff; border-bottom: 3px solid #4a6cf7; padding: 1.25rem 1.75rem; }}
#header h1 {{ font-size: 1.4rem; }}
#header .meta {{ color: #666; font-size: .8rem; margin-top: .2rem; }}
#body {{ display: flex; min-height: calc(100vh - 64px); }}
#sidebar {{ width: 200px; flex-shrink: 0; background: #fff; border-right: 1px solid #e4e8f8;
           padding: 1.25rem 1rem; display: flex; flex-direction: column; gap: 1rem; {sidebar_style} }}
#sidebar h2 {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; color: #888; }}
.pills {{ display: flex; flex-direction: column; gap: .3rem; }}
.pill {{ padding: .3rem .65rem; border-radius: 20px; border: 1.5px solid #c7d2fe; background: #f0f4ff;
         color: #4a6cf7; cursor: pointer; font-size: .8rem; text-align: left;
         transition: background .12s, color .12s; }}
.pill.active {{ background: #4a6cf7; color: #fff; border-color: #4a6cf7; }}
.pill:hover:not(.active) {{ background: #e0e7ff; }}
.filter-btns {{ display: flex; gap: .4rem; margin-top: auto; }}
.filter-btn {{ flex: 1; padding: .35rem; background: #f0f4ff; border: 1px solid #c7d2fe;
               border-radius: 6px; font-size: .75rem; color: #4a6cf7; cursor: pointer; }}
.filter-btn:hover {{ background: #e0e7ff; }}
.sources ul {{ list-style: none; padding: 0; display: flex; flex-direction: column; gap: .25rem; }}
.sources li code {{ font-size: .75rem; color: #555; background: #f0f4ff; padding: .15rem .45rem;
                    border-radius: 4px; font-family: "Fira Code", Consolas, monospace; }}
#main {{ flex: 1; padding: 1.25rem; display: flex; flex-direction: column; gap: 1.25rem; min-width: 0; }}
.narrative {{ background: #fff; border-left: 4px solid #4a6cf7; padding: 1rem 1.25rem;
              border-radius: 4px; font-size: .9rem; line-height: 1.65; }}
.narrative p {{ margin: .4rem 0; }}
.findings {{ background: #fff; border-radius: 8px; padding: 1rem 1.25rem; }}
.findings h3 {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: #4a6cf7; margin-bottom: .5rem; }}
.findings ul {{ padding-left: 1.2rem; }}
.findings li {{ font-size: .875rem; margin: .3rem 0; line-height: 1.5; }}
.chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 1.25rem; }}
.chart-card {{ background: #fff; border-radius: 10px; padding: .75rem;
               box-shadow: 0 1px 4px rgba(0,0,0,.06); min-width: 0; }}
.chart-card .plotly-graph-div {{ width: 100% !important; }}
.code-details {{ margin-top: .5rem; border-top: 1px solid #f0f0f8; padding-top: .25rem; }}
.code-details > summary {{ font-size: .75rem; color: #bbb; cursor: pointer; padding: .3rem 0;
                            user-select: none; list-style: none; }}
.code-details > summary::-webkit-details-marker {{ display: none; }}
.code-details > summary::before {{ content: "▶ "; font-size: .65rem; }}
.code-details[open] > summary::before {{ content: "▼ "; }}
.code-details > summary:hover {{ color: #4a6cf7; }}
.code-details pre {{ margin: .5rem 0 0; padding: .875rem 1rem; background: #1e1e2e; color: #cdd6f4;
                     border-radius: 6px; font-size: .72rem; line-height: 1.55; overflow-x: auto;
                     font-family: "Fira Code", "Cascadia Code", Consolas, monospace; }}
</style>
</head>
<body>
<div id="header">
  <h1>{title}</h1>
  <div class="meta">Gegenereerd op {date.today().strftime("%-d %B %Y")} · onderwijsdata-chat</div>
</div>
<div id="body">
  <nav id="sidebar">
    {f'<h2>Filters</h2>{filter_panel_html}' if filter_panel_html else ""}
    {sources_html}
  </nav>
  <div id="main">
    {f'<div class="narrative">{narrative_html}</div>' if narrative_html else ""}
    {findings_html}
    <div class="chart-grid">{chart_grid_html}</div>
  </div>
</div>
<script>
const TRACE_MAP = {trace_map_json};

document.querySelectorAll('.pill').forEach(btn => {{
  btn.addEventListener('click', () => {{
    btn.classList.toggle('active');
    const entries = TRACE_MAP[btn.dataset.trace] || [];
    const vis = btn.classList.contains('active') ? true : 'legendonly';
    entries.forEach(e => Plotly.restyle(e.id, {{visible: vis}}, [e.ti]));
  }});
}});

document.getElementById('all-btn')?.addEventListener('click', () => {{
  document.querySelectorAll('.pill').forEach(btn => btn.classList.add('active'));
  Object.values(TRACE_MAP).flat().forEach(e => Plotly.restyle(e.id, {{visible: true}}, [e.ti]));
}});

document.getElementById('none-btn')?.addEventListener('click', () => {{
  document.querySelectorAll('.pill').forEach(btn => btn.classList.remove('active'));
  Object.values(TRACE_MAP).flat().forEach(e => Plotly.restyle(e.id, {{visible: 'legendonly'}}, [e.ti]));
}});
</script>
</body>
</html>"""
