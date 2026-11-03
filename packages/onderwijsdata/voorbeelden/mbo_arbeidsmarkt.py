"""
MBO-uitstromers en de arbeidsmarkt
Combineert drie CBS-datasets:
  85696NED — Arbeidsmarktpositie na verlaten mbo
  85699NED — Bedrijfstakken van werkende mbo-uitstromers
  83832NED — Uurloon mbo-uitstromers per studierichting / bedrijfstak
"""

import pandas as pd
import matplotlib.pyplot as plt
from onderwijsdata import client

# ── Dimensie-lookups ─────────────────────────────────────────────────────────
print("Dimensies ophalen...")

ds96, ds99, ds32 = "85696NED", "85699NED", "83832NED"

pos96 = client.dimension(ds96, "Arbeidsmarktpositie")
uit96 = client.dimension(ds96, "UitstromersMboMetEnZonderDiploma")
ric96 = client.dimension(ds96, "Studierichting")
pei96 = client.dimension(ds96, "Peilmoment")
per96 = client.dimension(ds96, "Perioden")
ges96 = client.dimension(ds96, "Geslacht")
pke96 = client.dimension(ds96, "Persoonskenmerken")

bdt99 = client.dimension(ds99, "BedrijfstakkenSBI2008")
ric99 = client.dimension(ds99, "Studierichting")
uit99 = client.dimension(ds99, "UitstromersMboMetEnZonderDiploma")
per99 = client.dimension(ds99, "Perioden")
pei99 = client.dimension(ds99, "Peilmoment")
lft99 = client.dimension(ds99, "Leeftijd")

bdt32 = client.dimension(ds32, "BedrijfstakkenSBI2008")
ric32 = client.dimension(ds32, "Studierichting")
uit32 = client.dimension(ds32, "UitstromersMboMetEnZonderDiploma")
per32 = client.dimension(ds32, "Perioden")
pei32 = client.dimension(ds32, "Peilmoment")
ges32 = client.dimension(ds32, "Geslacht")

# Inverse
inv = lambda d: {v: k for k, v in d.items()}
pos96_inv = inv(pos96); uit96_inv = inv(uit96); ric96_inv = inv(ric96)
pei96_inv = inv(pei96); ges96_inv = inv(ges96); pke96_inv = inv(pke96)
bdt99_inv = inv(bdt99); ric99_inv = inv(ric99); lft99_inv = inv(lft99)
bdt32_inv = inv(bdt32); ric32_inv = inv(ric32); uit32_inv = inv(uit32)
pei32_inv = inv(pei32); ges32_inv = inv(ges32)

# Veelgebruikte codes
TOT_G96   = ges96_inv["Totaal"]
TOT_PKE   = pke96_inv["Totaal"]
TOT_UIT96 = uit96_inv["Bol-vt en bbl totaal"]
MET_DIP   = uit96_inv["Bol-vt en bbl totaal met diploma"]
ZDR_DIP   = uit96_inv["Bol-vt en bbl totaal zonder diploma"]
TOT_POS   = pos96_inv["Totaal"]
TOT_RIC96 = ric96_inv["Totaal"]
EEN_JAAR  = pei96_inv["1 jaar na verlaten onderwijs"]

TOT_G99   = list(ges96.keys())[0]   # zelfde als TOT_G96
TOT_LFT99 = lft99_inv["Totaal"]
TOT_UIT99 = list(uit99.keys())[0]
TOT_BDT99 = bdt99_inv["A-U Alle economische activiteiten"]
TOT_RIC99 = list(ric99.keys())[0]
EEN_J99   = [k for k, v in pei99.items() if "1 jaar" in v][0]

TOT_G32   = ges32_inv["Totaal"]
TOT_UIT32 = uit32_inv["Bol-vt en bbl totaal"]
TOT_RIC32 = ric32_inv["Totaal"]
TOT_BDT32 = bdt32_inv["A-U Alle economische activiteiten"]
EEN_J32   = pei32_inv["1 jaar na verlaten onderwijs"]

