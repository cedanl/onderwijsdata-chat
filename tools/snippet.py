"""Genereer reproduceerbare Python-snippets uit tool calls.

Een snippet moet buiten de app draaien met alleen de gedocumenteerde pakketten
(pandas, plotly, onderwijsdata, riodata): `store` bestaat daar niet (#131). Elke
snippet begint daarom met de laadstap van zijn bron, uit de laadaanroep die de
store bij de key bewaart.

Wat de tool met de data deed (sentinels uitgesloten, CBS-afronding, een afgekapte
pagina) komt als commentaar bovenaan, uit dezelfde response die het model las (#4).

Een afgeleide uitkomst (selectie, vaste maat) herhaalt de stappen van zijn ouder
uit zijn recept (#472), zodat `df` in dezelfde snippet ontstaat en de code opnieuw
te draaien is op actuele data. Zonder bekende keten blijft alleen een kopie van
de rijen over, met een opmerking die dat zegt (#624).
"""

import json

from core.config import RIO_PAGE_SIZE
from core.sentinels import BETEKENIS, SENTINELS, SIGNED_HINTS

from . import cbs_selectie, instellingsprovincie, maten, scopeprofiel, store
from .canoniek import parse_filter_key
from .duo import is_prognose
from .herlaad import Receptbron
from .periode import STUDIEJAAR_LABEL
from .plot import is_liggend, resolve_chart_type
from .query import NUMERIEKE_AGG
from .schemas import (
    TOOL_COMPUTE_KPI,
    TOOL_CREATE_CHOROPLETH_MAP,
    TOOL_CREATE_PLOT,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
)

# Alleen nog voor een onbekende keten: meer rijen dan dit gaan niet als literal de snippet in (#624).
_MAX_INLINE_RIJEN = 200

# Zo lang mag een receptenketen zijn, zoals herlaad._MAX_STAPPEN: een rondlopend recept loopt niet door (#624).
_MAX_KETEN = 10


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


def _cbs_filters(args: dict) -> dict:
    """De OData-parameters van de aanroep: de bewaarde `filters`, of het compilaat van een
    gesloten selectie (#343). Zonder poort: de snippet reproduceert de aanroep, hij keurt hem niet."""
    if (filters := args.get("filters")) is not None:
        return dict(filters)
    if (selectie := args.get("selectie")) is None:
        return {}
    compilaat = cbs_selectie.compileer(args["dataset_id"], selectie, None)
    return compilaat if isinstance(compilaat, dict) else {}


def _cbs_laadregels(args: dict) -> list[str]:
    filters = _cbs_filters(args)
    # Dezelfde sectorselectie als de app, in de aanroep en op de rijen (CH-03).
    selectie = scopeprofiel.cbs_sectorselectie(args["dataset_id"], filters)
    if isinstance(selectie, scopeprofiel.CbsSectorselectie):
        filters = selectie.params
    extra = f", **{filters!r}" if filters else ""
    regels = [
        "import pandas as pd",
        "from onderwijsdata import data",
        "",
        f"df = pd.DataFrame(data({_lit(args['dataset_id'])}{extra}))",
    ]
    if isinstance(selectie, scopeprofiel.CbsSectorselectie):
        rijen = f"df = df[df[{selectie.dimensie!r}].str.strip().isin({sorted(selectie.codes)!r})]"
        regels.append(f"{rijen}  # alleen {selectie.deel}")
    return regels


def _rio_laadregels(args: dict) -> list[str]:
    params = {**(args.get("filters") or {}), "page": 0, "pageSize": RIO_PAGE_SIZE}
    return [
        "import pandas as pd",
        "from riodata import fetch",
        "",
        f"df = pd.DataFrame(fetch({_lit(args['resource'])}, **{params!r}))",
    ]


def _uwv_laadregels(args: dict) -> list[str]:
    """Dezelfde tabel als get_uwv_vacatures in de store zet (#577): alle beroepenclusters van de plaats, aflopend."""
    regels = [
        "import pandas as pd",
        "from riodata import uwv",
        "",
        'df = uwv.load("latest", rec_type="Vacature")',
        f'df = df[df["PROVINCIE"].str.lower() == {_lit(args["provincie"].lower())}]',
    ]
    if gemeente := args.get("gemeente"):
        regels.append(f'df = df[df["GEMEENTE"].str.lower() == {_lit(gemeente.lower())}]')
    regels += [
        'df = df.groupby("BEROEPENCLUSTER", as_index=False)["AANTAL"].sum().sort_values("AANTAL", ascending=False)',
        'df = df.rename(columns={"AANTAL": "VACATURES"})',
        f'df.insert(0, "PROVINCIE", {_lit(args["provincie"])})',
    ]
    if gemeente:
        regels.append(f'df.insert(1, "GEMEENTE", {_lit(gemeente)})')
    return regels


