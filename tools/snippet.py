"""Genereer reproduceerbare Python-snippets uit tool calls.

Een snippet moet buiten de app draaien met alleen de gedocumenteerde pakketten
(pandas, plotly, onderwijsdata, riodata): `store` bestaat daar niet (#131). Elke
snippet begint daarom met de laadstap van zijn bron, uit de laadaanroep die de
store bij de key bewaart.
"""

import json

from core.config import RIO_PAGE_SIZE

from . import store
from .schemas import (
    TOOL_COMPUTE_KPI,
    TOOL_CREATE_CHOROPLETH_MAP,
    TOOL_CREATE_PLOT,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
)

# Meer rijen dan dit gaan niet als literal de snippet in; zie _afgeleide_regels.
_MAX_INLINE_RIJEN = 200


def _lit(value) -> str:
    """Een literal in dubbele aanhalingstekens voor tekst, repr voor de rest."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, str) else repr(value)


def _duo_laadregels(args: dict) -> list[str]:
    return ["from riodata import duo", "",
            f"df = duo.load({_lit(args['dataset_id'])}, {_lit(args.get('resource', 0))})"]


def _cbs_laadregels(args: dict) -> list[str]:
    filters = args.get("filters") or {}
    extra = f", **{filters!r}" if filters else ""
    return ["import pandas as pd", "from onderwijsdata import data", "",
            f"df = pd.DataFrame(data({_lit(args['dataset_id'])}{extra}))"]


def _rio_laadregels(args: dict) -> list[str]:
    params = {**(args.get("filters") or {}), "page": 0, "pageSize": RIO_PAGE_SIZE}
    return ["import pandas as pd", "from riodata import fetch", "",
            f"df = pd.DataFrame(fetch({_lit(args['resource'])}, **{params!r}))"]


_LAADREGELS = {"get_duo_data": _duo_laadregels, "get_cbs_data": _cbs_laadregels, "get_rio_data": _rio_laadregels}


def _bron_van_key(data_key: str) -> tuple[str, dict] | None:
    """De laadaanroep voor een key zonder bewaarde metadata, als de key hem ondubbelzinnig bevat."""
    soort, _, rest = data_key.partition(":")
    if soort == "duo" and rest.count(":") >= 1:
        dataset_id, resource = rest.split(":", 1)
        return "get_duo_data", {"dataset_id": dataset_id, "resource": resource}
    if soort == "cbs" and rest and ":" not in rest:
        return "get_cbs_data", {"dataset_id": rest}
    if soort == "rio" and rest and ":" not in rest:
        return "get_rio_data", {"resource": rest}
    return None


def _afgeleide_regels(data_key: str) -> list[str]:
    """Een selectie of analyse-uitkomst: klein genoeg dan als rijen, anders de bron plus een NB."""
    df = store.get(data_key)
    if df is not None and len(df) <= _MAX_INLINE_RIJEN:
        records = json.loads(df.to_json(orient="records", force_ascii=False))
        return ["import pandas as pd", "", f"df = pd.DataFrame({records!r})  # uitkomst van een eerdere stap"]
    return []


def _laadregels(data_key: str) -> list[str]:
    """Regels die `df` zetten voor een key, zonder `store`."""
    known = store.meta(data_key)
    if known and known.afgeleid_van:
        if inline := _afgeleide_regels(data_key):
            return inline
        root = data_key
        while (parent := store.meta(root)) and parent.afgeleid_van:
            root = parent.afgeleid_van
        return [*_laadregels(root), "# NB: de grafiek of berekening gebruikt hier een selectie van deze data (eerdere stappen)."]
    laad = known.laad if known and known.laad else _bron_van_key(data_key)
    if laad:
        return _LAADREGELS[laad[0]](laad[1])
    return ["import pandas as pd", "", f"# Geen laadstap bekend voor {data_key!r}: laad de data met de tool waarmee hij is opgehaald.",
            "df = pd.DataFrame()"]


def _query_data_snippet(args: dict) -> str:
    lines = _laadregels(args.get("data_key", ""))

    filters = args.get("filters")
    if filters:
        for key, val in filters.items():
            if "__" in key:
                col, op = key.rsplit("__", 1)
                if op == "gte":
                    lines.append(f'df = df[df["{col}"] >= {val!r}]')
                elif op == "lte":
                    lines.append(f'df = df[df["{col}"] <= {val!r}]')
                elif op == "in":
                    lines.append(f'df = df[df["{col}"].isin({val!r})]')
            elif isinstance(val, list):
                lines.append(f'df = df[df["{key}"].isin({val!r})]')
            else:
                lines.append(f'df = df[df["{key}"] == {val!r}]')

    columns = args.get("columns")
    if columns:
        lines.append(f"df = df[{columns!r}]")

    group_by = args.get("group_by")
    aggregate = args.get("aggregate")
    if group_by and aggregate:
        lines.append(f"df = df.groupby({group_by!r}).agg({aggregate!r}).reset_index()")

    lines.append("print(df)")
    return "\n".join(lines)


_KPI_EXPRESSIES = {
    "last": "s.iloc[-1]",
    "first": "s.iloc[0]",
    "sum": "s.sum()",
    "mean": "s.mean()",
    "min": "s.min()",
    "max": "s.max()",
    "delta": "s.iloc[-1] - s.iloc[0]",
    "pct_change": "(s.iloc[-1] / s.iloc[0] - 1) * 100",
    "index": "s.iloc[-1] / s.iloc[0] * 100",
}


def _compute_kpi_snippet(args: dict) -> str:
    """Maak de KPI-berekening reproduceerbaar, zodat de gebruiker het getal kan narekenen."""
    metric = args.get("metric", "")
    expressie = _KPI_EXPRESSIES.get(metric)
    if expressie is None:
        return ""
    value_column = args.get("value_column", "")
    sort_column = args.get("sort_column")
    label = args.get("label", "")

    lines = [f'# KPI: {label} ({metric})']
    if sort_column:
        lines.append(f"df = df.sort_values({sort_column!r})")
    lines.append(f's = pd.to_numeric(df[{value_column!r}], errors="coerce").dropna()')
    lines.append(f"kpi = {expressie}")
    lines.append("print(kpi)")
    return "\n".join(lines)


def _run_analysis_snippet(args: dict) -> str:
    code = args.get("code", "")
    data_key = args.get("data_key")
    if not data_key:
        return code
    # De sandbox geeft np, px en go kant-en-klaar; buiten de app moeten ze geïmporteerd worden.
    imports = ["import numpy as np", "import plotly.express as px", "import plotly.graph_objects as go"]
    return "\n".join([*_laadregels(data_key), *imports, "", code])


def _get_duo_data_snippet(args: dict) -> str:
    return "\n".join([*_duo_laadregels(args), "print(df)"])


def _get_cbs_data_snippet(args: dict) -> str:
    return "\n".join([*_cbs_laadregels(args), "print(df)"])


def _get_rio_data_snippet(args: dict) -> str:
    return "\n".join([*_rio_laadregels(args), "print(df)"])


def _frame_regels(args: dict, data_key: str | None) -> list[str]:
    """Laadstap plus plotly-import voor een grafiek: uit de key, of uit de meegegeven rijen."""
    if data_key:
        regels = _laadregels(data_key)
    else:
        regels = ["import pandas as pd", "", f"df = pd.DataFrame({args.get('data', [])!r})"]
    return [*regels, "import plotly.express as px", ""]


def _create_plot_snippet(args: dict) -> str:
    chart_type = args.get("chart_type", "bar")
    x = args.get("x", "x")
    y = args.get("y", "y")
    title = args.get("title", "")
    color_by = args.get("color_by")
    data_key = args.get("data_key")

    lines = _frame_regels(args, data_key)

    px_func = {"bar": "px.bar", "line": "px.line", "scatter": "px.scatter"}.get(chart_type, "px.bar")
    color_arg = f', color="{color_by}"' if color_by else ""
    lines.append(f'fig = {px_func}(df, x="{x}", y="{y}", title="{title}"{color_arg})')
    lines.append("fig.show()")
    return "\n".join(lines)


def _create_choropleth_snippet(args: dict) -> str:
    location_col = args.get("location_col", "")
    value_col = args.get("value_col", "")
    title = args.get("title", "")
    data_key = args.get("data_key")

    lines = _frame_regels(args, data_key)

    lines.append(f'fig = px.choropleth_map(df, locations="{location_col}", color="{value_col}", title="{title}")')
    lines.append("fig.show()")
    return "\n".join(lines)


_GENERATORS = {
    TOOL_QUERY_DATA: _query_data_snippet,
    TOOL_RUN_ANALYSIS: _run_analysis_snippet,
    TOOL_COMPUTE_KPI: _compute_kpi_snippet,
    TOOL_GET_DUO_DATA: _get_duo_data_snippet,
    TOOL_GET_RIO_DATA: _get_rio_data_snippet,
    TOOL_GET_CBS_DATA: _get_cbs_data_snippet,
    TOOL_CREATE_PLOT: _create_plot_snippet,
    TOOL_CREATE_CHOROPLETH_MAP: _create_choropleth_snippet,
}


def generate(tool_name: str, args: dict) -> str | None:
    gen = _GENERATORS.get(tool_name)
    if gen is None:
        return None
    return gen(args)
