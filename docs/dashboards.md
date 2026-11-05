# Dashboards

De app heeft drie vaste dashboards per onderwijsinstelling (Mijn instelling, Arbeidsmarkt en Landelijk) op de pagina
`/dashboards`. De LLM-gestuurde dashboardbouwer is verwijderd (#765); een analyse delen gaat met een rapport.

---

## Vaste dashboards

Vijf vaste dashboard-weergaven, beschikbaar via de API en het frontend zolang `ENABLE_DASHBOARDS` op `true` staat (standaard uit in de code, #765; op test en playground staat hij aan, op productie uit):

| Dashboard | Endpoint | Inhoud |
|-----------|----------|--------|
| **Instroom** | `/api/dashboard/instroom` | Ingeschrevenen per jaar, verdeling over sectoren, gediplomeerden; bij HO ook geslacht en eerstejaars |
| **Regio** | `/api/dashboard/regio` | Regionale vergelijking; mbo: leerwegen en ingeschrevenen per hoofdgroep |
| **Nationaal** | `/api/dashboard/nationaal` | Nationale onderwijsstatistieken, KPI's |
| **Rendement** | `/api/dashboard/rendement` | Diplomering, doorstroom, uitval |
| **Arbeidsmarktmatch** | `/api/dashboard/arbeidsmarktmatch` | UWV vacaturedata per sector, match scores |

Elk dashboard ontvangt een `instelling` query-parameter en retourneert JSON met figuren, data en bronvermeldingen.
De data komt uit `data/dashboard.py`.

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

### Wat de getallen tellen

- **Mbo per leerweg** (`sectoren`, `leerwegen`): BBL, BOL voltijd, BOL deeltijd en Extraneus uit
  `mbo-studenten-per-instelling`. Samen zijn ze het totaal ingeschrevenen, in het regio- en het instroomdashboard
  (#899).
- **Mbo per hoofdgroep** (`ingeschrevenen_per_hoofdgroep`): `TOTAAL MBO` uit `instromende-mbo-studenten`, het laatste
  jaar. Dat zijn ingeschrevenen, nieuw of niet, geen eerstejaars (domeinregel `mbo-instroom-totaal-mbo` in
  `data/domeinregels.toml`). Het is een ander DUO-bestand dan dat van het totaal, dus de som wijkt daarvan af.
- **Aanbod in de arbeidsmarktmatch** (`gediplomeerden_per_sector`): gediplomeerden per sector, gemiddeld over de
  laatste drie diplomajaren: per ho-onderdeel uit `p04hogdipl`, per mbo-hoofdgroep uit `gediplomeerde-mbo-studenten`.
  Tot #899 stond voor het mbo `TOTAAL MBO` (ingeschrevenen) in dit veld.

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
vaste lijst `_INSTROMENDE_MBO_HISTORISCH` (`data/dashboard.py`). Publiceert DUO een jaar, dan wordt de ping
`duo-instroom-mbo` van `bron:ping` rood; voeg dan de index toe aan die lijst en aan `scripts/duo_testfixtures.py`, en
ververs de fixtures (#924).

---

## Opgeslagen dashboards uit de dashboardbouwer

Een dashboard dat iemand met de verwijderde dashboardbouwer opsloeg, blijft op de server staan: de app gooit geen
gegevens weg omdat een functie verdwijnt. Het opent niet meer. Op `/dashboards` staat het onder de vaste dashboards in
een lijst met titel en datum, om het los te verwijderen; een oude link (`/dashboards?id=…`) zegt dat het niet meer opent.
Het zit in de export van "mijn gegevens", gaat mee met "al mijn gegevens verwijderen" en valt onder de gewone
bewaartermijn van werkboeken (365 dagen, [Privacy](privacy.md)). Met `ENABLE_DASHBOARDS=false` (productie)
is de pagina er niet en zie je ze dus ook niet.
