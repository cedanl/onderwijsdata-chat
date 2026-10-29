"""Ververs de bevroren DUO-bestanden waarop de instellings- en dashboardtests draaien (#766).

De pytest-job blokkeert elke MR; met live DUO-data viel hij om bij elke storing van onderwijsdata.duo.nl.
Dit script haalt de bestanden die `data/instellingen.py` en `data/dashboard.py` laden één keer op,
houdt alleen de rijen van een handvol instellingen over (plus de volledige, kleine adresbestanden)
en schrijft ze naar `tests/fixtures/duo/`. `tests/conftest.py` (fixture `duo_fixtures`) leest ze in
plaats van `duo.load`.

    .venv/bin/python scripts/duo_testfixtures.py

Draai het na een wijziging aan de DUO-bestanden die de tests raken, en commit de nieuwe bestanden.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from riodata import duo

MAP = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "duo"

# De instellingen die de tests bij naam noemen, plus een buur in dezelfde arbeidsmarktregio
# zodat de regiobenchmark iets te vergelijken heeft (HKU en UU naast HU, Zadkine naast Albeda).
HO = {
    "25DW": "Hogeschool Utrecht",
    "00MF": "Hogeschool voor de Kunsten Utrecht",
    "21PD": "Universiteit Utrecht",
    "21PL": "Vrije Universiteit Amsterdam",
    "21PK": "Universiteit van Amsterdam",
    "28DN": "Hogeschool van Amsterdam",
    "21PF": "Technische Universiteit Delft",
    "14NI": "Codarts, Hogeschool voor de Kunsten",
    "27UM": "De Haagse Hogeschool",
}
MBO = {
    "27GZ": "ROC Mondriaan",
    "25LH": "ROC Midden Nederland",
    "25PJ": "Deltion College",
    "24ZZ": "ROC Graafschap College",
    "00GT": "Albeda",
    "25LP": "Zadkine",
    "23JA": "Grafisch Lyceum R'dam",
}
# De grote mbo-bestanden (instroom en diploma's per opleiding) alleen voor de mbo-instellingen
# waarvan de tests het dashboard openen, met hun regiobuur: anders worden de fixtures megabytes.
MBO_DASHBOARD = {"27GZ", "00GT", "25LP"}

# (dataset, resource) → (kolom met de instellingscode, de codes die blijven); None houdt het hele bestand.
ALLE = set(HO) | set(MBO)
BESTANDEN: dict[tuple[str, int], tuple[str, set[str]] | None] = {
    ("adressen_ho", 1): None,
    ("adressen_mbo", 1): None,
    ("p01hoinges", 0): ("INSTELLINGSCODE_ACTUEEL", ALLE),
    ("p01hoinges", 1): ("INSTELLINGSCODE_ACTUEEL", ALLE),
    ("p02ho1ejrs", 0): ("INSTELLINGSCODE_ACTUEEL", ALLE),
    ("p02ho1ejrs", 1): ("INSTELLINGSCODE_ACTUEEL", ALLE),
    ("p04hogdipl", 0): ("INSTELLINGSCODE_ACTUEEL", ALLE),
    ("p04hogdipl", 1): ("INSTELLINGSCODE_ACTUEEL", ALLE),
    ("mbo-studenten-per-instelling", 0): ("INSTELLINGSCODE", ALLE),
    ("gediplomeerde-mbo-studenten", 0): ("INSTELLINGSCODE", MBO_DASHBOARD),
    ("instromende-mbo-studenten", 0): ("INSTELLINGSCODE", MBO_DASHBOARD),
    ("instromende-mbo-studenten", 1): ("INSTELLINGSCODE", MBO_DASHBOARD),
    ("instromende-mbo-studenten", 3): ("INSTELLINGSCODE", MBO_DASHBOARD),
    ("instromende-mbo-studenten", 5): ("INSTELLINGSCODE", MBO_DASHBOARD),
    ("instromende-mbo-studenten", 7): ("INSTELLINGSCODE", MBO_DASHBOARD),
}


def bestandsnaam(dataset_id: str, resource: int) -> str:
    return f"{dataset_id}_{resource}.csv.gz"


def tekstkolommen(df: pd.DataFrame) -> list[str]:
    """Kolommen die als tekst terug moeten: codes als '0363' verliezen anders hun voorloopnul."""
    return [kolom for kolom in df.columns if not pd.api.types.is_numeric_dtype(df[kolom])]


def main() -> None:
    MAP.mkdir(parents=True, exist_ok=True)
    tekst: dict[str, list[str]] = {}
    for (dataset_id, resource), filter_ in BESTANDEN.items():
        df = duo.load(dataset_id, resource)
        if filter_:
            codekolom, codes = filter_
            df = df[df[codekolom].astype(str).isin(codes)]
        naam = bestandsnaam(dataset_id, resource)
        # mtime 0: dezelfde bron geeft hetzelfde bestand, dus geen lege diff bij verversen.
        df.to_csv(MAP / naam, index=False, compression={"method": "gzip", "mtime": 0})
        tekst[naam] = tekstkolommen(df)
        print(f"{naam}: {len(df)} rijen")
    (MAP / "tekstkolommen.json").write_text(json.dumps(tekst, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