def _roa_laadregels(args: dict) -> list[str]:
    """De ROA-rijen achter get_roa_benchmark (#577): de regio (of landelijk) voor schoolverlaters en prognose.

    De app neemt per onderdeel de regio en valt terug op Nederland als ROA daar geen cijfers heeft;
    die keuze staat als commentaar, de rijen van beide staan in `df`.
    """
    regio = args.get("regio") or "Nederland"
    niveau = "opleidingssector (ONR2019)" if args.get("sector") else "opleidingsniveau (ONR2019)"
    regels = [
        "import pandas as pd",
        "from riodata import roa",
        "",
        'df = roa.load("ais2030", "arbeidsmarkt")',
        f'df = df[df["regionaam"].str.lower().isin([{_lit(regio.lower())}, "nederland", "provincie " + {_lit(regio.lower())}])]',
        f'df = df[df["aggregatieniveau"].str.strip() == {_lit(niveau)}]',
    ]
    if sector := args.get("sector"):
        regels.append(f'df = df[df["detailniveau"] == {_lit(sector)}]')
    regels += [
        'df = df[["thema", "regionaam", "detailniveau", "onderwerp", "perc", "aantal", "typering", "versie"]]',
        "# De app neemt per onderdeel (schoolverlaters, prognose) de regio en valt terug op Nederland als ROA daar geen cijfers heeft.",
    ]
    return regels


_LAADREGELS = {
    "get_duo_data": _duo_laadregels,
    "get_cbs_data": _cbs_laadregels,
    "get_rio_data": _rio_laadregels,
    "get_uwv_vacatures": _uwv_laadregels,
    "get_roa_benchmark": _roa_laadregels,
}


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
    """Een selectie of analyse-uitkomst als rijen: alleen als de keten niet bekend is (#624)."""
    df = store.get(data_key)
    if df is not None and len(df) <= _MAX_INLINE_RIJEN:
        records = json.loads(df.to_json(orient="records", force_ascii=False))
        return [
            "import pandas as pd",
            "",
            f"df = pd.DataFrame({records!r})  # kopie van een eerdere stap: de keten is onbekend, "
            "deze waarden groeien niet mee met de bron",
        ]
    return []


def _stapregels(recept: object, recept_van: Receptbron | None, stappen: int) -> list[str] | None:
    """De stappen van de aanroep die deze key opleverde: eerst de ouder, dan deze stap (#624).

    Uit het recept dat de sessie bijhoudt (#472), niet uit de argumenten van de huidige
    aanroep: de grafiek of KPI noemt alleen de key. Zonder bruikbaar recept keert dit
    terug en bakt _afgeleide_regels de rijen in.
    """
    if not isinstance(recept, dict) or stappen >= _MAX_KETEN:
        return None
    tool, args = recept.get("tool"), recept.get("args")
    if not isinstance(args, dict):
        return None
    ouder = recept.get("afgeleid_van")
    if tool == TOOL_QUERY_DATA and isinstance(ouder, str):
        return [*_laadregels(ouder, recept_van, stappen + 1), *_query_stappen(args)]
    if tool == TOOL_GET_MAAT:
        # Het recept van een vaste maat laadt en selecteert zelf (#188), zoals herlaad._hermaat.
        regels, fout = _maat_regels(args)
        return None if fout else regels
    return None


def _recept_laad(recept: object) -> tuple[str, dict] | None:
    """De laadaanroep uit een recept ({laad: [tool, args]}, #472); niets als die er niet is."""
    laad = recept.get("laad") if isinstance(recept, dict) else None
    tool, args = laad if isinstance(laad, list | tuple) and len(laad) == 2 else (None, None)
    return (tool, args) if isinstance(tool, str) and isinstance(args, dict) and tool in _LAADREGELS else None


