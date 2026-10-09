#!/usr/bin/env python
"""
Genereer data/arbeidsmarktregio_gemeente.json: per gemeente de arbeidsmarktregio (#454).

Gebruik:
    uv run scripts/refresh_arbeidsmarktregio.py [TABEL]

TABEL is de CBS-tabel "Gebieden in Nederland <jaar>" (standaard 86247NED, 2026). Draai dit
opnieuw als CBS een nieuwe jaargang publiceert (gemeentelijke herindelingen).

Het script:
  1. Haalt per gemeente de code en de arbeidsmarktregio uit de CBS-tabel
  2. Controleert dat ROA elke regionaam kent (get_roa_benchmark weigert anders)
  3. Schrijft het resultaat met de bron naar data/arbeidsmarktregio_gemeente.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import arbeidsmarkt

OUTPUT = ROOT / "data" / "arbeidsmarktregio_gemeente.json"
ODATA = "https://opendata.cbs.nl/ODataApi/odata/{tabel}/{deel}"


def _odata(tabel: str, deel: str, **params) -> list[dict]:
    r = httpx.get(ODATA.format(tabel=tabel, deel=deel), params={"$format": "json", **params}, timeout=60)
    r.raise_for_status()
    return r.json()["value"]


def _kolom(eigenschappen: list[dict], groep: str, titel: str) -> str:
    """De sleutel van kolom `titel` onder `groep`: de sleutels (Code_4, Naam_5) schuiven per jaargang."""
    groep_id = next(e["ID"] for e in eigenschappen if e["Title"] == groep)
    return next(e["Key"] for e in eigenschappen if e.get("ParentID") == groep_id and e["Title"] == titel)


def main(tabel: str = "86247NED") -> None:
    info = _odata(tabel, "TableInfos")[0]
    eigenschappen = _odata(tabel, "DataProperties")
    regio = _kolom(eigenschappen, "Arbeidsmarktregio's", "Naam")
    rijen = _odata(tabel, "TypedDataSet", **{"$select": f"RegioS,{regio}"})

    gemeenten = {
        r["RegioS"].strip().removeprefix("GM"): r[regio].strip() for r in rijen if r["RegioS"].startswith("GM")
    }
    onbekend = sorted(set(gemeenten.values()) - set(arbeidsmarkt.roa_regios()))
    if onbekend:
        sys.exit(f"ROA kent deze arbeidsmarktregio's niet: {onbekend}")

    OUTPUT.write_text(
        json.dumps(
            {
                "_bron": {
                    "tabel": tabel,
                    "titel": info["Title"],
                    "url": f"https://opendata.cbs.nl/statline/#/CBS/nl/dataset/{tabel}",
                    "opgehaald": date.today().isoformat(),
                },
                "gemeenten": dict(sorted(gemeenten.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"{len(gemeenten)} gemeenten, {len(set(gemeenten.values()))} arbeidsmarktregio's → {OUTPUT}")


if __name__ == "__main__":
    main(*sys.argv[1:])
