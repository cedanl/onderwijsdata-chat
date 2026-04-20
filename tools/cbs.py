import json

from onderwijsdata import data, dimension


def get_cbs_data(dataset_id: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "$top" not in params:
        params["$top"] = 20
    try:
        rows = data(dataset_id, **params)
        return json.dumps(rows[:20], ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return f"Fout bij ophalen CBS data: {e}"


def get_cbs_dimension(dataset_id: str, dimension_name: str) -> str:
    try:
        values = dimension(dataset_id, dimension_name)
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return f"Fout bij ophalen dimensie: {e}"
