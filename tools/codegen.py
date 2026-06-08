"""Generates a reproducible Python package from a chat session."""

from __future__ import annotations

import json
import logging
from datetime import date

import litellm

# Only skip tools that produce no reproducible output
_SKIP_TOOLS = {"search_catalog", "suggest_followups", "get_cbs_dimension"}

_CLEANUP_SYSTEM = (
    "Je bent een code-optimizer. Gegeven een genummerde lijst API-aanroepen die een LLM heeft gedaan "
    "om een vraag te beantwoorden, geef je ALLEEN de indices terug van aanroepen die essentieel zijn "
    "voor het eindresultaat.\n"
    "Verwijder: explorerende mislukkingen, get_duo_data-aanroepen waarvan de data_key nooit door "
    "een opvolgende query_data wordt gebruikt, en dead-ends.\n"
    "Houd: aanroepen die direct bijdragen aan het antwoord (query_data, create_plot, "
    "get_cbs_data, get_rio_data, get_duo_data die wél gebruikt wordt).\n"
    "Antwoord uitsluitend met een JSON-array van integers, bijv. [0, 2, 4]. Geen uitleg."
)

_ANALYSIS_CODE_SYSTEM = """\
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

_LEESMIJ = """\
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

_PY_HEADER = """\
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


def _is_upload_turn(tool_calls: list[dict]) -> bool:
    """Return True if any query_data call uses an upload: data_key."""
    for tc in tool_calls:
        if tc.get("name") == "query_data":
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except Exception:
                continue
            if args.get("data_key", "").startswith("upload:"):
                return True
    return False


def _has_plot(tool_calls: list[dict]) -> bool:
    return any(tc.get("name") == "create_plot" for tc in tool_calls)


def _plot_config_only(plot_calls: list[dict]) -> list[dict]:
    """Return chart config dicts with the 'data' key stripped.

    Passing data values to the code-gen LLM causes it to hardcode those values
    instead of writing real pandas transformations. Stripping 'data' forces it to
    derive values dynamically from the API calls or uploaded file.
    """
    configs = []
    for tc in plot_calls:
        try:
            args = json.loads(tc.get("arguments", "{}"))
        except Exception:
            args = {}
        configs.append({k: v for k, v in args.items() if k != "data"})
    return configs


def _render_call(name: str, arguments: str) -> str:
    """Fallback renderer for a single tool call (used when LLM code-gen fails)."""
    try:
        args = json.loads(arguments)
    except Exception:
        args = {}

    # Upload data_keys are not available outside a Chainlit session.
    data_key = args.get("data_key", "")
    if isinstance(data_key, str) and data_key.startswith("upload:"):
        filename = data_key[len("upload:"):].split(":")[0]
        return (
            f"# Geüpload bestand '{filename}' — laad het zelf en zet het in de store:\n"
            f"# import pandas as pd\n"
            f"# from tools import store\n"
            f"# store.put('{data_key}', pd.read_csv('{filename}', sep=None, engine='python', dtype=str))\n"
        )

    kwargs = ", ".join(
        f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items()
    )
    return f"result = {name}({kwargs})\nprint(result)\n"


def _to_source_lines(text: str) -> list[str]:
    """Split code into per-line strings as required by the nbformat spec."""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def _turn_code_lines(turn: dict) -> list[str]:
    if "_generated_code" in turn:
        return _to_source_lines(turn["_generated_code"])

    tool_calls = turn.get("tool_calls", [])
    lines = []
    for tc in tool_calls:
        name = tc.get("name", "")
        if name in _SKIP_TOOLS:
            continue
        lines.extend(_to_source_lines(_render_call(name, tc.get("arguments", "{}"))))
    return lines


def build_py(turns: list[dict]) -> str:
    parts = [_PY_HEADER.format(today=date.today())]
    for i, turn in enumerate(turns, 1):
        question = turn.get("question", "").replace("\n", " ")
        parts.append(f"# --- Vraag {i}: {question[:120]}\n")
        code_lines = _turn_code_lines(turn)
        if code_lines:
            parts.extend(code_lines)
        else:
            parts.append("# (geen data-aanroepen in deze beurt)\n")
        parts.append("\n")
    return "".join(parts)


def build_ipynb(turns: list[dict]) -> str:
    cells = []

    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": ["# Onderwijsdata analyse\n", f"Gegenereerd op {date.today()}\n"],
    })
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import pandas as pd\n",
            "import plotly.express as px\n",
            "import json\n",
            "\n",
            "# Alleen nodig voor CBS/DUO/RIO analyses (zie LEESMIJ.md)\n",
            "try:\n",
            "    from tools import get_cbs_data, get_duo_data, query_data, get_rio_data\n",
            "except ImportError:\n",
            "    pass\n",
        ],
    })

    for i, turn in enumerate(turns, 1):
        question = turn.get("question", "").replace("\n", " ")
        answer = turn.get("answer", "") or ""

        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": _to_source_lines(
                f"## Vraag {i}\n**Vraag:** {question}\n\n**Antwoord:**\n{answer[:1000]}\n"
            ),
        })

        code_lines = _turn_code_lines(turn)
        if code_lines:
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": code_lines,
            })

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "cells": cells,
    }
    return json.dumps(nb, ensure_ascii=False, indent=1)


def build_requirements(used_tool_names: set[str]) -> str:
    """Return requirements.txt content with versions from the running environment."""
    import importlib.metadata

    packages = ["plotly", "pandas", "openpyxl"]
    if used_tool_names & {"get_rio_data", "get_duo_data", "query_data"}:
        packages.append("riodata")
    if used_tool_names & {"get_cbs_data", "get_cbs_dimension"}:
        packages.append("cbsodata")

    lines = ["# gegenereerd door onderwijsdata-chat\n"]
    seen: set[str] = set()
    for pkg in packages:
        if pkg in seen:
            continue
        seen.add(pkg)
        try:
            version = importlib.metadata.version(pkg)
            lines.append(f"{pkg}=={version}\n")
        except importlib.metadata.PackageNotFoundError:
            lines.append(f"{pkg}\n")
    return "".join(lines)


async def _cleanup_turn_calls(
    turn: dict,
    model: str,
    extra_litellm_kwargs: dict,
) -> list[dict]:
    """Return a filtered list of tool calls with exploratory failures removed."""
    raw = [tc for tc in turn.get("tool_calls", []) if tc.get("name") not in _SKIP_TOOLS]
    if len(raw) <= 1:
        return raw

    indexed = []
    for i, tc in enumerate(raw):
        try:
            args = json.loads(tc.get("arguments", "{}"))
        except Exception:
            args = {}
        indexed.append({"i": i, "naam": tc["name"], "args": args})

    user_msg = (
        f"Vraag: {turn.get('question', '')[:300]}\n"
        f"Antwoord: {(turn.get('answer') or '')[:500]}\n\n"
        f"Aanroepen:\n{json.dumps(indexed, ensure_ascii=False, indent=2)}"
    )

    try:
        response = await litellm.acompletion(
            model=model,
            max_tokens=150,
            num_retries=2,
            messages=[
                {"role": "system", "content": _CLEANUP_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            **extra_litellm_kwargs,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        indices = json.loads(text)
        if isinstance(indices, list) and all(isinstance(i, int) for i in indices):
            kept = [raw[i] for i in sorted(set(indices)) if 0 <= i < len(raw)]
            if kept:
                return kept
    except Exception:
        logging.debug("codegen cleanup LLM call failed, keeping all tool calls", exc_info=True)

    return raw


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the model wrapped its output."""
    if not code.startswith("```"):
        return code
    lines = code.splitlines()
    start = 1
    end = len(lines)
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip() == "```":
            end = i
            break
    return "\n".join(lines[start:end]).strip()


