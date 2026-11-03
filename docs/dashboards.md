# Dashboards

De app heeft drie vaste dashboards per onderwijsinstelling (Mijn instelling, Arbeidsmarkt en Landelijk) op de pagina
`/dashboards`. De LLM-gestuurde dashboardbouwer is verwijderd (#765); een analyse delen gaat met een rapport.

---

## Vaste dashboards

Vijf vaste dashboard-weergaven, beschikbaar via de API en het frontend zolang `ENABLE_DASHBOARDS` op `true` staat (standaard uit in de code, #765; op test staat hij aan, op playground en productie uit):

| Dashboard | Endpoint | Inhoud |
|-----------|----------|--------|
| **Instroom** | `/api/dashboard/instroom` | Ingeschrevenen per jaar, verdeling over sectoren, gediplomeerden; bij HO ook geslacht en eerstejaars |
| **Regio** | `/api/dashboard/regio` | Regionale vergelijking, SBB sectorkamers |
| **Nationaal** | `/api/dashboard/nationaal` | Nationale onderwijsstatistieken, KPI's |
| **Rendement** | `/api/dashboard/rendement` | Diplomering, doorstroom, uitval |
| **Arbeidsmarktmatch** | `/api/dashboard/arbeidsmarktmatch` | UWV vacaturedata per sector, match scores |

Elk dashboard ontvangt een `instelling` query-parameter en retourneert JSON met figuren, data en bronvermeldingen.
De data komt uit `data/dashboard.py`.

---

## Opgeslagen dashboards uit de dashboardbouwer

Een dashboard dat iemand met de verwijderde dashboardbouwer opsloeg, blijft op de server staan: de app gooit geen
gegevens weg omdat een functie verdwijnt. Het opent niet meer. Op `/dashboards` staat het onder de vaste dashboards in
een lijst met titel en datum, om het los te verwijderen; een oude link (`/dashboards?id=…`) zegt dat het niet meer opent.
Het zit in de export van "mijn gegevens", gaat mee met "al mijn gegevens verwijderen" en valt onder de gewone
bewaartermijn van werkboeken (365 dagen, [Privacy](privacy.md)). Met `ENABLE_DASHBOARDS=false` (playground en productie)
is de pagina er niet en zie je ze dus ook niet.
