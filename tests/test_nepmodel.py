"""Het nepmodel voor lokaal testen zonder providersleutel (#1065).

Met `MODEL=mock/<scenario>` geeft `acompletion_with_backoff` een vaste stroom in LiteLLM-vorm terug, zonder provider.
De toolloop, de echte catalogus en de controles draaien; alleen het laden van de vaste maat (CBS, netwerk) is hier
nagebootst.
"""

import asyncio
import importlib
import json

import litellm
import pandas as pd
import pytest

import tools
from agent import nepmodel, ratelimit, report
from agent.model_context import clamp_max_tokens, get_max_context
from agent.stream import accumulate_stream
from config import Config, ConfigError
from core import config as runtime
from tools import store
from tools.catalog import search_catalog
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")

NEP = "mock/default"
VRAAG = "Hoeveel mbo-studenten zijn er landelijk?"
_KEY = "cbs:85354NED:nep"


def _tools(*namen: str) -> list[dict]:
    return [{"type": "function", "function": {"name": n, "parameters": {}}} for n in namen]


async def _stil(_event):
    pass


def _lees(model: str, messages: list[dict], tools_: list[dict], tool_choice=None):
    async def lees():
        stroom = await ratelimit.acompletion_with_backoff(
            _stil, model=model, messages=messages, tools=tools_, stream=True, tool_choice=tool_choice
        )
        return await accumulate_stream(stroom)

    return asyncio.run(lees())


@pytest.fixture
def geen_provider(monkeypatch):
    """Elke echte modelaanroep faalt de test: het nepmodel mag LiteLLM nooit bereiken."""

    async def verboden(*args, **kwargs):
        raise AssertionError("litellm.acompletion aangeroepen in nepmodus")

    monkeypatch.setattr(litellm, "acompletion", verboden)


@pytest.fixture
def vaste_maat(monkeypatch):
    """get_maat zonder CBS: één tabel in de store en het resultaat in de vorm van tools/maten.py."""
    rijen = [
        {"Perioden": "2020SJ00", "Perioden_label": "2020/'21", "Periodestatus": "Definitief", "MboStudenten_1": 518940},
        {"Perioden": "2021SJ00", "Perioden_label": "2021/'22", "Periodestatus": "Definitief", "MboStudenten_1": 512100},
    ]

    monkeypatch.setattr(tools.cbs, "definitions", lambda *a, **k: {})

    def get_maat(maat, **_):
        assert maat == "mbo_studenten_landelijk"
        store.put(_KEY, pd.DataFrame(rijen), KeyMeta(bron="cbs", dataset="85354NED"))
        return json.dumps(
            {
                "data_key": _KEY,
                "maat": maat,
                "teldefinitie": "mbo-studenten landelijk",
                "sector": "mbo",
                "periodekolom": "Perioden",
                "waardekolom": "MboStudenten_1",
                "totaal_rijen": len(rijen),
                "rijen": rijen,
            }
        )

    monkeypatch.setitem(tools._HANDLERS, "get_maat", get_maat)


# ─── de stroom ────────────────────────────────────────────────────────────────


def test_de_stroom_is_een_toolaanroep_die_accumulate_stream_leest(geen_provider):
    sr = _lees(NEP, [{"role": "user", "content": VRAAG}], _tools("search_catalog", "get_maat"))

    assert sr.text == ""
    assert sr.finish_reason == "tool_calls"
    assert sr.model_versie == NEP
    assert [(tc["name"], json.loads(tc["arguments"])) for tc in sr.tool_calls] == [("search_catalog", {"query": VRAAG})]
    assert sr.tool_calls[0]["id"]
    assert sr.tokens.uitvoer > 0


def test_na_de_zoekactie_de_vaste_maat_en_daarna_het_antwoord():
    tools_ = _tools("search_catalog", "get_maat")
    zoek = {"role": "assistant", "content": "", "tool_calls": [_aanroep("z1", "search_catalog")]}
    treffer = json.dumps({"status": "candidates", "kandidaten": [{"dataset_id": "85354NED", "titel": "Mbo"}]})
    gesprek = [{"role": "user", "content": VRAAG}, zoek, {"role": "tool", "tool_call_id": "z1", "content": treffer}]

    assert nepmodel.keuze(NEP, gesprek, tools_) == {
        "tool": "get_maat",
        "argumenten": {"maat": "mbo_studenten_landelijk"},
    }

    maat = json.dumps(
        {
            "data_key": _KEY,
            "maat": "mbo_studenten_landelijk",
            "periodekolom": "Perioden",
            "waardekolom": "W",
            "rijen": [{"Perioden": "2021SJ00", "Perioden_label": "2021/'22", "W": 512100}],
        }
    )
    gesprek += [
        {"role": "assistant", "content": "", "tool_calls": [_aanroep("m1", "get_maat")]},
        {"role": "tool", "tool_call_id": "m1", "content": maat},
    ]
    tekst = nepmodel.keuze(NEP, gesprek, tools_)["tekst"]
    assert "85354NED" in tekst and "512100" in tekst and "2021/'22" in tekst

    sr = _lees(NEP, gesprek, tools_)
    assert sr.text == tekst and not sr.tool_calls and sr.finish_reason == "stop"


