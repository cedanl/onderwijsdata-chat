# CLAUDE.md — RIO DUO Open Onderwijsdata

Dit is een Python package voor twee bronnen van Nederlandse onderwijsdata:

1. **RIO LOD API v3** — dagelijks bijgewerkt register van instellingen en opleidingen (typefilters heten `type`; cohorten, contactadressen en onderwijslocatiegebruiken alleen als sub-resource)
2. **DUO Open Data** — 56 datasets via onderwijsdata.duo.nl (CKAN API)

Hieronder staat hoe je als AI-assistent een nieuwe analyse maakt van A tot Z.

---

## Repo-structuur

```
src/riodata/
  client.py               RIO LOD API client (fetch, get, related)
  duo.py                  DUO CKAN client (catalog, resources, load, search)
  data/
    rio_resources_ai.json Catalogus: 14 RIO-resources met AI-samenvatting, tags, voorbeeldvragen
    rio_resources.json    Catalogus: zelfde resources, zonder AI-verrijking
    duo_resources.json    Catalogus: 56 DUO-datasets (gegenereerd uit CKAN)
data/02-prepared/         bron-JSONs voor de RIO-catalogus
RIO_LOD_API_v3.yml        OpenAPI spec van de RIO API (v3)
voorbeelden/
  manifest.json           Bron voor alle voorbeelden op de site
  output/                 Plots (.png) en interpretaties (INTERPRETATIE.md)
  *.py                    Analysescripts
docs/                     GitHub Pages site (gebouwd door workflow)
```

---

## Workflow: nieuwe analyse toevoegen

### Stap 1 — Verken de catalogus

```python
import riodata

# RIO: 14 live API-resources
rio = riodata.catalog(source="rio")

# DUO: 56 downloadbare datasets (offline, lokale JSON)
duo = riodata.catalog(source="duo")

# Alles gecombineerd
alle = riodata.catalog(source="all")
```

**RIO-records** hebben: `_rio_resource`, `bron`, `periode`, `doel`, `tags`, `voorbeeldvragen`,
`categorie`, `sub_resources`, `filters`.

**DUO-records** hebben dezelfde velden plus: `_ckan_id`, `_resources` (downloadlinks),
`_kolommen` (CSV-kolomnamen).

Handige filters voor RIO:
- Op categorie: `Instellingen`, `Opleidingsstructuur`, `Aanbod`, `Locaties`, `Licenties en erkenningen`
- Op `_rio_resource`: bijv. `"organisatorische-eenheden"`, `"aangeboden-opleidingen"`

Handige filters voor DUO:
- Op categorie: `PO`, `VO`, `MBO`, `HO`, `SO`, `Arbeidsmarkt`
- Via `riodata.duo.search("trefwoord")` voor full-text zoeken in CKAN

### Stap 2 — Verken de resource

**RIO:**
```python
from riodata import fetch, get, related

sample = fetch("onderwijslocaties", page=0, pageSize=3)
instelling = get("organisatorische-eenheden", "some-uuid")
cohorten = related("aangeboden-opleidingen", uuid, "aangeboden-opleiding-cohorten")
```

**DUO:**
```python
from riodata import duo

# Bekijk beschikbare bestanden per dataset
duo.resources("studentprognoses-mbo-per-instelling")

# Laad als DataFrame (vereist pandas)
df = duo.load("studentprognoses-mbo-per-instelling", 0)          # index
df = duo.load("p01hoinges", "b88721ef-9787-4299-afc7-5d74380d29ba")  # resource-UUID (stabiel)
duo.resource_schemas("p01hoinges")                                # officiële kolomtypes, offline
```

DUO-datasets bestaan uit meerdere CSV-bestanden per dimensie-combinatie
(bijv. `_instelling`, `_gemeente`, `_sectorkamer`). Bekijk `duo.resources()` eerst.

### Stap 3 — Schrijf het analysescript

Maak een nieuw script in `voorbeelden/`. Conventies:

