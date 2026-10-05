import json
import math

import pandas as pd
from riodata import duo as _duo

from core.sentinels import BETEKENIS, EMPTY_CELLS

from . import duo_meta, fouten, instelling, kolomprofiel, periode, store
from .catalog import catalogus_titel, resource_titel

_SAMPLE_ROWS = 3


# OPLEIDINGSVORM-codes, letterlijk uit de DUO-datasetbeschrijving: "VT voltijd onderwijs,
# DT deeltijd onderwijs en DU duaal onderwijs". Ook de antwoordcontrole leest ze (#196).
OPLEIDINGSVORMEN = {"VT": "voltijd", "DT": "deeltijd", "DU": "duaal"}
# Alleen deze beschrijvingen noemen die codes; mbo_opleidingsaanbod gebruikt bijv. KLASSIKAAL (#371).
OPLEIDINGSVORM_DATASETS = frozenset({"p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"})

# Definities die alleen de chat kent. Al het andere komt per dataset uit riodata (#371).
_STUDIEJAAR_LABEL_DEFINITIE = (
    "Volledig label van het studiejaar (2023 -> 2023/2024), afgeleid van STUDIEJAAR. "
    "Gebruik dit label in tekst, tabellen en grafieken; reken jaren niet zelf om."
)
# Ontbreekt upstream; zonder definitie raadde een model 'DT = duaal-tijd' (#172).
_OPLEIDINGSVORM_DEFINITIE = (
    "Opleidingsvorm hoger onderwijs: "
    + ", ".join(f"{code} = {vorm}" for code, vorm in OPLEIDINGSVORMEN.items())
    + " (bron: DUO-datasetbeschrijving)."
)


def column_definitions(columns: list[str], dataset_id: str) -> dict[str, str]:
    """Kolomdefinities voor deze dataset: riodata, aangevuld met wat alleen de chat kent."""
    defs = _duo.column_definitions(columns, dataset_id)
    if periode.STUDIEJAAR_LABEL in columns:
        defs[periode.STUDIEJAAR_LABEL] = _STUDIEJAAR_LABEL_DEFINITIE
    if "OPLEIDINGSVORM" in columns and dataset_id in OPLEIDINGSVORM_DATASETS:
        defs.setdefault("OPLEIDINGSVORM", _OPLEIDINGSVORM_DEFINITIE)
    return defs


# Per store-key: aantal gemaskeerde cellen per rij en kolom, alleen voor rijen met
# minstens één (sparse). Per rij en niet per key, zodat query_data de telling met
# dezelfde filter/selectie/groupby als de data kan meenemen: de melding hoort bij de
# geselecteerde rijen, niet bij de hele dataset (#171). Na maskering is het aantal
# niet meer uit de data af te leiden: de -1'en zijn dan weg. Het maskeren zelf staat
# in core.sentinels en gebeurt in store.put() voor elke `duo:`-key.
_sentinel_cells: dict[str, pd.DataFrame] = {}


def count_cells(cells: pd.DataFrame | None) -> dict[str, int]:
    """Aantal gemaskeerde cellen per kolom; kolommen zonder cellen vallen weg."""
    if cells is None or cells.empty:
        return {}
    return {col: int(n) for col, n in cells.sum().items() if n}


def record_sentinel_cells(key: str, cells: pd.DataFrame) -> None:
    """Leg vast welke cellen er voor deze key gemaskeerd zijn.

    Wordt door store.put() aangeroepen, zodat de telling er is ongeacht via welke route
    de data binnenkwam — niet alleen bij get_duo_data.
    """
    _sentinel_cells[key] = cells


def sentinel_cells(key: str) -> pd.DataFrame | None:
    """De gemaskeerde cellen van deze key; query_data neemt ze mee naar zijn selectie."""
    return _sentinel_cells.get(key)


def clear_sentinel_cells() -> None:
    """Hoort bij store.clear(): zonder dit blijven tellingen achter voor keys die weg zijn."""
    _sentinel_cells.clear()


