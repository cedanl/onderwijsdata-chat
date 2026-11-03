"""
Voeg _meest_recent toe aan multi-resource DUO catalogus-entries.

Voor elke entry waarbij _kolommen een dict is (resource-namen als keys),
wordt de resource-naam met het hoogste jaargetal als _meest_recent opgeslagen.
Als er geen jaargetal in de namen staat, wordt de laatste key gebruikt en staat
_meest_recent_bewijs op 'geen': het veld is dan geen autoritatieve selector.

Zie GitHub issue #7.
"""

import json
import re
from pathlib import Path

RESOURCES = Path("src/riodata/data/duo_resources.json")

with open(RESOURCES) as f:
    data = json.load(f)

changed = 0
for entry in data:
    kolommen = entry.get("_kolommen")
    resources = entry.get("_resources", [])

    # Only process multi-resource entries: _kolommen is a dict AND _resources > 1.
    # Single-resource entries also have _kolommen as a dict, but its keys are
    # column names (e.g. "AANTAL_LEERLINGEN"), not resource names — skip those.
    if not isinstance(kolommen, dict) or len(resources) <= 1:
        continue

    # Find resource with highest year, or last key if no years found
    best = None
    best_year = -1
    for naam in kolommen:
        years = re.findall(r'\b(20\d{2})\b', naam)
        year = max(int(y) for y in years) if years else -1
        if year > best_year:
            best_year = year
            best = naam

    if best is None:
        best = list(kolommen.keys())[-1]

    entry["_meest_recent"] = best
    # Alleen een jaartal in de naam is bewijs voor 'meest recent'; anders is het de laatste key.
    entry["_meest_recent_bewijs"] = "jaartal_in_naam" if best_year >= 0 else "geen"
    changed += 1
    print(f"  {entry['bron']}: {best}")

with open(RESOURCES, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n{changed} entries bijgewerkt")
