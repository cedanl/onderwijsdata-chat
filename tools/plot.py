import json as _json
import logging
import math
import re
import urllib.request

import plotly.express as px
import plotly.graph_objects as go

from . import cbs_afronding, duo, fouten, kaartlocaties, store
from .exportnoten import herkomstregels
from .getal import nl_getal
from .kolomlabel import kolomlabel, leesbaar, waardelabels

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

_MARGE = {"t": 60, "b": 50, "l": 70, "r": 20}

# De legenda horizontaal onder de x-as: rechts ernaast kostte hij een derde van de breedte en op
# een telefoon bijna alles, boven botst hij met de titel. Onderaan de figuur (container) duwt hij
# de ondermarge op in plaats van over de astitel te vallen.
_LEGENDA_ONDER = {"orientation": "h", "x": 0, "xanchor": "left", "yref": "container", "y": 0, "yanchor": "bottom"}

_LAYOUT_BASE = {
    "font": {"family": "Inter, Arial, sans-serif", "size": 13},
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
    "margin": _MARGE,
    "legend": {"bgcolor": "rgba(255,255,255,0.8)", "bordercolor": "#ddd", "borderwidth": 1, **_LEGENDA_ONDER},
}

# "Mbo-studenten perprovincie": "per" vast aan een niveauwoord in de titel van het model (#640). Alleen
# deze woorden, aan het begin van een woord, zodat "perspectief" en "personeel" blijven staan.
_PER_NIVEAU = re.compile(r"\b(per)(?=provincie|gemeente|corop|regio)", re.IGNORECASE)


def schone_titel(title: str) -> str:
    """De titel van een grafiek of kaart met de spatie na een vastgeplakt "per"; verder ongewijzigd."""
    return _PER_NIVEAU.sub(r"\1 ", title) if isinstance(title, str) else title


# Nederlandse notatie: punt voor duizendtallen, komma voor decimalen (#22).
_NL_SEPARATORS = ",."

_AXIS_STYLE = {"showgrid": True, "gridcolor": "#f0f0f0", "linecolor": "#ccc", "zeroline": False}

# Plotly's eigen `plotly`-template geeft elke as automargin en een title.standoff van 15: de
# ondermarge groeit dan mee met de legendarijen en de astitel blijft boven de tick-labels. Een
# figuur zonder template (geëxporteerd, of na `layout.pop("template")`) mist dat en dan valt de
# horizontale legenda over de astitel (#575). Hier expliciet, met dezelfde waarden, zodat de
# weergave met de template pixelgelijk blijft.
_AS_AUTOMARGIN = True
_AS_STANDOFF = 15

# Staande staven kantelen veel of lange namen onder de as tot ze onleesbaar zijn (90° in de
# chat, achttien universiteiten op een plotvlak van 60px). Liggend staat elke naam als gewone
# tekst naast zijn staaf.
_MAX_STAANDE_CATEGORIEEN = 8
_MAX_STAAND_LABEL = 12  # tekens: langer past op een telefoon niet meer naast elkaar

# Liggend krijgt elke categorie een rij en groeit de figuur mee, in plaats van de staven te pletten.
_STAAF_HOOGTE = 18  # px per staaf in een rij: het getal erin blijft 11-12px
_RIJ_RUIMTE = 6  # px tussen de rijen
_HOOGTE_RAND = 130  # titel, waardeas en astitel
_MIN_HOOGTE = 340  # de standaardhoogte van een grafiek in de chat
_MAX_HOOGTE = 1200

# Een waardelabel staat boven zijn punt (#22). Het label van het hoogste punt viel boven het plotvlak weg,
# en een label op de eerste of laatste x-waarde werd aan de zijkant afgeknipt (#579). De waardeas loopt
# daarom door tot boven het hoogste label: een deel van het waardebereik, zodat het op elke hoogte klopt
# (op een plotvlak van 160 px, een telefoon, ruim 20 px: de hoogte van een label). Naar binnen wijzende
# randlabels botsten op een telefoon met hun buurlabel, vandaar mag een lijnlabel buiten het plotvlak staan.
_LABEL_KOPRUIMTE = 0.15

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