RECENTSTE_ALL = max(per96.keys())
# Recentste jaar waarvoor studierichting-uitsplitsing beschikbaar is (kan 1 jaar achter lopen)
_probe = client.data(ds96, **{"$filter": (
    f"Geslacht eq '{[k for k,v in ges96.items() if v=='Totaal'][0]}' and "
    f"trim(Persoonskenmerken) eq '{[k for k,v in pke96.items() if v=='Totaal'][0]}' and "
    f"UitstromersMboMetEnZonderDiploma eq '{[k for k,v in uit96.items() if v=='Bol-vt en bbl totaal'][0]}' and "
    f"Peilmoment eq '{[k for k,v in pei96.items() if '1 jaar' in v][0]}'"
)})
import pandas as _pd
_df_probe = _pd.DataFrame(_probe)
_df_probe["_ric"] = _df_probe["Studierichting"].map(ric96)
_df_probe_ric = _df_probe[_df_probe["_ric"] != "Totaal"].dropna(subset=["UitstromersMbo_1"])
RECENTSTE = _df_probe_ric["Perioden"].max()
LABEL_J   = per96[RECENTSTE]
print(f"Recentste jaar met studierichting-data: {LABEL_J}")


# ── Decode-helpers ───────────────────────────────────────────────────────────
def decode(df, maps):
    df = df.copy()
    for col, m in maps.items():
        if col in df.columns:
            df[col] = df[col].map(m)
    return df.dropna(subset=["Perioden"])


# ── Data ophalen (enkel eq-filters, Totaal-rijen achteraf uitsluiten) ─────────
print("85696 — positie over tijd (trend)...")
rows = client.data(ds96, **{"$filter": (
    f"Geslacht eq '{TOT_G96}' and trim(Persoonskenmerken) eq '{TOT_PKE}' and "
    f"UitstromersMboMetEnZonderDiploma eq '{TOT_UIT96}' and "
    f"Studierichting eq '{TOT_RIC96}' and Peilmoment eq '{EEN_JAAR}'"
)})
df96_trend = decode(pd.DataFrame(rows), {
    "Arbeidsmarktpositie": pos96, "Perioden": per96,
    "Studierichting": ric96, "UitstromersMboMetEnZonderDiploma": uit96,
})
df96_trend = df96_trend[df96_trend["Arbeidsmarktpositie"] != "Totaal"]

print("85696 — positie per studierichting (recentste jaar)...")
rows = client.data(ds96, **{"$filter": (
    f"Geslacht eq '{TOT_G96}' and trim(Persoonskenmerken) eq '{TOT_PKE}' and "
    f"UitstromersMboMetEnZonderDiploma eq '{TOT_UIT96}' and "
    f"Peilmoment eq '{EEN_JAAR}' and Perioden eq '{RECENTSTE}'"
)})
df96_ric = decode(pd.DataFrame(rows), {
    "Arbeidsmarktpositie": pos96, "Perioden": per96, "Studierichting": ric96,
})
df96_ric = df96_ric[
    (df96_ric["Studierichting"] != "Totaal") &
    (df96_ric["Arbeidsmarktpositie"] != "Totaal")
]

print("85696 — diploma vs. geen diploma...")
rows = client.data(ds96, **{"$filter": (
    f"Geslacht eq '{TOT_G96}' and trim(Persoonskenmerken) eq '{TOT_PKE}' and "
    f"Studierichting eq '{TOT_RIC96}' and Peilmoment eq '{EEN_JAAR}'"
)})
df96_dip = decode(pd.DataFrame(rows), {
    "Arbeidsmarktpositie": pos96, "Perioden": per96,
    "UitstromersMboMetEnZonderDiploma": uit96,
})
df96_dip = df96_dip[
    df96_dip["UitstromersMboMetEnZonderDiploma"].isin(
        ["Bol-vt en bbl totaal met diploma", "Bol-vt en bbl totaal zonder diploma"]
    ) & (df96_dip["Arbeidsmarktpositie"] != "Totaal")
]

print("85699 — bedrijfstakken per studierichting (recentste jaar)...")
rows = client.data(ds99, **{"$filter": (
    f"Geslacht eq '{TOT_G99}' and trim(Leeftijd) eq '{TOT_LFT99}' and "
    f"UitstromersMboMetEnZonderDiploma eq '{TOT_UIT99}' and "
    f"Peilmoment eq '{EEN_J99}' and Perioden eq '{RECENTSTE}'"
)})
df99 = decode(pd.DataFrame(rows), {
    "BedrijfstakkenSBI2008": bdt99, "Studierichting": ric99, "Perioden": per99,
})
df99 = df99[
    (df99["Studierichting"] != "Totaal") &
    (df99["BedrijfstakkenSBI2008"] != "A-U Alle economische activiteiten")
].rename(columns={"BedrijfstakkenSBI2008": "Bedrijfstak"})

