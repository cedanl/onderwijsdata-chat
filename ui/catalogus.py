import json
from collections import Counter

from tools import search_catalog
from tools.catalog import _cbs as _cbs_catalog, _rio_duo as _rio_duo_catalog


def catalogus_overview() -> str:
    cbs = _cbs_catalog()
    rio_duo = _rio_duo_catalog()
    duo = [e for e in rio_duo if str(e.get("leverancier", "")).upper() == "DUO"]
    rio = [e for e in rio_duo if str(e.get("leverancier", "")).upper() == "RIO"]

    def top_categories(entries: list, n: int = 5) -> str:
        counts = Counter(e.get("categorie", "Overig") for e in entries)
        return ", ".join(k for k, _ in counts.most_common(n))

    rio_bronnen = ", ".join(e.get("bron", "") for e in rio[:6])
    if len(rio) > 6:
        rio_bronnen += f" en {len(rio) - 6} meer"

    return (
        f"**Catalogus** — {len(cbs) + len(duo) + len(rio)} datasets en registers beschikbaar\n\n"
        f"**CBS** — {len(cbs)} datasets\n"
        f"Statistieken van het Centraal Bureau voor de Statistiek\n"
        f"Categorieën: {top_categories(cbs)}\n\n"
        f"**DUO** — {len(duo)} datasets\n"
        f"Open data via onderwijsdata.duo.nl\n"
        f"Categorieën: {top_categories(duo)}\n\n"
        f"**RIO** — {len(rio)} registers\n"
        f"Register van onderwijsinstellingen en opleidingen (dagelijks bijgewerkt)\n"
        f"Registers: {rio_bronnen}\n\n"
        "Zoek specifiek: typ `/catalogus` gevolgd door een zoekterm, bijv. `/catalogus mbo instroom`."
    )


def catalogus_search(query: str) -> str:
    raw = search_catalog(query, source="both", top_n=8)
    if not raw.startswith("["):
        return raw
    results = json.loads(raw)
    lines = [f"**Catalogus** — {len(results)} resultaten voor '{query}'\n"]
    for r in results:
        leverancier = r.get("leverancier", "?")
        bron = r.get("bron", "?")
        periode = r.get("periode", "")
        doel = r.get("doel", r.get("beschrijving", ""))
        if len(doel) > 130:
            doel = doel[:130] + "…"
        ref = r.get("_cbs_id") or r.get("_ckan_id") or r.get("_rio_resource") or ""
        ref_str = f" `{ref}`" if ref else ""
        lines.append(f"**{leverancier} — {bron}**{ref_str}")
        if periode:
            lines.append(f"📅 {periode}")
        if doel:
            lines.append(doel)
        lines.append("")
    return "\n".join(lines).rstrip()
