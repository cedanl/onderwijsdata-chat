"""
MBO diplomarendement-trend 2011–2024
Datasets: CBS 85357NED — Mbo; gediplomeerden, niveau, leerweg, herkomst
          CBS 85354NED — Mbo; studenten naar niveau, leerweg, herkomst
Centrale vraag: Hoe heeft het aantal MBO-gediplomeerden en de ruwe diploma-ratio
                (gediplomeerden per 100 studenten) zich ontwikkeld over 2011/'12–2024/'25?

Noot: Dit is GEEN cohortstudie. De ratio gediplomeerden/studenten is een proxy
      en kan niet causaal aan BSA of ander beleid worden toegeschreven.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from onderwijsdata import client

OUTPUT = "voorbeelden/output/mbo_diploma_trend.png"

FILTER_TOTAAL = (
    "trim(Geslacht) eq 'T001038' and "
    "trim(Herkomstland) eq 'T001040' and "
    "trim(GeboortelandOuders) eq 'T001638'"
)

# ── 1. Data ophalen ───────────────────────────────────────────────────────────

# Gediplomeerden: per niveau × leerweg, alle jaren
rows_ged = client.data("85357NED", **{"$filter": FILTER_TOTAAL})
df_ged = pd.DataFrame(rows_ged)

# Studenten: per niveau × leerweg, alle jaren
rows_stud = client.data("85354NED", **{"$filter": FILTER_TOTAAL})
df_stud = pd.DataFrame(rows_stud)

# ── 2. Dimensie-labels ophalen ────────────────────────────────────────────────

perioden_map   = client.dimension("85357NED", "Perioden")
niveau_map     = client.dimension("85357NED", "Niveau")
leerweg_map    = client.dimension("85357NED", "Leerweg")

for df in (df_ged, df_stud):
    df["Schooljaar"] = df["Perioden"].map(perioden_map)
    df["NiveauLabel"] = df["Niveau"].map(niveau_map)
    df["LeerwegLabel"] = df["Leerweg"].map(leerweg_map)

df_ged["Gediplomeerden"] = pd.to_numeric(df_ged["GediplomeerdenMbo_1"], errors="coerce")
df_stud["Studenten"]     = pd.to_numeric(df_stud["MboStudenten_1"], errors="coerce")

# ── 3. Subsets selecteren ─────────────────────────────────────────────────────

# Niveau-uitsplitsing: excl. extranei, alleen de vier niveaus (niet het totaal)
NIVEAUS = {
    "A041751": "Entreeopleiding",
    "A041755": "Niveau 2",
    "A041759": "Niveau 3",
    "A041763": "Niveau 4",
}
LEERWEG_EXCL_EXT = "A041867"   # Totaal excl. extranei

ged_niveau = (
    df_ged[
        df_ged["Niveau"].isin(NIVEAUS) &
        (df_ged["Leerweg"] == LEERWEG_EXCL_EXT)
    ]
    .copy()
    .sort_values("Schooljaar")
)
ged_niveau["NiveauLabel"] = ged_niveau["Niveau"].map(NIVEAUS)

# BOL vs BBL totaal (excl. extranei)
LEERWEGEN = {"A041868": "BOL", "A025293": "BBL"}
NIVEAU_TOTAAL = "T001336"

ged_leerweg = (
    df_ged[
        df_ged["Leerweg"].isin(LEERWEGEN) &
        (df_ged["Niveau"] == NIVEAU_TOTAAL)
    ]
    .copy()
    .sort_values("Schooljaar")
)
ged_leerweg["LeerwegLabel"] = ged_leerweg["Leerweg"].map(LEERWEGEN)

stud_leerweg = (
    df_stud[
        df_stud["Leerweg"].isin(LEERWEGEN) &
        (df_stud["Niveau"] == NIVEAU_TOTAAL)
    ]
    .copy()
    .sort_values("Schooljaar")
)
stud_leerweg["LeerwegLabel"] = stud_leerweg["Leerweg"].map(LEERWEGEN)

# Ruwe ratio per leerweg
ratio = (
    ged_leerweg[["Schooljaar", "LeerwegLabel", "Gediplomeerden"]]
    .merge(
        stud_leerweg[["Schooljaar", "LeerwegLabel", "Studenten"]],
        on=["Schooljaar", "LeerwegLabel"],
    )
)
ratio["RatioPer100"] = ratio["Gediplomeerden"] / ratio["Studenten"] * 100

# ── 4. Plot ───────────────────────────────────────────────────────────────────

KLEUREN_NIVEAU = {
    "Entreeopleiding": "#d62728",
    "Niveau 2":        "#ff7f0e",
    "Niveau 3":        "#2ca02c",
    "Niveau 4":        "#1f77b4",
}
KLEUREN_LEERWEG = {"BOL": "#1f77b4", "BBL": "#ff7f0e"}

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

# ── Panel A: Absolute gediplomeerden per niveau ───────────────────────────────
ax = axes[0]
for niveau, grp in ged_niveau.groupby("NiveauLabel", sort=False):
    grp_sorted = grp.sort_values("Schooljaar")
    ax.plot(
        grp_sorted["Schooljaar"],
        grp_sorted["Gediplomeerden"] / 1000,
        marker="o", markersize=4, linewidth=2,
        color=KLEUREN_NIVEAU[niveau], label=niveau,
    )
ax.set_title("Gediplomeerden per niveau", fontsize=11, fontweight="bold")
ax.set_ylabel("Aantal (×1 000)")
ax.tick_params(axis="x", rotation=45, labelsize=7.5)
ax.legend(fontsize=8)
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}k"))

# ── Panel B: Absolute gediplomeerden BOL vs BBL ───────────────────────────────
ax = axes[1]
for lw, grp in ged_leerweg.groupby("LeerwegLabel"):
    grp_sorted = grp.sort_values("Schooljaar")
    ax.plot(
        grp_sorted["Schooljaar"],
        grp_sorted["Gediplomeerden"] / 1000,
        marker="o", markersize=4, linewidth=2,
        color=KLEUREN_LEERWEG[lw], label=lw,
    )
ax.set_title("Gediplomeerden BOL vs. BBL", fontsize=11, fontweight="bold")
ax.set_ylabel("Aantal (×1 000)")
ax.tick_params(axis="x", rotation=45, labelsize=7.5)
ax.legend(fontsize=8)
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}k"))

# ── Panel C: Ruwe ratio gediplomeerden per 100 studenten, BOL vs BBL ──────────
ax = axes[2]
for lw, grp in ratio.groupby("LeerwegLabel"):
    grp_sorted = grp.sort_values("Schooljaar")
    ax.plot(
        grp_sorted["Schooljaar"],
        grp_sorted["RatioPer100"],
        marker="o", markersize=4, linewidth=2,
        color=KLEUREN_LEERWEG[lw], label=lw,
    )
ax.set_title("Gediplomeerden per 100 studenten*", fontsize=11, fontweight="bold")
ax.set_ylabel("Ratio (niet-cohort proxy)")
ax.tick_params(axis="x", rotation=45, labelsize=7.5)
ax.legend(fontsize=8)
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.annotate(
    "* Geen cohortmeting — studenten staan\n  1–4 jaar ingeschreven per niveau",
    xy=(0.02, 0.04), xycoords="axes fraction",
    fontsize=7, color="#555555",
    bbox=dict(boxstyle="round,pad=0.3", fc="#f9f9f9", ec="#cccccc"),
)

fig.suptitle(
    "MBO-studentsucces: gediplomeerden-trend 2011/'12 – 2024/'25\n"
    "Beschrijvende trend — geen causale BSA-analyse mogelijk met CBS OpenData",
    fontsize=13, fontweight="bold", y=1.02,
)
fig.tight_layout()
fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
print(f"Plot opgeslagen: {OUTPUT}")
