# Changelog

Alle wijzigingen die voor gebruikers of beheerders van belang zijn. Formaat naar
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/). Versienummers volgen de git-tags;
de laatste tag is 1.8.6.

## Niet uitgebracht

### Scope
- De chat werkt alleen voor mbo, hbo en wo. Po-, so- en vo-bestanden van DUO (o.a. `voprognoses`,
  `02voins-v1`) zijn niet meer te vinden, op te vragen of te laden, ook niet met een dataset-ID uit de
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
- RIO-registers over alle sectoren (aangeboden opleidingen, opleidingen, opleidingserkenningen,
  onderwijslicenties) haalt de chat alleen op met een filter op een mbo/hbo/wo-type. Registers die niet per
  sector te selecteren zijn (erkenningen, contactadressen, onderwijslocaties, organisatorische eenheden) laadt
  hij niet; bestuur, instellingen en vestigingen van een instelling lopen via `get_rio_instelling`.

### Evaluatie
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
  welke controle afging.
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
  De uitleg begint met bron en selectie in woorden, met maat, eenheid en stap; de `data_key` staat eronder.
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
- Is de data van een gesprek na een herstart van de server weg, dan zegt een mislukte CSV-download dat en biedt
  "Vraag opnieuw stellen" aan. Een rapport of dashboard op zo'n gesprek wordt niet meer op de overgebleven data
  gemaakt: de melding zegt dat de vraag opnieuw moet (was: "Rapport kon niet worden gemaakt").
- Code-snippets draaien zelfstandig: ze beginnen met de laadstap van de bron, met bron-ID en filters.
- Code-snippets geven dezelfde uitkomst als de app: filters met dezelfde semantiek, DUO-cellen met -1
  uitgesloten, en ook een KPI-snippet laadt zijn eigen data.
- De CSV-export van een grafiek decodeert binaire Plotly-arrays en weigert kapotte figuren met een reden.
- Een herhaalde toolcall toont zijn grafiek niet twee keer.
- Het model gebruikt standaard temperature 0 en een vaste seed (`TEMPERATURE`, `SEED`).

### Gebruikersinterface
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
- Eén redeneerkaart per antwoord in plaats van een kaart per stap.
- Een vraag tijdens een lopend antwoord krijgt een melding, de getypte tekst blijft staan.
- Een onbekend pad toont een 404-pagina; een uitgeschakelde dashboardroute meldt dat hij nog niet beschikbaar is.
- Hernoem- en verwijderknoppen hebben een `aria-label`.
- Stuit een antwoord na alle pogingen op de rate limit, dan blijven de al opgehaalde stappen in het
  gesprek; een nieuwe poging bouwt erop voort.

### Beheer
- `run_analysis` draait in een eigen proces zonder omgevingsvariabelen, netwerk, schrijfrechten of
  toegang tot bestanden buiten Python, met een harde time-out en geheugenlimiet. Een AST-controle
  (imports, dunders zoals `__globals__`, frame-attributen) vervangt de regex-lijst. `store_get` vraagt
  een letterlijke key.
- De `pytest`-job draait ook `ruff check`; de pipeline blokkeert op falende tests.
- Evaluatie-uitvoer staat niet meer in git.
- riodata is gepind op 0.3.1 (rio-onderwijsdata `c0b4bce`); `/version` noemt de meegebouwde catalogusrevisies.
- `CORS_ORIGINS` staat standaard dicht en weigert `*`; elke omgeving noemt alleen haar eigen host.
- Productie-manifest geauditeerd: de allowlist-middleware waar de ingress naar verwijst wordt meegeleverd,
  dashboards staan uit zoals op test, en productie draait één pod zolang data en limiters in het geheugen leven.
