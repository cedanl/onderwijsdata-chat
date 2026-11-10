"""create_plot tekent een sankey voor doorstroomvragen, uit code (#995).

Op "kan je een sankey visualisatie hiervan maken?" (demo, test, 10-11; doorstroom mbo-Verpleegkundige → hbo) schreef het
model zelf Plotly-code in run_analysis: tekenen, kleuren en labels lagen bij het model, en het rapport kon de figuur
niet maken. Nu kiest het model chart_type "sankey" met source, target en value.
"""

import asyncio
import importlib
import json
from typing import Any

import pandas as pd
import plotly.io as pio
import pytest

from agent.figuurverwijzing import figuursoorten
from agent.grafiekvraag import gevraagde_typen, ontbrekende_grafiek
from agent.report_checks import report_problems
from agent.stream import StreamResult
from tools import dispatch, store
from tools.kolomlabel import kolomlabel
from tools.plot import _MAX_SANKEYKNOPEN, GEEN_ASSEN, TE_VEEL_KNOPEN, create_plot
from tools.schemas import TOOL_CREATE_PLOT, TOOL_RUN_ANALYSIS, TOOL_SCHEMAS

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_KEY = "skdb:doorstroom_mbo_hbo:verpleeg"
# De vaste casus: mbo-Verpleegkundige naar 13 hbo-opleidingen, samen 695 doorstromers.
_DOELEN = {
    "Opleiding tot Verpleegkundige": 412,
    "Social Work": 98,
    "Pedagogiek": 41,
    "Opleiding tot Verloskundige": 33,
    "Toegepaste Psychologie": 27,
    "Opleiding tot Fysiotherapeut": 22,
    "Management in de Zorg": 18,
    "Medische Hulpverlening": 13,
    "Opleiding tot Leraar Basisonderwijs": 11,
    "Sportkunde": 8,
    "Voeding en Diëtetiek": 6,
    "Huidtherapie": 4,
    "Ergotherapie": 2,
}
_RIJEN = [
    {
        "mbo_opleiding": "Mbo-Verpleegkundige",
        "hbo_studie": doel,
        "graad": "Associate degree" if doel == "Management in de Zorg" else "Bachelor",
        "doorstromers": aantal,
    }
    # Omgekeerd: de volgorde van de knopen komt uit de grootte, niet uit de rijen.
    for doel, aantal in reversed(_DOELEN.items())
]
_SANKEY: dict[str, Any] = {
    "chart_type": "sankey",
    "data_key": _KEY,
    "source": "mbo_opleiding",
    "target": "hbo_studie",
    "value": "doorstromers",
    "title": "Doorstroom mbo-Verpleegkundige naar het hbo",
}


@pytest.fixture(autouse=True)
def doorstroom():
    store.clear()
    store.put(_KEY, pd.DataFrame(_RIJEN))
    yield
    store.clear()


def _sankey(**args):
    return create_plot(**{**_SANKEY, **args})


def test_de_vaste_casus_geeft_14_knopen_13_stromen_en_695_doorstromers():
    uitkomst, fig = _sankey()

    assert fig is not None
    [trace] = fig.data
    assert trace.type == "sankey"
    assert len(trace.node.label) == 14
    assert len(trace.link.value) == 13
    assert sum(trace.link.value) == 695
    assert (
        uitkomst == "Sankey-diagram 'Doorstroom mbo-Verpleegkundige naar het hbo' aangemaakt (14 knopen, 13 stromen)."
    )


def test_knopen_staan_op_grootte_eerst_de_herkomst_dan_de_bestemmingen():
    _, fig = _sankey()

    assert list(fig.data[0].node.label) == ["Mbo-Verpleegkundige", *_DOELEN]
    # Elke stroom gaat van de herkomst (0) naar haar eigen bestemming.
    assert set(fig.data[0].link.source) == {0}
    assert sorted(fig.data[0].link.target) == list(range(1, 14))


def test_een_stroom_met_0_of_leeg_valt_weg_en_het_toolbericht_zegt_hoeveel():
    extra = [
        {"mbo_opleiding": "Mbo-Verpleegkundige", "hbo_studie": "Logopedie", "doorstromers": 0},
        {"mbo_opleiding": "Mbo-Verpleegkundige", "hbo_studie": "Oefentherapie", "doorstromers": None},
    ]
    store.put(_KEY, pd.DataFrame([*_RIJEN, *extra]))

    uitkomst, fig = _sankey()

    assert fig is not None
    assert len(fig.data[0].link.value) == 13
    assert "Logopedie" not in fig.data[0].node.label
    assert "2 rij(en) niet getekend (aantal 0 of leeg" in uitkomst
    # De export houdt alle rijen.
    assert len(fig.layout.meta["data"]) == 15