GEOJSON_URLS = {
    "provincie": "https://cartomap.github.io/nl/wgs84/provincie_2024.geojson",
    "gemeente": "https://cartomap.github.io/nl/wgs84/gemeente_2024.geojson",
    "corop": "https://cartomap.github.io/nl/wgs84/coropgebied_2024.geojson",
}
_GEOJSON_CACHE: dict[str, dict] = {}
# De opmaak van de kaart; het recept (tools/snippet.py) gebruikt dezelfde waarden (#630). Centrum en zoom laten heel
# Nederland zien in een Plotly-figuur van standaardmaat (700 x 450, kleurenbalk en titel eraf); met 52,3 en zoom 6
# viel Limburg onderaan weg (#642). De chat rekent ze zelf uit voor de breedte die de kaart heeft (kaartBeeld.js).
KAART_OPTIES = {
    "center": {"lat": 52.18, "lon": 5.3},
    "zoom": 5.8,
    "map_style": "white-bg",
    "color_continuous_scale": "Blues",
}
# De kolom met de feature-id waartegen de kaart tekent; de locatiekolom van de data houdt de namen (#628).
_KAARTCODE = "kaartcode"
# De naam van het gebied in de GeoJSON, voor het hoverlabel: "Groningen", niet "PV20" (#659).
_KAARTNAAM = "kaartnaam"


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


def _value_labels(y_vals: list, enabled: bool) -> list[str] | None:
    if not enabled or len(y_vals) > _MAX_LABELED_POINTS:
        return None
    return ["" if _is_missing(v) else nl_getal(v) for v in y_vals]


def _group_by_color(data: list[dict], x: str, y: str, color_by: str) -> dict[str, dict]:
    """Group data rows by the *color_by* column."""
    groups: dict[str, dict] = {}
    for row in data:
        key = str(row.get(color_by, "onbekend"))
        groups.setdefault(key, {"x": [], "y": []})
        groups[key]["x"].append(row.get(x))
        groups[key]["y"].append(row.get(y))
    return groups


def _is_naam(waarde) -> bool:
    """Tekst die geen getal is: een instelling of sector, geen leeftijd of cohort."""
    if not isinstance(waarde, str):
        return False
    try:
        float(waarde.replace(",", "."))
    except ValueError:
        return True
    return False


def _liggend(chart_type: str, x: str, categorieen: list) -> bool:
    """Liggende staven voor veel of lange namen; een tijdas en getallen blijven staand."""
    if chart_type != "bar" or _is_time_axis(x):
        return False
    namen = [c for c in dict.fromkeys(categorieen) if not _is_missing(c)]
    if not namen or not all(_is_naam(c) for c in namen):
        return False
    return len(namen) > _MAX_STAANDE_CATEGORIEEN or max(len(c) for c in namen) > _MAX_STAAND_LABEL


def is_liggend(rows: list[dict], chart_type: str, x: str, data_key: str | None = None) -> bool:
    """Of create_plot deze staven liggend tekent; de snippet leest het hier ook, zodat ze niet uiteenlopen (#245)."""
    known = store.meta(data_key) if data_key else None
    labels = waardelabels(x, known.dataset if known else None)
    return _liggend(chart_type, x, leesbaar([row.get(x) for row in rows], labels))


def _hoogte(categorieen: int, staven_per_rij: int) -> int:
    rij = _RIJ_RUIMTE + _STAAF_HOOGTE * staven_per_rij
    hoogte = categorieen * rij + _HOOGTE_RAND
    return max(_MIN_HOOGTE, min(_MAX_HOOGTE, hoogte))


def kopruimte(reeksen: list[dict]) -> float | None:
    """De waarde tot waar de waardeas moet lopen, zodat het label boven het hoogste punt in het plotvlak
    staat (#579). `reeksen` zijn traces als dict (y, text); alleen reeksen met labels tellen.

    Create_plot gebruikt dit, en het bijsnijden van een rapportgrafiek (#385) opnieuw.
    """
    getallen = [
        y
        for r in reeksen
        if r.get("text") is not None
        for y in r.get("y") or []
        if isinstance(y, int | float) and not isinstance(y, bool) and not _is_missing(y)
    ]
    if not getallen:
        return None
    hoog, laag = max(getallen), min(getallen)
    return hoog + _LABEL_KOPRUIMTE * ((hoog - laag) or abs(hoog) or 1)


def _accentkleuren(ruw: list, labels: list, highlight: str) -> list[str]:
    """Per staaf: de accentkleur voor de uitgelichte categorie (code of woord), grijs voor de rest."""
    return [
        _PALETTE[0] if highlight in (str(r), str(label)) else _HIGHLIGHT_GREY
        for r, label in zip(ruw, labels, strict=True)
    ]


