# Dashboards

De app biedt voorgeconfigurde dashboards per onderwijsinstelling en een LLM-gestuurde dashboard-generator.

---

## Voorgeconfigurde dashboards

Vijf vaste dashboard-weergaven, beschikbaar via de API en het frontend:

| Dashboard | Endpoint | Inhoud |
|-----------|----------|--------|
| **Instroom** | `/api/dashboard/instroom` | Eerstejaars inschrijvingen, trends per opleiding |
| **Regio** | `/api/dashboard/regio` | Regionale vergelijking, SBB sectorkamers |
| **Nationaal** | `/api/dashboard/nationaal` | Nationale onderwijsstatistieken, KPI's |
| **Rendement** | `/api/dashboard/rendement` | Diplomering, doorstroom, uitval |
| **Arbeidsmarktmatch** | `/api/dashboard/arbeidsmarktmatch` | UWV vacaturedata per sector, match scores |

Elk dashboard ontvangt een `instelling` query-parameter en retourneert JSON met figuren, data en bronvermeldingen.

---

## LLM-gestuurde generator

Gebruikers kunnen via de chat een dashboard laten genereren:

1. **Genereer** — het LLM analyseert de vraag en maakt een dashboard-specificatie
2. **Bekijk** — het dashboard wordt direct in de chat weergegeven
3. **Sla op** — via de workbook-functionaliteit (vereist authenticatie)
4. **Ververs** — data wordt opnieuw opgehaald via `/api/dashboard/refresh`

Het gegenereerde dashboard bevat:

- Interactieve Plotly-grafieken
- Bronvermeldingen met link naar de originele data
- Python-snippets voor reproduceerbaarheid

---

## Workbooks

Workbooks zijn opgeslagen dashboards die je kunt bewerken en delen. Ze bevatten:

- Gekoppelde datasets en figuren
- Dashboard-specificatie (recipe)
- HTML-export voor delen

Vereist authenticatie — zie [API Referentie → Persistentie](api.md#persistentie).
