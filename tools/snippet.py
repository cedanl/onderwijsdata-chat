"""Genereer reproduceerbare Python-snippets uit tool calls.

Een snippet moet buiten de app draaien met alleen de gedocumenteerde pakketten
(pandas, plotly, onderwijsdata, riodata): `store` bestaat daar niet (#131). Elke
snippet begint daarom met de laadstap van zijn bron, uit de laadaanroep die de
store bij de key bewaart.

Wat de tool met de data deed (sentinels uitgesloten, CBS-afronding, een afgekapte
pagina) komt als commentaar bovenaan, uit dezelfde response die het model las (#4).
"""

import json

from core.config import RIO_PAGE_SIZE
from core.sentinels import BETEKENIS, SENTINELS, SIGNED_HINTS

from . import instellingsprovincie, scopeprofiel, store
from .duo import is_prognose
from .periode import STUDIEJAAR_LABEL
from .plot import resolve_chart_type
from .query import NUMERIEKE_AGG, _parse_filter_key
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
    return [
        "import pandas as pd",
        "from riodata import duo",
        "",
        f"df = duo.load({_lit(args['dataset_id'])}, {_lit(args.get('resource', 0))})",
        *_duo_sentinelregels(),
        # De app voegt dit label toe (#115); analysecode mag het gebruiken.
        'if "STUDIEJAAR" in df.columns:',
        f'    df["{STUDIEJAAR_LABEL}"] = df["STUDIEJAAR"].map(lambda j: f"{{j}}/{{j + 1}}")',
        *_provincieregels(args["dataset_id"]),
    ]


def _provincieregels(dataset_id: str) -> list[str]:
    """De provincie van de instelling, zoals de app hem bij deze mbo-bestanden toevoegt (#453)."""
    if dataset_id not in instellingsprovincie.DATASETS:
        return []
    kolom, (adressen, resource) = instellingsprovincie.KOLOM, instellingsprovincie.ADRESBESTAND
    return [
        f"# De app voegt {kolom} toe uit DUO's adressenbestand; een code zonder adres blijft leeg.",
        f'if "INSTELLINGSCODE" in df.columns and "{kolom}" not in df.columns:',
        f"    adressen = duo.load({_lit(adressen)}, {resource}).dropna(subset=['PROVINCIE'])",
        "    provincie = dict(zip(adressen['INSTELLINGSCODE'].astype(str).str.strip(), adressen['PROVINCIE']))",
        f'    df["{kolom}"] = df["INSTELLINGSCODE"].astype(str).str.strip().map(provincie)',
    ]


def _duo_sentinelregels() -> list[str]:
    """Dezelfde maskering als core.sentinels.mask_sentinels in de app, met dezelfde constanten (#227)."""
    return [
        f"# DUO-sentinel -1 = {BETEKENIS}. De app sluit ze uit.",
        "# Totalen over een selectie met zulke cellen zijn een ondergrens.",
        "for kolom in df.select_dtypes('number').columns:",
        f"    if not any(h in str(kolom).upper() for h in {SIGNED_HINTS!r}):",
        f"        df[kolom] = df[kolom].mask(df[kolom].isin({list(SENTINELS)!r}))",
    ]


def _cbs_laadregels(args: dict) -> list[str]:
    filters = args.get("filters") or {}
    extra = f", **{filters!r}" if filters else ""
    regels = [
        "import pandas as pd",
        "from onderwijsdata import data",
        "",
        f"df = pd.DataFrame(data({_lit(args['dataset_id'])}{extra}))",
    ]
    if args["dataset_id"] in scopeprofiel.CBS_SECTORFILTER:
        # Dezelfde mbo-selectie als de app (CH-03).
        dimensie, codes = scopeprofiel.CBS_SECTORFILTER[args["dataset_id"]]
        regels.append(f"df = df[df[{dimensie!r}].str.strip().isin({sorted(codes)!r})]  # alleen mbo")
    return regels


def _rio_laadregels(args: dict) -> list[str]:
    params = {**(args.get("filters") or {}), "page": 0, "pageSize": RIO_PAGE_SIZE}
    return [
        "import pandas as pd",
        "from riodata import fetch",
        "",
        f"df = pd.DataFrame(fetch({_lit(args['resource'])}, **{params!r}))",
    ]


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
        return [
            *_laadregels(root),
            "# NB: de grafiek of berekening gebruikt hier een selectie van deze data (eerdere stappen).",
        ]
    laad = known.laad if known and known.laad else _bron_van_key(data_key)
    if laad:
        return _LAADREGELS[laad[0]](laad[1])
    return [
        "import pandas as pd",
        "",
        f"# Geen laadstap bekend voor {data_key!r}: laad de data met de tool waarmee hij is opgehaald.",
        "df = pd.DataFrame()",
    ]


_VERGELIJKING = {"gte": ">=", "lte": "<="}


def _filterregel(key: str, val) -> str:
    """Eén filter met de semantiek van query._apply_filters (#227).

    Gelijkheid zonder hoofdletters op de tekstvorm, zodat "2025" ook een int-kolom
    raakt; een bereik numeriek als de grens een getal is, anders op tekst.
    """
    col, op = _parse_filter_key(key)
    if op in ("eq", "in"):
        vals = [str(v).lower() for v in (val if isinstance(val, list) else [val])]
        return f"df = df[df[{col!r}].astype(str).str.lower().isin({vals!r})]"
    teken = _VERGELIJKING[op]
    try:
        grens = float(val)
    except (TypeError, ValueError):
        return f"df = df[df[{col!r}].astype(str).str.lower() {teken} {str(val).lower()!r}]"
    return f'df = df[pd.to_numeric(df[{col!r}], errors="coerce") {teken} {grens!r}]'


