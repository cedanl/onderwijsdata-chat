# Anti-hallucinatie architectuur

## Het probleem

Statistiekbureaus (ONS, Statistics Canada) hebben hun RAG-chatbots stilgezet omdat ze oncontroleerbare getallen genereerden. Dit gebeurt omdat LLMs getallen kunnen "verzinnen" wanneer ze niet opgelet worden.

**Voorbeeldhallucinatie:**
```
Q: "Hoeveel HBO-studenten volgen Informatica?"
A: "Ongeveer 15.000 HBO-studenten volgen Informatica in Nederland."
     ^^^^^^^^^^
     Verzonnengetal — niet uit data
```

Dit risico is onacceptabel voor instellingen die op cijfers worden afgerekend.

## Onze aanpak: 4-laag verdediging

Dit systeem maakt het onmogelijk voor de LLM om getallen te verzinnen. Elke laag blokkeert een ander aanvalspad.

### Laag 1: data_key — geen datarijen in context

**Wat:** De LLM krijgt nooit daadwerkelijke datawaarden te zien. In plaats daarvan krijgt het alleen een referentie (`data_key`).

**Hoe:**
```python
# LLM sees this:
"Please analyze the data in data_key='duo:p02ho1ejrs:resource_0'"

# LLM does NOT see:
# AANTAL_INGESCHREVENEN  STUDIEJAAR  ONDERDEEL
# 2500                   2023        HBO
# 3100                   2024        HBO
# ...
```

**Effect:** Geen getallen om op te pikken of te "veranderen".

---

### Laag 2: compute_kpi — server berekent, model refereert

**Wat:** De LLM roept een tool aan, maar krijgt niet de ruwe data terug — alleen het antwoord.

**Hoe:**
```python
# LLM calls:
compute_kpi(
    data_key="duo:p02ho1ejrs:resource_0",
    metric="sum",
    value_column="AANTAL_INGESCHREVENEN",
    group_by="ONDERDEEL"
)

# Server returns:
{
    "HBO": 5600,
    "WO": 8900
}

# LLM then outputs:
"The total is 5600 HBO students."
#               ^^^^
#               Dit getal is uit de tool, niet verzonnengetal
```

**Effect:** Getallen komen altijd uit gestructureerde tool-respons, nooit uit context of hint.

---

### Laag 3: AST-check — 6+ cijfers in output geweigerd

**Wat:** Model-output wordt geparst. Alle literal getallen ≥6 cijfers worden geweigerd.

**Hoe:**
```python
# Model tries to output:
"The country's total revenue is 3,500,000 euros."

# AST-parser sees: 3500000 (7 digits)
# Rejected: "Getallen ≥6 cijfers alleen via tools toestaan"

# Allowed:
"The country has 5600 HBO students."
                ^^^^
                4 digits, OK — sowieso onwaarschijnlijk verzonnengetal
```

**Effect:** Model kan niet casually grote getallen noemen.

---

### Laag 4: _check_number_sourcing — elk getal traceerbaar

**Wat:** Elk getal in de uiteindelijke response wordt geverifieerd: Het MOET afkomstig zijn van een tool-aanroep.

**Hoe:**
```
Response: "HBO had 5600 students in 2023, WO had 8900."
Numbers:  5600, 8900

Trace:
- 5600 → Found in compute_kpi output ✓
- 8900 → Found in compute_kpi output ✓

All numbers sourced. ✓
```

Zou dit mislukken:
```
Response: "HBO had 5600 students, but I estimate WO could reach 9500 by 2025."
Numbers:  5600, 9500

Trace:
- 5600 → Found in compute_kpi output ✓
- 9500 → NOT in any tool output ✗

Rejected: "9500 is not sourced from a tool call"
```

**Effect:** Geen speculatie, geen voorzeggen, geen gissingen — alleen data.

---

## Resultaat: onbreekbare contracten

| Scenario | Laag 1 | Laag 2 | Laag 3 | Laag 4 | Uitkomst |
|----------|--------|---------|---------|---------|----------|
| Model verzint "10000" | ✓ Ziet het getal niet | — | ✗ 5 digits OK | — | **Geweigerd door laag 3** |
| Model verzint "1000000" | ✓ Ziet het getal niet | — | — | ✗ Niet getraced | **Geweigerd door laag 4** |
| Model refereert aan tool output | ✓ Ziet key | ✓ Krijgt output | ✓ OK | ✓ Getraced | **Aanvaard** |

## Implementatie

**Files:**
- `tools/cbs.py`, `tools/duo.py` — Laag 1: data_key loading
- `tools/dashboard.py` — Laag 2: compute_kpi tool
- `agent/run.py` — Laag 3: AST-check op output
- `tools/cbs.py` — Laag 4: _check_number_sourcing validation

**Tests:**
- `tests/test_eval_*.py` — Eval-suite verifieert dat uitvoer alleen getallen uit tools bevat

## Voor auditors

U kunt dit zelf verifiëren:

1. **Vraag de Python-snippet:** Elke analyse exporteert als `.py` bestand
2. **Voer het uit:** `python analyse.py`
3. **Vergelijk getallen:** Uw output matcht precies wat de app rapporteerde

Geen "zwarte doos", geen speculatie. Alleen data.

---

**Zie ook:** [Reproduceerbare analyses](reproducibility.md), [ADR-001](architecture-decisions.md#adr-001-anti-hallucinatie-via-server-side-compute)