def _aanroep(id_: str, naam: str) -> dict:
    return {"id": id_, "type": "function", "function": {"name": naam, "arguments": "{}"}}


def test_zonder_tools_of_in_de_afrondronde_alleen_tekst():
    gesprek = [{"role": "user", "content": VRAAG}]
    assert "tekst" in nepmodel.keuze(NEP, gesprek, [])
    assert "tekst" in nepmodel.keuze(NEP, gesprek, _tools("search_catalog"), tool_choice="none")
    assert "tekst" in nepmodel.keuze("mock/tekst", gesprek, _tools("search_catalog", "get_maat"))


def test_een_herkansing_of_afrondvraag_hoort_bij_dezelfde_beurt():
    treffer = json.dumps({"status": "candidates", "kandidaten": [{"dataset_id": "85354NED"}]})
    beurt = [
        {"role": "user", "content": VRAAG},
        {"role": "assistant", "content": "", "tool_calls": [_aanroep("z1", "search_catalog")]},
        {"role": "tool", "tool_call_id": "z1", "content": treffer},
    ]
    tools_ = _tools("search_catalog")

    herkansing = [*beurt, {"role": "assistant", "content": "Antwoord."}, {"role": "user", "content": "Controle: …"}]
    afronden = [*beurt, {"role": "user", "content": "Rond af."}]

    assert "85354NED" in nepmodel.keuze(NEP, herkansing, tools_)["tekst"]
    assert "85354NED" in nepmodel.keuze(NEP, afronden, tools_, tool_choice="none")["tekst"]
    # Een nieuwe vraag na een antwoord zonder toolstappen in de historie is een nieuwe beurt: eerst weer zoeken.
    nieuw = [{"role": "user", "content": "Eerst"}, {"role": "assistant", "content": "Antwoord."}, *beurt[:1]]
    assert nepmodel.keuze(NEP, nieuw, tools_)["tool"] == "search_catalog"


def test_een_onbekende_tool_krijgt_een_antwoord_in_tekst():
    assert "tekst" in nepmodel.keuze(NEP, [{"role": "user", "content": VRAAG}], _tools("iets_anders"))


def test_de_rapportaanvraag_krijgt_het_json_blok_van_het_rapport():
    tekst = nepmodel.keuze(NEP, [{"role": "user", "content": "rapport"}], _tools("query_data", "compute_kpi"))["tekst"]
    spec = report._extract_json_object(tekst)
    assert spec["title"] and spec["conclusie"] and spec["beantwoordt"]


def test_een_echt_model_gaat_nog_naar_litellm(monkeypatch):
    gezien = []

    async def acompletion(**kwargs):
        gezien.append(kwargs["model"])
        return "ok"

    monkeypatch.setattr(litellm, "acompletion", acompletion)
    assert asyncio.run(ratelimit.acompletion_with_backoff(_stil, model="openai/gpt-4o", messages=[])) == "ok"
    assert gezien == ["openai/gpt-4o"]


# ─── een hele beurt en een rapport ───────────────────────────────────────────


@pytest.mark.usefixtures("zonder_scopekaart", "geen_provider", "vaste_maat")
def test_een_beurt_met_het_nepmodel_zoekt_laadt_en_antwoordt():
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    session: dict = {}
    antwoord = asyncio.run(
        run_module.run([{"role": "user", "content": VRAAG}], session, emit, asyncio.Event(), model=NEP)
    )

    soorten = [e["type"] for e in events]
    assert [e["name"] for e in events if e["type"] == "tool_start"] == ["search_catalog", "get_maat"]
    assert [e["name"] for e in events if e["type"] == "tool_end"] == ["search_catalog", "get_maat"]
    assert soorten.index("tool_end") < soorten.index("message_end")
    eerste = json.loads(search_catalog(VRAAG))["kandidaten"][0]["dataset_id"]
    slot = next(e for e in events if e["type"] == "message_end")
    assert nepmodel.KOP in slot["content"] and eerste in slot["content"]
    assert "512.100" in slot["content"] or "512100" in slot["content"]
    assert antwoord == slot["content"]
    assert _KEY in session["data_keys"]