def _aggregatiefuncties(aggregate: dict) -> str:
    """Het agg-argument als code: een som zonder één waarde blijft leeg, zoals in query (#394)."""
    delen = [
        f"{kolom!r}: " + ("lambda s: s.sum(min_count=1)" if fn == "sum" else repr(fn))
        for kolom, fn in aggregate.items()
    ]
    return "{" + ", ".join(delen) + "}"


def _aggregatieregels(group_by: list[str], aggregate: dict) -> list[str]:
    """Zoals query._apply_aggregation: rekenkolommen numeriek, lege groepen houden (#227, #411)."""
    lines = [f"group_by = {group_by!r}"]
    if "STUDIEJAAR" in group_by:
        lines += [
            f'if "{STUDIEJAAR_LABEL}" in df.columns and "{STUDIEJAAR_LABEL}" not in group_by:',
            f'    group_by.append("{STUDIEJAAR_LABEL}")',
        ]
    numeriek = [kolom for kolom, fn in aggregate.items() if fn in NUMERIEKE_AGG]
    if numeriek:
        lines += [
            f"for kolom in {numeriek!r}:",
            '    df[kolom] = pd.to_numeric(df[kolom], errors="coerce")',
        ]
    lines += [
        f"df = df.groupby(group_by, dropna=False).agg({_aggregatiefuncties(aggregate)}).reset_index()",
    ]
    return lines


def _query_data_snippet(args: dict) -> str:
    lines = _laadregels(args.get("data_key", ""))
    for key, val in (args.get("filters") or {}).items():
        if _parse_filter_key(key)[1] in ("eq", "in", *_VERGELIJKING):
            lines.append(_filterregel(key, val))

    columns = args.get("columns")
    if columns:
        lines.append(f"df = df[{columns!r}]")

    group_by = args.get("group_by")
    aggregate = args.get("aggregate")
    if group_by and aggregate:
        lines += _aggregatieregels(group_by, aggregate)

    # Prognoses op hele personen, zoals query_data ze teruggeeft (#247).
    lines.append("print(df.round())" if is_prognose(store.meta(args.get("data_key", ""))) else "print(df)")
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


def _bereikregels(sort_column: str | None, van: int | None, tot: int | None) -> list[str]:
    """De `van`/`tot`-selectie van compute_kpi: rijen waarvan het startjaar binnen het bereik valt."""
    if not sort_column or (van is None and tot is None):
        return []
    ondergrens = "-inf" if van is None else van
    bovengrens = "inf" if tot is None else tot
    return [
        f"jaar = pd.to_numeric(df[{sort_column!r}].astype(str).str[:4], errors='coerce')",
        f"df = df[jaar.between(float('{ondergrens}'), float('{bovengrens}'))]",
    ]


def _compute_kpi_snippet(args: dict) -> str:
    """Maak de KPI-berekening reproduceerbaar, zodat de gebruiker het getal kan narekenen."""
    metric = args.get("metric", "")
    expressie = _KPI_EXPRESSIES.get(metric)
    if expressie is None:
        return ""
    value_column = args.get("value_column", "")
    sort_column = args.get("sort_column")
    label = args.get("label", "")

    # Zelfstandig: de KPI laadt zijn eigen data, net als de andere snippets (#227).
    lines = [*_laadregels(args.get("data_key", "")), "", f"# KPI: {label} ({metric})"]
    lines += _bereikregels(sort_column, args.get("van"), args.get("tot"))
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
    x = args.get("x", "x")
    y = args.get("y", "y")
    title = args.get("title", "")
    color_by = args.get("color_by")
    data_key = args.get("data_key")

    lines = _frame_regels(args, data_key)

    df = store.get(data_key) if data_key else None
    rows = df.to_dict(orient="records") if df is not None else args.get("data") or []
    chart_type = resolve_chart_type(rows, args.get("chart_type", "auto"), x, y, color_by, args.get("is_share", False))
    color_arg = f', color="{color_by}"' if color_by else ""
    if chart_type == "pie":
        lines.append(f'fig = px.pie(df, names="{x}", values="{y}", title="{title}")')
    else:
        px_func = {"line": "px.line", "scatter": "px.scatter", "histogram": "px.histogram"}.get(chart_type, "px.bar")
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


def _bewerkingsregels(result: str | None) -> list[str]:
    """De bewerkingen en publicatieregels uit de tool-response, als commentaarregels.

    Uit de response zelf, niet opnieuw berekend: de verantwoording in de snippet
    kan zo niet uit de pas lopen met wat de tool deed en het model las.
    """
    try:
        data = json.loads(result) if result else None
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    regels = [r for r in data.get("databewerking") or [] if isinstance(r, str)]
    regels += [data[k] for k in ("afronding", "afronding_onbekend") if isinstance(data.get(k), str)]
    if data.get("volledig") is False or data.get("meer_beschikbaar") is True:
        regels.append(f"Afgekapt: {data.get('opgehaalde_rijen', '?')} rijen opgehaald, niet de hele bron.")
    return [f"# {r}" for r in regels]


def generate(tool_name: str, args: dict, result: str | None = None) -> str | None:
    gen = _GENERATORS.get(tool_name)
    if gen is None:
        return None
    snippet = gen(args)
    if snippet and (regels := _bewerkingsregels(result)):
        return "\n".join(["# Databewerking in de app:", *regels, "", snippet])
    return snippet