def select_cells(cells: pd.DataFrame | None, df: pd.DataFrame) -> pd.DataFrame:
    """Beperk de cellen tot de rijen en kolommen die in de selectie `df` zitten."""
    if cells is None or cells.empty:
        return EMPTY_CELLS
    return cells.loc[cells.index.intersection(df.index), [c for c in cells.columns if c in df.columns]]


def aggregate_cells(cells: pd.DataFrame, df: pd.DataFrame, group_by: list[str], agg: pd.DataFrame) -> pd.DataFrame:
    """Tel de cellen per groep op, uitgelijnd op de rijen van het aggregaat `agg`."""
    # Alleen geaggregeerde waardekolommen; een groepeerkolom zit al in df[group_by].
    cells = cells[[c for c in cells.columns if c in agg.columns and c not in group_by]]
    if cells.empty:
        return EMPTY_CELLS
    per_group = cells.join(df[group_by]).groupby(group_by, dropna=False).sum().reset_index()
    rows = agg[group_by].reset_index().merge(per_group, on=group_by).set_index("index")
    rows.index.name = None
    return rows[list(cells.columns)]


def sentinel_notes(counts: dict[str, int]) -> list[str]:
    """Leesbare melding per kolom met onderdrukte cellen, voor in de tool-output."""
    return [
        f"{n} cellen met DUO-sentinel -1 in '{col}' uitgesloten ({BETEKENIS}) — totalen zijn hierdoor een ondergrens"
        for col, n in counts.items()
    ]


PROGNOSE_NOOT = (
    "Prognose-aantallen afgerond op hele personen: een prognose heeft geen decimale precisie. "
    "Berekeningen (compute_kpi) gebruiken de onafgeronde waarden."
)


def is_prognose(known: store.KeyMeta | None) -> bool:
    """DUO-prognosebestanden (voprognoses, wpoprognoses, studentprognoses-*) tellen in fracties (#247)."""
    return known is not None and "prognose" in known.dataset.lower()


def json_waarde(v, afronden: bool = False):
    """Een telling als telling: de -1-maskering maakt kolommen float, en 4147.0 belandde in antwoorden (#222).

    `afronden`: prognoses op hele personen (#247), half-naar-even zoals pandas' round in de snippet.
    Eén regel voor toolresultaat (query_data) en grafiekdata (create_plot, dus ook de CSV-export, #328).
    """
    if isinstance(v, float):
        if math.isnan(v):
            return None
        if afronden or v.is_integer():
            return round(v)
    return v


def resource_sentinel_notes(counts: dict[str, int]) -> list[str]:
    """Melding voor get_duo_data: telling over de hele resource, niet over een selectie.

    Geen "ondergrens" hier: of een getal dat wordt, hangt af van de rijen die het
    model straks selecteert, en dat meldt query_data per selectie (#179).
    """
    return [
        f"{n} cellen met DUO-sentinel -1 in '{col}' in de hele resource "
        f"({BETEKENIS}; worden als leeg behandeld, rijen blijven staan). "
        f"Zegt niets over een gefilterd totaal: query_data meldt per selectie welke -1-cellen erin vallen"
        for col, n in counts.items()
    ]


def geladen_profielen(dataset_id: str) -> dict[str, dict]:
    """Het kolomprofiel van elk bestand van deze dataset dat al geladen is, per resource-index.

    Voor dataset_details: zonder te downloaden, en een afgeleide key (een selectie) telt niet mee.
    """
    prefix = f"duo:{dataset_id}:"
    return {
        index: kolomprofiel.profiel(df, count_cells(_sentinel_cells.get(key)))
        for key in store.list_keys()
        if (index := key.removeprefix(prefix)) != key and index.isdigit() and (df := store.get(key)) is not None
    }


class MeerdereResources(ValueError):
    """Een resourcenaam past op meer dan één bestand; kiezen is aan de aanroeper (#382)."""


