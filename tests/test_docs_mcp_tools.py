"""docs/mcp.md noemt elke tool die de MCP-server aanbiedt (audit 26-11-2026): een nieuwe tool komt niet ongedocumenteerd."""

from pathlib import Path

import pytest

from mcp_server import MCP_TOOLS

MCP_MD = (Path(__file__).resolve().parent.parent / "docs" / "mcp.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("naam", MCP_TOOLS)
def test_elke_mcp_tool_staat_in_de_mcp_pagina(naam):
    assert f"`{naam}`" in MCP_MD, f"niet in docs/mcp.md: {naam}"
