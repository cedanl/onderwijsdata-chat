# Dataproducten voor het onderwijs

Drie opties voor de data coalitie om waarde te leveren aan beleids- en datamedewerkers
bij onderwijsinstellingen — zonder dat elke instelling het wiel opnieuw uitvindt.

---

## Optie 1: Dataset-catalogus met AI-samenvatting

Automatisch alle publieke onderwijsdatasets ophalen en per dataset een begrijpelijke
AI-samenvatting genereren. Output: een doorzoekbare catalogus.

**Waarde:** beleidsmedewerker zoekt "uitval MBO" en vindt direct de juiste dataset,
wat erin zit, welke vragen je ermee kunt beantwoorden, en welke andere datasets
hiermee samenhangen — zonder zelf door de CBS-documentatie te hoeven.

**Technisch:**
- ~68 onderwijsdatasets via CBS OData (thema-gebaseerd)
- Per dataset: 2 vaste calls (TableInfos + DataProperties) + ~4 dimensie-calls
- Totaal: ~400 calls voor volledige catalogus, eenmalig te bouwen en te cachen
- LLM genereert per dataset een plain-language samenvatting op basis van metadata
- Output: statische HTML of JSON die instellingen kunnen embedden

---

## Optie 2: Natural language interface op de data

Een LLM die weet welke datasets er zijn, de dimensies kent, en OData-filters genereert
op basis van een vraag in gewone taal.

**Voorbeeld:**
> "Hoeveel vrouwen stromen in bij WO in regio west de afgelopen 5 jaar?"
→ LLM genereert filter → client haalt data op → plot als antwoord

**Waarde:** datamedewerkers zonder Python-kennis kunnen zelf vragen stellen aan
publieke onderwijsdata. De CBS-client wordt een "tool" die het model aanroept via
function calling (Anthropic Agent SDK).

---

## Optie 3: Gestandaardiseerde benchmarkrapporten per instelling

Instellingen vullen hun naam in en krijgen automatisch een rapport met hun positie
t.o.v. vergelijkbare instellingen: instroomtrends, man/vrouw verhouding, uitval.

**Waarde:** de coalitie beheert de definitie van de KPIs — dat is de
standaardisatiewaarde. Geen discussie meer over welke metrics tellen.

---

## Uitwerking Optie 1 — Catalogus

### Aanpak

1. **Datasets ophalen** via CBS ODataCatalog op basis van onderwijsthema's (68 datasets)
2. **Metadata verzamelen** per dataset: titel, periode, dimensies, onderwerpen
3. **AI-samenvatting genereren** per dataset met Claude: wat meet dit, welke vragen
   beantwoordt het, voor wie is het relevant
4. **Catalogus exporteren** als doorzoekbare statische HTML

### API calls berekening

| Stap | Calls |
|---|---|
| Alle dataset-IDs ophalen via themes | 1 call |
| TableInfos per dataset (beschrijving, periode, bron) | 68 calls |
| DataProperties per dataset (dimensies + meetwaarden) | 68 calls |
| Dimensiewaarden per dataset (~4 dims gemiddeld) | ~272 calls |
| **Totaal** | **~410 calls** |

Eenmalig te draaien, resultaat op te slaan als JSON. Daarna alleen refreshen
bij nieuwe datasets (CBS publiceert ~maandelijks).

### LLM input per dataset

Per dataset stuur je naar Claude:
- Titel + beschrijving
- Periode (bijv. 2011–2026)
- Dimensies met hun mogelijke waarden (bijv. Geslacht: M/V/Totaal)
- Meetwaarden (bijv. TotaalIngeschrevenen)

Claude genereert:
- Samenvatting in 2 zinnen
- 3 voorbeeldvragen die je met deze dataset kunt beantwoorden
- Tags (bijv. `mbo`, `instroom`, `regio`, `geslacht`)

### Output

```json
{
  "id": "85423NED",
  "titel": "Hoger onderwijs; ingeschrevenen",
  "periode": "2011-2026",
  "samenvatting": "Aantal ingeschreven studenten in HBO en WO, uitgesplitst naar geslacht, onderwijssoort en opleidingsvorm.",
  "voorbeeldvragen": [
    "Hoeveel studenten zijn er ingeschreven bij HBO in 2024?",
    "Hoe ontwikkelt het vrouwenaandeel in WO zich over tijd?",
    "Wat is het aandeel deeltijdstudenten per jaar?"
  ],
  "tags": ["ho", "hbo", "wo", "instroom", "geslacht", "opleidingsvorm"]
}
```

### Integratie met cedanl/overzicht-landelijke-databronnen

De repo `cedanl/overzicht-landelijke-databronnen` heeft al een GitHub Pages site
met een filterbare card-weergave op basis van `docs/data.json`. CBS-datasets zijn
daar nu volledig afwezig (24 handmatige entries, geen enkele CBS).

De catalogus-builder kan output genereren in exact hetzelfde JSON-formaat zodat
CBS-datasets automatisch in de bestaande site verschijnen — zonder nieuwe site te
bouwen.

```json
{
  "leverancier": "CBS",
  "bron": "Hoger onderwijs; ingeschrevenen",
  "onderwijstype": ["HBO", "WO"],
  "doel": "Aantal ingeschreven studenten uitgesplitst naar geslacht, onderwijstype en opleidingsvorm.",
  "frequentie": "Jaarlijks",
  "categorie": "Inschrijvingen en Studievoortgang",
  "sectie": "Studentgegevens & Onderwijs",
  "documentatie": {
    "tekst": "CBS Open Data 85423NED",
    "url": "https://opendata.cbs.nl/ODataApi/OData/85423NED"
  },
  "repositories": [],
  "publieke_producten": []
}
```

**Voordeel:** `data.json` groeit automatisch van 24 → ~92 entries. Een GitHub
Actions workflow kan dit periodiek draaien zodat nieuwe CBS-datasets direct
zichtbaar worden in de catalogussite.
