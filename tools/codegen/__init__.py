from __future__ import annotations

from .llm import cleanup_turn_calls, generate_analysis_code
from .templates import build_ipynb, build_py, build_requirements, has_plot
from .prompts import LEESMIJ


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
        cleaned_calls = await cleanup_turn_calls(turn, chosen_model, kwargs)
        cleaned = {**turn, "tool_calls": cleaned_calls}

        if has_plot(cleaned_calls):
            generated = await generate_analysis_code(cleaned, chosen_model, kwargs)
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
        "LEESMIJ.md": LEESMIJ,
    }
