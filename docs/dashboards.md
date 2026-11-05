# Dashboards

De app heeft drie vaste dashboards per onderwijsinstelling (Mijn instelling, Arbeidsmarkt en Landelijk) op de pagina
`/dashboards`. De LLM-gestuurde dashboardbouwer is verwijderd (#765); een analyse delen gaat met een rapport.

---

## Vaste dashboards

De frontend toont drie dashboards; ze halen hun cijfers uit vier eindpunten. Beide zijn er zolang `ENABLE_DASHBOARDS`
op `true` staat (standaard uit in de code, #765; op test en playground staat hij aan, op productie uit).

| Dashboard in de UI | Eindpunten | Inhoud |
|--------------------|------------|--------|
| **Mijn instelling** | `/api/dashboard/regio`, `/api/dashboard/rendement` | Kerncijfers, ingeschrevenen, sectoren, eerstejaars, gediplomeerden, bij ho geslacht, de regionale vergelijking en de kaart; mbo: leerwegen en ingeschrevenen per hoofdgroep. Daarnaast diplomarendement per cohort en sector |
| **Arbeidsmarkt** | `/api/dashboard/arbeidsmarktmatch`, `/api/dashboard/regio` | Gediplomeerden tegen vacatures per sector, de matchscore, ROA (schoolverlaters en prognoses per opleidingsniveau) en de vacatures in de provincie |
| **Landelijk** | `/api/dashboard/nationaal` | Positie per sector, marktaandeel, trend van de eigen sectoren en de ranking van alle instellingen van hetzelfde type |

**Bronnen.** De dashboards rekenen met DUO (open onderwijsdata per instelling), UWV (vacatures per provincie, een
momentopname van mei 2023) en ROA (schoolverlaters en prognoses, landelijk per opleidingsniveau). CBS-data gebruiken
ze niet; alleen de indeling in arbeidsmarktregio's (per gemeente) komt van CBS. Over de landelijke CBS-maat van de chat:
zie "Landelijk, groei en het regiogemiddelde" hieronder.

**Frontend.** De dashboards staan in `frontend/src/components/dashboards/` (een map per dashboard, gedeelde delen in
`shared/`) en tekenen met Chart.js (`react-chartjs-2`); alleen de kaart is een Plotly-figuur die de backend bouwt.
`WorkbookViewer` laadt ze lazy, zodat de rapportenroute Chart.js niet meelaadt (#907). Een klik op de legenda volgt
de standaard van Chart.js. De tests staan in `frontend/src/__tests__/dashboard*.test.js` (bouwfuncties, legenda,
laden, lege en mislukte lading, cijfers, toegankelijkheid) en voor de backend in `tests/test_dashboard_*.py` en
`tests/test_instellingen.py`.

Elk dashboard ontvangt een `instelling` query-parameter en retourneert JSON met figuren, data en bronvermeldingen
(`bronnen`, zie hieronder). De data komt uit `data/dashboard.py`.
`/api/dashboard/instroom` is weg (#930): geen dashboard gebruikte het, en wat het gaf, staat ook in `regio`.

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
- **DUO:** per bestand het resource-ID en `last_modified` van riodata (#717); `peilmoment` in de woorden van de
  bronregel in de chat. `peildatum` en `voorlopig_jaren` komen uit de DUO-beschrijving in de catalogus.
- **UWV:** de momentopname van mei 2023; `peildatum` uit de kolom PEILDATUM.
- **ROA:** `editie` uit het schema van riodata, `versie` uit de kolom `versie` van het bestand.
- `/api/dashboard/regio` dient Mijn instelling (de DUO-regels) en Arbeidsmarkt (UWV en ROA): elk dashboard neemt er zijn
  eigen deel uit, zoals bij `niet_beschikbaar`.

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
  `vacatures_peildatum` (de UWV-momentopname in de provincie), `diplomajaren` (de jaren van het gemiddelde),
  `roa_versie` en `sectormapping` (herkomst, versie en model van de indeling: een LLM-classificatie, niet van UWV). De
  tegels, de grafiek "Gediplomeerden vs. vacatures" en het vacatureaanbod tonen de peildatum uit de payload; onder de
  tegels staan de drie labels met de drempel en wat de score niet zegt (geen opleidingsniveau bij vacatures, één dag
  tegen een meerjarig gemiddelde).

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
- **Groei** op Mijn instelling loopt voor elke instelling vanaf hetzelfde startjaar (het laatste van de eerste jaren
  met data, over eigen instelling en peers) tot het laatste jaar, in grafiek, ranking en tabel; het startjaar staat in
  de kop.
- **Regiogemiddelde**: per jaar het gemiddelde over de peers met data in dat jaar; `benchmark.n_per_jaar` geeft hoeveel
  dat er zijn, `n_instellingen` het aantal in het laatste jaar. Een peer met in elk jaar 0 of een lege cel telt niet
  mee in gemiddelde, aantal, totaal en `onderdrukt`; hij staat per reeks in `benchmark.geen_gegevens` en in de
  concurrententabel met "geen gegevens" (#925). Een peer met één echt nuljaar telt wel mee.

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
