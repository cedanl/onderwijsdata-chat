# ============================================================
# Onderzoeksvraag: Wat is het meest recente instroomcijfer voor pabo-opleidingen in het HBO?
# Bron: DUO - Eerstejaars ingeschrevenen HBO (niveau opleiding)
# Dataset: p02ho1ejrs
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_feit_03(data_path=Path("data/raw/0f594842-cca9-4f17-8cbc-e502dba408b4.csv")):
    # sep=None met python-engine detecteert zowel komma- als puntkomma-bestanden.
    df = pd.read_csv(data_path, sep=None, engine="python", encoding="utf-8-sig")
    df["AANTAL_EERSTEJAARS_INGESCHREVENEN"] = pd.to_numeric(
        df["AANTAL_EERSTEJAARS_INGESCHREVENEN"].astype(str).str.strip(),
        errors="raise",
    )

    pabo_keywords = ["leraar basisonderwijs", "primary school", "pabo"]
    mask_pabo = df["OPLEIDINGSNAAM_ACTUEEL"].str.lower().str.contains(
        "|".join(pabo_keywords),
        na=False,
    )
    df_pabo = df.loc[mask_pabo].copy()
    df_pabo = df_pabo.loc[df_pabo["AANTAL_EERSTEJAARS_INGESCHREVENEN"] != -1]

    meest_recent = df_pabo["STUDIEJAAR"].dropna().max()

    return int(
        df_pabo.loc[
            df_pabo["STUDIEJAAR"] == meest_recent,
            "AANTAL_EERSTEJAARS_INGESCHREVENEN",
        ].sum()
    )


if __name__ == "__main__":
    print(ground_truth_feit_03())