"""Rekent de KPI over de selectie die de beurt maakte? (#319)

Harness-vergelijking §4.3: het model filterde op de instelling en rekende de KPI
daarna over de ongefilterde key. Het getal staat in de tooluitvoer, dus de
getalcontrole ziet niets; alleen `bron.aantal_waarden` verraadde de hele bron.
Noemt de tekst een KPI over een laadkey terwijl de beurt een filter op die key
maakte, dan is de scope waarschijnlijk verkeerd.

Waarschijnlijk, niet zeker: geeft dezelfde KPI over het filter hetzelfde getal,
dan maakt de scope voor dat getal niet uit (CH-01, wo-cbs-afronding: -8.700 over
344.630 → 335.930 werd gemeld terwijl het antwoord klopte). De code rekent dat na.
"""

import json

from tools import store
from tools.kpi import compute_kpi

from .kpi_bron import bereik
from .kpi_periode import noemt
from .probleem import Probleem
from .selectie import data_keys, laadkey, selectie_in_woorden


def _kpis(tool_results: list[str]) -> list[dict]:
    kpis = []
    for result in tool_results:
        try:
            data = json.loads(result)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict) and "value" in data and isinstance(data.get("bron"), dict):
            kpis.append(data)
    return kpis


def _zelfde_op_filter(kpi: dict, filters: list[str]) -> bool:
    """Geeft de KPI, over dezelfde kolom, maat en periode, op een van de filters hetzelfde getal?"""
    bron = kpi["bron"]
    jaren = bereik(kpi) if "periode" in kpi else None
    van, tot = jaren or (None, None)
    for key in filters:
        opnieuw = json.loads(
            compute_kpi(key, bron.get("kolom", ""), bron.get("metric", ""), bron.get("sort_column"), van=van, tot=tot)
        )
        if opnieuw.get("value") == kpi["value"]:
            return True
    return False


def kpi_naast_filter(tekst: str, tool_results: list[str]) -> list[str]:
    filters: dict[str, list[str]] = {}
    for key in data_keys(tool_results):
        if (known := store.meta(key)) and known.afgeleid_van:
            filters.setdefault(laadkey(key), []).append(key)
    problemen = []
    for kpi in _kpis(tool_results):
        key = kpi["bron"].get("data_key")
        if not key or key not in filters or not noemt(tekst, kpi["value"]):
            continue
        if _zelfde_op_filter(kpi, filters[key]):
            continue
        n = kpi["bron"].get("aantal_waarden")
        # De gebruiker leest bron en periode in woorden, het model de keys (CH-30).
        selectie = selectie_in_woorden(key) or "de opgehaalde data"
        aantal = f", {n} waarden" if n is not None else ""
        problemen.append(
            Probleem(
                f"{kpi['value']} rekent over de hele selectie ({selectie}{aantal}), "
                "niet over het filter dat het antwoord daarop maakte.",
                f"Hele selectie: {key}; filter: {', '.join(sorted(set(filters[key])))}. "
                "Reken de KPI over de gefilterde data_key, of zeg dat het getal over de hele selectie gaat.",
            )
        )
    return list(dict.fromkeys(problemen))
