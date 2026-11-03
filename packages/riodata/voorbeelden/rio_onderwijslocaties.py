"""
RIO: Onderwijslocaties per stad
Dataset: RIO LOD API v2 — onderwijslocaties
Centrale vraag: In welke steden staan de meeste geregistreerde onderwijslocaties?
"""
import pandas as pd
import matplotlib.pyplot as plt
from riodata import client

OUTPUT = "voorbeelden/output/rio_onderwijslocaties.png"


def main():
    # 1. Steekproef bekijken
    sample = client.fetch("onderwijslocaties", page=0, pageSize=3)
    print(f"Velden: {[k for k in sample[0].keys() if not k.startswith('_')]}")
    print(f"Voorbeeld: {sample[0].get('plaatsnaam')} | GPS: {sample[0].get('gpsLatitude')}, {sample[0].get('gpsLongitude')}")
    print()

    # 2. Alle onderwijslocaties ophalen (~137 pagina's, ~13.700 records)
    print("Onderwijslocaties ophalen...")
    locaties = client.fetch("onderwijslocaties")
    print(f"Totaal: {len(locaties)}\n")

    df = pd.DataFrame(locaties)

    # 3. Top 25 steden
    stad_telling = df["plaatsnaam"].value_counts().head(25)
    print(f"Top 10 steden:\n{stad_telling.head(10).to_string()}\n")

    # 4. Plot
    fig, ax = plt.subplots(figsize=(10, 9))
    stad_telling.plot(kind="barh", ax=ax, color="#1a6faf", edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Aantal onderwijslocaties", fontsize=11)
    ax.set_title(
        "Top 25 steden naar aantal geregistreerde onderwijslocaties\n(RIO — Registratie Instellingen en Opleidingen)",
        fontsize=12, fontweight="bold", pad=12
    )
    ax.invert_yaxis()

    for i, v in enumerate(stad_telling):
        ax.text(v + 0.5, i, str(v), va="center", fontsize=9)
    ax.set_xlim(0, stad_telling.max() * 1.15)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
    print(f"Plot opgeslagen: {OUTPUT}")


if __name__ == "__main__":
    main()
