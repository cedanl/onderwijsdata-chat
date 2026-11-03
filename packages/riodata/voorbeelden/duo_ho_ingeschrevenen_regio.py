"""
DUO — HBO ingeschrevenen per provincie en geslacht
Resource(s): DUO CKAN — p01hoinges (ingeschrevenengeslhbo.csv)
Centrale vraag: Hoe zijn HBO-ingeschrevenen verdeeld over provincies, en wat is de M/V-verhouding?
"""
import pandas as pd
import matplotlib.pyplot as plt
from riodata import duo

OUTPUT = "voorbeelden/output/duo_ho_ingeschrevenen_regio.png"

# 1. Data ophalen (DUO CKAN, CSV)
df = duo.load("p01hoinges", 0)

# 2. Meest recente studiejaar
jaar = df["STUDIEJAAR"].max()
recent = df[df["STUDIEJAAR"] == jaar]

# 3. Ingeschrevenen per provincie en geslacht
pivot = (
    recent.groupby(["PROVINCIENAAM", "GESLACHT"])["AANTAL_INGESCHREVENEN"]
    .sum()
    .unstack(fill_value=0)
)
pivot = pivot.sort_values(pivot.columns[0], ascending=True)

# 4. Plot
fig, ax = plt.subplots(figsize=(10, 7))
colors = {"MAN": "#2E86AB", "VROUW": "#E84855"}
bottom = pd.Series(0, index=pivot.index)

for geslacht in ["MAN", "VROUW"]:
    if geslacht in pivot.columns:
        ax.barh(pivot.index, pivot[geslacht], left=bottom,
                color=colors[geslacht], label=geslacht.capitalize(), alpha=0.85)
        bottom += pivot[geslacht]

ax.set_xlabel("Aantal ingeschrevenen")
ax.set_title(f"HBO ingeschrevenen per provincie ({jaar})", fontsize=13)
ax.legend(loc="lower right")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))

fig.suptitle("DUO Open Data — Hoger onderwijs", fontsize=10, color="gray")
fig.tight_layout()
fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
print(f"Plot opgeslagen: {OUTPUT}")
print(f"Studiejaar: {jaar}, totaal {int(recent['AANTAL_INGESCHREVENEN'].sum()):,} ingeschrevenen")