def _laadregels(data_key: str, recept_van: Receptbron | None = None, stappen: int = 0) -> list[str]:
    """Regels die `df` zetten voor een key, zonder `store`."""
    recept = recept_van(data_key) if recept_van else None
    if (stap := _stapregels(recept, recept_van, stappen)) is not None:
        return stap
    known = store.meta(data_key)
    if known and known.afgeleid_van:
        if inline := _afgeleide_regels(data_key):
            return inline
        root = data_key
        while (parent := store.meta(root)) and parent.afgeleid_van:
            root = parent.afgeleid_van
        return [
            *_laadregels(root, recept_van, stappen + 1),
            "# NB: de keten van deze selectie is niet bekend en er zijn meer rijen dan in de snippet passen:",
            "# deze code laadt de hele bron, dus de uitkomst kan afwijken van wat de app toonde.",
        ]
    laad = known.laad if known and known.laad else _recept_laad(recept) or _bron_van_key(data_key)
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
    col, op = parse_filter_key(key)
    if op in ("eq", "in"):
        vals = [str(v).lower() for v in (val if isinstance(val, list) else [val])]
        if all(v.isdigit() for v in vals):
            # Codes als tekst met voorloopnul ('0363' voor 363, #542): eerst exact, anders zonder voorloopnullen.
            kaal = [v.lstrip("0") or "0" for v in vals]
            return "\n".join(
                [
                    f"_kolom = df[{col!r}].astype(str)",
                    f"_exact = _kolom.str.lower().isin({vals!r})",
                    f"df = df[_exact] if _exact.any() else df[_kolom.str.isdigit() & _kolom.str.lstrip('0').replace('', '0').isin({kaal!r})]",
                ]
            )
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


def _query_stappen(args: dict) -> list[str]:
    """De selectie van query_data op een bestaande `df`: filters, kolommen en aggregatie (#227, #624)."""
    lines: list[str] = []
    for key, val in (args.get("filters") or {}).items():
        if parse_filter_key(key)[1] in ("eq", "in", *_VERGELIJKING):
            lines.append(_filterregel(key, val))
    if columns := args.get("columns"):
        lines.append(f"df = df[{columns!r}]")
    if (group_by := args.get("group_by")) and (aggregate := args.get("aggregate")):
        lines += _aggregatieregels(group_by, aggregate)
    return lines


def _query_data_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    lines = [*_laadregels(args.get("data_key", ""), recept_van), *_query_stappen(args)]

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


def _compute_kpi_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    """Maak de KPI-berekening reproduceerbaar, zodat de gebruiker het getal kan narekenen."""
    metric = args.get("metric", "")
    expressie = _KPI_EXPRESSIES.get(metric)
    if expressie is None:
        return ""
    value_column = args.get("value_column", "")
    sort_column = args.get("sort_column")
    label = args.get("label", "")

    # Zelfstandig: de KPI laadt zijn eigen data, net als de andere snippets (#227).
    lines = [*_laadregels(args.get("data_key", ""), recept_van), "", f"# KPI: {label} ({metric})"]
    lines += _bereikregels(sort_column, args.get("van"), args.get("tot"))
    if sort_column:
        lines.append(f"df = df.sort_values({sort_column!r})")
    lines.append(f's = pd.to_numeric(df[{value_column!r}], errors="coerce").dropna()')
    lines.append(f"kpi = {expressie}")
    lines.append("print(kpi)")
    return "\n".join(lines)


def _run_analysis_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    code = args.get("code", "")
    data_key = args.get("data_key")
    if not data_key:
        return code
    # De sandbox geeft np, px en go kant-en-klaar; buiten de app moeten ze geïmporteerd worden.
    imports = ["import numpy as np", "import plotly.express as px", "import plotly.graph_objects as go"]
    return "\n".join([*_laadregels(data_key, recept_van), *imports, "", code])


def _get_duo_data_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    return "\n".join([*_duo_laadregels(args), "print(df)"])


def _get_cbs_data_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    return "\n".join([*_cbs_laadregels(args), "print(df)"])


def _get_rio_data_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    return "\n".join([*_rio_laadregels(args), "print(df)"])


def _frame_regels(args: dict, data_key: str | None, recept_van: Receptbron | None = None) -> list[str]:
    """Laadstap plus plotly-import voor een grafiek: uit de key, of uit de meegegeven rijen."""
    if data_key:
        regels = _laadregels(data_key, recept_van)
    else:
        regels = ["import pandas as pd", "", f"df = pd.DataFrame({args.get('data', [])!r})"]
    return [*regels, "import plotly.express as px", ""]


