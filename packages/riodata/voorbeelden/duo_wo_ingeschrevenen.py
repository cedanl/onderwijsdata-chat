"""
DUO — WO ingeschrevenen per universiteit (2021–2025)
Resource(s): DUO CKAN — p01hoinges, resource 1 (ingeschrevenengeslwo.csv)
Centrale vraag: Hoe ontwikkelen de studentenaantallen bij Nederlandse universiteiten
                zich, en welke verschillen zijn er in omvang, groei en genderverhouding?
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from riodata import duo

OUTPUT_DIR = "voorbeelden/output/duo_wo_ingeschrevenen"

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Data laden ────────────────────────────────────────────────────────────────
df = duo.load("p01hoinges", 1)

# Standaard universiteiten (sluit theologische en transnationale uit voor hoofdplots)
# Sluit theologische en kleine/niet-universitaire instellingen uit
EXCL = {"Protestantse Theologische Universiteit",
        "Theologische Universiteit Apeldoorn",
        "Theologische Universiteit Utrecht",
        "transnationale Universiteit Limburg",
        "Breda University of Applied Sciences",
        "Hanzehogeschool Groningen",
        "Hogeschool van Amsterdam"}
main = df[~df["INSTELLINGSNAAM_ACTUEEL"].isin(EXCL)].copy()

# Korte namen voor labels
KORT = {
    "Radboud Universiteit Nijmegen":  "Radboud",
    "Rijksuniversiteit Groningen":    "RUG",
    "Universiteit van Amsterdam":     "UvA",
    "Vrije Universiteit Amsterdam":   "VU",
    "Universiteit Utrecht":           "UU",
    "Universiteit Leiden":            "Leiden",
    "Technische Universiteit Delft":  "TU Delft",
    "Technische Universiteit Eindhoven": "TU/e",
    "Erasmus Universiteit Rotterdam": "EUR",
    "Universiteit Maastricht":        "UM",
    "Universiteit Twente":            "UT",
    "Tilburg University":             "Tilburg",
    "Wageningen University":          "WUR",
    "Universiteit voor Humanistiek":  "UvH",
}
main["Instelling"] = main["INSTELLINGSNAAM_ACTUEEL"].map(KORT).fillna(main["INSTELLINGSNAAM_ACTUEEL"])

LAATSTE = main["STUDIEJAAR"].max()
EERSTE  = main["STUDIEJAAR"].min()

# ── Plot 1: Totaal ingeschrevenen per universiteit (2025) ─────────────────────
totaal_2025 = (
    main[main["STUDIEJAAR"] == LAATSTE]
    .groupby("Instelling")["AANTAL_INGESCHREVENEN"].sum()
    .sort_values(ascending=True)
)

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(totaal_2025.index, totaal_2025.values, color="#2E86AB", alpha=0.85)
ax.bar_label(bars, labels=[f"{v:,.0f}".replace(",", ".") for v in totaal_2025.values],
             padding=4, fontsize=8.5)
ax.set_xlabel("Aantal ingeschrevenen")
ax.set_title(f"WO ingeschrevenen per universiteit — studiejaar {LAATSTE}", fontsize=13)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))
ax.set_xlim(0, totaal_2025.max() * 1.18)
fig.suptitle("DUO Open Data — Hoger onderwijs (WO)", fontsize=9, color="gray")
fig.tight_layout()
fig.savefig(f"{OUTPUT_DIR}/01_totaal_per_uni.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 1 opgeslagen")

# ── Plot 2: Trend 2021–2025 (top 7 grootste universiteiten) ──────────────────
top7 = totaal_2025.nlargest(7).index.tolist()
trend = (
    main[main["Instelling"].isin(top7)]
    .groupby(["STUDIEJAAR", "Instelling"])["AANTAL_INGESCHREVENEN"].sum()
    .unstack()
)

colors = plt.cm.tab10(np.linspace(0, 0.7, len(top7)))
fig, ax = plt.subplots(figsize=(10, 6))
for i, uni in enumerate(trend.columns):
    ax.plot(trend.index, trend[uni], marker="o", label=uni, color=colors[i], linewidth=2)
    ax.annotate(f"{trend[uni].iloc[-1]:,.0f}".replace(",", "."),
                xy=(trend.index[-1], trend[uni].iloc[-1]),
                xytext=(4, 0), textcoords="offset points",
                fontsize=8, va="center")

ax.set_xlabel("Studiejaar")
ax.set_ylabel("Aantal ingeschrevenen")
ax.set_title(f"Trend ingeschrevenen — top 7 universiteiten ({EERSTE}–{LAATSTE})", fontsize=13)
ax.legend(loc="upper left", fontsize=8.5)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))
ax.set_xticks(trend.index)
fig.suptitle("DUO Open Data — Hoger onderwijs (WO)", fontsize=9, color="gray")
fig.tight_layout()
fig.savefig(f"{OUTPUT_DIR}/02_trend_top7.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 2 opgeslagen")

# ── Plot 3: Genderverhouding per universiteit (2025) ─────────────────────────
gender_2025 = (
    main[main["STUDIEJAAR"] == LAATSTE]
    .groupby(["Instelling", "GESLACHT"])["AANTAL_INGESCHREVENEN"].sum()
    .unstack(fill_value=0)
)
gender_2025 = gender_2025[["VROUW", "MAN"]].copy()
gender_2025["totaal"] = gender_2025.sum(axis=1)
gender_2025["pct_vrouw"] = gender_2025["VROUW"] / gender_2025["totaal"] * 100
gender_2025 = gender_2025.sort_values("pct_vrouw", ascending=True)

fig, ax = plt.subplots(figsize=(10, 6))
y = range(len(gender_2025))
ax.barh(y, gender_2025["VROUW"], color="#E84855", alpha=0.85, label="Vrouw")
ax.barh(y, gender_2025["MAN"],   left=gender_2025["VROUW"],
        color="#2E86AB", alpha=0.85, label="Man")
ax.set_yticks(list(y))
ax.set_yticklabels(gender_2025.index)
ax.axvline(gender_2025["totaal"].mean() / 2, color="gray", linestyle="--",
           linewidth=0.8, label="50% lijn")
for i, (_, row) in enumerate(gender_2025.iterrows()):
    ax.text(row["totaal"] + 200, i, f"{row['pct_vrouw']:.0f}% V",
            va="center", fontsize=8.5)
ax.set_xlabel("Aantal ingeschrevenen")
ax.set_title(f"Genderverhouding per universiteit — studiejaar {LAATSTE}", fontsize=13)
ax.legend(loc="lower right")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))
ax.set_xlim(0, gender_2025["totaal"].max() * 1.22)
fig.suptitle("DUO Open Data — Hoger onderwijs (WO)", fontsize=9, color="gray")
fig.tight_layout()
fig.savefig(f"{OUTPUT_DIR}/03_gender_per_uni.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 3 opgeslagen")

# ── Plot 4: Groei/krimp per universiteit 2021→2025 ────────────────────────────
totaal_eerste = (
    main[main["STUDIEJAAR"] == EERSTE]
    .groupby("Instelling")["AANTAL_INGESCHREVENEN"].sum()
)
groei = ((totaal_2025 - totaal_eerste) / totaal_eerste * 100).dropna().sort_values()

colors_bar = ["#E84855" if v < 0 else "#2E86AB" for v in groei.values]
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(groei.index, groei.values, color=colors_bar, alpha=0.85)
ax.bar_label(bars, labels=[f"{v:+.1f}%" for v in groei.values], padding=4, fontsize=8.5)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel("Procentuele verandering")
ax.set_title(f"Groei/krimp ingeschrevenen {EERSTE}→{LAATSTE}", fontsize=13)
ax.set_xlim(groei.min() * 1.5, groei.max() * 1.5)
fig.suptitle("DUO Open Data — Hoger onderwijs (WO)", fontsize=9, color="gray")
fig.tight_layout()
fig.savefig(f"{OUTPUT_DIR}/04_groei_krimp.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 4 opgeslagen")

# ── Plot 5: Radboud — faculteiten trend ──────────────────────────────────────
radboud = main[main["INSTELLINGSNAAM_ACTUEEL"] == "Radboud Universiteit Nijmegen"]
fac_trend = (
    radboud.groupby(["STUDIEJAAR", "ONDERDEEL"])["AANTAL_INGESCHREVENEN"].sum()
    .unstack(fill_value=0)
)
# Sorteer op grootte in laatste jaar
volgorde = fac_trend.iloc[-1].sort_values(ascending=False).index
fac_trend = fac_trend[volgorde]

colors_fac = plt.cm.Set2(np.linspace(0, 1, len(fac_trend.columns)))
fig, ax = plt.subplots(figsize=(10, 6))
for i, fac in enumerate(fac_trend.columns):
    naam = fac.replace("_", " ").title()
    ax.plot(fac_trend.index, fac_trend[fac], marker="o", label=naam,
            color=colors_fac[i], linewidth=2)
    ax.annotate(f"{fac_trend[fac].iloc[-1]:,}".replace(",", "."),
                xy=(fac_trend.index[-1], fac_trend[fac].iloc[-1]),
                xytext=(4, 0), textcoords="offset points",
                fontsize=8, va="center")

ax.set_xlabel("Studiejaar")
ax.set_ylabel("Aantal ingeschrevenen")
ax.set_title(f"Radboud Universiteit — ingeschrevenen per faculteit ({EERSTE}–{LAATSTE})", fontsize=12)
ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8.5)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))
ax.set_xticks(fac_trend.index)
fig.suptitle("DUO Open Data — Hoger onderwijs (WO)", fontsize=9, color="gray")
fig.tight_layout()
fig.savefig(f"{OUTPUT_DIR}/05_radboud_faculteiten.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 5 opgeslagen")

# ── Print cijfers voor interpretatie ─────────────────────────────────────────
print()
print("=== KERNCIJFERS ===")
print(f"Totaal WO {LAATSTE}: {main[main['STUDIEJAAR']==LAATSTE]['AANTAL_INGESCHREVENEN'].sum():,}")
print(f"Totaal WO {EERSTE}: {main[main['STUDIEJAAR']==EERSTE]['AANTAL_INGESCHREVENEN'].sum():,}")
print()
print("Grootste universiteit:", totaal_2025.idxmax(), f"({totaal_2025.max():,})")
print("Kleinste universiteit:", totaal_2025.idxmin(), f"({totaal_2025.min():,})")
print()
print("Sterkste groei:", groei.idxmax(), f"({groei.max():+.1f}%)")
print("Sterkste krimp:", groei.idxmin(), f"({groei.min():+.1f}%)")
print()
print("Meeste vrouwen %:", gender_2025["pct_vrouw"].idxmax(),
      f"({gender_2025['pct_vrouw'].max():.0f}%)")
print("Minste vrouwen %:", gender_2025["pct_vrouw"].idxmin(),
      f"({gender_2025['pct_vrouw'].min():.0f}%)")
print()
print("Radboud totaal 2025:", radboud[radboud['STUDIEJAAR']==LAATSTE]['AANTAL_INGESCHREVENEN'].sum())
print("Radboud % vrouw:", round(
    radboud[(radboud['STUDIEJAAR']==LAATSTE) & (radboud['GESLACHT']=='VROUW')]['AANTAL_INGESCHREVENEN'].sum() /
    radboud[radboud['STUDIEJAAR']==LAATSTE]['AANTAL_INGESCHREVENEN'].sum() * 100, 1))
