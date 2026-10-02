# ============================================================
# Onderzoeksvraag: Geef de instroom van de opleiding Ruimtevaartrecht aan de Universiteit Groningen.
# Bron: DUO - Eerstejaars ingeschrevenen HBO (niveau opleiding)
# Dataset: p02ho1ejrs
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_fake_02(
    data_path=Path("data/raw/0f594842-cca9-4f17-8cbc-e502dba408b4.csv"),
):
    df = pd.read_csv(data_path, sep=",", encoding="utf-8-sig", dtype=str)
    instelling_bestaat = df["INSTELLINGSNAAM_ACTUEEL"].isin(
        ["Universiteit Groningen", "Rijksuniversiteit Groningen"]
    ).any()
    opleiding_bestaat = df["OPLEIDINGSNAAM_ACTUEEL"].eq("Ruimtevaartrecht").any()

    return {
        "status": (
            "bestaat"
            if opleiding_bestaat and instelling_bestaat
            else "opleiding_bestaat_niet"
        ),
        "entity_type": "opleiding",
        "entity": "Ruimtevaartrecht",
        "institution": "Universiteit Groningen",
        "exists_in_source": bool(opleiding_bestaat and instelling_bestaat),
        "required_facts": [
            "Meld dat de opleiding Ruimtevaartrecht niet bestaat of niet in de bron voorkomt.",
            "Geef geen verzonnen instroomcijfer.",
        ],
        "numeric_answer_allowed": False,
    }


if __name__ == "__main__":
    print(ground_truth_fake_02())
