# Architecture Decision Records (ADRs)

This document captures major architectural decisions and their rationale. Each decision explains the context, options considered, and why we chose this path.

## ADR-001: Anti-hallucinatie via server-side compute

**Date:** 2026-09-22 (revised 2026-10-02: limits stated; 2026-11-02: percentages in reports)  
**Status:** Decided  
**Issue:** #39, #8

### Problem
Language models hallucinate numbers when unsupervised. Other statistical agencies (ONS, Statistics Canada) have stopped deploying RAG chatbots due to this risk.

### Decision
The server loads and computes; the model selects and phrases. Four layers:

1. **data_key** — No data rows in context; the model gets a key, the schema and a short preview.
2. **Compute in code** — `query_data` (aggregation) and `compute_kpi` (difference, percentage, index, largest drop/rise) return the numbers; the model copies them.
3. **run_analysis guard** — An AST check rejects a script with a literal data structure of six or more numbers (retyped data) or one that reads no data.
4. **Answer checks** — Every chat answer is checked against the tool results: numbers (`agent/grounding.py`), selection, labels and binding (`agent/selectie.py`, `agent/labels.py`, `agent/binding.py`). A failure triggers one correction round; a remaining problem stays visible on the answer. Reports use `agent/report_checks.py`. The report run has `compute_kpi` too, and checks every percentage the model wrote with the same rule as the chat (`unsourced_percentages` in `agent/grounding.py`, #872).

### Rationale
- **Auditable:** each number can be traced to the tool call that produced it.
- **Reproducible:** every analysis exports as a Python snippet that can be rerun.
- **Detectable:** a number that is not in the data is caught by code, not left to the prompt.

### Trade-off and limits
More orchestration, and the checks reduce the risk; they do not eliminate it. Known gaps, described in [Anti-hallucinatie architectuur](anti-hallucination-architecture.md#wat-dit-niet-dekt):

- Numbers under four digits and years are not checked; percentages are matched as value or fraction, in chat answers and in the model text of a report (not in the definitions a report quotes from the source). A percentage that matches some value in the data counts as sourced, whatever that value measures, and its sign is not checked.
- Binding only works when a sentence names exactly one year and one institution.
- Numbers from earlier assistant messages in the conversation count as sourced. Numbers the user gave do not (#211): they are a claim to test, not evidence (`agent/controles.py`, `agent/grounding.py`). In a live session every assistant message counts: the server put it there itself. After reopening or reconnecting, the history comes from the client, so only an assistant message whose text hash has a row in `beurtbewijs` (ADR-009, #876) counts; one without a row (a conversation from before the table, a restart before the save, a stopped answer, or a text the client added or changed) does not, also not as "earlier conversation" for the refusal. A follow-up on such a conversation therefore gets a rewrite or an omitted number more often, until it fetches the data again. Identical text is the only link: an answer the server wrote and the client then copied verbatim into another place still counts.
- `run_analysis` executes model-written Python in a separate process (AST check, resource limits, audit hook blocking network, writes and subprocesses; #62). That sandbox limits damage but is not a kernel-level security boundary (#443).
- Each check covers one class of error; a new class of error passes until a check exists for it. When the set of check modules keeps growing, revisit this decision (see ADR-007 for when).

---

## ADR-002: Reproducible analyses via code generation

**Date:** 2026-09-22  
**Status:** Decided  
**Issue:** #43

### Problem
Research institutions need to audit and reproduce analyses. "Chat gave me this number" is not reproducible.

### Decision
Every tool call automatically generates a Python snippet. Users can export and re-run the exact code that generated the result.

### Implementation
- `tools/snippet.py` generates code for each tool type (query_data, compute_kpi, create_plot, etc.)
- Gebruikers zien de snippet bij elke stap in de chat en exporteren het gesprek als Markdown ("Exporteer gesprek"): per
  antwoord de stappen, elk met zijn snippet als `python`-codeblok (`frontend/src/conversationExport.js`, #366). Een
  los `.py`-bestand is er niet
- Code matches what the model actually called

### Rationale
- **Institutional reproducibility** — Each analysis is self-documenting code
- **Audit trail** — Inspectors can verify the numbers independently
- **Researcher confidence** — Results are peer-reviewable

---

## ADR-003: Centralized provider→API-key mapping

**Date:** 2026-09-22  
**Status:** Decided  
**Issue:** #53

### Problem
Provider-to-API-key associations lived in two places:
- `routes/chat.py` — hardcoded list
- `tests/test_eval_aggregation.py` — relied on `litellm.validate_environment()`

This caused drift: new providers forgotten, or test logic diverging from prod.

### Decision
Single source of truth in `core/config.py`:
```python
_PROVIDER_API_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": None,  # no key needed
    ...
}
```

Both `routes/chat.py` and `tests/` depend on this mapping.

### Rationale
- **Drift-prevention** — One mapping, tested by `test_api_key_vars_are_reasonable`
- **Clarity** — Explicit which providers need keys
- **Extensibility** — Add a provider, one place to update

---

## ADR-004: Renovate dependency grouping

**Date:** 2026-09-22  
**Status:** Decided  
**Issue:** #28

### Problem
Renovate generated 24+ PRs with three patterns of failures:
1. Interdependent bumps (vite, vitest, @vitejs/plugin-react) fail separately
2. ESLint 10 repeatedly proposed despite team decision to stay on v9
3. Lockfile updates as individual PRs

### Decision
Configure Renovate with:
- **frontend-buildstack** group — vite, vitest, @vitejs/plugin-react, jsdom together
- **github-actions** group — all GitHub Actions grouped
- **ESLint major block** — with reason in config for future reviewers
- **lockFileMaintenance** — weekly batch instead of individual PRs

### Rationale
- **Reduces noise** — 24 PRs → ~4-5 focused PRs per week
- **Prevents silent failures** — grouped PRs merge if all pass, fail if any fails
- **Respects decisions** — ESLint block documents the team choice

---

## ADR-005: Data confidentiality — never secrets via LLM

**Date:** 2026-09-22  
**Status:** Decided  
**Issue:** Agents.md

### Problem
LLM sessions have full visibility to stdout, logging, variable inspection. Secrets leaked to an LLM are permanently compromised.

### Decision
- **LLM writes:** Infrastructure code (values.yaml, config.py, Helm templates)
- **LLM never touches:** Secret files, SOPS encryption, kubectl with secrets
- **Developer owns:** secret_orig.yaml → SOPS encrypt → git commit

### Rationale
- **Compartmentalization** — LLM handles structure, human handles secrets
- **Irreversible security** — Once a secret is in a transcript, assume it's public

---

## ADR-006: Gesloten selectieschema voor brondata — het model kiest codes, de server bouwt de filter

**Date:** 2026-10-12  
**Status:** Decided  
**Issue:** #343 (bouwt op #342; past in epic #191)

### Problem
`get_cbs_data(filters={"$filter": "…"})` liet het model OData schrijven: de filtertaal van de
bron zat in de modelinterface. Het model koos ook `$top`, en daarmee of een selectie volledig
was. De volledigheidscontrole (`check_dimensions_pinned`) deed het goede werk, maar pas ná het
ophalen van 5.000 rijen, en een stilzwijgend opengelaten dimensie telde later dubbel (#162).

### Decision
- De modelinterface van `get_cbs_data` is een **`selectie`**: per dimensie een enum-code uit
  `get_cbs_dimension` (of `"*"` om bewust uit te splitsen), `periode` als lijst of bereik
  (schooljaarspelling wordt in code vertaald via `tools/periode.py`), `onderwerpen` als
  kolomsleutels. De server compileert hieruit `$filter`/`$select` (`tools/cbs_selectie.py`), elke
  vergelijking als `trim(Dimensie) eq 'code'`: CBS vult de sleutels van een dimensie op tot één
  breedte (`4000   ` naast `T001038`) en toont ze gestript, dus de kale code matcht zonder `trim`
  niets (#531).
- De **volledigheidspoort** zit vóór het laden: een dimensie die noch gepind noch `"*"` is,
  of een onbenoemde periode, weigert de aanroep vóór de datacall en noemt wat ontbreekt.
- De **rijlimiet is beleid** (`CBS_ROW_LIMIT`), geen modelparameter.
- **DUO en RIO** volgen hetzelfde principe met een gemotiveerde eigen vorm: DUO laadt een
  volledig gepubliceerd bestand (`dataset_id`, `resource` — geen filtertaal; selectie gebeurt
  in `query_data`); RIO accepteert alleen exacte `key=value`-serverfilters uit een vaste
  allowlist (`rio_filters`). Geen van drieën biedt het model een vrije expressietaal.
- De parameter `filters` (ruwe OData) blijft **intern** bestaan: bewaarde recepten en het
  herladen/verversen van oudere gesprekken voeren hun laadstap letterlijk opnieuw uit, en de
  gecompileerde selectie wordt zelf als `filters` in het recept bewaard (reproduceerbaar,
  zie `docs/reproducibility.md`). De modelinterface biedt hem niet meer aan.

### Rationale
- **LLM kiest, code selecteert** (epic #191): de bron-filtertaal is een implementatiedetail;
  codes en compilatie horen in code, waar ze deterministisch en testbaar zijn.
- **Fail-closed op volledigheid**: dubbeltellen door totaalrijen wordt onmogelijk gemaakt
  vóór het laden, in plaats van gerepareerd erna.
- **Canoniek by construction** (#342): de compiler sorteert codes en dimensies, dus dezelfde
  selectie in een andere spelling geeft dezelfde `$filter`, dezelfde `data_key` en één load.

### Trade-off(s)
- Eén metadatacall (DataProperties, lru-gecachet) vóór elke selectie-load; bij bronuitval op
  metadata compileert de server zonder poort (bronuitval is geen onvolledige selectie) en
  meldt `get_cbs_data` de ontbrekende metadata zoals voorheen.
- Dimensiecodes worden niet vooraf per code gevalideerd (dat zou per dimensie een extra call
  kosten); een verkeerde code geeft zoals voorheen de 0-rijenmelding met herstelhint.
- Het model moet élke dimensie benoemen, ook waar het vroeger impliciet alles laadde; dat is
  een bewuste keuze: de poort maakt de keuze zichtbaar in plaats van stilzwijgend.

---

## ADR-007: Geen grootboek en geen plan-and-execute voor het antwoordpad

**Date:** 2026-10-19  
**Status:** Decided  
**Issue:** #349 (raakt #191, #197, #212)

### Problem
Een blueprint (`audits/HARNESS-BLUEPRINT.md`, 03-10-2026) stelde na de normalisatielaag een
volgende stap voor: een planner (model) → compiler (code) → uitvoerder (code) → renderer die
het feitenblok uit een grootboek bouwt. Elk getal wordt daarin een post met binding (jaar, maat,
bron, dataset, plan-digest); het model schrijft alleen getalvrije interpretatie, en bij afkeuring
blijft het feitenblok staan (fail closed). Dat raakt `agent/grounding.py`, `agent/binding.py` en
`agent/run.py`. De blueprint en de PoC (`audits/canoniek.py`, `uitvoerder.py`, `grootboek.py`,
18 tests) staan lokaal, niet in git.

### Decision
- Het grootboek en plan-and-execute worden **niet gebouwd**. De blueprint en de PoC worden niet
  aan de repo toegevoegd, ook niet als spike.
- **Vervangen of aanvullen:** geen van beide; er komt niets bij. De antwoordcontroles van ADR-001
  blijven het enige systeem: `agent/grounding.py` (getallen), `agent/binding.py` (getal bij jaar
  en instelling) en de andere controlemodules, die `agent/controles.py` na elk antwoord draait (aangeroepen vanuit `agent/run.py`). Er
  staan dus geen twee systemen naast elkaar.
- **Vraagklassen met een vast plan:** geen. Een vraag naar data blijft vrije verkenning met tools,
  en elk antwoord gaat door dezelfde poorten: de volledigheidspoort vóór het laden (ADR-006) en de
  antwoordcontroles erna (ADR-001). De vaste antwoorden uit code (`agent/vaste_antwoorden.py`,
  zoals de betekenis van een sentinel of een vraag buiten het domein) en de verduidelijkingskaart
  (`agent/scopevraag.py`) blijven zoals ze zijn; zij halen geen data op en zijn geen plan.
- **Migratiepad:** de drie stappen vóór het grootboek staan al op `main`, en elk levert los winst
  op. Alleen het grootboek bleef over; daarvoor zijn geen vervolgissues nodig.
    1. Canonieke selectie (#342, `tools/canoniek.py`): dezelfde selectie in een andere spelling
       geeft één digest, één `data_key` en één load.
    2. Gesloten foutcodes en herhaal-detectie (#331, `tools/fouten.py`, `agent/loop.py`): een
       ruwe providerfout wordt een vaste code met een vaste tekst, en een tool die twee keer
       dezelfde fout geeft, gaat voor de rest van de beurt op slot.
    3. Gesloten selectieschema (#343, ADR-006): het model kiest codes, de server bouwt de filter
       en weigert een onvolledige selectie vóór het laden.
- **#197 en #212** (binding op de gezamenlijke rij) blijven in `agent/binding.py`: een getal moet
  in een rij staan die past bij het jaar én de instelling die dezelfde zin of tabelrij noemt.

### Rationale
- **Geen tweede laag:** de controlelaag telde in audit 11 en 12 al 23 regexguards ("tactical
  tornado", #349). Een grootboek vervangt binding en grounding, en dat is een herbouw van het
  antwoordpad, of het komt er als tweede, parallelle laag naast. Het eerste is te groot voor de
  demofase, het tweede is wat #349 juist wil voorkomen.
- **De winst zonder grootboek is binnen:** canonieke selectie, foutcodes en het selectieschema
  brengen codes, selectie en foutafhandeling in code (epic #191), zonder het antwoordpad om te
  bouwen.
- **ADR-001 voorziet het heroverwegen al** ("When the set of check modules keeps growing, revisit
  this decision"). Dit besluit maakt dat moment concreet (zie hieronder).

### Trade-off(s)
- De getallen in de antwoordtekst blijven door het model geschreven en achteraf gecontroleerd, met
  de bekende gaten van ADR-001 ([Wat dit niet dekt](anti-hallucination-architecture.md#wat-dit-niet-dekt)).
  Een feitenblok dat bij afkeuring blijft staan, komt er niet.
- Een nieuwe klasse fout vraagt een nieuwe controle; de controlelaag kan dus verder groeien.
- **Heroverwegen** zodra een van deze zich voordoet:
    - een nieuwe klasse getalfout vraagt nog een guard die niet in de bestaande controlemodules past;
    - een bindingsfout van het type #197/#212 is niet in `agent/binding.py` op te lossen;
    - de app gaat van de demofase naar productie.

---

## ADR-008: Plotly inline in het rapport, voor een rapport dat offline werkt

**Date:** 2026-10-30  
**Status:** Decided  
**Issue:** #812 (restpunt van #689; raakt #642, #660, #796)

### Problem
Een rapport tekent zijn grafieken met Plotly. In het rapportframe van de viewer laadt het de eigen build zonder
maplibre (`plotly-rapport`, #660, `frontend/src/plotlyBron.js`), ongeveer 1,1 MB gzip bovenop de route. De download
krijgt Plotly inline (`frontend/src/offlineHtml.js`), zodat het bestand zonder app en zonder netwerk opent; die
weegt ongeveer 3,4 MB (gemeten 29-10: 3.376.438 B, vóór #660 4.895.353 B). Op een geknepen 3G-verbinding of een
databundel kost één rapport daardoor tientallen seconden (mobiel ronde 8, N41).

### Decision
- **Accepteren:** ongeveer 1,1 MB gzip in het rapportframe en 3,4 MB in de download zijn de bewuste prijs voor
  een rapport dat offline werkt en als los bestand te delen is.
- **De rem is het budget:** `npm run budget` (`frontend/scripts/bundleBudget.js`) houdt `plotly-rapport` op
  1.150.000 B gzip. Groei daarboven is een besluit, geen ongeluk; het budget gaat niet omhoog zonder nieuw besluit.
- **Niet gekozen:** een Plotly-bundel op maat met alleen de traces die `tools/plot.py` maakt (elk nieuw grafiektype
  moet dan in de bundel, met een test die de dekking bewaakt), en een download die naar een gecachet asset
  verwijst (dan werkt het rapport niet meer als los, offline bestand, wat #642 en #660 juist wilden).

### Rationale
- **Offline en deelbaar:** een rapport is iets om door te sturen en later te openen; de download moet zonder app,
  netwerk of CDN werken (#486, #642).
- **Eén bron:** dezelfde build tekent in de viewer, in de download en in "Opslaan als PDF"; geen tweede bundel om
  gelijk te houden met de grafiektypen van `tools/plot.py`.
- **Gecachet in de viewer:** het frame laadt het asset onder een gehashte naam en de browser bewaart het een jaar;
  alleen het eerste rapport na een nieuwe build betaalt de 1,1 MB.

### Trade-off(s)
- Op een trage mobiele verbinding duurt de eerste rapportweergave lang, en een download is groot voor een mailbijlage.
- **Heroverwegen** zodra een van deze zich voordoet:
    - er komen klachten over laadtijd of downloadgrootte op mobiel;
    - `npm run budget` faalt op `plotly-rapport` en de groei is niet terug te dringen;
    - een .docx- of andere export vraagt toch statische grafieken (#746).

---

## ADR-009: Het gesprek blijft van de client; de server bewaart per beurt wat rapport en controles nodig hebben

**Date:** 2026-11-03 (besluit 2026-10-30); bijgewerkt 2026-11-09 (besluiten op open vragen 1 en 2; feedback verwijderd)  
**Status:** Decided; stap 1 gebouwd (#875: tabel, schrijven, herstellen, levenscyclus), stap 2 gebouwd (#876: alleen
eigen beurten als bewijs na heropenen, de controle in de rij en `server_beurt` in de feedbacktrace); feedback per
antwoord verwijderd 09-11 (#983), de feedbacktrace is daarmee weg  
**Issue:** #784 (raakt #472, #677, #760, #785)

### Problem
De server schrijft zelf geen chatbeurt weg; de browser bezit de gezaghebbende kopie van elk gesprek.

- Na elk antwoord stuurt de frontend de hele `messages`-lijst met `PUT /api/conversations/{id}` (`routes/persistence.py`,
  de body is een ongetypeerde `dict`). De server bewaart die als één JSON-blob in `conversations.messages`
  (`persistence/db.py` `upsert_conversation`).
- Bij heropenen en na elke herverbinding stuurt de frontend het open gesprek als `history`-frame over de WebSocket
  (`ChatPage.jsx`, `sendHistory` in `useChat.js`). De server neemt die tekst over (`_handle_history` en
  `_open_conversation` in `routes/chat.py`), niet de kopie in de database. Alleen de data-keys komen uit de database,
  via de recepten (#472).
- `_open_conversation` begint met een verse sessie: `turns`, `data_provenance` en `rekenbewijs` zijn leeg.

De gevolgen uit #784:

1. **Assistentbeurten uit de client tellen als bewijs.** `agent/run.py` bouwt `earlier` uit de geschiedenis, en de
   getalcontrole (`maak_getalcontrole` in `agent/controles.py`) telt getallen daaruit als gedekt. Na heropenen komt
   die geschiedenis van de client.
2. **Feedback op een antwoord dat er misschien niet stond.** `core/answer_feedback.py` leest vraag, antwoord, controle
   en stappen via `message_index` uit het opgeslagen gesprek, en dat gesprek schreef de client.
3. **Twee tabbladen** overschreven elkaars beurten (#760).
4. **Een antwoord dat klaarkomt terwijl de client weg is**, wordt nooit bewaard (privacyaudit 29-10, F2).
5. **Een heropend gesprek is armer dan een levend.** Het rapport leest de lineage (`data_lineage` in
   `agent/session_data.py`; zonder lineage staat "onbekend (niet vastgelegd in dit gesprek)" in de prompt,
   `agent/report.py`), het rekenbewijs (`rekenbewijs`) en de kaarten (`_kaarten_in_gesprek`, uit `turns`). Na heropenen
   zijn alle drie leeg, terwijl de knop "Genereer rapport" al aangaat zodra er recepten zijn (`historyDataKeys > 0`,
   `reportEligibility.js`).

### Options
- **A. Zo laten**, maar alleen beurten met een handtekening of hash van de server als bewijs laten tellen, en
  `message_index` vervangen door een bericht-ID.
- **B. De server schrijft elke beurt zelf** (append-only, bij `message_end`); de client bewaart alleen UI-status
  (titel, ingeklapt, deeltekst). Heropenen leest uit de database.
- **C. Mengvorm:** de server bewaart per beurt alleen wat het rapport en de controles nodig hebben (lineage,
  rekenbewijs, kaartcontext, een hash van de gecontroleerde tekst). De client blijft het gesprek PUT'en.

### Decision
- **C.** De client blijft de bron van de gesprekstekst: de PUT, de GET en het `history`-frame houden hun vorm. Naast de
  blob komt per beurt één rij met wat de server zelf vastlegde (zie Datamodel).
- **Twee tabbladen (#760) los van dit besluit, met een eigen controle op de PUT.** Gebouwd in !747: `upsert_conversation`
  weigert met 409 een versie die al bewaarde vragen weglaat, en schrijft alleen op de versie die het las
  (`... AND messages = ?`). De frontend bewaart haar versie dan onder een nieuw id (`afsplitsing` in
  `conversationStore.js`). Dat blijft zo.
- **Niet gekozen:** B, want die is pas nodig bij meerdere pods (zie Trade-off(s)), en A, want een hash zonder lineage en
  rekenbewijs maakt een heropend gesprek niet rijker, en bericht-ID's raken elk pad dat berichten maakt of filtert.

### Datamodel
Nieuwe tabel `beurtbewijs`, in `_SCHEMA` van `persistence/db.py` (dezelfde DDL voor SQLite en PostgreSQL, #825):

| Kolom | Type | Inhoud |
|---|---|---|
| `username` | TEXT NOT NULL | de eigenaar, zoals in `conversations` |
| `conv_id` | TEXT NOT NULL | het gesprek-id van de PUT waarin de tekst stond |
| `tekst_hash` | TEXT NOT NULL | sha256 (hex) van de UTF-8-tekst die `message_end` als `content` stuurde: de tekst na de controles, die de frontend ongewijzigd als `content` bewaart |
| `lineage` | TEXT NOT NULL | JSON `{data_key: {name, arguments}}`: wat `record_data_key` sinds de vorige beurt van deze sessie aan `data_provenance` toevoegde |
| `rekenbewijs` | TEXT NOT NULL | JSON-lijst van `{tool, argumenten, resultaat}`: wat `record_rekenbewijs` sinds de vorige beurt toevoegde |
| `kaarten` | TEXT NOT NULL | JSON `{data_key: {...}}`: de kaarten die deze beurt tekende, alleen met de velden van `_KAARTREGEL_ARGUMENTEN` (geen titel en geen rijen, #211) |
| `created_at` | TEXT NOT NULL | ISO-tijd van `message_end` |
| `controle` | TEXT NOT NULL DEFAULT `'[]'` | JSON-lijst met de meldingen die `message_end` als `controle` droeg (#876, besluit 2). Toegevoegd met `_voeg_kolom_toe` in `_migrate`; een rij van daarvóór heeft een lege lijst |

Primaire sleutel `(username, conv_id, tekst_hash)`. Die dekt ook beide leesvragen: per gesprek, en per gesprek en hash.

- **Wat een beurt is:** wat `_process_message` aan `turns` toevoegt, dus een afgerond antwoord, ook een vast antwoord
  uit code. Een gestopt, afgebroken of mislukt antwoord en een verduidelijkingskaart krijgen geen rij. Wat die aan
  lineage of rekenbewijs opleverden, gaat mee in de rij van de volgende beurt ("sinds de vorige beurt"). Zo is een
  heropend gesprek gelijk aan het levende gesprek na zijn laatste afgeronde beurt.
- **Sleutel op de tekst, niet op een index:** berichten hebben geen ID en de index verschuift (`restorableMessages`
  filtert bij heropenen, `useChat.js` haalt een geweigerde vraag weg). De hash koppelt een rij aan de tekst die de
  client terugstuurt, waar die ook staat. Een tekst die de client veranderde, vindt geen rij; dan telt de beurt als niet
  van de server (fail closed). Dezelfde tekst twee keer in één gesprek geeft één rij: de tweede beurt voegt haar items
  toe, en voor de lineage wint de eerste maker, zoals in `data_provenance`.
- **Waarom op de server en niet in de blob:** het rapport zet de lineage als `herkomst` in de datasetcontext die zijn
  controles lezen, en het rekenbewijs is bewijs voor die controles (#397). Wat de client kan schrijven, hoort daar
  niet in.
- **Grootte:** het rekenbewijs bewaart het hele toolresultaat, zoals nu in de sessie. Bij het lezen geldt dezelfde grens
  als live (`_MAX_REKENBEWIJS`, de laatste 30). Ter vergelijking: een PUT met twee kaarten en tien figuren is 0,40 MiB
  (#785).

### Koppeling aan de PUT, heropenen, rapport en feedback
- **Schrijven, zoals de recepten (#472).** Bij `message_end` kent de server het gesprek-id niet; dat kiest de frontend.
  De sessie zet de rij daarom klaar in het geheugen, per `(username, tekst_hash)` en begrensd zoals `_wachtend` in
  `agent/recepten.py`. Na een geslaagde PUT (`routes/persistence.py`, naast `recepten.bewaar`) schrijft de server een
  rij onder dat gesprek-id voor elk assistentbericht in de body waarvan de hash klaarstaat. Een klaarstaande rij blijft
  na het schrijven staan tot de grens haar verdringt, zoals een recept. Een 409 schrijft niets; de afsplitsing die de
  frontend daarna PUT, krijgt de rijen onder haar nieuwe id. Frame en body veranderen niet.
- **Heropenen en herverbinden.** `_handle_history` leest de rijen van `(username, conv_id)` en de klaarstaande rijen met
  een hash uit het frame. `_open_conversation` vult daarmee `data_provenance`, `rekenbewijs` en de kaarten van de
  sessie, in de volgorde van de beurten. De hash gaat over de tekst zoals het frame haar brengt, vóór `_parse_history`
  inkort of markeert; zo krijgen ook beurten die buiten de modelgeschiedenis vallen hun lineage terug. Het vraagnummer
  per key (`data_vraag`, #733) wordt niet bewaard: het volgt uit de plaats van de beurt in het heropende gesprek, net als
  `gebruikersvragen`. De gesprekstekst zelf blijft uit het frame komen, niet uit de database.
- **Wat een rapport voortaan leest:** dezelfde sessievelden als live (`data_lineage`, `rekenbewijs`, `data_vraag`, de
  kaarten). Alleen `_kaarten_in_gesprek` leest naast `turns` ook de kaarten uit de rijen. Een gesprek zonder rijen geeft
  hetzelfde rapport als nu.
- **Controles.** In een live sessie verandert niets: daar zette de server de berichten zelf in `session["messages"]`. Na
  heropenen of herverbinden telt een assistentbericht alleen als bewijs in `earlier` als het een rij heeft (besluit 1):
  `zet_terug` onthoudt de hashes van de berichten zonder rij, en `eerdere_antwoorden` (`agent/beurtbewijs.py`) laat ze
  weg uit `earlier` in `agent/run.py`. Dat geldt voor de getalcontrole (`maak_getalcontrole`) en voor het "eerdere
  gesprek" van `weigering`. Wat de server na heropenen in dezelfde sessie schrijft, telt wel. De controles zelf
  (`agent/controles.py`) veranderen niet.
- **Feedback** (verwijderd 09-11, #983; zie hieronder). De sleutel van `answer_feedback` blijft `(username, conversation_id, message_index)`. `antwoord_trace`
  zoekt de rij van het bericht op die index op via de hash (`beurtbewijs_controles`, alleen hash en controle), en de
  trace krijgt `tekst_hash` en `server_beurt`. Zo is ook na een verschoven index na te gaan bij welk antwoord de melding
  hoort. De `controle` in de trace komt uit de rij, niet uit de blob; feedback op een tekst zonder rij wordt aangenomen
  met `server_beurt: false` en zonder controle (besluit 2). `als_markdown` toont beide. Vraag, antwoord, stappen en
  ingetrokken tekst blijven uit de blob komen.

### Bewaren en verwijderen
Dezelfde termijn als het gesprek. `docs/privacy.md` krijgt een rij voor `beurtbewijs`, in de tabel en in de tekst in de
app.

- **Gesprek verwijderen:** `ruim_gesprek_op` (`persistence/db.py`) verwijdert de rijen van het gesprek in dezelfde
  transactie. De klaarstaande rijen met een hash uit dat gesprek gaan uit het geheugen, zoals bij `recepten.vergeet`.
- **Opschonen** (CronJob, `persistence/opschonen.py`): de rijen gaan met hun gesprek mee via `ruim_gesprek_op`. Een rij
  zonder gesprek gaat 90 dagen na `created_at`, zoals een recept zonder gesprek. `beurtbewijs` komt in `SOORTEN`.
- **"Verwijder al mijn gegevens"** (`persistence/verwijderen.py`): één `DELETE ... WHERE username = ?` in `DELETES`, en
  de klaarstaande rijen van de gebruiker gaan uit het geheugen, zoals bij `recepten.vergeet_gebruiker`.
- **Export** (`persistence/export.py`): een soort `beurtbewijs` met `conv_id`, `tekst_hash`, `lineage`, `rekenbewijs`,
  `kaarten`, `controle` (sinds #876) en `created_at`, in de volgorde van `DELETES` (`tests/test_mijn_gegevens_verwijderen.py` bewaakt dat).
- **Log:** op INFO alleen aantallen en kenmerken, nooit lineage, argumenten of resultaten (#475).

### Migratie
- Alleen een nieuwe tabel (`CREATE TABLE IF NOT EXISTS` in `_SCHEMA`). `conversations`, de PUT, de GET en het
  WebSocket-protocol blijven gelijk. Terugdraaien is de code terugzetten; de tabel mag blijven staan.
- Geen backfill: van bestaande gesprekken heeft de server nooit lineage of rekenbewijs bewaard. Zij heropenen zoals nu
  (lineage "onbekend", geen rekenbewijs), en elke nieuwe beurt krijgt wel een rij.
- Een herstart vóór de PUT gooit de klaarstaande rijen weg, zoals de wachtende recepten. Die beurten tellen dan als niet
  van de server.

### Rationale
- **Lost de gevolgen op die nu schuren:** gevolg 5 (een rapport op een heropend of herverbonden gesprek krijgt dezelfde
  context als live) en gevolg 1 (na heropenen telt alleen een eigen beurt als bewijs). Voor gevolg 2 geeft de hash de
  koppeling.
- **Klein en omkeerbaar:** één tabel, geen migratie van gesprekken, geen nieuw protocol. De deelteksten na een
  verbindingsbreuk (#635, #652) blijven van de client.
- **Hetzelfde patroon als de recepten (#472):** klaarzetten in de sessie, schrijven bij de PUT, opruimen met het
  gesprek.

### Trade-off(s)
- **Niet opgelost: gevolg 4.** Een antwoord dat klaarkomt terwijl de client weg is, staat niet op de server, en zonder
  PUT komt er ook geen rij.
- **Eén pod:** de PUT moet bij hetzelfde proces uitkomen als de WebSocket, zoals nu al voor de recepten (#677).
- Twee kopieën: de tekst in de blob, het bewijs in de tabel. De hash is het enige verband.
- **B wordt nodig** zodra een van deze zich voordoet:
    - #677 kiest voor meer dan één pod: de PUT kan dan op een andere pod landen dan de WebSocket, en daar staan de rijen
      (en de recepten) niet klaar;
    - gevolg 4 moet dicht, bijvoorbeeld omdat de privacytekst belooft dat elk antwoord op de server staat;
    - feedback of controles hebben een vast bericht-ID nodig dat de hash niet kan geven;
    - de blob haalt de verzoeklimiet van 4 MiB (#785).

### Besluiten op de open vragen (2026-11-09, #876)
1. **Een assistentbericht zonder rij telt niet als bewijs** na heropenen of herverbinden: niet voor `earlier` en de
   getalcontrole, en niet als "eerder gesprek" voor de weigering. Dat geldt voor een gesprek van vóór de migratie, een
   herstart vóór de PUT, een gestopt antwoord en een tekst die de client toevoegde of veranderde. Alleen een bericht
   waarvan de hash een rij vindt (in de database of klaarstaand) telt. Een levende sessie blijft gelijk. De prijs: een
   vervolgvraag op zo'n gesprek krijgt vaker een herschrijving, een weggelaten getal of de weigering, tot de vraag
   opnieuw data ophaalt.
2. **Feedback op een antwoord zonder rij wordt aangenomen**, met `server_beurt: false`; de trace krijgt `tekst_hash`
   en `server_beurt`. **De controle-uitkomst staat in de rij** (kolom `controle`), zodat de trace haar niet uit de blob
   leest die de client schreef. Zonder rij heeft de trace geen controle.

### Feedback verwijderd (2026-11-09, #983)
De duimpjes onder een antwoord zijn uit de app (besluit gebruiker 09-11), en daarmee `POST`/`GET /api/answer-feedback`,
de trace (`core/answer_feedback.py`, `antwoord_trace`, `als_markdown`, `scripts/antwoordfeedback.py`) en
`beurtbewijs_controles`. Gevolg 2 hierboven bestaat dus niet meer, en besluit 2 geldt alleen nog voor de rij: de
kolom `controle` blijft geschreven en gaat mee in de export van "Mijn gegevens", maar geen code leest haar nog. De rij
zelf en besluit 1 (alleen eigen beurten als bewijs) blijven ongewijzigd. Bestaande rijen in `answer_feedback` blijven
tot de opschoning of tot de gebruiker al zijn gegevens verwijdert; export, verwijderen en ontkoppelen bij het
verwijderen van een gesprek nemen ze mee. De tabel weghalen is een vervolgstap.

### Open vragen
3. De instelling per beurt (`turns[].instelling`, #543) valt buiten de vier velden van het besluit. Na heropenen weet
   `_beurtcontext` daardoor niet dat de instelling in het gesprek wisselde. Hoort die in de rij? (Zonder besluit niet
   meegenomen in #875.)

---

## ADR-010: Eén ID-contract `bron:id` voor alle bronnen, eerst in schaduwmodus

**Date:** 2026-11-05 (besluit 2026-11-04 op #890); bijgewerkt 2026-11-05 (#914)
**Status:** Decided; sinds #914 het enige pad: de vlag `BRON_ID_CONTRACT` en de oude herleiding zijn weg
**Issue:** #912 (epic #890; nulmeting #909, verhuizing #910, importgrenzen #911, acceptatie #913, opruimen #914)

### Problem
Welke bron bij een ID hoort, werd op drie plekken beslist, elk met een eigen regel: `tools/catalog.py` `bron_id` en
`cbs_bron_id` (voorvoegsel eraf, hoofdletterongevoelig zoeken in de inventaris) en `tools/duo.py` `bron_van` (het
voorvoegsel van een datasleutel). Het CBS-pakket en riodata hadden elk een eigen catalogus en een eigen validatie; de
chat voegde ze zelf samen. Foutieve bronkeuzes ontstaan op die naden. Tegelijk staan in opgeslagen recepten,
gesprekken en rapporten op test en playground allerlei ID-vormen (#909): `85423NED` naast `80040ned`, `cbs_85423ned`,
`duo:p01hoinges`, `P01HOINGES`, `rio/aangeboden-opleidingen`, `ais2030`. Recepten worden niet gemigreerd.

### Decision
- **Eén type `BronId(bron, id)`** met `parse` en `normaliseer` in `onderwijsbronnen._kern.bron_id`; `str()` geeft
  `bron:id` in de spelling van de catalogus (`cbs:85423NED`, `cbs:71733ned`, `duo:p01hoinges`). Het `Register` kent per
  bron de ID's uit de catalogus; `onderwijsbronnen.register()` bouwt het uit `<bron>.metadata(record)["id"]`.
- **Elke opgeslagen vorm is een alias**, altijd: met voorvoegsel (`cbs:`, `cbs_`, `cbs/`, `duo:`, `rio/`, `roa:` …),
  zonder voorvoegsel en in elke hoofdletterspelling. Een kale ID die bij twee bronnen past, is `AmbigueBronId` met de
  opties, nooit een stille keuze; een onbekende ID is `OnbekendBronId`. Een test bewaakt dat geen ID in twee bronnen
  (of twee records) voorkomt en dat elk record heen en terug naar zichzelf herleidt.
- **Eén samengevoegde catalogus**: `onderwijsbronnen.catalogus()` geeft per bron haar records, CBS eerst. De chat
  leest die en voegt geen twee catalogi meer zelf samen.
- **In de chat één plek**: `tools/bron_ids.py` (`bron_id`, `cbs_tabel_id`, `bron_van`) vervangt de drie oude
  functies. De vlag `BRON_ID_CONTRACT` kiest: `uit` (oude herleiding), `schaduw` (oude herleiding beslist, de nieuwe
  draait ernaast; elk verschil komt als `BRON_ID_VERSCHIL` met een telling in het log) of `aan` (het contract
  beslist). Standaard `uit`; test draait `schaduw`. Dat was de overgang; zie **Afgerond (#914)** hieronder.
- **Niet nu:** waarden die het model ziet (`source="riodata"` in `search_catalog`, toolbeschrijvingen) en het
  catalogusformaat blijven gelijk; dat vraagt een eval tegen de nulmeting. BRIN- en bestuursnummers vallen buiten dit
  contract (#728): die identificeren een instelling, geen dataset.

### Rationale
- **Eén regel, één plek:** een nieuwe bron of een nieuwe spelling verandert één functie, en de test "elk ID hoort bij
  precies één bron" maakt een botsing rood vóór ze een verkeerde bronkeuze wordt.
- **Bewijs vóór overstap:** de nulmeting (`tests/test_bron_id_vormen.py`) draait onder `uit`, `schaduw` en `aan` en
  eist in `schaduw` nul verschillen voor elke opgeslagen vorm. Op test laat het schaduwlog zien of echte gesprekken
  vormen bevatten die de fixture mist (#913).
- **Terugvalknop:** de vlag schakelt zonder nieuwe release terug (`docs/promoten.md`, bevriezing).

### Trade-off(s)
- In `aan` herleidt het contract ook vormen die de oude regel niet kende (`roa:ais2030` → `ais2030`); dat zijn
  verbeteringen, en ze staan vooraf in het schaduwlog.
- Zonder vlag is er geen terugval meer zonder release: een fout in het contract herstel je met een fix of met de pin
  van playground terug naar een release van vóór #914 (`docs/promoten.md`).
- **Heroverwegen** zodra een van deze zich voordoet:
    - het schaduwlog op test toont een verschil voor een vorm die gebruikers echt opsloegen;
    - een nieuwe bron heeft ID's die met een bestaande bron botsen (de test wordt rood);
    - het model moet het volledige `bron:id` gaan zien (dan eerst een eval tegen de nulmeting).

### Afgerond (#914, 2026-11-05)
- **Geen schaduwperiode** (besluit gebruiker 05-11, comment op #913): het schaduwlog op test gaf 0 verschillen sinds
  de deploy van 80a77d9a, en de nulmeting en de volledige suite waren groen onder alle drie de standen. Release 2.7.0
  ging met `BRON_ID_CONTRACT=aan` naar test en playground.
- **De vlag en de oude herleiding zijn weg:** `tools/bron_ids.py` volgt alleen het contract (`parse_bron_id`,
  `bron_van_sleutel`); `_oud_*`, de modus, de telling en de logregel `BRON_ID_VERSCHIL` bestaan niet meer, en
  `core/config.py` leest de vlag niet meer. `manifests/test` zet hem niet meer; `manifests/playground` houdt hem tot
  de eerste promotie van een release met #914, omdat 2.7.0 hem nog leest (zonder vlag zou 2.7.0 terugvallen op `uit`).
- **De aliassen blijven:** elke vorm uit de nulmeting (`tests/fixtures/bron_id_vormen.json`, ongewijzigd) herleidt
  onder het contract naar dezelfde bron, dataset en hetzelfde bestand (`tests/test_bron_id_vormen.py`).
- **Ook weg:** de overgangsnamen `riodata` en `onderwijsdata` (shims uit #910). Opgeslagen recepten noemen geen
  modulepaden (#909); oude snippets installeren hun eigen commit van de oude pakketten en draaien daartegen
  (live-test in `tests/test_bron_id_vormen.py`). Pakketversie 0.9.0.
- **Nog niet:** `source="riodata"` in `search_catalog` en de toolbeschrijvingen; dat vraagt een eval (vervolg).

---

## ADR-011: De eerste productie draait bewust één pod; schaalbaar maken is een vervolgepic

**Date:** 2026-11-09 (besluit gebruiker 09-11 op #677)
**Status:** Decided
**Issue:** #677 (vervolgepic #984; graceful shutdown #675; productie uitrolbaar #674)

### Problem
De app kan maar met één pod draaien. De datastore (`tools/store.py`), de limieten (`core/rate_limit.py` voor login,
berichten en feedback; `core/gelijktijdig.py` voor verbindingen, runs en sandboxplaatsen, #688), de SRAM-gebruikerscache
(`routes/auth.py` `_oidc_user_cache`) en de nog niet opgeslagen recepten (`agent/recepten.py` `_wachtend`) leven in het
geheugen van het proces. Met twee pods komt een CSV-download, een dashboard-refresh of het opslaan van een gesprek
(`PUT /api/conversations/{id}`) soms bij de pod die die staat niet kent, en tellen alle limieten per pod. Tegelijk
betekent één pod: geen hoge beschikbaarheid, en elke uitrol een onderbreking (op test bij `Recreate` 8 minuten 503,
29-10). De docs beloofden eerder 3–10 replica's met HPA; dat is in !655 rechtgezet.

### Decision
- **Optie A nu:** de eerste productie draait bewust één pod. `replicaCount: 1` in elke omgeving, geen HPA en geen PDB;
  de HPA-knop (`autoscaling.enabled` zonder HPA-template) is uit de chart. `tests/test_manifests.py` toetst per omgeving
  de gerenderde chart.
- **Stoppen op orde:** `preStop` 5 s (Traefik laat de pod los voordat uvicorn stopt met luisteren), uvicorn 45 s voor
  lopende HTTP-verzoeken, `terminationGracePeriodSeconds: 60`. Een lopend antwoord redden we niet: uvicorn sluit een
  chat-WebSocket bij het stoppen met 1012. De frontend herkent 1012, zegt "De app wordt bijgewerkt" en blijft tot
  12 minuten herverbinden; het afgebroken antwoord krijgt "Probeer opnieuw".
- **Productie houdt de standaard RollingUpdate** (`maxSurge 1`, `maxUnavailable 0`): de oude pod stopt pas als de
  nieuwe klaar is. Laat het quotum van de productie-tenant geen tweede pod toe, dan `Recreate` zoals op test (#674).
- **Beschikbaarheid eerlijk benoemen** (besluit gebruiker 09-11), in `docs/operatie.md` (Beschikbaarheid):
    - **Geen vaste onderhoudsvensters.** Productie rolt uit wanneer dat nodig is; de melding "De app wordt bijgewerkt"
      en het automatisch opnieuw verbinden vangen dat op.
    - **Best effort, geen streefwaarde.** Geen percentage. De tekst beschrijft wat gebruikers bij een uitrol of storing
      zien en, in algemene termen, hoe we reageren, zonder reactie- of hersteltijd.
    - **Plek:** `docs/operatie.md`, publiek op de documentatiesite, en input voor de afspraken met Npuls en SURF AI
      Chat (#711). Niet in de app.
- **Optie B als vervolgepic (#984):** limieten en SRAM-cache naar Postgres, sticky sessions of een gedeelde store,
  daarna twee replica's met RollingUpdate en een PDB.

### Rationale
- **Klein en nu:** A vraagt geen wijziging in de datalaag; B raakt limieten, gelijktijdigheid, recepten en de ingress,
  en vraagt quotum voor twee pods. De eerste productie hoeft daar niet op te wachten.
- **Geen schijnzekerheid:** een PDB met één pod blokkeert een node-drain (`minAvailable: 1`) of beschermt niets
  (`maxUnavailable: 1`); een HPA zou de staat in het geheugen over pods verdelen. Liever geen knop dan een knop die
  stuk is.
- **Een duidelijke melding is haalbaar, een gered antwoord niet:** een antwoord mag tot `RUN_TIMEOUT_S` (300 s) duren.
  Een drain van die lengte verlengt bij `Recreate` de 503 voor iedereen, en bij RollingUpdate vraagt het een tweede pod
  die de staat van de eerste niet kent.

### Trade-off(s)
- Elke uitrol, herstart, node-drain of OOM is een onderbreking voor alle gebruikers; lopende antwoorden gaan verloren.
- Limieten beginnen na een herstart op nul (login, berichten).
- Met RollingUpdate draaien tijdens een uitrol kort twee pods; een CSV-download of dashboard-refresh in dat venster
  kan de verkeerde pod treffen. De recepten (#472) maken de data daarna weer herstelbaar.
- **Heroverwegen** zodra een van deze zich voordoet:
    - productie krijgt gebruikers die een onderbreking midden op de dag niet accepteren, of er komt een SLA met een
      streefwaarde;
    - het quotum laat twee pods toe en #984 stap 1 (limieten en cache naar Postgres) is klaar;
    - de server schrijft zijn beurten zelf weg (#784), waardoor de recepten niet meer per proces hoeven te wachten.

---

## How to add a new ADR

1. Increment the number (ADR-008, etc.)
2. Add to this file with:
   - Date
   - Status (Decided, Proposed, Deprecated)
   - Related issue(s)
   - Context, Decision, Rationale, Trade-off(s)
3. Link from relevant code (e.g., comments referencing "see ADR-001")

**Status meanings:**
- **Proposed** — Under discussion, not yet implemented
- **Decided** — Implemented, team agrees
- **Deprecated** — No longer applies, kept for history
