"""De prompts vragen niets wat create_plot niet kan (#827).

`create_plot` heeft geen parameter voor de oriëntatie van staven: de code kiest liggende staven zelf bij veel of
lange namen (`tools/plot.py`, `_liggend`). Een prompt die om een horizontale staafgrafiek vraagt, geeft het model
een instructie die het niet kan uitvoeren, met een andere grens dan de code.
"""

from pathlib import Path

import pytest

from tools.schemas import TOOL_CREATE_PLOT, TOOL_SCHEMAS

_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def test_create_plot_heeft_geen_orientatieparameter():
    [schema] = [s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_CREATE_PLOT]
    assert not {"orientation", "orientatie", "horizontaal", "liggend"} & set(
        schema["function"]["parameters"]["properties"]
    )


@pytest.mark.parametrize("prompt", ["system.md", "report.md"])
def test_geen_prompt_vraagt_om_een_horizontale_staafgrafiek(prompt):
    assert "horizontale staaf" not in (_PROMPTS / prompt).read_text(encoding="utf-8").lower()
