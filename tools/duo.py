import json

import pandas as pd
from riodata import duo as _duo

from . import store
from .catalog import catalogus_titel, resource_titel
from .duo_meta import teldefinitie

_SAMPLE_ROWS = 3


# Lokale glossary-correcties en -aanvullingen op riodata (zie #31, #23, #172).
# Deze patches worden toegepast op column_definitions() tot de upstream fix.
_GLOSSARY_PATCHES = {
    "STUDIEJAAR": "Startjaar van het studiejaar als geheel getal (2023 = studiejaar 2023/2024). Peildatum 1 oktober.",
    "LEERWEG": "Mbo-leerweg: BOL (beroepsopleidende leerweg) of BBL (beroepsbegeleidende leerweg).",
    # Ontbreekt upstream; zonder definitie raadde een model 'DT = duaal-tijd' (#172).
    "OPLEIDINGSVORM": "Opleidingsvorm hoger onderwijs: VT = voltijd, DT = deeltijd, DU = duaal (bron: DUO-datasetbeschrijving).",
}


def _apply_glossary_patches(defs: dict[str, str]) -> dict[str, str]:
    """Pas lokale correcties toe op riodata glossary-definities.

    Zie #31, #23: upstream bugs in STUDIEJAAR en LEERWEG definities in riodata;
    #172: OPLEIDINGSVORM ontbreekt upstream.
    Deze patches zorgen dat het schema correcte definities bevat totdat upstream dit
    adressen. Idempotent: kan veilig op al gepatched dicts worden toegepast.
    """
    return {**defs, **_GLOSSARY_PATCHES}


_DUO_SENTINELS = (-1,)

# Kolommen waarin -1 een geldige meetwaarde kan zijn in plaats van een onderdrukte cel.
# Niet beperken tot AANTAL*-kolommen: DUO kent pivot-datasets waarin de telling in de
# kolomnaam zit (DIPMAN2023, JAAR_2022 — zie prompts/system.md), en die zouden dan
# ongemaskeerd blijven.
_SIGNED_HINTS = ("MUTATIE", "SALDO", "VERSCHIL", "GROEI", "DELTA")

# Per store-key: aantal gemaskeerde cellen per rij en kolom, alleen voor rijen met
# minstens één (sparse). Per rij en niet per key, zodat query_data de telling met
# dezelfde filter/selectie/groupby als de data kan meenemen: de melding hoort bij de
# geselecteerde rijen, niet bij de hele dataset (#171). Na maskering is het aantal
# niet meer uit de data af te leiden: de -1'en zijn dan weg.
_sentinel_cells: dict[str, pd.DataFrame] = {}
_EMPTY_CELLS = pd.DataFrame()


def _is_maskable(df, col) -> bool:
    if not pd.api.types.is_numeric_dtype(df[col]):
        return False
    return not any(hint in str(col).upper() for hint in _SIGNED_HINTS)


