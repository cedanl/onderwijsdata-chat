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
| Pakket | `onderwijsdata`, in deze repo onder `packages/onderwijsdata`; de versie staat in `/version` onder `catalogus`, met de commit waaruit hij komt (#888) |
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
| Pakket | `riodata`, in deze repo onder `packages/riodata`; de versie staat in `/version` onder `catalogus`, met de commit waaruit hij komt (#888) |
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

- **Pakket:** `riodata.opvolgers(brin, peildatum)` en `riodata.voorgangers(brin, sinds)` volgen de overgangen, ook door
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

**Categorieën:**

| Categorie | Voorbeelden |
|-----------|------------|
| Prognoses | Studentprognoses MBO, HO |
| Diplomering | Geslaagden per opleiding, sector |
| Instroom | Eerstejaars inschrijvingen |
| Adressen | Vestigingsadressen instellingen |

**Regio en nevenlocaties (mbo, #744):** adressen en studentaantallen bestaan bij DUO alleen per instelling (BRIN), met
de plaats van de hoofdvestiging. Een regionaal roc dat alleen een nevenlocatie in de regio heeft, valt daar niet onder:
Zone.college (31JC) heeft zijn hoofdvestiging in Lochem en `mbo_opleidingsaanbod` noemt 22 opleidingen in Doetinchem,
waar het Graafschap College (24ZZ) staat. Zone.college is dus geen vestiging van het Graafschap College. Het aanbod kent
de plaats per onderwijslocatie (`PLAATSNAAM`, aanbieder in `NAAM`), maar geen BRIN, en de aanbieders zijn onderdelen
(`Graafschap College, Zorg, Welzijn & Sport`): de code koppelt het niet aan de studentaantallen (dat is het BRIN-register
van #728). Het model krijgt dit mee in de definitie van `PROVINCIE INSTELLING`, in het instellingsprofiel en in de
systeemprompt, en moet melden dat aantallen per instelling gelden en niet per locatie in de regio. Het dashboard
"mijn instelling" kiest zijn peers nog op het adres van de hoofdvestiging.

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

- **Alleen bij een vraag over vervolgonderwijs.** De zoekfunctie toont deze tien alleen als de vraag van de gebruiker het hoger onderwijs noemt (hbo, wo, ho, hoger onderwijs, hogeschool, universiteit), of een vo-niveau (vmbo, havo, vwo, vo, vavo, voortgezet onderwijs, middelbare school, havisten) samen met het mbo of een doorstroomwoord (doorstroom, stromen door, uitstroom, vervolgonderwijs, vervolgopleiding, na het examen, na hun diploma), of voortijdig schoolverlaters die terugkeren in het onderwijs. Code beslist dat (`ho_markers.opent_vo_context`), op de vraag van de gebruiker (bij een keuze op een verduidelijkingsvraag samen met de vraag die ze afbakent), niet op de zoekterm die het model meegeeft. Buiten de chat (MCP) is er geen gebruikersvraag en beslist de zoekterm. Zie [`search_catalog`](tools.md#search_catalog).
- **Voorbeelden.** Wel: "Hoeveel vmbo-leerlingen stromen door naar het mbo?", "Waar gaan havo-leerlingen heen na hun diploma?", "Hoeveel voortijdig schoolverlaters keren terug in het onderwijs?". Niet: "Hoeveel leerlingen zitten er op het vwo in Utrecht?" (een losse vo-vraag krijgt de vaste scope-uitleg) en "Hoeveel mbo-studenten per instelling?" (het mbo zonder vo-niveau).
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

| Eigenschap | Details |
|------------|---------|
| Toegang | Via CBS Open Data |
| Inhoud | Doorstroompercentages, match scores per opleidingssector |
| Formaat | Landelijke referentiewaarden; de prognose ook per arbeidsmarktregio (35) en provincie (12) |

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
- **Geen financiën:** de sheet `Financieel` (per bestuur, afgeleid van XBRL) leest de app niet; die hoort bij #725.
- **Geen cijfer:** een lege cel en een exacte 0 zijn "geen cijfer", tot DUO uitsluitsel geeft. In de editie 2026 staat
  0 bij de vsv van Talland College en Drenthe College Terra over 2023/24 en 2024/25.
- **Per instelling:** de cijfers gelden per BRIN, niet per opleiding, vestiging of bestuur. Eén organisatie kan twee
  BRIN's met verschillende vergelijkingsgroepen hebben (Curio: 21CY BER, 25LX ROC); de app telt of middelt nooit over
  BRIN's. De naam komt uit het register, want de namen in het bestand zijn afgekapt.
- **Niet vergelijkbaar met CBS:** het landelijke vsv-cijfer van CBS (85368NED) heeft een andere definitie en populatie.
- **Weigeren in plaats van gokken:** de kolommen komen uit de koppen. Een onbekende kop, sheet, BRIN of
  vergelijkingsgroep, een percentage buiten 0–1, of een groepswaarde die binnen een groep verschilt (verwisselde
  kolommen) geeft een foutmelding zonder cijfers. Een HTML-foutpagina met HTTP 200 (soft 404) ook.
- **Licentie:** DUO vermeldt geen licentie bij dit bestand; navraag loopt. De bronvermelding noemt DUO en de URL.
- **Bereikbaarheid:** `bron:ping` meet dagelijks of de bron bereikbaar is.

| Eigenschap | Details |
|------------|---------|
| Toegang | duo.nl, open onderwijsdata (licentie nog niet bevestigd) |
| Inhoud | Jaarresultaat, diplomaresultaat en nieuwe vsv'ers per mbo-instelling, met vergelijkingsgroep |
| Formaat | xlsx, één editie per jaar, één keer per dag opgehaald |
| Koppeling | Instellingscode (BRIN) uit het register |

---

## Accreditatie per ho-opleiding — DUO, Overzicht Erkenningen ho

DUO publiceert dagelijks de erkende ho-opleidingen per instelling (`overzicht-erkenningen-ho`, CC-BY), met de datums
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
| Toegang | onderwijsdata.duo.nl, open data (CC-BY), via het gewone DUO-laadpad |
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

Een regel heeft bewust geen link:

- **De catalogus kent de dataset niet, of heeft er geen http(s)-adres voor.** De app gokt geen link; de regel blijft tekst. Alleen een `http://`- of `https://`-adres wordt een link, op de server en nog eens in de browser.
- **Het antwoord is van vóór deze wijziging.** Een eerder bewaard gesprek toont zijn bronnen als tekst; de links worden niet achteraf toegevoegd.

Kopiëren en de gespreksexport geven de bronnen als tekst, zoals voorheen.

---

## Catalogus doorzoeken

De assistent kan de catalogus van CBS, RIO, DUO, ROA en UWV doorzoeken met `search_catalog`; UWV- en ROA-treffers (AIS 2030) noemen de tool waarmee ze op te vragen zijn; oudere ROA-edities zijn gemarkeerd als niet via de chat op te vragen. Gebruik dit als je niet zeker weet welke dataset je nodig hebt:

> *"Welke datasets zijn beschikbaar over zij-instroom?"*

> *"Zoek naar datasets over onderwijspersoneel."*
