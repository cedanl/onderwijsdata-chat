# Dashboards

De app heeft drie vaste dashboards per onderwijsinstelling (Mijn instelling, Arbeidsmarkt en Landelijk) op de pagina
`/dashboards`. De LLM-gestuurde dashboardbouwer is verwijderd (#765); een analyse delen gaat met een rapport.

---

## Vaste dashboards

De frontend toont drie dashboards; ze halen hun cijfers uit de eindpunten hieronder. Beide zijn er zolang `ENABLE_DASHBOARDS`
op `true` staat (standaard uit in de code, #765; op test en playground staat hij aan, op productie uit).

| Dashboard in de UI | Eindpunten | Inhoud |
|--------------------|------------|--------|
| **Mijn instelling** | `/api/dashboard/regio`, `/api/dashboard/rendement`, `/api/dashboard/financien`, `/api/dashboard/personeel` | Kerncijfers, ingeschrevenen, sectoren, eerstejaars, gediplomeerden, bij ho geslacht, de regionale vergelijking en de kaart; mbo: leerwegen en ingeschrevenen per hoofdgroep, en diploma's na 3 jaar per eerstejaars; hbo en wo: een noot waarom daar geen rendement staat; de financiën van het bestuur; wo met `ENABLE_WO_PERSONEEL`: het personeel uit WOPI |
| **Arbeidsmarkt** | `/api/dashboard/arbeidsmarktmatch`, `/api/dashboard/regio` | Gediplomeerden tegen vacatures per sector, de matchscore, ROA (schoolverlaters en prognoses per opleidingsniveau) en de vacatures in de provincie |
| **Landelijk** | `/api/dashboard/nationaal` | Positie per sector, marktaandeel, trend van de eigen sectoren en de ranking van alle instellingen van hetzelfde type |

**Bronnen.** De dashboards rekenen met DUO (open onderwijsdata per instelling, en de financiële verantwoording per
bestuur), UWV (vacatures per provincie, een momentopname van mei 2023), ROA (schoolverlaters en prognoses, landelijk per
opleidingsniveau) en, alleen met `ENABLE_WO_PERSONEEL`, WOPI van Universiteiten van Nederland (personeel per
universiteit). CBS-data gebruiken
ze niet; alleen de indeling in arbeidsmarktregio's (per gemeente) komt van CBS. Over de landelijke CBS-maat van de chat:
zie "Landelijk, groei en het regiogemiddelde" hieronder.

**Frontend.** De dashboards staan in `frontend/src/components/dashboards/` (een map per dashboard, gedeelde delen in
`shared/`) en tekenen met Chart.js (`react-chartjs-2`); alleen de kaart is een Plotly-figuur die de backend bouwt.
`WorkbookViewer` laadt ze lazy, zodat de rapportenroute Chart.js niet meelaadt (#907). Een klik op de legenda volgt
de standaard van Chart.js. Een liggende staaf noemt elke categorie op de as: `categorieTicks` in `shared/chart-opts.js`
zet `autoSkip` uit voor elke liggende staaf, `labelRegels` breekt een lang label af in regels (ook een woord dat
langer is dan de as, met een streepje) en `staafHoogte` geeft elke categorie de ruimte voor haar regels (#951; eerder
sloeg Chart.js bij veel categorieën elk tweede label over, en viel op 390 px de voorkant van een lang woord weg). De tests staan in `frontend/src/__tests__/dashboard*.test.js` (bouwfuncties, legenda,
laden, lege en mislukte lading, cijfers, toegankelijkheid) en voor de backend in `tests/test_dashboard_*.py` en
`tests/test_instellingen.py`.

Elk dashboard ontvangt een `instelling` query-parameter en retourneert JSON met figuren, data en bronvermeldingen
(`bronnen`, zie hieronder). De data komt uit `data/dashboard.py`.
`/api/dashboard/instroom` is weg (#930): geen dashboard gebruikte het, en wat het gaf, staat ook in `regio`. Het pad
geeft 410 met die uitleg; elk ander pad onder `/api/dashboard/` of `/api/dashboards` geeft 404 met de eindpunten
erin, geen kale 404 (#954, `routes/instellingen.py`). `tests/test_openbare_oppervlakte.py` houdt de eindpunten in de
API, in `docs/api.md`, in deze pagina en in de hooks van de frontend gelijk.

### Waarop `instelling` zoekt

De parameter is een van deze sleutels, exact en hoofdletterongevoelig (`resolve_alias` in `data/instellingen.py`):

- de naam uit het register (`/api/instellingen`), ook met "de" of "het" ervoor;
- een afkorting uit `ALIASSEN` of een SRAM-naam ("HU", "VU", "ROC MN");
- een instellingscode (BRIN) uit DUO, zoals `25DW` of `21cy`. Heeft een instelling er meer (Curio: 21CY en 25LX), dan
  staan ze alle in `instellingscodes` van het register en vindt elke code de instelling (#929). Een naam of afkorting
  die zo heet als een code, gaat voor.

Het antwoord noemt in `instelling` de registernaam. Is de instelling onbekend, dan is `gevonden` `false`. Bij
`/api/dashboard/regio` staan dan in `beschikbare_instellingen` de vijf namen die erop lijken; lijkt er geen op, dan is
die lijst leeg en zegt `geen_suggesties` waarop te zoeken (#901, #929). Een bron die niet laadde, geeft 503, geen
`gevonden: false`.

### Bronvermeldingen: het bronblok

Een gevonden instelling krijgt in elke payload `bronnen`: per gebruikte bron één regel (#904, `data/bronblok.py`).
De footer, de bronbadge en de ROA-teksten bij de grafieken tonen dit blok; de frontend heeft geen vaste bronlijst.

```json
{
  "bron": "DUO",
  "dataset": "gediplomeerde-mbo-studenten",
  "titel": "Gediplomeerde mbo-studenten",
  "url": "https://onderwijsdata.duo.nl/dataset/gediplomeerde-mbo-studenten",
  "bestanden": [{"resource": 0, "resource_id": "…", "last_modified": "2026-04-08T03:04:43"}],
  "editie": null,
  "last_modified": "2026-04-08T03:04:43",
  "peilmoment": "versie van 08-04-2026",
  "peildatum": "1 oktober van het studiejaar",
  "voorlopig": true,
  "voorlopig_jaren": ["2025"],
  "opgehaald_op": "2026-11-05T09:30:00+00:00"
}
```

- **Wat erin staat:** wat de lading echt laadde. Elke lader meldt een bestand dat hij met succes laadde
  (`core/brongebruik.py`); `actualiteit.Lading` meldt die bestanden ook bij een cachetreffer opnieuw. Een bron die niet
  laadde, staat er niet in, wel in `niet_beschikbaar`. De ho-poging van een mbo-instelling (de naam zoeken in
  `p01hoinges`) telt niet mee.
- **DUO:** per bestand het resource-ID en `last_modified` uit `onderwijsbronnen.duo` (#717); `peilmoment` in de woorden van de
  bronregel in de chat. `peildatum` en `voorlopig_jaren` komen uit de DUO-beschrijving in de catalogus.
- **UWV:** de momentopname van mei 2023; `peildatum` uit de kolom PEILDATUM.
- **ROA:** `editie` uit het schema van `onderwijsbronnen.roa`, `versie` uit de kolom `versie` van het bestand.
- **DUO-financiën en WOPI** (#935, #936): één editie per lading, geen versie per bestand. De lader meldt `editie`
  ("verslagjaren 2021-2025", "2025"), `peildatum` en bij de financiën de publicatiedatum als versie; WOPI noemt titel en
  link zelf, want de catalogus kent het niet. Dataset-ID `financien` (de CKAN-naam, zoals de andere DUO-regels) en
  `unl:wopi`, bron `DUO` en `UNL`.
- `/api/dashboard/regio` dient Mijn instelling (de DUO-regels) en Arbeidsmarkt (UWV en ROA): elk dashboard neemt er zijn
  eigen deel uit, zoals bij `niet_beschikbaar`.

### Jaren en getalnotatie

De reeksen hebben jaartallen als sleutel (`{2025: n}`); een gevonden instelling krijgt in elke payload `perioden` erbij:
welk soort jaar elke reeks heeft (#904, `PERIODEN` in `data/dashboard.py`).

```json
{"ingeschrevenen": "schooljaar", "eerstejaars": "schooljaar", "cohorten": "schooljaar", "gediplomeerden": "diplomajaar"}
```

- **Schooljaar:** ingeschrevenen en eerstejaars (ho `STUDIEJAAR`, mbo `JAAR`, peildatum 1 oktober) en de cohorten van
  het rendement (het jaar van de eerstejaars). De frontend schrijft ze als "2025/26", zoals chat en rapport (#847).
  Geslacht, sectoren, leerwegen, hoofdgroepen en Landelijk volgen de ingeschrevenen.
- **Diplomajaar:** de gediplomeerden (ho `DIPLOMAJAAR`, mbo de `DIP…`-kolommen). DUO legt niet vast of dat een kalender-
  of studiejaar is, dus het blijft een jaartal: "diplomajaar 2024" (CH-41, domeinregel `p04-diplomajaar`,
  `tools/periode.GEEN_SCHOOLJAAR`). De ratio diploma/inschrijving en de rendementvergelijking delen een diplomajaar door
  een schooljaar met hetzelfde jaartal (#927) en noemen beide.

Alle getallen gaan door één formatter, `fmt` in `frontend/src/components/dashboards/shared/getal.js`: komma als
decimaalteken, punt als duizendtal, in tegels, tabellen, tooltips en de callbacks van de assen. Een aandeel vrouw staat
met `fmtProcent` altijd op één decimaal ("32,0%" naast "67,2%", #951). Een sector heet bij zijn naam uit
`SECTOR_LABELS` ("Gedrag & Maatschappij"), ook in de genderbalken, de ondergrensnoot en het UWV-blok; de leerwegen op
Landelijk heten zoals op Mijn instelling ("BOL voltijd", "Extraneus"), niet naar hun DUO-kolom (`_mbo_per_leerweg`). Chart.js zelf staat op
`nl-NL` voor de ticks zonder eigen callback.

### Wat de getallen tellen

- **Mbo per leerweg** (`sectoren`, `leerwegen`): BBL, BOL voltijd, BOL deeltijd en Extraneus uit
  `mbo-studenten-per-instelling`. Samen zijn ze het totaal ingeschrevenen (#899).
- **Mbo per hoofdgroep** (`ingeschrevenen_per_hoofdgroep`): `TOTAAL MBO` uit het hoofdgroep-bestand van het laatste
  jaar van `instromende-mbo-studenten`, met dat jaar in `ingeschrevenen_per_hoofdgroep_jaar` (het bestand heeft geen
  `JAAR`-kolom; tot #934 was het stil het bestand van 2021). Dat zijn ingeschrevenen, nieuw of niet, geen eerstejaars
  (domeinregel `mbo-instroom-totaal-mbo` in `data/domeinregels.toml`). Het is een ander DUO-bestand dan dat van het
  totaal, dus de som wijkt daarvan af.
- **Aanbod in de arbeidsmarktmatch** (`gediplomeerden_per_sector`): gediplomeerden per sector, gemiddeld over de
  laatste drie diplomajaren: per ho-onderdeel uit `p04hogdipl`, per mbo-hoofdgroep uit `gediplomeerde-mbo-studenten`.
  Tot #899 stond voor het mbo `TOTAAL MBO` (ingeschrevenen) in dit veld.
- **Matchscore** (`match_score`): per sector het aandeel in de gewogen vacatures (`vacatures_per_sector`) tegenover het
  aandeel in de gediplomeerden, beide binnen de sectoren van de instelling. Schaarste als het vacature-aandeel meer dan
  `_MATCH_DREMPEL` (1,2) keer het diploma-aandeel is, overaanbod omgekeerd, anders evenwicht; `None` voor een sector
  zonder beroepenclusters in de indeling. `match_duiding` zegt waar de score op rust (#900): `drempel`,
  `min_gediplomeerden`, `vacatures_peildatum` (de UWV-momentopname in de provincie), `diplomajaren` (de jaren van het
  gemiddelde), `roa_versie` en `sectormapping` (herkomst, versie en model van de indeling: een LLM-classificatie, niet
  van UWV; een veld dat de mapping niet vastlegt, zoals nu het model, staat er niet in, #951). De
  tegels, de grafiek "Gediplomeerden vs. vacatures" en het vacatureaanbod tonen de peildatum uit de payload; onder de
  tegels staan de drie labels met de drempel en wat de score niet zegt (geen opleidingsniveau bij vacatures, één dag
  tegen een meerjarig gemiddelde).
- **Match als staafgrafiek** (#949): vanaf acht sectoren met een score (`MATCH_GRAFIEK_VANAF` in
  `shared/charts-arbeidsmarkt.jsx`) staat de match niet als tegels maar als liggende staafgrafiek "Match per sector";
  onder de acht blijven het tegels. De staaf is `match_verhouding`: per sector het vacature-aandeel gedeeld door het
  diploma-aandeel, op twee decimalen (`_match_verhoudingen`; `null` zonder label of zonder gediplomeerden). Stippellijnen
  staan op `drempel` (daarboven schaarste) en 1 / `drempel` (daaronder overaanbod), getekend door de inline-plugin
  `DREMPELLIJNEN` (`shared/chart-opts.js`); een noot onder de grafiek noemt beide drempels in tekst. Er is één reeks per
  label, zodat legenda en waardentabel het label in woorden geven en de kleur niet de enige drager is. Een payload
  zonder `match_verhouding` krijgt de tegels. Een staaf is hoogstens `MATCH_KAP` (5) lang (#952): de echte waarde
  staat in de tooltip, de waardentabel, het tekstalternatief en een noot ("Staaf afgekapt bij 5: Techniek (52,15)").
- **Kleine sectoren** (#952): een sector met minder dan `_MATCH_MIN_GEDIPLOMEERDEN` (30) gediplomeerden per jaar (het
  gemiddelde over drie jaar) krijgt geen label en geen verhouding: daar verschoof één diploma de verhouding met
  tientallen procenten (Tilburg University, Techniek: 52,15 bij 63 gediplomeerden; BUas 7,73 bij 13). Hij telt wel mee
  in de totalen, dus de aandelen van de andere sectoren veranderen niet. `match_weggelaten` geeft per sector zonder
  label de reden (te weinig gediplomeerden, geen beroepenclusters, geen vacatures); het dashboard noemt ze per reden.
  De duiding zegt ook dat teller en noemer verschillende grootheden zijn: een voorraad vacatures in de provincie op
  één dag tegen een jaarlijkse stroom diploma's van één instelling.
- **ROA-prognose** (`arbeidsmarkt_prognose`): per niveau de typering van het arbeidsmarktperspectief en de aantallen
  verwachte baanopeningen en instroom van schoolverlaters tot 2030. ROA geeft die twee als aantal, zonder typering; tot
  #951 las het dashboard alleen typeringen en stonden ze overal als "—".

### Diploma's na 3 jaar per eerstejaars (mbo) en geen rendement bij hbo en wo

`/api/dashboard/rendement` heette een "rendement", maar DUO volgt geen studenten. Besluit 05-11 (#898): mbo houdt de
tegel onder de naam van wat hij telt, hbo en wo krijgen geen tegel tot er een echte cohortbron is.

- **Mbo** (`type: "mbo"`): per cohort (het jaar van de eerstejaars) de mbo-diploma's van de instelling in diplomajaar
  cohort + 3 (`_RENDEMENT_TERMIJN`), gedeeld door haar eerstejaars van dat cohort (`INSTROOM MBO = J` in
  `instromende-mbo-studenten`), beide over al haar codes (#923). Het is een ruwe verhouding, geen cohortrendement: de
  diploma's zijn niet die van dit cohort. De payload draagt de naam, de termijn, de definitie, wat niet meetelt en wat
  wel (`definitie`, `_RENDEMENT_MBO`); het dashboard toont dat boven de cijfers, zoals het definitieblok (#736) en
  "Niet meegeteld" (#743) in het rapport. Wat niet meetelt, staat in de teldefinities van DUO en de domeinregel
  `mbo-instroom-mbo`; `tests/test_dashboard_rendement.py` leest het na.
- **Eén regel** (`_rendement`): de instelling en elke peer gaan door dezelfde functie, over dezelfde cohorten (alle jaren
  van de eerstejaars waarvan DUO het diplomajaar + 3 al publiceert). Elk cohort krijgt een verhouding of een reden in
  `weggelaten` (de instelling) of `peers_weggelaten` (per peer): geen eerstejaars, geen diploma's bekend, of meer
  diploma's dan eerstejaars (geen cohortmaat, voor instelling en peers gelijk). Niets valt stil weg; het dashboard noemt
  ze per reden, ook als er geen cohort overblijft. Tot #898 gold de bovengrens alleen voor de instelling, en kwam het
  regiogemiddelde daardoor boven 100 %.
- **Regiogemiddelde**: `benchmark_rendement` per cohort over de peers met een verhouding, met hun aantal in
  `benchmark_n_per_jaar`. `benchmark_label` (de ondertitel) telt de peers in dat gemiddelde, niet de gevonden peers
  (#951: Curio kreeg "7 andere" naast een legenda met 6; BBO de Schalm heeft geen eerstejaars).
  `benchmark_populatie` is de groep zonder aantal en terugval, voor de legenda ("Gemiddelde mbo-instellingen in
  provincie Noord-Brabant").
- **Ondergrenzen**: teller en noemer missen de cellen met 1 tot en met 4 studenten die DUO leeg laat. De diploma's
  staan ook per geslacht, in kleinere cellen, dus daar valt meestal meer weg (in de fixtures Curio ~19 % tegen ~15 %,
  Albeda ~10 % tegen ~5 %, geschat op 2,5 per lege cel) en is de verhouding eerder te laag dan te hoog. De definitie
  zegt dat (#951).
- **Hbo en wo** (`type: "ho"`): alleen `geen_rendement`, een noot waarom er geen rendement staat en dat de chat en het
  rapport het landelijk uit de CBS-cohorttabellen halen. De diploma's van `p04hogdipl` tellen ook masters, associate
  degrees en eerdere cohorten, de eerstejaars van `p02ho1ejrs` geen hbo-masters en niemand die eerder in het ho stond;
  live kwam de verhouding tot 2,45 en viel elk cohort af. Of de naam in het ho staat, zegt `p01hoinges`; dat bestand
  draagt geen getal en staat niet in het bronblok (`bronnen` is leeg). Het rendement per sector en de ho-peerberekening
  zijn weg.

### Financiën van het bestuur en personeel (Mijn instelling)

Twee kaarten op Mijn instelling, elk met een eigen lading (`DeelLading`): een bron die uitvalt, staat in
`niet_beschikbaar` en breekt de rest van het dashboard niet. Ze rekenen met de functies van de chat-tools, niet opnieuw,
en geven hun vaste zinnen zonder de aanwijzingen aan het model ("Zeg dat", "Noem geen getal"); een dashboard bewaart
niets in de store. De LLM komt er niet aan te pas.

- **Financiën van het bestuur** (`/api/dashboard/financien`, `data/dashboard_financien.py`, #935): voor mbo, hbo en wo,
  overal waar `beschikbaarheid.financien()` (CC0, geen vlag). De instelling gaat via het register naar haar bestuur in
  DUO's adressenbestand, of naar haar eigen eenheid als het bestuur er een per BRIN heeft (40833);
  `tools.financien.voor_instelling` geeft per verslagjaar solvabiliteit I en II, liquiditeit, rentabiliteit en
  rijksbijdragen, naast het gewogen sectorcijfer van de Inspectie (geen mediaan), met de signaleringen, de
  signaleringswaarden en de vaste voorbehouden (het cijfer geldt voor het hele bestuur, zegt niets over de kwaliteit van
  het onderwijs, is niet door een accountant gecontroleerd, één variant per jaar). Een signaal is geen oordeel. In
  `meldingen` staat als feit dat DUO het bestuur aan een andere sector toerekent (Aeres Hogeschool) en welke andere
  instellingen uit het register onder hetzelfde bestuur vallen. Geen ranking van besturen en geen gemiddelde over
  besturen. Zonder bestuur in het adressenbestand (transnationale Universiteit Limburg) geeft de payload `melding` en
  `financien: null`. Een waarde die in de bron ontbreekt, is `null` en staat er als "—", nooit als 0. Fusies binnen de
  reeks (RIO) noemt alleen de chat.
- **Personeel** (`/api/dashboard/personeel`, `data/dashboard_personeel.py`, #936): alleen voor wo en alleen met
  `ENABLE_WO_PERSONEEL` (nu alleen op test). Zonder vlag geeft het eindpunt 404 en vraagt de frontend het niet op
  (`bronnen.wo_personeel` uit `/api/config`). `tools.wo_personeel.reeks_van` geeft per jaar de fte zonder GEZO, naar
  wetenschappelijk personeel en OBP (`reken` met `wp_obp`) en naar vast en tijdelijk (vanaf 2003; daarvoor `null`), met
  het aandeel tijdelijk over vast plus tijdelijk, de definitie van WP en de vaste zinnen: peildatum 31 december, fte is
  geen aantal personen, wat niet meetelt, zonder GEZO, en dat een jaarverslag vaak een ander getal noemt. Een hbo- of
  mbo-instelling laadt WOPI niet en krijgt geen kaart; een universiteit die niet in WOPI staat (de vier niet-leden van
  UNL, tUL), krijgt de vaste melding uit `wo_personeel`.

### Onderdrukte en ontbrekende cellen

DUO zet kleine aantallen op -1; de dashboards laden DUO via `_duo_load`, dat zo'n cel leeg maakt (`core/sentinels.py`).
Een som telt een lege cel niet mee en is dan een ondergrens. Elke reeks meldt in `onderdrukt` per jaar (of per sector)
hoeveel lege cellen erin vallen, en het frontend zegt dan "ten minste" (#902). Een jaar of sector met alleen lege
cellen krijgt geen waarde: een gat, geen 0. Een positie landelijk waarin een lege cel meetelt, staat in
`onderdrukt.eigen_positie` en heet in de UI indicatief; een sector zonder eigen waarde staat in `positie_weggelaten`.

### Landelijk, groei en het regiogemiddelde

- **Landelijk** (`/api/dashboard/nationaal`) is de som van het DUO-bestand per instelling (`p01hoinges`,
  `mbo-studenten-per-instelling`). De chat geeft een landelijk aantal uit een vaste CBS-maat (`tools/maten.py`, #805:
  85423NED en 85354NED), een andere telling. Het dashboard blijft bij de DUO-som, omdat het per instelling rangschikt
  en aandelen per DUO-sector rekent, en zegt dat in het veld `landelijk` en op de pagina (#903). Per mbo-instelling
  geven dashboard en `get_maat` hetzelfde aantal; per ho-instelling leest de chat het bestand met opleidingsvorm, dat
  andere cellen onderdrukt, dus daar kan het een paar studenten schelen in een jaar met onderdrukte cellen
  (`tests/test_dashboard_cijfers.py`).
- **Ranking en positie per sector** op Landelijk lopen over de instellingen van het eigen type (#928): een
  universiteit staat naast de universiteiten, een hogeschool naast de hogescholen, een mbo-instelling naast de
  mbo-instellingen. Het type komt uit het register, zoals bij de vergelijkingsgroep hieronder; een hogeschool met een
  paar wo-studenten (HvA, Hanze, BUas staan ook in de wo-resource van `p01hoinges`) blijft een hogeschool en telt
  met al haar studenten. `populatie` noemt type en aantal in de ranking (`{"soort": "wo", "n": 18}`),
  `positie_populatie` per sector het aantal instellingen van dat type met ingeschrevenen in die sector; de pagina
  toont "4e van 9 wo".
- **Marktaandeel** op Landelijk is per type (#950): de landelijke sectortotalen (`sectoren_landelijk`, de noemer) lopen
  over de instellingen van het eigen type, met het type uit het register zoals bij de ranking. Een universiteit heeft
  zo een aandeel in alle wo-studenten van een sector, een hogeschool in alle hbo-studenten (een hogeschool met een paar
  wo-studenten telt met al haar studenten bij de hogescholen). Titel, ondertitel, reeksnaam en tooltip noemen die
  populatie ("aandeel van alle wo-studenten in Recht"), net als `landelijk.definitie` ("de som van DUO p01hoinges over
  alle universiteiten"). Het mbo was al type-zuiver: het bestand kent alleen mbo-instellingen. Tot #950 was de noemer
  alle hbo- plus wo-studenten.
- **Groei** op Mijn instelling loopt voor elke instelling vanaf hetzelfde startjaar (het laatste van de eerste jaren
  met data, over eigen instelling en peers) tot het laatste jaar, in grafiek, ranking en tabel; het startjaar staat in
  de kop.
- **Regiogemiddelde**: per jaar het gemiddelde over de peers met data in dat jaar; `benchmark.n_per_jaar` geeft hoeveel
  dat er zijn, `n_instellingen` het aantal in het laatste jaar. Ingeschrevenen, eerstejaars en gediplomeerden hebben elk
  een gemiddelde, ook bij het mbo (tot #951 had het mbo bij de gediplomeerden alleen de peers, terwijl de grafiek een
  vergelijking beloofde; een grafiek zonder gemiddelde zegt dat nu). Een peer met in elk jaar 0 of een lege cel telt
  niet mee in gemiddelde, aantal, totaal en `onderdrukt`; hij staat per reeks in `benchmark.geen_gegevens` en in de
  concurrententabel met "geen gegevens" (#925). Een peer met één echt nuljaar telt wel mee.
- **Regiototaal** (`benchmark.totaal_regio`): per jaar de ingeschrevenen van de eigen instelling plus die van de peers,
  alleen voor jaren met beide. Het is de tegel "Regio totaal" (of "Landelijk totaal" bij een landelijke vergelijking)
  met "Curio en 6 andere mbo-instellingen in provincie Noord-Brabant", en de noemer van het marktaandeel. Tot #951 was
  het veld `totaal_ingeschrevenen`, de som van de peers zonder de eigen instelling, onder "Regio totaal" en "6
  instellingen in regio" (Curio: 56.816, terwijl de concurrententabel 72.104 gaf, met Curio).

### De vergelijkingsgroep van Mijn instelling

De peers zijn de andere instellingen van hetzelfde type (#926): een hogeschool vergelijkt met hogescholen, een
universiteit met universiteiten, een mbo-instelling met mbo-instellingen. Het type komt uit het register
(`data/instellingen.py`), de regio van instelling en peers uit hetzelfde DUO-adres (`get_adres_lookup`). De regio
verbreedt in vaste treden tot er ten minste drie andere instellingen van het type in zitten (`_MIN_PEERS`; een
gemiddelde over één andere instelling is die instelling, over twee nog erg smal; tot #948 was de drempel twee):

1. de arbeidsmarktregio van de instelling;
2. haar provincie;
3. landelijk: alle andere instellingen van het type, ook die zonder adres. Ook een instelling zonder adres bij DUO
   vergelijkt landelijk.

`benchmark` noemt de uitkomst: `soort`, `regio_type` (`arbeidsmarktregio`, `provincie` of `nationaal`), `regio_naam`,
`terugval` (waarom niet een smallere trede, of `null`), `populatie` (de groep in een zin, voor ondertitels en
legenda: "hogescholen in provincie Noord-Brabant") en `label`, de kop van de kerncijfers met regio, aantal en
terugval:

- "Arbeidsmarktregio Rijnmond, 5 andere mbo-instellingen"
- "Provincie Noord-Brabant, 5 andere hogescholen — te weinig hogescholen in arbeidsmarktregio West-Brabant (0 andere)"
- "Landelijk, 17 andere universiteiten — te weinig universiteiten in provincie Noord-Brabant (1 andere)"

Het aantal in het label is `n_instellingen`, het aantal peers achter het gemiddelde in het laatste jaar. Tot #926
stonden hogescholen en universiteiten samen in één regio (Breda: vijf hogescholen en twee universiteiten in
Noord-Brabant) en vergeleek elke universiteit stil landelijk; een hogeschool zonder andere ho-instelling in haar
provincie (HZ, NHL Stenden) kreeg geen vergelijking. Bij universiteiten kan de regio een paar kleine instellingen
bevatten: de Universiteit Utrecht vergelijkt in Midden-Utrecht met PThU, TUU en de Universiteit voor Humanistiek. Met
drie andere haalt zij ook de drempel van #948; die drempel telt instellingen, niet hun omvang.

Gemeten op live DUO (05-11, #948), per type arbeidsmarktregio / provincie / landelijk: hbo 20 / 12 / 4 bij drempel
twee, 8 / 21 / 7 bij drie; wo 4 / 6 / 8 → 4 / 0 / 14; mbo 25 / 24 / 5 → 16 / 33 / 5.

### Regio, provincie en afdrukken

- **Kaart**: de punten staan op benaderde coördinaten van de plaats van de hoofdvestiging (`_CITY_COORDS` in
  `data/dashboard.py`, gespeld zoals de DUO-adressen: "HENGELO OV", "VELP GLD"). Elke plaats uit `adressen_ho` en
  `adressen_mbo` staat erin; `tests/test_dashboard_kaart.py` legt dat vast tegen de bevroren bestanden. Tot #951
  ontbrak Etten-Leur, en daarmee stond Curio niet op haar eigen kaart. Een instelling zonder bekende plaats noemt de
  kaart onder `zonder_locatie` (#906).

- **Regio en provincie** komen uit één adres per instelling: de hoofdvestiging in het DUO-adressenbestand
  (`adressen_ho`, `adressen_mbo`; `get_adres_lookup` in `data/instellingen.py`). Vestigingen elders tellen niet mee
  (#744). Staat er geen adres met een provincie, dan is de provincie die welke in het DUO-bestand het vaakst bij de
  instelling staat; die kan per lading anders uitvallen. `provincie_herkomst` in `regio` en `arbeidsmarktmatch` zegt
  welke van de twee het is: `"adres"`, `"inschrijvingen"`, of `null` als er geen provincie is (`_provincie` in
  `data/dashboard.py`, #904).
- **Het voorbehoud** (besluit B op #904): de regio- en provinciebadge krijgen een sterretje en één noot eronder
  (`RegioBadges`, `regioNoot` in `shared/shell.jsx`). Zonder adres zegt de noot dat de provincie uit de inschrijvingen
  komt; zonder herkomst staat er geen provinciebadge. Op Arbeidsmarkt zegt de noot ook dat de vacatures (UWV) over deze
  provincie gaan.
- **Afdrukken** (besluit B op #904): elk dashboard heeft een knop "Afdrukken of als pdf bewaren" (`AfdrukKnop` in de
  `DashboardShell`). De print-CSS in `styles.css` toont alleen het dashboard over zijn volle lengte, zonder knoppen, met
  het bronblok onderaan en de links ervan uitgeschreven. Er is geen CSV-export: wie verder wil rekenen, gebruikt chat of
  rapport.

### Een mbo-instelling met meer instellingscodes

`mbo-studenten-per-instelling` kent een instelling onder meer codes (Curio: 21CY en 25LX); de instroom- en
diplomabestanden tellen per code. Elke mbo-telling per instelling loopt daarom over de naam die
`mbo-studenten-per-instelling` bij de code geeft: eigen eerstejaars, de peers (ingeschrevenen, eerstejaars,
gediplomeerden) en het rendement (#923). Een peer met twee codes is één peer.

De mbo-eerstejaars komen uit de bestanden "met soorten instroom" van `instromende-mbo-studenten`, één per jaar, in de
vaste lijst `_INSTROMENDE_MBO_HISTORISCH` (`data/dashboard.py`). De ingeschrevenen per hoofdgroep komen uit het
hoofdgroep-bestand van het laatste jaar, `_INSTROMENDE_MBO_HOOFDGROEP` met het jaar uit de resourcenaam in
`_INSTROMENDE_MBO_HOOFDGROEP_JAAR` (#934). DUO publiceert per jaar beide bestanden. Komt er een jaar bij of verschuift de
volgorde, dan wordt de ping `duo-instroom-mbo` van `bron:ping` rood en noemt hij de bestanden. Dan:

1. voeg de index van het nieuwe bestand "met soorten instroom" toe aan `_INSTROMENDE_MBO_HISTORISCH` (#924);
2. zet `_INSTROMENDE_MBO_HOOFDGROEP` en `_INSTROMENDE_MBO_HOOFDGROEP_JAAR` op het nieuwe hoofdgroep-bestand en zijn
   jaar, na een blik op de kopregel: dezelfde kolommen, en `TOTAAL MBO` nog de ingeschrevenen (domeinregel
   `mbo-instroom-totaal-mbo`);
3. zet dezelfde indexen in `scripts/duo_testfixtures.py` (het oude hoofdgroep-bestand eruit), ververs de fixtures en
   werk de verwachte jaren en getallen in `tests/test_dashboard_mbo_reeksen.py` en `tests/test_dashboard_cijfers.py`
   bij.

---

## Opgeslagen dashboards uit de dashboardbouwer

Een dashboard dat iemand met de verwijderde dashboardbouwer opsloeg, blijft op de server staan: de app gooit geen
gegevens weg omdat een functie verdwijnt. Het opent niet meer. Op `/dashboards` staat het onder de vaste dashboards in
een lijst met titel en datum, om het los te verwijderen; een oude link (`/dashboards?id=…`) zegt dat het niet meer opent.
Het zit in de export van "mijn gegevens", gaat mee met "al mijn gegevens verwijderen" en valt onder de gewone
bewaartermijn van werkboeken (365 dagen, [Privacy](privacy.md)). Met `ENABLE_DASHBOARDS=false` (productie)
is de pagina er niet en zie je ze dus ook niet.
