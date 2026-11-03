"""
Verrijkt DUO- en RIO-catalogus met gestructureerde metadata uit de echte data.
Puur Python — geen LLM nodig. Haalt per dataset kolommen, types en
voorbeeldwaarden op.

Gebruik:
  uv run python catalogus/verrijk_catalogus.py --source duo
  uv run python catalogus/verrijk_catalogus.py --source rio
  uv run python catalogus/verrijk_catalogus.py --source all
  uv run python catalogus/verrijk_catalogus.py --source duo --limit 5
  uv run python catalogus/verrijk_catalogus.py --source duo --no-skip-existing   # eenmalige migratie
  uv run python catalogus/verrijk_catalogus.py --source duo --annotaties         # ook samenvatting/niet_geschikt_voor

Het uitvoerbestand bevat per record alleen afgeleide velden en annotaties, plus een
`_verrijking`-stempel (inputhash + schemaversie) van de bron waaruit ze zijn gemaakt.
Bronvelden komen bij het inladen altijd uit het basisbestand (zie riodata._catalog).
Een record wordt alleen overgeslagen als die stempel nog bij de bron past.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from riodata import _catalog  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "src" / "riodata" / "data"
DUO_INPUT = DATA_DIR / "duo_resources.json"
RIO_INPUT = DATA_DIR / "rio_resources_ai.json"
DUO_OUTPUT = DATA_DIR / "duo_resources_enriched.json"
RIO_OUTPUT = DATA_DIR / "rio_resources_enriched.json"

TOP_N_VALUES = 25


def parse_args():
    p = argparse.ArgumentParser(description="Verrijkt DUO/RIO catalogus met data-metadata.")
    p.add_argument("--source", choices=["duo", "rio", "all"], default="all")
    p.add_argument("--no-skip-existing", action="store_true")
    p.add_argument(
        "--annotaties",
        action="store_true",
        help="Genereer ook samenvatting en niet_geschikt_voor. Standaard uit: de chat scoort "
        "niet_geschikt_voor positief, dus vul die pas na de chat-fix (CHAT-04).",
    )
    p.add_argument("--limit", type=int, default=None)
    return p.parse_args()


def load_json(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data: list, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Auto-metadata helpers ────────────────────────────────────────────────


def build_niet_geschikt_voor(entry: dict) -> list:
    """Genereert automatische waarschuwingen over beperkingen van de dataset."""
    waarschuwingen = []

    geo = entry.get("_geo_niveau") or []
    if geo == ["landelijk"]:
        waarschuwingen.append(
            "Niet geschikt voor vragen op gemeente- of provincieniveau: "
            "alleen landelijke totalen beschikbaar."
        )

    periode = entry.get("periode", "")
    if periode:
        jaren = re.findall(r"\b(?:19|20)\d{2}\b", periode)
        if jaren and int(jaren[-1]) < 2020:
            waarschuwingen.append(
                f"Dataset is mogelijk verouderd: meest recente data is uit {jaren[-1]}."
            )

    return waarschuwingen


def build_samenvatting(entry: dict) -> str:
    """Bouwt een beschrijvende zin op basis van bestaande metadata."""
    leverancier = entry.get("leverancier", "DUO")
    bron = entry.get("bron", "onbekend")
    onderwijstype = entry.get("onderwijstype") or []
    geo = entry.get("_geo_niveau") or []
    periode = entry.get("periode", "")

    ot_str = ", ".join(onderwijstype) if onderwijstype else "onderwijs"
    geo_str = ", ".join(geo) if geo else "landelijk"

    if periode:
        return f"{leverancier} dataset over {bron} ({ot_str}) per {geo_str}, periode {periode}."
    return f"{leverancier} dataset over {bron} ({ot_str}) per {geo_str}."


# ─── DUO ──────────────────────────────────────────────────────────────────


def enrich_duo_entry(entry: dict, annotaties: bool = False) -> dict:
    """Verrijk één DUO entry met kolommen, types en top-waarden uit de echte data."""
    from riodata import duo as _duo

    dataset_id = entry.get("_ckan_id")
    if not dataset_id:
        return entry

    try:
        resources = _duo.resources(dataset_id)
    except Exception as e:
        print(f" WARN resources: {e}", end="")
        resources = []

    if not resources:
        return entry

    kolommen = {}
    kolomtypes = {}
    last_df_columns = []
    mislukt = []

    for res_idx, res in enumerate(resources[:5]):
        res_naam = res.get("naam", f"resource_{res_idx}")
        try:
            df = _duo.load(dataset_id, res_idx, nrows=200)
            last_df_columns = list(df.columns)
        except Exception as e:
            print(f" WARN {res_naam}: {e}", end="")
            mislukt.append(res_naam)
            continue

        res_kolommen = {}
        res_types = {}

        for col in df.columns:
            dtype = df[col].dtype
            non_null = df[col].dropna()

            if dtype.kind in ("i", "f", "u"):
                res_types[col] = "numeriek"
                if len(non_null) > 0:
                    res_kolommen[col] = f"numeriek (bereik: {non_null.min()}-{non_null.max()})"
                else:
                    res_kolommen[col] = "numeriek"
            else:
                uniques = non_null.unique()
                n_unique = len(uniques)
                res_types[col] = f"categorie ({n_unique} waarden)"
                top_vals = [str(v) for v in uniques[:TOP_N_VALUES]]
                res_kolommen[col] = top_vals

        if len(resources) == 1:
            kolommen = res_kolommen
            kolomtypes = res_types
        else:
            kolommen[res_naam] = res_kolommen
            kolomtypes[res_naam] = res_types

    if mislukt:
        # Een deelresultaat is geen vers schema: de aanroeper behoudt de oude verrijking als verouderd.
        raise RuntimeError(f"resources niet gelezen: {mislukt}")
    if kolommen:
        entry["_kolommen"] = kolommen
    if kolomtypes:
        entry["_kolomtypes"] = kolomtypes

    try:
        col_defs = _duo.column_definitions(last_df_columns, entry.get("_ckan_id")) if last_df_columns else {}
        if col_defs:
            entry["_kolomdefinities"] = col_defs
    except Exception as e:
        print(f" WARN defs: {e}", end="")

    if annotaties:
        entry.setdefault("niet_geschikt_voor", build_niet_geschikt_voor(entry))
        entry.setdefault("samenvatting", build_samenvatting(entry))

    return entry


# ─── RIO ──────────────────────────────────────────────────────────────────


def enrich_rio_entry(entry: dict, annotaties: bool = False) -> dict:
    """Verrijk één RIO entry met veldnamen, types en voorbeeldwaarden."""
    from riodata import fetch

    resource_name = entry.get("_rio_resource")
    if not resource_name:
        return entry

    try:
        records = fetch(resource_name, page=0, pageSize=50)
    except Exception:
        return entry

    if not records:
        return entry

    velden = {}
    veldtypes = {}

    for record in records:
        for key, value in record.items():
            if key.startswith("_"):
                continue
            if key not in velden:
                velden[key] = set()
            if key not in veldtypes:
                veldtypes[key] = None

            if value is None:
                continue

            if veldtypes[key] is None:
                if isinstance(value, bool):
                    veldtypes[key] = "boolean"
                elif isinstance(value, int):
                    veldtypes[key] = "integer"
                elif isinstance(value, float):
                    veldtypes[key] = "float"
                elif isinstance(value, list):
                    veldtypes[key] = "lijst"
                elif isinstance(value, dict):
                    veldtypes[key] = "object"
                else:
                    veldtypes[key] = "tekst"

            if isinstance(value, (str, int, float, bool)):
                velden[key].add(str(value))

    kolommen = {}
    for key, values in velden.items():
        sorted_vals = sorted(values)
        if len(sorted_vals) <= TOP_N_VALUES:
            kolommen[key] = sorted_vals
        else:
            kolommen[key] = sorted_vals[:TOP_N_VALUES]

    if kolommen:
        entry["_kolommen"] = kolommen
    if veldtypes:
        entry["_kolomtypes"] = {k: v or "onbekend" for k, v in veldtypes.items()}

    if annotaties:
        entry.setdefault("niet_geschikt_voor", build_niet_geschikt_voor(entry))
        entry.setdefault("samenvatting", build_samenvatting(entry))

    return entry


# ─── Main ─────────────────────────────────────────────────────────────────


def process_source(entries, enrich_fn, output_path, args, source_name, verrijkt):
    existing = {}
    if output_path.exists():
        for e in load_json(output_path):
            eid = _catalog.record_id(e)
            if eid:
                existing[eid] = e

    processed = 0
    skipped = 0
    failed = 0

    for idx, entry in enumerate(entries, 1):
        entry_id = _catalog.record_id(entry) or str(idx)

        status = _catalog.verrijking_status(entry, existing.get(entry_id), verrijkt)
        if not args.no_skip_existing and status == "actueel":
            skipped += 1
            continue

        if args.limit is not None and processed >= args.limit:
            break

        processed += 1
        naam = entry.get("bron", entry_id)
        print(f"[{idx}/{len(entries)}] {naam[:60]} ({status})", end="", flush=True)

        try:
            # De lezer start zonder afgeleide velden uit het basisbestand: alles wat er na afloop in zit,
            # is in deze run opgehaald (anders telt een oud schema als geslaagde aanwezigheidstest).
            invoer = {k: v for k, v in entry.items() if k not in _catalog.AFGELEID}
            enriched = enrich_fn(invoer, annotaties=args.annotaties)
            nieuw = {k: enriched[k] for k in verrijkt if k in enriched}
            if not any(k in nieuw for k in _catalog.AFGELEID):
                # Niets uit de echte data gelezen: oude verrijking behouden, niet als actueel stempelen.
                raise RuntimeError("geen schema-informatie opgehaald")
            nieuw[_catalog.STAMP] = _catalog.stamp(entry, verrijkt)
            # De afgeleide laag wordt vervangen, niet bijgemengd: oude sleutels (bijv. definities van
            # verdwenen kolommen) mogen niet onder een nieuwe stempel blijven staan.
            oud = {k: v for k, v in existing.get(entry_id, {}).items()
                   if k not in _catalog.AFGELEID and k != _catalog.STAMP}
            existing[entry_id] = {**oud, **nieuw}
            print(f" OK ({len(nieuw.get('_kolommen', {}))} kolommen)")
        except Exception as e:
            print(f" FOUT: {e}")
            failed += 1
            continue

        if processed % 5 == 0:
            _save(entries, existing, output_path, verrijkt)

    _save(entries, existing, output_path, verrijkt)
    print(f"\n{source_name}: {processed} verrijkt, {skipped} overgeslagen, {failed} mislukt")


def _save(entries, existing, output_path, verrijkt):
    """Schrijf per record bronvelden uit de basis plus de bijbehorende verrijking."""
    output_list = []
    for e in entries:
        bron = {k: v for k, v in e.items() if k not in verrijkt}
        oud = existing.get(_catalog.record_id(e)) or {}
        verrijking = {k: oud[k] for k in (*verrijkt, _catalog.STAMP) if k in oud}
        output_list.append({**bron, **verrijking})
    save_json(output_list, output_path)


def main():
    args = parse_args()

    if args.source in ("duo", "all"):
        print("=== DUO datasets ===")
        duo_data = load_json(DUO_INPUT)
        process_source(duo_data, enrich_duo_entry, DUO_OUTPUT, args, "DUO", _catalog.VERRIJKT_DUO)

    if args.source in ("rio", "all"):
        print("\n=== RIO resources ===")
        rio_data = load_json(RIO_INPUT)
        process_source(rio_data, enrich_rio_entry, RIO_OUTPUT, args, "RIO", _catalog.VERRIJKT_RIO)

    print("\nKlaar.")


if __name__ == "__main__":
    main()
