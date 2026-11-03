"""UWV Open Match Data client via data.overheid.nl (CKAN).

UWV publiceert wekelijkse snapshots van vacatures en werkzoekenden
per beroep, postcodegebied en provincie — inclusief opleidingsniveau-uitsplitsing.

Data loopt t/m mei 2023 (daarna gestopt met deze publicatievorm).

Gebruik:
    from riodata import uwv

    # Catalogus (beschikbare snapshots)
    snapshots = uwv.catalog()

    # Meest recente snapshot laden
    df = uwv.load()

    # Specifieke datum laden
    df = uwv.load("2023-05-16")

    # Alleen vacatures
    df = uwv.load(rec_type="Vacature")
"""
from __future__ import annotations

import io
import zipfile

import httpx

CKAN_BASE = "https://data.overheid.nl/data/api/3/action"
DATASET_ID = "uwv-open-match-data"


def catalog(live: bool = False) -> list[dict]:
    """Geef beschikbare UWV Open Match snapshots als catalogusrecords.

    Args:
        live: Haal actuele lijst op van CKAN (default False, geeft statische info).
    """
    if live:
        snaps = _get_snapshots()
        dates = [s["created"][:10] for s in snaps]
        periode = f"{dates[-1]} t/m {dates[0]}" if dates else "onbekend"
        n = len(snaps)
    else:
        periode = "2019-11-26 t/m 2023-05-16 (wekelijkse snapshots)"
        n = 181

    return [{
        "leverancier": "UWV",
        "bron": "UWV Open Match Data",
        "beschrijving": (
            "Wekelijkse snapshots van vacatures en werkzoekenden per beroep, "
            "4-cijferig postcodegebied en provincie. Inclusief uitsplitsing naar "
            "opleidingsniveau (AANT_OPLNIV_1 t/m 6), leeftijd, geslacht en werkloosheidsduur."
        ),
        "periode": periode,
        "onderwijstype": ["Allen"],
        "doel": (
            "Koppeling arbeidsmarkt aan opleidingsniveau per regio. "
            "Geschikt voor analyse van vraag/aanbod per beroep en postcode."
        ),
        "frequentie": f"Historisch — {n} wekelijkse snapshots, gestopt mei 2023",
        "categorie": "Arbeidsmarkt",
        "sectie": "UWV / data.overheid.nl",
        "documentatie": {
            "tekst": "UWV Open Match Data op data.overheid.nl",
            "url": "https://data.overheid.nl/dataset/uwv-open-match-data",
        },
        "filters": ["beroep", "postcodegebied", "provincie", "rec_type"],
        "sub_resources": [],
        "voorbeeldvragen": [
            "Hoeveel vacatures waren er per beroep in provincie Utrecht in 2022?",
            "Wat is het opleidingsniveau van werkzoekenden in de zorg per regio?",
            "Hoe verhoudt vraag (vacatures) zich tot aanbod (werkzoekenden) per beroep?",
        ],
        "tags": ["uwv", "vacatures", "werkzoekenden", "beroep", "postcode", "opleidingsniveau", "arbeidsmarkt"],
        "combineerbaar_met": [
            "ROA AIS (arbeidsmarktprognoses per beroep)",
            "CBS (beroepsbevolking naar opleiding)",
            "RIO (onderwijslocaties per postcode)",
        ],
        "_rio_resource": None,
        "_ckan_id": DATASET_ID,
        "_roa_id": None,
        "_thema": "Arbeidsmarkt",
    }]


def resources(live: bool = True) -> list[dict]:
    """Geef beschikbare snapshots (resource-lijst van CKAN)."""
    return _get_snapshots()


