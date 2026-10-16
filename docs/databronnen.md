# Databronnen

De assistent haalt data op uit drie open bronnen: **CBS, DUO en RIO**. De juiste bron wordt automatisch gekozen op basis van je vraag.

**ROA** en **UWV** geeft de assistent als arbeidsmarkt-context bij een onderwijsvraag, met een eigen tool: landelijk of per provincie, niet per instelling. Ze voeden ook de [dashboards](dashboards.md).

---

## CBS — Centraal Bureau voor de Statistiek

**123 datasets** met statistische onderwijsdata over mbo, hbo en wo: aantallen studenten, diploma's, voortijdig schoolverlaters en meer, uitgesplitst naar diverse dimensies. Tabellen over po/vo, en tabellen over alle onderwijssoorten zonder sectorselectie, laadt de chat niet. Bij de VSV-tabellen over mbo én vo laadt hij alleen de mbo-rijen; bij de woonregiotabellen over alle onderwijssoorten (`85701NED` studenten, `85702NED` gediplomeerden) alleen de rijen voor mbo, hbo en wo. Die regio is waar de student woont, niet waar de instelling staat. Vier vo-tabellen (`85566NED` doorstroom uit vo en vso, `85380NED` vo-leerlingen, `85381NED` en `85382NED` vo-gediplomeerden) zijn [vo-context voor ho](#vo-context-voor-ho): de zoekfunctie toont ze alleen bij een vraag die ho noemt, en elke bronvermelding zegt "…, vo-context voor ho".

| Eigenschap | Details |
|------------|---------|
| Toegang | CBS Open Data OData API |
| Catalogus | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| Granulariteit | Nationaal, regionaal, per onderwijstype |
| Tijdreeksen | Beschikbaar voor de meeste datasets |

**Voorbeeldvragen:**
- *"Hoeveel studenten zaten er in 2022 in het mbo?"*
- *"Toon het aantal gediplomeerden in het mbo per jaar als grafiek."*
- *"Wat zijn de beschikbare dimensies in CBS dataset 85423NED?"*

---

## RIO — Register Instellingen en Opleidingen

**9 resources** uit het officiële register van erkende Nederlandse onderwijsinstellingen en hun aangeboden opleidingen. Registers over alle sectoren haalt de chat alleen op met een filter op mbo/hbo/wo; bestuur, instellingen en vestigingen van één instelling lopen via een vaste route.

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

