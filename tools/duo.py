import json

from riodata import duo as _duo
from . import store

_SAMPLE_ROWS = 3


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
        store.put(key, df)

    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": df[col].dropna().unique()[:3].tolist(),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")

    return json.dumps(
        {"data_key": key, "totaal_rijen": len(df), "kolommen": schema, "preview": preview},
        ensure_ascii=False, separators=(",", ":"), default=str,
    )


def query_duo_data(
    data_key: str,
    filters: dict | None = None,
    columns: list[str] | None = None,
    max_rows: int = 500,
) -> str:
    df = store.get(data_key)
    if df is None:
        return f"Geen data gevonden voor '{data_key}'. Roep eerst get_duo_data aan."

    if filters:
        for col, val in filters.items():
            if col not in df.columns:
                return f"Kolom '{col}' bestaat niet. Beschikbare kolommen: {list(df.columns)}"
            df = df[df[col].astype(str).str.lower() == str(val).lower()]

    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return f"Kolommen niet gevonden: {missing}. Beschikbaar: {list(df.columns)}"
        df = df[columns]

    total = len(df)
    rows = df.head(max_rows).to_dict(orient="records")
    result: dict = {"totaal_rijen": total, "rijen": rows}
    if total > max_rows:
        result["waarschuwing"] = f"Eerste {max_rows} van {total} rijen teruggegeven. Verfijn je filters."

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
