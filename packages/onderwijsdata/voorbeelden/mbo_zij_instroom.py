"""
MBO zij-instroom: wie stroomt er in, vanwaar, en welke sectoren trekken hen?
Combineert twee CBS-datasets:
  85574NED — Instromers mbo; bedrijfstakken 1 jaar eerder (BBL-context)
  85569NED — Instromers mbo; maatschappelijke positie 1 jaar eerder

Strategische vraag (MBO Raad / SBB):
  Welke sectorkamers zijn afhankelijk van zij-instroom,
  en vanuit welke maatschappelijke positie komen die instromers?
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from onderwijsdata import client

OUTPUT_DIR = "voorbeelden/output/mbo_zij_instroom"

# ── Dimensies ────────────────────────────────────────────────────────────────
print("Dimensies ophalen...")
ds74, ds69 = "85574NED", "85569NED"

ges74  = client.dimension(ds74, "Geslacht")
niv74  = client.dimension(ds74, "Niveau")
lw74   = client.dimension(ds74, "Leerweg")
sk74   = client.dimension(ds74, "Sectorkamer")
lft74  = client.dimension(ds74, "Leeftijd")
bdt74  = client.dimension(ds74, "BedrijfstakkenBranchesSBI2008")
per74  = client.dimension(ds74, "Perioden")

mpos69 = client.dimension(ds69, "MaatschappelijkePositie1JaarEerder")
sk69   = client.dimension(ds69, "Sectorkamer")
niv69  = client.dimension(ds69, "Niveau")
lw69   = client.dimension(ds69, "Leerweg")
ges69  = client.dimension(ds69, "Geslacht")
pke69  = client.dimension(ds69, "Persoonskenmerken")
per69  = client.dimension(ds69, "Perioden")

def inv(d): return {v: k for k, v in d.items()}

# Codes
TOT_G74  = inv(ges74)["Totaal mannen en vrouwen"]
TOT_N74  = inv(niv74)["Totaal middelbaar beroepsonderwijs"]
TOT_LW74 = inv(lw74)["Totaal mbo (incl. extranei)"]
BBL_LW74 = inv(lw74)["Bbl totaal"]
TOT_SK74 = inv(sk74)["Totaal"]
TOT_LT74 = list(lft74.keys())[0]   # numeriek → trim() nodig
TOT_BDT  = inv(bdt74)["A-U Alle economische activiteiten"]

TOT_G69  = inv(ges69)["Totaal mannen en vrouwen"]
TOT_N69  = inv(niv69)["Totaal middelbaar beroepsonderwijs"]
TOT_LW69 = inv(lw69)["Totaal mbo (incl. extranei)"]
BBL_LW69 = inv(lw69)["Bbl totaal"]
BOL_LW69 = inv(lw69)["Bol totaal"]
TOT_SK69 = inv(sk69)["Totaal"]
TOT_PKE  = list(pke69.keys())[0]   # numeriek → trim() nodig
TOT_POS  = inv(mpos69)["Totaal instromers"]

RECENTSTE = max(per74.keys())
LABEL_J   = per74[RECENTSTE]


# ── Helpers ──────────────────────────────────────────────────────────────────
def korte_sk(label):
    """'Sectorkamer techniek en gebouwde omgeve.' → 'Techniek & gebouwde omgeving'"""
    s = label.replace("Sectorkamer ", "").replace("Niet gespecificeerd naar sectorkamer", "Niet gespecificeerd")
    return s[0].upper() + s[1:] if s else label

def korte_bdt(label):
    parts = label.split(" ", 1)
    return parts[1] if len(parts) == 2 else label

def korte_mpos(label):
    mapping = {
        "Met werk, zonder uitkering":   "Werkend",
        "Met werk, met uitkering":      "Werkend + uitkering",
        "Zonder werk, met uitkering":   "Uitkering, geen werk",
        "Onderwijsvolgend":             "In onderwijs",
        "Geen onderwijs":               "Geen onderwijs/werk",
        "Hoger onderwijs":              "Hoger onderwijs",
        "Vmbo-b/k 3-4 totaal":         "Vmbo-b/k",
        "Vmbo-g/t  3-4":               "Vmbo-g/t",
        "Havo 3-5/vwo 3-6":            "Havo/vwo",
        "Vavo":                         "Vavo",
        "Praktijkonderwijs":            "Praktijkonderwijs",
        "Speciale scholen: vso":        "VSO",
        "Vo algemene leerjaren 1-3":    "Vo 1-3",
        "Onbekend":                     "Onbekend",
    }
    return mapping.get(label, label)

def fmt_k(x, _): return f"{int(x/1000)}k"


# ── Data ophalen ─────────────────────────────────────────────────────────────
print("85569 — positie × leerweg over tijd (trend)...")
rows = client.data(ds69, **{"$filter": (
    f"Geslacht eq '{TOT_G69}' and Niveau eq '{TOT_N69}' and "
    f"Sectorkamer eq '{TOT_SK69}' and trim(Persoonskenmerken) eq '{TOT_PKE}'"
)})
df69_trend = pd.DataFrame(rows)
df69_trend["Leerweg"]   = df69_trend["Leerweg"].map(lw69)
df69_trend["Positie"]   = df69_trend["MaatschappelijkePositie1JaarEerder"].map(mpos69)
df69_trend["Perioden"]  = df69_trend["Perioden"].map(per69)
df69_trend = df69_trend.dropna(subset=["Perioden", "Positie", "Leerweg"])

print("85569 — positie × sectorkamer (recentste jaar, BBL)...")
rows = client.data(ds69, **{"$filter": (
    f"Geslacht eq '{TOT_G69}' and Niveau eq '{TOT_N69}' and "
    f"Leerweg eq '{BBL_LW69}' and trim(Persoonskenmerken) eq '{TOT_PKE}' and "
    f"Perioden eq '{RECENTSTE}'"
)})
df69_sk = pd.DataFrame(rows)
df69_sk["Sectorkamer"] = df69_sk["Sectorkamer"].map(sk69)
df69_sk["Positie"]     = df69_sk["MaatschappelijkePositie1JaarEerder"].map(mpos69)
df69_sk["Perioden"]    = df69_sk["Perioden"].map(per69)
df69_sk = df69_sk.dropna(subset=["Sectorkamer", "Positie"])

print("85574 — bedrijfstakken BBL-instromers (alle jaren)...")
rows = client.data(ds74, **{"$filter": (
    f"Geslacht eq '{TOT_G74}' and Niveau eq '{TOT_N74}' and "
    f"Leerweg eq '{BBL_LW74}' and Sectorkamer eq '{TOT_SK74}' and "
    f"trim(Leeftijd) eq '{TOT_LT74}'"
)})
df74_bdt = pd.DataFrame(rows)
df74_bdt["Bedrijfstak"] = df74_bdt["BedrijfstakkenBranchesSBI2008"].map(bdt74)
df74_bdt["Perioden"]    = df74_bdt["Perioden"].map(per74)
df74_bdt = df74_bdt.dropna(subset=["Perioden", "Bedrijfstak"])

print("85574 — leeftijd × sectorkamer BBL (recentste jaar)...")
rows = client.data(ds74, **{"$filter": (
    f"Geslacht eq '{TOT_G74}' and Niveau eq '{TOT_N74}' and "
    f"Leerweg eq '{BBL_LW74}' and BedrijfstakkenBranchesSBI2008 eq '{TOT_BDT}' and "
    f"Perioden eq '{RECENTSTE}'"
)})
df74_lft = pd.DataFrame(rows)
df74_lft["Sectorkamer"] = df74_lft["Sectorkamer"].map(sk74)
df74_lft["Leeftijd"]    = df74_lft["Leeftijd"].map(lft74)
df74_lft["Perioden"]    = df74_lft["Perioden"].map(per74)
df74_lft = df74_lft.dropna(subset=["Sectorkamer", "Leeftijd"])

print("85569 — herkomst van zij-instromers totaal over tijd...")
rows = client.data(ds69, **{"$filter": (
    f"Geslacht eq '{TOT_G69}' and Niveau eq '{TOT_N69}' and "
    f"Sectorkamer eq '{TOT_SK69}' and trim(Persoonskenmerken) eq '{TOT_PKE}' and "
    f"Leerweg eq '{BBL_LW69}'"
)})
df69_bbl = pd.DataFrame(rows)
df69_bbl["Positie"]   = df69_bbl["MaatschappelijkePositie1JaarEerder"].map(mpos69)
df69_bbl["Perioden"]  = df69_bbl["Perioden"].map(per69)
df69_bbl = df69_bbl.dropna(subset=["Perioden", "Positie"])


# ── Kleuren per positie ──────────────────────────────────────────────────────
POSITIE_KLEUREN = {
    "Werkend":              "#2ecc71",
    "Werkend + uitkering":  "#82c982",
    "Uitkering, geen werk": "#e67e22",
    "In onderwijs":         "#3498db",
    "Vmbo-b/k":             "#5dade2",
    "Vmbo-g/t":             "#7fb3d3",
    "Havo/vwo":             "#a9cce3",
    "Praktijkonderwijs":    "#76d7c4",
    "Hoger onderwijs":      "#1a5276",
    "Geen onderwijs/werk":  "#e74c3c",
    "VSO":                  "#aab7b8",
    "Vavo":                 "#d7bde2",
    "Vo 1-3":               "#c8d6e5",
    "Onbekend":             "#bdc3c7",
}
POSITIE_VOLGORDE = list(POSITIE_KLEUREN.keys())


# ── Figuur ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(20, 12))
fig.suptitle(
    "MBO zij-instroom — wie stroomt er in, vanwaar, en welke sectoren trekken hen?",
    fontsize=15, fontweight="bold",
)


# ── Plot 1: BOL vs BBL totale instroomtrend ───────────────────────────────────
print("Plot 1: BOL vs BBL trend...")
ax = axes[0, 0]

lw_trend = (
    df69_trend[
        (df69_trend["Leerweg"].isin(["Bol totaal", "Bbl totaal"])) &
        (df69_trend["Positie"] == "Totaal instromers")
    ]
    .groupby(["Perioden", "Leerweg"])["InstromersTotaal_1"]
    .sum().unstack("Leerweg").sort_index()
)
lw_trend.plot(ax=ax, marker="o", linewidth=2, color=["#3498db", "#e67e22"])
ax.set_title("Totale instroom BOL vs BBL per jaar")
ax.set_ylabel("Instromers"); ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")
ax.text(0, -0.28,
        "Bron: CBS 85569NED — totale instroom MBO naar leerweg",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 2: Maatschappelijke positie BBL-instromers over tijd (gestapeld %) ───
print("Plot 2: positie BBL over tijd...")
ax = axes[0, 1]

bbl_pos_trend = (
    df69_bbl[df69_bbl["Positie"] != "Totaal instromers"]
    .groupby(["Perioden", "Positie"])["InstromersTotaal_1"]
    .sum().unstack("Positie").fillna(0).sort_index()
)
cols2 = [p for p in POSITIE_VOLGORDE if p in bbl_pos_trend.columns]
bbl_pos_trend = bbl_pos_trend[cols2]
totaal2 = bbl_pos_trend.sum(axis=1).replace(0, np.nan)
pct2 = bbl_pos_trend.div(totaal2, axis=0) * 100
pct2.plot(
    kind="bar", stacked=True, ax=ax, width=0.85,
    color=[POSITIE_KLEUREN[c] for c in cols2], legend=False,
)
ax.set_title("BBL-instromers: herkomst positie per jaar (%)")
ax.set_ylabel("%"); ax.set_ylim(0, 100); ax.set_xlabel("")
ax.tick_params(axis="x", rotation=45)
# Compacte legenda
handles = [plt.Rectangle((0,0),1,1, color=POSITIE_KLEUREN[c]) for c in cols2]
ax.legend(handles, cols2, fontsize=6, loc="lower right", framealpha=0.85,
          ncol=1)
ax.text(0, -0.28,
        "Bron: CBS 85569NED — BBL-instromers naar positie jaar daarvoor",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 3: Zij-instroom (werkend) per sectorkamer — absoluut + % ─────────────
print("Plot 3: zij-instroom per sectorkamer...")
ax = axes[0, 2]

sk_totaal = (
    df69_sk[df69_sk["Positie"] == "Totaal instromers"]
    .groupby("Sectorkamer")["InstromersTotaal_1"].sum()
)
sk_werkend = (
    df69_sk[df69_sk["Positie"] == "Met werk, zonder uitkering"]
    .groupby("Sectorkamer")["InstromersTotaal_1"].sum()
)
df_zijinstroom = pd.DataFrame({
    "Totaal": sk_totaal, "Werkend": sk_werkend
}).dropna()
df_zijinstroom["PctWerkend"] = df_zijinstroom["Werkend"] / df_zijinstroom["Totaal"] * 100
df_zijinstroom = df_zijinstroom[
    ~df_zijinstroom.index.str.contains("Totaal|Niet gespec", na=False)
].sort_values("PctWerkend")
df_zijinstroom.index = [korte_sk(s) for s in df_zijinstroom.index]

norm = plt.Normalize(df_zijinstroom["PctWerkend"].min(), df_zijinstroom["PctWerkend"].max())
kleuren3 = plt.cm.RdYlGn(norm(df_zijinstroom["PctWerkend"].values))
ax.barh(df_zijinstroom.index, df_zijinstroom["PctWerkend"], color=kleuren3)
for i, (idx, row) in enumerate(df_zijinstroom.iterrows()):
    ax.text(row["PctWerkend"] + 0.3, i,
            f"{row['PctWerkend']:.0f}%  ({int(row['Werkend']/1000*10)/10}k)",
            va="center", fontsize=8)
ax.set_title(f"% BBL-instromers dat al werkend was\n({LABEL_J})")
ax.set_xlabel("% van alle BBL-instromers in sectorkamer")
ax.set_xlim(0, df_zijinstroom["PctWerkend"].max() * 1.5)
ax.tick_params(axis="y", labelsize=8)
ax.text(0, -0.14,
        "Bron: CBS 85569NED — BBL-instromers, maatschappelijke positie 1 jaar eerder",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 4: Top bedrijfstakken BBL-instromers over tijd ──────────────────────
print("Plot 4: bedrijfstakken trend...")
ax = axes[1, 0]

bdt_trend = (
    df74_bdt[
        ~df74_bdt["Bedrijfstak"].str.contains("Alle economische|onbekend", case=False, na=False)
    ]
    .groupby(["Perioden", "Bedrijfstak"])["InstromersMbo_1"]
    .sum().unstack("Bedrijfstak").fillna(0).sort_index()
)
# Sorteer kolommen op recentste jaar
laatste_bdt = bdt_trend.iloc[-1].sort_values(ascending=False)
top_bdt = laatste_bdt.head(6).index
bdt_top = bdt_trend[top_bdt]
bdt_top.columns = [korte_bdt(c) for c in bdt_top.columns]

bdt_top.plot(ax=ax, marker="o", linewidth=2)
ax.set_title("Top bedrijfstakken van BBL-instromers over tijd")
ax.set_ylabel("Instromers"); ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="", fontsize=7)
ax.text(0, -0.28,
        "Bron: CBS 85574NED — BBL-instromers naar bedrijfstak jaar daarvoor",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 5: Leeftijdsverdeling BBL per sectorkamer (recentste jaar) ────────────
print("Plot 5: leeftijdsverdeling BBL per sectorkamer...")
ax = axes[1, 1]

LEEFTIJD_VOLGORDE = [
    "15 tot 20 jaar", "20 tot 25 jaar", "25 tot 30 jaar",
    "30 tot 35 jaar", "35 tot 40 jaar", "40 tot 45 jaar",
    "45 tot 50 jaar", "50 jaar of ouder",
]
LEEFTIJD_KLEUREN = plt.cm.plasma(np.linspace(0.1, 0.9, len(LEEFTIJD_VOLGORDE)))

lft_heat = (
    df74_lft[
        (~df74_lft["Sectorkamer"].str.contains("Totaal|Niet gespec", na=False)) &
        (~df74_lft["Leeftijd"].str.contains("Totaal", na=False))
    ]
    .groupby(["Sectorkamer", "Leeftijd"])["InstromersMbo_1"]
    .sum().unstack("Leeftijd").fillna(0)
)
beschikbare_lft = [l for l in LEEFTIJD_VOLGORDE if l in lft_heat.columns]
lft_heat = lft_heat[beschikbare_lft]
totaal_lft = lft_heat.sum(axis=1).replace(0, np.nan)
lft_pct = lft_heat.div(totaal_lft, axis=0) * 100
lft_pct = lft_pct.dropna(how="all").astype(float)
lft_pct.index = [korte_sk(s) for s in lft_pct.index]

lft_pct.plot(
    kind="barh", stacked=True, ax=ax, width=0.8,
    color=LEEFTIJD_KLEUREN[:len(beschikbare_lft)], legend=False,
)
ax.set_title(f"Leeftijdsverdeling BBL-instromers\nper sectorkamer ({LABEL_J})")
ax.set_xlabel("%"); ax.set_xlim(0, 100)
ax.tick_params(axis="y", labelsize=8)
handles = [plt.Rectangle((0,0),1,1, color=LEEFTIJD_KLEUREN[i]) for i in range(len(beschikbare_lft))]
ax.legend(handles, beschikbare_lft, fontsize=6, loc="lower right", framealpha=0.85)
ax.text(0, -0.14,
        "Bron: CBS 85574NED — BBL-instromers naar leeftijd en sectorkamer",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 6: Heatmap sectorkamer × maatschappelijke positie ────────────────────
print("Plot 6: heatmap sectorkamer × positie...")
ax = axes[1, 2]

heat69 = (
    df69_sk[
        (~df69_sk["Sectorkamer"].str.contains("Totaal|Niet gespec", na=False)) &
        (~df69_sk["Positie"].isin(["Totaal instromers", "Onbekend"]))
    ]
    .groupby(["Sectorkamer", "Positie"])["InstromersTotaal_1"]
    .sum().unstack("Positie").fillna(0)
)
cols6 = [p for p in POSITIE_VOLGORDE if p in heat69.columns]
heat69 = heat69[cols6]
heat69.index = [korte_sk(s) for s in heat69.index]
heat69.columns = [korte_mpos(p) for p in heat69.columns]

# Normaliseer per rij
totaal6 = heat69.sum(axis=1).replace(0, np.nan)
heat_pct6 = (heat69.div(totaal6, axis=0) * 100).astype(float)

im = ax.imshow(heat_pct6.values, aspect="auto", cmap="YlOrRd", vmin=0)
ax.set_xticks(range(len(heat_pct6.columns)))
ax.set_xticklabels(heat_pct6.columns, rotation=38, ha="right", fontsize=7)
ax.set_yticks(range(len(heat_pct6.index)))
ax.set_yticklabels(heat_pct6.index, fontsize=7)
for i in range(heat_pct6.shape[0]):
    for j in range(heat_pct6.shape[1]):
        val = heat_pct6.values[i, j]
        if val >= 4:
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=6.5,
                    color="white" if val > 40 else "black")
fig.colorbar(im, ax=ax, label="%", shrink=0.75)
ax.set_title(f"Maatschappelijke herkomst BBL-instromers\nper sectorkamer ({LABEL_J})")
ax.text(0, -0.14,
        "Bron: CBS 85569NED — BBL-instromers naar positie 1 jaar eerder",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Opslaan ──────────────────────────────────────────────────────────────────
plt.tight_layout(rect=[0, 0.02, 1, 1])
fig.text(
    0.5, 0.005,
    "Bron: CBS OpenData — 85574NED, 85569NED  ·  opendata.cbs.nl",
    ha="center", fontsize=8, color="gray",
)
output_path = f"{OUTPUT_DIR}/mbo_zij_instroom.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
print(f"Opgeslagen: {output_path}")
