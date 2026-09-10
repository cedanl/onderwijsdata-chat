# ============================================================
# Onderzoeksvraag: Wat is de gemiddelde jaarlijkse groei van het aantal WO-inschrijvingen in Nederland tussen 2015/'16 en 2023/'24?
# Bron: CBS OData API - Hoger onderwijs; ingeschrevenen, onderwijssoort, opleidingsfase en -vorm
# Dataset: 85423NED
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_calc_01(
    data_path=Path("data/raw/85423NED_UntypedDataSet_20260810161207.csv")
):
    df = pd.read_csv(data_path, sep=";", encoding="utf-8-sig")
    df["TotaalIngeschrevenen_1"] = pd.to_numeric(
        df["TotaalIngeschrevenen_1"].astype(str).str.strip(),
        errors="raise",
    )

    df = df.loc[
        (df["Geslacht"] == "T001038")
        & (df["Onderwijssoort"] == "A025297")
        & (df["Opleidingsfase"] == "A045745")
        & (df["Opleidingsvorm"] == "T001228")
        & (df["Perioden"] >= "2015SJ00")
        & (df["Perioden"] <= "2023SJ00")
    ].sort_values("Perioden")

    jaarlijkse_groei = df["TotaalIngeschrevenen_1"].pct_change().dropna() * 100
    return round(float(jaarlijkse_groei.mean()), 2)


if __name__ == "__main__":
    print(ground_truth_calc_01())