# CLAUDE-cbs.md — CBS in onderwijsbronnen (`onderwijsbronnen.cbs`, was `onderwijsdata`)

Dit is een Python package voor publieke Nederlandse onderwijsdata via de CBS OData API,
plus een GitHub Pages catalogussite. Hieronder staat hoe je als AI-assistent
een nieuwe analyse maakt van A tot Z.

---

## Repo-structuur

```
src/onderwijsbronnen/cbs/client.py  CBS OData client (data, dimension, properties)
data/02-prepared/
  cbs_datasets_ai.json          Catalogus: 268 datasets met AI-samenvatting, tags, voorbeeldvragen
  cbs_datasets.json             Catalogus: zelfde datasets, zonder AI-verrijking
voorbeelden/cbs/
  manifest.json                 Bron voor alle voorbeelden op de site
  output/                       Plots (.png) en interpretaties (INTERPRETATIE.md)
  *.py                          Analysescripts
docs/cbs/                       catalogussite, /catalogus/cbs/ op de Pages-site van de chat (CI-job catalogus:site)
```

---

## Workflow: nieuwe analyse toevoegen

### Stap 1 — Verken de catalogus

Lees `data/02-prepared/cbs_datasets_ai.json` om te zien welke datasets beschikbaar zijn.
Elk object heeft: `_cbs_id`, `bron`, `periode`, `doel`, `tags`, `voorbeeldvragen`, `_thema`.

Handige filters om relevante datasets te vinden:
- Op thema: `mbo`, `ho`, `vo`, `po`, `arbeidsmarkt`, `herkomst`, etc. (zie `tags`)
- Op `_thema`: bijv. `"Mbo studenten"`, `"Ho ingeschrevenen"`, `"Van mbo naar arbeidsmarkt"`
- Op `_cbs_id`: direct opzoeken als het ID bekend is

### Stap 2 — Verken de dataset

Gebruik de client om dimensies en meetwaarden te bekijken vóórdat je data ophaalt:

```python
from onderwijsbronnen.cbs import client

# Beschikbare dimensies en meetwaarden
props = client.properties("85353NED")

# Waarden van een specifieke dimensie
niveaus = client.dimension("85353NED", "Niveau")
# → {"1": "Niveau 1", "2": "Niveau 2", ...}

# Kleine steekproef van de data
sample = client.data("85353NED", **{"$top": 10})
```

### Stap 3 — Schrijf het analysescript

Maak een nieuw script in `voorbeelden/cbs/`. Conventies:

- **Bestandsnaam**: beschrijvend, lowercase met underscores, bijv. `mbo_uitval_regio.py`
- **Docstring bovenaan**: vermeld gebruikte dataset-IDs en de centrale vraag
- **Output**: sla plot(s) op in `voorbeelden/cbs/output/` als PNG
- **Submap**: bij meerdere plots per analyse, gebruik een submap: `voorbeelden/cbs/output/{analyse_naam}/`
- Gebruik `matplotlib` voor visualisaties; geen interactieve libraries

Minimale scriptstructuur:

```python
"""
Titel van de analyse
Dataset(s): CBS XXXXXNED — Omschrijving
Centrale vraag: ...
"""
import pandas as pd
import matplotlib.pyplot as plt
from onderwijsbronnen.cbs import client

OUTPUT = "voorbeelden/cbs/output/mijn_analyse.png"

# 1. Dimensies ophalen
dim = client.dimension("XXXXXNED", "DimensieNaam")

# 2. Data ophalen
rows = client.data("XXXXXNED", **{"$filter": "..."})
df = pd.DataFrame(rows)

# 3. Bewerken en plotten
fig, ax = plt.subplots(figsize=(10, 6))
# ...
fig.suptitle("Titel", fontsize=14, fontweight="bold")
fig.tight_layout()
fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
print(f"Plot opgeslagen: {OUTPUT}")
```

Scripts draaien met: `uv run python voorbeelden/cbs/mijn_analyse.py`

### Stap 4 — Schrijf de interpretatie

