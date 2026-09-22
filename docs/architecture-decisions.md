# Architecture Decision Records (ADRs)

This document captures major architectural decisions and their rationale. Each decision explains the context, options considered, and why we chose this path.

## ADR-001: Anti-hallucinatie via server-side compute

**Date:** 2026-09-22  
**Status:** Decided  
**Issue:** #39, #8

### Problem
Language models hallucinate numbers when unsupervised. Other statistical agencies (ONS, Statistics Canada) have stopped deploying RAG chatbots due to this risk.

### Decision
Implement a 4-layer defense where the server computes all numbers and the model only references them:

1. **data_key** — No data rows in context; only a key (e.g., `duo:p02ho1ejrs:resource_0`)
2. **compute_kpi** — Server calculates metrics; model just outputs the variable name
3. **AST-check** — Reject literals ≥6 digits in model output (prevents "making up" numbers)
4. **_check_number_sourcing** — Every number in the response must originate from a tool call

### Rationale
- **Deterministic:** Server controls all numbers; model cannot invent them
- **Auditable:** Each number traced to its source tool call
- **Reproducible:** Users can re-run the Python snippet and verify

### Trade-off
Slightly more complex orchestration, but eliminates hallucination risk entirely.

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
