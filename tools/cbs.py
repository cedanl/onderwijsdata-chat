import json
from functools import lru_cache

from onderwijsdata import data, dimension
from config import CBS_ROW_LIMIT


def get_cbs_data(dataset_id: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "$top" not in params:
        params["$top"] = CBS_ROW_LIMIT
    try:
        rows = data(dataset_id, **params)
    except Exception as e:
        return f"Fout bij ophalen CBS data: {e}"
    if not rows:
        return (
            f"Geen rijen gevonden in dataset '{dataset_id}' met filters {filters or {}}. "
            "Controleer de filtercodes via get_cbs_dimension — CBS gebruikt interne codes, geen leesbare labels."
        )
    result = json.dumps(rows[:CBS_ROW_LIMIT], ensure_ascii=False, separators=(",", ":"))
    if len(rows) >= CBS_ROW_LIMIT:
        result += f" // Resultaat afgekapt op {CBS_ROW_LIMIT} rijen. Verfijn je $filter of $select om volledigere data te krijgen."
    return result


@lru_cache(maxsize=256)
def get_cbs_dimension(dataset_id: str, dimension_name: str) -> str:
    try:
        values = dimension(dataset_id, dimension_name)
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return f"Fout bij ophalen dimensie: {e}"
