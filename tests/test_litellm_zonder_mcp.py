"""litellm mag `mcp` niet nodig hebben voor een gewone aanroep met tools.

Het runtime-image heeft `mcp` niet (extra `mcp`, alleen voor mcp_server.py). litellm 1.106.x importeerde hem toch zodra
een aanroep tools meegaf: elke chatvraag op test gaf "Kan de API niet bereiken" (APIConnectionError: No module named
'mcp'). De pytest-omgeving heeft `mcp` wel, dus de test blokkeert hem in een apart proces, zonder netwerk
(`mock_response`). Een litellm-bump die dit breekt, faalt hier in plaats van op test.
"""

import subprocess
import sys
import textwrap

_SCRIPT = textwrap.dedent(
    """
    import sys

    sys.modules["mcp"] = None  # een import van mcp geeft ImportError, ook als het pakket is geïnstalleerd

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
)


def test_een_aanroep_met_tools_werkt_zonder_het_mcp_pakket():
    proces = subprocess.run([sys.executable, "-I", "-c", _SCRIPT], capture_output=True, text=True, timeout=120)

    assert proces.returncode == 0, proces.stderr[-800:]
    assert proces.stdout.strip() == "ok"
