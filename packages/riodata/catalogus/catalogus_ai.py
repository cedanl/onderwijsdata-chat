"""
Verrijkt resource-JSON bestanden met AI-samenvattingen via de Batches API.
Goedkoopste aanpak: 50% korting, asynchroon, ~$0.01 totaal met Haiku.

Gebruik:
  uv run python catalogus/catalogus_ai.py submit           # RIO (default)
  uv run python catalogus/catalogus_ai.py submit rio
  uv run python catalogus/catalogus_ai.py submit inspectie
  uv run python catalogus/catalogus_ai.py submit sbb
  uv run python catalogus/catalogus_ai.py collect          # Haal resultaten op
"""
import json
import sys
import time
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

MODEL   = "claude-haiku-4-5"
ID_FILE = ".batch_id"

# Per bron: input, output en de sleutel die als custom_id dient
SOURCES = {
    "rio": {
        "input":  "data/02-prepared/rio_resources.json",
        "output": "data/02-prepared/rio_resources_ai.json",
        "id_key": "_rio_resource",
    },
    "inspectie": {
        "input":  "src/riodata/data/inspectie_resources.json",
        "output": "src/riodata/data/inspectie_resources_ai.json",
        "id_key": "_inspectie_id",
    },
    "sbb": {
        "input":  "src/riodata/data/sbb_resources.json",
        "output": "src/riodata/data/sbb_resources_ai.json",
        "id_key": "_sbb_id",
    },
}

SYSTEM = """Je bent een assistent die Nederlandse onderwijsdatabronnen samenvat voor
beleids- en datamedewerkers bij onderwijsinstellingen. Geef altijd antwoord als JSON
zonder extra tekst of markdown."""


def make_prompt(entry: dict) -> str:
    leverancier = entry.get("leverancier", "")
    filters_str = ", ".join(entry.get("filters", [])) or "geen"
    sub_str = ", ".join(entry.get("sub_resources", [])) or "geen"
    return f"""Geef een samenvatting van deze onderwijsdatabron voor een beleidsmedewerker.

Leverancier: {leverancier}
Bron: {entry['bron']}
Beschrijving: {entry.get('beschrijving', '')}
Categorie: {entry.get('categorie', '')}
Filters: {filters_str}
Sub-resources: {sub_str}

Geef terug als JSON met exact deze sleutels:
{{
  "doel": "<2 zinnen: wat bevat deze bron en voor wie is het relevant>",
  "voorbeeldvragen": ["<vraag 1>", "<vraag 2>", "<vraag 3>"],
  "tags": ["<tag1>", "<tag2>", "..."]
}}

Tags zijn korte trefwoorden zoals: instellingen, opleidingen, locaties, erkenningen, mbo, hbo, po, vo, besturen, aanbieders, cohorten, licenties, kwaliteit, arbeidsmarkt, oordelen, crebo."""


def submit(source: str = "rio"):
    cfg = SOURCES.get(source)
    if not cfg:
        print(f"Onbekende bron '{source}'. Kies uit: {list(SOURCES)}")
        sys.exit(1)

    with open(cfg["input"]) as f:
        resources = json.load(f)

    id_key = cfg["id_key"]
    client = anthropic.Anthropic()

    requests = [
        Request(
            custom_id=str(entry[id_key]),
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=512,
                system=SYSTEM,
                messages=[{"role": "user", "content": make_prompt(entry)}],
            ),
        )
        for entry in resources
        if entry.get(id_key)
    ]

    batch = client.messages.batches.create(requests=requests)
    with open(ID_FILE, "w") as f:
        f.write(f"{source}:{batch.id}")

    print(f"Batch ingediend voor '{source}': {batch.id}")
    print(f"Status: {batch.processing_status}")
    print(f"Gebruik 'uv run python catalogus/catalogus_ai.py collect' om resultaten op te halen.")


def collect():
    try:
        with open(ID_FILE) as f:
            content = f.read().strip()
    except FileNotFoundError:
        print("Geen batch gevonden. Run eerst: uv run python catalogus/catalogus_ai.py submit")
        sys.exit(1)

    # Formaat: "source:batch_id"
    if ":" in content:
        source, batch_id = content.split(":", 1)
    else:
        source, batch_id = "rio", content  # terugwaartse compatibiliteit

    cfg = SOURCES.get(source)
    if not cfg:
        print(f"Onbekende bron '{source}' in {ID_FILE}.")
        sys.exit(1)

    client = anthropic.Anthropic()

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        print(f"Status: {batch.processing_status} | "
              f"gereed: {batch.request_counts.succeeded} | "
              f"bezig: {batch.request_counts.processing}")
        if batch.processing_status == "ended":
            break
        time.sleep(10)

    results = {}
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            text = next((b.text for b in result.result.message.content if b.type == "text"), "")
            try:
                results[result.custom_id] = json.loads(text)
            except json.JSONDecodeError:
                print(f"  JSON parse fout voor {result.custom_id}: {text[:100]}")

    with open(cfg["input"]) as f:
        resources = json.load(f)

    id_key = cfg["id_key"]
    for entry in resources:
        entry_id = str(entry.get(id_key, ""))
        if entry_id in results:
            ai = results[entry_id]
            entry["doel"]            = ai.get("doel", entry.get("beschrijving", ""))
            entry["voorbeeldvragen"] = ai.get("voorbeeldvragen", [])
            entry["tags"]            = ai.get("tags", [])

    with open(cfg["output"], "w", encoding="utf-8") as f:
        json.dump(resources, f, ensure_ascii=False, indent=2)

    print(f"\nKlaar: {len(results)}/{len(resources)} resources verrijkt → {cfg['output']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "submit":
        source = sys.argv[2] if len(sys.argv) > 2 else "rio"
        submit(source)
    elif cmd == "collect":
        collect()
    else:
        print(__doc__)
