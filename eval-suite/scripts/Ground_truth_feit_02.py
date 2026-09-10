# ============================================================
# Onderzoeksvraag: Welke universiteit heeft de meeste wo-ingeschrevenen?
# Bron: DUO - Ingeschrevenen wetenschappelijk onderwijs inclusief geslacht
# Dataset: p01hoinges
# ============================================================

from pathlib import Path

import pandas as pd


def vraag2_meestestudenten(data_path=Path("data/raw/b88721ef-9787-4299-afc7-5d74380d29ba.csv")):
    # sep=None met python-engine detecteert zowel komma- als puntkomma-bestanden.
    df = pd.read_csv(data_path, sep=None, engine="python", encoding="utf-8-sig")
    df["AANTAL_INGESCHREVENEN"] = pd.to_numeric(
        df["AANTAL_INGESCHREVENEN"].astype(str).str.strip(),
        errors="raise",
    )

    meest_recent = df["STUDIEJAAR"].dropna().max()
    df_recent = df.loc[df["STUDIEJAAR"] == meest_recent].copy()
    df_recent = df_recent.loc[df_recent["AANTAL_INGESCHREVENEN"] > 0]

    totaal_per_instelling = (
        df_recent.groupby("INSTELLINGSNAAM_ACTUEEL", as_index=False)["AANTAL_INGESCHREVENEN"]
        .sum()
        .sort_values("AANTAL_INGESCHREVENEN", ascending=False)
        .reset_index(drop=True)
    )

    top = totaal_per_instelling.iloc[0]
    return {
        "instellingsnaam": str(top["INSTELLINGSNAAM_ACTUEEL"]),
        "aantal_ingeschrevenen": int(top["AANTAL_INGESCHREVENEN"]),
    }


if __name__ == "__main__":
    print(vraag2_meestestudenten())