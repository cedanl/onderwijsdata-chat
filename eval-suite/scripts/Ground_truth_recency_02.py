# ============================================================
# Onderzoeksvraag: Hoeveel mbo-diploma's zijn in het laatst beschikbare jaar uitgereikt in Nederland?
# Bron: CBS - Mbo; gediplomeerden, niveau, leerweg, studierichting, regiokenmerken
# Dataset: 85356NED
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_recency_02(
    data_path=Path("data/raw/85356NED-202602050000/Observations.csv"),
):
    df = pd.read_csv(data_path, sep=";", encoding="utf-8-sig", dtype=str)
    df["Value"] = pd.to_numeric(df["Value"], errors="raise")

    nationaal_totaal = df.loc[
        (df["Measure"] == "A025290")
        & (df["Geslacht"] == "T001038")
        & (df["Niveau"] == "T001336")
        & (df["Leerweg"] == "A025290")
        & (df["Studierichting"] == "T001072")
        & (df["Regio"] == "NL01")
    ].sort_values("Perioden")

    return int(nationaal_totaal.iloc[-1]["Value"])


if __name__ == "__main__":
    print(ground_truth_recency_02())