print("83832 — uurloon per studierichting (recentste jaar)...")
rows = client.data(ds32, **{"$filter": (
    f"Geslacht eq '{TOT_G32}' and UitstromersMboMetEnZonderDiploma eq '{TOT_UIT32}' and "
    f"BedrijfstakkenSBI2008 eq '{TOT_BDT32}' and "
    f"Peilmoment eq '{EEN_J32}' and Perioden eq '{RECENTSTE}'"
)})
df32_ric = decode(pd.DataFrame(rows), {
    "Studierichting": ric32, "Perioden": per32, "BedrijfstakkenSBI2008": bdt32,
})
df32_ric = df32_ric[df32_ric["Studierichting"] != "Totaal"]

print("83832 — uurloon per bedrijfstak (recentste jaar)...")
rows = client.data(ds32, **{"$filter": (
    f"Geslacht eq '{TOT_G32}' and UitstromersMboMetEnZonderDiploma eq '{TOT_UIT32}' and "
    f"Studierichting eq '{TOT_RIC32}' and "
    f"Peilmoment eq '{EEN_J32}' and Perioden eq '{RECENTSTE}'"
)})
df32_bdt = decode(pd.DataFrame(rows), {
    "BedrijfstakkenSBI2008": bdt32, "Studierichting": ric32, "Perioden": per32,
})
df32_bdt = df32_bdt[
    df32_bdt["BedrijfstakkenSBI2008"] != "A-U Alle economische activiteiten"
].rename(columns={"BedrijfstakkenSBI2008": "Bedrijfstak"})

# 85699 — totaal bedrijfstakken (voor aandeel in plot 6)
print("85699 — bedrijfstak-aandelen totaal (recentste jaar)...")
rows = client.data(ds99, **{"$filter": (
    f"Geslacht eq '{TOT_G99}' and trim(Leeftijd) eq '{TOT_LFT99}' and "
    f"UitstromersMboMetEnZonderDiploma eq '{TOT_UIT99}' and "
    f"Studierichting eq '{TOT_RIC99}' and "
    f"Peilmoment eq '{EEN_J99}' and Perioden eq '{RECENTSTE}'"
)})
df99_bdt = decode(pd.DataFrame(rows), {
    "BedrijfstakkenSBI2008": bdt99, "Studierichting": ric99, "Perioden": per99,
})
df99_bdt = df99_bdt[
    df99_bdt["BedrijfstakkenSBI2008"] != "A-U Alle economische activiteiten"
].rename(columns={"BedrijfstakkenSBI2008": "Bedrijfstak"})


# ── Kleurenpalet ─────────────────────────────────────────────────────────────
POSITIE_KLEUREN = {
    "Met werk, zonder uitkering":    "#2ecc71",
    "Met werk, met uitkering":       "#82c982",
    "Terug in onderwijs":            "#3498db",
    "Zonder werk, met uitkering":    "#e67e22",
    "Zonder werk, zonder uitkering": "#e74c3c",
    "Onbekend: niet in BRP":         "#bdc3c7",
}
POSITIE_VOLGORDE = list(POSITIE_KLEUREN.keys())

def korte(label, sep=" "):
    """Verwijder numeriek prefix '01 Onderwijs' → 'Onderwijs'."""
    parts = label.split(sep, 1)
    if len(parts) == 2 and parts[0][:2].strip().isdigit():
        return parts[1].strip()
    return label


# ── Figuur ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(20, 12))
fig.suptitle(
    "MBO-uitstromers en de arbeidsmarkt — 1 jaar na verlaten onderwijs",
    fontsize=15, fontweight="bold",
)


