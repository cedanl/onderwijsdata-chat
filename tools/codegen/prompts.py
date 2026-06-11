
# Tools that produce no reproducible output
SKIP_TOOLS = {"search_catalog", "suggest_followups", "get_cbs_dimension"}

CLEANUP_SYSTEM = (
    "Je bent een code-optimizer. Gegeven een genummerde lijst API-aanroepen die een LLM heeft gedaan "
    "om een vraag te beantwoorden, geef je ALLEEN de indices terug van aanroepen die essentieel zijn "
    "voor het eindresultaat.\n"
    "Verwijder: explorerende mislukkingen, get_duo_data-aanroepen waarvan de data_key nooit door "
    "een opvolgende query_data wordt gebruikt, en dead-ends.\n"
    "Houd: aanroepen die direct bijdragen aan het antwoord (query_data, create_plot, "
    "get_cbs_data, get_rio_data, get_duo_data die wél gebruikt wordt).\n"
    "Antwoord uitsluitend met een JSON-array van integers, bijv. [0, 2, 4]. Geen uitleg."
)

ANALYSIS_CODE_SYSTEM = """\
Je genereert reproduceerbare Python code voor een data-analyse.
Schrijf ALLEEN Python code — geen markdown, geen uitleg, geen codeblok-markers.

ABSOLUTE REGEL: Hardcode NOOIT data als Python-literals.
- Verboden: lijsten of dicts met vaste waarden, bijv. [{"JAAR": 2024, "Aantal": 79892}, ...]
- Verboden: hardgecodeerde DataFrames, bijv. pd.DataFrame([{"x": 1}, ...])
- Alle data moet dynamisch worden opgehaald via API-aanroepen of bestandsinlezen.

Gebruik pandas voor transformaties en plotly.express voor visualisaties.
Sluit elke visualisatie af met fig.show().

Regels voor API-aanroepen:
- Roep de tools aan — ze zijn beschikbaar via 'from tools import ...'
- Parse het resultaat naar een DataFrame:
    query_data   → df = pd.DataFrame(json.loads(result)['rijen'])
    get_cbs_data → df = pd.DataFrame(json.loads(result)['value'])
    get_rio_data → df = pd.DataFrame(json.loads(result))
- Zet numerieke kolommen om: df[col] = pd.to_numeric(df[col], errors='coerce')
- Gebruik 'import json' voor het parsen

Regels voor geüploade bestanden:
- Laad CSV: df = pd.read_csv(bestand, sep=None, engine='python', dtype=str)
- Laad Excel: df = pd.read_excel(bestand, dtype=str)
- Zet numerieke kolommen om na het inladen

Vervang create_plot ALTIJD door plotly.express — gebruik de opgegeven chart_type, x, y, title en color_by.\
"""

LEESMIJ = """\
# Onderwijsdata analyse

Gegenereerde Python-bestanden voor het reproduceren van de analyse uit de chat.

## Vereisten

Python 3.11 of hoger.

**Met uv (aanbevolen)**
```
uv venv
uv pip install -r requirements.txt
```

**Met pip**
```
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Voor CBS/DUO/RIO analyses is ook de map `tools/` vereist uit de onderwijsdata-chat repository:

```
git clone https://github.com/cedanl/onderwijsdata-chat.git
cd onderwijsdata-chat
```

Kopieer dan `analyse.py`, `analyse.ipynb` en `requirements.txt` naar de root van de repository.

## Geüploade bestanden

Als de analyse gebaseerd is op een geüpload bestand, zorg dan dat het bestand
aanwezig is in de map waar je het script uitvoert.

## Uitvoeren

```
python analyse.py
```

Of open `analyse.ipynb` in Jupyter of VS Code.
"""

PY_HEADER = """\
\"\"\"
Reproduceerbare analyse — gegenereerd door onderwijsdata-chat
Datum: {today}

Vereist: pip install pandas plotly openpyxl
Voor CBS/DUO/RIO analyses ook: map tools/ uit de onderwijsdata-chat repository.
\"\"\"

import pandas as pd
import plotly.express as px
import json

try:
    from tools import (
        get_cbs_data,
        get_duo_data,
        query_data,
        get_rio_data,
    )
except ImportError:
    pass  # Alleen nodig voor CBS/DUO/RIO analyses

"""
