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

    # Expliciet de totaal-codes per dimensie, anders selecteert de query 36 rijen
    # (alle combinaties van geslacht/opleidingsfase/-vorm) en pakt .iloc[0] er
    # willekeurig een uit.
    hoger_onderwijs_totaal = "A028566"  # Onderwijssoort: hbo + wo
    geslacht_totaal = "T001038"
    opleidingsfase_totaal = "A045745"  # bachelor + master samen
    opleidingsvorm_totaal = "T001228"  # voltijd + deeltijd + duaal samen
    meest_recent = df["Perioden"].dropna().sort_values().iloc[-1]

    resultaat = df.loc[
        (df["Perioden"] == meest_recent)
        & (df["Onderwijssoort"] == hoger_onderwijs_totaal)
        & (df["Geslacht"] == geslacht_totaal)
        & (df["Opleidingsfase"] == opleidingsfase_totaal)
        & (df["Opleidingsvorm"] == opleidingsvorm_totaal),
        "TotaalIngeschrevenen_1",
    ]

    if len(resultaat) != 1:
        raise ValueError(
            f"Verwacht precies 1 totaal-rij, kreeg er {len(resultaat)}. "
            "Controleer of de dimensiecodes nog kloppen in deze CBS-download."
        )

    return int(resultaat.iloc[0])


if __name__ == "__main__":
    print(ground_truth_feit_01())
