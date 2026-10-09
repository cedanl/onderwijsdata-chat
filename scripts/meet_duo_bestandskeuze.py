#!/usr/bin/env python
"""
Meet per DUO-ho-groep welk bestand leidend is voor een totaal per instelling (#325).

Gebruik:
    uv run scripts/meet_duo_bestandskeuze.py

Draai dit na een catalogusbump of een nieuwe DUO-jaargang. Per groep in
tools/duo_bestandskeuze._GROEPEN (alleen de ho-datasets: één maatkolom in lange vorm):
  1. Laadt elk bestand en telt per (jaar, instelling) het totaal zonder -1-cellen
  2. Telt per bestand hoeveel het in totaal onder het hoogste bestand blijft
  3. Meldt of het bestand met het kleinste tekort het eerste ID van de groep is

Exitcode 1 als een groep een ander leidend bestand heeft dan de code.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from riodata import duo

from tools import duo_bestandskeuze, duo_meta

_HO = ("p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl")


def _totalen(df: pd.DataFrame) -> pd.Series:
    maat = next(c for c in df.columns if c.startswith("AANTAL"))
    jaar = next(c for c in ("STUDIEJAAR", "DIPLOMAJAAR") if c in df.columns)
    gepubliceerd = df[df[maat] != -1]
    return gepubliceerd.groupby([jaar, "INSTELLINGSCODE_ACTUEEL"])[maat].sum()


def main() -> int:
    warnings.filterwarnings("ignore")
    afwijkend = 0
    for dataset_id in _HO:
        bestanden = duo_meta.record(dataset_id)["_resources"]
        index = {r["id"]: i for i, r in enumerate(bestanden)}
        for groep in duo_bestandskeuze._GROEPEN[dataset_id]:
            totalen = pd.DataFrame({i: _totalen(duo.load(dataset_id, index[i])) for i in groep}).fillna(0)
            tekort = totalen.max(axis=1).to_frame().values - totalen
            som = tekort.sum().astype(int)
            beste = som.idxmin()
            print(f"{dataset_id}: leidend {'ok' if beste == groep[0] else 'ANDERS'}")
            for i in groep:
                teken = "*" if i == groep[0] else " "
                print(f"  {teken} {index[i]} tekort {som[i]:>5}  {bestanden[index[i]]['naam'][:70]}")
            afwijkend += beste != groep[0]
    return 1 if afwijkend else 0


if __name__ == "__main__":
    sys.exit(main())
