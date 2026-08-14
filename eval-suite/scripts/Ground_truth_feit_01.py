# ============================================================
# Onderzoeksvraag: Hoeveel studenten telde het hoger onderwijs (hbo + wo) in Nederland in het meest recente schooljaar?
# Bron: CBS OData API - Hoger onderwijs; ingeschrevenen, onderwijssoort, opleidingsfase en -vorm
# Dataset: 85423NED
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_feit_01(
    data_path=Path("data/raw/85423NED_UntypedDataSet_20260810161207.csv")
):
    df = pd.read_csv(data_path, sep=";", encoding="utf-8-sig")
    df["TotaalIngeschrevenen_1"] = pd.to_numeric(
        df["TotaalIngeschrevenen_1"].astype(str).str.strip(),
        errors="raise",
    )

    hoger_onderwijs_totaal = "A028566"
    meest_recent = df["Perioden"].dropna().sort_values().iloc[-1]

    return int(
        df.loc[
            (df["Perioden"] == meest_recent)
            & (df["Onderwijssoort"] == hoger_onderwijs_totaal),
            "TotaalIngeschrevenen_1",
        ].iloc[0]
    )


if __name__ == "__main__":
    print(ground_truth_feit_01())
