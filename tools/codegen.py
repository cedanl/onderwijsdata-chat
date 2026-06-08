"""Generates a reproducible Python package from a chat session."""

from __future__ import annotations

import json
from datetime import date

# Only skip tools that produce no reproducible output
_SKIP_TOOLS = {"search_catalog", "suggest_followups"}

_LEESMIJ = """\
# Onderwijsdata analyse

Gegenereerde Python-bestanden voor het reproduceren van de analyse uit de chat.

## Vereisten

Python 3.11 of hoger. De map `tools/` uit de onderwijsdata-chat repository is vereist
naast deze bestanden — kopieer hem mee of kloon de repository:

```
git clone https://github.com/cedanl/onderwijsdata-chat.git
cd onderwijsdata-chat
```

Kopieer daarna `analyse.py`, `analyse.ipynb` en `requirements.txt` naar de root van de
repository en voer de stappen hieronder uit.

## Installeren

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

Vereist: de map tools/ uit de onderwijsdata-chat repository.
\"\"\"

from tools import (
    get_cbs_data,
    get_cbs_dimension,
    get_duo_data,
    query_data,
    get_rio_data,
    create_plot,
)
import json

"""


def _render_call(name: str, arguments: str) -> str:
    """Return a Python statement for a single tool call."""
    try:
        args = json.loads(arguments)
    except Exception:
        args = {}

    # Uploads cannot be reproduced — emit a placeholder comment
    data_key = args.get("data_key", "")
    if isinstance(data_key, str) and data_key.startswith("upload:"):
        return (
            f"# TODO: '{data_key}' is een geüpload bestand — laad het zelf:\n"
            f"# import pandas as pd; df = pd.read_csv('jouw_bestand.csv', dtype=str)\n"
            f"# from tools.store import put; put('{data_key}', df)\n"
        )

    kwargs = ", ".join(
        f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items()
    )
    return f"result = {name}({kwargs})\nprint(result)\n"


def _to_source_lines(text: str) -> list[str]:
    """Split a block of code into per-line strings as required by the nbformat spec."""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def _turn_code_lines(tool_calls: list[dict]) -> list[str]:
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
        tool_calls = turn.get("tool_calls", [])
        code_lines = _turn_code_lines(tool_calls)
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
            "# Zorg dat tools/ beschikbaar is (zie LEESMIJ.md)\n",
            "from tools import get_cbs_data, get_cbs_dimension, get_duo_data, query_data, get_rio_data, create_plot\n",
            "import json\n",
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

        tool_calls = turn.get("tool_calls", [])
        code_lines = _turn_code_lines(tool_calls)
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

    packages = ["riodata", "plotly"]
    if used_tool_names & {"get_cbs_data", "get_cbs_dimension"}:
        packages.append("cbsodata")
    if used_tool_names & {"get_duo_data", "query_data"}:
        packages.extend(["pandas", "openpyxl"])

    lines = ["# gegenereerd door onderwijsdata-chat\n"]
    for pkg in packages:
        try:
            version = importlib.metadata.version(pkg)
            lines.append(f"{pkg}=={version}\n")
        except importlib.metadata.PackageNotFoundError:
            lines.append(f"{pkg}\n")
    return "".join(lines)


def build_package(turns: list[dict], thread_id: str) -> dict[str, str | bytes]:
    """Return {filename: content} dict ready to be zipped."""
    used = {
        tc["name"]
        for turn in turns
        for tc in turn.get("tool_calls", [])
        if tc.get("name") not in _SKIP_TOOLS
    }
    return {
        "analyse.py": build_py(turns),
        "analyse.ipynb": build_ipynb(turns),
        "requirements.txt": build_requirements(used),
        "LEESMIJ.md": _LEESMIJ,
    }
