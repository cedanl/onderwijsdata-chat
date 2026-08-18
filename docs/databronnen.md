# Databronnen

De assistent heeft toegang tot vijf open Nederlandse onderwijs- en arbeidsmarktdatabronnen. De juiste bron wordt automatisch gekozen op basis van je vraag.

---

## CBS — Centraal Bureau voor de Statistiek

**68 datasets** met statistische onderwijsdata: aantallen leerlingen, studenten, diploma's, personeel en meer, uitgesplitst naar diverse dimensies.

| Eigenschap | Details |
|------------|---------|
| Toegang | CBS Open Data OData API |
| Catalogus | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| Granulariteit | Nationaal, regionaal, per onderwijstype |
| Tijdreeksen | Beschikbaar voor de meeste datasets |

**Voorbeeldvragen:**
- *"Hoeveel leerlingen zaten er in 2022 in het voortgezet onderwijs?"*
- *"Toon het aantal gediplomeerden in het mbo per jaar als grafiek."*
- *"Wat zijn de beschikbare dimensies in CBS dataset 85423NED?"*

---

## RIO — Register Instellingen en Opleidingen

**14 resources** met het officiële register van alle erkende Nederlandse onderwijsinstellingen en hun aangeboden opleidingen.

| Eigenschap | Details |
|------------|---------|
| Toegang | RIO LOD (Linked Open Data) API |
| Catalogus | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| Inhoud | Instellingen, locaties, opleidingen, besturen |

**Beschikbare resources:**

| Resource | Beschrijving |
|----------|-------------|
| `onderwijslocaties` | Alle fysieke locaties van onderwijsinstellingen |
| `aangeboden-opleidingen` | Erkende opleidingen per instelling |
| `onderwijsaanbieders` | Rechtspersonen die onderwijs aanbieden |
| `onderwijserkenningen` | Formele erkenningen |
| `besturen` | Schoolbesturen en hun instellingen |

**Voorbeeldvragen:**
- *"Welke hbo-instellingen zijn er in Rotterdam?"*
- *"Hoeveel onderwijslocaties heeft de Radboud Universiteit?"*

---

## DUO — Dienst Uitvoering Onderwijs

**57 open datasets** gepubliceerd door DUO, inclusief prognoses, diplomering, instroom, adressen en meer.

| Eigenschap | Details |
|------------|---------|
| Toegang | CKAN-gebaseerde open data portal |
| Catalogus | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| Formaten | Excel/CSV via CKAN |
| Dekking | PO, VO, MBO, HBO, WO |

**Categorieën:**

| Categorie | Voorbeelden |
|-----------|------------|
| Prognoses | Studentprognoses MBO, HO |
| Diplomering | Geslaagden per opleiding, sector |
| Instroom | Eerstejaars inschrijvingen |
| Adressen | Vestigingsadressen instellingen |
| Bekostiging | Leerlinggewichten, bekostigingsgegevens |

**Twee-stap patroon:**
DUO-data wordt in twee stappen geladen: eerst `get_duo_data` (schema + preview), dan `query_data` (gefilterde rijen). Eenmaal geladen data wordt hergebruikt binnen een gesprek via de sessiecache.

**Voorbeeldvragen:**
- *"Laad de dataset over studentprognoses MBO en maak een trendgrafiek."*
- *"Vergelijk de diplomering in de sector techniek voor 2020-2023."*

---

## ROA — Landelijk referentiekader arbeidsmarkt

**ROA-data** biedt landelijke referentiewaarden voor de aansluiting tussen onderwijs en arbeidsmarkt. Gebruikt in het regiodashboard als benchmark.

| Eigenschap | Details |
|------------|---------|
| Toegang | Via CBS Open Data |
| Inhoud | Doorstroompercentages, match scores per opleidingssector |
| Formaat | Landelijke referentiewaarden (geen regionale uitsplitsing) |

**Voorbeeldvragen:**
- *"Hoe vergelijkt de arbeidsmarktmatch van MBO-opleidingen met het landelijk gemiddelde?"*

---

## UWV — Uitvoeringsinstituut Werknemersverzekeringen

**UWV-vacaturedata** geeft inzicht in de vraag naar arbeid per sector. Ingezet in het arbeidsmarktdashboard.

| Eigenschap | Details |
|------------|---------|
| Toegang | Via het UWV |
| Inhoud | Aantallen vacatures per (sub-)sector |
| Formaat | Momentopname |

!!! warning "Bevroren data"
    De UWV-vacaturedata is een bevroren momentopname uit mei 2023. Actuele vacaturedata is niet beschikbaar via deze bron.

**Voorbeeldvragen:**
- *"Hoeveel vacatures waren er in de sector techniek?"*

---

## Catalogus doorzoeken

De assistent kan de catalogus van CBS, RIO, DUO, ROA en UWV doorzoeken met `search_catalog`. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