- **Bestandsnaam**: beschrijvend, lowercase met underscores, bijv. `duo_mbo_prognose_regio.py`
- **Prefix**: `rio_` voor RIO-analyses, `duo_` voor DUO-analyses
- **Docstring bovenaan**: vermeld gebruikte resource(s) en de centrale vraag
- **Output**: sla plot(s) op in `voorbeelden/output/` als PNG
- **Submap**: bij meerdere plots per analyse: `voorbeelden/output/{analyse_naam}/`
- Gebruik `matplotlib` voor visualisaties; geen interactieve libraries

Minimale structuur voor een **RIO-analyse**:

```python
"""
Titel van de analyse
Resource(s): RIO LOD API v3 — onderwijslocaties
Centrale vraag: ...
"""
import pandas as pd
import matplotlib.pyplot as plt
from riodata import fetch

OUTPUT = "voorbeelden/output/mijn_analyse.png"

items = fetch("onderwijslocaties")
df = pd.DataFrame(items)

fig, ax = plt.subplots(figsize=(10, 6))
# ...
fig.tight_layout()
fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
```

Minimale structuur voor een **DUO-analyse**:

```python
"""
Titel van de analyse
Resource(s): DUO CKAN — studentprognoses-mbo-per-instelling
Centrale vraag: ...
"""
import pandas as pd
import matplotlib.pyplot as plt
from riodata import duo

OUTPUT = "voorbeelden/output/mijn_analyse.png"

df = duo.load("studentprognoses-mbo-per-instelling", "mbo-studentenprognose_instelling")

fig, ax = plt.subplots(figsize=(10, 6))
# ...
fig.tight_layout()
fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
```

Scripts draaien met: `uv run python voorbeelden/mijn_analyse.py`

### Stap 4 — Schrijf de interpretatie

Bij een enkele plot: `voorbeelden/output/{naam}_INTERPRETATIE.md`.
Bij een submap: `voorbeelden/output/{naam}/INTERPRETATIE.md`.

```markdown
# Titel van de analyse

**Resource(s):** DUO CKAN — [dataset naam]
**Periode:** ...
**Analyseniveau:** ...

---

## Kerncijfers

| | |
|---|---|
| Totaal ... | **...** |

## Belangrijkste bevindingen

### 1. Bevinding
Beschrijving met concrete cijfers.

---

## Strategische implicaties

1. ...

---

*Bron: DUO Open Data — onderwijsdata.duo.nl*
*Analyse: [maand jaar]*
```

### Stap 5 — Voeg toe aan manifest

```json
{
  "id": "mijn_analyse",
  "titel": "Korte beschrijvende titel",
  "vraag": "De centrale vraag die deze analyse beantwoordt?",
  "datasets": ["studentprognoses-mbo-per-instelling"],
  "plot": "mijn_analyse.png",
  "interpretatie": "mijn_analyse_INTERPRETATIE.md",
  "status": "experimenteel"
}
```

Voor DUO: `datasets` bevat de `_ckan_id` waarden (bijv. `"p01hoinges"`).
Voor RIO: `datasets` bevat de `_rio_resource` waarden (bijv. `"onderwijslocaties"`).

Voor een analyse met submap:
- `"plot": "mijn_analyse/01_plot.png"`
- `"interpretatie": "mijn_analyse/INTERPRETATIE.md"`

### Stap 6 — Push

```bash
git add voorbeelden/
git commit -m "feat: [beschrijving analyse]"
git push
```

---

## Client-referentie

### RIO LOD API

```python
from riodata import fetch, get, related

fetch(resource, **params)
# Pagineert automatisch via HATEOAS. page=N voor één pagina, pageSize=N (max 100).

get(resource, id, **params)
# Één resource via UUID.

related(resource, id, sub, **params)
# Gelinkte sub-resources van één record.
```

### DUO CKAN