def _resource_index(dataset_id: str, resource: int | str) -> int | str:
    """The resource as its index, so one file has one store key however it is named (#21).

    In volgorde: een index, het stabiele resource-ID, de exacte naam, en een naamdeel dat
    op precies één bestand past. Een naamdeel dat op meerdere bestanden past koos eerst
    stilzwijgend het eerste (#382) — 'Ingeschrevenen' gaf de uitsplitsing naar geslacht —
    en geeft nu MeerdereResources. Onbekende namen blijven zoals gegeven, zodat de bron
    zelf de fout meldt.
    """
    if isinstance(resource, int) or resource.strip().isdigit():
        return int(resource)
    try:
        bestanden = _duo.resources(dataset_id)
    except Exception:
        return resource
    gezocht = resource.strip().lower()
    for veld in ("id", "naam"):
        if (i := next((i for i, r in enumerate(bestanden) if r.get(veld, "").lower() == gezocht), None)) is not None:
            return i
    treffers = [i for i, r in enumerate(bestanden) if gezocht in r.get("naam", "").lower()]
    if len(treffers) > 1:
        opties = ", ".join(f"{i} = '{bestanden[i]['naam']}'" for i in treffers)
        raise MeerdereResources(
            f"Resource '{resource}' past op meerdere bestanden van {dataset_id}: {opties}. "
            f"Kies er één met de index, bijv. get_duo_data('{dataset_id}', {treffers[0]})."
        )
    return treffers[0] if treffers else resource


def get_duo_data(dataset_id: str, resource: int | str = 0) -> str:
    try:
        resource = _resource_index(dataset_id, resource)
    except MeerdereResources as e:
        return str(e)
    key = f"duo:{dataset_id}:{resource}"

    df = store.get(key)
    if df is None:
        try:
            df = periode.met_studiejaarlabel(_duo.load(dataset_id, resource))
        except Exception as e:
            try:
                cats = _duo.catalog()
                matches = [c for c in cats if dataset_id.lower() in json.dumps(c, ensure_ascii=False).lower()]
                hint = f" Vergelijkbare datasets: {[c.get('_ckan_id') for c in matches[:3]]}" if matches else ""
            except Exception:
                hint = ""
            return fouten.bronfout("DUO", e, f" Dataset '{dataset_id}', resource {resource}.{hint}")
        kolom = periode.duo_periodekolom(df.columns)
        codekolom = instelling.codekolom(df.columns)
        meta = store.KeyMeta(
            bron="duo",
            dataset=dataset_id,
            resource=resource,
            teldefinitie=duo_meta.teldefinitie(duo_meta.record(dataset_id)),
            periodekolom=kolom,
            schooljaren=periode.dekking(df, "duo", kolom),
            instellingskolom=codekolom,
            instellingen=instelling.dekking(df, codekolom),
            laad=("get_duo_data", {"dataset_id": dataset_id, "resource": resource}),
        )
        store.put(key, df, meta)
        # put() maskeert een kopie, dus de lokale df is nog ongemaskeerd: schema en
        # preview moeten van de versie komen die daadwerkelijk is opgeslagen.
        df = store.get(key)

    defs = column_definitions(list(df.columns), dataset_id)
    min1 = count_cells(_sentinel_cells.get(key))
    profielen = kolomprofiel.profiel(df, min1)
    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            # Naast een bereik of een volledige waardenlijst zijn voorbeelden dubbel.
            **(
                {}
                if profielen[col].keys() & {"bereik", "waarden"}
                else {"voorbeelden": df[col].dropna().unique()[:3].tolist()}
            ),
            **profielen[col],
            **({"definitie": defs[col]} if col in defs else {}),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")

    result = {
        "data_key": key,
        "catalogus_titel": catalogus_titel(dataset_id),
        "resource_titel": resource_titel(dataset_id, resource),
        "totaal_rijen": len(df),
        "kolommen": schema,
        "preview": preview,
    }
    result.update(duo_meta.metadata(duo_meta.record(dataset_id)))
    known = store.meta(key)
    if known and known.schooljaren:
        result["beschikbare_schooljaren"] = periode.labels(known.schooljaren)
    notes = resource_sentinel_notes(min1)
    if notes:
        result["databewerking"] = notes

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
