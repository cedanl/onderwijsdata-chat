"""Gesloten foutcodes en een tool die op slot gaat na twee keer dezelfde fout (#331).

UX-audit P1-1: gpt-oss kreeg vier keer dezelfde CBS-fout, probeerde `cbs_85353NED`
als data_key en liep na 22 toolaanroepen vast. Elke ruwe providertekst was een
nieuwe prompt; niets stopte een tool die steeds hetzelfde misging.
"""

import asyncio
import json
from unittest.mock import patch

import httpx
import pandas as pd
import pytest

from agent import loop as loop_module
from agent.stream import StreamResult
from tools import dispatch, fouten, store
from tools.cbs import get_cbs_data, get_cbs_dimension
from tools.duo import get_duo_data
from tools.kpi import compute_kpi
from tools.query import query_data
from tools.rio import get_rio_data
from tools.store import KeyMeta

_GEHEIM = "upstream says: secret-host.internal:8443 stacktrace"


def _http(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://bron.example/x")
    return httpx.HTTPStatusError(_GEHEIM, request=request, response=httpx.Response(status, request=request))


# ── Foutcodes ────────────────────────────────────────────────────────────────


def test_code_leest_de_melding_en_de_kpi_fout():
    assert fouten.code(fouten.melding(fouten.Fout.BRON_WEIGERT, "x")) == "bron_weigert"
    assert fouten.code(json.dumps({"fout": fouten.melding(fouten.Fout.ONBEKENDE_DATA_KEY, "x")})) == (
        "onbekende_data_key"
    )
    assert fouten.code('{"rijen": []}') is None
    assert fouten.code("Geen rijen gevonden") is None


@pytest.mark.parametrize(
    ("fout", "code"),
    [
        (_http(400), "bron_weigert"),
        (_http(503), "bron_onbereikbaar"),
        (httpx.ConnectTimeout(_GEHEIM), "bron_onbereikbaar"),
    ],
)
def test_cbs_geeft_een_code_en_geen_ruwe_providertekst(fout, code):
    with patch("tools.cbs.data", side_effect=fout):
        result = get_cbs_data("85423NED")
    assert fouten.code(result) == code
    assert "secret-host" not in result


def test_cbs_dimensie_geeft_een_code_en_geen_ruwe_providertekst():
    with patch("tools.cbs.get", side_effect=_http(404)), patch("tools.cbs.definitions", return_value={}):
        result = get_cbs_dimension("85423NED", "Status")
    assert fouten.code(result) == "bron_weigert"
    assert "secret-host" not in result


def test_rio_geeft_een_code_en_geen_ruwe_providertekst():
    with patch("tools.rio.fetch", side_effect=httpx.ReadTimeout(_GEHEIM)):
        result = get_rio_data("erkenningen")
    assert fouten.code(result) == "bron_onbereikbaar"
    assert "secret-host" not in result


def test_duo_geeft_een_code_en_geen_ruwe_providertekst():
    with (
        patch("tools.duo._duo.load", side_effect=RuntimeError(_GEHEIM)),
        patch("tools.duo._duo.catalog", return_value=[]),
        patch("tools.duo._resource_index", return_value=0),
    ):
        result = get_duo_data("p01hoinges")
    assert fouten.code(result) == "bron_fout"
    assert "secret-host" not in result


def test_exception_in_een_tool_geeft_een_code_zonder_ruwe_tekst():
    with patch.dict("tools._HANDLERS", {"query_data": lambda **_: (_ for _ in ()).throw(KeyError(_GEHEIM))}):
        result, _ = dispatch("query_data", {})
    assert fouten.code(result) == "toolfout"
    assert "secret-host" not in result


def test_onbekende_data_key_heeft_een_code():
    assert fouten.code(query_data("cbs:bestaat_niet")) == "onbekende_data_key"
    assert fouten.code(compute_kpi("cbs:bestaat_niet", "N", "last")) == "onbekende_data_key"


# ── data_key-varianten bij de ingang ─────────────────────────────────────────


@pytest.mark.parametrize("variant", ["cbs_85353NED", "cbs/85353NED", "CBS:85353ned", "cbs:85353NED"])
def test_data_key_variant_wordt_de_canonieke_key(variant):
    store.put("cbs:85353NED", pd.DataFrame({"N": [1, 2]}), KeyMeta(bron="cbs", dataset="85353NED"))
    result, _ = dispatch("query_data", {"data_key": variant})
    assert json.loads(result)["data_key"] == "cbs:85353NED"


def test_onbekende_variant_blijft_onbekend():
    result, _ = dispatch("query_data", {"data_key": "cbs_99999NED"})
    assert fouten.code(result) == "onbekende_data_key"


# ── Op slot in de toolloop ───────────────────────────────────────────────────


def _call(name: str, arguments: str, call_id: str) -> dict:
    return {"id": call_id, "name": name, "arguments": arguments}


def _loop(monkeypatch, steps: list[StreamResult], results: dict[str, str]):
    executed: list[str] = []

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute(call, emit):
        executed.append(call.arguments)
        return results[call.name], None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    messages = [{"role": "user", "content": "vraag"}]

    async def emit(event):
        pass

    asyncio.run(
        loop_module.tool_loop(
            messages, model="openai/gpt-4o", tools=[], emit=emit, max_iterations=6, max_result_chars=2000
        )
    )
    return executed, [m["content"] for m in messages if m["role"] == "tool"]


def _cbs_stappen(n: int) -> list[StreamResult]:
    return [
        *(
            StreamResult(text="", tool_calls=[_call("get_cbs_data", json.dumps({"filters": {"i": i}}), f"t{i}")])
            for i in range(n)
        ),
        StreamResult(text="Klaar.", tool_calls=[]),
    ]


def test_tweede_keer_dezelfde_fout_zet_de_tool_op_slot(monkeypatch):
    fout = fouten.melding(fouten.Fout.BRON_WEIGERT, "CBS weigerde de aanvraag (HTTP 400).")
    executed, antwoorden = _loop(monkeypatch, _cbs_stappen(3), {"get_cbs_data": fout})

    assert len(executed) == 2
    assert "OP SLOT" in antwoorden[2] and "bron_weigert" in antwoorden[2]
    assert "get_cbs_dimension" in antwoorden[2]


def test_eenmaal_dezelfde_fout_is_nog_geen_slot(monkeypatch):
    fout = fouten.melding(fouten.Fout.BRON_WEIGERT, "CBS weigerde de aanvraag (HTTP 400).")
    executed, _ = _loop(monkeypatch, _cbs_stappen(1), {"get_cbs_data": fout})
    assert len(executed) == 1


def test_resultaat_zonder_code_zet_niets_op_slot(monkeypatch):
    executed, antwoorden = _loop(monkeypatch, _cbs_stappen(3), {"get_cbs_data": '{"data_key": "cbs:x"}'})
    assert len(executed) == 3
    assert not any("OP SLOT" in a for a in antwoorden)


def test_slot_geldt_alleen_voor_die_tool(monkeypatch):
    fout = fouten.melding(fouten.Fout.BRON_WEIGERT, "CBS weigerde de aanvraag (HTTP 400).")
    steps = [
        *_cbs_stappen(2)[:-1],
        StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": "x"}', "s1")]),
        StreamResult(text="Klaar.", tool_calls=[]),
    ]
    executed, antwoorden = _loop(monkeypatch, steps, {"get_cbs_data": fout, "search_catalog": "[]"})
    assert executed[-1] == '{"q": "x"}'
    assert antwoorden[-1] == "[]"