```python
from riodata import duo

duo.catalog()
# 56 DUO-datasets als catalogusrecords (offline, lokale JSON).

duo.catalog()  # gebruik riodata.catalog(source="duo", live=True) voor live CKAN

duo.search("trefwoord")
# Zoek datasets via CKAN full-text search.

duo.resources("dataset-id")
# Lijst van downloadbare bestanden voor een dataset.
# Returns: [{"naam": ..., "url": ..., "format": ..., "id": ...}]

duo.load("dataset-id", resource=0, skiprows=None, **kwargs)
# Download en laad als DataFrame. resource: int (index), resource-UUID, exacte naam of
# unieke naam-substring. Ambigue substring → AmbigueResource met .opties.

duo.resource_schemas("dataset-id") / duo.resource_schema("dataset-id", resource)
# Offline schema per resource: Datastore-types, definities, volledig domein of steekproef.

from riodata import contract
contract.catalog_records(sector="mbo"); contract.get_dataset("duo:p01hoinges")
# Datasetcontract (RIO-03): stabiele IDs, scopeprofiel, sectorselectie, capabilities.
# Vereist pandas + openpyxl voor .xlsx; pandas is voldoende voor .csv.
```

### Catalogus

```python
import riodata

riodata.catalog(source="rio")              # 14 RIO-resources
riodata.catalog(source="duo")              # 56 DUO-datasets (lokale snapshot)
riodata.catalog(source="all")              # 77 gecombineerd
riodata.catalog(source="duo", live=True)   # live van CKAN
riodata.catalog(source="rio", ai=False)    # zonder AI-verrijking
```

---

## Efficiënt queries schrijven (RIO)

RIO is een HATEOAS-API. De valkuil is duizenden records ophalen om een UUID te vinden.

### Regel 1 — Gebruik filters, niet traversal

```python
# FOUT: 20.700 records ophalen om UUID te vinden
alle = fetch("organisatorische-eenheden")
uuid = next(i["id"] for i in alle if "ROC" in i.get("naam", ""))

# GOED: direct filteren via BRIN-code
aanbod = fetch("aangeboden-opleidingen", organisatorischeEenheidcode="25LH")
```

### Regel 2 — Beschikbare filters per resource

| Resource | Nuttige filters |
|---|---|
| `organisatorische-eenheden` | `organisatorischeEenheidType` (`ONDERWIJSINSTELLING` / `ONDERWIJSBESTUUR` / `ONDERWIJSAANBIEDER`) |
| `aangeboden-opleidingen` | `organisatorischeEenheidcode` (BRIN), `onderwijslocatieId`, `type`, `opleidingseenheidcode` |
| `onderwijslocatiegebruiken` | `onderwijslocatieId`, `onderwijsbestuurId` |
| `onderwijslocaties` | `aangebodenOpleidingId` |
| `erkenningen` | `volledigeNaam`, `plaatsnaam`, `erkenningtype` |
| `opleidingserkenningen` | `erkendeopleidingscode`, `opleidingserkenningtype` |
| Alle resources | `datumGeldigOp` (bijv. `2024-01-01`) voor historische snapshots |

### Regel 3 — Filter op type als UUID toch nodig is

```python
# Alleen instellingen (~2.000 i.p.v. 20.700)
instellingen = fetch("organisatorische-eenheden",
                     organisatorischeEenheidType="ONDERWIJSINSTELLING")
uuid = next(i["id"] for i in instellingen if "ROC van Amsterdam" in i.get("naam", ""))
```

### Regel 4 — `related()` alleen voor één specifiek record

```python
# GOED
cohorten = related("aangeboden-opleidingen", known_uuid, "aangeboden-opleiding-cohorten")

# FOUT: related() in een loop
for item in alle_opleidingen:
    cohorten = related("aangeboden-opleidingen", item["id"], "aangeboden-opleiding-cohorten")
```

### Regel 5 — Steekproef vóór volledige fetch

```python
sample = fetch("aangeboden-opleidingen", page=0, pageSize=5)
print(sample[0].keys())
```

---

## Wat niet hoeft

- Geen `docs/` handmatig aanpassen — de workflow regelt dat
- Geen `docs/data.json` of `docs/voorbeelden.json` aanraken
- Geen nieuwe dependencies toevoegen zonder `uv add`
- `duo_resources.json` niet handmatig bewerken — regenereer via het generatiescript
