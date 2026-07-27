# Issues & verbeterpunten — overzicht 2026-07-27

## Werkwijze

**Product owner:** Claude (deze sessie) — stuurt agents aan, monitort output, corrigeert bij afwijking.

**Branch:** `release/1.8.0`

### Beschikbare modellen (opencode CLI)

| Model | Inzet |
|-------|-------|
| `opencode/big-pickle` | Complexe taken, architectuur |
| `opencode/deepseek-v4-flash-free` | Snelle code-generatie |
| `opencode/laguna-s-2.1-free` | Alternatief voor review/second opinion |
| `opencode/ling-3.0-flash-free` | Snelle iteraties |
| `opencode/mimo-v2.5-free` | Code-generatie |
| `opencode/nemotron-3-ultra-free` | Zware reasoning taken |
| `opencode/north-mini-code-free` | Kleine gerichte fixes |

### Principes

- **TDD** — test eerst, implementatie volgt. Geen code zonder test.
- **Modulair** — kleine bestanden, duidelijke verantwoordelijkheid, geen god-objects.
- **Onderhoudbaar** — leesbare code boven slimme code. Geen premature abstracties.
- **Geen tactical tornado** — geen snel-even-fiksen dat technische schuld achterlaat.
- **Dode code opruimen** — ongebruikte imports, functies, variabelen worden direct verwijderd.
- **Monitoren** — elke agent-output wordt gereviewed. Bij afwijking: stoppen, corrigeren, opnieuw.

---

## 1. Open GitHub issues

