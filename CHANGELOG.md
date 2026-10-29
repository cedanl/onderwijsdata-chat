# Changelog

Alle wijzigingen die voor gebruikers of beheerders van belang zijn. Formaat naar
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/). Versienummers volgen de git-tags;
de laatste tag is 2.5.0. Tot en met 1.8.6 staat elke versie hieronder apart. De releases 2.0.1–2.5.0 beschrijven de
GitHub-releases; wat sinds 1.8.6 is veranderd staat nog onder "Niet uitgebracht" en krijgt bij de volgende release een
eigen kop (`docs/promoten.md`).

## Niet uitgebracht

### Na een herstart of failover van PostgreSQL falen er geen aanvragen meer op dode verbindingen (#764)
- De vrije verbindingen in de pool waren na een herstart, switchover of failover dood. Tot `POSTGRES_POOL_SIZE` (8)
  aanvragen faalden daarop: een 500, een mislukte WebSocket-handshake, of `/ready` rood, waardoor de enige pod even uit
  de Service viel. Nu vervangt de pool een verbinding waarop het eerste statement faalt omdat ze dicht is, en voert
  dat statement opnieuw uit. Een SQL-fout gaat zoals altijd naar de aanroeper.
- Een nieuwe verbinding krijgt `connect_timeout=5` en TCP-keepalives, tenzij `POSTGRES_URI` die zelf zet.
- Gemeten met PostgreSQL 17: na `pg_ctl restart -m fast` faalden met drie verbindingen in de pool alle drie
  gelijktijdige aanroepen. Nu slagen ze.

### CI: de GitHub-spiegel springt niet meer terug bij een tag (#769)
- Een tag-pipeline pushte de getagde commit ook naar GitHub `main`. Was main al verder, dan stond de spiegel terug tot
  de volgende merge. Nu pusht een tag-pipeline alleen de tag.

### De pytest-gate hangt niet meer af van live DUO en CBS (#766)
- De register- en dashboardtests draaien op bevroren DUO-bestanden in `tests/fixtures/duo/`, niet op
  onderwijsdata.duo.nl. Een storing of verbroken verbinding bij DUO maakte de blokkerende pytest-job rood
  (17 falers op main-pipeline 776057). Die tests duren nu 3,5 s in plaats van 3,5 minuut.
- `scripts/duo_testfixtures.py` ververst de bestanden. De live CBS-test, die zichzelf bij een storing stil oversloeg,
  is weg: `test_cbs_laatste_update_tekst.py` toetst hetzelfde zonder netwerk.

### Verwijderen dat op de server mislukt, zegt dat (#778)
- Een gesprek, rapport of dashboard verdween van het scherm, ook als de server het niet verwijderde (netwerkfout,
  5xx). Het kwam dan na herladen of op een ander apparaat stil terug. Nu staat het weer in de lijst, met een melding en
  "Opnieuw proberen". Een 404 telt als verwijderd.
- Wie een gesprek verwijderde en binnen de bedenktijd van 8 s uitlogde, hield het gesprek op de server: de DELETE ging
  pas na het wissen van het token en kreeg een 401. Nu gaat ze bij het uitloggen meteen, met het token van vóór het
  uitloggen, en het token wordt pas ingetrokken als ze klaar is.
- Sluit je binnen de bedenktijd de tab, dan gaat de DELETE nog steeds zonder melding (`keepalive`). Mislukt die, dan
  staat het gesprek bij het volgende bezoek weer in de lijst.

