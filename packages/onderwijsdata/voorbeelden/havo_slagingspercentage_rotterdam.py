"""
HAVO slagingspercentage: Rotterdam vs. landelijk
Dataset: CBS 85382NED — Vo; examenkandidaten en gediplomeerden, onderwijssoort, woonregio
Centrale vraag: Hoe verhoudt het HAVO-slagingspercentage in Rotterdam zich tot het landelijk gemiddelde?
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from onderwijsdata import client

OUTPUT = "voorbeelden/output/havo_slagingspercentage_rotterdam.png"

# 1. Data ophalen: HAVO, Rotterdam + Nederland, alle perioden, totaal geslacht
rows = client.data(
    "85382NED",
    **{
        "$filter": (
            "trim(Geslacht) eq 'T001038' and "
            "trim(Onderwijssoort) eq 'A025285' and "
            "(trim(Regiokenmerken) eq 'NL01' or trim(Regiokenmerken) eq 'GM0599')"
        )
    },
)
df = pd.DataFrame(rows)

# 2. Perioden omzetten naar leesbaar schooljaar
perioden = client.dimension("85382NED", "Perioden")
df["Schooljaar"] = df["Perioden"].map(perioden)

# Regio label
regio_map = {"NL01": "Nederland", "GM0599": "Rotterdam"}
df["Regio"] = df["Regiokenmerken"].str.strip().map(regio_map)

# Kolommen opschonen
df["Slagingspercentage"] = pd.to_numeric(df["GediplomeerdenRelatief_3"], errors="coerce")
df["Kandidaten"] = pd.to_numeric(df["Examenkandidaten_1"], errors="coerce")
df["Gediplomeerden"] = pd.to_numeric(df["Gediplomeerden_2"], errors="coerce")

df = df[["Schooljaar", "Regio", "Slagingspercentage", "Kandidaten", "Gediplomeerden"]].dropna()
df = df.sort_values("Schooljaar")

nl = df[df["Regio"] == "Nederland"]
rot = df[df["Regio"] == "Rotterdam"]

# 3. Plot
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# -- Links: slagingspercentage tijdreeks
ax = axes[0]
ax.plot(nl["Schooljaar"], nl["Slagingspercentage"], marker="o", linewidth=2,
        color="#003082", label="Nederland")
ax.plot(rot["Schooljaar"], rot["Slagingspercentage"], marker="s", linewidth=2,
        color="#E63312", label="Rotterdam")

# Verschil annotaties
for _, row_nl in nl.iterrows():
    row_rot = rot[rot["Schooljaar"] == row_nl["Schooljaar"]]
    if not row_rot.empty:
        diff = row_rot.iloc[0]["Slagingspercentage"] - row_nl["Slagingspercentage"]
        y = row_rot.iloc[0]["Slagingspercentage"]
        if abs(diff) >= 1:
            ax.annotate(
                f"{diff:+.0f}%",
                xy=(row_nl["Schooljaar"], y),
                xytext=(6, 4), textcoords="offset points",
                fontsize=7.5, color="#E63312",
            )

ax.set_title("Slagingspercentage HAVO", fontsize=12, fontweight="bold")
ax.set_ylabel("Geslaagden per 100 kandidaten (%)")
ax.set_ylim(70, 100)
ax.yaxis.set_minor_locator(mticker.MultipleLocator(1))
ax.tick_params(axis="x", rotation=45, labelsize=8)
ax.legend()
ax.grid(axis="y", linestyle="--", alpha=0.4)

# -- Rechts: absoluut aantal kandidaten Rotterdam
ax2 = axes[1]
bars = ax2.bar(rot["Schooljaar"], rot["Kandidaten"], color="#E63312", alpha=0.8)
ax2.bar(rot["Schooljaar"], rot["Gediplomeerden"], color="#003082", alpha=0.8, label="Gediplomeerden")
ax2.bar(rot["Schooljaar"], rot["Kandidaten"], color="none", edgecolor="#E63312",
        linewidth=1.2, label="Kandidaten (totaal)")
ax2.set_title("HAVO-examenkandidaten Rotterdam", fontsize=12, fontweight="bold")
ax2.set_ylabel("Aantal leerlingen")
ax2.tick_params(axis="x", rotation=45, labelsize=8)
ax2.legend(fontsize=8)
ax2.grid(axis="y", linestyle="--", alpha=0.4)

fig.suptitle(
    "HAVO-examenresultaten: Rotterdam vs. Nederland",
    fontsize=14, fontweight="bold", y=1.01
)
fig.tight_layout()
fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
print(f"Plot opgeslagen: {OUTPUT}")
print("\nData samenvatting:")
print(df.to_string(index=False))
