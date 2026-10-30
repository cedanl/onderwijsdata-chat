# Databronnen

De assistent haalt data op uit drie open bronnen: **CBS, DUO en RIO**. De juiste bron wordt automatisch gekozen op basis van je vraag.

**ROA** en **UWV** geeft de assistent als arbeidsmarkt-context bij een onderwijsvraag, met een eigen tool: landelijk of per provincie, niet per instelling. Ze voeden ook de [dashboards](dashboards.md).

---

## CBS — Centraal Bureau voor de Statistiek

**125 datasets** met statistische onderwijsdata over mbo, hbo en wo: aantallen studenten, diploma's, voortijdig schoolverlaters en meer, uitgesplitst naar diverse dimensies. Tabellen over po/vo, en tabellen over alle onderwijssoorten zonder sectorselectie, laadt de chat niet. Bij de VSV-tabellen over mbo én vo (waaronder `85368NED` en `85367NED`, naar leeftijd) laadt hij alleen de mbo-rijen; bij de woonregiotabellen over alle onderwijssoorten (`85701NED` studenten, `85702NED` gediplomeerden) alleen de rijen voor mbo, hbo en wo. Die regio is waar de student woont, niet waar de instelling staat. `84312NED` geeft de mbo-studenten van Caribisch Nederland (Bonaire, Sint Eustatius en Saba); de tabel over po, vo en mbo samen (`84732NED`) laadt de chat niet. Vier vo-tabellen (`85566NED` doorstroom uit vo en vso, `85380NED` vo-leerlingen, `85381NED` en `85382NED` vo-gediplomeerden) zijn [vo-context voor ho](#vo-context-voor-ho): de zoekfunctie toont ze alleen bij een vraag die ho noemt, en elke bronvermelding zegt "…, vo-context voor ho".

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

**8 resources** uit het officiële register van erkende Nederlandse onderwijsinstellingen en hun aangeboden opleidingen. Registers over alle sectoren haalt de chat alleen op met een filter op mbo/hbo/wo; bestuur, instellingen en vestigingen van één instelling lopen via een vaste route.

| Eigenschap | Details |
|------------|---------|
| Toegang | RIO LOD (Linked Open Data) API v3 (`https://lod.onderwijsregistratie.nl/api/rio/v3`; v2 is op 19-10-2026 verwijderd) |
| Catalogus | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| Inhoud | Instellingen, locaties, opleidingen, besturen |

**Beschikbare resources** (de namen van de RIO-API):

| Resource | Beschrijving | In de chat |
|----------|-------------|------------|
| `aangeboden-opleidingen` | Opleidingsaanbod per instelling en locatie | met `type` op een mbo/ho-waarde |
| `opleidingen`, `opleidingsfasen`, `opleidingsgroepen`, `opleidingsonderdelen` | De opleidingsstructuur | met `type` op een mbo/ho-waarde |
| `opleidingserkenningen`, `onderwijslicenties` | Erkenningen en licenties per opleiding | met `type` op een mbo/ho-waarde |
| `examenlicenties` | Examenlicenties (alleen mbo) | ja |
| `erkenningen` | Besturen, instellingen en vestigingen met hun erkenning | alleen via `get_rio_instelling` |
| `organisatorische-eenheden`, `onderwijslocaties` | Aanbieders en fysieke locaties | niet per sector te selecteren: niet |

Sinds v3 heet het typefilter op elk register `type` (v2: `erkenningtype`, `opleidingseenheidtype`, …), en bestaan `aangeboden-opleiding-cohorten`, `contactadressen` en `onderwijslocatiegebruiken` alleen nog als sub-resource van een ander record, niet als lijst. De chat laadt ze daarom niet; de catalogus noemt ze wel.

**Voorbeeldvragen:**
- *"Welke hbo-opleidingen biedt de Hogeschool Rotterdam aan?"*
- *"Hoeveel vestigingen heeft ROC Mondriaan?"*

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

## Onderwijsinspectie — oordelen per bestuur

De Inspectie publiceert elke maand een peilbestand met het oordeel per bevoegd gezag (`…-oordeel-en-standaard-bg.ods`,
CC0 1.0). In de chat via `get_inspectieoordeel`, alleen voor mbo-instellingen (#749).
- **Per bestuur:** het oordeel geldt per bestuur, niet per instelling, vestiging of opleiding.
- **Gemengd bestuur:** heeft het bestuur ook po, vo of ho, dan zegt het antwoord dat het oordeel over het hele bestuur
  gaat. Op 1 oktober 2026 noemden 164 besturen mbo; 126 daarvan hebben alleen mbo.
- **Hoger onderwijs:** het hoger onderwijs heeft geen oordeel per bestuur. Daar beoordeelt de NVAO de opleidingen, en
  die bron zit niet in de app.
- **Bereikbaarheid:** `bron:ping` meet dagelijks of de bron bereikbaar is.

| Eigenschap | Details |
|------------|---------|
| Toegang | onderwijsinspectie.nl, open data (CC0 1.0) |
| Inhoud | Eindoordeel en standaarden per bevoegd gezag |
| Formaat | ODS, maandelijks peilbestand |
| Koppeling | Bestuursnummer = DUO `BEVOEGD GEZAG NUMMER` (adressen_mbo) |

---

## Bronnen onder een antwoord

Onder een antwoord met data staat het blok **Bronnen**: elke dataset die de beurt las, één keer, met titel, periode en dataset-ID. De lijst komt uit de stappen van de beurt, niet uit de tekst van het model.

Elke regel is een link naar de bronpagina van die dataset (#621), die in een nieuw tabblad opent. Het is dezelfde link als onder een grafiek in een rapport: voor CBS de StatLine-tabelpagina (#638), voor de andere bronnen de documentatie-URL uit de catalogus. Op een telefoon is de hele regel aan te tikken.

| Bron | Link naar |
|------|-----------|
| CBS | de tabelpagina op StatLine, bijv. `https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table` (niet de OData-JSON; het ID in de spelling van de catalogus) |
| DUO | de datasetpagina in de DUO-portal, bijv. `https://onderwijsdata.duo.nl/datasets/p01hoinges`; onder een rapportgrafiek de pagina van het geladen bestand (`…/datasets/p01hoinges/resources/<resource-id>`, #737) |
| RIO | het register in de RIO-API, ook bij een opzoeking per instelling (`erkenningen`) |
| UWV | UWV Open Match op data.overheid.nl |
| ROA | de dataset AIS 2030 (DOI) |

Een regel heeft bewust geen link:

- **De catalogus kent de dataset niet, of heeft er geen http(s)-adres voor.** De app gokt geen link; de regel blijft tekst. Alleen een `http://`- of `https://`-adres wordt een link, op de server en nog eens in de browser.
- **Het antwoord is van vóór deze wijziging.** Een eerder bewaard gesprek toont zijn bronnen als tekst; de links worden niet achteraf toegevoegd.

Kopiëren en de gespreksexport geven de bronnen als tekst, zoals voorheen.

---

## Catalogus doorzoeken

De assistent kan de catalogus van CBS, RIO, DUO, ROA en UWV doorzoeken met `search_catalog`; UWV- en ROA-treffers (AIS 2030) noemen de tool waarmee ze op te vragen zijn; oudere ROA-edities zijn gemarkeerd als niet via de chat op te vragen. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
