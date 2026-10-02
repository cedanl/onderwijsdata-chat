# ============================================================
# Onderzoeksvraag: Welke 3 provincies hadden de grootste absolute daling in het totale aantal mbo-studenten tussen 2024/'25 en 2025/'26?
# Bron: CBS - Mbo; studenten, niveau, leerweg, studierichting, regiokenmerken
# Dataset: 85353NED
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_calc_02(
    data_path=Path("data/raw/85353NED-202604090000/Observations.csv")
):
    df = pd.read_csv(data_path, sep=";", encoding="utf-8-sig", dtype=str)
    df["Value"] = pd.to_numeric(df["Value"], errors="raise")

    provincie_map = {
        "PV20": "Groningen",
        "PV21": "Fryslan",
        "PV22": "Drenthe",
        "PV23": "Overijssel",
        "PV24": "Flevoland",
        "PV25": "Gelderland",
        "PV26": "Utrecht",
        "PV27": "Noord-Holland",
        "PV28": "Zuid-Holland",
        "PV29": "Zeeland",
        "PV30": "Noord-Brabant",
        "PV31": "Limburg",
    }

    df = df.loc[
        (df["Measure"] == "M003171")
        & (df["Geslacht"] == "T001038")
        & (df["Niveau"] == "T001336")
        & (df["Leerweg"] == "A025290")
        & (df["Studierichting"] == "T001072")
        & (df["Regio"].isin(provincie_map))
    ].copy()

    laatste_perioden = sorted(df["Perioden"].dropna().unique())[-2:]
    df = df.loc[df["Perioden"].isin(laatste_perioden)]

    pivot = df.pivot(index="Regio", columns="Perioden", values="Value").reset_index()
    vorig_jaar, laatste_jaar = laatste_perioden
    pivot["Provincie"] = pivot["Regio"].map(provincie_map)
    pivot["daling"] = pivot[laatste_jaar] - pivot[vorig_jaar]
    pivot["daling_pct"] = pivot["daling"] / pivot[vorig_jaar] * 100

    top3 = pivot.sort_values("daling").head(3)
    return [
        {
            "provincie": str(row["Provincie"]),
            "vorig_schooljaar": vorig_jaar,
            "laatste_schooljaar": laatste_jaar,
            "vorig_aantal": int(row[vorig_jaar]),
            "laatste_aantal": int(row[laatste_jaar]),
            "daling": int(row["daling"]),
            "daling_pct": round(float(row["daling_pct"]), 2),
        }
        for _, row in top3.iterrows()
    ]


if __name__ == "__main__":
    print(ground_truth_calc_02())