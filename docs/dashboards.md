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

---

## Opgeslagen dashboards uit de dashboardbouwer

Een dashboard dat iemand met de verwijderde dashboardbouwer opsloeg, blijft op de server staan: de app gooit geen
gegevens weg omdat een functie verdwijnt. Het opent niet meer. Op `/dashboards` staat het onder de vaste dashboards in
een lijst met titel en datum, om het los te verwijderen; een oude link (`/dashboards?id=…`) zegt dat het niet meer opent.
Het zit in de export van "mijn gegevens", gaat mee met "al mijn gegevens verwijderen" en valt onder de gewone
bewaartermijn van werkboeken (365 dagen, [Privacy](privacy.md)). Met `ENABLE_DASHBOARDS=false` (productie)
is de pagina er niet en zie je ze dus ook niet.
