# Databronnen

De assistent haalt data op uit drie open bronnen: **CBS, DUO en RIO**. De juiste bron wordt automatisch gekozen op basis van je vraag.

**ROA** en **UWV** geeft de assistent als arbeidsmarkt-context bij een onderwijsvraag, met een eigen tool: landelijk of per provincie, niet per instelling. Ze voeden ook de [dashboards](dashboards.md).

---

## CBS — Centraal Bureau voor de Statistiek

**130 datasets** met statistische onderwijsdata over mbo, hbo en wo: aantallen studenten, diploma's, voortijdig schoolverlaters en meer, uitgesplitst naar diverse dimensies. Tabellen over po/vo, en tabellen over alle onderwijssoorten zonder sectorselectie, laadt de chat niet. Bij de VSV-tabellen over mbo én vo (waaronder `85368NED` en `85367NED`, naar leeftijd) laadt hij alleen de mbo-rijen; bij de woonregiotabellen over alle onderwijssoorten (`85701NED` studenten, `85702NED` gediplomeerden) alleen de rijen voor mbo, hbo en wo. Bij een doorstroomvraag die zelf het vo noemt, komen hun vo- en vavo-rijen erbij, als [vo-context voor vervolgonderwijs](#vo-context-voor-vervolgonderwijs) (#879). Die regio is waar de student woont, niet waar de instelling staat. `84312NED` geeft de mbo-studenten van Caribisch Nederland (Bonaire, Sint Eustatius en Saba); de tabel over po, vo en mbo samen (`84732NED`) laadt de chat niet. Negen tabellen over het vo (doorstroom, vo-leerlingen en -gediplomeerden, vo-cohorten, vavo en de terugkeer van voortijdig schoolverlaters) zijn [vo-context voor vervolgonderwijs](#vo-context-voor-vervolgonderwijs): de zoekfunctie toont ze alleen bij een vraag over het ho of over doorstroom uit het vo, en elke bronvermelding zegt "…, vo-context voor vervolgonderwijs". Ongeveer twee derde van de tabellen is gearchiveerd: CBS werkt ze niet meer bij. De zoekfunctie toont ze pas als er geen lopende tabel past, en de zoektreffer, het resultaat van `get_cbs_data` (`gearchiveerd`, `laatste_periode`), de Bronnen, de bronregel onder een rapportgrafiek en de kop van een CSV-export zeggen "…, gearchiveerd, laatste periode 2016/'17" (#865).