> Bron: [GitHub Issues](https://github.com/cedanl/onderwijsdata-chat/issues)

### Geraakt door release/1.8.0

| # | Titel | Status |
|---|-------|--------|
| ~~78~~ | Lookup regio/provincie | Gesloten |
| 36 | Standaard regiodashboard | 6 dashboards: samenvatting + instroom + diplomering + arbeidsmarkt + gender + sectorkamers |
| 71 | Dashboard UX Arena.ai vergelijking | 9 fixes geleverd, ideeënlijst blijft open |
| 79 | SBB Regio Atlas inspiratie | Samenvatting-tile (item 1) + sectorkamers chart (MBO). Items 2-7 vereisen externe data (SBB/ROA/CBS) |

### Volgende prioriteit

| # | Titel | Waarom |
|---|-------|--------|
| 81 | Doorstroom MBO na diplomering | Logisch vervolg op regio-data |
| 80 | SBB open data integratie (stage/baankans) | Voedt regio dashboards |
| ~~59~~ | ~~Bericht bewerken en opnieuw sturen~~ | ~~Geïmplementeerd: resend-knop op user messages~~ |
| 32 | CSV-export querydata | Hoge gebruikerswaarde, goed afgebakend |
| 23 | Evals: LLM rapporteert op verwachting ipv data | Kwaliteit/vertrouwen |

### On-hold / backlog

| # | Titel |
|---|-------|
| 70 | Dynamische uitsplitsing via "Verder bewerken" |
| 69 | Visualisatietype wisselen per grafiek |
| 68 | Cosmetische dashboard-edits (titel, kleuren) |
| 30 | Dashboard exporteren en delen via link |
| 27 | Doorzoekbare conversatiegeschiedenis |
| 34 | Zoeken (project tracker) |
| 22 | Use case schrijven |
| 4 | Quarto export: chat naar rapport |

---

## 2. SonarCloud

> Bron: [SonarCloud project](https://sonarcloud.io/project/overview?id=cedanl_onderwijsdata-chat) — 182 open issues

### Bugs (9)

| Ernst | Locatie | Beschrijving | Status |
|-------|---------|-------------|--------|
| MAJOR | `server.py:77` | Synchrone `open()` in async functie | ~~Al opgelost met `asyncio.to_thread()`~~ |
| MAJOR | `tests/test_tools_query.py:159-160` | Float equality zonder `pytest.approx()` | ~~Al opgelost op deze branch~~ |
| MINOR | Frontend (6×) | Click handlers zonder keyboard listeners | ✅ ARIA + Escape op modals, role/tabIndex op WorkbookViewer |

### Vulnerabilities (8)

| Ernst | Locatie | Beschrijving | Status |
|-------|---------|-------------|--------|
| MAJOR | `.github/workflows/*.yml` (3×) | Actions op tags i.p.v. commit SHA | ✅ SHA-pinned |
| MINOR | `ChatPage`, `App` | Unsanitized data naar `localStorage` | Niet van toepassing — React escapet output, geen dangerouslySetInnerHTML |
| MINOR | `InlineDashboards`, `useChat`, `useDashboardChat` | User-controlled values in request URLs | Niet van toepassing — alleen relatieve paden met interne IDs |

### Code smells (top items uit 165)

| Regel | Beschrijving | Status |
|-------|-------------|--------|
| S3776 | 10 functies boven cognitive complexity threshold (9 Python, 1 JS) | ✅ Alle functies <15: rendement 102→0, nationaal 18→3, regio_mbo 24→9, rendement_mbo 20→orchestrator, arbeidsmarkt 31→14 |
| S6479 | 5× array index als React key | ✅ Stabiele keys |
| S3358 | 4× nested ternaries in `WorkbookViewer.jsx` | ✅ 7-level ternary → lookup map |
| S1172 | 4× unused function parameters in Python | ✅ Underscore-prefix |

---

## 3. Inspiratie uit Nao

> Bron: ~280 merged PRs + 50 releases (v0.0.45–v0.3.0), gescand 2026-07-27

### Geïmplementeerd

| Feature | Nao PR | Status |
|---------|--------|--------|
| KPI variation pills (delta-indicators) | #1243 | ✅ Sparklines + delta op instroom/arbeidsmarkt |

### Direct toepasbaar (volgende sprint)

| Feature | Nao PR | Relevantie voor ons |
|---------|--------|---------------------|
| Chat resend + versie-navigatie | #954 | Raakt direct issue #59 — hoge UX-waarde |
| Excel/CSV download per tabel | #1246 | Raakt issue #32 — hoge gebruikersvraag |
| K/M/B suffix grote getallen | #766 | Tooltips en KPIs leesbaarder |
| Data labels toggle op charts | #1083 | Waarde direct op bars/lines |
| Follow-up placeholder in chat input | #495 | Kleine UX-verbetering, laag effort |
| Chat message queue (max 5) | #352 | Voorkomt wachten op antwoord |
| Chronologisch sorteren datum x-as | #493 | Defensive check of wij dit al doen |

### Relevant maar groter effort

| Feature | Nao PR | Relevantie voor ons |
|---------|--------|---------------------|
| Point maps op OpenStreetMap | #1206 | Regio-dashboards + adres-lookup |
| Dual Y-axis charts | #1241 | Gender/instroom: % en absolute samen |
| 100% stacked bar/area | #1153 | Samenstellingsdata (geslacht, sectoren) |
| Export als PDF/HTML | #567 | Raakt issue #4 (Quarto export) |
| Sortable table columns | #1226 | Tabellen interactiever |
| Y-as bounds aanpassen aan waarden | #1091 | Betere chart leesbaarheid |
| Paginatie in resultatentabel | #523 | Grote datasets |

### Inspiratie / later evalueren

| Feature | Nao PR | Beschrijving |
|---------|--------|-------------|
| Flexible chart grids (resize/reorder) | #1224 | Onze layout is nu fixed |
| View SQL/data achter chart | #940 | Transparantie voor data-savvy gebruikers |
| Floating suggestion panel | #952 | Contextual suggestions boven chat input |
| Conditional formatting via AI | #1161 | Kleuren in tabellen op basis van context |
| Self-analyzing context recommendations | #885 | Systeem stelt voor welke vragen te stellen |
| Stories met tabs | #1211 | Tabbed dashboard views |
| Annotations per tabel | #1189 | Metadata/notities bij datasets |
| Command palette + chat zoeken | #366 | Raakt issue #27 (doorzoekbare geschiedenis) |
| Bulk chat deletion (soft delete) | #478 | Opschonen conversaties |
| Agent memory voor user preferences | #313 | Personalisatie per gebruiker |
| Selectie → vraag agent | #625 | "Leg dit uit" op geselecteerde tekst |
| Image upload in chat | #501 | Screenshots/context meesturen |
| Dashboard filters | #1250 | Interactieve filtering op dashboards |

### Niet relevant (~200 PRs)

Database connectors (Trino, ClickHouse, Redshift, Fabric, Athena, StarRocks, MySQL), enterprise auth (OIDC, Google SSO, GitLab, Azure AD), messaging (Slack/Teams/WhatsApp/Telegram bots), MCP servers, Docker/CI, admin tools, automations, white-labeling, billing, CLI tooling.
