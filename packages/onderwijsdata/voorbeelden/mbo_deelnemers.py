import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from onderwijsdata import client

DATASET = "85353NED"

print("Dimensies ophalen...")
geslacht_map       = client.dimension(DATASET, "Geslacht")
niveau_map         = client.dimension(DATASET, "Niveau")
leerweg_map        = client.dimension(DATASET, "Leerweg")
studierichting_map = client.dimension(DATASET, "Studierichting")
regio_map          = client.dimension(DATASET, "Regio")
perioden_map       = client.dimension(DATASET, "Perioden")

geslacht_inv = {v: k for k, v in geslacht_map.items()}
niveau_inv   = {v: k for k, v in niveau_map.items()}
leerweg_inv  = {v: k for k, v in leerweg_map.items()}
richting_inv = {v: k for k, v in studierichting_map.items()}
regio_inv    = {v: k for k, v in regio_map.items()}


def fetch(filt: str) -> pd.DataFrame:
    rows = client.data(DATASET, **{"$filter": filt})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["Geslacht"]       = df["Geslacht"].map(geslacht_map)
    df["Niveau"]         = df["Niveau"].map(niveau_map)
    df["Leerweg"]        = df["Leerweg"].map(leerweg_map)
    df["Studierichting"] = df["Studierichting"].map(studierichting_map)
    df["Regio"]          = df["Regio"].map(regio_map)
    df["Perioden"]       = df["Perioden"].map(perioden_map)
    return df.dropna()


# Codes (stripped)
TOT_G  = geslacht_inv["Totaal mannen en vrouwen"]
MAN    = geslacht_inv["Mannen"]
VRW    = geslacht_inv["Vrouwen"]
TOT_N  = niveau_inv["Totaal"]
TOT_L  = leerweg_inv["Totaal mbo (incl. extranei)"]
BOL    = leerweg_inv["Bol totaal"]
BBL    = leerweg_inv["Bbl totaal"]
TOT_R  = richting_inv["Totaal"]
NL     = regio_inv["Nederland"].strip()
NIVEAUS = ["Mbo-entreeopleiding", "Mbo niveau 2", "Mbo niveau 3", "Mbo niveau 4"]
NIV_CODES = [niveau_inv[n] for n in NIVEAUS]
LANDSDELEN = ["Noord-Nederland (LD)", "Oost-Nederland (LD)", "West-Nederland (LD)", "Zuid-Nederland (LD)"]
LD_CODES = [regio_inv[r].strip() for r in LANDSDELEN]

# Basis filter (geen complexe OR-nesting)
BASE = f"Studierichting eq '{TOT_R}' and trim(Regio) eq '{NL}'"

def fmt_k(x, _): return f"{int(x/1000)}k"

fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("MBO Nederland — Studenten 2015–2026", fontsize=15, fontweight="bold")

# ── Plot 1: Totaal per niveau over tijd ──────────────────────────────────────
print("Plot 1: niveau trend...")
frames = []
for code, label in zip(NIV_CODES, NIVEAUS):
    df = fetch(f"trim(Geslacht) eq '{TOT_G}' and Niveau eq '{code}' and Leerweg eq '{TOT_L}' and {BASE}")
    frames.append(df)
df1 = pd.concat(frames)
niveau_trend = (
    df1.groupby(["Perioden", "Niveau"])["MboStudenten_1"]
    .sum().unstack().sort_index()[NIVEAUS]
)
ax = axes[0, 0]
niveau_trend.plot(ax=ax, marker="o", linewidth=2)
ax.set_title("Studenten per MBO-niveau")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="", fontsize=8)

# ── Plot 2: BOL vs BBL over tijd ─────────────────────────────────────────────
print("Plot 2: BOL vs BBL...")
df_bol = fetch(f"trim(Geslacht) eq '{TOT_G}' and Niveau eq '{TOT_N}' and Leerweg eq '{BOL}' and {BASE}")
df_bbl = fetch(f"trim(Geslacht) eq '{TOT_G}' and Niveau eq '{TOT_N}' and Leerweg eq '{BBL}' and {BASE}")
df2 = pd.concat([df_bol, df_bbl])
leerweg_trend = (
    df2.groupby(["Perioden", "Leerweg"])["MboStudenten_1"]
    .sum().unstack().sort_index()
)
ax = axes[0, 1]
leerweg_trend.plot(ax=ax, marker="o", linewidth=2)
ax.set_title("BOL vs BBL — studenten per jaar")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

