"""
Volledig integratietest van roa en uwv modules.
Alles moet slagen voor push naar main.
"""
import sys
sys.path.insert(0, "src")

from riodata import catalog, roa, uwv

GROEN = "\033[92m✓\033[0m"
ROOD  = "\033[91m✗\033[0m"
fouten = []

def ok(label: str, detail: str = "") -> None:
    print(f"  {GROEN} {label}" + (f"  ({detail})" if detail else ""))

def fout(label: str, detail: str = "") -> None:
    print(f"  {ROOD} {label}" + (f"  ({detail})" if detail else ""))
    fouten.append(label)


# ── catalog() ─────────────────────────────────────────────────────────────────
print("\n=== catalog() ===")

for source in ("rio", "duo", "roa", "uwv", "all"):
    try:
        records = catalog(source=source)
        ok(f"source='{source}' — {len(records)} records")
        if source == "all":
            leveranciers = {r["leverancier"] for r in records}
            ok(f"  leveranciers: {sorted(leveranciers)}")
    except Exception as e:
        fout(f"source='{source}'", str(e))


# ── roa.catalog() ─────────────────────────────────────────────────────────────
print("\n=== roa.catalog() ===")
try:
    records = roa.catalog()
    ok(f"{len(records)} datasets")
    for r in records:
        ok(f"  {r['_roa_id']}: {r['bron']} — {len(r['_resources'])} resources")
        assert r["leverancier"] == "ROA"
        assert r["_roa_id"] in ("ais2030", "ais2028")
except Exception as e:
    fout("roa.catalog()", str(e))


# ── roa.resources() ───────────────────────────────────────────────────────────
print("\n=== roa.resources() ===")
for ds in ("ais2030", "ais2028"):
    try:
        res = roa.resources(ds)
        ok(f"{ds}: {len(res)} resources — {[r['naam'] for r in res]}")
    except Exception as e:
        fout(f"roa.resources({ds})", str(e))


# ── roa.load() — klein bestand ─────────────────────────────────────────────
print("\n=== roa.load() — uitkomsten (klein, ~0.2 MB) ===")
try:
    df = roa.load("ais2030", "uitkomsten")
    ok(f"DataFrame geladen: {df.shape[0]} rijen × {df.shape[1]} kolommen")
    ok(f"Kolommen: {list(df.columns[:6])}")
    ok(f"Eerste rij: {df.iloc[0].to_dict()}")
except Exception as e:
    fout("roa.load('ais2030', 'uitkomsten')", str(e))

print("\n=== roa.load() — toelichting (encoding-test) ===")
try:
    df = roa.load("ais2030", "toelichting")
    ok(f"Toelichting geladen: {df.shape[0]} rijen × {df.shape[1]} kolommen")
    ok(f"Kolommen: {list(df.columns[:4])}")
except Exception as e:
    fout("roa.load('ais2030', 'toelichting')", str(e))


# ── uwv.catalog() ─────────────────────────────────────────────────────────────
print("\n=== uwv.catalog() ===")
try:
    records = uwv.catalog()
    ok(f"{len(records)} records")
    r = records[0]
    assert r["leverancier"] == "UWV"
    ok(f"  bron: {r['bron']}")
    ok(f"  periode: {r['periode']}")
except Exception as e:
    fout("uwv.catalog()", str(e))


# ── uwv.resources() ───────────────────────────────────────────────────────────
print("\n=== uwv.resources() ===")
try:
    snaps = uwv.resources()
    ok(f"{len(snaps)} snapshots beschikbaar")
    ok(f"  Meest recent: {snaps[0]['created'][:10]}")
    ok(f"  Oudste: {snaps[-1]['created'][:10]}")
except Exception as e:
    fout("uwv.resources()", str(e))


# ── uwv.load() ────────────────────────────────────────────────────────────────
print("\n=== uwv.load() — meest recente snapshot ===")
try:
    df = uwv.load()
    ok(f"DataFrame geladen: {df.shape[0]} rijen × {df.shape[1]} kolommen")
    ok(f"Kolommen: {list(df.columns[:6])}")
    ok(f"REC_TYPE waarden: {df['REC_TYPE'].unique().tolist()}")
    ok(f"Provincies: {sorted(df['PROVINCIE'].dropna().unique().tolist())[:5]}")
    ok(f"Datum: {df['PEILDATUM'].iloc[0]}")
except Exception as e:
    fout("uwv.load()", str(e))

print("\n=== uwv.load(rec_type='Vacature') ===")
try:
    df = uwv.load(rec_type="Vacature")
    ok(f"Alleen vacatures: {df.shape[0]} rijen")
    assert (df["REC_TYPE"].str.lower() == "vacature").all()
except Exception as e:
    fout("uwv.load(rec_type='Vacature')", str(e))

print("\n=== uwv.load(date='2022-01-18') ===")
try:
    df = uwv.load(date="2022-01-18")
    ok(f"Historische snapshot: {df['PEILDATUM'].iloc[0]}, {df.shape[0]} rijen")
except Exception as e:
    fout("uwv.load(date='2022-01-18')", str(e))


# ── Samenvatting ──────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
if fouten:
    print(f"{ROOD} {len(fouten)} FOUTEN — niet pushen!")
    for f in fouten:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"{GROEN} Alle tests geslaagd — klaar voor push.")
