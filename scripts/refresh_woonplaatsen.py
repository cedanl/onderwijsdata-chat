#!/usr/bin/env python
"""
Genereer data/woonplaatsen.json: per woonplaats de gemeente, per gemeente de naam en de provincie (#744).

Gebruik:
    .venv/bin/python scripts/refresh_woonplaatsen.py [TABEL]

TABEL is de CBS-tabel "Woonplaatsen in Nederland <jaar>" (standaard 86312NED, 2026). Draai dit opnieuw als CBS een
nieuwe jaargang publiceert (gemeentelijke herindelingen), samen met scripts/refresh_arbeidsmarktregio.py.

De plaatsnamen van RIO en DUO's mbo_opleidingsaanbod zijn de woonplaatsen van de BAG, dezelfde namen als hier (nagegaan
op 05-11-2026: alle plaatsen van de 570 mbo-locaties staan erin). Een naam kan bij meer gemeenten horen (Velp: Rheden
en Land van Cuijk); het bestand houdt ze dan allemaal, de lezer raadt niet.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "woonplaatsen.json"
ODATA = "https://opendata.cbs.nl/ODataApi/odata/{tabel}/{deel}"


def _odata(tabel: str, deel: str, **params) -> list[dict]:
    r = httpx.get(ODATA.format(tabel=tabel, deel=deel), params={"$format": "json", **params}, timeout=60)
    r.raise_for_status()
    return r.json()["value"]


def _kolom(eigenschappen: list[dict], groep: str, titel: str) -> str:
    """De sleutel van kolom `titel` onder `groep`: de sleutels (Naam_2, Code_3) schuiven per jaargang."""
    groep_id = next(e["ID"] for e in eigenschappen if e["Title"].strip() == groep)
    return next(e["Key"] for e in eigenschappen if e.get("ParentID") == groep_id and e["Title"].strip() == titel)


def main(tabel: str = "86312NED") -> None:
    info = _odata(tabel, "TableInfos")[0]
    eigenschappen = _odata(tabel, "DataProperties")
    gemeentenaam, gemeentecode = _kolom(eigenschappen, "Gemeente", "Naam"), _kolom(eigenschappen, "Gemeente", "Code")
    provinciecode = _kolom(eigenschappen, "Provincie", "Code")
    namen = {w["Key"].strip(): w["Title"].strip() for w in _odata(tabel, "Woonplaatsen")}

    woonplaatsen: dict[str, set[str]] = {}
    gemeenten: dict[str, dict[str, str]] = {}
    for rij in _odata(tabel, "TypedDataSet"):
        code = rij[gemeentecode].strip().removeprefix("GM")
        woonplaatsen.setdefault(namen[rij["Woonplaatsen"].strip()], set()).add(code)
        gemeenten[code] = {"naam": rij[gemeentenaam].strip(), "provincie": rij[provinciecode].strip()}

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
                "woonplaatsen": {naam: sorted(codes) for naam, codes in sorted(woonplaatsen.items())},
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )
    print(f"{len(woonplaatsen)} woonplaatsen in {len(gemeenten)} gemeenten → {OUTPUT}")


if __name__ == "__main__":
    main(*sys.argv[1:])
