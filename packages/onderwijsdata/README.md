# onderwijsdata

Python client voor publieke Nederlandse onderwijsdata via de [CBS OData API](https://opendata.cbs.nl/ODataCatalog/).

## Installatie

`onderwijsdata` staat **nog niet op PyPI**. Installeer vanuit Git met een vaste ref
(een release-tag of commit-hash; gebruik niet `main` voor reproduceerbare omgevingen):

```bash
pip install "onderwijsdata @ git+https://github.com/cedanl/cbs-onderwijsdata@v0.2.2"
pip install "onderwijsdata[analyse] @ git+https://github.com/cedanl/cbs-onderwijsdata@v0.2.2"  # + pandas, matplotlib
```

Met uv: `uv add "onderwijsdata @ git+https://github.com/cedanl/cbs-onderwijsdata@v0.2.2"`.

De installatie bevat de catalogus en `cbs_manifest.json`. Controle na installatie:

```python
import onderwijsdata
onderwijsdata.catalog_manifest()["consistent"]   # True: geleverde bestanden horen bij het manifest
```

De test `tests/test_release.py` bouwt wheel en sdist, controleert catalogus en manifest daarin
en installeert de wheel in een schone omgeving. Een PyPI-release volgt pas als die test slaagt.

### Brede catalogus en chatprofiel

De package levert de **brede** publieke CBS-catalogus (alle onderwijsthema's, inclusief po/vo en
historische tabellen). Het mbo/hbo/wo-profiel voor de chat is een selectie daarvan:
`catalog_records(sector="mbo")`. Historische tabellen zijn gemarkeerd (`archief.gearchiveerd`).

## Gebruik

```python
from onderwijsdata import data, dimension, properties

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
from onderwijsdata import catalog_records, get_dataset, catalog_manifest, scope_review

catalog_records(sector="mbo")      # alleen records waar mbo `supported` is
scope_review()                     # onbekende sectordekking: eerst verifiëren
get_dataset("cbs:85423NED")        # exacte ID-resolutie (ook zonder prefix)
catalog_manifest()                 # schemaversie, aantallen, inhoudshash
```

Onbekende informatie staat als `{"status": "unknown", ...}`, nooit als lege lijst.
`catalog()` blijft ongewijzigd werken.

## Structuur

```
src/onderwijsdata/    Python package (CBS OData client)
catalogus/            Catalogus builder + AI-verrijking
data/02-prepared/     Verrijkte CBS catalogus (JSON)
voorbeelden/          Voorbeeldanalyses + gegenereerde plots
docs/                 GitHub Pages catalogussite
```

## Catalogus opbouwen

```bash
uv run python catalogus/catalogus.py
uv run python catalogus/catalogus_ai.py submit
uv run python catalogus/catalogus_ai.py collect
```

## Links

- [Catalogussite](https://cedanl.github.io/cbs-onderwijsdata)
- [CBS OData API](https://opendata.cbs.nl/ODataCatalog/)
