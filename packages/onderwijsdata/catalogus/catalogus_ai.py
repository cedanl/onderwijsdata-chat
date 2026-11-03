"""
Verrijkt cbs_datasets.json met AI-samenvattingen via de Batches API.
Goedkoopste aanpak: 50% korting, asynchroon, ~$0.05 totaal met Haiku.

Gebruik:
  uv run python catalogus_ai.py submit   # Dien batch in, sla batch_id op
  uv run python catalogus_ai.py collect  # Haal resultaten op en sla op
"""
import json
import sys
import time
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

MODEL    = "claude-haiku-4-5"
DATASETS = "data/02-prepared/cbs_datasets.json"
OUTPUT   = "data/02-prepared/cbs_datasets_ai.json"
ID_FILE  = ".batch_id"

SYSTEM = """Je bent een assistent die CBS onderwijsdatasets samenvat voor Nederlandse
beleids- en datamedewerkers bij onderwijsinstellingen. Geef altijd antwoord als JSON
zonder extra tekst of markdown."""

def make_prompt(entry: dict) -> str:
    return f"""Geef een samenvatting van deze CBS onderwijsdataset voor een beleidsmedewerker.

Dataset: {entry['bron']}
Periode: {entry.get('periode', 'onbekend')}
Beschrijving: {entry['doel']}
Thema: {entry.get('_thema', '')}

Geef terug als JSON met exact deze sleutels:
{{
  "samenvatting": "<2 zinnen: wat meet deze dataset en voor wie is het relevant>",
  "voorbeeldvragen": ["<vraag 1>", "<vraag 2>", "<vraag 3>"],
  "tags": ["<tag1>", "<tag2>", "..."]
}}

Tags zijn korte trefwoorden zoals: instroom, uitval, geslacht, regio, niveau, mbo, hbo, wo, po, vo, arbeidsmarkt, financiering."""


def submit():
    with open(DATASETS) as f:
        datasets = json.load(f)

    # Haal bestaande AI-data op om te voorkomen dat al-verrijkte entries opnieuw worden ingediend
    try:
        with open(OUTPUT) as f:
            existing_ai = {e["_cbs_id"] for e in json.load(f) if e.get("samenvatting") or e.get("tags")}
    except FileNotFoundError:
        existing_ai = set()

    to_process = [e for e in datasets if e["_cbs_id"] not in existing_ai]
    skipped    = len(datasets) - len(to_process)
    print(f"Totaal: {len(datasets)} | Al verrijkt (overgeslagen): {skipped} | In te dienen: {len(to_process)}")

    if not to_process:
        print("Niets te doen — alle entries zijn al verrijkt.")
        return

    client = anthropic.Anthropic()

    requests = [
        Request(
            custom_id=entry["_cbs_id"],
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=512,
                system=SYSTEM,
                messages=[{"role": "user", "content": make_prompt(entry)}],
            ),
        )
        for entry in to_process
    ]

    batch = client.messages.batches.create(requests=requests)
    with open(ID_FILE, "w") as f:
        f.write(batch.id)

    print(f"Batch ingediend: {batch.id}")
    print(f"Status: {batch.processing_status}")
    print(f"Gebruik 'uv run python catalogus_ai.py collect' om resultaten op te halen.")


def collect():
    try:
        with open(ID_FILE) as f:
            batch_id = f.read().strip()
    except FileNotFoundError:
        print("Geen batch gevonden. Run eerst: uv run python catalogus_ai.py submit")
        sys.exit(1)

    client = anthropic.Anthropic()

    # Wacht tot batch klaar is
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        print(f"Status: {batch.processing_status} | "
              f"gereed: {batch.request_counts.succeeded} | "
              f"bezig: {batch.request_counts.processing}")
        if batch.processing_status == "ended":
            break
        time.sleep(10)

    # Resultaten ophalen
    results = {}
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            text = next((b.text for b in result.result.message.content if b.type == "text"), "")
            try:
                results[result.custom_id] = json.loads(text)
            except json.JSONDecodeError:
                print(f"  JSON parse fout voor {result.custom_id}: {text[:100]}")

    # Merge: bestaande AI-data + nieuwe resultaten
    with open(DATASETS) as f:
        datasets = json.load(f)

    # Laad bestaande AI-output als basis (behoudt eerder verrijkte entries)
    try:
        with open(OUTPUT) as f:
            ai_by_id = {e["_cbs_id"]: e for e in json.load(f)}
    except FileNotFoundError:
        ai_by_id = {}

    # Kopieer basisvelden uit cbs_datasets.json (bijv. nieuw toegevoegde _archief/_laatste_update)
    base_by_id = {e["_cbs_id"]: e for e in datasets}
    for cbs_id, entry in ai_by_id.items():
        if cbs_id in base_by_id:
            for field in ("_archief", "_laatste_update", "periode", "frequentie",
                      "_dimensies", "_meetwaarden", "_meetwaarden_details",
                      "_perioden_formaat", "_geo_niveau"):
                entry[field] = base_by_id[cbs_id].get(field)

    # Verwerk nieuwe batch-resultaten
    new_count = 0
    for cbs_id, ai in results.items():
        base = base_by_id.get(cbs_id, {})
        entry = dict(base)
        entry["doel"]            = ai.get("samenvatting", base.get("doel", ""))
        entry["samenvatting"]    = ai.get("samenvatting", "")
        entry["voorbeeldvragen"] = ai.get("voorbeeldvragen", [])
        entry["tags"]            = ai.get("tags", [])
        ai_by_id[cbs_id] = entry
        new_count += 1

    # Sla op in volgorde van cbs_datasets.json
    output_list = []
    for entry in datasets:
        cbs_id = entry["_cbs_id"]
        output_list.append(ai_by_id.get(cbs_id, entry))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_list, f, ensure_ascii=False, indent=2)

    print(f"\nKlaar: {new_count} nieuw verrijkt | {len(output_list)} totaal → {OUTPUT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "submit":
        submit()
    elif cmd == "collect":
        collect()
    else:
        print("Gebruik: uv run python catalogus_ai.py [submit|collect]")