def _add_trace(
    fig: go.Figure,
    chart_type: str,
    x_vals: list,
    y_vals: list,
    color: str | list[str],
    name: str | None = None,
    text: list[str] | None = None,
    liggend: bool = False,
) -> None:
    """Add a single trace to the figure based on *chart_type*."""
    common = {"name": name} if name else {}
    if chart_type == "bar":
        # Liggend staat het getal in de staaf als het past, anders erachter: buiten de staaf viel
        # het getal van de langste staaf op een smal scherm van de figuur af.
        assen = (
            {"x": y_vals, "y": x_vals, "orientation": "h", "cliponaxis": False, "insidetextanchor": "end"}
            if liggend
            else {"x": x_vals, "y": y_vals}
        )
        plek = ("auto" if liggend else "outside") if text else None
        fig.add_trace(go.Bar(**assen, marker_color=color, text=text, textposition=plek, **common))
    elif chart_type == "line":
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers" + ("+text" if text else ""),
                text=text,
                textposition="top center",
                cliponaxis=False if text else None,
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


def _astitel(tekst: str) -> dict:
    """De astitel met de standoff van Plotly's template, zodat de titel boven de tick-labels blijft
    en niet tegen de legenda aan staat (#575)."""
    return {"text": tekst, "standoff": _AS_STANDOFF}


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
    y_vanaf_nul: bool = False,
) -> tuple[str, go.Figure | None]:
    if data_key:
        df = store.get(data_key)
        if df is None:
            return fouten.onbekende_key(data_key), None
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
    title = schone_titel(title)
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

    # Titels en woorden uit de bron in plaats van kolomnamen en codes (#418); de rijen in
    # meta blijven zoals de bron ze geeft, voor de export.
    known = store.meta(data_key) if data_key else None
    titels = known.kolomtitels if known else None
    dataset = known.dataset if known else None
    x_labels = waardelabels(x, dataset)

    fig = go.Figure()
    show_labels = chart_type in ("bar", "line") and len(data) <= _MAX_LABELED_POINTS
    x_ruw = [row.get(x) for row in data]
    x_vals = leesbaar(x_ruw, x_labels)
    liggend = _liggend(chart_type, x, x_vals)
    # color_by op de x-kolom zelf (alleen om één staaf uit te lichten) gaf een reeks per staaf
    # en een legenda die de as herhaalt: dat is één reeks met een kleur per staaf.
    groepkolom = color_by if color_by != x else None

    if groepkolom:
        groups = _group_by_color(data, x, y, groepkolom)
        groep_labels = waardelabels(groepkolom, dataset)
        for i, (name, vals) in enumerate(groups.items()):
            if highlight:
                color = _PALETTE[0] if name == highlight else _HIGHLIGHT_GREY
            else:
                color = _PALETTE[i % len(_PALETTE)]
            _add_trace(
                fig,
                chart_type,
                leesbaar(vals["x"], x_labels),
                vals["y"],
                color,
                name=groep_labels.get(name, name),
                text=_value_labels(vals["y"], show_labels),
                liggend=liggend,
            )

        if chart_type == "bar":
            fig.update_layout(barmode="group")
        elif chart_type == "histogram":
            fig.update_layout(barmode="overlay")

    else:
        y_vals = [row.get(y) for row in data]
        uitlichten = highlight and chart_type == "bar"
        kleur = _accentkleuren(x_ruw, x_vals, highlight) if uitlichten else _PALETTE[0]
        _add_trace(fig, chart_type, x_vals, y_vals, kleur, text=_value_labels(y_vals, show_labels), liggend=liggend)

    layout = {
        **_LAYOUT_BASE,
        "title": {"text": title, "font": {"size": 16, "color": "#222"}},
        "legend_title": kolomlabel(groepkolom, titels) if groepkolom else "",
        "separators": _NL_SEPARATORS,
    }
    if not groepkolom:
        layout["showlegend"] = False

    if chart_type != "pie":
        categorie_as = {"title": _astitel(kolomlabel(x, titels)), "automargin": _AS_AUTOMARGIN, **_AXIS_STYLE}
        if _is_time_axis(x):
            # Jaartallen als categorie: geen 2.023,5-tussenticks met duizendtalpunt (#240).
            categorie_as.update(type="category", categoryorder="category ascending")
        waarde_as = {
            "title": _astitel(kolomlabel(y, titels)),
            "tickformat": ",",
            "automargin": _AS_AUTOMARGIN,
            **_AXIS_STYLE,
        }
        if y_vanaf_nul:
            # Op verzoek van de gebruiker (#741): een lijn begint anders bij het kleinste getal, wat verschillen
            # groter laat lijken. Staven beginnen al op 0.
            waarde_as["rangemode"] = "tozero"
        if liggend:
            # De eerste rij bovenaan, zoals de agent de rijen sorteerde; de namen duwen de marge opzij.
            # Zonder astitel: de namen spreken voor zich, en op een telefoon viel de titel eroverheen.
            layout["yaxis"] = {**categorie_as, "title": {"text": ""}, "autorange": "reversed"}
            if any(t.text is not None for t in fig.data):
                # Elke staaf draagt zijn getal: een waardeas ernaast herhaalt dat, en kantelt op een telefoon.
                waarde_as.update(showticklabels=False, showgrid=False)
            layout["xaxis"] = waarde_as
            layout["height"] = _hoogte(len(set(x_vals)), max(len(fig.data), 1))
        else:
            layout["xaxis"] = categorie_as
            layout["yaxis"] = waarde_as
            if chart_type == "line":
                kop = kopruimte([{"y": list(t.y or []), "text": t.text} for t in fig.data])
                if kop is not None:
                    waarde_as["autorangeoptions"] = {"include": [kop]}

    fig.update_layout(**layout)
    fig.update_layout(
        meta={
            "data": data,
            "x": x,
            "y": y,
            "chart_type": chart_type,
            "color_by": color_by,
            "herkomst": herkomstregels(data_key) if data_key else [],
            **_dataset_meta(data_key),
            **_noot_meta(data_key),
        }
    )

    chart_label = _CHART_TYPE_LABELS.get(chart_type, "Grafiek")
    return f"{chart_label} '{title}' aangemaakt ({len(data)} datapunten).", fig


