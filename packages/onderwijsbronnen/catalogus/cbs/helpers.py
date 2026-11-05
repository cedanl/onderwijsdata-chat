"""
Gedeelde helperfuncties voor catalogus.py en uitbreiden.py.
"""


def _infer_geo_niveau(bron: str, dims: list[str]) -> list[str]:
    if "RegioS" not in dims:
        return []
    bron_lower = bron.lower()
    if "regiokenmerken" in bron_lower:
        return ["landelijk", "corop", "provincie", "gemeente"]
    if "woonregio" in bron_lower:
        return ["landelijk", "provincie", "gemeente"]
    if "gemeente" in bron_lower:
        return ["gemeente"]
    if "provincie" in bron_lower:
        return ["provincie"]
    return ["landelijk", "provincie"]


_KALENDERJAAR_THEMAS = frozenset({
    "financiering en uitgaven onderwijs",
    "onderwijs en arbeidsmarkt",
    "onderwijsniveau bevolking",
})


def _infer_perioden_formaat(freq: str, theme_name: str) -> list[str]:
    freq_lower = freq.lower()
    if "stopgezet" in freq_lower:
        return []
    if "maand" in freq_lower:
        return ["MM"]
    if "kwartaal" in freq_lower:
        return ["KW"]
    if theme_name.lower() in _KALENDERJAAR_THEMAS:
        return ["JJ"]
    return ["SJ"]


def meetwaarden_uit_properties(props: list[dict]) -> tuple[list[str], dict[str, dict]]:
    """Splits DataProperties in officiële meetwaardesleutels en presentatiedetails.

    Retourneert (keys, details): keys is de technische identiteit (bruikbaar in
    $select), details is key → {title, unit, description, datatype, decimals}.
    Topics zonder Key worden overgeslagen; een titel is geen geldige sleutel.
    """
    keys: list[str] = []
    details: dict[str, dict] = {}
    for p in props:
        if p.get("Type") != "Topic":
            continue
        key = (p.get("Key") or "").strip()
        if not key:
            continue
        keys.append(key)
        details[key] = {
            "title": (p.get("Title") or "").strip(),
            "unit": (p.get("Unit") or "").strip(),
            "description": (p.get("Description") or "").strip(),
            "datatype": (p.get("Datatype") or "").strip(),
            "decimals": p.get("Decimals"),
        }
    return keys, details
