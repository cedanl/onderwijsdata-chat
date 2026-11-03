import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from onderwijsdata import client

DATASET = "85423NED"

# --- Data laden ---
geslacht_map    = client.dimension(DATASET, "Geslacht")
soort_map       = client.dimension(DATASET, "Onderwijssoort")
fase_map        = client.dimension(DATASET, "Opleidingsfase")
vorm_map        = client.dimension(DATASET, "Opleidingsvorm")
perioden_map    = client.dimension(DATASET, "Perioden")

rows = client.data(DATASET, **{"$top": 10000})
df = pd.DataFrame(rows)

df["Geslacht"]       = df["Geslacht"].map(geslacht_map)
df["Onderwijssoort"] = df["Onderwijssoort"].map(soort_map)
df["Opleidingsfase"] = df["Opleidingsfase"].map(fase_map)
df["Opleidingsvorm"] = df["Opleidingsvorm"].map(vorm_map)
df["Perioden"]       = df["Perioden"].map(perioden_map)
df = df.dropna()

N = df["TotaalIngeschrevenen_1"]

fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("Hoger Onderwijs Nederland — Ingeschrevenen 2011–2026", fontsize=15, fontweight="bold")

def fmt_k(x, _): return f"{int(x/1000)}k"

# ── Plot 1: HBO vs WO trend ──────────────────────────────────────────────────
ax = axes[0, 0]
hbo_wo = (
    df[
        (df["Geslacht"] == "Totaal mannen en vrouwen") &
        (df["Opleidingsfase"] == "Opleidingsfase totaal") &
        (df["Opleidingsvorm"] == "Totaal opleidingsvorm") &
        (df["Onderwijssoort"].isin(["Hoger beroepsonderwijs", "Wetenschappelijk onderwijs"]))
    ]
    .groupby(["Perioden", "Onderwijssoort"])["TotaalIngeschrevenen_1"]
    .sum()
    .unstack()
    .sort_index()
)
hbo_wo.plot(ax=ax, marker="o", linewidth=2)
ax.set_title("HBO vs WO — ingeschrevenen per jaar")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

# ── Plot 2: Vrouwenaandeel over tijd per onderwijssoort ──────────────────────
ax = axes[0, 1]
pivot = (
    df[
        (df["Geslacht"].isin(["Mannen", "Vrouwen"])) &
        (df["Opleidingsfase"] == "Opleidingsfase totaal") &
        (df["Opleidingsvorm"] == "Totaal opleidingsvorm") &
        (df["Onderwijssoort"].isin(["Hoger beroepsonderwijs", "Wetenschappelijk onderwijs"]))
    ]
    .groupby(["Perioden", "Onderwijssoort", "Geslacht"])["TotaalIngeschrevenen_1"]
    .sum()
    .unstack("Geslacht")
)
pivot["pct_vrouw"] = pivot["Vrouwen"] / (pivot["Mannen"] + pivot["Vrouwen"]) * 100
for soort, grp in pivot["pct_vrouw"].groupby("Onderwijssoort"):
    ax.plot(grp.index.get_level_values("Perioden"), grp.values, marker="o", label=soort, linewidth=2)
ax.axhline(50, color="gray", linestyle="--", linewidth=1)
ax.set_title("Vrouwenaandeel (%) per onderwijstype")
ax.set_ylabel("%")
ax.set_ylim(40, 65)
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

# ── Plot 3: Bachelor vs Master trend (totaal HO) ─────────────────────────────
ax = axes[0, 2]
fase = (
    df[
        (df["Geslacht"] == "Totaal mannen en vrouwen") &
        (df["Onderwijssoort"] == "Hoger onderwijs") &
        (df["Opleidingsvorm"] == "Totaal opleidingsvorm") &
        (df["Opleidingsfase"].isin(["Bachelor- en doctoraalopleidingen", "Master- en vervolgopleidingen"]))
    ]
    .groupby(["Perioden", "Opleidingsfase"])["TotaalIngeschrevenen_1"]
    .sum()
    .unstack()
    .sort_index()
)
fase.plot(ax=ax, marker="o", linewidth=2)
ax.set_title("Bachelor vs Master — ingeschrevenen per jaar")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

# ── Plot 4: Deeltijd als % van totaal ────────────────────────────────────────
ax = axes[1, 0]
vorm = (
    df[
        (df["Geslacht"] == "Totaal mannen en vrouwen") &
        (df["Onderwijssoort"] == "Hoger onderwijs") &
        (df["Opleidingsfase"] == "Opleidingsfase totaal") &
        (df["Opleidingsvorm"].isin(["Voltijd", "Deeltijd", "Duaal"]))
    ]
    .groupby(["Perioden", "Opleidingsvorm"])["TotaalIngeschrevenen_1"]
    .sum()
    .unstack()
    .sort_index()
)
totaal_per_jaar = vorm.sum(axis=1)
(vorm.div(totaal_per_jaar, axis=0) * 100).plot(ax=ax, marker="o", linewidth=2)
ax.set_title("Aandeel opleidingsvorm (%) per jaar")
ax.set_ylabel("%")
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

# ── Plot 5: Groeiindex HBO en WO (2011 = 100) ────────────────────────────────
ax = axes[1, 1]
basis = hbo_wo.iloc[0]
index = (hbo_wo / basis * 100)
index.plot(ax=ax, marker="o", linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=1)
ax.set_title("Groeiindex ingeschrevenen (2011/'12 = 100)")
ax.set_ylabel("Index")
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

# ── Plot 6: Man/Vrouw gestapeld per jaar (totaal HO) ─────────────────────────
ax = axes[1, 2]
mv = (
    df[
        (df["Geslacht"].isin(["Mannen", "Vrouwen"])) &
        (df["Onderwijssoort"] == "Hoger onderwijs") &
        (df["Opleidingsfase"] == "Opleidingsfase totaal") &
        (df["Opleidingsvorm"] == "Totaal opleidingsvorm")
    ]
    .groupby(["Perioden", "Geslacht"])["TotaalIngeschrevenen_1"]
    .sum()
    .unstack()
    .sort_index()
)
mv.plot(kind="bar", stacked=True, ax=ax, width=0.8)
ax.set_title("Ingeschrevenen man/vrouw per jaar")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
ax.tick_params(axis="x", rotation=45)
ax.legend(title="")

plt.tight_layout()
fig.text(
    0.5, -0.02,
    f"Bron: CBS OpenData — {DATASET} · Hoger onderwijs; ingeschrevenen · "
    f"https://opendata.cbs.nl/ODataApi/OData/{DATASET}",
    ha="center", fontsize=8, color="gray"
)
plt.savefig("voorbeelden/output/ho_ingeschrevenen.png", dpi=150, bbox_inches="tight")
print("Opgeslagen: voorbeelden/output/ho_ingeschrevenen.png")