def mask_sentinels(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vervang DUO-sentinels (-1) door pd.NA en geef per rij aan welke cellen dat waren.

    DUO markeert onderdrukte waarden (kleine aantallen) met -1. Die mogen nooit als
    telwaarde meedoen. De cellen worden bijgehouden omdat een onderdrukte cel betekent
    dat een totaal een ondergrens is: bij 2 onderdrukte cellen kan 300 in werkelijkheid
    hoger liggen, en dat moet de gebruiker kunnen zien.

    Geeft (gemaskeerde df, cellen) terug; `cellen` heeft de index van df, alleen rijen
    met minstens één sentinel, en per maskeerbare kolom het aantal (0/1).

    Wordt aangeroepen vanuit store.put() voor elke `duo:`-key, dus ook voor data die
    niet via get_duo_data binnenkomt. Idempotent: al gemaskeerde data levert niets op.
    """
    masks = {}
    for col in df.columns:
        if _is_maskable(df, col):
            mask = df[col].isin(_DUO_SENTINELS)
            if mask.any():
                masks[col] = mask
    if not masks:
        return df, _EMPTY_CELLS
    # Pas kopiëren als er echt iets te maskeren valt: put() draait dit op elke
    # DataFrame die de store in gaat, ook de al gemaskeerde.
    out = df.copy()
    for col, mask in masks.items():
        out.loc[mask, col] = pd.NA
    cells = pd.DataFrame(masks).astype(int)
    return out, cells[cells.any(axis=1)]


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
        return _EMPTY_CELLS
    return cells.loc[cells.index.intersection(df.index), [c for c in cells.columns if c in df.columns]]


def aggregate_cells(cells: pd.DataFrame, df: pd.DataFrame, group_by: list[str], agg: pd.DataFrame) -> pd.DataFrame:
    """Tel de cellen per groep op, uitgelijnd op de rijen van het aggregaat `agg`."""
    # Alleen geaggregeerde waardekolommen; een groepeerkolom zit al in df[group_by].
    cells = cells[[c for c in cells.columns if c in agg.columns and c not in group_by]]
    if cells.empty:
        return _EMPTY_CELLS
    per_group = cells.join(df[group_by]).groupby(group_by, dropna=False).sum().reset_index()
    rows = agg[group_by].reset_index().merge(per_group, on=group_by).set_index("index")
    rows.index.name = None
    return rows[list(cells.columns)]


def sentinel_notes(counts: dict[str, int]) -> list[str]:
    """Leesbare melding per kolom met onderdrukte cellen, voor in de tool-output."""
    return [
        f"{n} cellen met DUO-sentinel -1 in '{col}' uitgesloten "
        f"(betekent leeg/n.v.t., geen telwaarde) — totalen zijn hierdoor een ondergrens"
        for col, n in counts.items()
    ]


def resource_sentinel_notes(counts: dict[str, int]) -> list[str]:
    """Melding voor get_duo_data: telling over de hele resource, niet over een selectie.

    Geen "ondergrens" hier: of een getal dat wordt, hangt af van de rijen die het
    model straks selecteert, en dat meldt query_data per selectie (#179).
    """
    return [
        f"{n} cellen met DUO-sentinel -1 in '{col}' in de hele resource (betekent "
        f"leeg/n.v.t., geen telwaarde; worden als leeg behandeld, rijen blijven staan). "
        f"Zegt niets over een gefilterd totaal: query_data meldt per selectie welke -1-cellen erin vallen"
        for col, n in counts.items()
    ]


def get_duo_data(dataset_id: str, resource: int | str = 0) -> str:
    key = f"duo:{dataset_id}:{resource}"

    df = store.get(key)
    if df is None:
        try:
            df = _duo.load(dataset_id, resource)
        except Exception as e:
            try:
                cats = _duo.catalog()
                matches = [c for c in cats if dataset_id.lower() in json.dumps(c, ensure_ascii=False).lower()]
                hint = f" Vergelijkbare datasets: {[c.get('_ckan_id') for c in matches[:3]]}" if matches else ""
            except Exception:
                hint = ""
            return f"Fout bij laden DUO dataset '{dataset_id}': {e}.{hint}"
        meta = store.KeyMeta(bron="duo", dataset=dataset_id, resource=resource, teldefinitie=teldefinitie(dataset_id))
        store.put(key, df, meta)
        # put() maskeert een kopie, dus de lokale df is nog ongemaskeerd: schema en
        # preview moeten van de versie komen die daadwerkelijk is opgeslagen.
        df = store.get(key)

    defs = _apply_glossary_patches(_duo.column_definitions(list(df.columns)))
    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": df[col].dropna().unique()[:3].tolist(),
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
    definitie = teldefinitie(dataset_id)
    if definitie:
        result["teldefinitie"] = definitie
    notes = resource_sentinel_notes(count_cells(_sentinel_cells.get(key)))
    if notes:
        result["databewerking"] = notes

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