def test_meer_dan_40_knopen_geeft_geen_figuur_maar_een_vraag_om_te_filteren():
    rijen = [{"mbo_opleiding": f"Mbo {i}", "hbo_studie": f"Hbo {i}", "doorstromers": 10 + i} for i in range(21)]
    store.put(_KEY, pd.DataFrame(rijen))

    uitkomst, fig = _sankey()

    assert fig is None
    assert uitkomst == TE_VEEL_KNOPEN.format(knopen=42, grens=_MAX_SANKEYKNOPEN)
    assert "Filter" in uitkomst and "groepeer" in uitkomst


def test_precies_40_knopen_wordt_getekend():
    rijen = [{"mbo_opleiding": f"Mbo {i}", "hbo_studie": f"Hbo {i}", "doorstromers": 10 + i} for i in range(20)]
    store.put(_KEY, pd.DataFrame(rijen))

    assert _sankey()[1] is not None


def test_de_hover_toont_het_aantal_en_het_aandeel_van_de_herkomst():
    _, fig = _sankey()
    link = fig.data[0].link
    maat = kolomlabel("doorstromers")
    grootste = link.customdata[list(link.value).index(412)]

    assert grootste.startswith("Mbo-Verpleegkundige → Opleiding tot Verpleegkundige")
    assert f"{maat}: 412" in grootste
    assert "59,3 % van de getoonde stromen uit Mbo-Verpleegkundige" in grootste
    assert link.hovertemplate == "%{customdata}<extra></extra>"
    assert fig.data[0].node.customdata[0] == f"Mbo-Verpleegkundige<br>{maat}: 695"


def test_een_herkomst_met_een_stroom_krijgt_geen_aandeel_van_100_procent():
    rijen = [
        {"mbo_opleiding": "Mbo A", "hbo_studie": "Hbo A", "doorstromers": 1200},
        {"mbo_opleiding": "Mbo B", "hbo_studie": "Hbo A", "doorstromers": 30},
    ]
    store.put(_KEY, pd.DataFrame(rijen))

    _, fig = _sankey()

    assert all("%" not in tekst for tekst in fig.data[0].link.customdata)
    assert "Hbo A<br>" in fig.data[0].node.customdata[2] and "1.230" in fig.data[0].node.customdata[2]


def test_kleur_en_letter_komen_uit_het_thema_zonder_zwart():
    _, fig = _sankey(title="Doorstroom perprovincie")
    trace = fig.data[0]

    assert fig.layout.title.text == "Doorstroom per provincie"
    assert fig.layout.font.family.startswith("Inter")
    assert fig.layout.font.color is None  # het thema van de chat en het rapport zet de letterkleur (#567)
    assert trace.textfont.color is None
    kleuren = [*trace.node.color, *trace.link.color]
    assert not any("#000000" in k or "rgba(0,0,0" in k for k in kleuren)
    assert all(k.startswith("rgba(") for k in trace.link.color)


def test_meta_draagt_rijen_dataset_herkomst_en_afrondingsnoot():
    store.put("cbs:85423NED:1", pd.DataFrame(_RIJEN), store.KeyMeta(bron="cbs", dataset="85423NED", afronding=10))

    _, fig = _sankey(data_key="cbs:85423NED:1")
    meta = fig.layout.meta

    assert meta["data"] == _RIJEN
    assert (meta["x"], meta["y"], meta["chart_type"]) == ("mbo_opleiding", "doorstromers", "sankey")
    assert meta["dataset"] == "85423NED"
    assert isinstance(meta["herkomst"], list) and meta["herkomst"]
    assert "afrondingsnoot" in meta


def test_kleur_per_groep_kleurt_de_stromen_en_noemt_de_kleuren():
    uitkomst, fig = _sankey(color="graad")
    link = fig.data[0].link

    assert len(set(link.color)) == 2
    assert set(fig.data[0].node.color) == {"#B0B0B0"}
    assert "Stromen gekleurd naar" in uitkomst and "Bachelor blauw" in uitkomst
    assert any("Associate degree" in tekst for tekst in link.customdata)


def test_een_sankey_zonder_source_target_of_value_zegt_wat_ontbreekt():
    uitkomst, fig = _sankey(source=None, value="")

    assert fig is None
    assert uitkomst.startswith("Een sankey heeft source, value nodig")


def test_een_onbekende_kolom_voor_de_sankey_noemt_de_beschikbare():
    uitkomst, fig = _sankey(target="bestemming")

    assert fig is None and "['bestemming'] niet gevonden" in uitkomst


@pytest.mark.parametrize("ontbreekt", ["x", "y"])
def test_andere_typen_zonder_x_of_y_krijgen_een_duidelijke_melding(ontbreekt):
    args: dict[str, Any] = {"data_key": _KEY, "chart_type": "bar", "x": "hbo_studie", "y": "doorstromers", "title": "t"}
    del args[ontbreekt]

    assert create_plot(**args) == (GEEN_ASSEN, None)