def _dataset_meta(data_key: str | None) -> dict:
    """Het dataset-id voor de CSV-naam van de grafiek, <titel>_<dataset-id>.csv (#533); leeg zonder bron."""
    known = store.meta(data_key) if data_key else None
    return {"dataset": known.dataset} if known else {}


def _noot_meta(data_key: str | None) -> dict:
    """Dezelfde afrondingsnoot als in tekst, KPI en export (#352), als platte tekst naast de figuur: de weergave
    zet hem als tekstregel onder de grafiek (#651). Als ondertitel in de figuur was hij niet te selecteren,
    op een telefoon te klein, en kostte hij bovenmarge (CH-34). Leeg zonder afronding."""
    noot = cbs_afronding.van_key(data_key) if data_key else None
    return {"afrondingsnoot": noot} if noot else {}


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


def leesbare_titels(fig: go.Figure, known: store.KeyMeta | None) -> go.Figure:
    """Een eigen figuur (run_analysis) zoals create_plot hem tekent: titels uit de bron
    in plaats van kolomnamen, de Nederlandse getalnotatie (#418) en de legenda onder de
    grafiek, tenzij de code hem zelf een plek gaf.

    Na with_export_rows: de exportrijen houden de bronnamen.
    """
    titels = known.kolomtitels if known else None
    for as_ in ("xaxis", "yaxis"):
        as_object = fig.layout[as_]
        if tekst := as_object.title.text:
            as_object.title.text = kolomlabel(tekst, titels)
        # Automargin en standoff komen normaal uit Plotly's template; zonder template overlapt de
        # legenda de astitel (#575). Alleen aanvullen wat de figuur zelf niet zette.
        aanvullen = {}
        if as_object.automargin is None:
            aanvullen["automargin"] = _AS_AUTOMARGIN
        if as_object.title.standoff is None:
            aanvullen["title"] = {"standoff": _AS_STANDOFF}
        if aanvullen:
            fig.update_layout({as_: aanvullen})
    if tekst := fig.layout.legend.title.text:
        fig.layout.legend.title.text = kolomlabel(tekst, titels)
    legenda = fig.layout.legend
    if legenda.x is None and legenda.y is None and legenda.orientation is None:
        fig.update_layout(legend=_LEGENDA_ONDER)
    fig.update_layout(separators=_NL_SEPARATORS)
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
    url = GEOJSON_URLS[level]
    if url not in _GEOJSON_CACHE:
        with urllib.request.urlopen(url, timeout=15) as resp:
            _GEOJSON_CACHE[url] = _json.loads(resp.read())
    return _GEOJSON_CACHE[url]


def kaartlabel(value_col: str, known: store.KeyMeta | None) -> str:
    """De titel van de kleurenbalk: de titel uit de bron, anders de leesbare kolomnaam."""
    return kolomlabel(value_col, known.kolomtitels if known else None)


# De getallen op een kaart zoals op een grafiekas: Nederlandse scheidingstekens, hele getallen op de kleurenbalk
# ("40.000", niet "40k"). Recept en app gebruiken dezelfde opmaak (#655).
KAART_GETALLEN = {"separators": _NL_SEPARATORS, "coloraxis_colorbar_tickformat": ","}


