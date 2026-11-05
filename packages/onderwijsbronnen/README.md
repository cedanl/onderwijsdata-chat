# onderwijsbronnen

Python client voor Nederlandse onderwijs- en arbeidsmarktdata uit acht bronnen, elk in een eigen subpakket:

- **CBS** — StatLine-tabellen over onderwijs via de OData API (`onderwijsbronnen.cbs`, zie [CBS.md](CBS.md))

- **RIO LOD API v3** — dagelijks bijgewerkt register van instellingen en opleidingen (14 resources, waarvan 3 alleen als sub-resource) (`onderwijsbronnen.rio`)
- **DUO Open Data** — 57 datasets: 56 via [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) (CKAN API) en de financiële verantwoording uit XBRL per bestuur (`onderwijsbronnen.duo`, `duo.financien`)
- **ROA** — arbeidsmarktprognoses (2 datasets) (`onderwijsbronnen.roa`)
- **UWV** — Open Match Data (1 dataset) (`onderwijsbronnen.uwv`)
- **Inspectie van het Onderwijs** — open data (2 datasets) (`onderwijsbronnen.inspectie`)
- **SBB** — CREBO-lijst en kwalificatiedossiers (2 datasets) (`onderwijsbronnen.sbb`, met `sbb.crebo` en `sbb.dossiers`)
- **UNL** — WOPI-personeelsbestand van de 14 universiteiten (`onderwijsbronnen.unl`, zie [UNL](#unl-wopi-personeel)); niet in `catalog(source="all")`

Tot november 2026 waren dit twee pakketten: `onderwijsdata` (CBS) en `riodata` (de rest). Sinds 0.9.0 (#914) bestaan
die namen niet meer in dit pakket. Overstappen: `from riodata import duo` wordt `from onderwijsbronnen import duo`
(net zo `roa`, `uwv`, `inspectie`, `sbb`), `from riodata import fetch` wordt `from onderwijsbronnen.rio import fetch`,
en `from onderwijsdata import data` wordt `from onderwijsbronnen.cbs import data`. Code met de oude namen draait
tegen haar eigen installatie: een installatieregel met een oudere commit en `#subdirectory=packages/riodata` of
`packages/onderwijsdata` blijft werken, want die commit heeft de oude mappen nog.

Elke bron heeft dezelfde interface (`BRON`, `catalogusrecords()`, `laad`, `metadata(record)`; zie
`src/onderwijsbronnen/_kern/broncontract.py`), en een bron importeert nooit een andere bron, alleen `_kern`.

## Installatie

Niet op PyPI. Het pakket woont in de repo van de chat
([`packages/onderwijsbronnen`](https://github.com/cedanl/onderwijsdata-chat/tree/main/packages/onderwijsbronnen)).
Installeer vanaf GitHub op een vaste commit van die repo (gebruik niet `main` voor reproduceerbare omgevingen):

```bash
pip install "onderwijsbronnen @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"             # alleen clients (httpx)
pip install "onderwijsbronnen[analyse] @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"    # + pandas, matplotlib, openpyxl
pip install "onderwijsbronnen[duo] @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"        # + openpyxl (DUO Excel)
pip install "onderwijsbronnen[sbb] @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"        # + openpyxl (sbb.crebo)
pip install "onderwijsbronnen[catalogus] @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"  # + anthropic, pyyaml
```

Met uv: `uv add "onderwijsbronnen[analyse] @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/onderwijsbronnen"`.

De oude repo's `cedanl/rio-onderwijsdata` en `cedanl/cbs-onderwijsdata` zijn gearchiveerd en blijven bestaan: een
bestaande regel met een tag of commit van die repo's werkt nog.
Controle na installatie: `python -c "import onderwijsbronnen as o; print(o.__version__, o.contract.catalog_manifest()['inhoudshash'], o.cbs.catalog_manifest()['consistent'])"`.

## RIO LOD API

```python
from onderwijsbronnen.rio import fetch, get, related

# Alle onderwijslocaties ophalen (pagineert automatisch)
locaties = fetch("onderwijslocaties")

# Typefilters heten in v3 overal `type` (v2: erkenningtype, opleidingseenheidtype, ...)
besturen = fetch("erkenningen", type="BEVOEGD_GEZAG", volledigeNaam="ROC Mondriaan")

# Aangeboden opleidingen per instelling via BRIN-code
aanbod = fetch("aangeboden-opleidingen", organisatorischeEenheidcode="25LH")

# Één record ophalen via UUID
instelling = get("organisatorische-eenheden", "some-uuid")

# Sub-resources van een record
cohorten = related("aangeboden-opleidingen", uuid, "aangeboden-opleiding-cohorten")
```

### Fusies en overdrachten

RIO legt elke overgang vast als instellingsrelatie `OVERGANG_VOLLEDIG` of `OVERGANG_GEDEELTELIJK`. `opvolgers` en
`voorgangers` volgen die, ook door een keten (A → B → C) en veilig bij een cyclus, en geven altijd `datumGeldigOp` mee.
Per stap: `code`, `naam`, `overgang` (`"volledig"`/`"gedeeltelijk"`), `datum` en `via` (de erkenning aan de andere kant). Een bestuursnummer
werkt net zo: besturen fuseren langs dezelfde relaties (`opvolgers("40864")` → Stichting Talland College, 40877).

```python
from onderwijsbronnen.rio import opvolgers, voorgangers

opvolgers("25LG", "2026-11-05")
# [Stap(code='08PG', naam='Firda', overgang='volledig', datum='2023-08-01', via='25LG')]
voorgangers("08PG", sinds="2021-10-01")
# [Stap(code='25LG', naam='Regionaal Opleidingen Centrum Friesland College', overgang='volledig', datum='2023-08-01', via='08PG')]
```

### Aanbieders van een instelling

Het aanbod per onderwijslocatie (RIO, en DUO's `mbo_opleidingsaanbod`) noemt de onderwijsaanbieder, niet het BRIN.
`onderwijsaanbieders` geeft de aanbieders van een erkenning op een peildatum (standaard vandaag), via
`/erkenningen/{brin}/organisatorische-eenheden`:

```python
from onderwijsbronnen.rio import onderwijsaanbieders

onderwijsaanbieders("31JC", "2026-11-05")
# ['100A932', '100A933', '110A638']  (Zone.college mbo, Zone.college vmbo, Zone.college)
```

## DUO Open Data

```python
from onderwijsbronnen import duo

# Catalogus bekijken (56 datasets, offline)
datasets = duo.catalog()

# Zoeken op trefwoord
hits = duo.search("prognose mbo")

# Beschikbare bestanden per dataset
duo.resources("studentprognoses-mbo-per-instelling")

# Data laden als DataFrame (vereist pandas)
df = duo.load("studentprognoses-mbo-per-instelling", "mbo-studentenprognose_instelling")
df = duo.load("p01hoinges", 1)           # WO ingeschrevenen per geslacht
df = duo.load("p01hoinges", "b88721ef-9787-4299-afc7-5d74380d29ba")  # op CKAN resource-UUID (stabiel)
# Een naam-substring die op meer resources past geeft AmbigueResource met de opties.

# Herkomst van wat er geladen is: dataset, resource en url, plus de bestandsversie
df.attrs["bron"]["last_modified"]  # '2026-04-08T12:51:36.650779': wanneer DUO het bestand verving (UTC)
df.attrs["bron"]["hash"]           # md5 die DUO opgeeft; None bij een datastore-dump
df.attrs["bron"]["md5"]            # md5 van de geladen bytes: gelijk aan hash als het DUO's bestand is
df.attrs["bron"]["etag"]           # ETag van de download

# Officiële kolomtypes per resource (offline; '0106' blijft tekst)
duo.resource_schemas("p01hoinges")
```

### Financiën per bestuur (verantwoording uit XBRL)

DUO's financiële verantwoording staat niet in CKAN maar op een eigen pagina, met de jaren in de bestandsnaam.
`duo.financien` leest de nieuwste editie (variant `standaard`, alleen mbo, hbo en wo) en rekent het gewogen
sectorcijfer van de Inspectie en de toets aan haar signaleringswaarden (vereist `onderwijsbronnen[duo]`, #935):

```python
from onderwijsbronnen import Bestuurssleutel
from onderwijsbronnen.duo import financien

f = financien.laad()
f.editie.jaren                         # '2021-2025'
financien.overzicht(f, "40597")        # per verslagjaar: kengetallen, *_sector, signaleringen (onafgerond)
f.sectorcijfer("MBO", 2025, "liquiditeit").waarde
Bestuurssleutel.parse("40833-25PZ")    # bestuur 40833 heeft drie eenheden, één per BRIN: nooit optellen
```

## Datasetcontract

Modelonafhankelijk contract voor de zes bronnen naast CBS, afgestemd op `onderwijsbronnen.cbs.contract`:

```python
from onderwijsbronnen import contract

contract.catalog_records(sector="mbo")            # alleen datasets waar mbo 'supported' is
contract.get_dataset("duo:p01hoinges")             # of de alias "p01hoinges"
contract.get_resource("duo:p01hoinges", "c454d7e1-b9b1-4460-b9ff-55938c85788e")
contract.scope_review()                            # dekking nog onbekend
contract.catalog_manifest()                        # versie, inhoudshash, aantallen
```

Dekking is `supported`/`unsupported`/`unknown`, nooit afgeleid uit een ontbrekend veld. HO-breed
(`ho_breed`) staat los van hbo en wo; `sectorselectie[sector].verplicht` zegt wanneer een sector
alleen met een filter (RIO-type), resourcekeuze of rijselectie (DUO) leverbaar is.

## ID-contract `bron:id`

Eén sleutel per dataset, voor alle acht bronnen (#912):

```python
import onderwijsbronnen as o

o.normaliseer_bron_id("cbs_85423ned")   # 'cbs:85423NED'
o.normaliseer_bron_id("71733NED")       # 'cbs:71733ned' (de spelling van de catalogus, nooit upper())
o.parse_bron_id("rio/aangeboden-opleidingen")  # BronId(bron='rio', id='aangeboden-opleidingen')
o.catalogus()                           # {"cbs": [...], "rio": [...], "duo": [...], ...}: de samengevoegde catalogus
```

Een kale ID die bij twee bronnen past geeft `AmbigueBronId` (met `.opties`), een onbekende `OnbekendBronId`.

## UNL: WOPI-personeel

Het WOPI-personeelsbestand van Universiteiten van Nederland (#936): personeel in dienst op 31 december, per
universiteit (BRIN) en landelijk. De lader leest de link naar de nieuwste editie van de
[downloadpagina](https://www.universiteitenvannederland.nl/downloadbare-gegevens-personeel) en daarna de records van
de draaitabellen (de pivotcaches), niet de getoonde cellen. Een cache wordt gekozen op de naam van zijn brontabel;
velden, de 14 BRIN-codes en het editiejaar worden gecontroleerd (`unl.WopiFout` als iets afwijkt).

```python
from onderwijsbronnen import unl

df = unl.load("functie")                  # fte per functie en vast/tijdelijk, zonder GEZO (standaard), totaal
df = unl.load("functie", gezo="incl")     # met het HOOP-gebied Gezondheid; nooit door elkaar
df = unl.load("personen", geslacht="vrouwen")  # personen per leeftijdsklasse, alleen vrouwen

wopi = unl.lees(*unl.haal_op())           # alle tabellen van één download, met de herkomst
wopi.herkomst                             # url, editiejaar, sha256, bytes, Last-Modified; .peildatum = "31-12-2025"
```

Licentie: UNL zegt niets over hergebruik. Er staat geen data van UNL in dit pakket; de tests gebruiken een
synthetisch bestand met dezelfde XML-vorm (`unl.proefbestand`). Het XML gaat door `defusedxml`.

## Broncontrole

Een wekelijkse GitLab-job in de chatrepo (`rio:broncontrole`, zie `docs/operatie.md` daar) vergelijkt de DUO
CKAN-inventaris en de RIO-spec met de catalogus, doet één GET per RIO-lijstresource (een verwijderde API-versie valt zo
op bij de eerstvolgende controle) en meldt verschillen in één open issue. De catalogus wordt daarbij niet automatisch
vernieuwd. SBB, ROA, UWV en Inspectie worden nog niet gecontroleerd.

De live contracttest tegen RIO v3 (elke lijstresource, elk filter, de sub-resources en de ID-formaten) draait
alleen op verzoek: `RIODATA_LIVE=1 uv run pytest tests/test_rio_live.py` (de naam van de vlag is gebleven).

## Catalogus

```python
import onderwijsbronnen

onderwijsbronnen.catalog(source="rio")   # 14 RIO-resources (offline, lokale JSON)
onderwijsbronnen.catalog(source="duo")   # 57 DUO-datasets (offline, lokale JSON; met financien)
onderwijsbronnen.catalog(source="all")   # 78 gecombineerd (RIO, DUO, ROA, UWV, Inspectie, SBB)

# Live DUO-catalogus vernieuwen vanuit CKAN
onderwijsbronnen.catalog(source="duo", live=True)

# CBS heeft (nog) een eigen catalogus: onderwijsbronnen.cbs.catalog()
```

Elk record heeft dezelfde velden: `leverancier`, `bron`, `beschrijving`, `periode`,
`onderwijstype`, `tags`, `voorbeeldvragen`, `combineerbaar_met`, en voor DUO ook
`_ckan_id`, `_resources` en `_kolommen`.

## Structuur

```
src/onderwijsbronnen/
  __init__.py           catalog(source=...), BRONNEN; de bovenlaag mag alle bronnen gebruiken
  contract.py           datasetcontract voor RIO, DUO, ROA, UWV, Inspectie en SBB
  scope.py              scopebesluit per catalogusrecord (mbo/hbo/wo)
  _kern/                gedeeld: resolutie, lezen, verrijking, broncontract, versie (importeert geen bron)
  cbs/                  CBS OData-client, contract, validatie; data/ met de CBS-catalogus
  duo/                  DUO CKAN-client (resources, load, search), notes; data/ met de DUO-catalogus
  rio/                  RIO LOD API-client (fetch, get, related), filtercontract, overgangen; data/
  roa/ uwv/ inspectie/  loaders; elk een data/ met de eigen catalogus
  sbb/                  SBB-loader, crebo (CREBO-lijst), dossiers (kwalificatiedossiers-XML); data/
data/02-prepared/       bron-JSONs voor de catalogus (CBS en RIO)
catalogus/cbs/, catalogus/rio/     scripts die de catalogi en sites bouwen
voorbeelden/cbs/, voorbeelden/rio/ analysescripts + plots
docs/cbs/, docs/rio/    de catalogussites (/catalogus/cbs/ en /catalogus/rio/ op GitHub Pages)
RIO_LOD_API_v3.yml      OpenAPI spec van de RIO API (v3; v2 is op 19-10-2026 verwijderd)
```

## Links

- Catalogussites: [RIO, DUO en de rest](https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/) en
  [CBS](https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/)
- [RIO LOD API documentatie](https://lod.onderwijsregistratie.nl/rio-api)
- [DUO Open Data portaal](https://onderwijsdata.duo.nl/datasets)