def test_het_schema_kent_sankey_en_vraagt_geen_x_en_y_meer():
    [schema] = [s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_CREATE_PLOT]
    params = schema["function"]["parameters"]

    assert "sankey" in params["properties"]["chart_type"]["enum"]
    assert {"source", "target", "value", "color"} <= set(params["properties"])
    assert params["required"] == ["data_key", "chart_type", "title"]


def test_de_sankey_via_dispatch_met_de_schemanamen():
    uitkomst, fig = dispatch(TOOL_CREATE_PLOT, dict(_SANKEY))

    assert fig is not None and uitkomst.startswith("Sankey-diagram")


# ── Grafiekvraag: "maak een sankey" toetst op een sankey (#221, #995) ──


@pytest.mark.parametrize(
    "vraag",
    ["maak een sankey van de doorstroom", "Kan je een sankey visualisatie hiervan maken?", "Toon een stroomdiagram"],
)
def test_een_sankeyvraag_is_een_sankey_en_niet_auto(vraag):
    assert gevraagde_typen(vraag) == {"sankey"}


def test_een_staafgrafiek_op_een_sankeyvraag_is_het_verkeerde_type():
    staaf = "Staafgrafiek 'Doorstroom' aangemaakt (13 datapunten)."
    sankey = "Sankey-diagram 'Doorstroom' aangemaakt (14 knopen, 13 stromen)."

    [probleem] = ontbrekende_grafiek("maak een sankey", "Hier is hij.", [staaf])

    assert "sankey-diagram" in probleem and "chart_type 'sankey'" in probleem
    assert ontbrekende_grafiek("maak een sankey", "Hier is hij.", [sankey]) == []


# ── Het rapport tekent en keurt een sankey uit create_plot (#995, #994) ──


def test_een_rapport_met_een_sankey_uit_create_plot_komt_door_de_controle(monkeypatch):
    from tests.test_report_checks import _rapportrun

    plot = {"id": "p1", "name": TOOL_CREATE_PLOT, "arguments": json.dumps(_SANKEY)}
    tekst = json.dumps(
        {
            "onderzoeksvraag": "Waar gaan mbo-verpleegkundigen naartoe in het hbo?",
            "beantwoordt": ["Doorstroom van mbo-Verpleegkundige naar hbo-opleidingen"],
            "visualisaties": [
                {
                    "titel": "Doorstroom mbo-Verpleegkundige naar het hbo",
                    "toelichting": "Het sankey-diagram toont dat de grootste stroom, 412 doorstromers, naar de "
                    "Opleiding tot Verpleegkundige gaat.",
                }
            ],
            "conclusie": "De meeste doorstromers (412) kiezen de Opleiding tot Verpleegkundige; daarna Social Work (98).",
        }
    )
    rijen = json.dumps({"rijen": _RIJEN})

    def met_echte_plot(name, args):
        return dispatch(name, args) if name == TOOL_CREATE_PLOT else (rijen, None)

    query = {"id": "q1", "name": "query_data", "arguments": json.dumps({"data_key": _KEY})}
    stappen = [StreamResult(text="", tool_calls=[query, plot]), StreamResult(text=tekst, tool_calls=[])]

    spec = _rapportrun(monkeypatch, stappen, dispatch=met_echte_plot)

    [visualisatie] = spec.visualisaties
    figuur = visualisatie["figure_json"]
    assert json.loads(figuur)["data"][0]["type"] == "sankey"
    assert figuursoorten([figuur]) == {"sankey"}
    assert report_problems(spec, [figuur], [rijen]) == []


# ── De chat: "maak een sankey" → create_plot met chart_type sankey, geen run_analysis (#995) ──


def test_maak_een_sankey_in_de_chat_tekent_met_create_plot(monkeypatch):
    stappen = [
        StreamResult(text="", tool_calls=[{"id": "p1", "name": TOOL_CREATE_PLOT, "arguments": json.dumps(_SANKEY)}]),
        StreamResult(text="Hierboven staat de doorstroom als sankey-diagram.", tool_calls=[]),
    ]
    aanroepen: list[str] = []

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    def volg_dispatch(name, args):
        aanroepen.append(name)
        return dispatch(name, args)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "dispatch", volg_dispatch)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    messages = [{"role": "user", "content": "maak een sankey van de doorstroom van mbo-Verpleegkundige naar het hbo"}]
    session: dict = {"data_keys": [_KEY]}
    asyncio.run(run_module.run(messages, session, emit, asyncio.Event(), model="openai/gpt-4o"))

    assert aanroepen == [TOOL_CREATE_PLOT]
    assert TOOL_RUN_ANALYSIS not in aanroepen
    [figuur] = [e for e in events if e["type"] == "figure"]
    assert pio.from_json(figuur["figure_json"]).data[0].type == "sankey"
    einde = next(e for e in reversed(events) if e["type"] == "message_end")
    assert "sankey-diagram" in einde["content"]
    assert not stappen  # geen herkansing: de controle vond de gevraagde sankey
