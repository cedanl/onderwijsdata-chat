"""#546: welke toolstap het geheugen opjaagt staat in het log, zodat een OOMKill op test te herleiden is."""

import asyncio
import json
import logging
from pathlib import Path

import pytest

from agent import loop as loop_module
from core.geheugen import rss_mb
from tools import store


@pytest.mark.skipif(not Path("/proc/self/statm").exists(), reason="alleen met /proc")
def test_rss_is_een_positief_aantal_mib():
    rss = rss_mb()
    assert rss is not None and rss > 0


def test_zonder_proc_geen_fout_maar_none(monkeypatch, tmp_path):
    from core import geheugen

    monkeypatch.setattr(geheugen, "_STATM", tmp_path / "bestaat-niet")
    assert rss_mb() is None


def test_elke_toolstap_logt_rss_en_de_omvang_van_de_store(monkeypatch, caplog):
    """Alleen getallen en de toolnaam: geen argumenten of resultaat op INFO (#475)."""
    store.clear()
    result = json.dumps({"data_key": "duo:x:0:ab12", "rijen": [{"N": 1}]})
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (result, None))

    async def emit(_ev):
        pass

    args = {"data_key": "duo:x:0", "filters": {"INSTELLINGSNAAM": "Hogeschool Utrecht"}}
    call = loop_module.ToolCall(id="t1", name="query_data", arguments=json.dumps(args), args=args)
    with caplog.at_level(logging.INFO, logger="agent.loop"):
        asyncio.run(loop_module._execute_tool(call, emit))

    regel = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("GEHEUGEN"))
    assert "tool=query_data" in regel
    assert "rss_mb=" in regel and "store_mb=0.0" in regel and "store_keys=0" in regel
    assert "Hogeschool Utrecht" not in regel