def kaart_hoverlabel(maat: str) -> str:
    """Wat een tik op een gebied toont: de naam vet, daaronder de maat met haar waarde ("Mbo-studenten: 41.500"),
    in plaats van Plotly's "Mbo-studenten=41.5k" (#655)."""
    return f"<b>%{{hovertext}}</b><br>{maat}: %{{z:,}}<extra></extra>"


def _kaartframe(rows: list[dict], location_col: str, code_van: dict[str, str], namen: dict[str, str]):
    """De rijen van de kaart met per rij de feature-id en de gebiedsnaam; zonder naam in de GeoJSON de waarde."""
    import pandas as pd

    df = pd.DataFrame(rows)
    codes = [code_van[row[location_col]] for row in rows]
    df[_KAARTCODE] = codes
    df[_KAARTNAAM] = [namen.get(code, row[location_col]) for code, row in zip(codes, rows, strict=True)]
    return df


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
            return fouten.onbekende_key(data_key), None
        data = df.to_dict(orient="records")
        if duo.is_prognose(store.meta(data_key)):
            # Dezelfde afronding als in de tekst, zodat grafiek en CSV hele personen tonen (#328).
            data = [{k: duo.json_waarde(v, afronden=True) for k, v in row.items()} for row in data]
    elif data:
        logger.info("create_choropleth_map zonder data_key aangeroepen, %d rijen", len(data))
    if not data:
        return "Geen data om op kaart te tonen. Geef de data_key van een query_data-resultaat mee.", None
    title = schone_titel(title)

    cleaned = [
        {**row, location_col: str(row.get(location_col, "")).strip()}
        for row in data
        if str(row.get(location_col, "")).strip() and row.get(value_col) is not None
    ]
    if not cleaned:
        return f"Kolommen '{location_col}' of '{value_col}' zijn leeg of niet gevonden.", None

    try:
        locaties = kaartlocaties.vertaal([row[location_col] for row in cleaned], level, _load_geojson)
    except kaartlocaties.Geweigerd as weigering:
        return str(weigering), None
    except Exception as exc:
        return f"GeoJSON laden mislukt: {exc}", None
    detected = locaties.niveau

    try:
        for row in cleaned:
            float(row[value_col])
    except (TypeError, ValueError):
        return f"Kolom '{value_col}' bevat geen getal-waarden.", None

    # Alleen wat op de kaart staat gaat mee; de rest staat in de melding. De kaart tekent op de feature-id,
    # de CSV houdt de waarde uit de data (#628) en het hoverlabel de naam van het gebied (#659).
    cleaned = [row for row in cleaned if row[location_col] in locaties.code_van]
    geojson = _load_geojson(detected)
    df = _kaartframe(cleaned, location_col, locaties.code_van, kaartlocaties.namen(geojson))
    known = store.meta(data_key) if data_key else None
    maat = kaartlabel(value_col, known)

    # Use px.choropleth_map (Plotly 6 maplibre renderer) — more reliable than geo projection
    # featureidkey='id' matches against the top-level GeoJSON feature id (e.g. 'PV20')
    fig = px.choropleth_map(
        df,
        geojson=geojson,
        locations=_KAARTCODE,
        hover_name=_KAARTNAAM,
        hover_data={_KAARTCODE: False},
        color=value_col,
        # De kleurenbalk en het hoverlabel heten naar de maat, zoals een grafiekas (#418, #640);
        # meta.value_col houdt de kolomnaam voor de CSV.
        labels={value_col: maat},
        featureidkey="id",
        title=title,
        **KAART_OPTIES,
    )
    fig.update_traces(hovertemplate=kaart_hoverlabel(maat))
    fig.update_layout(
        font={"family": "Inter, Arial, sans-serif", "size": 13},
        paper_bgcolor="white",
        margin={"t": 60, "b": 0, "l": 0, "r": 0},
        **KAART_GETALLEN,
        meta={
            "type": "choropleth",
            "geojson_url": GEOJSON_URLS.get(detected, ""),
            "location_col": location_col,
            "value_col": value_col,
            "data": cleaned,
            "herkomst": herkomstregels(data_key) if data_key else [],
            **_dataset_meta(data_key),
        },
    )

    label = kaartlocaties.NIVEAU_LABELS.get(detected, detected)
    aangemaakt = f"Kaart '{title}' aangemaakt ({len(cleaned)} {label})."
    totaal = len(locaties.code_van) + len(locaties.onbekend)
    return aangemaakt + kaartlocaties.melding_onbekend(locaties, totaal), fig
