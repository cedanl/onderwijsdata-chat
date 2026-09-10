# ============================================================
# Onderzoeksvraag: Hoeveel studenten heeft de Rijksuniversiteit Eindhoven?
# Bron: DUO - Eerstejaars ingeschrevenen HBO (niveau opleiding)
# Dataset: p02ho1ejrs
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_fake_01(
    data_path=Path("data/raw/0f594842-cca9-4f17-8cbc-e502dba408b4.csv"),
):
    df = pd.read_csv(data_path, sep=",", encoding="utf-8-sig", dtype=str)
    instelling_bestaat = df["INSTELLINGSNAAM_ACTUEEL"].eq(
        "Rijksuniversiteit Eindhoven"
    ).any()
    alternatieven = [
        "Technische Universiteit Eindhoven (TU/e)",
        "Rijksuniversiteit Groningen (RUG)",
    ]

    return {
        "status": "bestaat" if instelling_bestaat else "bestaat_niet",
        "entity_type": "instelling",
        "entity": "Rijksuniversiteit Eindhoven",
        "exists_in_source": bool(instelling_bestaat),
        "required_facts": [
            "Meld dat Rijksuniversiteit Eindhoven niet bestaat of niet in de bron voorkomt.",
            "Geef geen verzonnen studentenaantal.",
        ],
        "valid_corrections": alternatieven if not instelling_bestaat else [],
        "numeric_answer_allowed": False,
    }


if __name__ == "__main__":
    print(ground_truth_fake_01())
