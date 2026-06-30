import json as _json
import re
from datetime import date
import html as html_module

import markdown as md
import nh3
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


def _parse_data_calls(tool_calls: list) -> list[dict]:
    """Extract data-fetching tool calls with parsed arguments."""
    result = []
    for tc in (tool_calls or []):
        if tc.get("name") in ("get_cbs_data", "get_duo_data", "query_data", "get_rio_data"):
            try:
                args = _json.loads(tc.get("arguments") or "{}")
            except Exception:
                args = {}
            result.append({"name": tc["name"], "args": args})
    return result


def _figure_to_code(fig: go.Figure, source_hint: str = "", tool_calls: list | None = None) -> str:
    """Generate reproducible Python code using the actual source API calls from the session."""
    layout = fig.layout
    title_text = getattr(getattr(layout, "title", None), "text", None)
    meta = getattr(layout, "meta", None) or {}

    data_calls = _parse_data_calls(tool_calls)
    cbs_call = next((c for c in data_calls if c["name"] == "get_cbs_data"), None)
    duo_call = next((c for c in data_calls if c["name"] == "get_duo_data"), None)
    query_call = next((c for c in data_calls if c["name"] == "query_data"), None)

    lines: list[str] = []

    # ── Choropleth kaart ─────────────────────────────────────
    if meta.get("type") == "choropleth":
        geojson_url = meta.get("geojson_url", "")
        location_col = meta.get("location_col", "RegioS")
        value_col = meta.get("value_col", "waarde")

        if cbs_call:
            lines += ["from onderwijsdata import data as cbs_data", "import pandas as pd",
                      "import urllib.request, json", "import plotly.express as px", ""]
        else:
            lines += ["import pandas as pd", "import urllib.request, json", "import plotly.express as px", ""]

        if cbs_call:
            dataset_id = cbs_call["args"].get("dataset_id", "")
            filters = {k: v for k, v in (cbs_call["args"].get("filters") or {}).items()
                       if not k.startswith("$top")}
            lines.append(f"# CBS {dataset_id}")
            if filters:
                lines += [f"df = pd.DataFrame(cbs_data(", f"    {dataset_id!r},",
                          f"    **{filters!r},", "))", ""]
            else:
                lines += [f"df = pd.DataFrame(cbs_data({dataset_id!r}))", ""]
        else:
            if source_hint:
                lines += [f"# Bron: {source_hint}", ""]
            lines += ["# Haal data op via de bron (zie sessie voor exacte parameters)", "df = ...  # vul aan", ""]

        if geojson_url:
            lines += [f'with urllib.request.urlopen("{geojson_url}") as _r:',
                      "    geojson = json.loads(_r.read())", ""]

        kw = [f"    df, geojson=geojson", f"    locations={location_col!r}",
              f"    color={value_col!r}", "    featureidkey='id'",
              '    center={"lat": 52.3, "lon": 5.3}', "    zoom=6",
              '    map_style="white-bg"', "    color_continuous_scale='Blues'"]
        if title_text:
            kw.append(f"    title={title_text!r}")
        lines += ["fig = px.choropleth_map("] + [k + "," for k in kw] + [")"]
        lines.append("fig.show()")
        return "\n".join(lines)

    # ── Reguliere grafiek ────────────────────────────────────
    x_col = meta.get("x", "x")
    y_col = meta.get("y", "y")
    chart_type = meta.get("chart_type", "line")
    color_by = meta.get("color_by")
    barmode = getattr(layout, "barmode", None)

    px_map = {"bar": "px.bar", "line": "px.line", "scatter": "px.scatter",
              "pie": "px.pie", "histogram": "px.histogram"}
    px_func = px_map.get(chart_type, "px.line")

    # Imports
    if cbs_call:
        lines += ["from onderwijsdata import data as cbs_data", "import pandas as pd",
                  "import plotly.express as px", ""]
    elif duo_call:
        lines += ["from riodata.duo import load as duo_load", "import pandas as pd",
                  "import plotly.express as px", ""]
    else:
        lines += ["import pandas as pd", "import plotly.express as px", ""]

    # Data fetch
    if cbs_call:
        dataset_id = cbs_call["args"].get("dataset_id", "")
        filters = {k: v for k, v in (cbs_call["args"].get("filters") or {}).items()
                   if not k.startswith("$top")}
        lines.append(f"# CBS {dataset_id}")
        if filters:
            lines += [f"df = pd.DataFrame(cbs_data(", f"    {dataset_id!r},",
                      f"    **{filters!r},", "))", ""]
        else:
            lines += [f"df = pd.DataFrame(cbs_data({dataset_id!r}))", ""]

    elif duo_call:
        dataset_id = duo_call["args"].get("dataset_id", "")
        resource = duo_call["args"].get("resource", 0)
        lines.append(f"# DUO: {dataset_id}")
        if resource and resource != 0:
            lines += [f"df = duo_load({dataset_id!r}, resource={resource!r})", ""]
        else:
            lines += [f"df = duo_load({dataset_id!r})", ""]

        if query_call:
            filters = query_call["args"].get("filters") or {}
            columns = query_call["args"].get("columns")
            if filters:
                parts = [f"(df[{col!r}].astype(str) == {str(val)!r})" for col, val in filters.items()]
                mask = " & ".join(parts)
                lines.append(f"df = df[{mask}]")
            if columns:
                lines.append(f"df = df[{columns!r}]")
            if filters or columns:
                lines.append("")

    else:
        if source_hint:
            lines += [f"# Bron: {source_hint}", ""]
        lines += ["# Haal data op via de bron (zie sessie voor exacte parameters)", "df = ...  # vul aan", ""]

    # Plot
    if chart_type == "pie":
        kw = [f"df", f"names={x_col!r}", f"values={y_col!r}"]
    elif chart_type == "histogram":
        kw = [f"df", f"x={x_col!r}"]
    else:
        kw = [f"df", f"x={x_col!r}", f"y={y_col!r}"]

    if color_by:
        kw.append(f"color={color_by!r}")
    if barmode == "stack":
        kw.append('barmode="stack"')
    if title_text:
        kw.append(f"title={title_text!r}")

    if len(kw) <= 4:
        lines.append(f"fig = {px_func}({', '.join(kw)})")
    else:
        lines += [f"fig = {px_func}("] + [f"    {k}," for k in kw] + [")"]

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
    narrative_html = nh3.clean(md.markdown(meta.get("narrative") or "", extensions=["nl2br"]))
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
            code = _figure_to_code(fig, source_hint, turn.get("tool_calls") or [])
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
