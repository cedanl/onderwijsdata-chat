import json

from riodata import duo as _duo

_MAX_ROWS = 200


def get_duo_data(dataset_id: str, resource: int | str = 0, max_rows: int = _MAX_ROWS) -> str:
    try:
        df = _duo.load(dataset_id, resource)
    except Exception as e:
        # Help agent find the right dataset_id
        try:
            cats = _duo.catalog()
            matches = [c for c in cats if dataset_id.lower() in json.dumps(c, ensure_ascii=False).lower()]
            hint = f" Vergelijkbare datasets: {[c.get('_ckan_id') for c in matches[:3]]}" if matches else ""
        except Exception:
            hint = ""
        return f"Fout bij laden DUO dataset '{dataset_id}': {e}.{hint}"

    rows = df.head(max_rows).to_dict(orient="records")
    total = len(df)
    result = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)

    if total > max_rows:
        result += f' // Eerste {max_rows} van {total} rijen. Gebruik max_rows of filter de dataset.'

    return result
