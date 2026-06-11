"""Pure template/render functions — no LLM calls, no I/O."""

from __future__ import annotations

import json
from datetime import date

from .prompts import LEESMIJ, PY_HEADER, SKIP_TOOLS  # noqa: F401 — re-exported for convenience


def is_upload_turn(tool_calls: list[dict]) -> bool:
    for tc in tool_calls:
        if tc.get("name") == "query_data":
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except Exception:
                continue
            if args.get("data_key", "").startswith("upload:"):
                return True
    return False


def has_plot(tool_calls: list[dict]) -> bool:
    return any(tc.get("name") == "create_plot" for tc in tool_calls)


def plot_config_only(plot_calls: list[dict]) -> list[dict]:
    """Return chart config dicts with the 'data' key stripped.

    Passing data values to the code-gen LLM causes it to hardcode those values
    instead of writing real pandas transformations.
    """
    configs = []
    for tc in plot_calls:
        try:
            args = json.loads(tc.get("arguments", "{}"))
        except Exception:
            args = {}
        configs.append({k: v for k, v in args.items() if k != "data"})
    return configs


def render_call(name: str, arguments: str) -> str:
    """Fallback renderer for a single tool call (used when LLM code-gen fails)."""
    try:
        args = json.loads(arguments)
    except Exception:
        args = {}

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


def to_source_lines(text: str) -> list[str]:
    """Split code into per-line strings as required by the nbformat spec."""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def turn_code_lines(turn: dict) -> list[str]:
    if "_generated_code" in turn:
        return to_source_lines(turn["_generated_code"])

    tool_calls = turn.get("tool_calls", [])
    lines = []
    for tc in tool_calls:
        name = tc.get("name", "")
        if name in SKIP_TOOLS:
            continue
        lines.extend(to_source_lines(render_call(name, tc.get("arguments", "{}"))))
    return lines


def build_py(turns: list[dict]) -> str:
    parts = [PY_HEADER.format(today=date.today())]
    for i, turn in enumerate(turns, 1):
        question = turn.get("question", "").replace("\n", " ")
        parts.append(f"# --- Vraag {i}: {question[:120]}\n")
        code_lines = turn_code_lines(turn)
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
            "source": to_source_lines(
                f"## Vraag {i}\n**Vraag:** {question}\n\n**Antwoord:**\n{answer[:1000]}\n"
            ),
        })

        code_lines = turn_code_lines(turn)
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