**15 open datasets** gepubliceerd door DUO over mbo, hbo en wo, inclusief prognoses, diplomering, instroom en adressen. DUO publiceert ook po-, so- en vo-bestanden; die vallen buiten het profiel van de chat, behalve `voprognoses`: [vo-context voor ho](#vo-context-voor-ho), net als de vier vo-tabellen van CBS.

| Eigenschap | Details |
|------------|---------|
| Toegang | CKAN-gebaseerde open data portal |
| Catalogus | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| Formaten | Excel/CSV via CKAN |
| Dekking | MBO, HBO, WO |

**Categorieën:**

| Categorie | Voorbeelden |
|-----------|------------|
| Prognoses | Studentprognoses MBO, HO |
| Diplomering | Geslaagden per opleiding, sector |
| Instroom | Eerstejaars inschrijvingen |
| Adressen | Vestigingsadressen instellingen |

**Twee-stap patroon:**
DUO-data wordt in twee stappen geladen: eerst `get_duo_data` (schema + preview), dan `query_data` (gefilterde rijen). Eenmaal geladen data wordt hergebruikt binnen een gesprek via de sessiecache.

**Voorbeeldvragen:**
- *"Laad de dataset over studentprognoses MBO en maak een trendgrafiek."*
- *"Vergelijk de diplomering in de sector techniek voor 2020-2023."*

---

## Vo-context voor ho

De chat werkt voor mbo, hbo en wo; po, so en vo vallen buiten het profiel. Daarop is één smalle uitzondering (epic #554): vier CBS-tabellen en één DUO-dataset over het vo geven een vraag over het hoger onderwijs context, zoals wie er vanuit het vo naar het ho kan instromen.

| Dataset | Wat | Periode |
|---------|-----|---------|
| `85566NED` (CBS) | Doorstroom en uitstroom uit vo en vso | 2015/'16 naar 2016/'17 t/m 2022/'23 naar 2023/'24 |
| `85380NED` (CBS) | Vo-leerlingen per onderwijssoort, leerjaar en woonregio | 2021/'22-2025/'26 |
| `85381NED` (CBS) | Vo-gediplomeerden naar onderwijssoort en herkomst | 2011/'12-2024/'25 |
| `85382NED` (CBS) | Vo-gediplomeerden naar woonregio | 2011/'12-2024/'25 |
| `voprognoses` (DUO) | Leerlingenprognose vo per instelling | 2024-2030 |

- **Alleen bij een ho-vraag.** De zoekfunctie toont deze vijf alleen als de vraag van de gebruiker het hoger onderwijs noemt: hbo, wo, ho, hoger onderwijs, hogeschool of universiteit. Havo en vwo tellen niet: dat is vo (#597). Zonder zo'n woord blijven ze weg. Code beslist dat, op de vraag van de gebruiker (bij een keuze op een verduidelijkingsvraag samen met de vraag die ze afbakent), niet op de zoekterm die het model meegeeft. Buiten de chat (MCP) is er geen gebruikersvraag en beslist de zoekterm. Zie [`search_catalog`](tools.md#search_catalog).
- **Altijd met label.** Elke zoektreffer en elke bronvermelding noemt ze "vo-context voor ho": het gaat om leerlingen in het voortgezet onderwijs, niet om studenten.
- **Verder geen po, so of vo.** Alle andere po-, so- en vo-bronnen blijven buiten het profiel, ook met een dataset-ID uit de vraag.

**Grenzen.** De uitzondering is minder streng dan ze klinkt:

- **Een vervolgvraag zonder ho-woord blijft dicht.** "En voor het vwo?" na een hbo-vraag noemt zelf geen ho; de poort kijkt alleen naar de vraag van deze beurt (#597).
- **`85566NED` is slecht vindbaar.** Bij geen enkele doorstroomvraag stond hij in de top 15 (gemeten in #559); de andere vier worden wel gevonden. Niet bijgesteld zonder een echte vraag die hem mist (#597): dan eerst een testprompt in de retrieval-baseline.
- **Een dataset-ID laadt zonder ho-woord.** De poort zit alleen in het zoeken: met een van deze vijf ID's (`dataset_details`, `get_cbs_data`, `get_duo_data`) laadt de chat de data ook als niemand het hoger onderwijs noemt.
- **Alle vo-rijen.** De vier CBS-tabellen krijgen geen sectorselectie zoals de VSV-tabellen: `85566NED`, `85380NED`, `85381NED` en `85382NED` laden al hun vo-rijen (bij `85566NED` ook vso). Alleen het label zegt dat het context is.

---

## ROA — Landelijk referentiekader arbeidsmarkt

**ROA-data** biedt landelijke referentiewaarden voor de aansluiting tussen onderwijs en arbeidsmarkt. In de chat via `get_roa_benchmark`: schoolverlatersinformatie (SIS 2024, alleen landelijk) en de prognose tot 2030 per opleidingsniveau (mbo2-4, bachelor, master) of opleidingssector, landelijk of per arbeidsmarktregio of provincie. Het resultaat noemt per onderdeel de regio waar de cijfers vandaan komen. Ook gebruikt in het regiodashboard.

| Eigenschap | Details |
|------------|---------|
| Toegang | Via CBS Open Data |
| Inhoud | Doorstroompercentages, match scores per opleidingssector |
| Formaat | Landelijke referentiewaarden; de prognose ook per arbeidsmarktregio (35) en provincie (12) |

---

## UWV — Uitvoeringsinstituut Werknemersverzekeringen

**UWV-vacaturedata** geeft inzicht in de vraag naar arbeid per sector. In de chat via `get_uwv_vacatures` per provincie of gemeente en onderwijssector; ook ingezet in het arbeidsmarktdashboard. Welke beroepenclusters bij een sector horen, is een indeling van deze app, gemaakt met een taalmodel (`data/sector_cluster_mapping.json`); UWV deelt vacatures niet in onderwijssectoren in. Het resultaat houdt de UWV-aantallen, die indeling (met versie en model) en het gewogen sectorgetal apart. Een beroepencluster dat bij meer sectoren hoort, telt per sector naar rato mee, zodat de sectoren samen nooit meer vacatures hebben dan het totaal. Het arbeidsmarktdashboard telt zo'n cluster op dezelfde manier, in de match score en in de grafiek. UWV legt bij vacatures geen opleidingsniveau vast.

Een UWV- of ROA-resultaat is in de chat een dataset zoals elke andere: de tabel erachter (UWV: alle beroepenclusters van de plaats met het aantal vacatures; ROA: elk cijfer als rij met onderdeel, regio, opleiding en indicator) staat in de store onder een `data_key`, met de laadaanroep en de peildatum of versie. Daardoor lopen rapport en dashboard, het recept na een herstart, de bronnenlijst, de citaties, de snippet en de CSV-export mee; tot dan bestonden UWV en ROA voor het rapport niet en schreef het model dat er geen vacaturegegevens waren.

| Eigenschap | Details |
|------------|---------|
| Toegang | Via het UWV |
| Inhoud | Aantallen vacatures per (sub-)sector |
| Formaat | Momentopname |

!!! warning "Bevroren data"
    De UWV-vacaturedata is een bevroren momentopname uit mei 2023. Actuele vacaturedata is niet beschikbaar via deze bron.

---

## Catalogus doorzoeken

De assistent kan de catalogus van CBS, RIO, DUO, ROA en UWV doorzoeken met `search_catalog`; UWV- en ROA-treffers (AIS 2030) noemen de tool waarmee ze op te vragen zijn; oudere ROA-edities zijn gemarkeerd als niet via de chat op te vragen. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
