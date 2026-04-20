import json

from riodata import fetch


def get_rio_data(resource: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "pageSize" not in params:
        params["pageSize"] = 20
    try:
        results = fetch(resource, **params)
        return json.dumps(results[:20], ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return f"Fout bij ophalen RIO data: {e}"