# ── Plot 1: Arbeidsmarktpositie over tijd (gestapeld 100%) ───────────────────
print("Plot 1...")
ax = axes[0, 0]
pivot1 = (
    df96_trend
    .groupby(["Perioden", "Arbeidsmarktpositie"])["UitstromersMbo_1"]
    .sum()
    .unstack("Arbeidsmarktpositie")
    .sort_index()
    .fillna(0)
)
cols1 = [p for p in POSITIE_VOLGORDE if p in pivot1.columns]
pivot1 = pivot1[cols1]
pct1 = pivot1.div(pivot1.sum(axis=1), axis=0) * 100
pct1.plot(
    kind="bar", stacked=True, ax=ax, width=0.85,
    color=[POSITIE_KLEUREN[c] for c in cols1], legend=False,
)
ax.set_title("Arbeidsmarktpositie over tijd (%)")
ax.set_ylabel("%"); ax.set_xlabel(""); ax.set_ylim(0, 100)
ax.tick_params(axis="x", rotation=45)
ax.legend(cols1, fontsize=7, loc="lower left", framealpha=0.85)
ax.text(0, -0.30, "Bron: CBS 85696NED — 1 jaar na verlaten mbo, totaal uitstromers",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 2: Arbeidsmarktpositie per studierichting (recentste jaar, horizontaal)
print("Plot 2...")
ax = axes[0, 1]
pivot2 = (
    df96_ric
    .groupby(["Studierichting", "Arbeidsmarktpositie"])["UitstromersMbo_1"]
    .sum()
    .unstack("Arbeidsmarktpositie")
    .fillna(0)
)
cols2 = [p for p in POSITIE_VOLGORDE if p in pivot2.columns]
pivot2 = pivot2[cols2]
totaal2 = pivot2.sum(axis=1).replace(0, pd.NA)
pct2 = pivot2.div(totaal2, axis=0) * 100
pct2 = pct2.dropna(how="all")
if "Met werk, zonder uitkering" in pct2.columns:
    pct2 = pct2.sort_values("Met werk, zonder uitkering")
pct2.index = [korte(r) for r in pct2.index]
pct2.plot(
    kind="barh", stacked=True, ax=ax, width=0.8,
    color=[POSITIE_KLEUREN[c] for c in cols2], legend=False,
)
ax.set_title(f"Positie per studierichting\n({LABEL_J}, %)")
ax.set_xlabel("%"); ax.set_xlim(0, 100)
ax.tick_params(axis="y", labelsize=8)
ax.text(0, -0.14, "Bron: CBS 85696NED — totaal uitstromers",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 3: Diploma vs. geen diploma — % met werk over tijd ──────────────────
print("Plot 3...")
ax = axes[0, 2]
dip_pivot = (
    df96_dip
    .groupby(["Perioden", "UitstromersMboMetEnZonderDiploma", "Arbeidsmarktpositie"])["UitstromersMbo_1"]
    .sum()
    .unstack("Arbeidsmarktpositie")
    .fillna(0)
)
totaal_dip = dip_pivot.sum(axis=1)
pct_dip = dip_pivot.div(totaal_dip, axis=0) * 100

kleuren_dip = {"met diploma": "#2ecc71", "zonder diploma": "#e74c3c"}
for dip_type, grp in pct_dip.groupby("UitstromersMboMetEnZonderDiploma"):
    perioden = grp.index.get_level_values("Perioden")
    label = "Met diploma" if "met diploma" in dip_type.lower() else "Zonder diploma"
    kleur = kleuren_dip["met diploma"] if "met diploma" in dip_type.lower() else kleuren_dip["zonder diploma"]
    if "Met werk, zonder uitkering" in grp.columns:
        ax.plot(perioden, grp["Met werk, zonder uitkering"].values,
                marker="o", linewidth=2, label=label, color=kleur)
    if "Met werk, met uitkering" in grp.columns:
        ax.plot(perioden, grp["Met werk, met uitkering"].values,
                marker="s", linewidth=1.5, linestyle="--", label=f"{label} (m. uitkering)", color=kleur, alpha=0.6)

ax.set_title("% met werk — diploma vs. geen diploma")
ax.set_ylabel("%"); ax.set_ylim(0, 80)
ax.tick_params(axis="x", rotation=45)
ax.legend(fontsize=7)
ax.text(0, -0.14, "Bron: CBS 85696NED — 1 jaar na verlaten mbo",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 4: Heatmap studierichting × bedrijfstak ──────────────────────────────
print("Plot 4...")
ax = axes[1, 0]
heat = (
    df99
    .groupby(["Studierichting", "Bedrijfstak"])["TotaalUitstromersMetWerk_1"]
    .sum()
    .unstack("Bedrijfstak")
    .fillna(0)
)
heat.index = [korte(r) for r in heat.index]
heat.columns = [korte(c) for c in heat.columns]
heat_pct = heat.div(heat.sum(axis=1), axis=0) * 100

im = ax.imshow(heat_pct.values, aspect="auto", cmap="YlOrRd", vmin=0)
ax.set_xticks(range(len(heat_pct.columns)))
ax.set_xticklabels(heat_pct.columns, rotation=38, ha="right", fontsize=7)
ax.set_yticks(range(len(heat_pct.index)))
ax.set_yticklabels(heat_pct.index, fontsize=7)
for i in range(heat_pct.shape[0]):
    for j in range(heat_pct.shape[1]):
        val = heat_pct.values[i, j]
        if val >= 5:
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=6,
                    color="white" if val > 45 else "black")
ax.set_title(f"Werkende uitstromers per sector\n({LABEL_J}, % per studierichting)")
fig.colorbar(im, ax=ax, label="%", shrink=0.75)
ax.text(0, -0.14, "Bron: CBS 85699NED — 1 jaar na verlaten mbo",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 5: Uurloon per studierichting ────────────────────────────────────────
print("Plot 5...")
ax = axes[1, 1]
loon_ric = (
    df32_ric
    .dropna(subset=["UurloonWerknemersNaVerlatenMbo_1"])
    .groupby("Studierichting")["UurloonWerknemersNaVerlatenMbo_1"]
    .mean()
    .sort_values()
)
loon_ric.index = [korte(r) for r in loon_ric.index]
gem_loon = loon_ric.mean()

kleuren_loon = ["#e74c3c" if v < gem_loon else "#2ecc71" for v in loon_ric.values]
ax.barh(loon_ric.index, loon_ric.values, color=kleuren_loon)
ax.axvline(gem_loon, color="steelblue", linestyle="--", linewidth=1.5,
           label=f"Gemiddeld: €{gem_loon:.2f}/u")
for i, (idx, val) in enumerate(loon_ric.items()):
    ax.text(val + 0.05, i, f"€{val:.2f}", va="center", fontsize=8)
ax.set_title(f"Gemiddeld uurloon per studierichting\n({LABEL_J})")
ax.set_xlabel("€ per uur")
ax.tick_params(axis="y", labelsize=8)
ax.legend(fontsize=8)
ax.text(0, -0.14, "Bron: CBS 83832NED — werknemers 1 jaar na verlaten mbo",
        transform=ax.transAxes, fontsize=7, color="gray")


# ── Plot 6: Combinatie 85699 × 83832 — bedrijfstak: loon én aandeel werkenden ─
print("Plot 6...")
ax = axes[1, 2]
loon_b = (
    df32_bdt
    .dropna(subset=["UurloonWerknemersNaVerlatenMbo_1"])
    .groupby("Bedrijfstak")["UurloonWerknemersNaVerlatenMbo_1"]
    .mean()
)
aandeel_b = (
    df99_bdt
    .groupby("Bedrijfstak")["TotaalUitstromersMetWerk_1"]
    .sum()
)
gem6 = pd.DataFrame({"Uurloon": loon_b, "Werkenden": aandeel_b}).dropna()
totaal_w = gem6["Werkenden"].sum()
gem6["AandeelPct"] = gem6["Werkenden"] / totaal_w * 100
gem6 = gem6.sort_values("Uurloon")
gem6.index = [korte(b) for b in gem6.index]

norm = plt.Normalize(gem6["Uurloon"].min(), gem6["Uurloon"].max())
kleuren6 = plt.cm.RdYlGn(norm(gem6["Uurloon"].values))
bars6 = ax.barh(gem6.index, gem6["Uurloon"], color=kleuren6)
for i, (idx, row) in enumerate(gem6.iterrows()):
    ax.text(
        row["Uurloon"] + 0.05, i,
        f"€{row['Uurloon']:.2f}  ({row['AandeelPct']:.0f}% uitstromers)",
        va="center", fontsize=8,
    )
ax.set_title(f"Uurloon per bedrijfstak ({LABEL_J})\n+ aandeel werkende mbo-uitstromers")
ax.set_xlabel("€ per uur (gemiddeld, 1jr na mbo)")
ax.tick_params(axis="y", labelsize=8)
ax.set_xlim(0, gem6["Uurloon"].max() * 1.65)
ax.text(
    0, -0.14,
    "Bron: CBS 83832NED (uurloon) × 85699NED (aandelen) — 1 jaar na verlaten mbo",
    transform=ax.transAxes, fontsize=7, color="gray",
)


# ── Opslaan ──────────────────────────────────────────────────────────────────
plt.tight_layout(rect=[0, 0.02, 1, 1])
fig.text(
    0.5, 0.005,
    "Bron: CBS OpenData — 85696NED, 85699NED, 83832NED  ·  opendata.cbs.nl",
    ha="center", fontsize=8, color="gray",
)
plt.savefig("voorbeelden/output/mbo_arbeidsmarkt.png", dpi=150, bbox_inches="tight")
print("Opgeslagen: voorbeelden/output/mbo_arbeidsmarkt.png")
