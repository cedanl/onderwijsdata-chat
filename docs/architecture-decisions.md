# Architecture Decision Records (ADRs)

This document captures major architectural decisions and their rationale. Each decision explains the context, options considered, and why we chose this path.

## ADR-001: Anti-hallucinatie via server-side compute

**Date:** 2026-09-22 (revised 2026-10-02: limits stated)  
**Status:** Decided  
**Issue:** #39, #8

### Problem
Language models hallucinate numbers when unsupervised. Other statistical agencies (ONS, Statistics Canada) have stopped deploying RAG chatbots due to this risk.

### Decision
The server loads and computes; the model selects and phrases. Four layers:

1. **data_key** — No data rows in context; the model gets a key, the schema and a short preview.
2. **Compute in code** — `query_data` (aggregation) and `compute_kpi` (difference, percentage, index, largest drop/rise) return the numbers; the model copies them.
3. **run_analysis guard** — An AST check rejects a script with a literal data structure of six or more numbers (retyped data) or one that reads no data.
4. **Answer checks** — Every chat answer is checked against the tool results: numbers (`agent/grounding.py`), selection, labels and binding (`agent/selectie.py`, `agent/labels.py`, `agent/binding.py`). A failure triggers one correction round; a remaining problem stays visible on the answer. Dashboards use `_check_number_sourcing` in `agent/dashboard.py`, reports `agent/report_checks.py`.

### Rationale
- **Auditable:** each number can be traced to the tool call that produced it.
- **Reproducible:** every analysis exports as a Python snippet that can be rerun.
- **Detectable:** a number that is not in the data is caught by code, not left to the prompt.

### Trade-off and limits
More orchestration, and the checks reduce the risk; they do not eliminate it. Known gaps, described in [Anti-hallucinatie architectuur](anti-hallucination-architecture.md#wat-dit-niet-dekt):

- Numbers under four digits and years are not checked; percentages are matched as value or fraction.
- Binding only works when a sentence names exactly one year and one institution.
- Numbers from earlier messages in the conversation count as sourced, including numbers the user gave.
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
- Users download `.py` file alongside the answer
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
  en instelling) en de andere controlemodules, die `agent/run.py` na elk antwoord draait. Er
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