Maak een `INTERPRETATIE.md` naast de plot. Bij een enkele plot: `voorbeelden/cbs/output/{naam}_INTERPRETATIE.md`.
Bij een submap: `voorbeelden/cbs/output/{naam}/INTERPRETATIE.md`.

Structuur van de interpretatie:

```markdown
# Titel van de analyse

**Dataset(s):** CBS XXXXXNED · [naam dataset]
**Periode:** ...
**Analyseniveau:** ...

---

## Belangrijkste bevindingen

### 1. Bevinding
Beschrijving met concrete cijfers uit de plot.

### 2. Bevinding
...

---

## Strategische implicaties

1. ...
2. ...

---

*Bron: CBS OpenData — XXXXXNED*
*Analyse: [maand jaar]*
```

### Stap 5 — Voeg toe aan manifest

Voeg een entry toe aan `voorbeelden/cbs/manifest.json`:

```json
{
  "id": "mijn_analyse",
  "titel": "Korte beschrijvende titel",
  "vraag": "De centrale vraag die deze analyse beantwoordt?",
  "datasets": ["XXXXXNED"],
  "plot": "mijn_analyse.png",
  "interpretatie": "mijn_analyse_INTERPRETATIE.md",
  "status": "experimenteel"
}
```

Voor een analyse met submap:
- `"plot": "mijn_analyse/mijn_analyse.png"`
- `"interpretatie": "mijn_analyse/INTERPRETATIE.md"` → wordt door `scripts/catalogussite.py` (chatrepo) hernoemd naar `mijn_analyse_INTERPRETATIE.md`

Velden:
| Veld | Beschrijving |
|---|---|
| `id` | Uniek, lowercase underscore, zelfde als scriptnaam |
| `titel` | Wat de analyse laat zien (max ~60 tekens) |
| `vraag` | De concrete vraag die beantwoord wordt |
| `datasets` | Lijst van `_cbs_id`'s die gebruikt worden |
| `plot` | Pad relatief t.o.v. `voorbeelden/cbs/output/` |
| `interpretatie` | Idem, of `null` als er geen is |
| `status` | Altijd `"experimenteel"` |

### Stap 6 — Push

```bash
git add voorbeelden/cbs/
git commit -m "feat: [beschrijving analyse]"
git push
```

De dagelijkse CI-job `catalogus:site` in de chatrepo pikt de wijzigingen in `voorbeelden/cbs/manifest.json` en `voorbeelden/cbs/output/` op en zet ze in een MR naar `docs/cbs/voorbeelden/` (`scripts/catalogussite.py`). De dataset-kaart op de catalogussite krijgt automatisch een "▶ Voorbeeld" knopje voor elke `_cbs_id` in het manifest.

---

## Client-referentie

```python
from onderwijsbronnen.cbs import client

client.data(dataset_id, **params)
# Haalt TypedDataSet op. Ondersteunt OData-filters:
# $filter="trim(Geslacht) eq 'T001038' and Perioden eq '2024JJ00'"
# $top=N voor gelimiteerde resultaten

client.dimension(dataset_id, dim_name)
# → dict van Key → Title voor een dimensie
# Gebruik dit om filterwaarden te ontdekken

client.properties(dataset_id)
# → lijst van alle kolommen (dimensies + meetwaarden) met metadata
```

OData-filtертips:
- Strings vereisen `trim()`: `"trim(Geslacht) eq 'T001038'"`
- Perioden formaat: jaarlijks = `'2024JJ00'`, schooljaar = `'2024KW00'` (check via `client.dimension`)
- Regiokenmerken: gemeente = `'GM0363'`, provincie = `'PV27'`

---

## Wat niet hoeft

- Geen `docs/cbs/` handmatig aanpassen — de CI-job `catalogus:site` van de chatrepo regelt dat (MR met auto-merge)
- Geen `docs/cbs/data.json` of `docs/cbs/voorbeelden.json` aanraken
- Geen nieuwe dependencies toevoegen zonder `uv add`