| Eigenschap | Details |
|------------|---------|
| Toegang | CBS Open Data OData API |
| Catalogus | [catalogus/cbs](https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/) |
| Pakket | `onderwijsbronnen.cbs` (tot #910 het pakket `onderwijsdata`), in deze repo onder `packages/onderwijsbronnen`; de versie staat in `/version` onder `catalogus`, met de commit waaruit hij komt (#888) |
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
| Catalogus | [catalogus/rio](https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/) |
| Pakket | `onderwijsbronnen.duo` en `onderwijsbronnen.rio` (tot #910 het pakket `riodata`), in deze repo onder `packages/onderwijsbronnen`; de versie staat in `/version` onder `catalogus`, met de commit waaruit hij komt (#888) |
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

Bij een doorstroomvraag die zelf het vo noemt, laten `aangeboden-opleidingen`, `opleidingen`, `opleidingserkenningen` en `onderwijslicenties` ook hun vo- en vavo-typen toe (`AANGEBODENVAVOOPLEIDING`, `VOOPLEIDING`, …), als [vo-context voor vervolgonderwijs](#vo-context-voor-vervolgonderwijs) (#880). Po- en (v)so-typen blijven dicht.

Sinds v3 heet het typefilter op elk register `type` (v2: `erkenningtype`, `opleidingseenheidtype`, …), en bestaan `aangeboden-opleiding-cohorten`, `contactadressen` en `onderwijslocatiegebruiken` alleen nog als sub-resource van een ander record, niet als lijst. De chat laadt ze daarom niet; de catalogus noemt ze wel.

### Fusies (RIO-overgangen, #728)

RIO legt elke fusie en overdracht vast als instellingsrelatie `OVERGANG_VOLLEDIG` of `OVERGANG_GEDEELTELIJK`, van de oude
erkenning naar de nieuwe, met de dag van de overgang. Het DUO-register "Basisgegevens instellingen" voegt daar bij mbo,
hbo en wo niets aan toe (onderzoek 04-11-2026, no-go): de chat gebruikt alleen RIO.

- **Pakket:** `onderwijsbronnen.rio.opvolgers(brin, peildatum)` en `onderwijsbronnen.rio.voorgangers(brin, sinds)` volgen de overgangen, ook door
  een keten en veilig bij een cyclus, en geven altijd `datumGeldigOp` mee. Per stap: code, naam, volledig/gedeeltelijk en
  datum.
- **Oude naam of BRIN:** `get_rio_instelling("Friesland College")` of `get_rio_instelling("25LG")` geeft `status:
  opgegaan` met de vaste zin "Regionaal Opleidingen Centrum Friesland College (25LG) is per 1 augustus 2023 opgegaan in
  Firda (08PG) (volledige overgang)." Vindt de naam ook een actieve instelling (Regio College → Talland), dan komt de
  zin naast het overzicht. De zin staat ook onder het antwoord, in het Telling-blok. Een opgeheven po/vo-instelling
  krijgt geen zin (#355).
- **Meerjarige DUO-reeks per instelling:** DUO rekent elke reeks om naar de huidige code. Firda telt in 2021 en 2022 dus
  ook Friesland College mee. Valt een fusie na de telling (1 oktober) van het eerste jaar en uiterlijk op die van het
  laatste, dan krijgt het Telling-blok de regel "Fusie bij Firda (08PG): DUO telt de jaren vóór de fusie (1 augustus
  2023) bij de huidige instelling (voorgangers: …)". In de reeksen 2021–2025 geldt dat voor vijf instellingen: Vonk, KW1C,
  Firda, Drenthe College Terra en Talland. Yuverta (fusie 1-8-2021) valt vóór de eerste telling.
  - Een voorganger uit po, vo of so (wet `WPO`, `WVO` of `WEC` in RIO, op de dag vóór de overgang) staat niet in de
    regel: een mbo- of ho-reeks van DUO telt die leerlingen niet (#937). Landstede nam per 1-8-2025 Morgen College
    (02EX, vmbo) op en krijgt daarom geen regel. Een voorganger waarvan RIO de wet niet kent, blijft staan.
  - De selectie legt de regel vast bij het afleiden (`dekking.van`, `KeyMeta.fusies`), alleen bij DUO, minstens twee
    jaren en hooguit tien instellingen: een ranglijst van alle instellingen vraagt RIO niets.
  - De voorgangers per code staan een dag in de cache (`core/actualiteit.py`). Een fout komt niet in de cache; bij een
    storing komt er geen regel en een WARNING `FUSIES_ONBEKEND`, en het antwoord gaat gewoon door.
  - De bron-ping `rio-fusies` (`scripts/bronping.py`) bewaakt dat de vijf hun regel houden en dat Landstede haar
    vmbo-voorganger niet noemt.
- **Peildatum in het verleden:** `get_rio_instelling` leest de relaties en erkenningen met `datumGeldigOp`. "Friesland
  College" op 2022-10-01 vindt zo bestuur 40295 met 25LG, in plaats van "geen mbo-, hbo- of wo-instelling".

**Voorbeeldvragen:**
- *"Welke hbo-opleidingen biedt de Hogeschool Rotterdam aan?"*
- *"Hoeveel vestigingen heeft ROC Mondriaan?"*
- *"Hoeveel vestigingen had Friesland College?"* (opgegaan in Firda)

---

## DUO — Dienst Uitvoering Onderwijs

**15 open datasets** gepubliceerd door DUO over mbo, hbo en wo, inclusief prognoses, diplomering, instroom en adressen. DUO publiceert ook po-, so- en vo-bestanden; die vallen buiten het profiel van de chat, behalve `voprognoses`: [vo-context voor vervolgonderwijs](#vo-context-voor-vervolgonderwijs), net als de negen vo-tabellen van CBS.

| Eigenschap | Details |
|------------|---------|
| Toegang | CKAN-gebaseerde open data portal |
| Catalogus | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| Formaten | Excel/CSV via CKAN |
| Dekking | MBO, HBO, WO |
| Licentie | CC0 1.0 (hieronder) |

**Licentie, voor elke DUO-bron (#971):** CC0 1.0. DUO verklaart op
[Hergebruik open onderwijsdata](https://duo.nl/open_onderwijsdata/veelgestelde-vragen/hergebruik.jsp) dat op de open
onderwijsdata die DUO beschikbaar stelt een CC0-verklaring van toepassing is, met de Engelse Legal Code als leidend
(nagelezen 06-11-2026). Dat geldt voor de CKAN-portal onderwijsdata.duo.nl en voor de bestanden op
duo.nl/open_onderwijsdata (de indicatoren mbo, de financiën uit XBRL), ook als een bestand of pagina zelf geen licentie
noemt. Het CKAN-veld `license_id` zegt bij 51 van de 57 datasets `cc-by` en bij 6 niets; de app volgt de verklaring van
DUO zelf. Omdat de app bij elk antwoord DUO en de URL noemt, voldoet ze ook aan CC-BY. Een DUO-bestand als testfixture
in de repo (en dus op de publieke spiegel) valt onder dezelfde regel, met de URL in `tests/fixtures/gouden/bronnen.json`.

**Categorieën:**

| Categorie | Voorbeelden |
|-----------|------------|
| Prognoses | Studentprognoses MBO, HO |
| Diplomering | Geslaagden per opleiding, sector |
| Instroom | Eerstejaars inschrijvingen |
| Adressen | Vestigingsadressen instellingen |

**Regio en nevenlocaties (mbo, #744):** adressen en studentaantallen bestaan bij DUO alleen per instelling (BRIN), met
de plaats van de hoofdvestiging. Zone.college (31JC) heeft zijn hoofdvestiging in Lochem en geeft 22 opleidingen in
Doetinchem, waar het Graafschap College (24ZZ) staat; het is geen vestiging van het Graafschap College. Filtert
`query_data` een mbo-bestand op de plaats, de gemeente, de provincie of de arbeidsmarktregio van de instelling
(`PLAATSNAAM INSTELLING`, `GEMEENTE INSTELLING`/`GEMEENTENUMMER INSTELLING`, `PROVINCIE INSTELLING`,
`ARBEIDSMARKTREGIO INSTELLING`) en blijft het resultaat per instelling (geen
aggregatie, of een groepering op `INSTELLINGSCODE` of `INSTELLINGSNAAM`), dan neemt de code ook de instellingen mee met
een onderwijslocatie in dat gebied (`tools/regiolocaties.py`). Het niveau volgt uit de kolom van het filter, niet uit
een vaste keuze. Een vaste regel in het Telling-blok noemt wie alleen zo meedoet, met de hoofdvestiging, en zegt dat
hun studentaantallen per instelling gelden en niet per locatie; de snippet herhaalt dezelfde selectie.

**`ARBEIDSMARKTREGIO INSTELLING`:** geen DUO-bestand heeft de arbeidsmarktregio van de instelling. De chat zet haar
erbij in dezelfde mbo-bestanden als `PROVINCIE INSTELLING` (`tools/instellingsprovincie.py`): de gemeente van de
hoofdvestiging (`GEMEENTENUMMER INSTELLING` als het bestand die heeft, anders het adres uit `adressen_mbo`) en de
CBS-indeling van `data/arbeidsmarktregio.py`, dezelfde als in het instellingsprofiel en voor ROA. Een gemeente zonder
regio blijft leeg. Op 05-11-2026 kregen alle 55 instellingen van mbo-studenten-per-instelling een regio (28 regio's).
De snippet zet de kolom op dezelfde manier, met de CBS-tabel via `onderwijsbronnen.cbs.data`.

**Totalen blijven bij de hoofdvestiging.** Een som over de instellingen heen (bijvoorbeeld per jaar) telt alleen de
instellingen met hun hoofdvestiging in het gebied, zoals vóór #744: anders telde een instelling met één locatie in het
gebied met al haar studenten mee (Gelderland 2025: 53.761 werd 104.040, met KW1C, Landstede en Yuverta). Een lezing in
de toolresponse zegt hoeveel instellingen met alleen een onderwijslocatie in het gebied niet in het totaal zitten; die
telling gebruikt dezelfde dagcache als de vergelijking per instelling.

- **Locaties:** `mbo_opleidingsaanbod`, DUO's dagelijkse export van het RIO-aanbod per onderwijslocatie (plaats en
  aanbieder, `ONDERWIJSAANBIEDERID`). RIO zelf filtert locaties niet op plaats: de lijst telt 13.655 locaties in pagina's
  van 100. De plaatsnamen zijn die van RIO (nagegaan voor alle 570 mbo-locaties).
- **Aanbieder → BRIN:** RIO, `/erkenningen/{brin}/organisatorische-eenheden` (`onderwijsbronnen.rio.onderwijsaanbieders`), voor
  alle instellingen in het bestand in één lading. De andere routes in RIO zijn niet bruikbaar (05-11-2026): de
  locatiegebruiken dragen bij 459 van de 570 mbo-locaties geen erkenning, `/organisatorische-eenheden/{aanbieder}/erkenningen`
  gaf HTTP 500 voor 23 van de 407 aanbieders (Summa College, Koning Willem I College) en
  `/erkenningen/{vestiging}/onderwijslocatiegebruiken` mist de locatie van Zone.college in Doetinchem.
- **Gemeente en provincie** van een woonplaats: CBS "Woonplaatsen in Nederland 2026" (86312NED,
  `data/woonplaatsen.json`, ververs met `scripts/refresh_woonplaatsen.py`). Een woonplaatsnaam in meer gemeenten (Velp:
  Rheden en Land van Cuijk; ook Hoorn en Beek) krijgt geen gemeente: zo'n locatie telt alleen als het filter op de
  plaats staat.
- **Arbeidsmarktregio** van een locatie: de gemeente uit de woonplaats, dan de CBS-indeling gemeente → arbeidsmarktregio
  van `data/arbeidsmarktregio.py` (86247NED, "Gebieden in Nederland 2026", de 35 regio's van UWV en ROA).
- Beide bronnen staan een dag in de cache. Een storing geeft geen extra instellingen, geen regel en een WARNING
  (`REGIOLOCATIES_ONBEKEND`).

Bekende grenzen: de locaties zijn die van het huidige aanbod, ook bij een reeks over eerdere jaren. Op 05-11-2026 koppelden
486 van de 570 mbo-locaties aan een van de 55 instellingen in mbo-studenten-per-instelling; de rest zijn vooral
niet-bekostigde aanbieders, en aanbieders die RIO nog onder een opgeheven instelling of een eigen bestuur voert (de
Zaanse locaties van het Regio College, nu Talland; de Kop van Noord-Holland, nu Vonk). Een selectie die het model met
`run_analysis` zelf op regio maakt, gaat er buiten om. Het dashboard "mijn instelling" kiest zijn peers nog op het
adres van de hoofdvestiging (#904).

**Twee-stap patroon:**
DUO-data wordt in twee stappen geladen: eerst `get_duo_data` (schema + preview), dan `query_data` (gefilterde rijen). Eenmaal geladen data wordt hergebruikt binnen een gesprek via de sessiecache.

**Voorbeeldvragen:**
- *"Laad de dataset over studentprognoses MBO en maak een trendgrafiek."*
- *"Vergelijk de diplomering in de sector techniek voor 2020-2023."*

---

## Vo-context voor vervolgonderwijs

De chat werkt voor mbo, hbo en wo; po, so en vo vallen buiten het profiel. Daarop is één uitzondering (epic #554, besluit A van #877): negen CBS-tabellen en één DUO-dataset over het vo geven context bij een vraag over vervolgonderwijs, zoals wie er vanuit het vo naar het mbo, hbo of wo doorstroomt of kan doorstromen.

| Dataset | Wat | Periode |
|---------|-----|---------|
| `85566NED` (CBS) | Doorstroom en uitstroom uit vo en vso | 2015/'16 naar 2016/'17 t/m 2022/'23 naar 2023/'24 |
| `85380NED` (CBS) | Vo-leerlingen per onderwijssoort, leerjaar en woonregio | 2021/'22-2025/'26 |
| `85379NED` (CBS) | Vo-leerlingen per onderwijssoort in detail (vmbo-leerweg), leerjaar en herkomst | 2020/'21-2025/'26 |
| `85381NED` (CBS) | Vo-gediplomeerden naar onderwijssoort en herkomst | 2011/'12-2024/'25 |
| `85382NED` (CBS) | Vo-gediplomeerden naar woonregio | 2011/'12-2024/'25 |
| `85534NED` (CBS) | Vo-cohorten: hoogst behaald diploma en onderwijspositie op een later peilmoment | startjaren 2008-2018 (even jaren) |
| `85328NED` (CBS) | Vavo-gediplomeerden naar onderwijssoort | 2006/'07-2024/'25 |
| `85329NED` (CBS) | Vavo-deelnemers naar onderwijssoort | 2006/'07-2025/'26 |
| `85948NED` (CBS) | Terugkeer in het onderwijs van voortijdig schoolverlaters uit vo en mbo | 2007/'08-2021/'22 |
| `voprognoses` (DUO) | Leerlingenprognose vo per instelling | 2024-2030 |

- **Alleen bij een vraag over vervolgonderwijs.** De zoekfunctie toont deze tien alleen als de vraag van de gebruiker het hoger onderwijs noemt (hbo, wo, ho, hoger onderwijs, hogeschool, universiteit), of een vo-niveau (vmbo, havo, vwo, vo, vavo, voortgezet onderwijs, middelbare school, havisten) samen met het mbo of een doorstroomwoord (doorstroom, stromen door, uitstroom, vervolgonderwijs, vervolgopleiding, na het examen, na hun diploma), of voortijdig schoolverlaters die terugkeren in het onderwijs. Code beslist dat (`ho_markers.opent_vo_context`), op de vraag van de gebruiker (bij een keuze op een verduidelijkingsvraag samen met de vraag die ze afbakent), niet op de zoekterm die het model meegeeft. Een keuze op een kaart uit code telt niet mee: "Landelijk: mbo, hbo en wo samen" op de afbakeningskaart is tekst van code en opent de poort niet (#968). Buiten de chat (MCP) is er geen gebruikersvraag en beslist de zoekterm. Zie [`search_catalog`](tools.md#search_catalog).
- **Voorbeelden.** Wel: "Hoeveel vmbo-leerlingen stromen door naar het mbo?", "Waar gaan havo-leerlingen heen na hun diploma?", "Hoeveel voortijdig schoolverlaters keren terug in het onderwijs?". Niet: "Hoeveel leerlingen zitten er op het vwo in Utrecht?" (een losse vo-vraag krijgt de vaste scope-uitleg) en "Hoeveel mbo-studenten per instelling?" (het mbo zonder vo-niveau).
- **Toelating tot een ho-opleiding (#878, #957).** Een vraag naar de toelatingseisen van een ho-opleiding met havo of vwo als vooropleiding ("Welk profiel heb ik met havo nodig voor Verpleegkunde?", "Kan ik met een havo-diploma naar Geneeskunde?") krijgt niet de vaste scope-uitleg (`ho_markers.TOELATING_HO` in `agent/po_vraag.py`): het vo-niveau is dan de vooropleiding, geen vo-data, en de eisen komen uit de Studiekeuzedatabase (weergave `toelating`). Die vraag opent de vo-context niet. Een los toelatingswoord of een losse graad telt niet (#968): "Hoeveel leerlingen worden toegelaten tot het vwo?", "…een vwo-advies na de toelatingstoets?" en "Hoeveel leraren in het vo hebben een master?" krijgen de scope-uitleg. Het telt alleen als havo of vwo de vooropleiding is met een doel ("met havo … nodig/naar/toegelaten/studeren"), als een opleiding of studie het doel is ("voor de bachelor Psychologie"), bij een toelatingseis voor iets anders dan een vo-niveau, of bij numerus fixus en associate degree; een vo-doel ("naar/tot het vwo") sluit uit.
- **Altijd met label.** Elke zoektreffer en elke bronvermelding (de Bronnen, de bronregel onder een rapportgrafiek, de kop van een CSV-export) noemt ze "vo-context voor vervolgonderwijs": het gaat om leerlingen in het voortgezet onderwijs, vavo-deelnemers of schoolverlaters, niet om mbo- of ho-studenten.
- **Het vo-deel van gemengde bronnen (#879, #880).** De VSV-tabellen `85368NED`/`85367NED` en de woonregiotabellen `85701NED`/`85702NED` laden hun vo- en vavo-rijen erbij, en de RIO-registers met een typefilter laten hun vo- en vavo-typen toe, maar alleen als de vraag de vo-context opent én zelf een vo-niveau of voortijdig schoolverlaters noemt, zonder po of (v)so (`ho_markers.vo_deel_poort`). Wel: "Hoeveel vo-leerlingen worden voortijdig schoolverlater en hoeveel daarvan in het mbo?", "Hoeveel havisten en vwo'ers in Utrecht stromen door naar het hbo?", "Welke vavo-opleidingen bieden roc's in Utrecht aan?". Niet: "Hoeveel mbo-studenten verlaten voortijdig de school?", en ook niet "Hoeveel hbo-studenten wonen er in Utrecht?": die opent de zoekpoort, maar zonder vo-niveau zouden vo-leerlingen tussen de studenten komen. De totalen over vo en mbo samen ("Totaal onderwijs") en de po- en (v)so-rijen blijven weg. De bronregel noemt het deel per lading: "…, alleen mbo en vo (vo-context voor vervolgonderwijs)" bij CBS, "…, vo-context voor vervolgonderwijs" bij een RIO-pagina met een vo-type; een eerdere lading houdt haar bronregel, ook als een latere beurt dezelfde tabel anders laadt.
- **Inspectieoordelen van vo-scholen (#881).** Achter dezelfde poort (`vo_deel_poort`) geeft `get_inspectieoordeel_vo` de oordelen van de Inspectie per afdeling (vmbo, havo, vwo, pro) van de vo-scholen in één gemeente, met het etiket "vo-context voor vervolgonderwijs" in het resultaat, de bronregel en de Bronnen. Wel: "Hoe beoordeelt de inspectie de havo/vwo-afdelingen van de scholen waar onze eerstejaars hbo vandaan komen in Utrecht?". Niet: "Wat is het inspectieoordeel van ROC Midden Nederland?" (daarvoor is `get_inspectieoordeel`), "Hoe beoordeelt de inspectie de havo-afdelingen in Utrecht?" en een vraag over één vo-school, die het vaste vo-antwoord krijgt. Zie [Onderwijsinspectie — oordelen per vo-school](#onderwijsinspectie-oordelen-per-vo-school-vo-context).
- **Verder geen po, so of vo.** Alle andere po-, so- en vo-bronnen blijven buiten het profiel, ook met een dataset-ID uit de vraag: de gearchiveerde CBS-reeksen (zoals `80040ned`-`80043ned`), de DUO-bestanden t/m 2019 (`01/02voins-v1`, `03/04_voex-v1`), `06_vomtgo`, `adressen_vo` en alles over po en (v)so. Ze komen pas mee als een echte vraag erom vraagt.

**Grenzen.** De uitzondering is minder streng dan ze klinkt:

- **Een vervolgvraag zonder eigen woord blijft dicht.** "En voor het vwo?" na een doorstroomvraag noemt zelf geen ho en geen doorstroom; de poort kijkt alleen naar de vraag van deze beurt (#597).
- **Een ho-vraag opent alles.** Wie het ho noemt, krijgt de hele vo-context, ook als de vraag niet over doorstroom gaat. Daarom staat `adressen_vo` er niet in: bij "Wat is het adres van de Hogeschool Utrecht?" kwam hij op rang 3 (#877).
- **Doorstroom binnen het vo telt niet**, als de vraag het doel noemt ("van het vmbo naar de havo"). Zonder doel ("Hoeveel vo-leerlingen stromen door?") gaat de poort wel open.
- **Een vo-school blijft dicht.** Een vraag over één vo-school ("het Erasmus Gymnasium") krijgt het vaste vo-antwoord, ook met een doorstroomwoord: er is geen doorstroom per school in deze set.
- **`85566NED` vindt trefwoorden, geen volzin.** De catalogus noemt zijn onderwijstype "VO", niet vmbo, havo of vwo; sinds #882 raakt een vo-schoolsoort het onderwijstype van een vo-contextrecord, zodat hij bij "doorstroom vmbo mbo" en "doorstroom vwo wo" op rang 4 staat en bij "havo doorstroom vervolgonderwijs" op rang 2. Met de volzin ("Hoeveel vmbo-leerlingen stromen door naar het mbo?") staat hij nog buiten de top 15: "vmbo-leerlingen" en "stromen door" raken hem niet. Een tabel over vo en mbo samen krijgt die schoolsoorten niet.
- **Een dataset-ID laadt zonder poort.** De poort zit alleen in het zoeken: met een van deze tien ID's (`dataset_details`, `get_cbs_data`, `get_duo_data`) laadt de chat de data ook zonder doorstroomvraag.
- **Alle vo-rijen in de vo-tabellen.** De vo-tabellen krijgen geen sectorselectie: ze laden al hun rijen (bij `85566NED` ook vso, bij `85948NED` ook de mbo-kolommen).
- **Het vo-deel van een gemengde bron alleen in de chat.** Buiten de chat (MCP, evals) is er geen gebruikersvraag; daar laden de gemengde CBS-tabellen alleen hun mbo/hbo/wo-rijen en weigeren de RIO-registers een vo-type, ook met een dataset-ID. Een herlaadrecept onthoudt wel of een lading het vo-deel had.
- **Een vervolgvraag zonder vo-niveau laadt geen vo-rijen.** "En per gemeente?" na een doorstroomvraag noemt zelf geen vo: de poort kijkt naar de vraag van deze beurt (#597), net als de zoekpoort.
- **RIO geeft geen aantallen.** Het vavo-aanbod van een roc komt uit één pagina van het register, zonder totaal; vavo-deelnemers tellen doet `85329NED`. De retrieval-baseline vindt `aangeboden-opleidingen` bij "vavo opleidingsaanbod" op rang 4, met de vraag zelf niet in de top 15 (mbo-32).

---

## ROA — Landelijk referentiekader arbeidsmarkt

**ROA-data** biedt landelijke referentiewaarden voor de aansluiting tussen onderwijs en arbeidsmarkt. In de chat via `get_roa_benchmark`: schoolverlatersinformatie (SIS 2024, alleen landelijk) en de prognose tot 2030 per opleidingsniveau (mbo2-4, bachelor, master) of opleidingssector, landelijk of per arbeidsmarktregio of provincie. Het resultaat noemt per onderdeel de regio waar de cijfers vandaan komen. Ook gebruikt in het regiodashboard.

**Hbo- en wo-opleidingen (#745).** ROA deelt de opleidingen in naar ONR2019: niveau (Bachelor, "Master, doctor"), sector, subsector en opleidingstype. In AIS 2030 (editie 2025, versie v20251218) staan voor het ho 8 bachelor- en 7 master-subsectoren, ook per arbeidsmarktregio en provincie (de prognose, als typering), en 26 bachelor- en 21 master-opleidingstypen, alleen landelijk. De code in de kolom `waarde` geeft de hiërarchie: subsector 32120, haar typen 32121-32123. Met het argument `onderdeel` (het DUO-onderdeel, zoals `GEDRAG_EN_MAATSCHAPPIJ`) geeft de tool naast de ho-niveaus de gekoppelde subsector (of sector) voor de regio en de opleidingstypen eronder, landelijk.

- **De koppeling is een tabel van de app**, geen indeling van DUO of ROA: `data/roa_koppeling.py`. Ze is gemeten op de ISCED-rubrieken van de erkende opleidingen in DUO (`overzicht-erkenningen-ho`, 05-11-2026): een onderdeel hoort bij een subsector als ten hoogste 20% van zijn opleidingen aantoonbaar elders valt, anders bij de sector erboven, anders nergens. Op beide niveaus gekoppeld: Gezondheidszorg, Landbouw en natuurlijke omgeving, Onderwijs, Recht (ook op type: recht), Taal en cultuur en Techniek. Economie koppelt bij de master aan een subsector, bij de bachelor alleen aan de sector (logistiek, horeca en toerisme vallen bij ROA onder dienstverlening). Gedrag en maatschappij koppelt alleen bij de master. Natuur (informatica en kunstmatige intelligentie vallen bij ROA onder techniek en ict) en Sectoroverstijgend koppelen niet. Per niveau staat in het resultaat hoeveel opleidingen elders vallen.
- **Wat de bron niet kan, zegt de tool zelf:** het opleidingstype is alleen landelijk ("opleidingstype alleen landelijk"), ROA splitst niet naar hbo en wo, een ongekoppeld onderdeel houdt alleen de cijfers per niveau, en UWV-vacatures hebben geen opleidingsniveau.
- **Opleidingsnamen koppelen we niet:** er is geen bron die een CROHO-opleiding aan een ROA-opleidingstype hangt.

| Eigenschap | Details |
|------------|---------|
| Toegang | Via DataverseNL (`onderwijsbronnen.roa`, AIS 2030) |
| Inhoud | Schoolverlatersinformatie en arbeidsmarktprognoses per opleidingsniveau, -sector, -subsector en -type (ONR2019) |
| Formaat | Landelijke referentiewaarden; de prognose per niveau, sector en subsector ook per arbeidsmarktregio (35) en provincie (12); het opleidingstype alleen landelijk |

---

## UWV — Uitvoeringsinstituut Werknemersverzekeringen

**UWV-vacaturedata** geeft inzicht in de vraag naar arbeid per sector. In de chat via `get_uwv_vacatures` per provincie of gemeente en onderwijssector; ook ingezet in het arbeidsmarktdashboard. Welke beroepenclusters bij een sector horen, is een indeling van deze app, gemaakt met een taalmodel (`data/sector_cluster_mapping.json`); UWV deelt vacatures niet in onderwijssectoren in. Welk model en welke prompt de huidige indeling maakten, is niet vastgelegd, en de indeling is nog niet gevalideerd: een steekproef van 30 clusters (`docs/sector-cluster-steekproef.csv`, `scripts/steekproef_sector_mapping.py`) wacht op handmatige beoordeling. Een cluster dat het model bij geen sector zette, staat in `_niet_toegewezen`; een test bewaakt dat elk cluster uit de snapshot een plaats heeft (#873). Het resultaat houdt de UWV-aantallen, die indeling (met versie en model) en het gewogen sectorgetal apart. Een beroepencluster dat bij meer sectoren hoort, telt per sector naar rato mee, zodat de sectoren samen nooit meer vacatures hebben dan het totaal. Het arbeidsmarktdashboard telt zo'n cluster op dezelfde manier, in de match score en in de grafiek. UWV legt bij vacatures geen opleidingsniveau vast.

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
- **Hoger onderwijs:** het hoger onderwijs heeft geen oordeel per bestuur. Daar accrediteert de NVAO de opleidingen.
  De accreditatiedatums per opleiding staan in `get_accreditatie` (zie hieronder); de NVAO-oordelen zitten (nog) niet
  in de app.
- **Onderzoekskader:** de standaarden staan per kader in andere kolommen (#874). Onder het kader 2021 (`Kader` =
  `BST2021` of `BST21_V25`) zijn dat BKA1-3, onder het kader 2017 (`BST2017`) KA1-3 en FB1-3 met daarnaast een oordeel
  per kwaliteitsgebied. De namen komen uit de [toelichting open data oordelen en standaarden
  2025/2026](https://www.onderwijsinspectie.nl/documenten/2025/09/02/toelichting-open-data-oordelen-en-standaarden-2025-2026).
  Op 1 oktober 2026 hadden 25 van de 164 mbo-besturen geen kader: oudere onderzoeken, van voor 2021.
- **Bereikbaarheid:** `bron:ping` meet dagelijks of de bron bereikbaar is.

| Eigenschap | Details |
|------------|---------|
| Toegang | onderwijsinspectie.nl, open data (CC0 1.0) |
| Inhoud | Eindoordeel en standaarden per bevoegd gezag |
| Formaat | ODS, maandelijks peilbestand |
| Koppeling | Bestuursnummer = DUO `BEVOEGD GEZAG NUMMER` (adressen_mbo) |

---

## Onderwijsinspectie — oordelen per vo-school (vo-context)

In hetzelfde maandelijkse document staat het peilbestand per school en onderwijssoort voor po, so en vo
(`…-oordeel-en-standaard-po-so-vo.ods`, CC0 1.0 volgens de documentpagina). In de chat via `get_inspectieoordeel_vo`,
alleen als vo-context voor vervolgonderwijs (#881): bij een vraag die de vo-context opent en zelf het vo noemt (zie
[Vo-context voor vervolgonderwijs](#vo-context-voor-vervolgonderwijs)).
- **Per afdeling:** bij vo is het object van toezicht de onderwijssoort op één vestiging (`Elementtype` ODS): het oordeel
  geldt voor bijvoorbeeld de havo-afdeling van die vestiging, niet voor de school als geheel en niet voor het bestuur.
- **Alleen vo:** de tool neemt alleen `Sector` VO met een onderwijssoort, en nooit een speciale school (`TypeOVT` SPEC).
  Po- en so-rijen staan wel in het bestand, maar nooit in het resultaat.
- **Vo-onderdeel van een roc:** 89 vo-afdelingen horen bij een roc (`TypeOVT` ROCV). Het antwoord zegt dan dat het
  oordeel over het vo-deel gaat, niet over het mbo.
- **Plaats en naam uit DUO:** het bestand noemt geen plaats en geen schoolnaam. De koppeling is BRIN + vestigingsnummer
  = DUO `VESTIGINGSCODE` in de adressen van vestigingen in het vo (`adressen_vo`, 1632 vestigingen in 288 gemeenten).
- **Aantallen op 1 november 2026:** 11.093 rijen, waarvan 6615 po, 669 so en 3809 vo. Daarvan zijn 3634
  vo-afdelingen op 1438 vestigingen (978 vmbo-gt, 696 havo, 646 vwo, 570 vmbo-k, 556 vmbo-b, 188 pro).
  - Oordelen: 2512 geen eindoordeel, 850 voldoende, 192 onvoldoende, 47 zeer zwak, 24 goed, 9 basistoezicht.
  - 3620 afdelingen op 1433 vestigingen vinden hun vestiging bij DUO.

**Bekende grenzen:**
- **Geen eindoordeel is de regel.** Bij 69% van de afdelingen staat "Geen eindoordeel": nog niet onderzocht, gefuseerd,
  of het laatste oordeel Voldoende of Goed is ouder dan vier jaar (toelichting, p. 5). Het antwoord noemt dat geen
  onvoldoende.
- **Niet waar studenten vandaan komen.** De bron kent de vo-scholen in een gemeente, niet de scholen waar de studenten
  van een instelling vandaan komen. Het resultaat zegt dat.
- **Geen standaarden.** De standaarden staan per onderzoekskader in andere kolommen (OP0-OP8, SK, VS, OR, SKA, ...), met
  per kader een andere naam. De tool toont alleen het eindoordeel per afdeling.
- **Per gemeente, ten hoogste 25 vestigingen.** Een grote gemeente (Amsterdam: 84 vestigingen met een vo-afdeling) wordt
  afgekapt. De telling per oordeel telt wel alle vestigingen.
- **Niet gekoppeld:** 14 afdelingen van een `TypeOVT` EDUV staan niet in DUO's vestigingen en hebben dus geen gemeente.
  Eén afdeling heet "Overig EOA": die onderwijssoort kent de tool niet. Die komt in het log (`INSPECTIE_VO_ONBEKEND`).
- **Alleen in de chat.** Buiten een beurt (MCP, evals) weigert de tool, want er is geen vraag van een gebruiker.
- **Bereikbaarheid:** `bron:ping` meet het po-so-vo-bestand dagelijks (`inspectie-po-so-vo`, minstens 3000
  vo-afdelingen).

| Eigenschap | Details |
|------------|---------|
| Toegang | onderwijsinspectie.nl, open data (CC0 1.0) |
| Inhoud | (Eind)oordeel per school en onderwijssoort, po, so en vo; de tool leest alleen vo |
| Formaat | ODS, maandelijks peilbestand, in hetzelfde document als het bg-bestand |
| Koppeling | BRIN + Vestiging = DUO `VESTIGINGSCODE` (adressen_vo, vestigingen) |

---

## DUO — indicatoren per mbo-instelling

DUO publiceert elk voorjaar de indicatoren van het geïntegreerd jaardocument mbo
(`…/images/{editie}-indicatoren-per-instelling.xlsx`, vindbaar via
[indicatoren.jsp](https://duo.nl/open_onderwijsdata/middelbaar-beroepsonderwijs/indicatoren/indicatoren.jsp)). In de
chat via `get_mbo_indicatoren`, alleen voor mbo-instellingen (#727).
- **Inhoud:** jaarresultaat, diplomaresultaat en het percentage nieuwe vsv'ers, drie schooljaren, elk naast de waarde
  van de vergelijkingsgroep: alle roc's (ROC) of alle beroepscolleges (BER), een gewogen gemiddelde op
  deelnemersaantallen. De code rondt af op één decimaal en berekent het verschil in procentpunt.
- **Alleen de nieuwste editie:** edities mengen geeft andere cijfers voor hetzelfde schooljaar. DUO herberekent na een
  fusie, en het laatste vsv-jaar is voorlopig (zo gelabeld in het resultaat). Oudere edities (2021 en 2022 als `.xls`,
  met andere vergelijkingsgroepen) leest de app niet.
- **Geen financiën:** de sheet `Financieel` (per bestuur, afgeleid van XBRL) leest de app niet: de financiën per bestuur
  komen uit de verantwoording uit XBRL zelf (hieronder, #935).
- **Geen cijfer:** een lege cel en een exacte 0 zijn "geen cijfer", tot DUO uitsluitsel geeft. In de editie 2026 staat
  0 bij de vsv van Talland College en Drenthe College Terra over 2023/24 en 2024/25.
- **Per instelling:** de cijfers gelden per BRIN, niet per opleiding, vestiging of bestuur. Eén organisatie kan twee
  BRIN's met verschillende vergelijkingsgroepen hebben (Curio: 21CY BER, 25LX ROC); de app telt of middelt nooit over
  BRIN's. De naam komt uit het register, want de namen in het bestand zijn afgekapt.
- **Niet vergelijkbaar met CBS:** het landelijke vsv-cijfer van CBS (85368NED) heeft een andere definitie en populatie.
- **Weigeren in plaats van gokken:** de kolommen komen uit de koppen. Een onbekende kop, sheet, BRIN of
  vergelijkingsgroep, een percentage buiten 0–1, of een groepswaarde die binnen een groep verschilt (verwisselde
  kolommen) geeft een foutmelding zonder cijfers. Een HTML-foutpagina met HTTP 200 (soft 404) ook.
- **Licentie:** CC0 1.0, zoals alle open onderwijsdata van DUO ([de regel](#duo-dienst-uitvoering-onderwijs)); het
  bestand en indicatoren.jsp noemen zelf geen licentie. De bronvermelding noemt DUO en de URL.
- **Bereikbaarheid:** `bron:ping` meet dagelijks of de bron bereikbaar is.

| Eigenschap | Details |
|------------|---------|
| Toegang | duo.nl, open onderwijsdata (CC0) |
| Inhoud | Jaarresultaat, diplomaresultaat en nieuwe vsv'ers per mbo-instelling, met vergelijkingsgroep |
| Formaat | xlsx, één editie per jaar, één keer per dag opgehaald |
| Koppeling | Instellingscode (BRIN) uit het register |

---

## DUO — financiële verantwoording per bestuur (XBRL)

DUO publiceert elk jaar (september/oktober) de jaarrekeningen die de besturen in XBRL aanleveren, per onderdeel als
xlsx op [financiele-verantwoording-uit-xbrl.jsp](https://duo.nl/open_onderwijsdata/onderwijs-algemeen/financiele-overzichten/financiele-verantwoording-uit-xbrl.jsp).
In de chat via `get_bestuursfinancien`; in het pakket `onderwijsbronnen.duo.financien`, in de catalogus als
`duo:financien` (geen CKAN-dataset; `get_duo_data` verwijst naar de tool). Onderzoek en besluit: #725, bouw: #935.
- **Inhoud:** solvabiliteit I en II, liquiditeit (current ratio), rentabiliteit en het totaal van de verantwoorde
  rijksbijdragen, per bestuur en verslagjaar (de laatste vijf; editie 2021-2025, gepubliceerd 15 september 2026).
  Weerstandsvermogen, kapitalisatiefactor en netto werkkapitaal zijn voor mbo, hbo en wo leeg en blijven weg.
- **Alleen mbo, hbo en wo:** besturen die DUO aan po of vo toerekent, laadt de app niet (fail closed, #355). DUO rekent
  een bestuur met meer sectoren toe aan één leidende sector: Aeres Hogeschool hoort bij een bestuur onder mbo.
- **Editie uit de bestandsnaam:** de jaren staan in de naam, dus de app leest de pagina en neemt per onderdeel de
  nieuwste. Een vervallen bestand geeft HTTP 200 met een HTML-pagina (soft 404): dat telt niet als bestand. De
  bestanden staan een dag in de cache en worden daarna met If-Modified-Since opnieuw gevraagd.
- **Variant `standaard`:** geconsolideerd waar het bestuur dat aanleverde, anders enkelvoudig. 13 van de 111 reeksen
  wisselen binnen 2021-2025; het antwoord meldt dat. Varianten worden nooit gemengd of opgeteld.
- **Bestuur 40833** heeft geen eigen rij maar drie verantwoordingen, één per BRIN (`40833-25LR` ROC van Flevoland,
  `40833-25PZ` ROC van Amsterdam, `40833-30RM` ROC TOP). Ze blijven aparte eenheden (`Bestuurssleutel`), ook in het
  sectorcijfer.
- **Sectorcijfer volgens de Inspectie:** gewogen, de som van de teller over alle eenheden van de sector gedeeld door de
  som van de noemer (technisch rapport financiële kwaliteit, Staat van het Onderwijs 2024). Daarvoor leest de app ook
  de balans en de staat van baten en lasten; die posten zelf geeft ze niet. Nagerekend: mbo 2021 liquiditeit 1,58,
  solvabiliteit II 0,64, rentabiliteit 4,05 %, zoals in het rapport. De mediaan uit de verkenning (0,573 voor
  solvabiliteit I in 2025) gebruikt de app niet.
- **Signaleringswaarden van de Inspectie** (zelfde rapport, §3.2.1, vast in de code): solvabiliteit II onder 0,30;
  liquiditeit onder 1,50 (baten onder € 3 mln), 1,00 (tot en met € 12 mln), 0,75 (tot en met € 25 mln) of 0,50
  (daarboven). Geen voor rentabiliteit, en geen voor bovenmatig eigen vermogen (daarvoor ontbreken gegevens).
- **Leeg is geen nul:** een lege cel blijft `null`. Bij de wo-besturen met umc staat de rijksbijdrage voor de
  werkplaatsfunctie apart; het totaal is zonder dat bedrag (nagerekend op alle 90 wo-rijen).
- **Fusies:** XBRL rekent niet om naar het huidige bestuur, de DUO-studentbestanden wel. Een voorganger houdt eigen
  rijen tot zijn laatste verslagjaar; het antwoord meldt een bestuursfusie binnen de reeks uit de RIO-overgangen (#728),
  alleen met voorgangers die zelf als mbo-, hbo- of wo-bestuur in de verantwoording staan.
- **Vaste voorbehouden:** het hele bestuur (ook vo), geen uitspraak over kwaliteit, verslagjaar = boekjaar en niet door
  een accountant gecontroleerd, één variant, een signaal is geen oordeel.
- **Licentie:** CC0 1.0, zoals alle open onderwijsdata van DUO ([de regel](#duo-dienst-uitvoering-onderwijs)); de
  pagina van het bestand noemt zelf geen licentie. Een schriftelijke bevestiging per bestand is er niet. `LICENTIE_BEVESTIGD` in `tools/beschikbaarheid.py` staat daarom op True; op False geeft de tool op playground en
  productie weer alleen een melding, en bepaalt dezelfde regel de status in search_catalog (dan `alleen_catalogus`), de
  suggestievragen op het startscherm en de tellingen (#956).
- **Citaties, telling en export (#956):** elk getal uit de tool krijgt een citatie (ook met decimale komma); de tabel
  achter het resultaat (`financien.overzicht`, onafgerond) staat in de store als `financien:<sleutel>` met dataset
  `duo:financien` en de editie als peilmoment, en is als CSV met inhoudshash te exporteren. De Telling noemt over hoeveel
  eenheden het sectorcijfer gaat en een fusie in de reeks.
- **Bereikbaarheid:** `bron:ping` (`duo-financien`) leest dagelijks de nieuwste editie en telt de eenheden per sector.

| Eigenschap | Details |
|------------|---------|
| Toegang | duo.nl, open onderwijsdata (CC0) |
| Inhoud | Financiële kengetallen en rijksbijdragen per bestuur, met gewogen sectorcijfer en signaleringswaarden |
| Formaat | xlsx, één editie per jaar (vier onderdelen, variant standaard) |
| Koppeling | `Bevoegd Gezag` = DUO `BEVOEGD GEZAG NUMMER` (adressenbestanden) = RIO-bestuurscode (vijf tekens) |

---

## Accreditatie per ho-opleiding — DUO, Overzicht Erkenningen ho

DUO publiceert dagelijks de erkende ho-opleidingen per instelling (`overzicht-erkenningen-ho`, CC0 zoals elke
[DUO-bron](#duo-dienst-uitvoering-onderwijs); CKAN meldt `cc-by`), met de datums
die de NVAO of de minister over de accreditatie vastlegt (toelichting v1.8). In de chat via `get_accreditatie`, per
hbo- of wo-opleiding (#726, stap A).
- **Geen oordeel:** het overzicht bevat geen NVAO-oordeel (voldoende, goed, excellent), geen besluittekst en geen
  rapport. De NVAO publiceert die zelf; of de app ze mag ophalen, wacht op toestemming van de NVAO (#726, stap B).
- **Inleverdatum:** `ACCREDITATIE_INLEVERDATUM` is de uiterste indiening van het visitatierapport voor de volgende
  beoordeling, geen einddatum. De tool noemt hem zo en zegt het erbij.
- **Vervaldatum:** `ACCREDITATIE_VERVALDATUM` geldt alleen voor de termijn van een nieuwe opleiding.
- **Per opleiding:** de datums zeggen niets over kwaliteit; de tool geeft één opleiding per aanroep, geen ranglijst.

| Eigenschap | Details |
|------------|---------|
| Toegang | onderwijsdata.duo.nl, open data (CC0), via het gewone DUO-laadpad |
| Inhoud | Erkenning en accreditatiedatums per instelling en opleiding (CROHO) |
| Formaat | CSV, dagelijks bijgewerkt |
| Koppeling | `INSTELLINGSCODE` = instellingscode uit het register; `ERKENDEOPLEIDINGSCODE` = CROHO, vijf cijfers |

---

## Wettelijk collegegeld — Regeling financiën hoger onderwijs

Het wettelijk collegegeld staat in artikel 9 van de Regeling financiën hoger onderwijs
([BWBR0024005](https://wetten.overheid.nl/BWBR0024005)). De app haalt de wettekst (ruim 700 KB HTML) niet bij elke
vraag op: de bedragen staan in een kleine vaste tabel in `tools/collegegeld.py`, per studiejaar met de wetsversie en
de dag waarop ze zijn nagelezen. In de chat via `get_collegegeld`, één studiejaar per aanroep (#729).
- **Voltijd en deeltijd:** per studiejaar het volledig wettelijk collegegeld (voltijd, artikel 7.45a, derde lid, WHW)
  en het minimum- en maximumbedrag van het gedeeltelijk wettelijk collegegeld (deeltijd en duaal, vierde lid). Het
  bedrag voor deeltijd of duaal kiest de instelling tussen die twee (artikel 7.45, tweede lid); dat bedrag staat niet
  in de wettekst.
- **Nagelezen op 03-11-2026:**

  | Studiejaar | Voltijd | Deeltijd en duaal (min–max) | Versie van de regeling |
  |---|---:|---:|---|
  | 2023/2024 | € 2.314 | € 1.377 – € 2.314 | geldend van 01-09-2024 |
  | 2024/2025 | € 2.530 | € 1.506 – € 2.530 | geldend van 01-09-2025 |
  | 2025/2026 | € 2.601 | € 1.548 – € 2.601 | geldend van 18-09-2026 |
  | 2026/2027 | € 2.694 | € 1.604 – € 2.694 | geldend van 18-09-2026 |
  | 2027/2028 | € 2.771 | € 1.650 – € 2.771 | vastgestelde wijziging, geldend van 01-09-2027 |

- **Verlaagd collegegeld:** tot en met 2023/2024 kon een eerstejaars verlaagd collegegeld betalen (vervallen per
  01-09-2024). Dat bedrag staat niet in de tabel; bij 2023/2024 zegt een noot het.
- **Geen open bron:** het instellingscollegegeld en andere bedragen die een instelling zelf vaststelt, zijn geen open
  data. De tool zegt dat bij elk antwoord, en het model noemt er geen bedrag voor.
- **Bijhouden:** jaarlijks rond 1 september (zie [Promoten naar playground](promoten.md#jaarlijks)). `bron:ping` wordt
  rood zodra het lopende studiejaar niet in de tabel staat.

| Eigenschap | Details |
|------------|---------|
| Toegang | wetten.overheid.nl, de wettekst; geen API, de tabel staat in de repo |
| Inhoud | Wettelijk collegegeld per studiejaar: voltijd, en minimum en maximum voor deeltijd en duaal |
| Formaat | Vaste tabel in `tools/collegegeld.py`, met BWBR-ID, versiedatum en ophaaldatum |
| Koppeling | Studiejaar (startjaar) |

---

## Personeel van de universiteiten — UNL, WOPI (achter een vlag, alleen test)

Universiteiten van Nederland (UNL) publiceert jaarlijks het WOPI-personeelsbestand als xlsx met draaitabellen
([downloadpagina](https://www.universiteitenvannederland.nl/downloadbare-gegevens-personeel)). Het pakket leest het in
`onderwijsbronnen.unl`, de chat via `get_wo_personeel` (#936; onderzoek en besluit op #731). Alleen wo: voor hbo en mbo
bestaat geen open personeelsbestand per instelling, en de tool zegt dat bij zo'n vraag.
- **Achter een vlag:** `ENABLE_WO_PERSONEEL` staat alleen in `manifests/test` aan. UNL zegt niets over hergebruik
  ("De universiteiten zijn eigenaar van deze gegevens"); playground wacht op een schriftelijk ja van UNL. Er staat geen
  data van UNL in de repo: de tests gebruiken een synthetisch bestand met dezelfde XML-vorm
  (`onderwijsbronnen.unl.proefbestand`).
- **Records, geen cellen:** de lader leest de link naar de nieuwste editie van de pagina (de bestandsnaam verschilt per
  editie, `…WOPI_draaitabellen_tm_{jaar}.xlsx`) en daarna de caches van de draaitabellen (`xl/pivotCache`), gekozen op
  de naam van de brontabel, niet op hun nummer. De getoonde cellen tellen de rij "Totaal" bij een kolomsom dubbel
  (116.924 in plaats van 58.462 fte). Elk totaal is een som over de records.
- **Controles:** de velden van elke cache, 14 BRIN-codes in het jongste jaar en het jongste jaar gelijk aan de editie;
  wijkt er iets af, dan geeft de tool een bronfout en geen cijfer. Het bestand gaat door `defusedxml`.
- **GEZO:** standaard zonder het HOOP-gebied Gezondheid (`gezo="excl"`), zodat de reeks vergelijkbaar blijft; met GEZO
  alleen op uitdrukkelijk verzoek, één variant per antwoord, en de variant staat in de bronregel. Met GEZO is vóór 2006
  niet vergelijkbaar (het medische personeel ging over naar de umc's): de tool weigert die jaren.
- **Eenheid:** standaard fte; personen per instelling bestaan alleen per leeftijdsklasse (vanaf 2005). Docent en
  onderzoeker bestaan vanaf 2005, vast en tijdelijk vanaf 2003. "Mannen" leidt de app niet af (totaal min vrouwen).
- **Wat er niet in staat:** inhuur, uitzendkrachten, studentassistenten, gastmedewerkers en umc-personeel; promovendi
  alleen als ze in dienst zijn. Vier wo-instellingen zijn geen lid van UNL (Theologische Universiteit Apeldoorn,
  Protestantse Theologische Universiteit, Universiteit voor Humanistiek, Theologische Universiteit Kampen): voor hen
  een vaste melding, geen 0. HOOP-gebied, salarisgroep en fte per leeftijd zijn (nog) niet ontsloten.
- **Controlewaarden (editie 2025, peildatum 31-12-2025):** Universiteit Utrecht 6.184,36 fte zonder GEZO, waarvan
  3.584,05 wetenschappelijk personeel; landelijk 58.462,07 fte zonder en 61.371,30 met GEZO. Het synthetische
  proefbestand reproduceert ze.

| Eigenschap | Details |
|------------|---------|
| Toegang | universiteitenvannederland.nl, downloadpagina; hergebruik nog niet bevestigd door UNL |
| Inhoud | fte per functiecategorie en vast/tijdelijk (Tabel 1), personen per leeftijdsklasse (Tabel 9), per universiteit |
| Formaat | xlsx met draaitabellen, één editie per jaar (mei tot november); runtime-cache van 24 uur, geen opslag |
| Koppeling | BRIN-code (`brincode` in de caches), via het register van de chat |
| ID | `unl:wopi` in het ID-contract; niet in `catalog(source="all")`. In de zoekcatalogus van de chat alleen met de vlag `ENABLE_WO_PERSONEEL`, als `via_tool` naar `get_wo_personeel` (#956) |
| Citaties en export | elk getal (fte, personen, aandeel) met citatie; de tabel staat in de store als `wopi:<brin>:…` met dataset `unl:wopi`, als CSV met inhoudshash te exporteren; de Telling zegt wat fte en personen tellen (#956) |

---

## Studiekeuzedatabase — Landelijk Centrum Studiekeuze (LCSK; alleen test en playground)

De Studiekeuzedatabase (SKDB) van het Landelijk Centrum Studiekeuze is de data achter Studiekeuze123
([studiekeuzedata raadplegen](https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/)). Het pakket leest haar in `onderwijsbronnen.skdb`,
de chat via `get_studiekeuze` (#957). Alleen hbo en wo: 109 hogescholen en universiteiten (ook niet-bekostigde) en
3.312 opleidingen, waarbij een opleiding één CROHO-code bij één BRIN op één vestiging is; per vorm (voltijd, deeltijd,
duaal) zijn het er ruim 4.400.
- **Alleen met een sleutel:** de API (`https://api.skdb.nl/v1`) vraagt een eigen Bearer-sleutel van LCSK,
  `STUDIEKEUZEDATABASE_API_KEY`. Die staat als secret op test en playground; development en productie hebben hem niet.
  Zonder sleutel staat `get_studiekeuze` niet in de toolset, staat het record niet in de zoekcatalogus, toont het
  startscherm geen studiekeuzevragen en het databronnenvenster geen rij LCSK (`tools/beschikbaarheid.py`, bron
  `studiekeuze`).
- **Dagexport:** de lader haalt in één request `/export/json` op, een ZIP van ongeveer 18 MB met één JSON-bestand per
  tabel (`instellingen`, `opleidingen`, `opleidingvormen`, `studies`, `studievormen`, `standaardonderwijsindelingvorm`,
  `doorstroombachelormaster`, `doorstroommbohbo`, `lotingopleidingendecentraleselecties`). Ontbreekt er
  een tabel, dan is de vorm veranderd en geeft de tool een bronfout, geen cijfer. De bestandsnaam geeft het
  versienummer van de data (`export-skdb-26.6-…`) en de exportdatum; de app laadt de export één keer per 24 uur
  (`core/actualiteit.py`, in het geheugen) en bewaart haar niet op schijf.
- **Jaren uit de export:** het NSE-jaar (`enqueteJaar`) en het 1cijferHO-jaar (`eenCijferHoMeestRecenteJaar`, begin van
  het collegejaar) zijn de hoogste waarde in `opleidingvormen`. De tool noemt ze in de voorbehouden en de bronregel bij
  opleidingen en studies; ze staan niet vast in de code of de catalogus.
- **Inhoud:** per opleiding en vorm het NSE-oordeel (algemeen en tien thema's, schaal 1-5) met het aantal
  respondenten van het algemeen oordeel, doorstroom naar jaar 2 en diplomarendement (door LCSK berekend uit 1cijferHO,
  dat niet openbaar is), numerus fixus met capaciteit (Studielink); per opleiding de wettelijke vooropleidingseisen
  voor havo, vwo en mbo (RATHO); per landelijke studie het ROA-opleidingstype en de arbeidsmarkt van afgestudeerden per
  SOI-rubriek (mediaan salaris, werkloosheid, baan op niveau; CBS-microdata en NAE/HBO-monitor); de doorstroom van
  mbo-4-kwalificaties naar hbo-studies en van bachelors naar masters.
- **Andere bron leidend (afspraken #878):** wat SKDB overneemt van een bron die de chat al heeft, toont de chat uit
  die bron, niet uit SKDB. Aantallen studenten en eerstejaars komen uit DUO (SKDB telt een andere populatie), het
  wettelijk collegegeld uit `get_collegegeld`, de accreditatie uit `get_accreditatie` en de aansluiting studie-baan uit
  ROA-AIS (de chat heeft een nieuwere editie). Van AIS neemt de tool alleen de koppeling studie → ROA-opleidingstype
  over (`roa_opleidingstype`), de sleutel naar de ROA-cijfers.
- **Wat er niet in staat:** mbo-opleidingen (van het mbo alleen waar mbo-4-gediplomeerden in het hbo naartoe gaan);
  een vraag over een mbo-instelling krijgt een vaste melding. Reeksen: de export is de stand van nu, één NSE-jaar en
  één 1cijferHO-jaar. Het aantal respondenten per NSE-thema: alleen het algemeen oordeel heeft een aantal; bij een
  thema noemt de chat dat aantal, met de zin dat het aantal per thema onbekend is. Arbeidsmarktcijfers bestaan alleen
  voor voltijd hbo-bachelor, associate degree en wo-master, gaan over een SOI-rubriek, niet over één studie, en vormen
  geen reeks met CBS StatLine.
- **Koppelen:** `brin` is de instellingscode van RIO en DUO, `croho` de opleidingscode van RIO en DUO; daarmee vind je
  dezelfde opleiding in de DUO-bestanden en in RIO. `studiecode` is de landelijke studie van LCSK: meestal gelijk aan
  de CROHO-code, maar niet altijd (samengevoegde studies). Koppel daarom op `croho`, niet op `studiecode`. `brin` en
  `croho` zijn canonieke sleutels van `onderwijsbronnen.sleutels` (#958): het catalogusrecord noemt ze als
  `koppelbaar_via`, en `relatie` noemt een SKDB-tabel en een DUO-tabel zo als koppelkandidaten.
- **Schema en wat de chat ermee kan (#978):** de export beschrijft zichzelf in `exporttabellen` (45 tabellen) en
  `exportkolommen` (639 kolommen). `onderwijsbronnen.skdb.schema` bouwt daaruit per tabel de omschrijving, de kolommen
  met type, de korrel (de parameters van het endpoint, zoals instelling × vestiging × product bij `tracks`), de
  relaties (tabellen waarvan de korrel in deze tabel staat), de jaarkolommen, de editie (versie, exportdatum, NSE- en
  1cijferHO-jaar) en wat een leeg veld betekent (niet gevuld, nooit 0). Per tabel staat erbij wat de chat ermee kan:
  een weergave van `get_studiekeuze` (de negen tabellen van de zes weergaven), alleen in het pakket leesbaar
  (`skdb.load`, zoals `tracks`, `studieadvies` en `opendagen`), of bewust niet in de chat omdat een andere bron
  leidend is (`collegegelden`: de wettekst; `cijfersopleidingniveauland`: CBS StatLine). Kolommen die de chat volgens
  de afspraken hierboven niet toont (aantallen studenten en eerstejaars, accreditatiedatums, wettelijk collegegeld,
  aansluiting studie-baan, loon uit CBS-microdata) staan in het schema met de leidende bron in plaats van hun
  omschrijving. `search_catalog` vindt de bron op een tabelnaam ("tracks", "studieadvies") en op "skdb", en noemt de
  geraakte tabel met wat er kan; `dataset_details("skdb:studiekeuzedatabase")` geeft het overzicht van de tabellen,
  `dataset_details("skdb:studiekeuzedatabase/<tabel>")` het schema van één tabel, met de sleutels naar andere bronnen
  uit de connectoren van `relatie` (`instellingCode` = BRIN, `opleidingCode` = CROHO, `gemeenteCode`).
  *Licentie:* de omschrijvingen zijn het gegevenswoordenboek van LCSK (art. 11.1, databankrechten) en de repo wordt
  publiek gespiegeld. Daarom staan alleen de tabelnamen in de code (zoals de veldnamen in de proefexport, het voorstel
  in #878 "ja voor alleen veldnamen", waarop LCSK nog moet antwoorden); omschrijvingen, kolommen en types komen alleen
  uit de export van vandaag, in het geheugen, en gaan niet naar de catalogussite. Zoeken downloadt daarom niets; pas
  `dataset_details` haalt de export op (dezelfde lading als `get_studiekeuze`). Zoeken op een kolomnaam of een woord uit
  een omschrijving kan zo niet.
- **Licentie:** de [Algemene Leveringsvoorwaarden Data van LCSK, versie 25.1](https://lcsk.nl/over-ons/leveringsvoorwaarden/).
  - *Bronvermelding (art. 4.1 en 4.2):* bij elke uiting die op de data steunt de zin "Er is gebruik gemaakt van de data
    van Landelijk Centrum Studiekeuze.", met een link naar
    [lcsk.nl/over-ons/studiekeuzedata-raadplegen](https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/), het
    versienummer van de data en bij NSE-cijfers "NSE {jaar}". De bronregel onder elk antwoord met de tool bevat dat
    alles, plus de oorspronkelijke bron van de weergave (zie [Bronnen onder een antwoord](#bronnen-onder-een-antwoord)).
  - *Melding bij publicatie (art. 4.6):* binnen drie weken na publicatie een link of pdf naar info@lcsk.nl; een actie
    bij livegang op playground.
  - *Geen indruk van samenwerking (art. 4.5):* de app wekt niet de indruk dat LCSK haar steunt of eraan meewerkt.
  - *Geen doorlevering:* er staat geen data van LCSK in de repo en het pakket levert er geen mee. De tests gebruiken
    een synthetische export met dezelfde vorm (`onderwijsbronnen.skdb.proefbestand`, verzonnen getallen). Een snippet
    haalt de export zelf op, met de eigen sleutel van wie hem draait.
  - *Publieke verantwoording bij selectie en ranking (art. 5):* zie hieronder.

### Verantwoording: hoe de app selecteert, sorteert en afrondt

Artikel 5 van de leveringsvoorwaarden vraagt dat wie uit de data een selectie of rangorde maakt, publiek uitlegt hoe.
Dit is die uitleg voor `get_studiekeuze` (`tools/studiekeuze.py`, rekenen in `onderwijsbronnen.skdb.overzicht`). Het
taalmodel kiest alleen de weergave en de filters uit de vraag; selecteren, sorteren, afronden en het landelijke oordeel
doet de code, en het model neemt de getallen letterlijk over.

- **Selectie:** een opleiding komt in de uitkomst als ze aan alle opgegeven filters voldoet: instelling (BRIN-code;
  een naam wordt een BRIN via de export of het register van de chat), opleiding (CROHO-code, of een deel van de naam
  van de opleiding), hbo of wo, graad, vorm, plaats van het bezoekadres en "alleen met numerus fixus". Passen er meer
  instellingen of landelijke studies bij een naam, dan kiest de gebruiker; de app gokt niet. Zonder instelling,
  opleiding, plaats of numerus fixus geeft de weergave `opleidingen` geen lijst (te veel om zinnig te tonen). Er wordt
  geen opleiding weggelaten om haar cijfers, en er wordt niets geschat of aangevuld.
- **Volgorde:** standaard alfabetisch op instelling, opleiding, plaats en vorm: geen rangorde. Alleen als de vraag
  erom vraagt, sorteert de tool aflopend op één cijfer: het NSE-oordeel of de doorstroom naar jaar 2. Opleidingen zonder dat cijfer komen achteraan, gelijke waarden op naam. Elke rangorde
  krijgt het vaste voorbehoud dat het een rangorde op één cijfer is, dat het aantal respondenten erbij hoort, en dat
  het geen oordeel over de kwaliteit van een opleiding is. De app maakt geen samengestelde score en geen top-lijst
  over meer cijfers.
- **Toelating:** de weergave `toelating` geeft per opleiding (CROHO-code) de wettelijke vooropleidingseisen zoals LCSK
  ze uit de regeling (RATHO) overneemt, één rij per gelijke set eisen met de instellingen die haar noemen: meestal één
  rij per opleiding, twee als één instelling andere eisen noemt. Ze vraagt een opleiding of een instelling. Op naam
  van de opleiding, zonder rangorde. Een
  instelling kan meer vragen (selectie, numerus fixus, deficiënties); de tool zegt dat erbij.
- **Doorstroom:** de rang (1 is de grootste stroom) is die van LCSK; de app rekent hem niet opnieuw uit. Het aandeel
  is van alle gediplomeerden van de mbo-opleiding of bachelor, niet van wie doorstroomt.
- **Afronding:** NSE-oordelen op twee decimalen, percentages op één decimaal, aantallen en bedragen zoals LCSK ze
  levert. Een leeg veld blijft leeg: de app noemt dan geen getal, ook geen 0. Numerus fixus is de capaciteit van het
  nieuwste studiejaar, opgeteld over de taaltrajecten van dezelfde opleiding en vorm.
- **Landelijk oordeel:** naast het NSE-oordeel van een opleiding staat `nse_oordeel_landelijk`, het oordeel over
  dezelfde landelijke studie in dezelfde vorm over alle instellingen samen, zoals LCSK het berekent (tabel
  `studievormen`). Het is geen gemiddelde van de getoonde rijen.
- **Onzekerheid:** het antwoord noemt het aantal respondenten. Een oordeel op minder dan 30 respondenten markeert de
  code zelf als onzeker (`nse_onzeker`), en een verschil van een paar honderdsten heet geen verschil.
- **Omvang:** het toolresultaat toont hooguit 15 rijen (de thema's van de NSE alleen bij hooguit 3) en zegt hoeveel er
  zijn; de hele selectie staat in de store (`skdb:<weergave>:…`, dataset `skdb:studiekeuzedatabase`).
- **Dashboard Opleidingen:** dezelfde rijen per opleiding van één instelling, op naam en zonder rangorde; wat het toont
  en zijn eigen verantwoording staan in [Dashboards](dashboards.md#opleidingen-studiekeuzedatabase).

| Eigenschap | Details |
|------------|---------|
| Toegang | api.skdb.nl, Bearer-sleutel van LCSK (`STUDIEKEUZEDATABASE_API_KEY`); alleen test en playground |
| Inhoud | NSE, doorstroom, rendement, numerus fixus per hbo- en wo-opleiding en vorm; vooropleidingseisen (RATHO) per opleiding; ROA-opleidingstype en arbeidsmarkt per SOI-rubriek; doorstroom mbo-hbo en bachelor-master. Niet: aantallen studenten en eerstejaars (DUO), collegegeld, accreditatie, aansluiting studie-baan (ROA) |
| Formaat | dagelijkse JSON-export als ZIP (`/export/json`, ongeveer 18 MB); runtime-cache van 24 uur, geen opslag |
| Koppeling | `brin` = BRIN-code van RIO en DUO, `croho` = CROHO-code; `studiecode` is van LCSK en niet altijd een CROHO-code |
| Licentie | Algemene Leveringsvoorwaarden Data van LCSK (v25.1): verplichte bronvermelding met link, versie en NSE-jaar, melding binnen drie weken na publicatie, geen doorlevering, publieke verantwoording bij selectie en ranking (hierboven) |
| ID | `skdb:studiekeuzedatabase`; in de zoekcatalogus van de chat alleen waar de sleutel staat, als `via_tool` naar `get_studiekeuze`. Het schema van één tabel: `skdb:studiekeuzedatabase/<tabel>` in `dataset_details` (#978) |

---

## ID's: één contract `bron:id`

Elke dataset heeft één getypeerde sleutel `bron:id`, bijvoorbeeld `cbs:85423NED`, `duo:p01hoinges`,
`rio:aangeboden-opleidingen` of `roa:ais2030` (#912, [ADR-010](architecture-decisions.md)). Het pakket
`onderwijsbronnen` normaliseert elke vorm naar die sleutel (`parse_bron_id`, `normaliseer_bron_id`): met of zonder
voorvoegsel (`cbs:`, `cbs_`, `rio/`, `duo:`), in elke hoofdletterspelling, en in de spelling van de catalogus (CBS
schrijft `85423NED` naast `80040ned`). Een kale ID die bij twee bronnen past, is een fout met de opties, nooit een
stille keuze; een test bewaakt dat geen ID in twee bronnen voorkomt. Alle vormen die in opgeslagen recepten en
gesprekken staan (de nulmeting van #909, `tests/fixtures/bron_id_vormen.json`), blijven geldig.

De chat gebruikt alleen dit contract, via `tools/bron_ids.py`; de vlag `BRON_ID_CONTRACT` en de oude herleiding
zijn weg sinds #914. Het model ziet de ID's zoals voorheen: zonder voorvoegsel, en `search_catalog` kent nog
`source="riodata"` (een waarde die het model kiest; wijzigen vraagt eerst een eval).

## Bronnen onder een antwoord

Onder een antwoord met data staat het blok **Bronnen**: elke dataset die de beurt las, één keer, met titel, periode en dataset-ID. De lijst komt uit de stappen van de beurt, niet uit de tekst van het model.

Een CBS-regel eindigt met de dag waarop CBS de tabel het laatst bijwerkte en de dag waarop de app hem ophaalde: "…, bijgewerkt door CBS op 20-10-2026, opgehaald op 02-11-2026" (#864). De eerste datum vraagt de app bij het laden live aan CBS (`TableInfos.Modified`), met de catalogus als terugval. Een opgehaalde tabel en de CBS-metadata gelden 24 uur; daarna haalt een gesprek dat ze nog gebruikt ze opnieuw op.

Elke regel is een link naar de bronpagina van die dataset (#621), die in een nieuw tabblad opent. Het is dezelfde link als onder een grafiek in een rapport: voor CBS de StatLine-tabelpagina (#638), voor de andere bronnen de documentatie-URL uit de catalogus. Op een telefoon is de hele regel aan te tikken.

| Bron | Link naar |
|------|-----------|
| CBS | de tabelpagina op StatLine, bijv. `https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table` (niet de OData-JSON; het ID in de spelling van de catalogus) |
| DUO | de datasetpagina in de DUO-portal, bijv. `https://onderwijsdata.duo.nl/datasets/p01hoinges`; onder een rapportgrafiek de pagina van het geladen bestand (`…/datasets/p01hoinges/resources/<resource-id>`, #737) |
| RIO | het register in de RIO-API, ook bij een opzoeking per instelling (`erkenningen`) |
| UWV | UWV Open Match op data.overheid.nl |
| ROA | de dataset AIS 2030 (DOI) |
| Onderwijsinspectie (bg en po-so-vo), DUO-indicatoren mbo | het gelezen bestand zelf (#749, #881, #727) |
| Wettelijk collegegeld | artikel 9 in de versie van de regeling op wetten.overheid.nl (#729) |
| UNL, WOPI | de downloadpagina van UNL; de regel is vast: "WOPI {jaar}, Universiteiten van Nederland, peildatum 31-12-{jaar}, excl. sector Gezondheid" (of incl., #936) |
| LCSK, Studiekeuzedatabase | de pagina [studiekeuzedata raadplegen](https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/) van LCSK; de regel is vast: "Studiekeuzedatabase {versie} ({herkomst}), Landelijk Centrum Studiekeuze, export van {datum}. Er is gebruik gemaakt van de data van Landelijk Centrum Studiekeuze.", met als herkomst per weergave het NSE-jaar en de oorspronkelijke bron, bijv. "NSE 2026; studieverloop uit 1cijferHO 2025, bewerkt door LCSK" (verplicht volgens de leveringsvoorwaarden, #957, #878) |

Een regel heeft bewust geen link:

- **De catalogus kent de dataset niet, of heeft er geen http(s)-adres voor.** De app gokt geen link; de regel blijft tekst. Alleen een `http://`- of `https://`-adres wordt een link, op de server en nog eens in de browser.
- **Het antwoord is van vóór deze wijziging.** Een eerder bewaard gesprek toont zijn bronnen als tekst; de links worden niet achteraf toegevoegd.

Kopiëren en de gespreksexport geven de bronnen als tekst, zoals voorheen.

---

## Catalogus doorzoeken

De assistent kan de catalogus van CBS, RIO, DUO, ROA en UWV doorzoeken met `search_catalog`; UWV- en ROA-treffers (AIS 2030) noemen de tool waarmee ze op te vragen zijn; oudere ROA-edities zijn gemarkeerd als niet via de chat op te vragen. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
