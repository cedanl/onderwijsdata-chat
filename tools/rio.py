import json

from riodata import fetch
from config import RIO_PAGE_SIZE


def get_rio_data(resource: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "pageSize" not in params:
        params["pageSize"] = RIO_PAGE_SIZE
    try:
        results = fetch(resource, **params)
        return json.dumps(results[:RIO_PAGE_SIZE], ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return f"Fout bij ophalen RIO data: {e}"
