# Reproduceerbare analyses

## Waarom dit belangrijk is

Onderzoeksinstellingen moeten kunnen aantonen HOE zij tot hun bevindingen zijn gekomen. Een getal zonder code is niet controleerbaar. Dit systeem genereert automatisch het Python-script dat onder de motorkap draait — zodat:

- **Auditeurs** je analyse kunnen nazien
- **Collega's** je bevindingen kunnen reproduceren  
- **Toekomstige onderzoekers** exact kunnen zien wat je hebt gedaan
- **Je** niet hoeft te onthouden welke filters je hebt gebruikt

## Hoe het werkt

### 1. Stel een vraag
```
"Hoeveel eerstejaars hadden HBO opleidingen in 2023?"
```

### 2. De app gebruikt tools

Achter de schermen roept de app functies aan:
- `get_duo_data()` — Laadt DUO dataset
- `query_data()` — Filtert op OPLEIDINGSVORM="VT", JAAR=2023
- `compute_kpi()` — Telt totaal eerstejaars

### 3. Exporteer als code

Elke tool-aanroep genereert Python-snippet. Het app verzamelt ze in één reproduceerbaar script:

```python
# Laad DUO eerstejaars HBO 2023
from riodata import duo
import pandas as pd

# Dataset laden
df = duo.load("p02ho1ejrs", "Eerstejaarsingeschrevenen hoger onderwijs")

# Filter op HBO (ONDERDEEL="HBO")
df = df[df["ONDERDEEL"] == "HBO"]

# Filter op 2023 (STUDIEJAAR=2023)
df = df[df["STUDIEJAAR"] == 2023]

# Aggregatie: som eerstejaars
totaal = df["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
print(f"HBO eerstejaars 2023: {totaal}")
```

### 4. Jij voert het uit

Run het script zelf:
```bash
python analyse.py
```

Resultaat:
```
HBO eerstejaars 2023: 42583
```

Dit getal matcht precies wat de app rapporteerde. Geen gissing, geen "zwarte doos" — pure reproducibiliteit.

## Tools die snippets genereren

| Tool | Wat het genereert |
|------|------------------|
| `query_data` | DataFrame-laad + filters + aggregatie |
| `get_duo_data` | `duo.load()` call + resource |
| `get_cbs_data` | `onderwijsdata.data()` call + filters |
| `compute_kpi` | KPI-formule (sum, mean, delta, %) |
| `run_analysis` | Gebruiker's eigen Python-code |
| `create_plot` | Plotly visualisatie |
| `create_choropleth_map` | Geografische kaart |

## Voor onderzoekers

- Export je chat-sessie na elke analyse
- Voeg snippets toe aan je rapport als "methodologie"
- Laat collega's ze draaien ter verificatie
- Archiveer ze met je onderzoeksgegevens

## Voor auditors

Vraag naar het snippet — de app levert het direct:

> "Toon me de code voor het studentenaantal per opleiding"

Geen ambiguïteit, geen achteraf geknutsel. Het is het óf-of-code dat je gebruiker daadwerkelijk hebt gerund.

## Anti-hallucinatie control

Omdat snippets altijd data-tools gebruiken, kan het model nooit een getal verzinnen:

```
❌ NIET MOGELIJK:
    "Het aantal studenten was 50.000"     ← Getal niet uit tool
    
✓ ALTIJD UIT DATA:
    df.groupby("JAAR")["AANTAL"].sum()    ← Uit data
    compute_kpi(metric="sum", ...)        ← Uit tool
```

Zie [architectuur-keuzes.md](architectuur-keuzes.md) voor details.
