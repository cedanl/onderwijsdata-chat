# Databronnen

De assistent heeft toegang tot drie open Nederlandse onderwijsdatabronnen. De juiste bron wordt automatisch gekozen op basis van je vraag.

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
DUO-data wordt in twee stappen geladen: eerst `get_duo_data` (schema + preview), dan `query_duo_data` (gefilterde rijen). Dit is de enige bron met een sessiecache — eenmaal geladen data wordt hergebruikt binnen een gesprek.

**Voorbeeldvragen:**
- *"Laad de dataset over studentprognoses MBO en maak een trendgrafiek."*
- *"Vergelijk de diplomering in de sector techniek voor 2020-2023."*

---

## Catalogus doorzoeken

De assistent kan de catalogus van alle drie bronnen doorzoeken met `search_catalog`. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