def _create_plot_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    x = args.get("x", "x")
    y = args.get("y", "y")
    title = args.get("title", "")
    color_by = args.get("color_by")
    data_key = args.get("data_key")

    lines = _frame_regels(args, data_key, recept_van)

    df = store.get(data_key) if data_key else None
    rows = df.to_dict(orient="records") if df is not None else args.get("data") or []
    chart_type = resolve_chart_type(rows, args.get("chart_type", "auto"), x, y, color_by, args.get("is_share", False))
    # Op de x-kolom zelf kleurt create_plot per staaf zonder legenda; px zou er een legenda van maken.
    color_arg = f', color="{color_by}"' if color_by and color_by != x else ""
    if chart_type == "pie":
        lines.append(f'fig = px.pie(df, names="{x}", values="{y}", title="{title}")')
    elif chart_type == "bar" and is_liggend(rows, chart_type, x, data_key):
        lines.append(f'fig = px.bar(df, x="{y}", y="{x}", orientation="h", title="{title}"{color_arg})')
        lines.append('fig.update_yaxes(autorange="reversed")')
    else:
        px_func = {"line": "px.line", "scatter": "px.scatter", "histogram": "px.histogram"}.get(chart_type, "px.bar")
        lines.append(f'fig = {px_func}(df, x="{x}", y="{y}", title="{title}"{color_arg})')
    lines.append("fig.show()")
    return "\n".join(lines)


def _create_choropleth_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    location_col = args.get("location_col", "")
    value_col = args.get("value_col", "")
    title = args.get("title", "")
    data_key = args.get("data_key")

    lines = _frame_regels(args, data_key, recept_van)

    lines.append(f'fig = px.choropleth_map(df, locations="{location_col}", color="{value_col}", title="{title}")')
    lines.append("fig.show()")
    return "\n".join(lines)


def _maat_regels(args: dict) -> tuple[list[str], str | None]:
    """De regels van een vaste maat zonder `print`: laden, filteren, per studiejaar optellen (#188, #624).

    Retourneert (regels, foutmelding); bij een melding zijn de regels leeg. Zonder print
    kan het recept van een eerdere KPI of grafiek dezelfde regels herhalen (#624).
    """
    p = maten.plan(
        args.get("maat"),
        args.get("instelling"),
        args.get("sector"),
        args.get("vorm", maten.ALLE),
        args.get("schooljaren"),
    )
    if isinstance(p, str):
        return [], p
    if isinstance(p.recept, maten.CbsRecept):
        params = cbs_selectie.compileer(p.recept.dataset, maten.selectie(p), None)
        return [
            *_cbs_laadregels({"dataset_id": p.recept.dataset, "filters": params if isinstance(params, dict) else {}}),
        ], None
    lines = _duo_laadregels({"dataset_id": p.recept.dataset, "resource": p.bestand})
    lines += [_filterregel(key, val) for key, val in maten.filters(p).items()]
    lines += _aggregatieregels([p.recept.periodekolom], maten.aggregate(p))
    if isinstance(p.recept, maten.DuoBreedRecept):
        kolommen = list(p.recept.leerwegen[p.vorm])
        lines.append(f'df["{maten.AANTAL}"] = df[{kolommen!r}].sum(axis=1, min_count=1)')
    return lines, None


def _get_maat_snippet(args: dict, recept_van: Receptbron | None = None) -> str:
    """Het recept van een vaste maat als zelfstandig script (#188)."""
    regels, fout = _maat_regels(args)
    return f"# {fout}" if fout else "\n".join([*regels, "print(df)"])


_GENERATORS = {
    TOOL_GET_MAAT: _get_maat_snippet,
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


def generate(tool_name: str, args: dict, result: str | None = None, recept_van: Receptbron | None = None) -> str | None:
    """Genereer de snippet; `recept_van` levert de keten van een afgeleide key (#472, #624)."""
    gen = _GENERATORS.get(tool_name)
    if gen is None:
        return None
    snippet = gen(args, recept_van=recept_van)
    if snippet and (regels := _bewerkingsregels(result)):
        return "\n".join(["# Databewerking in de app:", *regels, "", snippet])
    return snippet
