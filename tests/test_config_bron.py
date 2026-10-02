"""Eén bron per instelling: geen tweede default die stil afwijkt (#234)."""

import asyncio
import re
from pathlib import Path

import core.config
from config import Config
from routes.config import get_config

_ROOT = Path(__file__).parent.parent
_PRODUCTIECODE = [
    p for d in ("agent", "auth", "core", "data", "persistence", "routes", "tools") for p in (_ROOT / d).rglob("*.py")
]
_PRODUCTIECODE += [_ROOT / "config.py", _ROOT / "server.py", _ROOT / "health.py"]


def test_server_en_agent_gebruiken_hetzelfde_model():
    # config.py had "willma/default", core/config.py "anthropic/claude-sonnet-4-6".
    assert Config.MODEL == core.config.MODEL


def test_frontendconfig_volgt_de_dashboardvlag():
    assert asyncio.run(get_config())["dashboards_enabled"] is core.config.DASHBOARDS_ENABLED


def test_model_en_dashboardvlag_worden_op_een_plek_gelezen():
    for naam in ("MODEL", "ENABLE_DASHBOARDS"):
        lezers = [
            p.relative_to(_ROOT).as_posix()
            for p in _PRODUCTIECODE
            if re.search(rf"os\.(?:getenv|environ\.get)\(\s*[\"']{naam}[\"']", p.read_text())
        ]
        assert lezers == ["core/config.py"], f"{naam} gelezen in {lezers}"