@pytest.mark.usefixtures("geen_provider")
def test_scenario_verzonnen_wordt_ingetrokken_en_het_getal_komt_in_twee_stukken():
    """#1254: het getal van de eerste versie stroomt in twee stukken binnen ("27." en "135"), de controle trekt het
    antwoord in, en het slot noemt het niet. Elke message_start draagt de regel van de getalcontrole."""
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(
        run_module.run(
            [{"role": "user", "content": VRAAG}],
            {},
            emit,
            asyncio.Event(),
            model="mock/verzonnen",
        )
    )

    soorten = [e["type"] for e in events]
    stukken = [e["content"] for e in events if e["type"] == "text_delta"]
    assert any(s.endswith("27.") for s in stukken) and any(s.startswith("135") for s in stukken)
    assert "message_cancel" in soorten
    slot = next(e for e in events if e["type"] == "message_end")
    assert nepmodel.VERZONNEN not in slot["content"] and "27135" not in slot["content"]
    starts = [e for e in events if e["type"] == "message_start"]
    assert len(starts) >= 2 and all(e["getalregel"]["min_cijfers"] == 4 for e in starts)


@pytest.mark.usefixtures("geen_provider")
def test_het_rapport_van_het_nepmodel_komt_door_de_controles():
    store.put(
        _KEY,
        pd.DataFrame({"Perioden": ["2021SJ00"], "MboStudenten_1": [512100]}),
        KeyMeta(bron="cbs", dataset="85354NED"),
    )

    spec = asyncio.run(report.generate({"data_keys": [_KEY]}, _stil, model=NEP))

    assert "1 rijen" in spec.conclusie and spec.beantwoordt
    assert spec.manifest["model"] == NEP


# ─── de rest van de app kent het nepmodel ────────────────────────────────────


def test_geen_sleutel_nodig_en_een_vaste_context():
    assert runtime.get_required_api_key_env_var(NEP) is None
    assert runtime.llm_sleutel_aanwezig(NEP) is True
    assert get_max_context(NEP) > 4096
    assert clamp_max_tokens(NEP, 40960) == 40960


def test_de_kiezer_toont_de_nepscenarios_zonder_available_models(monkeypatch):
    monkeypatch.setattr(runtime, "MODEL", NEP)
    monkeypatch.setattr(runtime, "_AVAILABLE_MODELS_RAW", None)

    aanbod = runtime.get_available_models() or []

    assert [m[0] for m in aanbod] == ["mock/default", "mock/tekst", "mock/verzonnen"]
    assert all(m[1].startswith("Nepmodel") for m in aanbod)
    assert runtime.toegestaan_model(None, "mock/tekst") == "mock/tekst"


def test_zonder_nepmodel_blijft_de_kiezer_weg(monkeypatch):
    monkeypatch.setattr(runtime, "MODEL", "anthropic/claude-sonnet-4-6")
    monkeypatch.setattr(runtime, "_AVAILABLE_MODELS_RAW", None)
    assert runtime.get_available_models() is None


# ─── de startcontrole ────────────────────────────────────────────────────────


def _configuratie(monkeypatch, *, omgeving: str, model: str = "anthropic/claude-sonnet-4-6", aanbod=None, per=None):
    from core import auth

    monkeypatch.setattr(Config, "APP_ENV", omgeving)
    monkeypatch.setattr(Config, "MODEL", model)
    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(runtime, "MODEL", model)
    monkeypatch.setattr(runtime, "_AVAILABLE_MODELS_RAW", aanbod)
    monkeypatch.setattr(runtime, "_USER_MODELS", per or {})


@pytest.mark.parametrize("omgeving", ["local", "development"])
def test_het_nepmodel_start_lokaal_en_op_development(monkeypatch, omgeving):
    _configuratie(monkeypatch, omgeving=omgeving, model=NEP)
    Config.validate()


@pytest.mark.parametrize("omgeving", ["test", "playground", "production", "staging-otc", "production-otc"])
@pytest.mark.parametrize(
    "instelling",
    [
        {"model": NEP},
        {"aanbod": "anthropic/claude-sonnet-4-6,mock/default"},
        {"per": {"anna": ["mock/tekst"]}},
    ],
    ids=["MODEL", "AVAILABLE_MODELS", "USER_MODELS"],
)
def test_het_nepmodel_start_nergens_anders(monkeypatch, omgeving, instelling):
    _configuratie(monkeypatch, omgeving=omgeving, **instelling)

    with pytest.raises(ConfigError) as fout:
        Config.validate()

    melding = str(fout.value)
    assert "nepmodel" in melding and omgeving in melding and "local" in melding


def test_een_onbekend_scenario_start_niet(monkeypatch):
    _configuratie(monkeypatch, omgeving="local", model="mock/onbekend")

    with pytest.raises(ConfigError, match="mock/onbekend"):
        Config.validate()


def test_elk_scenario_heeft_een_naam_in_de_kiezer():
    assert {f"{runtime.NEP_PREFIX}{s}" for s in runtime.NEP_SCENARIOS} <= set(runtime._KNOWN_NAMES)
