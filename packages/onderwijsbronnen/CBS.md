# onderwijsbronnen.cbs (was: onderwijsdata)

Python client voor publieke Nederlandse onderwijsdata via de [CBS OData API](https://opendata.cbs.nl/ODataCatalog/).

## Installatie

De CBS-client is het subpakket `onderwijsbronnen.cbs` van het pakket `onderwijsbronnen` (tot november 2026 het
losse pakket `onderwijsdata`; die naam bestaat sinds #914 niet meer). Het staat **niet op PyPI** en woont in
de repo van de chat
([`packages/onderwijsbronnen`](https://github.com/cedanl/onderwijsdata-chat/tree/main/packages/onderwijsbronnen)).
Installeer vanuit Git met een vaste commit van die repo (gebruik niet `main` voor reproduceerbare omgevingen):

```bash
pip install "onderwijsbronnen @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"
pip install "onderwijsbronnen[analyse] @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"  # + pandas, matplotlib
```

Met uv: `uv add "onderwijsbronnen @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"`.

De oude repo `cedanl/cbs-onderwijsdata` is gearchiveerd en blijft bestaan: een bestaande regel met de tag `v0.2.2`
werkt nog.

De installatie bevat de catalogus en `cbs_manifest.json`. Controle na installatie:

```python
import onderwijsbronnen.cbs
onderwijsbronnen.cbs.catalog_manifest()["consistent"]   # True: geleverde bestanden horen bij het manifest
```

De test `tests/test_release.py` bouwt wheel en sdist, controleert catalogus en manifest daarin
en installeert de wheel in een schone omgeving. Een PyPI-release volgt pas als die test slaagt.

### Brede catalogus en chatprofiel

De package levert de **brede** publieke CBS-catalogus (alle onderwijsthema's, inclusief po/vo en
historische tabellen). Het mbo/hbo/wo-profiel voor de chat is een selectie daarvan:
`catalog_records(sector="mbo")`. Historische tabellen zijn gemarkeerd (`archief.gearchiveerd`).

## Gebruik

```python
from onderwijsbronnen.cbs import data, dimension, properties

# Dimensiewaarden ophalen
geslacht = dimension("85423NED", "Geslacht")

# Data ophalen met filter
rows = data("85380NED", **{
    "$filter": "Onderwijssoort eq 'A041920' and trim(Regiokenmerken) eq 'GM0363'"
})

# Kolommen en meetwaarden bekijken
props = properties("85353NED")
```

### Catalogus (versieerbaar contract, offline)

```python
from onderwijsbronnen.cbs import catalog_records, get_dataset, catalog_manifest, scope_review

catalog_records(sector="mbo")      # alleen records waar mbo `supported` is
scope_review()                     # onbekende sectordekking: eerst verifiëren
get_dataset("cbs:85423NED")        # exacte ID-resolutie (ook zonder prefix)
catalog_manifest()                 # schemaversie, aantallen, inhoudshash
```

Onbekende informatie staat als `{"status": "unknown", ...}`, nooit als lege lijst.
`catalog()` blijft ongewijzigd werken.

## Structuur

```
src/onderwijsbronnen/cbs/   Python-subpakket (CBS OData client)
catalogus/            Catalogus builder + AI-verrijking
data/02-prepared/     Verrijkte CBS catalogus (JSON)
voorbeelden/cbs/          Voorbeeldanalyses + gegenereerde plots
docs/cbs/                 GitHub Pages catalogussite
```

## Catalogus opbouwen

```bash
uv run python catalogus/cbs/catalogus.py
uv run python catalogus/cbs/catalogus_ai.py submit
uv run python catalogus/cbs/catalogus_ai.py collect
```

## Links

- [Catalogussite](https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/)
- [CBS OData API](https://opendata.cbs.nl/ODataCatalog/)