def load(
    date: str = "latest",
    rec_type: str | None = None,
    **kwargs,
) -> "pd.DataFrame":
    """Download en laad een UWV Open Match snapshot als DataFrame.

    Args:
        date:     "latest" (laatste historische snapshot, niet vandaag), of datum als "YYYY-MM-DD" of "YYYYMMDD"
        rec_type: Filter op "Vacature", "ErvaringsBeroep" of "WensBeroep" (default: alle). Werkzoekenden
                  staan als ErvaringsBeroep/WensBeroep in het bestand; "Werkzoekende" bestaat niet.
                  Alleen die twee hebben opleidingsniveau (AANT_OPLNIV_*); Vacature heeft alleen AANTAL.
        **kwargs: Doorgegeven aan pd.read_csv()

    Kolommen (39 totaal):
        PEILDATUM, BEROEP_CD, REFERENTIEBEROEP, BEROEPENCLUSTER_CD, BEROEPENCLUSTER,
        POSTCODEGEBIED, PROVINCIE, GEMEENTE, REC_TYPE, AANTAL,
        GEM_LEEFTIJD, AANTAL_MAN, AANTAL_VROUW, OPLNIV_GEM,
        AANT_OPLNIV_1..6, AANT_LEEFT_*, AANT_UPW_*, AANT_WE_*

    Vereist pandas (uv add 'riodata[analyse]').
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Installeer pandas: uv add 'riodata[analyse]'")

    snapshots = _get_snapshots()
    snap = _pick_snapshot(snapshots, date)

    r = httpx.get(snap["url"], timeout=120, follow_redirects=True)
    r.raise_for_status()

    from ._lezen import ParserFout, SchemaFout, controleer_omvang, herkomst, lees_csv

    controleer_omvang(len(r.content), "UWV ZIP")
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile as e:
        raise ParserFout(f"UWV-download is geen geldige ZIP: {e}") from e
    csvs = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
    if not csvs:
        raise ParserFout(f"Geen CSV in UWV ZIP. Bestanden: {zf.namelist()}")
    controleer_omvang(csvs[0].file_size, f"Uitgepakte CSV {csvs[0].filename}")

    with zf.open(csvs[0]) as f:
        raw = f.read()

    df, enc = lees_csv(raw, defaults={"sep": ";", "decimal": ",", "low_memory": False}, **kwargs)

    peildata = sorted({_iso(w) for w in df["PEILDATUM"].dropna().astype(str)}) if "PEILDATUM" in df.columns else []
    df.attrs["snapshot"] = {
        "gevraagd": date,
        "peildatum": peildata[-1] if peildata else None,
        "peildata_in_bestand": peildata,
        "created": snap["created"],
        "status": "historisch_archief",
        "opmerking": "Gearchiveerde UWV-snapshot (publicatie liep t/m mei 2023); geen actuele vacatures.",
        **herkomst(r.content, snap["url"]),
        "encoding": enc,
        "bestand": csvs[0].filename,
    }

    if rec_type:
        if "REC_TYPE" not in df.columns:
            raise SchemaFout(f"Kolom REC_TYPE ontbreekt voor filter rec_type. Aanwezig: {list(df.columns)}")
        bekend = sorted(df["REC_TYPE"].dropna().unique())
        if rec_type.lower() not in {b.lower() for b in bekend}:
            hint = " Werkzoekenden staan als ErvaringsBeroep of WensBeroep." if "zoek" in rec_type.lower() else ""
            raise ValueError(f"Onbekend rec_type '{rec_type}'. In dit bestand: {bekend}.{hint}")
        df = df[df["REC_TYPE"].str.lower() == rec_type.lower()]

    return df


# ── intern ────────────────────────────────────────────────────────────────────

def _iso(datum: str) -> str:
    """PEILDATUM staat als DD-MM-YYYY in het bestand; ISO maakt sorteren en vergelijken veilig."""
    import datetime as _dt
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return _dt.datetime.strptime(datum.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return datum

def _get_snapshots() -> list[dict]:
    r = httpx.get(f"{CKAN_BASE}/package_show", params={"id": DATASET_ID}, timeout=15)
    r.raise_for_status()
    pkg = r.json()["result"]
    zips = [
        {
            "naam": res.get("name", ""),
            "url": res.get("url", ""),
            "created": res.get("created", ""),
        }
        for res in pkg.get("resources", [])
        if "ZIP" in res.get("format", "").upper()
    ]
    return sorted(zips, key=lambda r: r["created"], reverse=True)


def _pick_snapshot(snapshots: list[dict], date: str) -> dict:
    if not snapshots:
        raise RuntimeError("Geen UWV snapshots gevonden.")
    if date == "latest":
        return snapshots[0]
    # Normaliseer naar YYYYMMDD voor vergelijking met URL-patroon
    d_clean = date.replace("-", "")
    if len(d_clean) != 8:
        raise ValueError(f"Ongeldige datum '{date}'. Gebruik YYYY-MM-DD of YYYYMMDD.")
    # Zoek in URL (bevat datum als YYYYMMDD) of created-veld
    matches = [
        s for s in snapshots
        if d_clean in s["url"] or d_clean in s["created"].replace("-", "")[:8]
    ]
    if not matches:
        beschikbaar = [s["created"][:10] for s in snapshots[:5]]
        raise ValueError(
            f"Geen snapshot voor '{date}'. Meest recent beschikbaar: {beschikbaar}"
        )
    return matches[0]
