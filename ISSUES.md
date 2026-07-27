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
| 36 | Standaard regiodashboard | Deels — gender is 5e dashboard, adres-lookup klaar |
| 71 | Dashboard UX Arena.ai vergelijking | 9 fixes geleverd, ideeënlijst blijft open |
| 79 | SBB Regio Atlas inspiratie | Screenshots verwerkt, inhoudelijk nog niet opgepakt |

### Volgende prioriteit

| # | Titel | Waarom |
|---|-------|--------|
| 81 | Doorstroom MBO na diplomering | Logisch vervolg op regio-data |
| 80 | SBB open data integratie (stage/baankans) | Voedt regio dashboards |
| 59 | Bericht bewerken en opnieuw sturen | Standalone UX, geen data-dependency |
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
| MINOR | `ChatPage`, `App` | Unsanitized data naar `localStorage` | Open |
| MINOR | `InlineDashboards`, `useChat`, `useDashboardChat` | User-controlled values in request URLs | Open |

### Code smells (top items uit 165)

| Regel | Beschrijving | Status |
|-------|-------------|--------|
| S3776 | 10 functies boven cognitive complexity threshold (9 Python, 1 JS) | ✅ Alle functies <15: rendement 102→0, nationaal 18→3, regio_mbo 24→9, rendement_mbo 20→orchestrator, arbeidsmarkt 31→14 |
| S6479 | 5× array index als React key | ✅ Stabiele keys |
| S3358 | 4× nested ternaries in `WorkbookViewer.jsx` | ✅ 7-level ternary → lookup map |
| S1172 | 4× unused function parameters in Python | ✅ Underscore-prefix |

---

## 3. Inspiratie uit Nao releases

> Bron: [Nao releases v0.2.0–v0.3.0](https://github.com/getnao/nao/releases)

### Direct toepasbaar

| Feature | Nao PR | Relevantie voor ons |
|---------|--------|---------------------|
| KPI variation pills (delta-indicators) | #1243 | Onze KPI tiles zijn statisch — trend-badges toevoegen |
| Excel download per tabel | #1246 | Wij exporteren hele workbooks, niet per tabel |
| Dual Y-axis charts | #1241 | Gender/instroom: % en absolute aantallen samen tonen |
| 100% stacked bar/area | #1153 | Samenstellingsdata (geslacht, sectoren) |
| Chat resend + versie-navigatie | #954 | Raakt direct issue #59 |
| Point maps op OpenStreetMap | #1206 | Relevant voor regionale kaarten (adres-lookup) |
| Sortable table columns | #1226 | Verifiëren of onze tabellen dit ondersteunen |

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
