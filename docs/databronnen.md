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
DUO-data wordt in twee stappen geladen: eerst `get_duo_data` (schema + preview), dan `query_data` (gefilterde rijen). Dit is de enige externe bron met een sessiecache — eenmaal geladen data wordt hergebruikt binnen een gesprek.

**Voorbeeldvragen:**
- *"Laad de dataset over studentprognoses MBO en maak een trendgrafiek."*
- *"Vergelijk de diplomering in de sector techniek voor 2020-2023."*

---

## Geüploade bestanden

Naast de drie open databronnen kun je eigen **xlsx- of csv-bestanden** uploaden via de paperclip-knop in het invoerveld.

| Eigenschap | Details |
|------------|---------|
| Formaten | `.csv` (elke separator), `.xlsx` (meerdere sheets mogelijk) |
| Rijlimiet sessie | 10.000 rijen per bestand |
| Sessiecache | Ja — beschikbaar voor de rest van het gesprek zonder opnieuw te uploaden |
| Resume-ondersteuning | Ja — uploads worden bewaard bij gesprekken met ingelogde gebruikers |

Na het uploaden ontvangt de assistent een compact schema (kolommen, typen, voorbeeldwaarden). Je kunt daarna direct vragen stellen:

> *"Geef een samenvatting van dit bestand."*

> *"Maak een grafiek van de verdeling van Herkomst per Collegejaar."*

> *"Vergelijk de cijfers in dit bestand met de CBS-data over hetzelfde onderwerp."*

!!! tip "Reproduceerbare code"
    Analyses op geüploade bestanden zijn volledig reproduceerbaar via de **📦 Reproduceerbare code** knop. De gegenereerde `analyse.py` bevat echte `pandas`-code die de filters en aggregaties reconstrueert — geen black-box snapshot.

---

## Catalogus doorzoeken

De assistent kan de catalogus van CBS, RIO en DUO doorzoeken met `search_catalog`. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
