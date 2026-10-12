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
- `run_analysis` executes model-written Python; a sandbox with file I/O blocked is still open work.
- Each check covers one class of error; a new class of error passes until a check exists for it. When the set of check modules keeps growing, revisit this decision.

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
  kolomsleutels. De server compileert hieruit `$filter`/`$select` (`tools/cbs_selectie.py`).
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

## How to add a new ADR

1. Increment the number (ADR-006, etc.)
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
