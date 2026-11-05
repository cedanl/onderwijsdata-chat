"""litellm en `mcp` in het runtime-image (#938).

litellm importeert `mcp` zodra een aanroep tools meegeeft (sinds 1.106; `responses/mcp` in `main.completion`). Tot #938
zat `mcp` niet in het image en hield de cap `litellm<1.106` dat tegen: zonder `mcp` gaf elke chatvraag "Kan de API niet
bereiken" (APIConnectionError: No module named 'mcp'). Nu is `mcp` een gewone dependency (ook voor `/mcp` in de app,
#706), en bewaken deze tests wat er nog toe doet:

- `mcp` staat in de gewone dependencies, niet in een extra: het image installeert alleen `--extra postgres`.
- een aanroep met tools werkt in een vers proces, zonder netwerk (`mock_response`, lokale kostentabel).
- de tools van de chat sturen litellm nooit naar zijn MCP-gateway (`acompletion_with_mcp`): die zou zelf MCP-servers
  aanroepen. Gemeten op 1.108.0: het mcp-pad laadt bij de eerste aanroep met tools ±108 `mcp`-modules (eenmalig ±0,6 s,
  ±10 MB), zonder threads, bestanden, netwerk of omgevingsvariabelen.
"""

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from tools import SCHEMAS

_ROOT = Path(__file__).resolve().parent.parent

_SCRIPT = """
import litellm

tools = [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}}]
r = litellm.completion(
    model="azure_ai/claude-sonnet-5-5",
    messages=[{"role": "user", "content": "zeg ok"}],
    tools=tools,
    mock_response="ok",
    api_key="nep",
    api_base="https://nep.invalid",
)
print(r.choices[0].message.content)
"""


def _pyproject() -> dict:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_mcp_is_een_gewone_dependency_en_geen_extra():
    project = _pyproject()

    namen = [re.split(r"[\[<>=!~ ;]", d, maxsplit=1)[0] for d in project["dependencies"]]
    assert "mcp" in namen
    assert "mcp" not in project.get("optional-dependencies", {})


def test_een_aanroep_met_tools_werkt_in_een_vers_proces():
    # De kostentabel lokaal: anders haalt `import litellm` hem van GitHub, en de netwerkblokkade van de suite geldt
    # niet in een subproces.
    env = {**os.environ, "LITELLM_LOCAL_MODEL_COST_MAP": "True"}

    proces = subprocess.run(
        [sys.executable, "-I", "-c", _SCRIPT], capture_output=True, text=True, timeout=120, env=env, check=False
    )

    assert proces.returncode == 0, proces.stderr[-800:]
    assert proces.stdout.strip() == "ok"


def test_de_tools_van_de_chat_gaan_niet_via_de_mcp_gateway_van_litellm():
    from litellm.responses.mcp.litellm_proxy_mcp_handler import LiteLLM_Proxy_MCP_Handler

    assert SCHEMAS
    assert all(t["type"] == "function" for t in SCHEMAS)
    assert not LiteLLM_Proxy_MCP_Handler.should_use_litellm_mcp_gateway(tools=SCHEMAS)
