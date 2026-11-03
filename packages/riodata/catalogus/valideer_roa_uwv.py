"""Inhoudelijke validatie van ROA- en UWV-bestanden (RIO-06).

Gebruik:
    uv run --extra analyse python catalogus/valideer_roa_uwv.py

Leest elk ROA-bestand van DataverseNL (beide AIS-DOI's) en de UWV-snapshots echt in, en
schrijft per bestand een ``schema`` in ``roa_resources.json`` / ``_schema`` in
``uwv_resources.json``: kolommen, rijen, checksum, separator/decimaal, granulariteit,
uitsplitsingen, perioden en sentinelwaarden. Feiten komen uit de data; teksten over
betekenis komen uit de toelichting-PDF (V20260826) en staan als zodanig gemarkeerd.
Ongedocumenteerde codes (``-9``) worden geteld maar niet geïnterpreteerd.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "src" / "riodata" / "data"
DATAVERSE = "https://dataverse.nl/api"
VANDAAG = dt.date.today().isoformat()
TOELICHTING = "Toelichting ArbeidsmarktInformatieSysteem (AIS), versie V20260826"

# Bestandsnaam (DataverseNL) → (resourcenaam in de catalogus, soort). Bestaande namen blijven.
ROA_BESTANDEN = {
    "ais2030": {
        "AIStot2030_Arbeidsmarktinformatie_editie2025.csv": ("arbeidsmarkt", "arbeidsmarkt", "2025"),
        "AIStot2030_Arbeidsmarktinformatie_editie2025_toelichting.csv": ("toelichting", "toelichting", "2025"),
        "AIStot2030_Arbeidsmarktuitkomsten.csv": ("uitkomsten", "uitkomsten", "2025"),
        "AIStot2030_Kerncijfers_Schoolverlatersonderzoeken_2024.csv": ("schoolverlaters", "schoolverlaters", "2025"),
        "AIStot2030_Arbeidsmarktinformatie_editie2026.csv": ("arbeidsmarkt_editie2026", "arbeidsmarkt", "2026"),
        "AIStot2030_Arbeidsmarktinformatie_editie2026_toelichting.csv": ("toelichting_editie2026", "toelichting", "2026"),
        "AIStot2030_Arbeidsmarktuitkomsten_editie2026.csv": ("uitkomsten_editie2026", "uitkomsten", "2026"),
        "AIStot2030_Kerncijfers_Schoolverlatersonderzoeken_2025.csv": ("schoolverlaters_editie2026", "schoolverlaters", "2026"),
    },
    "ais2028": {
        "AIStot2028_Arbeidsmarktinformatie_editie2023_v20240612.csv": ("arbeidsmarkt_2023", "arbeidsmarkt", "2023"),
        "AIStot2028_Arbeidsmarktinformatie_editie2024_v20240612.csv": ("arbeidsmarkt_2024", "arbeidsmarkt", "2024"),
        "AIStot2028_Arbeidsmarktinformatie_toelichting_editie2023_v20240612.csv": ("toelichting_2023", "toelichting", "2023"),
        "AIStot2028_Arbeidsmarktinformatie_toelichting_editie2024_v20240612.csv": ("toelichting_2024", "toelichting", "2024"),
    },
}
DOI = {"ais2030": "doi:10.34894/DVQTOG", "ais2028": "doi:10.34894/UIQHCI"}

# Betekenis per soort bestand, uit de toelichting-PDF. Geen eigen interpretatie.
SOORT_TEKST = {
    "arbeidsmarkt": {
        "granulariteit": "regio × indeling (bedrijfssector/beroep/opleiding) × aggregatieniveau × onderwerp",
        "beperkingen": [
            {"tekst": "Lege cellen: cijfers op minder dan 80 ongewogen EBB-waarnemingen worden niet gepubliceerd.",
             "bron": TOELICHTING},
            {"tekst": "EBB-cijfers zijn het gemiddelde van twee jaren (bijv. 2024 en 2025).", "bron": TOELICHTING},
            {"tekst": "Deelnemers en gediplomeerden zijn afgerond op tientallen; blanco = onder de publicatiegrens "
                      "of onbekend.", "bron": TOELICHTING},
            {"tekst": "Niet per onderwijsinstelling.", "bron": "kolommen (geen instellingscode)"},
        ],
    },
    "uitkomsten": {
        "granulariteit": "opleiding (ROA-opleidingscode) × sociaaleconomische positie (SECM), landelijk",
        "beperkingen": [
            {"tekst": "Landelijk: geen regio- of instellingskolom.", "bron": "kolommen"},
            {"tekst": "De waarde -9 komt veel voor in amount_/aandeel_-kolommen; de betekenis staat niet in de "
                      "toelichting. Niet als getal gebruiken zonder bevestiging van ROA.", "bron": "data"},
        ],
    },
    "schoolverlaters": {
        "granulariteit": "opleiding (SIS-code, centraal-registercode) × indicator, landelijk; schooljaren als kolommen",
        "beperkingen": [
            {"tekst": "Alleen cijfers op minimaal 20 respondenten.", "bron": TOELICHTING},
            {"tekst": "Landelijk: geen regio- of instellingskolom.", "bron": "kolommen"},
        ],
    },
    "toelichting": {
        "granulariteit": "documentatie per variabele (geen data)",
        "beperkingen": [{"tekst": "Bevat HTML-fragmenten en afgebroken regels; alleen als naslag gebruiken.",
                         "bron": "data"}],
    },
}


def _dataverse_files(client: httpx.Client, doi: str) -> dict[str, dict]:
    r = client.get(f"{DATAVERSE}/datasets/:persistentId/", params={"persistentId": doi})
    r.raise_for_status()
    versie = r.json()["data"]["latestVersion"]
    return {f["label"]: {**f["dataFile"], "release": versie.get("releaseTime")} for f in versie["files"]}


def _jaren(tekst: str) -> list[int]:
    return [int(j) for j in re.findall(r"(?<!\d)(20\d\d)(?!\d)", tekst)]


def roa_schema(df, meta: dict, soort: str, editie: str) -> dict:
    kolommen = list(df.columns)
    s = {
        "bestandsnaam": meta["filename"],
        "editie": editie,
        "dataverse_sha1": (meta.get("checksum") or {}).get("value"),
        "grootte": meta.get("filesize"),
        "dataverse_release": meta.get("release"),
        "gecontroleerd_op": VANDAAG,
        "aantal_rijen": int(len(df)),
        "kolommen": kolommen,
        "separator": ";",
        "decimaal": ",",
        "soort": soort,
        **{k: v for k, v in SOORT_TEKST[soort].items()},
    }
    if soort == "arbeidsmarkt":
        regios = list(df["regionaam"].dropna().unique())
        s["uitsplitsingen"] = {
            "regio": {"aantal": len(regios), "voorbeelden": regios[:5], "landelijk": "Nederland" in regios},
            "indeling": sorted(df["indeling"].dropna().unique().tolist()),
            "aggregatieniveau": sorted(x.strip() for x in df["aggregatieniveau"].dropna().unique()),
        }
        themas = sorted(df["thema"].dropna().unique().tolist())
        s["themas"] = themas
        prog = [t for t in themas if "prognose" in t.lower()]
        s["prognosehorizon"] = max(_jaren(" ".join(prog))) if prog else None
        if "versie" in df.columns:
            s["versie_in_bestand"] = sorted(df["versie"].dropna().unique().tolist())
    elif soort == "uitkomsten":
        jaren = sorted({j for k in kolommen for j in _jaren(k)})
        s["meetjaren"] = jaren
        s["sentinels"] = {"-9": {"aantal": int((df[[k for k in kolommen if _jaren(k)]] == -9).sum().sum()),
                                 "betekenis": "niet gedocumenteerd"}}
    elif soort == "schoolverlaters":
        s["schooljaren"] = [k for k in kolommen if re.fullmatch(r"20\d\d - 20\d\d", k)]
    return s


def valideer_roa(client: httpx.Client) -> None:
    import pandas as pd
    from riodata._lezen import lees_csv

    pad = DATA / "roa_resources.json"
    records = json.loads(pad.read_text(encoding="utf-8"))
    for rec in records:
        ds = rec["_roa_id"]
        bestanden = _dataverse_files(client, DOI[ds])
        nieuw = []
        for bestandsnaam, (naam, soort, editie) in ROA_BESTANDEN[ds].items():
            meta = bestanden[bestandsnaam]
            r = client.get(f"{DATAVERSE}/access/datafile/{meta['id']}")
            r.raise_for_status()
            sha1 = hashlib.sha1(r.content).hexdigest()
            if sha1 != (meta.get("checksum") or {}).get("value"):
                raise SystemExit(f"Checksum wijkt af voor {bestandsnaam}")
            opties = {"decimal": ",", "low_memory": False}
            df, enc = lees_csv(r.content, defaults={"sep": ";"}, **opties)
            schema = roa_schema(df, meta, soort, editie)
            schema["encoding"] = enc
            nieuw.append({"naam": naam, "file_id": meta["id"],
                          "url": f"{DATAVERSE}/access/datafile/{meta['id']}", "schema": schema})
            print(f"  {ds}/{naam}: {len(df)} rijen, {len(df.columns)} kolommen", file=sys.stderr)
        # meest recente editie per soort markeren
        per_soort: dict[str, str] = {}
        for x in nieuw:
            s = x["schema"]
            per_soort[s["soort"]] = max(per_soort.get(s["soort"], ""), s["editie"])
        for x in nieuw:
            x["schema"]["meest_recente_editie"] = x["schema"]["editie"] == per_soort[x["schema"]["soort"]]
        rec["_resources"] = nieuw
    pad.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    del pd


def uwv_schema(df) -> dict:
    per_type = {}
    for rt, sub in df.groupby("REC_TYPE"):
        gevuld = [c for c in df.columns if sub[c].notna().any()]
        per_type[rt] = {
            "aantal_rijen": int(len(sub)),
            "kolommen_met_waarden": gevuld,
            "kolommen_altijd_leeg": [c for c in df.columns if c not in gevuld],
            "opleidingsniveau": any(c.startswith("AANT_OPLNIV_") for c in gevuld),
            "postcode_gevuld_aandeel": round(float(sub["POSTCODEGEBIED"].notna().mean()), 3),
        }
    return {"kolommen": list(df.columns), "rec_types": per_type}


def valideer_uwv() -> None:
    from riodata import uwv

    pad = DATA / "uwv_resources.json"
    records = json.loads(pad.read_text(encoding="utf-8"))
    df = uwv.load("latest")
    schema = uwv_schema(df)
    gecontroleerd = [df.attrs["snapshot"]["peildatum"]]
    for datum in ("20191126", "2021-06-01", "20220104"):
        oud = uwv.load(datum)
        if list(oud.columns) != schema["kolommen"] or set(oud["REC_TYPE"].unique()) != set(schema["rec_types"]):
            raise SystemExit(f"UWV-schema wijkt af in snapshot {datum}")
        gecontroleerd.append(oud.attrs["snapshot"]["peildatum"])
    schema.update({
        "laatste_peildatum": df.attrs["snapshot"]["peildatum"],
        "status": "historisch_archief",
        "gecontroleerd_op": VANDAAG,
        "schema_gelijk_in_snapshots": gecontroleerd,
        "bron_url": df.attrs["snapshot"]["bron_url"],
        "sha256": df.attrs["snapshot"]["sha256"],
    })
    records[0]["_schema"] = schema
    pad.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  uwv: {schema['laatste_peildatum']}, rec_types {sorted(schema['rec_types'])}", file=sys.stderr)


def main() -> int:
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        valideer_roa(client)
    valideer_uwv()
    return 0


if __name__ == "__main__":
    sys.exit(main())