### Na een herverbinding kent de server het gesprek weer (#756)
- Elke WebSocket is een nieuwe serversessie, maar de app stuurde het gesprek en de instellingen maar één keer per
  pagina mee. Na een verbindingsbreuk, slaapstand of uitrol antwoordde de server daarom zonder eerdere beurten,
  zonder het profiel en met het standaardmodel, terwijl het antwoord het gekozen model noemde. Ook een rapport
  vond de data van het gesprek niet meer. Nu krijgt de server bij elke (her)verbinding de instellingen en het open
  gesprek, met zijn id voor de data-keys (#472).

### Een hernoemd gesprek houdt zijn titel (#757)
- Na het hernoemen van het open gesprek zette de volgende vraag de automatische titel terug, in de zijbalk en op de
  server: elke opslag na een antwoord stuurde de titel uit de eerste vraag mee, en de server nam die over. Nu zet de
  server de titel alleen bij het aanmaken van een gesprek; hernoemen blijft de enige manier om hem te wijzigen, ook
  vanaf een ander apparaat. De zijbalk houdt de titel die er al stond.

### De databasecontrole van een token en het recept achter een snippet houden de chat niet meer stil (#763)
- De WebSocket-handshake en `POST /api/dashboard/refresh` lezen de denylist van ingetrokken tokens in een thread, en
  de snippet na elke toolaanroep zoekt het recept daar ook. Op een trage of volle PostgreSQL-pool bevroor zo'n
  aanroep eerder elke chatstream en `/health` van de pod. Snippets, events en de weigering van een verlopen of
  ingetrokken token (close 4001, HTTP 401) zijn ongewijzigd.

### De melding "opnieuw opgehaald" geldt per gebruiker, en alleen waar ze klopt (#788, #762)
- De vlag dat data na een eerder antwoord opnieuw bij de bron is opgehaald, stond in de gedeelde store. Laadde een
  ander dezelfde dataset live, dan verdween de melding bij jouw volgende rapport of download, of kreeg zijn live
  antwoord jouw melding. Nu staat de vlag per gebruiker; de store bewaart alleen wat voor iedereen gelijk is.
- Een ander gesprek met dezelfde data verwijderen, of veel nieuwe data laden zodat een oud recept uit het geheugen
  valt, gaf live data de melding "opnieuw opgehaald". Nu telt alleen data die je vóór een herstart maakte, of die een
  recept voor je terugzette.
- Na "verwijder al mijn gegevens" blijft ook van deze vlag en van wat je live maakte niets in het geheugen.

### Een misvormd WebSocket-frame sluit de chatverbinding niet meer (#758)
- Een frame dat geen JSON-object is (geen JSON, een lijst, een tekst, een getal), `settings` dat geen object is en
  `history` met `messages` dat geen lijst is, worden geweigerd met dezelfde melding als een onbekende actie. De
  verbinding blijft open, de vorige instellingen en het open gesprek blijven staan. Het log noemt alleen het type.
- Eindigt de chatverbinding door een andere fout dan een disconnect, dan stopt een lopend antwoord, rapport of
  dashboard ook. Eerder draaide het door tot de volgende melding naar de browser faalde.

### Een rapport komt alleen door op tekst die de controle goedkeurde (#754)
- Liep de herkansing van een rapport op een modelfout (bijvoorbeeld een rate limit), dan kwam het afgekeurde rapport
  toch door, met alleen de melding "deels gegenereerd". Hetzelfde als de fout een ronde vóór het antwoord trof. Nu
  controleert `report.generate` de tekst die overblijft opnieuw en weigert het rapport bij een hard probleem; de
  frontend biedt het rapport dan opnieuw aan, zoals bij elke weigering (#515).
- Een rapport waarvoor het model binnen het stappenbudget geen antwoord gaf, werd als lege schil geleverd. Nu volgt
  een weigering met de melding dat het rapport niet af kwam.
- De melding bij een gedeeltelijk rapport noemt geen "rate limit" meer als het een andere fout was; de fout zelf staat
  onder een fout-ID in het log.

### Inspectie-oordelen per mbo-bestuur: de datalaag (#749)
- `tools/inspectie.py` haalt het nieuwste peilbestand per bevoegd gezag van de Onderwijsinspectie op (CC0 1.0). De code
  volgt de pagina's: overzicht, nieuwste schooljaarpagina met een document, nieuwste document, bg-bestand. De
  bestandsnaam en het document-ID wisselen elke maand.
- Het ODS-bestand wordt gelezen met de standaardbibliotheek, zonder nieuwe dependency. De code houdt de besturen waarvan
  de sectoren mbo noemen en markeert een gemengd bestuur (ook po, vo of ho). Het bestuursnummer (`="00008"`) wordt een
  getal, gelijk aan DUO's `BEVOEGD GEZAG NUMMER`. De adreslookup van het register kent nu het bestuur van een instelling.
- Gemeten op het bestand van 1 oktober 2026: 164 besturen noemen mbo, waarvan 126 alleen mbo; dat verklaart de twee
  tellingen uit #722. Alle 55 mbo-instellingen in DUO's adressenbestand vinden via hun bestuur een oordeel.
- `bron:ping` pingt de Inspectie ook. Zo meet de geplande job of de bron vanaf de CI-runner bereikbaar is.
- De chattool `get_inspectieoordeel` geeft het oordeel van het bestuur van een mbo-instelling: het eindoordeel, de
  standaarden, de vaststellingsdatum en de peildatum. Onder het antwoord staat de bronregel "Onderwijsinspectie ·
  Oordelen per bevoegd gezag, peildatum …", met een link naar het bestand.
  - Een gemengd bestuur krijgt de noot dat het oordeel het hele bestuur betreft. Zonder eindoordeel noemt het antwoord
    geen oordeel.
  - Hbo en wo krijgen een vaste melding: daar beoordeelt de NVAO de opleidingen.
  - Twee evals toetsen het oordeel van een mbo-instelling en de melding bij een hbo-instelling.

### Aannames zichtbaar: wat niet meetelt, en een vaste vraag bij instroom (#743)
- Een antwoord op een DUO-telling die iets uitsluit, krijgt onder het Uitgangspunt één regel "**Niet meegeteld:**"
  (`agent/niet_meegeteld.py`). Bij de eerstejaars ho (p02ho1ejrs) staat daar dat wie eerder in het hoger onderwijs
  stond, niet meetelt: dus ook wie na een Nederlandse bachelor aan een master begint. Hbo-masters en opleidingen aan
  aangewezen instellingen tellen ook niet. Er zijn regels voor ingeschrevenen (p01) en gediplomeerden (p04). Dat stond
  wel in de teldefinitie, maar midden in een lange DUO-alinea; na doorvragen bleken de masters te ontbreken. Alleen
  wat de teldefinitie zelf uitsluit: een test leest het na in de catalogus.
- Een vraag naar instroom in het hoger onderwijs zonder fase ("Wat is de instroom van de HvA?") krijgt een vaste kaart
  uit code, vóór het model (`agent/scopevraag.py`). De opties zijn eerstejaars ho per instelling (DUO, zonder masters),
  of landelijk per hbo en wo met de masters erbij (CBS 85422NED). Noemt de vraag bachelor, master, eerstejaars of een
  opleidingsnaam als "B Informatica", dan komt er geen kaart, en buiten deze vaste gevallen vraagt de app niet extra.

### Een afwijking van de vraag staat vooraan in het rapport (#734)
- Wijkt een rapport meetbaar af van wat de gebruiker vroeg, dan staat dat als eerste blok, vóór de onderzoeksvraag. Het
  blok komt uit code (`agent/report_afwijking.py`, veld `afwijkingen` in het rapport). Er zijn twee soorten:
  - een periode die de grafieken niet dekken, zoals "Gevraagd was de afgelopen 10 jaar; de grafieken tonen 2021/22 t/m
    2025/26 (5 jaar), meer staat niet in de bron". Dat geldt ook bij "vanaf 2016" en "2016 tot 2025";
  - een prognosevraag terwijl geen geladen bron een prognose is.
- "Het veranderen van de onderzoeksvraag had veel prominenter in beeld en als eerste genoemd moeten zijn." Wat gevraagd
  was, komt uit de woorden van de gebruiker: de bevestigde onderzoeksvraag, anders de laatste vraag die een periode
  noemt. Andere afwijkingen blijven tekst van het model.

### Grafiek en rapport (feedback 28 oktober, #741, #748)
- `create_plot` kent `y_vanaf_nul` (#741): op verzoek begint de waardeas op 0. Een lijngrafiek begon anders bij het
  kleinste getal (in het rapport van 28 oktober rond 48.560), en "ik wilde eigenlijk dat de y as op 0 begon, maar dat is
  niet gelukt". Standaard blijft het bereik vrij; staven beginnen al op 0. De snippet tekent dezelfde as.
- De auteursregel van een rapport zegt dat het met de tool is gemaakt (#748): "Opgesteld door <naam> met openEDUdata+
  (AI-assistent)", zonder naam "Opgesteld met openEDUdata+ (AI-assistent)" in plaats van "onbekend".
- Een definitie van meer zinnen staat in het rapport als opsomming, één zin per punt (#748): "het blok definities mag meer
  bulletsgewijs".

### Kritieke set en drempel voor de bronwaarheid-evals (besluit #693, #753)
- `expected.kritiek` markeert in `tests/e2e/evaluations.json` de 17 kritieke vragen: de ijk-cases met exacte bronwaarden,
  de weigeringen en het #742-paar over geslacht per opleiding.
- Een weigering moet in elke herhaling slagen; een verzonnen getal is de ernstige fout. Een andere kritieke vraag moet in
  een meerderheid slagen, 2 van 3 bij `TEST_REPEATS=3`.
- De runner schrijft `eval_results/kritiek-<datum>.json` en logt één regel per model, bijvoorbeeld "kritiek …: 16 van 17
  gehaald; rood: ijk-hu-deeltijd (1/3)". De promotiechecklist (`docs/promoten.md`) vraagt om die regel in de
  promotie-MR. De evals blokkeren niets (`allow_failure` blijft); een kritieke vraag zonder run telt als rood.
- De verslagen van de evals waren onvolledig. Playwright start na een mislukte test een nieuwe worker, en de stand in het
  geheugen raakte dan kwijt: het slagingspercentage en het rapportverslag (#752) bevatten alleen de vragen van de
  laatste worker. Nu legt elke run een regel vast in `eval_results/runs.jsonl`, en `eval-teardown.js` bouwt de verslagen
  na alle workers (`tests/e2e/runlog.js`).

### Rapporteval: volgt het rapport de bijsturing? (#752)
- Een eval over de echte keten (`tests/e2e/rapport-bijsturing.spec.js`) speelt de twee gesprekken uit de
  rapportfeedback van 28 oktober na. Daarna drukt hij op "Genereer rapport" met de onderzoeksvraag die de app voorstelt:
  - "alleen universitaire bachelors, geen verwante opleidingen" na een vraag over drie informatica-bachelors. Het
    rapport mag dan geen grafiek uit het hbo-bestand hebben, en geen hbo- of verwante reeks;
  - "Genereer een rapport dat ingaat op je laatste antwoord" na twee data-antwoorden. Het rapport moet dan over het
    tweede antwoord gaan.
- De controles zijn code: de onderzoeksvraag, de bronregel van elke grafiek en de reeksen erin. Per scenario komen de
  geslaagde runs en de redenen in `eval_results/rapport-<datum>.json`. De job `eval:bronwaarheid` draait de eval mee,
  informatief (besluit #693).
- De runners delen nu één gesprekshulp (`tests/e2e/gesprek.js`, één verbinding per gesprek) en één `haalToken`.

### Geslacht per opleiding uit code (#742)
- "Wat is de man-vrouwverhouding bij Luchtvaart van Inholland?" gaf de ene keer een verdeling en de andere keer "niet
  beschikbaar": of het model het geslachtsbestand van DUO aan de opleiding koppelde, besliste het per run. Nu doet de code
  het, via `get_maat` met `opleiding_naar_geslacht` (naam of CROHO-code). DUO heeft geslacht niet per opleiding. In een
  jaar is de verdeling toch exact als de opleiding de enige is in haar cel van het geslachtsbestand (instelling,
  vestigingsgemeente, onderdeel, subonderdeel en type ho), er niets onderdrukt is en de totalen van beide bestanden gelijk
  zijn. Anders geeft de tool per jaar de reden, zonder getal; een onderdrukte cel wordt nooit uit een verschil
  teruggerekend. B Luchtvaarttechnologie van Inholland is in elk jaar exact (2025/26: 140 man, 30 vrouw); HBO-Rechten deelt
  haar cel met acht andere opleidingen en krijgt de vaste melding. De Uitgangspuntregel noemt de opleiding die de code
  koos, de snippet rekent hetzelfde uit, en twee evals (`geslacht-opleiding-exact`, `geslacht-opleiding-niet-exact`) toetsen
  dat de beschikbaarheid per run gelijk blijft.

### Presentatie
- Een RIO-antwoord noemt van welke dag de stand is ("stand van 26-10-2026"), en de snippet vraagt die dag op met
  `datumGeldigOp` (#718). RIO is een levend register: dezelfde aanroep een week later gaf een andere stand zonder dat iemand
  het zag. De app zet de dag van de aanroep zelf (dezelfde rijen als zonder filter, gemeten op elf resources); een eigen
  `datumGeldigOp` blijft staan, en een resource zonder dat filter krijgt in de snippet een opmerking.
- Het manifest, de logregel `GEPUBLICEERD` en de kop van de CSV-export noemen een `inhoudshash` van de brontabel van een
  CBS- of RIO-antwoord (#715), te narekenen met `hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:12]`. Zo is
  later vast te stellen of een herlading dezelfde data oplevert.
- Een DUO-antwoord noemt van wanneer het bestand is (#717): de bronregel en het manifest zeggen "versie van 10-07-2026", de
  dag waarop DUO het bestand verving. Het manifest (`bronhash`), de logregel `GEPUBLICEERD` en de CSV-kop noemen de md5
  van het geladen bestand, gelijk aan de hash die DUO erbij vermeldt en na te rekenen met `md5sum`. Voorheen toonde de app
  voor DUO alleen een herlaaddatum. Vraagt `riodata` 0.7.0 (`df.attrs["bron"]` met `last_modified`, `hash`, `etag` en
  `md5`); een datastore-dump zonder datum krijgt alleen de md5.
- Een link `/chat#vraag=…` opent de chat met die vraag in de invoer van een nieuw gesprek (#709), ook als de
  gebruiker eerst moet inloggen, via SRAM of met een wachtwoord. De vraag gaat niet vanzelf naar het model; de app
  haalt hem uit het adres, maakt er één regel platte tekst van en kapt hem af op 500 tekens. Hij staat in het fragment
  (`#`), niet in de query: zo komt hij niet in de toegangslog van uvicorn of de ingress. Zie `docs/api.md`.
- Een foutmelding bij een ontbrekende of ongeldige API-sleutel, een onbekend model of een verbinding die de server met
  de provider niet krijgt, stuurt de gebruiker niet meer naar `.env` of naar zijn eigen internetverbinding (#712). Hij leest
  "Het model is nu niet beschikbaar", met een fout-ID om door te geven; de beheerder vindt onder dat ID in het log wat er
  speelt en waar te kijken (sleutel in het secret, `MODEL`, `*_API_BASE`).
- De gespreksexport (markdown) zet onder elk antwoord een blok "Herkomst" met het model, de prompt-, catalogus- en
  appversie en de dataversie achter het antwoord (bijgewerkt, status, herlaaddatum, peilmoment; #713). Het manifest ging al mee
  met elk chatantwoord, maar bleef onbenut; alleen rapporten toonden het. Een gesprek dat uit de database is teruggezet
  heeft geen manifest en dus geen blok. Er staat geen vraag- of antwoordtekst in het blok.
- Een Python-snippet noemt bovenaan de pakketversies waarmee hij is gemaakt (`onderwijsdata`, `riodata`, appversie) en een
  `pip install` met dezelfde versies, bij een git-installatie op de exacte commit (#714). Zo geeft een latere run niet
  stilletjes een andere uitkomst door een nieuwere pakketversie.
- Een foutmelding in de chat houdt zijn knoppen niet meer als de vraag daarna toch is beantwoord (#703). Na een
  limietfout en een geslaagde herhaling bleef de oude melding een werkende "Opnieuw" houden, naast het antwoord op
  dezelfde vraag. De melding blijft als geschiedenis in het gesprek staan, zonder knoppen.
- Onder elke grafiek in de chat staat een ingeklapte knop "Toon de waarden" met alle waarden van de grafiek als
  tabel (#664). Op een telefoon was een tik-tooltip de enige weg naar een waarde; een schermlezer kreeg per reeks alleen
  de eerste en laatste. De tabel komt uit dezelfde rijen als de CSV (`layout.meta.data`, anders de getekende reeksen),
  met meer reeksen naast elkaar en getallen in Nederlandse notatie. Gemeten op 390 px (iPhone 14, licht en donker): de
  knop is 44 px hoog, een grafiek met 12 en een met 3 × 6 punten past zonder zijwaarts scrollen en de pagina loopt niet
  over. De terugvaltabel van een kaart die niet getekend is (#632) gebruikt dezelfde tabel; dashboards en rapporten
  blijven zoals ze waren.
- Het feedbackformulier op een rapport laat per blok zien hoeveel vragen er zijn en hoeveel je er hebt beantwoord
  ("Over dit rapport — 2 van 7 vragen beantwoord"). De vragen over het rapport hebben nu een eigen kopje (`section` bij
  `nuttig` in `core/feedback.py`); de knop "Help ons verder" noemt het aantal vragen erachter. Op een telefoon
  (390 px) weet je zo na het eerste blok hoeveel er nog komt (#665). Verzenden en de bewaartekst zijn ongewijzigd.
- Een grafiek in een streamend antwoord verschuift op een telefoon niets meer in beeld (CLS van de landing 0,036 →
  0,0005 op een staaf- en lijngrafiek, licht en donker, 390 px; #661, naast de herhaalknop uit !641). Het etiket "Antwoord van <model>" onder de
  bubbel stond er al zodra de grafiek binnenkwam, terwijl de tekst nog stroomde, en schoof bij elke regel en bij de
  landing van de grafiek mee omlaag. Het komt nu pas als elk bericht van de beurt klaar is. Op een breed scherm
  verdwijnt dezelfde verschuiving (0,043 → 0,030); wat daar overblijft is de grafiek zelf, die tijdens het
  streamen meeschuift (#639).

### Rapport volgt de vraag zoals die in het gesprek groeide (#732)
- Het rapportmodel ziet de vragen van het gesprek, genummerd, en per dataset bij welke vraag hij ontstond (#733). Een
  latere bijsturing gaat voor: na "Ik wil het alleen zien voor universitaire bachelor's. Geen verwante opleidingen" tekende
  het rapport de wo+hbo-analyse van de eerste vraag, omdat het alleen die eerste vraag kreeg. De vragen staan alleen in de
  prompt; wat de gebruiker zei telt niet als bewijs voor een getal in het rapport (#211).
- `generate_report` neemt een bevestigde onderzoeksvraag aan (`onderzoeksvraag`, #750). Die wordt titel en onderzoeksvraag
  van het rapport, zonder persoonsgegevens, en het model formuleert haar niet opnieuw. Zonder dat veld blijft het onderwerp de
  eerste vraag van het gesprek. Ook het onderwerp zelf telt niet meer als bewijs: een getal in de vraag van de gebruiker
  dekte een getal in het rapport.
- Bij "Genereer rapport" staat de onderzoeksvraag in een veld, al ingevuld en aan te passen (#751): de regel
  **Onderzoeksvraag:** uit het laatste antwoord dat er een heeft, anders de eerste vraag. Genereer of Enter stuurt haar mee;
  wie meteen op Genereer drukt, krijgt het rapport over die vraag. Leeg laten neemt de eerste vraag, Escape of Annuleren
  sluit zonder rapport. Kan het rapport nu niet starten, dan komt er geen veld maar meteen de melding waarom (#648).
  Bijvangst: "Annuleren" in een bevestigingsdialoog was in het donkere thema donker op donker; de knop neemt nu de
  tekstkleur van de dialoog.

### Restpunten audit 29 oktober
- De bronlink naar DUO opent de dataset weer (#737). De catalogus gaf de CKAN-URL `onderwijsdata.duo.nl/dataset/<id>`,
  en die belandt in de DUO-portal op een lege pagina "Datasets" (gemeten in een browser). De link is nu
  `/datasets/<id>`; onder een rapportgrafiek gaat hij naar de pagina van het geladen bestand
  (`/datasets/<id>/resources/<resource-id>`), het bestand dat de bronregel al noemt. De bronlinks in de chat gaan naar de
  datasetpagina.
- Titel en onderwerp van een rapport of dashboard komen uit de eerste vraag van het gesprek, ook na heropenen of na een
  verduidelijkingskaart (#732, stap 1). Na verversen of terugkeren van /rapporten begon de sessie met lege beurten, en
  werd de eerste vraag daarna het onderwerp ("Genereer een rapport dat ingaat op je laatste antwoord"); een vraag met
  een verduidelijkingskaart telde niet, dus werd de gekozen optie het onderwerp. Welke vraag de hoofdvraag is, blijft
  een besluit in #732.
- De regel "Dataversie" in rapport en gespreksexport noemt de inhoudshash van een CBS- of RIO-tabel (#715) en de md5 van
  een DUO-bestand (#717), zodat je kunt narekenen of het dezelfde data is. Ze stonden al in het manifest.
- De verbinding met Postgres vraagt TLS (`sslmode=require`), tenzij de URI zelf een `sslmode` noemt (#683). Zonder die
  instelling viel psycopg2 stil terug op `prefer`. Test en playground praten al TLS 1.3 (gemeten met `pg_stat_ssl`).
- Test geeft `LOG_HASH_SECRET` uit het secret door aan de pod, als optionele sleutel (#678). Zonder die sleutel start de
  pod zoals nu; met die sleutel staat het pseudoniem `gebruiker=` in het log. Playground gaat mee in de volgende
  promotie-MR, zodat de pod daar niet buiten de promotie om herstart.

### Feedback
- Het feedbackformulier op een rapport noemt de instelling die je in de app koos: "Over Hogeschool Utrecht" in
  plaats van "Over jouw instelling". Heb je geen instelling gekozen, dan blijft het formulier zoals het was; de
  standaardinstelling van de pagina telt niet als keuze. De gekozen instelling wordt met de inzending bewaard in
  de nieuwe kolom `feedback.instelling` (leeg zonder keuze, hoogstens 200 tekens, 90 dagen zoals de rest van de
  feedback) en staat in de export van je gegevens. De kolom komt er bij de eerstvolgende start vanzelf bij; oude
  rijen houden een lege instelling. `onderwijsdata-chat-feedback.sh` (glab-surf) toont haar mee.

### Rapporten (feedback 28 oktober)
- De bronnen, de gekozen definities, het voorbehoud bij een afgekapte bron en de regel "Dataversie" van een rapport
  noemen alleen wat het rapport gebruikte (#738): de datasets die de rapportrun zelf las (haar bevragingen en de
  grafieken die in het rapport staan) en een berekening uit het gesprek waarvan het rapport een getal citeert. Eerder
  kwam alles mee wat het gesprek had opgehaald; bij twee grafieken uit CBS 83285NED stonden ook CBS 83282NED en twee
  DUO-tabellen erbij. Rust een rapport op geen enkele herleidbare key, dan blijven de bronnen van het gesprek staan.
- Op een telefoon scrolt een veeg over een rapportgrafiek de pagina, in plaats van in de grafiek in te zoomen (#740).
  In de chat stond de sleepzoom op een smal scherm al uit (#614); het rapport krijgt dezelfde instelling tot 640 px.
  Gemeten op 390 px met een aanraking: de pagina scrolt 247 px en het asbereik blijft gelijk, waar de pagina eerst
  stilstond en de y-as inzoomde. In de chat scrolt dezelfde veeg 194 px.

### Rapporten (#660)
- De HTML van rapporten en dashboards (viewer en download) laadt een eigen Plotly-build zonder maplibre: 3,3 MB in
  plaats van 4,8 MB, dus een gedownload rapport is ongeveer 1,5 MB kleiner. Een kaart in een rapport tekent sinds
  #642 als SVG en had maplibre niet meer nodig; met maplibre is ook de verwijzing naar `cdn.jsdelivr.net` (de
  maki-iconen van `scattermap`) uit rapporten en downloads weg. De andere grafieksoorten blijven. `npm run build`
  maakt het asset (`assets/plotly-rapport.min-<hash>.js`, Vite-plugin in `frontend/src/plotlyRapportBouw.js`); een
  opgeslagen rapport krijgt het bij het tonen, zonder migratie. De chat houdt de volledige Plotly. Een `scattermap`
  of `densitymap` in een rapport geeft een lege grafiek (getekend werd hij in de sandbox en vanaf schijf al niet).

### Bronnen
- Afhankelijkheden: `pillow` 12.3.0 → 13.0.0 (acht CVE's; alleen transitief via matplotlib, de app importeert PIL niet) en `certifi` 2026.7.22 → 2026.10.19 (PYSEC-2026-4320). `pip-audit` meldt daarna geen bekende kwetsbaarheden meer.
- Vijf DUO-datasets (`ho_opleidingsoverzicht`, `overzicht-erkenningen-ho`, `mbo_opleidingsaanbod`,
  `rio_nfo_po_vo_vavo_mbo_ho`, `sectorale_ontwikkelpaden`) hebben in de catalogus weer een werkende verwijzing naar
  hun controlebestand: DUO maakt dat bestand bij elke publicatie opnieuw aan, het snapshot hield de oude ID vast
  (riodata 9931ce3). De databestanden zelf werkten al.
- CBS-catalogus: twee tabellen erbij, `85367NED` (voortijdig schoolverlaters naar geslacht, leeftijd, onderwijssoort
  en herkomst; de chat laadt alleen de mbo-rij `A025290`, zoals bij `85368NED`) en `84312NED` (mbo-studenten in
  Caribisch Nederland). Het pakket `onderwijsdata` gaat van v0.2.0 naar v0.2.2. `84732NED` (Caribisch NL, po/vo/mbo
  samen) blijft erbuiten: het heeft één mbo-rij naast po en vo en `84312NED` dekt mbo volledig. De telling is nu
  CBS 125, DUO 15, RIO 8.
- README en `docs/index.md` zeiden dat ROA en UWV alleen in de dashboards zitten; ze zijn ook in de chat te
  bevragen met `get_roa_benchmark` en `get_uwv_vacatures`, zoals `docs/databronnen.md` al zei.
- RIO heeft op 19-10-2026 API v2 verwijderd (HTTP 410 op elke aanroep): `get_rio_instelling` en `get_rio_data`
  werkten niet meer, op test en playground. De chat draait nu op RIO LOD API v3 via riodata 0.6.0 (#627): het
  typefilter heet op elk register `type` (v2: `erkenningtype`, `opleidingseenheidtype`, `opleidingserkenningtype`),
  de route per instelling leest de relaties via `vanErkenningId`/`naarErkenningId`, en de bronlinks wijzen naar v3.
  `aangeboden-opleiding-cohorten`, `contactadressen` en `onderwijslocatiegebruiken` hebben in v3 geen lijst-endpoint;
  `get_rio_data` zegt dat vóór de aanroep. De sectorfilters in `tools/scopeprofiel.py` worden getoetst tegen het
  riodata-contract, zodat een volgende hernoeming in de test opvalt en niet live.
- De bronlink van een CBS-tabel (bronnenblok onder een antwoord, bronregel onder een rapportgrafiek) opent de
  StatLine-tabelpagina (`https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table`) in plaats van de ruwe OData-JSON
  (#638). DUO, RIO, UWV en ROA houden hun link; bewaarde gesprekken houden de oude link.

### Tools en documentatie (audit 19 oktober, #631)
- `compute_kpi` weigert `delta`, `pct_change`, `index`, `max_drop` en `max_rise` over één waarde ("minstens twee
  waarden") in plaats van "0,0%" te geven; bij `last` en `first` noemt `periode` alleen het jaar van die waarde, niet
  de hele reeks.
- `get_maat` (mbo) en `run_analysis` geven tellingen als hele getallen (4507, niet 4507.0), dezelfde regel als
  `query_data`; een echte breuk blijft een breuk.
- `search_catalog` vraagt in het schema om Nederlandse trefwoorden, ook bij een vraag in een andere taal: de
  catalogus is Nederlandstalig en "university students" vond niets.
- UWV: `Fryslân` telt als `Friesland` (de spelling van CBS naast die van UWV) en `Onbekend` staat niet meer in de
  lijst provincies die de foutmelding noemt.
- Instellingsregister: aliassen `VU Amsterdam`, `Codarts`, `HKU`, `Graafschap College`; een lidwoord vóór een
  naam of alias ("de VU", "het Deltion") telt niet mee, een naam die zelf met een lidwoord begint ("De Haagse
  Hogeschool") blijft gewoon werken.
- Docs: de zoeklimiet van `search_catalog` is 3 (`SEARCH_CATALOG_LIMIT`), niet 5 zoals `docs/tools.md` en
  `docs/kwaliteit-en-veiligheid.md` zeiden.

### Zoeken (#358)
- **Stap 2: een vaste envelope.** `search_catalog` geeft altijd dezelfde JSON terug, ook bij een fout: `status`,
  `catalogus` (hash van de catalogus), `kandidaten`, `melding`/`meldingen` en `vervolgstap`. Voorheen was het een
  lijst met treffers, platte tekst (`no_match: …`) bij een miss en pseudo-records met een `melding`. De zeven statussen
  zijn `candidates`, `no_match`, `needs_clarification` (zwakke suggesties; het model laadt er geen en stelt één vraag),
  `out_of_scope` (de zoekvraag gaat over po, so of vo zonder ho of mbo; dezelfde regel als `agent/po_vraag.py`),
  `metadata_unknown` (bij `geo_niveau`: de geodekking is onbekend), `source_unavailable` (de catalogus is niet
  leesbaar) en `tool_error` (een onverwachte fout, in plaats van een uitzondering naar de loop).
- Een kandidaat draagt `dataset_id` (het ID voor `dataset_details` en de datatools) en `geraakt`: de zoektermen die
  hij raakt. `no_match` en `needs_clarification` noemen de gebruikte zoektermen (`gezocht`) en geven een begrensde
  herformulering mee: hooguit één nieuwe poging met andere of bredere termen, zonder sector, periode of populatie los
  te laten; daarna zegt het model dat de catalogus niets vindt dat past, niet dat de data niet bestaat.
- Prompt, toolschema, MCP-server (`docs/mcp.md`), de aanroepers in de agent en het retrieval-harnas lezen de nieuwe vorm;
  een test houdt de statussen in prompt en schema gelijk aan de code. Meting vóór en na: de retrieval-baseline (`scripts/meet_retrieval.py`) is ongewijzigd (recall en MRR gelijk: de zoekcode scoort hetzelfde); op acht audittermen blijft de envelope onder het toolbudget van 12.000 tekens (9.000 tot 11.800 tekens, was 9.000 tot 11.700) en een tikfout in een dataset-ID (`85423NEDX`) noemt nu de bedoelde dataset. De bronwaarheid-evals (`eval:bronwaarheid`) zijn niet opnieuw gedraaid: ze lopen tegen de testomgeving en volgen na de merge.
- **Stap 1:** een zoekhit van `search_catalog` is compact: ID, titel, status, leverancier, periode, onderwijstype, één samenvatting
  van hoogstens 200 tekens, de CBS-dimensies en -meetwaarden (eerste twaalf), geo-niveau en perioden, de DUO-zoekkaart,
  de RIO-filters en -sub-resources en `niet_geschikt_voor` (eerste drie); lege velden ontbreken. De documentatielink,
  voorbeeldvragen, tags, `combineerbaar_met`, kolomtoelichting en waardenbereik staan alleen nog in `dataset_details`.
  Past het resultaat ook zo niet binnen wat het model van een toolresultaat ziet (`TOOL_RESULT_MAX_CHARS`, 12.000), dan
  laat de tool hele treffers van achteren weg en meldt hoeveel; het model leest zo altijd geldige JSON. Gemeten op twaalf
  zoektermen uit de audit van 19-10: bij `top_n=15` ging acht keer het resultaat over die grens (tot 49.000 tekens), nu
  geen enkele keer; de rangorde verandert niet (retrieval-baseline Δ 0,00).

### Scope
- De chat werkt alleen voor mbo, hbo en wo. Po-, so- en vo-bestanden van DUO (o.a. `02voins-v1`)
  zijn niet meer te vinden, op te vragen of te laden, ook niet met een dataset-ID uit de
  vraag. De DUO-telling gaat daardoor van 56 naar 14 datasets. Een record zonder scopebesluit valt erbuiten.
- Dezelfde grens geldt nu voor CBS: tabellen over alle onderwijssoorten (zoals `37220`) of over po/vo
  zijn niet te vinden, op te vragen of te laden, ook niet als herstelpoging na een lege selectie. De
  CBS-telling gaat van 266 naar 117 tabellen. Bij de VSV-tabellen over mbo én vo laadt de chat alleen de
  mbo-rijen; dat selecteert de code, niet het filter van het model (de CBS-feed negeert een EN-clausule).
  Elke bronvermelding van zo'n tabel zegt dat ook ("…, alleen mbo"): in de citaties, het Telling-blok, de
  rapportbronnen en de CSV- en grafiekexport. De mbo-selectie zit nu ook in de aanroep zelf, vooraan in
  `$filter` (de feed gebruikt bij twee clausules op dezelfde dimensie alleen de eerste); een vo-code gaat niet
  meer de deur uit. Een volle pagina zonder mbo-rijen heet onvolledig, niet leeg.
- De woonregiotabellen van CBS over alle onderwijssoorten, `85701NED` (leerlingen en studenten) en
  `85702NED` (gediplomeerden), zijn weer op te vragen, maar alleen de rijen voor mbo, hbo en wo: dezelfde
  selectie in de code als bij de VSV-tabellen, in de aanroep en op de rijen, en de bronvermelding zegt
  "…, alleen mbo, hbo en wo". Het is de enige open bron voor hbo/wo-studenten naar woongemeente, COROP,
  provincie of landsdeel (zonder instelling). De CBS-telling gaat van 117 naar 119 tabellen.
- Vijf vo-bronnen zijn op te vragen als vo-context voor ho: de CBS-tabellen `85566NED` (doorstroom uit vo en
  vso), `85380NED` (vo-leerlingen), `85381NED` en `85382NED` (vo-gediplomeerden), en DUO's `voprognoses`. De
  zoekfunctie toont ze alleen bij een vraag die ho noemt (hbo, wo, ho, hoger onderwijs, havo, vwo, hogeschool,
  universiteit); elke treffer en elke bronvermelding zegt "vo-context voor ho". Andere po-, so- en vo-bronnen
  blijven erbuiten. De CBS-telling gaat van 119 naar 123 tabellen, de DUO-telling van 14 naar 15 datasets.
- De documentatie (`docs/databronnen.md`, `docs/tools.md`) noemt de vo-context voor ho met een tabel van de vijf
  bronnen en hun grenzen: havo en vwo tellen als ho-woord, dus ook een zuivere vo-vraag met havo of vwo kan deze
  tabellen vinden en laden (open punt op #554); de keuzekaart bij een vage vraag toont het label niet; en een
  dataset-ID laadt ook zonder ho-woord.
- RIO-registers over alle sectoren (aangeboden opleidingen, opleidingen, opleidingserkenningen,
  onderwijslicenties) haalt de chat alleen op met een filter op een mbo/hbo/wo-type. Registers die niet per
  sector te selecteren zijn (erkenningen, contactadressen, onderwijslocaties, organisatorische eenheden) laadt
  hij niet; bestuur, instellingen en vestigingen van een instelling lopen via `get_rio_instelling`.
- Een vraag over po, so of vo zonder ho-context ("Hoeveel leerlingen zitten er in groep 8?", "op de basisschool in
  Utrecht", "op het vwo") krijgt de vaste scope-uitleg uit code, vóór elke verduidelijkingskaart en zonder
  modelronde of toolaanroep (#647). Het model bood eerst het totaal basisonderwijs uit `85701NED` aan, deed daarvoor
  een `get_cbs_data`-ronde en stelde bij "basisschool in Utrecht" eerst de plaatskaart. Noemt de vraag of het vorige
  bericht ook ho, mbo, studenten, eerstejaars of een instelling uit het register, dan gaat ze zoals voorheen naar
  het model, net als een keuze op een verduidelijkingskaart. Een losse "so" of "bo" (ook Engels) telt niet.

### Evaluatie
- `scripts/ijkwaarden.py` stopt niet meer bij de eerste bron die niet antwoordt: de ijkwaarden van CBS en DUO worden
  toch vergeleken, het ijkpunt dat faalde staat met de fout van de bron in het rapport (exitcode 1) en zijn vastgelegde
  waarde blijft staan, ook met `--schrijf`. Dat was nodig toen RIO op 19-10 HTTP 410 gaf (#627).
- Ketenbrede controle los van `/health` en `/ready` (#169). Elk gepubliceerd resultaat (antwoord, figuur, CSV-export,
  rapport) schrijft één logregel `GEPUBLICEERD` met per data-key bron, dataset, resource, de key (de digest van de
  selectie), volledigheid, afronding en herlaaddatum, en de versies uit het manifest (model, prompt, catalogus, app);
  het tijdstip is dat van de regel, de selectiestappen in woorden staan op DEBUG, geen vraag- of antwoordtekst. De
  eval-runner draait nu ook tegen een draaiende omgeving: `EVAL_BASE_URL`, `EVAL_USERNAME` en `EVAL_PASSWORD` in
  plaats van `localhost` en `admin/admin`, met `playwright.eval.config.js` zonder webserver en browser. De nieuwe
  CI-job `eval:bronwaarheid` (gepland of met de hand, informatief) draait de bronwaarheid-evals tegen de testomgeving
  en bewaart `eval_results/` 90 dagen als artifact. De runner heeft nu een eigen `package.json` met vastgezette
  versies van Playwright en `ws`. `docs/kwaliteit-en-veiligheid.md` zegt welke garanties code afdwingt en welke
  regels de prompt alleen vraagt.
- Bronwaarheid-evals met onafhankelijke ijkwaarden (#190): `scripts/ijkwaarden.py` haalt 21 referentiewaarden
  rechtstreeks bij CBS (OData via httpx), DUO en RIO (`riodata`) op, buiten `tools/` om, en legt ze met bron,
  selectie, eenheid, schooljaar, CBS-status en ophaaldag vast in `tests/e2e/ijkwaarden.json`; zonder `--schrijf`
  toont het script elk verschil met de vastgelegde stand en faalt het, zodat drift van de bron zichtbaar is in
  plaats van een eval die stil gaat falen. Negen nieuwe cases in `evaluations.json` stellen de ongehulpte vragen
  uit audit 7a/7b/8 (hbo voltijd landelijk met status, HU voltijd 2021–2025 als personen, HU deeltijd 7.408 en
  niet 7.418, eerstejaars met een onderdrukte cel, mbo vrouwen uit F-10, Aeres 30TX met vijf vestigingen, en
  weigeringen voor een RIO-totaal, 2035/36 en code 99ZZ); hun referentiewaarden verwijzen naar de fixture en
  zijn exact, zonder tolerantie. `TEST_REPEATS=3` laat elke vraag drie keer per model lopen (één fout telt) en
  de runner schrijft het slagingspercentage per model en vraag naar `eval_results/slagingspercentage-<datum>.json`.
- Determinisme is een CI-eigenschap (#347, `tests/determinisme/`): per vast geval worden 40
  gelijkwaardige spellingen gegenereerd die op één plan-digest moeten uitkomen, zonder netwerk en
  zonder model. De golden stand (plan-digests, het compilaat van een gesloten selectie en
  uitkomst-digests) wijzigt alleen via `scripts/meet_determinisme.py --schrijf-golden`, met een
  verantwoording in de MR; de scorekaart draagt prompt-hash, model en schema-digest. De
  periodeherstelroute (#342) logt per antwoord `PERIODE_HERSTEL`/`PERIODE_WEIGERING`, zodat de
  reparatiegraad over echte runs te volgen is.
- De productievragen-eval (`tests/e2e/real-questions.spec.js`) keurt een leeg, mislukt of afgebroken
  resultaat niet meer goed: een geldig einde, tekst, geen fout en geen timeout zijn harde poorten, en elke
  eis (tool, dataset, term, referentiewaarde, grafiek) faalt apart in plaats van in één totaalscore. De
  runners sturen het token als WS-subprotocol en tellen ingetrokken tekst niet mee. De poort heeft
  unittests die in CI draaien.

### Arbeidsmarkt
- `get_roa_benchmark` geeft echte ROA-cijfers (AIS 2030, landelijk): schoolverlatersinformatie (SIS 2024) en de
  prognose tot 2030 per opleidingsniveau of -sector. Daarvoor gaf hij vaste waarden uit de code ("~80%") als
  ROA-cijfers door.
- `get_uwv_vacatures` en `get_roa_benchmark` lopen langs dezelfde scopepoort als CBS, DUO en RIO; de peildatum
  komt uit de data, en een onbekende sector of provincie geeft de geldige keuzes.
- De arbeidsmarktdata staat in `data/arbeidsmarkt.py`, gedeeld door tools en dashboards. De ROA-prognose in het
  dashboard is nu landelijk; daarvoor won de typering van de laatst gelezen regio.
- `get_uwv_vacatures` telt een beroepencluster dat bij meer sectoren hoort niet meer dubbel: het telt per sector
  naar rato mee, zodat de sectoren samen nooit meer vacatures hebben dan het totaal (TECHNIEK en ECONOMIE in Utrecht
  kwamen samen op 21.027 van de 25.225). Het resultaat zegt dat UWV geen opleidingsniveau kent, en de vacatures zijn
  ook per gemeente op te vragen.
- Het arbeidsmarktdashboard telt zo'n gedeeld beroepencluster ook naar rato, net als de chat: de match score en de
  grafiek gediplomeerden tegenover vacatures gebruiken dezelfde gewogen telling per sector (`vacatures_per_sector`).
  Daarvoor konden de sectoren samen boven het provincietotaal uitkomen. `scripts/refresh_sector_mapping.py` kent nu
  alle sectoren van beide indelingen (10 hbo/wo, 17 mbo); opnieuw draaien wist geen sectoren of `_indelingen` meer.
- `get_uwv_vacatures` met een sector houdt drie lagen apart: de ongewogen UWV-aantallen (`uwv_broncijfer`), de
  toewijzing van clusters aan de sector (`lokale_classificatie`, een LLM-classificatie van deze app, met versie en
  model van de mapping) en het gewogen sectorgetal (`gewogen_aandeel`). Eerder stond alles naast elkaar onder de
  UWV-bron en schreef het model de toewijzing aan UWV toe. `vacatures_sector` staat niet meer op het hoogste niveau.
- `get_roa_benchmark` geeft de ROA-prognose tot 2030 ook per arbeidsmarktregio of provincie (bijv. Midden-Utrecht,
  Mbo2 techniek en ict: "matig", landelijk "slecht"). De schoolverlatersinformatie heeft ROA alleen landelijk; het
  resultaat noemt per onderdeel de regio waar de cijfers vandaan komen. Een onbekende regio geeft de geldige namen.
  De mastersectoren ('Master - techniek en ict') heetten onbekend; ze zijn nu op te vragen.
- De arbeidsmarktregio in het instellingsprofiel heet nu zoals UWV en ROA hem kennen: hij volgt uit de gemeente
  van het instellingsadres en de CBS-gebiedsindeling (Gebieden in Nederland 2026), niet meer uit het RPA-gebied
  van DUO. Daar kende ROA 16 van de 27 namen niet (Utrecht-Midden tegenover Midden-Utrecht), zodat
  `get_roa_benchmark` de regio van het profiel weigerde. `scripts/refresh_arbeidsmarktregio.py` ververst de indeling.

### Betrouwbaarheid van antwoorden
- Dezelfde mbo-vraag geeft hetzelfde getal (#653). In veertien mbo-tabellen van CBS (o.a. 85353NED, 85354NED en
  85569NED) koos het model per run "Totaal mbo (incl. extranei)" of "(excl. extranei)": "vmbo → mbo" telde op
  19-10 157.450 mbo-instromers en op 20-10 155.270. Nu kiest de code de ruimste telling, inclusief extranei; de
  telling zonder extranei alleen als de gebruiker daarom vraagt ("zonder extranei", "bol en bbl"), ook eerder in
  het gesprek. De Uitgangspunt-regel, het recept en de code-snippet tonen de telling die geladen is. De tabellen en
  de regel staan in `docs/domeinregels.md`.
- Waar de code de telling zonder extranei verving door de ruimste, levert `get_cbs_data` hem gegrond mee (#658): in
  dezelfde aanroep haalt hij beide totalen op (één CBS-aanroep met twee codes) en bewaart de smallere onder een eigen
  `data_key` in `alternatieve_telling` (label, code, preview, herlaadbaar). De standaardtelling blijft het antwoord;
  het model noemt de andere telling alleen als de gebruiker erom vraagt, en dan met een citatie. Past de aanroep
  met twee totalen niet in een pagina of weigert de bron hem, dan valt `get_cbs_data` terug op de standaard alleen,
  zonder alternatief.
- "Vmbo → mbo" heeft één vaste bron (#667). Dezelfde vraag kreeg CBS 85569NED (83.020) of DUO "Instromende
  mbo-studenten" (96.629): beide juist, met een andere definitie. Nu is het de vaste maat `doorstroom_vmbo_mbo` van
  `get_maat`: CBS 85569NED, mbo-instromers die een jaar eerder in vmbo-leerjaar 3-4 zaten, met de extranei-standaard
  van #653. Het antwoord eindigt met een regel uit code, "**Bron en definitie:**", die ook de DUO-telling (met een
  vmbo-diploma, direct en indirect) en haar definitie noemt. De keuze tussen de opties uit #667 ligt nog bij de
  gebruiker; gebouwd is optie A met B als tekstregel (`docs/domeinregels.md`).
- De kaart (`create_choropleth_map`) tekent nu ook met namen: DUO-kolommen als `PROVINCIE INSTELLING` en
  `GEMEENTE INSTELLING` en elke groepering op een naamkolom, in elke spelling (`'S-GRAVENHAGE`, `HENGELO` voor
  Hengelo (O.), een gemeentenummer). Zonder codes in de kolom gaf de kaart eerder een lege figuur met de melding
  "Kaart aangemaakt (12 provincies)". Het niveau volgt uit wat past, locaties die niet op de kaart staan worden
  genoemd, en past er niets (of past het gekozen niveau niet) dan is het een fout in plaats van een lege kaart (#628).
- `run_analysis` geeft bij een fout een korte, leesbare melding: de regel in het script en de laatste regel van de
  fout, zonder paden van de server. Een deling door nul met numpy-getallen (zoals `df['a'].sum() / df['b'].sum()`)
  eindigde in `KeyError: '__import__'`; dat is nu een `FloatingPointError` met de uitleg dat de noemer 0 is. Een
  uitkomst als `result = df` geeft het model hoogstens zoveel rijen als `query_data` (met `totaal_rijen` en de
  verwijzing naar de `data_key`, waar de volledige tabel staat), en een uitkomst boven 8 MB wordt geweigerd (#629).
- Blijft na de herkansing alleen een getal over dat niet in de opgehaalde data staat (meestal eigen rekenwerk in
  een lang antwoord), dan houdt de app niet meer het hele antwoord in: code haalt de zinnen en tabelrijen met dat
  getal weg, toetst de rest opnieuw en zegt eronder dat er iets is weggelaten. Valt er meer weg dan blijft, of
  klopt de rest niet, dan blijft het antwoord ingehouden. De herkansing vraagt het model nu ook verschillen,
  percentages en aandelen met `compute_kpi` of `query_data` te berekenen. De oorzaakcontrole kent een voorbehoud
  ook in andere woorden ("de data laat de oorzaak niet zien", "vermoedens", "denkbaar", "zou kunnen samenhangen")
  en slaat de herhaalde onderzoeksvraag over (#619).
- Een lang antwoord (drie of meer onderdelen, of meer dan ± 600 tekens) begint met de kern in één of twee zinnen en
  geeft elk onderdeel daarna een kop of een lijst, zodat je op een telefoon kunt skimmen; een kort antwoord blijft
  één alinea. De regel "Onderzoeksvraag:" komt bij een lang antwoord direct na de kern, als gewone regel en niet
  meer als citaatblok (#618).
- Een UWV- of ROA-resultaat is een dataset zoals elke andere (#577): de tabel erachter staat in de store onder een
  `data_key`, met de laadaanroep en de peildatum of versie. Een rapport over een gesprek met vacaturecijfers ziet
  die cijfers nu (het rapport van 8 oktober schreef "geen vacaturegegevens geladen" terwijl de chat ze toonde),
  de bronnenlijst van rapport en dashboard noemt UWV Open Match met peildatum en ROA met versie, het recept haalt
  ze na een herstart terug, de citaties wijzen naar de tabel, en snippet en CSV-export werken erop. Het model kan
  de tabel met `query_data` filteren en met `create_plot` tekenen.
- Onder elke grafiek in een rapport staat een bronregel uit code (#569): bron en catalogustitel, dataset-ID,
  bij een DUO-dataset met meer bestanden het bestand, de periode en de CBS-periodestatus van de getekende
  rijen, en een link naar de open-databron (CBS OData, de DUO-datasetpagina, de RIO-API) die in een nieuw
  tabblad opent. Twee gebruikers vroegen bij een rapportgrafiek waar precies deze cijfers vandaan komen; de
  lijst Bronnen onderaan zei dat niet per grafiek en doorklikken kon niet. Een grafiek zonder herleidbare
  bron zegt "Bron niet vastgesteld". Bestaande rapporten veranderen niet.
- Een rapport of dashboard op een afgekapte bron zegt dat nu ook (#578). De chat meldde het al ("ik kan niet
  uitsluiten dat er in de rest van het bestand nog andere rijen staan"), het rapport op dezelfde data zweeg erover.
  Per afgekapte laadkey staat er één vaste regel uit code, met bron en catalogustitel en het aantal opgehaalde
  rijen: in een rapport vooraan in "Wat dit rapport niet beantwoordt", in een dashboard na de bronnen. De
  controles op het rapport zien alleen de modeltekst. Bestaande rapporten en dashboards veranderen niet.
- Het Bronnen-blok onder een antwoord noemt bij een DUO-dataset met meer dan één tabelbestand ook het bestand
  (#540): de drie hbo-bestanden van `p01hoinges` gaven voor dezelfde instelling en hetzelfde studiejaar 34.751,
  34.754 en 34.755, elk met andere onderdrukte cellen, terwijl de bron er hetzelfde uitzag. Een telvraag via
  `get_maat` gebruikt altijd het leidende bestand; dit maakt een verschil op een ander pad herleidbaar.
- Een zoekhit van `search_catalog` draagt bij DUO-datasets de zoekkaart uit riodata (`zoekkaart`: teleenheid,
  inschrijvingstype, peildatum, uitsluitingen en publicatieregels), zonder lege delen. Het model ziet zo vóór
  `dataset_details` of een bron personen of inschrijvingen telt en hoe kleine aantallen zijn afgerond (#358).
- Nieuwe tool `get_maat` (#188): vaste recepten voor de gewone telvragen. Het model kiest de maat
  (`ingeschreven_personen_ho`, `inschrijvingen_ho`, `eerstejaars_ho`, `deelnemers_ho_landelijk`,
  `mbo_studenten_instelling`) en de afbakening (instelling of sector, vorm, schooljaren); de code lost de
  instelling op in het register, kiest het DUO-bestand (het opleidingsvorm-bestand per sector) of de CBS-codes,
  vertaalt vorm en schooljaar naar de spelling van de bron en laadt en selecteert met dezelfde tools als anders.
  Eén rij per studiejaar, met teldefinitie en het recept erbij; een onbekende instelling, maat of vorm is een fout,
  geen gok. "Studenten" is standaard personen (p01); inschrijvingen (p03) alleen op expliciete vraag, met
  vermelding. De prompt zet `get_maat` vóór `search_catalog`; een key uit `get_maat` komt na een herstart terug
  door het recept opnieuw te draaien, en de snippet is het recept als script.
- Eén bron-ID voor alle drie de bronnen (#356, sluit aan op #370): `duo:p01hoinges`, `DUO/P01HOINGES` en
  `rio:erkenningen` wijzen in `dataset_details`, `get_duo_data`, `get_rio_data` en de scopegrens naar hetzelfde
  record als het kale ID, zoals `cbs:85423NED` dat al deed; eerder gaf zo'n ID "niet gevonden in de catalogus".
  Elke zoekhit en elk detailrecord draagt nu een `status`: `opvraagbaar`, `via_tool`, `alleen_documentatie` of
  `alleen_catalogus` (vindbaar en package-leesbaar, zonder chat-adapter), op één plek beslist. De interne
  bronfilter van het zoeken betekent wat hij zegt: `rio` geeft alleen RIO, `riodata` alles uit de package.
- Nieuwe tool `dataset_profiel(data_key)` (#59, #61): het profiel van een geladen tabel zonder model. Per kolom het
  type, waar hij op lijkt (identificatie, jaar, schooljaar, geocode, categorie, getal, datum, tekst), lege en
  unieke cellen, bereik en kwartielen of de vaakste waarden; voor de tabel het aandeel dubbele rijen en de
  korrel: de kleinste kolomcombinaties (tot drie kolommen) die elke rij apart aanwijzen. Pure pandas
  (`tools/profiel.py`), één keer per key berekend en onthouden zolang dezelfde data onder die key staat. De
  prompt zet het in vóór een som of telling over een tabel waarvan de korrel niet zeker is.
- Nieuwe tool `relatie(data_key, andere_key)` (#63, relatielaag stap 1): wat hangt aan wat tussen CBS, DUO en
  RIO, uit bestaande kennis en zonder model. Per sleutelkolom van een geladen tabel (instellingscode, naam,
  gemeente, provincie, schooljaar, opleidingscode) wat eraan hangt (instellingsregister, CBS-gebiedsindeling,
  RIO) en hoeveel waarden de naslag kent; met een tweede tabel de kolommen die dezelfde sleutel dragen, de
  vertaling van de waarden (`GM0344` ↔ `344`, `2021SJ00` ↔ `2021`), de kardinaliteit en de overlap. Elke
  uitkomst heeft `basis` en `confidence`. De tool koppelt niets; de prompt laat het model hem vragen vóór het
  twee bronnen combineert, en zonder gedeelde sleutel per bron apart antwoorden.
- Het antwoord is in de taal van de vraag en een Nederlands antwoord schrijft decimalen met een komma
  (#326). Een Engelse vraag kreeg soms een Nederlands antwoord (audit 12); nu zegt de code het model in welke
  taal het antwoordt, en een antwoord dat duidelijk in de andere taal is, krijgt één herkansing. Bij een
  korte of gemengde vraag beslist de code niets. In een Nederlands antwoord wordt 6.4 nu 6,4 en 1234.5 wordt
  1.234,5; drie cijfers na de punt blijven een duizendtal (3.303), en datums, versies, codes en verwijzingen
  als "artikel 7.13" houden hun punt. Een Engels antwoord houdt de notatie van het model; de getalcontrole
  leest 12,345 daar als twaalfduizend, zodat zo'n getal zonder bron ook opvalt. Een percentage met een
  decimale punt (9.5%) toetst de controle nu als percentage, zoals het getoond wordt (9,5%). Vaste teksten
  uit de app (weigering, ingehouden antwoord, verduidelijkingskaart, meldingen) blijven Nederlands.
- Het antwoord, het rapport en de meldingen spreken je aan met je, niet met u (#536, uitvoering van besluit
  #326). In één gesprek stond "het getal dat u noemt" naast "je" (testronde 13 oktober); alleen de
  verduidelijkingskaart werd omgezet. Nu zet de code ook het eindantwoord, de conclusie, reikwijdte en
  grafiektekst van een rapport en de meldingen onder een antwoord per zin om: "dat u noemt" wordt "dat je
  noemt", "U kunt" wordt "Je kunt", "jullie instelling" wordt "je instelling". Alleen werkwoorden uit een
  vaste lijst gaan om; een zin met een u-vorm die niet zeker om te zetten is, blijft zoals hij was (liever u
  dan kapot Nederlands). Code, links, HTML, de eigen bronnenlijst van het model en de onderzoeksvraag,
  titel, definities en bronnen van een rapport blijven ongemoeid. Blijft er na de omzetting een u-vorm over,
  dan krijgt het model één herkansing; blijft hij daarna, dan staat er "Let op" onder het antwoord, of krijgt
  het rapport een waarschuwing. Een Engels antwoord blijft ongemoeid. Het besluit en de aanpak staan in
  "Kwaliteit & veiligheid".
- Een vraag met een open slot krijgt haar verduidelijkingskaart nu uit code, vóór het model (#348). Een
  telling bij een plaats die in meer dan één instellingsnaam uit het register zit ("Hoeveel studenten
  heeft Utrecht?") vraagt instelling of woonplaats, met de instellingen uit het register als opties (de
  eigen sector uit het profiel voorop); een kort thema zonder maat ("arbeidsmarkt") vraagt de maat,
  met de catalogusrecords die `search_catalog` bovenaan zet, mits elke term raakt. Dezelfde vraag geeft zo
  altijd dezelfde eerste stap, waar het model de ene run negentien toolaanroepen deed en de andere een
  verduidelijking stelde (audit 12). Geen kaart als de vraag een instelling noemt, het profiel haar bepaalt,
  twee gebieden vergelijkt, of na een beantwoorde kaart. Een vraagvorm met "wanneer", "wie" of "waar"
  telt niet meer als vaag thema. De vaste plannen voor de aanbevolen startvragen wachten op #349.
- De melding bij een onbekende `data_key` noemt als beschikbare datasets alleen nog de keys van het eigen
  gesprek, niet alles wat de gedeelde store voor andere sessies vasthoudt; buiten een gesprek noemt ze geen keys.
  Elke tool van een verbinding, ook in een taak of thread, kent zo de keys van het eigen gesprek (#13).
- Een CBS-selectie op een korte code, zoals `Geslacht` = `4000` (Vrouwen) in de mbo-tabellen 85353NED en
  85354NED, geeft nu rijen. CBS vult de sleutels van een dimensie op tot één breedte (`4000   ` naast
  `T001038`) en toont ze gestript; de gecompileerde filter `Geslacht eq '4000'` matchte daardoor niets en de
  tool meldde "Geen rijen gevonden", waarna het antwoord vrouwen afleidde als totaal min mannen (248.940 in
  plaats van de gepubliceerde 248.930). De server compileert elke vergelijking nu als
  `trim(Dimensie) eq 'code'`, zoals het CBS-package in `prepare_query` ook doet; de sectorgrens van de
  VSV- en woonregiotabellen leest die vorm ook. Een eigen berekening (`run_analysis`) op afgeronde CBS-data
  draagt nu dezelfde afrondingsnoot als `compute_kpi` en `query_data`, en de reproduceer-snippet van een
  gesloten selectie toont de gecompileerde filter in plaats van een aanroep zonder filter (#531, F-10).
- Bij CBS-data noemt het antwoord de datum nu als "CBS heeft deze tabel voor het laatst bijgewerkt op 9 april 2026"
  in plaats van "Deze dataset is actueel tot 9 april 2026"; die zin vroeg de systeemprompt. De datum is de dag
  waarop CBS de tabel het laatst bijwerkte, uit de meegeleverde catalogus (`_laatste_update`), niet het einde van
  de cijfers: welke periode die beslaan, staat in de perioden van de data (#496, F-03).
- Bij een CBS-tabel die afrondt (bijvoorbeeld op 10-tallen) noemt het antwoord een verschil tussen het
  gepubliceerde totaal en de som van de delen nu bij dat totaal, bijvoorbeeld "Exclusief extranei" 465.820 naast
  bol 328.610 + bbl 137.220 in 85353NED/85354NED: het verschil komt van de afronding van CBS, geen rekenfout. De
  systeemprompt vraagt dit; de som zelf schrijft het antwoord niet uit. Zonder afrondingsnoot in de data schrijft
  het antwoord een verschil niet aan afronding toe (#496, F-02).
- Een vage vraag, een kort thema zonder maat zoals "studentenwelzijn", krijgt een zichtbare interpretatie (#514):
  komt er geen verduidelijkingskaart, dan opent het antwoord met "Ik ga uit van de lezing «…»" met de titels van
  de datasets waarop het rust, uit de catalogus, en de uitnodiging om de maat of bron te noemen als iets anders
  bedoeld was. De app zet die zin er in code voor als het model zijn lezing niet zelf benoemde; de systeemprompt
  vraagt het model eerst om een verduidelijkingsvraag of die zin.
- Een antwoord met data opent met een vaste regel "**Uitgangspunt:** …" als de selectie een afbakening vastlegt
  die de gebruiker niet noemde (#620, besluit: altijd tonen). De regel noemt de gekozen instelling met haar
  volledige naam en code ("Universiteit Utrecht (21PD)" in plaats van "Utrecht", naast Hogeschool Utrecht
  dubbelzinnig), de CBS-dimensies die op één waarde liggen (geen totaal), de periode, en bij `get_maat` zonder
  instelling de sector en de vorm. Bijvoorbeeld bij "Waarom zijn er meer studenten informatica?":
  "WO · Informatica · Nederland · 2015/16 t/m 2024/25". De regel komt helemaal uit de toolstappen, niet uit de
  modeltekst, en staat na de interpretatiezin van #514. Hij blijft weg als de vraag (met de gekozen
  verduidelijking) alles al noemt en het antwoord de instelling volledig noemt, bij meer dan drie instellingen
  (dan geen opsomming van instellingen), en bij een vast antwoord. De regel is ook bij een Engels antwoord
  Nederlands, en een periode in woorden ("laatste vijf jaar") telt niet als genoemd.
- `dataset_details` noemt voor een CBS-tabel nu ook de populatie, de sectoren in het profiel, de
  periodecodes met hun CBS-status ("2025/'26 (voorlopig)"), het bereik en de geografische dekking uit het
  contract van de CBS-package (#370), naast de teldefinitie en afronding van #383. Het model kiest zo een
  periode zonder dimensiecall en citeert de bron in plaats van zelf een populatie te raden.
- `cbs:85423NED`, `cbs_85423ned` en `85423NED` zijn in `dataset_details`, `get_cbs_data` en
  `get_cbs_dimension` dezelfde tabel: het contract-ID van de package en de spelling van een model of een
  bewaard recept komen op één plek terug op het bron-ID (#370).
- Server-side preflight op het CBS-contract (#370): na de selectiepoort vraagt `get_cbs_data` aan
  `validate_selection` van de CBS-package of de tabel de selectie kan leveren: bestaat elke code in haar
  dimensie, komt de periode in de tabel voor, en past de code bij de sector waarvoor het model de tabel
  bevraagt (nieuw, optioneel: `selectie.sector`, `mbo`/`hbo`/`wo`; `hbo` met de wo-code `A025297` is
  tegenstrijdig). Alleen een `unsupported`-oordeel houdt de datacall tegen, met per controle de reden en wat
  wél in de tabel staat (`2031/32` → de perioden die er zijn); bronuitval of een onbekende dimensie laat door.
  Een tijddimensie naast `periode` werd al vóór het contract geweigerd.
- Het model schrijft geen OData meer voor CBS (#343, ADR-006). `get_cbs_data` krijgt een gesloten
  `selectie` — per dimensie een code uit `get_cbs_dimension` of `"*"` om uit te splitsen, de periode
  als lijst of bereik (schooljaarspelling wordt in code vertaald), onderwerpen als kolomsleutels — en
  de server compileert daaruit de bronfilter. Een selectie waarin een dimensie noch gepind noch bewust
  uitgesplitst is, wordt geweigerd vóór de datacall, met de ontbrekende dimensie(s) erbij; de rijlimiet
  is een beleidsregel van de server, geen modelparameter. Bewaarde recepten en het herladen/verversen
  van oudere gesprekken blijven werken via het interne `filters`-pad; nieuwe recepten bewaren de
  gecompileerde filter en blijven letterlijk reproduceerbaar.
- Dezelfde selectie in een andere spelling is nu dezelfde selectie (#342). De identiteit van een
  toolaanroep en van een data_key is de digest van het canonieke plan, niet meer de letterlijke
  modeljson: sleutelvolgorde, `__in` met één waarde, hoofd- en kleine letters, `2024/'25` naast
  `2024SJ00` of `2024-2025`, en varianten als `cbs_85353NED` delen één uitvoering, één data_key en
  één snippet, in plaats van vier loads en vier keys voor dezelfde dataset in één gesprek. Een
  schooljaarspelling in een filter wordt vóór het filteren herschreven naar de spelling die de data
  gebruikt; een schooljaar dat niet in een volledige selectie staat, wordt geweigerd met de waarden
  die er wél staan. Keys uit eerdere gesprekken blijven bij verversen en herladen als alias werken.
- Eén DUO-bestand is leidend voor een totaal per instelling. De ho-datasets (p01–p04) hebben per sector drie
  bestanden met dezelfde telling en een andere uitsplitsing, en elk onderdrukt andere cellen: Hanze kwam uit op
  26.362, 26.373 of 26.379, afhankelijk van het bestand. Zonder bestandskeuze laadt `get_duo_data` nu het
  leidende bestand, het bestand dat het minst tekortkomt (gemeten met `scripts/meet_duo_bestandskeuze.py`),
  en niet meer index 0, het geslacht-bestand met de meeste onderdrukte cellen. `dataset_details` markeert
  het leidende bestand, en een ander bestand zegt bij het laden welk bestand leidend is. Bij mbo is dat het
  bestand per instelling en leerweg. Onder Telling staat bij een ondergrens uit welk bestand de totalen
  komen en dat de andere bestanden afwijken. Komen jaren uit de terugblik (Type 'Historie') van de
  mbo-studentprognose, dan zegt Telling dat ze licht afwijken van `mbo-studenten-per-instelling`.
- Een uitsplitsing per groep (bijv. per geslacht) zegt per groep of er cellen met -1 in vallen: alleen dat
  totaal is een ondergrens. Eerder meldde `query_data` dat "totalen" een ondergrens waren, en noemde het
  antwoord ook de groep zonder onderdrukte cel er een. Onder Telling staat de ondergrens nu alleen als een
  genoemd groepstotaal er een is. Bij cellen in meer kolommen noemt de tool cellen en rijen apart ("305
  onderdrukte cellen in 268 rijen"); die werden als rijen geteld.
- Een antwoord op data met DIPLOMAJAAR (ho-gediplomeerden) zegt onder Telling dat DUO niet vastlegt of dat
  een kalender- of studiejaar is: diplomajaar 2023 is niet aantoonbaar studiejaar 2023/24. De kolomuitleg
  zegt hetzelfde. De app zet een diplomajaar niet om naar een schooljaar.
- Staat hetzelfde getal in twee zinnen ("Instelling B had 10.000 … Instelling A had 10.000"), dan krijgt
  elke vermelding een eigen citatie en de ondergrens van haar eigen selectie. Eerder erfde de tweede de
  bron van de eerste.
- Getallen in een arbeidsmarktantwoord krijgen een citatie: UWV-vacatures met provincie, sector en
  beroepencluster en de peildatum, ROA-cijfers met opleiding, indicator, regio en versie. Een landelijke ROA-
  terugval heet in de citatie ook landelijk.
- Een getal dat zowel in een selectie als in een analyse op die selectie staat, krijgt de selectie als
  herkomst in plaats van "herkomst niet vastgesteld". Blijft de herkomst toch onzeker, dan zegt de uitleg
  waarom: het getal staat niet als meetwaarde in de data, of staat er meer dan eens in zonder dat de zin
  aanwijst welke plek het is.
- Een getal uit een eigen berekening (`run_analysis`) telt alleen als bron als de controle vaststelt dat het
  van de data afhangt. Loopt die controle vast, dan geldt elk getal dat niet in de invoer staat niet als bron
  (was: alles bewijs). Een conditionele constante (`987654 if … else 0`) telt niet meer, en een afgekeurd getal
  blijft afgekeurd in een volgende `query_data` of `run_analysis` op dezelfde data.
- Staat er een instelling in het profiel, dan krijgt de chat haar sector (mbo/hbo/wo), instellingscode,
  provincie en arbeidsmarktregio mee uit de DUO-instellingsadressen, in plaats van zelf een provincie te kiezen.
  Bij "mijn regio" gebruikt het antwoord die provincie of arbeidsmarktregio en noemt het welk niveau. Een
  instelling met vestigingen in meer provincies krijgt de regio van haar instellingsadres; een naam die niet in
  de instellingenlijst staat krijgt geen regio.
- Foute en lege DUO-kolombeschrijvingen zijn in de chat gecorrigeerd: `DIPLOMAJAAR` en `SOORT_DIPLOMA` in de
  ho-gediplomeerden gaan over het behaalde ho-diploma, niet de vooropleiding; provincie en gemeente in de
  hbo/wo-bestanden zijn de vestiging, niet de woonplaats van de student; `TOTAAL MBO`, `INSTROOM MBO` en
  `INSTROOM OPLEIDING` hebben een definitie (totaal is alle ingeschrevenen, geen instroom). Zoekt iemand naar
  woonplaats of herkomst in het hoger onderwijs, dan zegt de catalogus bij deze bestanden dat ze daar niet
  geschikt voor zijn.
- Het mbo-diplomabestand, de instroombestanden en de bestanden van mbo-studenten per instelling hebben een
  kolom `PROVINCIE INSTELLING` (adres van de instelling volgens DUO, niet de woonprovincie van de student).
  "Gediplomeerden van ROC Midden Nederland tegenover de andere instellingen in Utrecht" is zo één selectie na
  het laden: drie toolaanroepen in plaats van vijf, zonder tweede bestand of koppeling. Een instelling zonder
  adres krijgt geen provincie.
- De controlemelding over een KPI over de hele selectie noemt bron en periode in woorden
  ("DUO · Ingeschrevenen hbo, 2020/21 t/m 2024/25"), niet de interne sleutel.
- Een lege modelrespons (vaak een contentfilter van de provider) krijgt een vaste uitleg in plaats van
  "stuur je vraag opnieuw", wat dan niet helpt.
- Staat een getal in meer selecties (10.000 bij instelling A én B), dan wijst de zin de selectie aan, niet de
  volgorde van de toolstappen: de citatie wijst naar A, en de ondergrens van A geldt ook als B exact is. Niet te
  onderscheiden kandidaten geven "herkomst niet vastgesteld".
- `query_data` telt de onderdrukte cellen (-1) per jaar binnen de selectie, zodat het antwoord niet een
  bestandsbreed getal of een som over jaren aan één jaar hangt.
- `get_rio_instelling` toetst naast de relatie ook de erkenning zelf op type en bedrijfsstatus op de peildatum:
  een vestiging die uit bedrijf is, telt niet meer mee achter een nog geldige relatie. Een relatie zonder object
  in RIO staat als `niet_te_lezen` in het resultaat, en andere erkenningen onder het bestuur (zoals erkende
  onderwijsondersteuners) als `niet_meegeteld`.
- De DUO-publicatieregel ('1-4 gepubliceerd als 4') blijft zichtbaar; ernaast staan wat het bestand laat zien
  en een status (`volgt`, `conflict`, `niet_vast_te_stellen`) met een melding per oorzaak. De tool zegt niet meer
  dat "een 4 hier een echte 4" is.
- Trekt een controle een antwoord in, dan zegt de melding niet meer dat het "niet klopte met de opgehaalde data"
  (dat gold ook voor stijlcontroles). De ingetrokken versie noemt de reden in gewone taal, en het uitklapblok
  verschijnt alleen als die versie tekst had en anders was dan het eindantwoord. Het log noemt per herschrijving
  welke controle afging. Dat geldt nu ook voor de rapportcontroles op een leeg rapport, een getal zonder bron,
  "geen data" naast een gevulde grafiek en een verwijzing als "resource 3": daar stond `None`. Een controle die
  zelf niet kon draaien, staat in het log onder haar eigen naam als `niet gecontroleerd`, niet als `ok` met een
  los `None` ernaast.
- Minder valse intrekkingen. Het verschil van twee getallen die het antwoord zelf noemt en die uit de data komen
  ("van 478.660 naar 475.460, 3.200 minder") geldt niet meer als getal zonder bron. "Komt uit van … en komt uit
  op …", "begon … eindigde" en "verschil tussen" tellen als vergelijking, zodat het tweede getal niet aan het
  enige genoemde jaar wordt gehangen. Een toolnaam in de Bronnen-sectie haalt de app er zelf uit, zonder
  herschrijving. Het log noemt per antwoord elke controle met haar uitkomst (`CONTROLES`), ook als die `ok` was.
  Een KPI over de hele selectie naast een filter wordt alleen nog gemeld als dezelfde KPI over het filter een
  ander getal geeft; de code rekent dat na.
- Getallen, schooljaren en instellingen in een antwoord worden getoetst aan de data van het gesprek.
- Opleidingsvorm en dataset-ID in een antwoord worden getoetst aan de bron.
- De app zet zelf onder een DUO-antwoord wat de bestanden tellen (personen of inschrijvingen) en
  wanneer totalen een ondergrens zijn (-1-cellen in de selectie); de teleenheid-regex is vervallen.
- Citaties bij getallen wijzen een meetwaarde aan (maatkolom, KPI-uitkomst of analyseresultaat), nooit een
  code, rijtelling of stuk van een key. Elk gecontroleerd getal in een dataantwoord krijgt er een, zodat
  hetzelfde antwoord altijd evenveel citaties heeft; zonder binding staat er "Herkomst niet vastgesteld".
  De uitleg begint met bron en selectie in woorden, met maat, eenheid en stap.
- Grootste daling of stijging komt uit code (`compute_kpi`: `max_drop`, `max_rise`) en niet uit het model.
- DUO-studiejaren hebben een `STUDIEJAAR_LABEL` (2021 = 2021/2022), zodat jaren niet een jaar verschuiven.
- Hoogstens één scopevraag per vraag; daarna redelijke aannames, die het antwoord noemt.
- `run_analysis` weigert overgetypte data en scripts die geen data lezen.
- Een getal in een `run_analysis`-uitkomst dat niet van de data afhangt, telt niet als bron van een getal,
  percentage of citatie in het antwoord: ook niet via een variabele (`a = 987650; result = a + 4 + len(df) * 0`)
  of als df wel gelezen maar niet gebruikt wordt. De app draait het script daarvoor nog twee keer op
  verstoorde data (andere celwaarden, een rij erbij); wat dan gelijk blijft, komt niet uit de data.
- DUO-teldefinitie en publicatieregels (aantallen 1-4 gepubliceerd als 4) komen uit de riodata-catalogus,
  zonder CKAN-aanroep tijdens het gesprek. Kan de package een beschrijving niet lezen, dan meldt de tool dat.
- Kolomdefinities gelden per DUO-dataset: mbo-opleidingsaanbod krijgt geen hbo-codes VT/DT/DU meer.
- RIO-filters worden vóór het request getoetst aan het filtercontract van RIO, ook enum-waarden en datums;
  de melding noemt de geldige codes (bijv. status `G`, niet `OPEN`).
- Een oorzaak in chat of rapport staat er alleen met voorbehoud: telreeksen tonen een verschil of samenhang,
  niet de reden ervan. Een getal uit een tweede telbron geldt niet meer als bewijs van een oorzaak.
- Heeft een DUO-bestand een teldefinitie, dan schrijft het rapport niet ook een eigen afbakening
  ("buiten beschouwing", "exclusief") naast de brontekst.
- Een verschil tussen twee genoemde schooljaren, of een `compute_kpi`-waarde over die jaren, geldt niet meer
  als verkeerd gebonden omdat hetzelfde getal toevallig ook in een ander jaar staat; zo'n antwoord wordt niet
  meer ingehouden. Lijkt een getal in een vergelijking afgeleid, dan volgt een waarschuwing in plaats van intrekken.
- Een vraag naar bestuur, instellingen of vestigingen van één instelling volgt een vaste route in code
  (`get_rio_instelling`: naam → bevoegd gezag → instellingen → vestigingen), met de aantallen uit code.
  Dezelfde vraag geeft zo hetzelfde antwoord (#412).
- Zinnen waarin het model zichzelf herziet ("Mijn tussenzin ... was onjuist") staan niet meer in het
  antwoord, maar in de redeneerkaart (#412).

### Export en reproduceerbaarheid
- "Exporteer al mijn gegevens" in de instellingen (#645, AVG art. 15): één JSON-bestand met alles wat de server
  onder je account bewaart (gesprekken, rapporten en dashboards met hun HTML, feedback, feedback per antwoord en
  datarecepten), via `GET /api/mijn-gegevens/export`. De export wordt rij voor rij geschreven, zodat ook tachtig
  rapporten van een paar MB niet tegelijk in het geheugen staan. `/privacy` en `docs/privacy.md` noemen hem.
- "Verwijder al mijn gegevens" in de instellingen (#646, AVG art. 17): na het typen van "verwijder" verdwijnt in één
  transactie alles wat de server onder je account bewaart (gesprekken, rapporten en dashboards, alle feedback, ook de
  feedback per antwoord met zijn kopie van vraag en antwoord, en datarecepten), via `DELETE /api/mijn-gegevens`. Het
  token wordt ingetrokken, de browser wist zijn kopie en het profiel, en de loginpagina zegt "Al je gegevens zijn
  verwijderd. Je bent uitgelogd." De dialoog biedt eerst de export aan en waarschuwt dat een gedeeld account ook het
  werk van de anderen kwijtraakt. Alleen met een eigen login: zonder login (iedereen is `gast`) ontbreekt de knop en
  antwoordt de server 404. Blijven staan: serverlogs en back-ups van de beheerder, feedback die al van een verwijderd
  gesprek was losgekoppeld (#476) en de kopie op andere apparaten tot je daar uitlogt. `/privacy`, `docs/privacy.md`
  en `SECURITY.md` (S16) beschrijven het.
- Bewaartermijn en opschoning (#485, privacy M5): elke nacht verwijdert een CronJob (`python -m persistence.opschonen`,
  aan op test en playground, uit op productie) gesprekken 90 dagen na het laatste bericht, met hun datarecepten,
  en feedback 90 dagen na het geven (ook de `trace` van feedback per antwoord, maar niet zolang het gesprek bestaat);
  rapporten en dashboards 365 dagen nadat ze voor het laatst zijn opgeslagen of geopend. Instelbaar met
  `BEWAARTERMIJN_GESPREKKEN_DAGEN` en `BEWAARTERMIJN_RAPPORTEN_DAGEN`; een termijn onder de 7 dagen of een ongeldige
  waarde verwijdert niets, en alles gebeurt in één transactie. `--droog` telt alleen. `/privacy`, `docs/privacy.md`
  en de feedbackdialogen noemen de termijnen. Bestaande rapporten tellen vanaf de invoering.
- Het recept bij een kaart tekent dezelfde kaart als de app: het laadt de GeoJSON van het niveau, vertaalt codes en
  namen (ook DUO-spelling en gemeentenummers) naar de gebiedscode, noemt wat niet op de kaart staat en gebruikt
  dezelfde opmaak. Het gaf eerder `px.choropleth_map(df, locations=…)` zonder GeoJSON: een lege kaart (#630).
- De snippet van een grafiek, KPI, selectie of eigen berekening op een eerdere stap herhaalt de stappen van die
  stap in plaats van de rijen ervan in te bakken (#624): eerst de laadstap van de bron, dan de selectie
  (`query_data`), de vaste maat (`get_maat`) of het script van de eigen berekening (`run_analysis`), zodat `df` in
  dezelfde snippet ontstaat en de code opnieuw draait op actuele data. Het script van een eigen berekening komt
  uit het geheugen van de sessie; de database bewaart nog steeds geen script. Alleen zonder bekende keten (na een
  herstart) staat er een kopie van de rijen, met de opmerking dat die niet meegroeit met de bron.
- De knop "Download data als CSV" staat ook onder een antwoord dat via `get_maat` liep (#538): een telvraag
  als "Hoeveel studenten zaten er in 2022 in het mbo?" kreeg sinds `get_maat` geen knop meer, omdat de export
  alleen `query_data` en `run_analysis` als bron kende. De download heet `<titel>_<dataset-id>.csv`, zoals bij
  een selectie via `query_data`; het recept van de maat zorgt dat de export een herstart overleeft.
- De CSV-export (`/api/data/csv?key=`) geeft alleen een tabel uit een eigen gesprek: een key waar deze gebruiker
  een recept van heeft (in het geheugen of bij een opgeslagen gesprek). De datastore blijft gedeeld over alle
  sessies (openbare brondata, met een bovengrens), maar een ingelogde gebruiker kon tot nu toe elke tabel via
  haar key ophalen, ook die van een ander (audit 14 §5). Een vreemde key krijgt dezelfde melding als een
  verdwenen key, zodat de export niet bevestigt dat ze bestaat (#13).
- Elk antwoord en elk rapport draagt een manifest (#345): model (en de providerversie die de
  stream terugmeldde), of seed en temperature het model echt bereikten (een provider zonder
  seed-ondersteuning staat er als "niet toegepast" in), prompt- en catalogusversie, appversie en
  per dataset de dataversie (CBS-bijwerkdatum, Periodestatus van de geladen rijen, herlaaddatum).
  Het rapport en de export tonen het compact als "Verantwoording" onderaan; het manifest bevat
  alleen herkomst, geen vraag- of antwoordtekst.
- Is de data van een gesprek na een herstart van de server weg, dan zegt een mislukte CSV-download dat en biedt
  "Vraag opnieuw stellen" aan. Een rapport of dashboard op zo'n gesprek wordt niet meer op de overgebleven data
  gemaakt: de melding zegt dat de vraag opnieuw moet (was: "Rapport kon niet worden gemaakt").
- Data overleeft een herstart: bij het opslaan van een gesprek bewaart de server per tabel hoe die ontstond
  (de laadaanroep naar CBS, DUO of RIO en de selecties daarop, nooit een script). Een CSV-download onder een
  eerder antwoord haalt ontbrekende data dan opnieuw op bij de bron. Zulke data zegt dat bij elke download: in
  de header `X-Data-Herladen`, als eerste `#`-regel van de CSV en onder de downloadknop ("opnieuw opgehaald op
  <datum>; de bron kan intussen zijn gewijzigd"). Een heropend gesprek kent de tabellen met zo'n recept weer:
  de rapportknop staat dan direct aan, en het rapport haalt ontbrekende data eerst opnieuw op, met een melding.
  Een eigen berekening (`run_analysis`) komt nog niet terug; de foutmelding noemt dan die stap en de key.
  Nieuwe tabel `data_recipes`, aangemaakt bij de start.
- Een dashboard verversen meldt alleen "Data ververst" als elke dataset echt opnieuw is opgehaald. Laadt er
  één niet (bron onbereikbaar, geweigerde tool), dan zegt de melding hoeveel datasets niet laadden en blijft het
  bewaarde dashboard ongewijzigd; eerder ging dat stil door met de oude data. Reproduceren noemt per grafiek de
  waarden die afwijken van het bewaarde dashboard en bewaart de reproductie niet. De bijwerkdatum van een
  CBS-tabel (het anker) komt bij verversen en bij het maken van een dashboard rechtstreeks van CBS, niet meer uit
  de meegeleverde catalogus, en een bijwerking van CBS is zo zonder herstart zichtbaar (#524).
- Code-snippets draaien zelfstandig: ze beginnen met de laadstap van de bron, met bron-ID en filters.
- Code-snippets geven dezelfde uitkomst als de app: filters met dezelfde semantiek, DUO-cellen met -1
  uitgesloten, en ook een KPI-snippet laadt zijn eigen data.
- De CSV-export van een grafiek decodeert binaire Plotly-arrays en weigert kapotte figuren met een reden.
- Een herhaalde toolcall toont zijn grafiek niet twee keer.
- Het model gebruikt standaard temperature 0 en een vaste seed (`TEMPERATURE`, `SEED`).

### Gebruikersinterface
- Valt de verbinding weg tussen twee stappen van een antwoord, dan blijft de tekst die al geschreven was staan, ook
  na verversen (#652). Een antwoord begint vaak met een zin als "Ik zoek eerst de juiste dataset op" en roept dan een
  tool aan; bij de volgende stap schuift die zin naar de redenering, die op een telefoon dan al dicht is. Brak de
  verbinding vóór het eerste woord van die stap, dan toonde het antwoord alleen de vraag, "Redenering" en "Verbinding
  verbroken". Nu staat die laatste zin als deeltekst boven "Probeer opnieuw", ook in een gesprek dat al zo bewaard is.
- De uitleg bij een getal in een tabel (herkomst, #611) wordt niet meer afgeknipt (#657). Sinds tabellen in een
  antwoord zelf scrollen (#626) viel de open uitleg onderaan weg en kreeg de tabel een verticale scrollbalk; nu hangt
  hij buiten de tabel onder het getal en schuift hij mee als je de tabel opzij scrolt.
- Een tik op een provincie of gemeente op de kaart toont naam en waarde (#655), in de chat, de rapportviewer en de
  HTML-download (gemeten op 390 px met aanraking, licht en donker). De waarde staat er als Nederlands getal
  ("Mbo-studenten: 41.500" in plaats van "Mbo-studenten=41.5k"), ook op de kleurenbalk ("40.000" in plaats van
  "40k"); het recept van de kaart tekent hetzelfde. In de download verdween het label direct na de tik: de browser
  stuurt na de klik ook mouseout, en Plotly haalde het label dan weg. Het kaartscript zet het nu terug.
- Op een telefoon is de kleinste tekst nu overal minstens 12,5 px (#650, gemeten op 390 px, licht en donker): "Meer
  laden" in de gesprekkenlijst, de noot in het ⋯-menu, op de homepage het sectielabel, de footerlinks, de disclaimer en
  de licentieregel, en op /dashboards de tekst op de nieuw-kaart en het label "Voorbeeld" en de instellingsnaam op een
  voorbeeldkaart (tot 9,75 px). Alleen de beschrijving op een kaart in /rapporten en /dashboards blijft bewust klein
  (#613). De sneltoets-hint "Ctrl K" naast Zoeken staat niet meer op een aanraakscherm, ook niet op een tablet. De
  CSV-knop bij een grafiek en de footerlinks hadden op een telefoon al een tikvlak van minstens 44 px.
- De afrondingsnoot van CBS ("De aantallen zijn door CBS afgerond op 10-tallen: …") staat niet meer als kleine
  ondertitel in de grafiek, maar als gewone tekstregel onder de grafiek (#651): in de chat, in een rapport (viewer,
  HTML-download en PDF, vóór de bronregel) en in een gegenereerd dashboard (weergave en download). Hij is nu te
  selecteren en te kopiëren, op een telefoon 12,5 px in plaats van 11 px, en de grafiek houdt de 40 px bovenmarge
  die de noot kostte; liggende staven worden er niet meer hoger van. `create_plot` zet de noot in
  `layout.meta.afrondingsnoot`. Een bewaard gesprek of dashboard toont de noot ook als regel onder de grafiek; een
  rapport dat al als HTML is bewaard, houdt de oude ondertitel.
- Het zoekpalet (Ctrl/⌘K) zet de tijd naast de datum van elke treffer ("Vandaag 14:32", "12 okt 09:00"), bij
  gesprekken en rapporten (#654). Twee gesprekken met dezelfde titel, dezelfde vraag twee keer gesteld, waren
  anders niet uit elkaar te houden. "Vandaag" en "Gisteren" tellen nu in kalenderdagen, ook in de gesprekkenlijst:
  gisteravond 23:50 is 's ochtends "Gisteren", niet "Vandaag".
- De voorbeelden op `/rapporten` bevatten geen `<script>`-blokken meer (#654): het frame (`sandbox=""`) blokkeerde
  ze toch, met per script een regel "Blocked script execution" in de console. In een meting met twaalf rapporten
  van drie grafieken ging de pagina-HTML (`outerHTML`) van 406.093 naar 142.057 tekens; het voorbeeld zelf ziet er
  hetzelfde uit.
- Elke tik op "Genereer rapport" geeft een uitkomst (#648): voortgang, een rapport of een melding waarom het nu niet
  kan ("Wacht tot het antwoord klaar is", "Er wordt al een rapport gemaakt", "Even wachten: het nieuwe gesprek wordt
  gestart", "Geen verbinding: …"). Een tik vlak nadat de verbinding wegviel, ging eerder stil verloren: het verzoek
  ging een gesloten verbinding in en de herverbinding zette de knop zonder melding terug. Weigert de server het
  rapport (er loopt nog een antwoord, of de verzoeklimiet is bereikt), dan stopt het wachten meteen met die melding,
  in plaats van tien minuten "Rapport wordt gegenereerd…". Zonder verbinding of tijdens een nieuw gesprek is de knop
  gedimd maar tikbaar (`aria-disabled`). Het rapport van een kaartvraag bevat nu de kaart: de rapportrun kan
  `create_choropleth_map` gebruiken en kent de kaart uit het gesprek; in de viewer en de HTML-download tekent ze als
  SVG, zonder maplibre-worker (#642).
- Het feedbackformulier op een rapport heeft een blok "Over jouw instelling" voor de conferentie: of een PoC
  het komende jaar mogelijk is (1-5), welke dashboardtool en voor welke doelgroepen (meerdere antwoorden, met
  "Anders" en een toelichting), wat CEDA moet oppakken en optioneel contactgegevens voor vervolgvragen. Nieuw is
  het vraagtype `multi`: dat antwoord staat in `feedback.answers` als lijst, niet als tekst; de contactgegevens
  zijn vrije tekst bij het account (`docs/privacy.md`).
- De zoekknop in de balk houdt "Zoeken" en de sneltoets (Ctrl K) op één regel; op een smal venster (rond 1025 px)
  brak de sneltoets over twee regels (#602).
- Het zoekpalet (Ctrl/⌘K, #602) is rustiger vormgegeven: een lichte schaduw in plaats van het blauwe vlak van de
  dialogen, een zoekicoon voor het veld, een duidelijke markering van de gekozen treffer en op een computer de
  toetsen (Esc, ↑↓, ↵) onderaan. Op een telefoon zoomt Safari niet meer in zodra het zoekveld opent: het veld is 16 px
  (#590) en het palet past dus weer in het scherm.
- Elke regel in het Bronnen-blok onder een dataantwoord is een link naar de bronpagina van de dataset (#621): de
  CBS-tabel, de DUO-datasetpagina, het RIO-register, UWV Open Match en de ROA-dataset (AIS 2030). De link komt uit
  de catalogus, dezelfde als onder een rapportgrafiek (#569), en opent in een nieuw tabblad. Op een telefoon is de
  hele regel het tikdoel (minstens 44 px hoog) en past het blok op 390 px. Een regel heeft bewust geen link als de
  catalogus de dataset niet kent of er geen http(s)-adres voor heeft, en in een gesprek van vóór deze wijziging.
  De tekst van de regels, kopiëren en de gespreksexport zijn ongewijzigd.
- De chat krijgt op een telefoon ruim 80 % van het scherm (#596, gemeten op 390×664 zonder toetsenbord; was 43 %).
  Er is één bovenrij van 52 px met een menu (Home, Chat, Rapporten, Dashboard, instellingen, bronnen, privacy,
  uitloggen), de gesprekkenlijst en een ⋯-menu met "Exporteer gesprek". De tabbalk, de aparte gesprekkenbalk en
  de vaste actierij zijn weg. "Genereer rapport" staat onder het laatste antwoord. Het invoerkader is een pil met
  veld en verstuurknop; de modelkiezer staat in de gesprekkenlijst. De disclaimer staat alleen nog op de
  homepage en op desktop onder het invoerveld; op een telefoon staat "geen persoonsgegevens" in de placeholder,
  en de waarschuwing bij een ingetypt persoonsgegeven blijft. De voortgang tijdens een antwoord hangt als pil over
  de onderkant van de berichten, zodat het invoerveld niet verspringt. Desktop is ongewijzigd.
- Op een telefoon verspringt de chat niet meer rond de eerste vraag (#649; CLS 0,27 → 0,03 op 390×844 en 0,04 op
  390×664, nagebootste beurt): het invoerkader houdt een vaste plek van één regel en groeit bij een lange vraag omhoog
  over de berichten, de melding "Verbinding herstellen..." staat erboven in plaats van erin, en de gesprekkenknop in de
  navbar blijft staan als het ⋯-menu verschijnt.
- Op een telefoon schuift je eigen vraag niet meer opzij als een antwoord klaar is (#661). De herhaalknop naast een
  vraag bestond alleen als er geen antwoord liep, dus hij verscheen aan het eind van elk antwoord en maakte elke
  vraag in het gesprek 30 px breder; bij een korte vraag gaf dat CLS 0,38 (nagebootste beurt, 390×844). De knop staat er
  nu altijd en is tijdens een antwoord alleen verborgen. Het landen van een staafgrafiek kost nu 0,012 en van een kaart
  0,017–0,018 (was 0,064–0,072 bij een staafgrafiek met een vraag van 28 tekens).
- Een rapport is op een telefoon leesbaar zonder inzoomen (#571, gemeten op 390 en 375 px, licht en donker):
  een lang woord of een link in de tekst rekt de pagina niet meer op (die werd daardoor uitgezoomd tot 559 px),
  de instellingsbadge staat onder de titel in plaats van ernaast (de titel had nog de halve breedte), een
  grafiek krijgt de volle kaartbreedte en 420 in plaats van 360 px hoogte, en in de grafiek wordt een lange
  titel afgebroken en kleiner, staat de legendatitel boven de items (de legenda was breder dan de grafiek),
  zijn tick- en legendaletters 11 px en worden lange namen op de y-as van liggende staven afgebroken (het
  plotvlak was nog 64 px breed). De kleinste letters (sectiekoppen, verantwoording) zijn 12 px. Bestaande
  rapporten veranderen niet.
- Een rapport volgt de weergavekeuze van de app (Instellingen: systeem, licht, donker) in plaats van alleen de
  voorkeur van het besturingssysteem (#568). Wie in de app 'Licht' kiest op een donker systeem, kreeg een donker
  rapport, en omgekeerd. Bij 'Systeem' blijft de OS-voorkeur beslissen, net als voor de download; een rapport
  van vóór deze wijziging kent de keuze niet en blijft de OS-voorkeur volgen. Ook de voorbeeldkaarten in de
  rapportenlijst volgen de keuze.
- De inlogkaart staat op een telefoon in het midden van het zichtbare scherm (#499): de pagina volgt `100dvh`
  (zichtbare hoogte) met `100vh` als terugval, zodat de verborgen adresbalk de kaart niet naar de onderrand duwt.
- Privacy-informatie in de app (#477): de pagina `/privacy` zegt wat naar de externe AI-dienst gaat, wat de server
  en de browser bewaren, wat in het log staat en wat je zelf kunt verwijderen of exporteren. Zij is vóór het
  inloggen te lezen via een link op de loginpagina, en verder via de voettekst, de regel onder het invoerveld en
  de instellingen (die nu ook zeggen dat instelling en functie alleen in de browser staan en als context naar de
  AI-dienst gaan). Dezelfde tekst staat in `docs/privacy.md`. Verwerkingsverantwoordelijke, verwerkersovereenkomst,
  regio en bewaartermijn staan als open punten op de pagina, niet als feit.
- `/privacy` en `docs/privacy.md` noemen de deelnemende instelling als verwerkingsverantwoordelijke (#553): een
  privacyvraag gaat naar die instelling. Verwerkersovereenkomst, regio, bewaartermijn en DPIA blijven open punten.
- Onder de opties van een verduidelijkingskaart staat "Anders formuleren": een klik zet je oorspronkelijke vraag
  terug in het invoerveld, om aan te passen en opnieuw te stellen. Er gaat niets vanzelf weg en de gekozen optie
  blijft staan; wie meteen een optie kiest, merkt er niets van (#494).
- Wie een gesprek verwijdert, leest in de bevestiging dat een rapport van dat gesprek blijft bestaan en los te
  verwijderen is via Rapporten (#513). Een rapport is een eigen kopie met de vraag als titel; het verdwijnt
  bewust niet mee met het gesprek.
- De modelkiezer onder het invoerveld gebruikt gewone taal (#496, F10): "Sonnet 5.5 — voor de meeste vragen" in
  plaats van "Sonnet 5.5 (Foundry) — Azure AI Foundry — gebalanceerd". Wie het model draait, staat er als rustig
  bijschrift naast of onder, altijd zichtbaar: "Via Microsoft Azure AI Foundry". `GET /api/settings/config` geeft
  daarvoor per model een veld `provider`. Twee modellen die hetzelfde zouden heten (hetzelfde model via twee
  providers) krijgen hun provider tussen haakjes. Dezelfde kiezer staat in het dashboardvenster.
- Grafieken met veel of lange categorieën blijven leesbaar in chat, rapport en dashboard. Een staafgrafiek met meer
  dan acht categorieën of namen langer dan twaalf tekens (instellingen, sectoren) krijgt liggende staven: de naam staat
  als gewone tekst naast de staaf, het getal in de staaf als het past, en de grafiek groeit mee in hoogte in plaats van
  achttien namen 90° gedraaid onder een plotvlak van 60px te zetten. Eén staaf uitlichten kan zonder `color_by` en
  geeft geen legenda meer die de as herhaalt. De legenda staat horizontaal onder de grafiek in plaats van ernaast,
  waar hij een derde van de breedte kostte en op een telefoon bijna alles; ook opgeslagen gesprekken tonen hem daar.
  In een rapport op een telefoon staat de grafiek zonder dubbele kaartmarge.
- Na een verlopen of ongeldige sessie staat op het inlogscherm nu "Je sessie is verlopen. Log opnieuw in." (#499), en
  de invoervelden van het inlogscherm volgen het donkere thema in plaats van wit te blijven.
- Uitloggen of een verlopen sessie terwijl de app net het token vernieuwt, laat geen nieuw token meer achter in
  de browser en plant geen volgende vernieuwing meer in (#499).
- Met inloggen op wachtwoord (zonder SRAM) eindigt de sessie nu ook als alleen de chatverbinding het token
  weigert, in de chat en in het dashboardvenster (#499); eerder gebeurde dat pas bij de volgende actie. De app
  vraagt dat na bij het nieuwe `GET /api/auth/session` (204 of 401, zonder gebruikersgegevens), dat er met en
  zonder SRAM is.
- Instellingen zoeken met een typefout ("Hogescool Utrecht") zegt nu "Bedoel je Hogeschool Utrecht?" met tot drie
  dichtstbijzijnde namen om op te klikken, in plaats van alleen "Geen instellingen gevonden" (#496, F04).
- Een zoekterm van meer woorden vindt die suggesties nu ook per woord, met een typefout per woord en in elke
  volgorde (#533): "universiteit vam" geeft "Bedoel je Universiteit van Amsterdam, Vrije Universiteit Amsterdam?"
  in plaats van alleen "Geen instellingen gevonden". Elk woord moet in de naam terugkomen; een vulwoord als "van"
  mag ontbreken, en een half getypt woord telt als begin van een woord ("uni amst").
- Boven een antwoord dat na controle is aangepast staat nu "Eerste versie van dit antwoord is aangepast na
  controle — bekijk wat er veranderde" (bij meer versies "2 eerdere versies van dit antwoord zijn aangepast na
  controle — …"), in plaats van "Eerdere versie ingetrokken na controle", wat als interne ruis las. Het blok blijft
  standaard dicht; de reden en de eerdere tekst staan er ongewijzigd in (#496, F-01).
- Die kopregel belooft niet meer "bekijk wat er veranderde", want het blok markeert geen wijzigingen: hij zegt
  nu "— bekijk de eerdere versie en de reden" (bij meer versies "— bekijk ze en de reden") (#566).
- Een gesprek verwijderen is acht seconden ongedaan te maken (#493): na het bevestigen verdwijnt het gesprek
  meteen uit de lijst en toont een toast "Gesprek verwijderd" met "Ongedaan maken"; de verwijdering op de server
  gaat pas als die tijd om is, of direct bij het sluiten van de tab. Ongedaan maken zet het gesprek met zijn
  titel op zijn plaats terug. Verwijderen blijft echt verwijderen: de lijst zonder het gesprek staat al lokaal,
  en de lokale kopie van een open gesprek gaat weg zodra de tijd om is.
- Onder elk gewoon antwoord met data staan tot drie vervolgvragen als knoppen (#364). Een klik zet de vraag in het
  invoerveld, waar je haar aanpast of verstuurt; er gaat niets vanzelf weg. Of er vervolgvragen komen, hangt niet
  af van een keuze van het model (#539): de app biedt ze zelf aan, uit de voorbeeldvragen in de catalogus van de
  datasets die het antwoord laadde, en alleen vragen die de chat kan beantwoorden: binnen mbo/hbo/wo, zonder "mijn"
  of "onze", zonder ruwe veldnamen, codes of dataset-ID's, zonder verwijzing naar "dit" of "de data", zonder
  aantallen uit een RIO-register, en vindbaar met de catalogus. Geen vervolgvragen na een verduidelijkingsvraag, een
  weigering, een ingehouden, leeg, afgekapt of afgebroken antwoord of een deelantwoord, en alleen onder het laatste
  antwoord. De "Verken …"-voorbeeldvragen sturen hun vraag nog steeds meteen.
- Een gesprek verwijderen vanuit de zoekresultaten in de zijbalk werkt nu net zo (#529): de treffer verdwijnt
  meteen, de toast "Gesprek verwijderd." biedt "Ongedaan maken" en de server verwijdert pas na acht seconden.
  Dat geldt ook voor een gesprek dat niet in de geladen lijst staat; daar gebeurde eerst niets. Ongedaan maken
  zet de treffer op zijn plaats terug, een nieuwe zoekopdracht binnen de bedenktijd toont hem niet. Is het
  gesprek nergens meer te vinden, dan meldt de app "Gesprek verwijderen is mislukt. Probeer het opnieuw."
- Een verwijderd open gesprek komt na verversen niet meer terug (#530): het sluiten of verbergen van de tab en
  een antwoord dat daarna nog afrondt schreven het opnieuw in de lokale opslag. Het blijft op het scherm staan
  tot een nieuw gesprek; pas een nieuwe vraag daarin wordt weer bewaard. Ongedaan maken bewaart het meteen weer.
- Een antwoord dat na het verwijderen van het open gesprek nog afrondt, of het verlaten van de pagina, zet dat
  gesprek ook niet meer terug op de server of in de gesprekslijst (#535). Een nieuwe vraag binnen de bedenktijd
  blijft lokaal bewaard; voorheen wiste het verlopen van de bedenktijd die kopie toch.
- Een ververs van een dashboard zonder datarecept meldt niet meer "Data ververst" maar "Bij de bron is niets
  opgehaald: dit dashboard heeft geen datarecept; de grafieken zijn opnieuw getekend uit de data in het
  geheugen", als waarschuwing (#528, vervolg op #524). "Data ververst" staat er alleen als er bij de bron iets
  is opgehaald.
- Persoonsgegevens in de invoer (#478): onder het invoerveld staat dat een vraag naar een externe AI-dienst gaat
  en dat je geen persoonsgegevens invoert. Lijkt een concept een BSN (elfproef), e-mailadres of telefoonnummer te
  bevatten, dan zegt een waarschuwing dat voor het versturen; versturen blijft mogelijk. Zo'n vraag krijgt als
  gesprekstitel "Gesprek (persoonsgegevens weggelaten)", en dus ook die exportbestandsnaam; de terugvaltitel van
  een rapport doet hetzelfde. De systeemprompt heeft één regel over persoonsgegevens en kleine aantallen.
- Een tab sluiten of verbergen tijdens een lopend antwoord bewaart nu de tekst tot het laatst ontvangen fragment (#520):
  de bewaarstap leest ook de nog niet getoonde tekst mee, en sluiten op Safari/iOS (`pagehide`) bewaart ook als de
  tab nog als zichtbaar geldt.
- Een volle lokale opslag meldt zich nu ook bij de gesprekslijst (#521, vervolg op #511): één waarschuwing "De lokale
  opslag is vol: de gesprekslijst kan na verversen korter zijn.", los van die over het open gesprek. De lijst wordt
  niet ingekort; de server bewaart alle gesprekken. Een gesprek dat zonder grafieken is bewaard, zegt dat na
  verversen ("Dit gesprek is niet volledig bewaard: grafieken ontbreken na verversen."). Past ook dat niet, dan komt
  een oudere momentopname niet meer terug alsof hij actueel is. Meldingen tegelijk staan onder elkaar in plaats van
  over elkaar heen.
- Kleine restpunten uit testronde 9 oktober (#496): de CSV van een grafiek heet naar de titel van die grafiek in
  plaats van altijd `Grafiek_aangemaakt.csv`, en de hernoem- en verwijdericoontjes in de zijbalk staan in een smal
  venster altijd zichtbaar, ook met een muis.
- Elke CSV-export heet nu `<titel>_<dataset-id>.csv` (#533): de globale CSV-knop en "Tabel N als CSV" naar de
  catalogustitel van de dataset (`Mbo_studenten_naar_niveau_leerweg_herkomst_85354NED.csv` in plaats van
  `85354NED.csv`), de CSV van een grafiek naar de grafiektitel met het dataset-id erachter. Kent de catalogus de
  dataset niet, dan is het alleen het id; een grafiek zonder dataset houdt `<titel>.csv`.
- De rapportviewer is nooit meer een leeg vlak (#533): zolang een rapport rendert, staat de inhoud als bezig
  (`aria-busy`) naast de melding "Rapport wordt geladen…", en een rapport zonder inhoud zegt "Dit rapport heeft geen
  inhoud." in plaats van een wit kader.
- Blijft het kader van een rapport leeg, of geeft het na 15 seconden nog geen teken van leven, dan staat er tussen de
  titelbalk en het rapport "Zie je dit rapport niet? Download het als HTML." (#541), met een knop die hetzelfde
  bestand downloadt als "Download als HTML". Een rapport dat wel iets toont, krijgt de melding niet.
- De gesprekslijst in de zijbalk haalt alleen id, titel en tijdstip op, niet meer de volledige berichten met
  figuur-JSON van elk gesprek (#509); een gesprek haalt zijn berichten pas op bij het openen
  (`GET /api/conversations/{id}`), met "Openen…" in de lijst en een melding als dat mislukt. De lokale kopie
  van de lijst bevat geen berichten meer, zodat ze niet met het open gesprek om de localStorage-ruimte strijdt.
- Wifi uit en weer aan tijdens een vraag laat in de chat en de dashboardchat één verbinding over (#522): de
  melding "Verbinding herstellen..." verdwijnt zodra die open is, en het late sluiten van de oude verbinding
  breekt een nieuwe vraag niet meer af. Een stil weggevallen verbinding wordt na de hartslag meteen gemeld; een
  gezonde verbinding blijft staan als de server tot 5 s nodig heeft om een lopend antwoord te stoppen.
- Wie offline gaat, ziet in de chat en de dashboardmaker meteen "Je bent offline. Verbinding herstelt zodra je
  weer online bent.", ook als de verbinding dat zelf nog niet gemerkt heeft en ook midden in een vraag (#532).
  Die melding en "Verbinding herstellen..." staan in een live region die altijd klaarstaat, zodat een
  schermlezer ze aankondigt; in de dashboardmaker werden ze tot nu toe niet voorgelezen. Op een smal scherm
  loopt de tekst door op een tweede regel.
- Het invoergebied op een telefoon is flink lager (#527): "Exporteer gesprek" en "Genereer rapport"
  staan op één compacte rij in plaats van gestapeld, de paddings van invoerkader en footer zijn op
  mobiel terug, de tabbalk is iets lager (tap targets blijven ≥44px) en verdwijnt zolang het
  invoerveld focus heeft (toetsenbord open) — die hoogte gaat naar de berichten. Samen scheelt dat
  ruwweg 100px; met het toetsenbord open nog eens de hele tabbalk.
- Antwoorden staan niet meer in een bubbel (#525): de tekst van de assistent staat als lopende tekst op
  de paginagrond, alleen het bericht van de gebruiker houdt de blauwe bubbel. Op een telefoon verdwijnen
  ook de avatars en wordt de zijruimte kleiner, zodat een antwoord de volle schermbreedte krijgt; een
  foutmelding houdt haar eigen gekleurde kader.
- Houdt de controle een rapport tegen, dan staat er een vaste zin in gewone taal in plaats van de technische
  controlemelding met getallen (#515). Eronder staan twee knoppen: "Opnieuw proberen" maakt het rapport opnieuw,
  "Vraag opnieuw stellen" stelt de laatste vraag nog eens. Wat de controle vond, staat alleen in het log.
- Een vervolgvraag typen na het eerste antwoord liep traag, vooral met grafieken in het gesprek: elke toetsaanslag
  parseerde alle antwoorden opnieuw en tekende alle grafieken opnieuw. Het invoerveld bewaart nu zelf wat je typt,
  en een antwoord of grafiek wordt alleen opnieuw getekend als het zelf verandert. In een testgesprek met drie
  grafieken ging de scripttijd per toetsaanslag van 53 naar 2 ms (productiebouw, normale processorsnelheid).
- Zonder instelling in het profiel tonen de suggesties alleen algemene vragen over de open data, één of twee
  per categorie; een vraag over "onze instelling" eindigde daar in een scope-weigering. Met een profiel staat elke
  vraag er één keer, met de tekst voor de eigen sector. De uitvalvraag voor hbo en wo gaat over het
  diplomarendement uit de CBS-cohorten, de UWV-vraag staat er nog maar één keer, onder Arbeidsmarktmatch, en
  de herkomstvraag voor mbo noemt de woongemeente.
- De suggestievragen over de arbeidsmarkt beloven niet meer dat gediplomeerden "aansluiten" op vacatures:
  ze vragen naar de UWV-vacatures per provincie (momentopname mei 2023) en de landelijke ROA-prognose. De
  uitvalvraag gaat over landelijke uitval, want voor hbo en wo bestaat uitval niet per opleiding.
- De suggestievragen hangen af van de sector van de instelling in het profiel. De herkomstvraag staat alleen bij
  mbo, want alleen de mbo-bestanden kennen de woonplaats van studenten. Een universiteit wordt vergeleken met
  het wo als geheel in plaats van met haar provincie, waar ze meestal de enige is. Zonder bekende instelling
  staan alleen de vragen die voor elke sector te beantwoorden zijn.
- Onder elk dataantwoord staan vaste bouwstenen in een vaste volgorde: Citaties (hoeveel getallen, en hoeveel
  zonder vastgestelde herkomst), Telling, Export (de CSV-knoppen) en Bronnen, elk gevuld of met "n.v.t.". De
  bronnenlijst komt uit de stappen van het antwoord (titel, periode en dataset-ID per geladen dataset); de eigen
  Bronnen-sectie van het model vervalt. Kopiëren en de gespreksexport nemen de lijst mee.
- De titel van een rapport is de vraag van de gebruiker, met de instelling erachter; het model schrijft hem
  niet meer, dus vijf keer hetzelfde rapport heeft één titel.
- Eén redeneerkaart per antwoord in plaats van een kaart per stap.
- Een vraag tijdens een lopend antwoord krijgt een melding, de getypte tekst blijft staan.
- Een onbekend pad toont een 404-pagina; een uitgeschakelde dashboardroute meldt dat hij nog niet beschikbaar is.
- Hernoem- en verwijderknoppen hebben een `aria-label`.
- De technische key van een citatie (`data_key`) staat dichtgeklapt onder "Technische details", onderaan de uitleg.
- Stuit een antwoord na alle pogingen op de rate limit, dan blijven de al opgehaalde stappen in het
  gesprek; een nieuwe poging bouwt erop voort.

### MCP-server
- De catalogus is ook vanuit een MCP-client (Claude Desktop, Cursor, VS Code) te doorzoeken, zonder de
  chat-app: `mcp_server.py` biedt `search_catalog`, `dataset_details` en `dataset_counts` via stdio, met
  dezelfde schema's en dezelfde uitvoering als in de chat (scopegrens mbo/hbo/wo, bron-ID's, status per
  record). Optionele extra `mcp` (`uv sync --extra mcp`), niet in het image; geen sleutel nodig. De
  datatools blijven bij de chat (#41, stap 1). Zie `docs/mcp.md`.
- Elk resultaat van de MCP-server draagt een `bewijs`-blok (bron, dataset-ID, selectie, peildatum, catalogusversie,
  verwijzing; `maat` en `waarde` voor de datatools van #708) en een `vervolg` met een link naar de volledige app (#707).
  Bij een MCP-client schrijft het model van de client het antwoord en draaien de controles van de chat niet; zo blijft
  elk overgenomen gegeven herleidbaar. Tekst van de bronnen komt ontsmet mee (`[ ]` met een backslash, `< >` als
  entiteit), zodat een link of tag uit een beschrijving in de client niet actief wordt; een resultaat in gewone tekst
  staat als `melding` in hetzelfde JSON-object. Toolbeschrijvingen en instructies zeggen: "Noem geen getal dat niet in
  een toolresultaat staat." Nieuwe sleutels, geen breaking change; `APP_URL` kiest de omgeving (standaard playground).
- `docs/edugenai.md` beschrijft de geplande koppeling met EduGenAI (#710): wat hij wel en niet doet, waarom de
  betrouwbaarheid lager is dan in de eigen app (het model van EduGenAI schrijft het antwoord en onze controles draaien
  niet), welke claim we wel en niet doen, concepttekst voor label, beschrijving en persona (af te stemmen met Npuls,
  #711) en de gegevensstroom met bewaartermijnen voor de DPIA.

### Beheer
- Renovate stelt geen digest-pin meer voor het eigen image in `charts/onderwijsdata-chat/values.yaml` voor (#656): de
  lege `tag` is bewust, het chart-appVersion bepaalt de tag.
- `HEAD` op een pad van de app (`/`, `/login`, `/openapi.json`) antwoordt als `GET`: 200 met `text/html`, zonder
  body (#654). Het gaf een JSON-405, zodat de HEAD-respons `application/json` beloofde voor een pad dat HTML geeft.
  `HEAD` op `/health`, `/ready`, `/version` en alles onder `/api` blijft 405, zoals voorheen.
- Wekelijkse bron-ping in CI (#627): de geplande job `bron:ping` roept elke bron één keer aan door de toollaag van de
  chat (CBS, DUO, RIO en de GeoJSON van de kaart; `scripts/bronping.py`, zonder LLM en zonder testomgeving) en faalt
  zodra één bron niet antwoordt. RIO verwijderde API v2 op 19 oktober en dat viel pas op in een chatbeurt, omdat
  pytest de bronnen mockt en `/health` er geen toetst. Een geplande pipeline op `main` bouwt en rolt niets meer uit:
  elke regel op `main` sluit haar uit, ook die van de SBOM- en failure-jobs van de SDP-componenten.
- Afspraken voor de testomgeving (#488): een eigen account per tester en per auditspoor, geen persoonsgegevens in
  een vraag, en opruimen na een ronde (`docs/test-environment.md`). Een test toetst dat gesprekken, werkboeken,
  rapport- en antwoordfeedback en de CSV-export per account gescheiden zijn.
- De DUO-domeinregels staan in één bestand, `data/domeinregels.toml` (#363): de −1-sentinel, de correcties op
  kolombeschrijvingen, de ho-bestanden waarvan de plaats de vestiging is en de OPLEIDINGSVORM-codes. Elke regel
  heeft een id, een bron en een controledatum. Een databeheerder wijzigt een regel met een MR op dat bestand,
  zonder Python; de tests lopen vanzelf over elke regel en tonen dat de dataset en kolom in de gepinde catalogus
  staan en dat de regel in de tools zichtbaar is. Een nieuwe of gewijzigde kolomcorrectie of herkomstregel
  verandert de catalogus, dus hoort er een nieuwe meting van de retrieval-baseline in dezelfde MR. Een ongeldig
  bestand laadt niet, met een melding die de regel noemt, en de app start dan niet; zo weigert het laden ook een
  regeleinde of onzichtbaar teken in een tekst die de tools doorgeven (alleen de bron mag over meer regels
  lopen). Het gedrag van de chat verandert niet. Uitleg: `docs/domeinregels.md`.
- Feedback per antwoord (👍/👎) van een verwijderd gesprek hangt niet meer aan de gebruiker (#476, privacy M2):
  gesprek verwijderen zet in `answer_feedback` de gebruikersnaam op `verwijderd` en het gesprek-id op een willekeurige
  waarde (één per verwijderd gesprek). Oordeel, toelichting en trace blijven voor het team, ook in
  `scripts/antwoordfeedback.py`; het oordeel komt niet meer terug bij het oude gesprek-id. De 👎-vorm zegt wat er
  bewaard wordt. Feedback van gesprekken die al eerder zijn verwijderd, wordt bij de eerste start eenmalig op
  dezelfde manier ontkoppeld (`476_ontkoppel_feedback_zonder_gesprek`).
- De chat heeft een berichtlimiet (#444, SECURITY.md S5): `CHAT_RATE_LIMIT` verzoeken die het model kosten
  (vraag, verduidelijking, dashboard, rapport) per `CHAT_RATE_WINDOW_S` seconden, standaard 30 per 10 minuten,
  per gebruiker en zonder login per verbinding. Daarboven ziet de gebruiker "Te veel verzoeken in korte tijd.
  Probeer het over N seconden opnieuw." en start er geen modelaanroep; voorbeeldvragen tellen niet mee.
- De AST-controle van `run_analysis` weigert ook een stdlib-module die als attribuut van pandas of numpy te
  bereiken is (`pd.io.common.os`, `pd.compat.sys`, #443): `os.getpid()`, `os.getcwd()` en `os.environ` waren zo
  nog bereikbaar, al draait het script in een eigen proces zonder omgeving, netwerk of schrijfrechten. De
  beveiligingsdocumentatie beschrijft nu de twee lagen zoals ze zijn, inclusief wat de sandbox niet is (geen
  seccomp of container) en wat de pod-limieten moeten dragen. Dezelfde regel geldt nu ook in een string: pandas
  lost `@naam` in `df.query`/`df.eval` en elke naam in `pd.eval` op in de variabelen van het script, en
  `df.eval('@pd.io.common.os.getpid()')` gaf het pid, de werkmap en de (lege) omgeving van het kindproces terug.
  Zo'n expressie wordt op dezelfde tokens geweigerd; een `@variabele` of een kolomnaam in backticks blijft gewoon
  pandas. De testomgeving krijgt dezelfde pod-limieten als playground (2 GiB, 1 CPU): met de chartstandaard van
  1 GiB zou een script dat de 1 GiB van het kindproces benut de hele server laten stoppen.
- De SRAM-gebruikerscache (naam, e-mail, organisatie per ingelogde gebruiker, voor na een herlaad van de pagina)
  is begrensd (#487, privacy M4): een rij vervalt na `SESSION_MAX_HOURS` en boven duizend gebruikers gaat de
  langst niet gebruikte eruit. Eerder groeide ze tot een herstart. De keuze voor `sub` als sleutel en gehashte
  wachtwoorden blijft een besluit in #487.
- Rapporten en dashboards laden Plotly van de eigen server in plaats van `cdn.plot.ly` (#486, privacy M3/L1):
  een kijker stuurt geen IP, user-agent of referrer meer naar een Amerikaanse CDN. De gebundelde plotly.js
  wordt als asset uitgeleverd, nieuwe rapport-HTML verwijst daarnaar (één keer, in de head), al opgeslagen
  rapporten met de CDN-URL worden bij het tonen herschreven, en de download haalt diezelfde Plotly op en zet
  haar inline zoals al gebeurde. De CSP noemt geen CDN-hosts meer (`cdn.plot.ly`, `cdn.jsdelivr.net`); een
  test houdt dat zo.
- Log-hardening, vervolg op #475 (#502): foutregels van tools, het herladen, de sandboxcontrole, het dashboard
  en de provider-timeout noemen op WARNING en ERROR alleen het type en een kenmerk (`fout_len=… fout_hash=…`),
  de tekst staat op DEBUG; een dataset-ID dat het model opgeeft staat alleen letterlijk in het log als de
  catalogus het kent; elke logregel van een chatverbinding draagt een kort verbindings-ID (`verbinding=…`,
  in JSON als eigen veld), zodat de regels van één verbinding te koppelen zijn zonder gebruikersnaam of
  gespreks-ID; met `LOG_HASH_SECRET` is de hash in logregels een HMAC in plaats van een kale SHA-256.
- Log-hardening, restpunt van #502: de interne-foutregel (`log_interne_fout`) noemt op ERROR alleen het
  fout-ID, waar het misging, het type en een kenmerk (`fout_len=… fout_hash=…`); de traceback staat onder
  hetzelfde fout-ID op DEBUG. Het fout-ID dat de gebruiker ziet, blijft werken. De CBS-meldingen "… ophalen
  mislukt" (DataProperties, TableInfos, dimensies) noemen het type en een kenmerk in plaats van de fouttekst
  met de request-URL, en de sandbox-regel bij een script zonder uitkomst noemt de returncode en een kenmerk
  van stderr (`stderr_len=… stderr_hash=…`); de tekst zelf staat op DEBUG.
- Log-hardening, rapportregels van #502: een mislukt rapport logt op ERROR het fout-ID, het type en een kenmerk
  (`fout_len=… fout_hash=…`) in plaats van een traceback met de fouttekst, die modeluitvoer kan citeren; de
  traceback staat onder hetzelfde fout-ID op DEBUG. De melding "Sampling-ondersteuning … niet vast te stellen"
  noemt het type en een kenmerk in plaats van de providerfout. Tests houden elke INFO+-regel van het rapportpad
  vrij van vraag, antwoord, toolargumenten en fouttekst.
- Log-hardening, restpunt van #475/#502 (#580): een dataset-ID dat de catalogus niet kent, staat ook in de
  WARNING-regels van de scopegrens ("niet in de catalogus") en van `dataset_details` ("dataset_details miss")
  alleen als lengte en hash (`id_len=… id_hash=…`), niet letterlijk; een regeleinde in zo'n ID splitst de regel
  niet meer. Een bekend ID blijft letterlijk; de tekst richting het model is ongewijzigd.
- Restpunten van de robuustheidsronde van 16 oktober (#607). `GET /api/settings/config` (de modellijst) vraagt met
  inloggen aan een geldig token, zoals de andere `/api`-routes, en geeft anders 401; zonder inloggen blijft het
  voor `gast`. De loginpagina vraagt de lijst niet op. `POST /api/auth/refresh` antwoordt in het Nederlands ("Token
  ontbreekt", "Ongeldig of verlopen token" in plaats van Duitse meldingen), en een onbekend gesprek geeft "Gesprek
  niet gevonden". De CSV-export van een tabel en van een grafiek zet ook een `'` voor een cel, kolomnaam of
  reeksnaam die met een tab of een CR begint (OWASP, CSV-injectie), naast `= + - @` (#483); een cel met een CR
  staat tussen quotes, zodat ze geen rij splitst.
- Laatste Engelse foutmeldingen van de API (#637). Ongeldige invoer (een `limit` buiten 1–50, een lege titel,
  `POST /api/auth/refresh` zonder body) geeft 422 met één Nederlandse zin in `detail` in plaats van pydantic's lijst,
  die de verstuurde waarde herhaalde en "Field required" of "Input should …" zei. Een onbekende `/api`-route geeft 404
  "Niet gevonden" (was "Not Found"), een verkeerde methode 405 "Methode niet toegestaan" met de `Allow`-header. Geen
  melding noemt het pad of de invoer; wat een route zelf meldt ("Gesprek niet gevonden" en dergelijke) blijft gelijk.
  Een WebSocket-frame met een onbekende actie, zonder `action` of met een lijst als `action` krijgt direct een
  foutframe ("Onbekende actie. …") in plaats van stilte tot de time-out van de client; de verbinding blijft open.
- De datastore in het geheugen heeft een bovengrens (#13): `STORE_MAX_MB` (standaard 512). Daarboven gaan de
  langst niet gebruikte tabellen eruit, met hun metadata en onderdrukte-celtelling; het log noemt de key en de
  omvang. Een gesprek dat zo'n tabel nog nodig heeft, haalt haar uit zijn recept terug zoals na een herstart.
  Openbare brondata blijft gedeeld tussen sessies; lezen maakt een tabel weer de jongste.
- Databaseaanroepen van de REST-handlers (gesprekken, werkboeken, feedback, token verversen) en de
  readiness-check draaien in de threadpool in plaats van op de event loop (#508): een trage database
  zette tot nu toe elke lopende chat-stream van alle gebruikers stil. Postgres-verbindingen worden
  hergebruikt via een pool (`POSTGRES_POOL_SIZE`, standaard 8) in plaats van per aanroep geopend;
  SQLite houdt een verbinding per aanroep.
- `/version` noemt bij de package `onderwijsdata` onder `manifest` de meegebouwde CBS-catalogus (#370):
  `catalogusrevisie`, `consistent` (horen de geleverde bestanden bij dat manifest), `aantal`,
  `laatste_succesvolle_controle` en `versheid` (oudste controle, verouderde perioden en afleidingen).
- `/version` toont de release waarop de omgeving draait (de chartversie, dus de tag `X.Y.Z`) in plaats van de
  vaste waarde uit `pyproject.toml`. Het chart geeft die mee als `APP_VERSION`; op test is dat de prerelease van de
  main-build, lokaal valt het terug op `pyproject.toml`.
- Het log bevat op INFO en hoger geen vraag- of antwoordtekst meer: `RUN START`, `FINALE ANTWOORD`,
  `ANTWOORD INGEHOUDEN`, `ZELFCORRECTIE`, de controle-, zoek-, `CATALOGUS_GELADEN`/`CATALOGUS_AFWIJKING`-, rapport-,
  KPI- en `REPRODUCEER`-regels noemen model, lengte, een korte SHA-256-hash of de namen van de controles. De
  tekst zelf staat alleen op DEBUG. Het log valt buiten "gesprek verwijderen", dus wat de gebruiker typte bleef
  daar staan.
- `run_analysis` draait in een eigen proces zonder omgevingsvariabelen, netwerk, schrijfrechten of
  toegang tot bestanden buiten Python, met een harde time-out en geheugenlimiet. Een AST-controle
  (imports, dunders zoals `__globals__`, frame-attributen) vervangt de regex-lijst. `store_get` vraagt
  een letterlijke key.
- De `pytest`-job draait ook `ruff check`; de pipeline blokkeert op falende tests.
- Evaluatie-uitvoer staat niet meer in git.
- riodata is gepind op 0.3.1 (rio-onderwijsdata `c0b4bce`); `/version` noemt de meegebouwde catalogusrevisies.
- `/version` noemt onder `arbeidsmarkt` ook de dataversie van UWV (snapshots t/m 2023-05-16) en ROA (AIS 2030,
  editie 2025), uit de statische catalogus van riodata en zonder download.
- riodata is gepind op 0.5.0 (rio-onderwijsdata `f93defe`, de commit van tag `v0.5.0`): `duo.catalog()` en
  `duo.search()` pagineren over alle 56 DUO-datasets op CKAN (`search` gaf er hooguit 50), `duo.load` houdt de
  voorloopnul van codes als `GEMEENTENUMMER` (`0080`, niet 80), en de schema- en contractcorrecties uit de
  ketenaudit (A3-A6) zitten erin. ROA heet in `/version` nu "Edities 2025 en 2026 (2026 is de nieuwste;
  DataverseNL-release 2026-09-18). Prognoses tot 2030." in plaats van "Editie 2025". Een filter op zo'n code
  in `query_data` vraagt nu de tekst met voorloopnul (`"0363"`); `363` geeft 0 rijen en die suggestie. Omdat
  riodata nu elk bestand beschrijft, laat `dataset_details` bij zeven grote DUO-datasets (p01-p04,
  `instromende-mbo-studenten`, `studentprognoses-mbo-per-instelling` en `mbo-studenten-per-instelling`) de
  voorbeeldwaarden en zo nodig de kolomtypes weg, zodat het binnen het toolbudget van de chat blijft; de kolommen
  per bestand, de teldefinitie en de publicatieregels blijven staan.
- `CORS_ORIGINS` staat standaard dicht en weigert `*`; elke omgeving noemt alleen haar eigen host.
- `CORS_ORIGINS` weigert bij het opstarten ook een origin met een `*` erin, zoals `https://*.nl`: origins worden
  letterlijk vergeleken, dus zo'n patroon werkte nooit en faalde stil. De melding noemt de foute origin.
- De ongebruikte dependency `nh3` is verwijderd.
- Productie-manifest geauditeerd: de allowlist-middleware waar de ingress naar verwijst wordt meegeleverd,
  dashboards staan uit zoals op test, en productie draait één pod zolang data en limiters in het geheugen leven.
- `/ready` geeft bij een falende check (database of LLM-sleutels) HTTP 503 met een JSON-object, in plaats
  van 200 met een JSON-array. De readiness-probe van de chart gebruikt `/health` en merkt hier niets van.
- Een onbekend pad onder `/api` geeft een JSON-404 (`{"detail": "Not Found"}`) in plaats van de SPA met 200.
- Uitloggen trekt het token ook op de server in (`POST /api/auth/logout`, tabel `revoked_tokens`): REST, de
  chat-WebSocket, dashboard-refresh en verversen weigeren het daarna. Een token geldt nu 8 uur in plaats van
  24 (`SESSION_TTL_HOURS`) en verversen kan tot 24 uur na inloggen (`SESSION_MAX_HOURS`), niet meer onbeperkt.
  Wie met `CHAT_USERS` inlogt, moet na 8 uur opnieuw inloggen. Bestaande tokens blijven geldig tot hun vervaltijd.
- CSP `connect-src` staat alleen nog de eigen server toe (`'self'` plus de `wss://`-origin uit `SERVER_URL`) in plaats
  van WebSockets naar elke host (#506, SECURITY.md S13). Nieuwe CI-jobs `audit:python` (pip-audit op `uv.lock`) en
  `audit:npm` (npm audit, high) scannen de dependencies op `main` en in elke MR; informatief, ze blokkeren niets
  (SECURITY.md S12). De SDP-securitycomponent bleek alleen secret detection en SAST te draaien.
