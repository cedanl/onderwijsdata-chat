#!/usr/bin/env python
"""
Meet hoeveel instellingen van de Studiekeuzedatabase het dashboard Opleidingen bereikt (#980).

Gebruik:
    .venv/bin/python scripts/meet_skdb_dekking.py                 # export via STUDIEKEUZEDATABASE_API_KEY
    .venv/bin/python scripts/meet_skdb_dekking.py --zip export.zip # een export van schijf

Twee maten, los van elkaar:
  1. Registerdekking: de instellingen van de export waarvan de BRIN-code in het DUO-register staat. De rest (de
     niet-bekostigde hogescholen, Nyenrode, de Open Universiteit) krijgt op het dashboard de grensmelding
     (`dashboard_opleidingen.BUITEN_REGISTER`), geen cijfers.
  2. Naamdekking: van die instellingen de namen uit de export die het register niet als naam of alias kent. Zo'n
     naam hoort als alias in `data/instellingen.ALIASSEN`.

De numerieke juistheid (de cijfers per opleiding) meten tests/test_dashboard_opleidingen.py op de proefexport en de
onafhankelijke herberekening van de SKDB-audit; dit script rekent geen cijfers.

Het register komt uit live DUO. Exitcode 1 als er namen zonder alias zijn.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from onderwijsbronnen import skdb

from data import instellingen


def dekking(export: skdb.Export) -> dict[str, list[dict]]:
    """De instellingen van de export in drie groepen: `bereikt` (BRIN in het register en de naam gekend),
    `naam_onbekend` (BRIN in het register, de naam niet; met de registernaam) en `buiten_register`."""
    per_code = {code: i["naam"] for i in instellingen.get_all() for code in i["instellingscodes"]}
    uit: dict[str, list[dict]] = {"bereikt": [], "naam_onbekend": [], "buiten_register": []}
    for inst in skdb.instellingen(export):
        registernaam = per_code.get(inst["brin"])
        if registernaam is None:
            uit["buiten_register"].append(inst)
            continue
        profiel = instellingen.instellingsprofiel(inst["naam"])
        gekend = profiel is not None and profiel["naam"] == registernaam
        uit["bereikt" if gekend else "naam_onbekend"].append({**inst, "registernaam": registernaam})
    return uit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", type=Path, help="een export-ZIP van schijf in plaats van een download")
    args = parser.parse_args()
    if args.zip:
        inhoud = args.zip.read_bytes()
        export = skdb.lees(inhoud, skdb.herkomst(inhoud, args.zip.name))
    else:
        export = skdb.lees(*skdb.haal_op())
    groepen = dekking(export)
    in_register = len(groepen["bereikt"]) + len(groepen["naam_onbekend"])
    totaal = in_register + len(groepen["buiten_register"])
    print(f"{export.herkomst.bestand}: {totaal} instellingen")
    print(
        f"registerdekking: {in_register} met BRIN-code in het DUO-register, {len(groepen['buiten_register'])} erbuiten"
    )
    print(f"naamdekking: {len(groepen['bereikt'])} van {in_register} op hun naam uit de export")
    for inst in groepen["naam_onbekend"]:
        print(f"  zonder alias: {inst['brin']} {inst['naam']!r} -> {inst['registernaam']!r}")
    for inst in groepen["buiten_register"]:
        print(f"  buiten het register: {inst['brin']} {inst['naam']} ({inst['soort']}, {inst['bekostiging']})")
    return 1 if groepen["naam_onbekend"] else 0


if __name__ == "__main__":
    sys.exit(main())
