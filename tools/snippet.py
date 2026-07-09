"""Genereer reproduceerbare Python-snippets uit tool calls."""


def _query_data_snippet(args: dict) -> str:
    data_key = args.get("data_key", "")
    parts = data_key.split(":", 2)

    if parts[0] == "duo" and len(parts) == 3:
        load_line = f'df = duo.load("{parts[1]}", "{parts[2]}")'
        imports = "from riodata import duo"
    elif parts[0] == "cbs" and len(parts) >= 2:
        load_line = f'df = store.get("{data_key}")  # eerder geladen via get_cbs_data'
        imports = "# CBS data al geladen in store"
    elif parts[0] == "rio" and len(parts) >= 2:
        load_line = f'df = store.get("{data_key}")  # eerder geladen via get_rio_data'
        imports = "# RIO data al geladen in store"
    else:
        load_line = f'df = store.get("{data_key}")'
        imports = ""

    lines = [imports, "", load_line]

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


def _run_analysis_snippet(args: dict) -> str:
    return args.get("code", "")


def _get_duo_data_snippet(args: dict) -> str:
    dataset_id = args["dataset_id"]
    resource = args.get("resource", 0)
    return f'from riodata import duo\n\ndf = duo.load("{dataset_id}", "{resource}")\nprint(df)'


def _get_cbs_data_snippet(args: dict) -> str:
    dataset_id = args["dataset_id"]
    filters = args.get("filters")
    lines = ["from onderwijsdata import data", ""]
    params = f'"{dataset_id}"'
    if filters:
        for k, v in filters.items():
            params += f", {k}={v!r}"
    lines.append(f"rows = data({params})")
    lines.append("print(rows)")
    return "\n".join(lines)


def _create_plot_snippet(args: dict) -> str:
    import json
    chart_type = args.get("chart_type", "bar")
    x = args.get("x", "x")
    y = args.get("y", "y")
    title = args.get("title", "")
    color_by = args.get("color_by")
    data_key = args.get("data_key")

    lines = ["import pandas as pd", "import plotly.express as px", ""]

    if data_key:
        lines.append(f'df = store.get("{data_key}")')
    else:
        data = args.get("data", [])
        lines.append(f"data = {json.dumps(data, ensure_ascii=False)}")
        lines.append("df = pd.DataFrame(data)")

    px_func = {"bar": "px.bar", "line": "px.line", "scatter": "px.scatter"}.get(chart_type, "px.bar")
    color_arg = f', color="{color_by}"' if color_by else ""
    lines.append(f'fig = {px_func}(df, x="{x}", y="{y}", title="{title}"{color_arg})')
    lines.append("fig.show()")
    return "\n".join(lines)


def _create_choropleth_snippet(args: dict) -> str:
    import json
    location_col = args.get("location_col", "")
    value_col = args.get("value_col", "")
    title = args.get("title", "")
    data_key = args.get("data_key")

    lines = ["import pandas as pd", "import plotly.express as px", ""]

    if data_key:
        lines.append(f'df = store.get("{data_key}")')
    else:
        data = args.get("data", [])
        lines.append(f"data = {json.dumps(data, ensure_ascii=False)}")
        lines.append("df = pd.DataFrame(data)")

    lines.append(f'fig = px.choropleth_map(df, locations="{location_col}", color="{value_col}", title="{title}")')
    lines.append("fig.show()")
    return "\n".join(lines)


_GENERATORS = {
    "query_data": _query_data_snippet,
    "run_analysis": _run_analysis_snippet,
    "get_duo_data": _get_duo_data_snippet,
    "get_cbs_data": _get_cbs_data_snippet,
    "create_plot": _create_plot_snippet,
    "create_choropleth_map": _create_choropleth_snippet,
}


def generate(tool_name: str, args: dict) -> str | None:
    gen = _GENERATORS.get(tool_name)
    if gen is None:
        return None
    return gen(args)
