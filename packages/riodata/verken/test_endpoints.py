"""
Test alle endpoints die ROA en UWV modules gaan gebruiken.
Draai dit VOOR je pusht — alles moet slagen.
"""
import io
import json
import zipfile
import httpx

DATAVERSE_BASE = "https://dataverse.nl/api"
OVERHEID_CKAN = "https://data.overheid.nl/data/api/3/action"

GROEN = "\033[92m✓\033[0m"
ROOD  = "\033[91m✗\033[0m"


def ok(label: str, detail: str = "") -> None:
    print(f"  {GROEN} {label}" + (f"  ({detail})" if detail else ""))


def fout(label: str, detail: str = "") -> None:
    print(f"  {ROOD} {label}" + (f"  ({detail})" if detail else ""))


# ── ROA: DataverseNL ──────────────────────────────────────────────────────────

print("\n=== ROA — DataverseNL ===")

ROA_DOIS = {
    "AIS tot 2030": "doi:10.34894/DVQTOG",
    "AIS tot 2028": "doi:10.34894/UIQHCI",
}

roa_files: dict[str, list[dict]] = {}

for naam, doi in ROA_DOIS.items():
    print(f"\n{naam} ({doi})")
    try:
        r = httpx.get(
            f"{DATAVERSE_BASE}/datasets/:persistentId/versions/:latest/files",
            params={"persistentId": doi},
            timeout=30,
        )
        r.raise_for_status()
        files = r.json()["data"]
        roa_files[naam] = files
        ok(f"Dataset bereikbaar — {len(files)} bestanden")
        for f in files:
            df = f["dataFile"]
            size_mb = df.get("filesize", 0) / 1024 / 1024
            ok(f"  [{df['id']}] {df['filename']} ({size_mb:.1f} MB)")
    except Exception as e:
        fout(f"Dataset niet bereikbaar: {e}")

# Test download van kleinste CSV (toelichting-bestand)
print("\nTest download kleinste ROA-bestand...")
for naam, files in roa_files.items():
    csvs = [f for f in files if f["dataFile"]["filename"].endswith(".csv")]
    if not csvs:
        continue
    smallest = min(csvs, key=lambda f: f["dataFile"].get("filesize", 999999999))
    df_meta = smallest["dataFile"]
    try:
        r = httpx.get(
            f"{DATAVERSE_BASE}/access/datafile/{df_meta['id']}",
            timeout=60, follow_redirects=True,
        )
        r.raise_for_status()
        import pandas as pd
        df = pd.read_csv(io.BytesIO(r.content), sep=";", encoding="utf-8-sig", nrows=5)
        ok(f"{naam}: {df_meta['filename']} — {list(df.columns[:5])}")
    except Exception as e:
        fout(f"{naam}: {df_meta['filename']} — {e}")
    break  # alleen één testen


# ── UWV: data.overheid.nl ─────────────────────────────────────────────────────

print("\n=== UWV — data.overheid.nl CKAN ===")

try:
    r = httpx.get(
        f"{OVERHEID_CKAN}/package_show",
        params={"id": "uwv-open-match-data"},
        timeout=15,
    )
    r.raise_for_status()
    pkg = r.json()["result"]
    resources = pkg.get("resources", [])
    zips = [res for res in resources if "ZIP" in res.get("format", "").upper()]
    zips_sorted = sorted(zips, key=lambda r: r.get("created", ""), reverse=True)
    ok(f"Dataset bereikbaar — {len(resources)} resources, {len(zips)} ZIPs")
    ok(f"Meest recent: {zips_sorted[0].get('created','?')[:10]}")
    ok(f"Oudste: {zips_sorted[-1].get('created','?')[:10]}")

    # Test download meest recente ZIP
    print("\nTest download meest recente UWV ZIP...")
    latest = zips_sorted[0]
    r2 = httpx.get(latest["url"], timeout=60, follow_redirects=True)
    r2.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r2.content))
    csvs = [n for n in zf.namelist() if n.endswith(".csv")]
    ok(f"ZIP downloadbaar — {len(r2.content)//1024} KB, {len(csvs)} CSV-bestanden")

    with zf.open(csvs[0]) as f:
        raw = f.read().decode("utf-8-sig", errors="replace")
        header = raw.splitlines()[0]
        kolommen = header.split(";")
        ok(f"CSV leesbaar — {len(kolommen)} kolommen, eerste: {kolommen[:4]}")

except Exception as e:
    fout(f"UWV fout: {e}")


# ── Bestaand: DUO ─────────────────────────────────────────────────────────────

print("\n=== Bestaand: DUO CKAN ===")
try:
    r = httpx.get(
        "https://onderwijsdata.duo.nl/api/3/action/package_search",
        params={"rows": 1},
        timeout=15,
    )
    r.raise_for_status()
    count = r.json()["result"]["count"]
    ok(f"DUO CKAN bereikbaar — {count} datasets")
except Exception as e:
    fout(f"DUO CKAN: {e}")


# ── Bestaand: RIO ─────────────────────────────────────────────────────────────

print("\n=== Bestaand: RIO LOD API ===")
try:
    r = httpx.get(
        "https://lod.onderwijsregistratie.nl/api/rio/v3/organisatorische-eenheden",
        params={"pageSize": 1},
        timeout=15,
    )
    r.raise_for_status()
    ok(f"RIO LOD API bereikbaar — status {r.status_code}")
except Exception as e:
    fout(f"RIO LOD API: {e}")

print("\n=== Klaar ===\n")