# ── Plot 3: Vrouwenaandeel per niveau (meest recent jaar) ────────────────────
print("Plot 3: vrouwenaandeel...")
frames_mv = []
for code in NIV_CODES:
    for g_code, g_label in [(MAN, "Mannen"), (VRW, "Vrouwen")]:
        df = fetch(f"trim(Geslacht) eq '{g_code}' and Niveau eq '{code}' and Leerweg eq '{TOT_L}' and {BASE}")
        frames_mv.append(df)
df3 = pd.concat(frames_mv)
laatste_jaar = df3["Perioden"].max()
vrouw_niveau = (
    df3[df3["Perioden"] == laatste_jaar]
    .groupby(["Niveau", "Geslacht"])["MboStudenten_1"]
    .sum().unstack().reindex(NIVEAUS)
)
vrouw_niveau["pct_vrouw"] = vrouw_niveau["Vrouwen"] / (vrouw_niveau["Mannen"] + vrouw_niveau["Vrouwen"]) * 100
ax = axes[0, 2]
vrouw_niveau["pct_vrouw"].plot(kind="barh", ax=ax, color="steelblue")
ax.axvline(50, color="gray", linestyle="--", linewidth=1)
ax.set_title(f"Vrouwenaandeel per niveau ({laatste_jaar})")
ax.set_xlabel("%")
ax.set_xlim(0, 80)

# ── Plot 4: Top 6 studierichtingen (meest recent jaar) ───────────────────────
print("Plot 4: studierichtingen...")
df4 = fetch(f"trim(Geslacht) eq '{TOT_G}' and Niveau eq '{TOT_N}' and Leerweg eq '{TOT_L}' and trim(Regio) eq '{NL}'")
df4 = df4[df4["Studierichting"] != "Totaal"]
top_richtingen = (
    df4[df4["Perioden"] == df4["Perioden"].max()]
    .groupby("Studierichting")["MboStudenten_1"]
    .sum().nlargest(6).sort_values()
)
ax = axes[1, 0]
top_richtingen.plot(kind="barh", ax=ax, color="steelblue")
ax.set_title(f"Top 6 studierichtingen ({laatste_jaar})")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))

# ── Plot 5: Regionale verdeling over tijd ────────────────────────────────────
print("Plot 5: regio trend...")
frames_regio = []
for code, label in zip(LD_CODES, LANDSDELEN):
    df = fetch(f"trim(Geslacht) eq '{TOT_G}' and Niveau eq '{TOT_N}' and Leerweg eq '{TOT_L}' and Studierichting eq '{TOT_R}' and trim(Regio) eq '{code}'")
    frames_regio.append(df)
df5 = pd.concat(frames_regio)
regio_trend = (
    df5.groupby(["Perioden", "Regio"])["MboStudenten_1"]
    .sum().unstack().sort_index()[LANDSDELEN]
)
ax = axes[1, 1]
regio_trend.plot(ax=ax, marker="o", linewidth=2)
ax.set_title("Studenten per regio")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="", fontsize=7)

# ── Plot 6: Vrouwenaandeel per niveau over tijd ──────────────────────────────
print("Plot 6: feminisering trend...")
fem_trend = (
    df3.groupby(["Perioden", "Niveau", "Geslacht"])["MboStudenten_1"]
    .sum().unstack("Geslacht")
)
fem_trend["pct_vrouw"] = fem_trend["Vrouwen"] / (fem_trend["Mannen"] + fem_trend["Vrouwen"]) * 100
ax = axes[1, 2]
for niveau, grp in fem_trend["pct_vrouw"].groupby("Niveau"):
    perioden = grp.index.get_level_values("Perioden")
    ax.plot(perioden, grp.values, marker="o", label=niveau, linewidth=2)
ax.axhline(50, color="gray", linestyle="--", linewidth=1)
ax.set_title("Vrouwenaandeel (%) per niveau over tijd")
ax.set_ylabel("%")
ax.set_ylim(20, 70)
ax.tick_params(axis="x", rotation=45)
ax.legend(title="", fontsize=7)

plt.tight_layout()
fig.text(
    0.5, -0.02,
    f"Bron: CBS OpenData — {DATASET} · MBO; deelnemers en gediplomeerden · "
    f"https://opendata.cbs.nl/ODataApi/OData/{DATASET}",
    ha="center", fontsize=8, color="gray"
)
plt.savefig("voorbeelden/output/mbo_deelnemers.png", dpi=150, bbox_inches="tight")
print("Opgeslagen: voorbeelden/output/mbo_deelnemers.png")