async def _generate_analysis_code(
    turn: dict,
    model: str,
    extra_litellm_kwargs: dict,
) -> str | None:
    """Generate reproducible pandas/plotly code for a turn with create_plot.

    Key design: the 'data' array from create_plot is intentionally NOT passed to
    the code-gen LLM. Passing it causes the LLM to hardcode those values instead
    of writing real data-retrieval + transformation code. Only chart configuration
    (chart_type, x, y, title, color_by) is passed so the LLM knows what to build
    but must derive all values dynamically.

    Returns Python source as a string, or None on failure.
    """
    tool_calls = turn.get("tool_calls", [])
    plot_calls = [tc for tc in tool_calls if tc.get("name") == "create_plot"]
    if not plot_calls:
        return None

    # Chart config without data values — prevents hardcoding
    plot_configs = _plot_config_only(plot_calls)

    is_upload = _is_upload_turn(tool_calls)
    data_calls = [
        tc for tc in tool_calls
        if tc.get("name") not in _SKIP_TOOLS | {"create_plot"}
    ]

    if is_upload:
        filenames: set[str] = set()
        upload_query_calls = []
        for tc in data_calls:
            if tc.get("name") == "query_data":
                try:
                    args = json.loads(tc.get("arguments", "{}"))
                except Exception:
                    args = {}
                data_key = args.get("data_key", "")
                if data_key.startswith("upload:"):
                    filenames.add(data_key[len("upload:"):].split(":")[0])
                    upload_query_calls.append(args)

        if not filenames:
            return None

        filename = next(iter(filenames))
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

        parts = [
            f"Geüpload bestand: {filename} (extensie: {ext})",
            "",
            f"Vraag: {turn.get('question', '')[:400]}",
            f"Antwoord: {(turn.get('answer') or '')[:600]}",
            "",
            "query_data aanroepen (filters en kolomselectie die werden gebruikt):",
            json.dumps(upload_query_calls, ensure_ascii=False, indent=2),
            "",
            "Grafiekconfiguratie (maak deze grafiek — data DYNAMISCH ophalen uit het bestand):",
            json.dumps(plot_configs, ensure_ascii=False, indent=2),
            "",
            "VERBODEN: schrijf geen enkele hardgecodeerde lijst of dict met data.",
            "Genereer standalone Python code die:",
            "1. Het bestand laadt met pandas",
            "2. De filters en kolomselectie uit query_data toepast",
            "3. Aggregaties uitvoert die passen bij de grafiekconfiguratie",
            "4. De grafiek maakt met plotly.express",
            "Voeg 'import pandas as pd' en 'import plotly.express as px' toe (geen tools-import).",
        ]
    else:
        api_calls_repr = []
        for tc in data_calls:
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except Exception:
                args = {}
            api_calls_repr.append({"tool": tc["name"], "args": args})

        parts = [
            f"Vraag: {turn.get('question', '')[:400]}",
            f"Antwoord: {(turn.get('answer') or '')[:600]}",
            "",
            "API tool calls die werden uitgevoerd (roep deze opnieuw aan om verse data op te halen):",
            json.dumps(api_calls_repr, ensure_ascii=False, indent=2),
            "",
            "Grafiekconfiguratie (maak deze grafiek — data DYNAMISCH ophalen via de API calls):",
            json.dumps(plot_configs, ensure_ascii=False, indent=2),
            "",
            "VERBODEN: schrijf geen enkele hardgecodeerde lijst of dict met data.",
            "Genereer Python code die:",
            "1. De API tool calls uitvoert (importeer via 'from tools import ...')",
            "2. JSON-resultaten parsed naar DataFrames:",
            "   query_data   → df = pd.DataFrame(json.loads(result)['rijen'])",
            "   get_cbs_data → df = pd.DataFrame(json.loads(result)['value'])",
            "   get_rio_data → df = pd.DataFrame(json.loads(result))",
            "3. Numerieke kolommen omzet met pd.to_numeric(..., errors='coerce')",
            "4. Benodigde transformaties uitvoert (hernoemen, groeperen, samenvoegen, berekeningen)",
            "   Afleidbaar uit de antwoordtekst, de API-filters en de grafiekconfiguratie",
            "5. De grafiek maakt met plotly.express",
            "Voeg 'import json', 'import pandas as pd' en 'import plotly.express as px' toe.",
        ]

    try:
        response = await litellm.acompletion(
            model=model,
            max_tokens=1500,
            num_retries=2,
            messages=[
                {"role": "system", "content": _ANALYSIS_CODE_SYSTEM},
                {"role": "user", "content": "\n".join(parts)},
            ],
            **extra_litellm_kwargs,
        )
        code = _strip_fences(response.choices[0].message.content.strip())
        return code + "\n"
    except Exception:
        logging.debug("codegen analysis code generation failed", exc_info=True)
        return None


async def build_package(
    turns: list[dict],
    thread_id: str,
    model: str | None = None,
    extra_litellm_kwargs: dict | None = None,
) -> dict[str, str]:
    """Return {filename: content} dict ready to be zipped."""
    from config import MODEL
    chosen_model = model or MODEL
    kwargs = extra_litellm_kwargs or {}

    cleaned_turns = []
    for turn in turns:
        cleaned_calls = await _cleanup_turn_calls(turn, chosen_model, kwargs)
        cleaned = {**turn, "tool_calls": cleaned_calls}

        if _has_plot(cleaned_calls):
            generated = await _generate_analysis_code(cleaned, chosen_model, kwargs)
            if generated:
                cleaned["_generated_code"] = generated

        cleaned_turns.append(cleaned)

    used = {
        tc["name"]
        for turn in cleaned_turns
        for tc in turn.get("tool_calls", [])
        if "_generated_code" not in turn
    }
    return {
        "analyse.py": build_py(cleaned_turns),
        "analyse.ipynb": build_ipynb(cleaned_turns),
        "requirements.txt": build_requirements(used),
        "LEESMIJ.md": _LEESMIJ,
    }
