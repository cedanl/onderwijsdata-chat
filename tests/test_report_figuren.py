"""De figuren uit het gesprek in het rapport (#993): gekozen in de checklist, opnieuw gemaakt op de server.

Vaste casus (10-11): beurt 1 haalde de doorstroom van mbo-verpleegkundigen naar het hbo op, beurt 2 vroeg om een
sankey. Het model bouwde die in `run_analysis`; het rapport gaf een staafgrafiek. Nu komt dezelfde sankey in het
rapport, opnieuw gemaakt uit het script en de data, met de bronregel eronder. Het rapportmodel tekent zelf geen
figuren (besluit 18-11): zonder keuze heeft het rapport er geen.
"""

import asyncio
import json

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pytest

from agent import figuurstappen, report, report_figuren
from agent.loop import LoopResult, ToolCall
from agent.probleem import harde
from agent.rapportselectie import MAX_FIGUREN, kies
from agent.report_figuren import NIET_OPNIEUW, beschrijf, maak_figuren
from core.config import MAX_REQUEST_BYTES
from tests.rapportfiguren import figuur_in_gesprek
from tools import dispatch, store
from tools.schemas import TOOL_COMPUTE_KPI, TOOL_CREATE_PLOT, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS
from tools.store import KeyMeta

_KEY = "duo:p01hoinges:0:sankey993"
_HBO = [
    "Verpleegkunde",
    "Social Work",
    "Pedagogiek",
    "Fysiotherapie",
    "Mondzorgkunde",
    "Toegepaste Psychologie",
    "Verloskunde",
    "Ergotherapie",
    "Logopedie",
    "Huidtherapie",
    "Voeding en Dietetiek",
    "Medische Hulpverlening",
    "Oefentherapie",
]
_AANTALLEN = [1840 - 120 * i for i in range(len(_HBO))]

# Het script zoals het model het in de chat schreef: een sankey, die create_plot toen niet kende.
_SANKEY = {
    "data_key": _KEY,
    "code": """bronnen = list(df['MBO'].unique())
doelen = list(df['HBO'].unique())
figure = go.Figure(go.Sankey(
    node=dict(label=bronnen + doelen),
    link=dict(
        source=[bronnen.index(m) for m in df['MBO']],
        target=[len(bronnen) + doelen.index(h) for h in df['HBO']],
        value=df['AANTAL'].tolist(),
    ),
))
figure.update_layout(title='Doorstroom mbo-verpleegkundigen naar hbo')
result = {'stromen': len(df), 'totaal': int(df['AANTAL'].sum())}
""",
}
# Een staafgrafiek met wat de gebruiker liet aanpassen: alleen lijnen in plaats van staven, één opleiding uitgelicht.
_STAAF = {
    "data_key": _KEY,
    "chart_type": "line",
    "x": "HBO",
    "y": "AANTAL",
    "title": "Doorstroom per hbo-opleiding",
    "highlight": "Verloskunde",
}

_ANTWOORD = {
    "onderzoeksvraag": "Naar welke hbo-opleidingen stromen mbo-verpleegkundigen door?",
    "beantwoordt": ["De doorstroom van mbo-verpleegkundigen naar hbo-opleidingen"],
    "beantwoordt_niet": ["De oorzaken van de keuzes"],
    "visualisaties": [{"titel": "Van mbo-verpleegkundige naar hbo", "toelichting": "Verpleegkunde trekt de meesten."}],
    "conclusie": "De meeste mbo-verpleegkundigen, 1840, stromen door naar de hbo-opleiding Verpleegkunde.",
}


@pytest.fixture
def sessie():
    store.put(
        _KEY,
        pd.DataFrame({"MBO": ["Verpleegkundige"] * len(_HBO), "HBO": _HBO, "AANTAL": _AANTALLEN}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=0, schooljaren=(2023,)),
    )
    return {
        "messages": [
            {"role": "user", "content": "Naar welke hbo-opleidingen stromen mbo-verpleegkundigen door?"},
            {"role": "assistant", "content": "Zie de tabel."},
            {"role": "user", "content": "kan je een sankey visualisatie hiervan maken?"},
            {"role": "assistant", "content": "Zie de sankey."},
        ],
        "data_keys": [_KEY],
        "data_vraag": {_KEY: 1},
        "data_provenance": {_KEY: {"name": "get_duo_data", "arguments": {"dataset_id": "p01hoinges"}}},
    }


async def _stil(_event):
    pass


def _rapport(sessie, monkeypatch, figuren=(), antwoord=None, model_stappen=()):
    """Het rapport met een nepmodel. Geeft (spec of RapportGeweigerd, wat de lus zag)."""
    gezien: dict = {}
    tekst = json.dumps(antwoord or _ANTWOORD)

    async def lus(messages, *, tools, check, on_tool_result, **_):
        gezien["prompt"] = messages[0]["content"]
        gezien["tools"] = [t["function"]["name"] for t in tools]
        for call, resultaat, figuur in model_stappen:
            await on_tool_result(call, resultaat, figuur)
        gezien["problemen"] = check(tekst, [])
        return LoopResult(text=tekst, problems=gezien["problemen"])

    monkeypatch.setattr(report, "tool_loop", lus)
    try:
        return asyncio.run(report.generate(sessie, _stil, figuren=tuple(figuren))), gezien
    except report.RapportGeweigerd as fout:
        return fout, gezien


def _sankey(figure_json: str) -> dict:
    [trace] = json.loads(pio.to_json(pio.from_json(figure_json)))["data"]
    figuur = pio.from_json(figure_json)
    link = figuur.data[0].link
    return {
        "type": trace["type"],
        "knopen": list(figuur.data[0].node.label),
        "stromen": list(
            zip(*(report_figuren._lijst(getattr(link, v)) for v in ("source", "target", "value")), strict=True)
        ),
    }


# ── De vaste casus: een sankey uit run_analysis ──────────────────────────────


def test_de_sankey_uit_het_gesprek_komt_in_het_rapport_met_haar_bronregel(sessie, monkeypatch):
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    _, chat = dispatch(TOOL_RUN_ANALYSIS, _SANKEY)

    spec, gezien = _rapport(sessie, monkeypatch, figuren=[figuur_id])

    [visualisatie] = spec.visualisaties
    assert _sankey(visualisatie["figure_json"]) == _sankey(pio.to_json(chat))
    assert _sankey(visualisatie["figure_json"])["type"] == "sankey"
    assert len(_sankey(visualisatie["figure_json"])["stromen"]) == 13
    # De bronregel van haar data_key (#569) en haar periode in de titel (#893).
    assert visualisatie["bron"]["dataset"] == "p01hoinges"
    assert "2023/24" in spec.title
    assert visualisatie["titel"] == "Van mbo-verpleegkundige naar hbo"
    assert harde(gezien["problemen"]) == []


def test_de_figuur_komt_uit_de_stap_niet_uit_wat_het_gesprek_bewaarde(sessie, monkeypatch):
    """De figuur-JSON van het gesprek komt van de client en is geen bewijs: ook een andere figuur in de beurten, de
    berichten of een vervalste stap-titel verandert niets aan wat het rapport toont."""
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    nep = go.Figure(go.Bar(x=["Nep"], y=[999999]), layout={"title": {"text": "Nep"}})
    sessie["turns"] = [{"question": "?", "tool_calls": [], "figures": [nep]}]
    sessie["turn_figures"] = [nep]
    sessie["messages"][3]["figures"] = [{"figure_json": pio.to_json(nep)}]
    _, chat = dispatch(TOOL_RUN_ANALYSIS, _SANKEY)

    spec, gezien = _rapport(sessie, monkeypatch, figuren=[figuur_id])

    assert _sankey(spec.visualisaties[0]["figure_json"]) == _sankey(pio.to_json(chat))
    assert "999999" not in json.dumps(spec.to_dict()) and "999999" not in gezien["prompt"]


def test_een_aangepaste_grafiek_uit_create_plot_komt_identiek_terug(sessie, monkeypatch):
    figuur_id = figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, _STAAF)
    _, chat = dispatch(TOOL_CREATE_PLOT, _STAAF)

    spec, _ = _rapport(sessie, monkeypatch, figuren=[figuur_id])

    assert spec.visualisaties[0]["figure_json"] == pio.to_json(chat)


# ── Wat het rapportmodel krijgt ──────────────────────────────────────────────


def test_het_model_krijgt_de_figuren_als_beschrijving_en_geen_tekentool(sessie, monkeypatch):
    sankey = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    staaf = figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, _STAAF)
    antwoord = {
        **_ANTWOORD,
        "visualisaties": [{"titel": "Stromen", "toelichting": "A"}, {"titel": "Per opleiding", "toelichting": "B"}],
    }

    spec, gezien = _rapport(sessie, monkeypatch, figuren=[staaf, sankey], antwoord=antwoord)

    assert gezien["tools"] == [TOOL_QUERY_DATA, TOOL_COMPUTE_KPI]
    vast = gezien["prompt"].rsplit("## Vaste figuren", 1)[1]
    # In de volgorde van het gesprek: eerst de sankey, dan de grafiek.
    assert vast.index("### Figuur 1") < vast.index("sankey") < vast.index("### Figuur 2") < vast.index("(scatter)")
    assert "Titel: Doorstroom mbo-verpleegkundigen naar hbo" in vast
    assert "Verpleegkundige → Verloskunde: 1120" in vast
    assert "Oefentherapie" in vast
    # De figuren van het rapport, in die volgorde, met de titel en toelichting van het model.
    assert [v["titel"] for v in spec.visualisaties] == ["Stromen", "Per opleiding"]
    assert [json.loads(v["figure_json"])["data"][0]["type"] for v in spec.visualisaties] == ["sankey", "scatter"]


def test_de_waarden_van_een_vaste_figuur_zijn_bewijs(sessie, monkeypatch):
    """Het getal 1120 staat alleen in de sankey (het script gaf alleen het totaal): met de figuur is het gedekt, zonder
    niet. Alle bestaande controles lopen over de vaste figuur."""
    antwoord = {**_ANTWOORD, "conclusie": "Naar Verloskunde stromen 1120 mbo-verpleegkundigen door."}
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)

    spec, met = _rapport(sessie, monkeypatch, figuren=[figuur_id], antwoord=antwoord)
    zonder_spec, zonder = _rapport(sessie, monkeypatch, antwoord={**antwoord, "visualisaties": []})

    assert harde(met["problemen"]) == [] and spec.visualisaties
    assert any("1.120" in str(p) for p in harde(zonder["problemen"]))
    assert isinstance(zonder_spec, report.RapportGeweigerd)


def test_de_titel_van_een_figuur_uit_het_gesprek_is_geen_bewijs(sessie, monkeypatch):
    """Een titel is tekst van het model in de chat (#211): een getal dat alleen daarin staat, dekt niets."""
    titel = {**_STAAF, "title": "Doorstroom, samen 98765"}
    figuur_id = figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, titel)
    antwoord = {**_ANTWOORD, "conclusie": "Samen stromen 98765 mbo-verpleegkundigen door."}

    fout, gezien = _rapport(sessie, monkeypatch, figuren=[figuur_id], antwoord=antwoord)

    assert isinstance(fout, report.RapportGeweigerd)
    assert any("98.765" in str(p) for p in harde(gezien["problemen"]))


# Een getal dat het script zelf typte en in de figuur zette, op twee manieren: letterlijk (en ook in `result`), of
# alleen in de figuur en zo dat geen literal het verraadt. Alleen de herhaling op verstoorde invoer ziet het tweede.
_GETYPT = {
    "letterlijk": (
        "a = 98765\n"
        "result = {'totaal': a + int(df['AANTAL'].sum()) * 0}\n"
        "figure = go.Figure(go.Bar(x=['Verpleegkunde'], y=[result['totaal']]))\n",
        "98765",
    ),
    "alleen-in-de-figuur": (
        "result = {'totaal': int(df['AANTAL'].sum())}\n"
        "figure = go.Figure(go.Bar(x=['Verpleegkunde'], y=[int('9' * 5) + len(df) * 0]))\n",
        "99999",
    ),
}


@pytest.mark.parametrize("code, getal", _GETYPT.values(), ids=_GETYPT.keys())
def test_een_getal_dat_het_script_typte_is_ook_in_zijn_figuur_geen_bewijs(sessie, monkeypatch, code, getal):
    """#410, CH-27: een getal dat niet van de data afhangt, bewijst niets, ook niet als waarde van een vaste figuur."""
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, {"data_key": _KEY, "code": code})
    antwoord = {**_ANTWOORD, "conclusie": f"In totaal stroomden {getal} mbo-verpleegkundigen door naar het hbo."}

    fout, gezien = _rapport(sessie, monkeypatch, figuren=[figuur_id], antwoord=antwoord)

    assert isinstance(fout, report.RapportGeweigerd)
    assert any(f"{getal[:2]}.{getal[2:]}" in str(p) for p in harde(gezien["problemen"]))


@pytest.mark.parametrize("constanten, geweigerd", [((), False), ((1120,), True)], ids=["uit-de-data", "getypt"])
def test_een_grafiek_op_een_key_met_getypte_getallen_bewijst_die_niet(sessie, monkeypatch, constanten, geweigerd):
    """Zoals query_data (CH-27, #456): wat een eerdere berekening zelf typte en met haar key meereist, is geen bewijs,
    ook niet als waarde van een grafiek. De conclusie noemt 1120, dat alleen de grafiek toont."""
    store.put(
        _KEY,
        store.get(_KEY),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=0, schooljaren=(2023,), scriptconstanten=constanten),
    )
    figuur_id = figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, _STAAF)
    antwoord = {**_ANTWOORD, "conclusie": "Naar Verloskunde stromen 1120 mbo-verpleegkundigen door."}

    spec, gezien = _rapport(sessie, monkeypatch, figuren=[figuur_id], antwoord=antwoord)

    assert isinstance(spec, report.RapportGeweigerd) is geweigerd
    assert any("1.120" in str(p) for p in harde(gezien["problemen"])) is geweigerd


def test_een_figuur_zonder_bron_bewijst_niets():
    """#201: een script dat geen data las, of een grafiek op een key zonder bekende herkomst."""
    figuur = go.Figure(go.Bar(x=["a"], y=[98765]))
    script = {"tool": TOOL_RUN_ANALYSIS, "arguments": {"code": "x"}}
    grafiek = {"tool": TOOL_CREATE_PLOT, "arguments": {"data_key": "analysis:zonderherkomst993"}}

    assert report_figuren._bewijs(script, json.dumps({"bron": None, "resultaat": {"a": 98765}}), figuur) == ()
    assert report_figuren._bewijs(grafiek, "Grafiek aangemaakt", figuur) == ()


@pytest.mark.parametrize(
    "stap",
    [
        {"id": "x", "tool": "get_duo_data", "arguments": {"dataset_id": "p01hoinges"}, "keys": [_KEY]},
        {"id": "x", "tool": TOOL_CREATE_PLOT, "arguments": _STAAF, "keys": []},
        {"id": "x", "tool": TOOL_CREATE_PLOT, "keys": [_KEY]},
    ],
    ids=["geen-figuurtool", "zonder-keys", "zonder-argumenten"],
)
def test_een_stap_die_niet_klopt_draait_niet_en_valt_weg(sessie, monkeypatch, stap):
    """Alleen de server schrijft stappen; een rij die toch niet klopt, laat alleen die figuur weg."""
    gedraaid: list = []
    echte_dispatch = report_figuren.dispatch
    monkeypatch.setattr(
        report_figuren, "dispatch", lambda tool, args: gedraaid.append(tool) or echte_dispatch(tool, args)
    )
    sessie["figuurstappen"] = [stap]

    vast = asyncio.run(maak_figuren(sessie, ("x",)))

    assert vast.figuren == () and vast.mislukt == 1
    assert "get_duo_data" not in gedraaid


def test_na_een_stop_maakt_het_rapport_geen_figuren_meer(sessie, monkeypatch):
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    gedraaid: list = []
    monkeypatch.setattr(report_figuren, "dispatch", lambda tool, args: gedraaid.append(tool))
    stop = asyncio.Event()
    stop.set()

    with pytest.raises(report.RapportGeannuleerd):
        asyncio.run(report.generate(sessie, _stil, stop_event=stop, figuren=(figuur_id,)))
    assert gedraaid == []


def test_de_beschrijving_begrenst_namen_en_knopen():
    """Namen en labels zijn tekst uit de chat: de prompt krijgt ze kort, en de knopen van een sankey begrensd zoals haar stromen."""
    lang = "x" * 500
    staaf = go.Figure(go.Bar(x=[lang], y=[3], name=lang))
    knopen = [f"k{i}" for i in range(100)]
    sankey = go.Figure(go.Sankey(node={"label": knopen}, link={"source": [0], "target": [1], "value": [5]}))

    assert lang not in beschrijf(staaf) and "x" * 79 + "…" in beschrijf(staaf)
    assert "k58; k59 (en nog 40)" in beschrijf(sankey) and "k60" not in beschrijf(sankey)


# ── Zonder keuze geen figuren; hoogstens vier ────────────────────────────────


def test_zonder_gekozen_figuren_tekent_het_rapport_niets(sessie, monkeypatch):
    """Besluit 18-11: het model krijgt geen tekentool, en een figuur die het toch maakt, valt weg."""
    figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    melding, figuur = dispatch(TOOL_CREATE_PLOT, _STAAF)
    call = ToolCall(id="p", name=TOOL_CREATE_PLOT, arguments=json.dumps(_STAAF), args=_STAAF)
    antwoord = {**_ANTWOORD, "visualisaties": []}

    spec, gezien = _rapport(sessie, monkeypatch, antwoord=antwoord, model_stappen=[(call, melding, figuur)])

    assert TOOL_CREATE_PLOT not in gezien["tools"]
    assert spec.visualisaties == []
    assert "de gebruiker koos geen figuren" in gezien["prompt"]


def test_ook_met_gekozen_figuren_voegt_het_model_er_geen_toe(sessie, monkeypatch):
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    melding, figuur = dispatch(TOOL_CREATE_PLOT, _STAAF)
    call = ToolCall(id="p", name=TOOL_CREATE_PLOT, arguments=json.dumps(_STAAF), args=_STAAF)

    spec, _ = _rapport(sessie, monkeypatch, figuren=[figuur_id], model_stappen=[(call, melding, figuur)])

    assert [json.loads(v["figure_json"])["data"][0]["type"] for v in spec.visualisaties] == ["sankey"]


def test_hoogstens_vier_figuren(sessie):
    ids = [figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, {**_STAAF, "title": f"Figuur {i}"}) for i in range(5)]

    vast = asyncio.run(maak_figuren(sessie, tuple(ids)))

    assert len(vast.figuren) == MAX_FIGUREN == 4 and vast.mislukt == 0


# ── Een figuur die niet terugkomt ────────────────────────────────────────────


@pytest.mark.parametrize(
    "dispatcher",
    [
        lambda tool, args: ("Fout in script:\nZeroDivisionError", None),
        lambda tool, args: (_ for _ in ()).throw(RuntimeError("sandbox weg")),
        lambda tool, args: ('{"gelezen": []}', go.Figure()),
    ],
    ids=["sandboxfout", "uitzondering", "lege-figuur"],
)
def test_een_figuur_die_niet_opnieuw_lukt_valt_weg_met_een_regel(sessie, monkeypatch, dispatcher):
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    monkeypatch.setattr(report_figuren, "dispatch", dispatcher)
    antwoord = {**_ANTWOORD, "visualisaties": []}

    spec, gezien = _rapport(sessie, monkeypatch, figuren=[figuur_id], antwoord=antwoord)

    assert not isinstance(spec, report.RapportGeweigerd)
    assert spec.visualisaties == []
    assert spec.beantwoordt_niet[0] == NIET_OPNIEUW == "Deze figuur uit het gesprek kon niet opnieuw gemaakt worden."
    assert "konden niet opnieuw gemaakt worden" in gezien["prompt"]


def test_data_die_niet_meer_terugkomt_laat_alleen_die_figuur_weg(sessie, monkeypatch):
    """Het script las een key die de store kwijt is en die geen recept heeft: de figuur valt weg, de rest blijft."""
    weg = "duo:p01hoinges:0:weg993"
    store.put(weg, pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p01hoinges", resource=0))
    script = {"data_key": _KEY, "code": f"x = store_get('{weg}')\n" + _SANKEY["code"]}
    kapot = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, script)
    heel = figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, _STAAF)
    store._verwijder(weg, "test")  # wat een herstart of de TTL doet
    antwoord = {**_ANTWOORD, "visualisaties": [{"titel": "Per opleiding", "toelichting": "B"}]}

    spec, _ = _rapport(sessie, monkeypatch, figuren=[kapot, heel], antwoord=antwoord)

    assert [v["titel"] for v in spec.visualisaties] == ["Per opleiding"]
    assert spec.beantwoordt_niet.count(NIET_OPNIEUW) == 1


def test_de_regel_is_geen_modeltekst_voor_de_controles(sessie, monkeypatch):
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    monkeypatch.setattr(report_figuren, "dispatch", lambda tool, args: ("Fout", None))
    gecontroleerd: list = []
    echte_controle = report.report_problems

    def controle(spec, *args):
        gecontroleerd.append(list(spec.beantwoordt_niet))
        return echte_controle(spec, *args)

    monkeypatch.setattr(report, "report_problems", controle)
    _rapport(sessie, monkeypatch, figuren=[figuur_id], antwoord={**_ANTWOORD, "visualisaties": []})

    assert gecontroleerd and all(NIET_OPNIEUW not in regels for regels in gecontroleerd)


# ── De keten: checklist, keuze, rapport ──────────────────────────────────────


def test_een_figuur_van_een_latere_beurt_zonder_data_staat_bij_de_databeurt_en_trekt_die_mee(sessie, monkeypatch):
    """Beurt 2 ("maak er een sankey van") haalde geen data op: de sankey staat bij beurt 1 en trekt die mee."""
    from agent.rapportselectie import beurten_met_data

    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)

    [item] = beurten_met_data(sessie)
    assert item["beurt"] == 1 and item["figuren"] == [
        {"id": figuur_id, "titel": "Doorstroom mbo-verpleegkundigen naar hbo", "beurten": [1]}
    ]
    keuze = kies(sessie, [], [figuur_id])
    spec, _ = _rapport(sessie, monkeypatch, figuren=keuze.figuren)
    assert len(spec.visualisaties) == 1


# ── Grootte (#785) ───────────────────────────────────────────────────────────


def test_een_rapport_met_vaste_figuren_blijft_ruim_onder_de_grens(sessie, monkeypatch):
    """Een rapport met de sankey van 13 stromen, en een met vier figuren, past ruim in MAX_REQUEST_BYTES (4 MiB)."""
    sankey = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)
    anderen = [figuur_in_gesprek(sessie, TOOL_CREATE_PLOT, {**_STAAF, "title": f"Figuur {i}"}) for i in range(3)]

    een, _ = _rapport(sessie, monkeypatch, figuren=[sankey])
    vier, _ = _rapport(sessie, monkeypatch, figuren=[sankey, *anderen])

    groottes = [len(json.dumps(spec.to_dict(), ensure_ascii=False).encode()) for spec in (een, vier)]
    assert len(vier.visualisaties) == 4
    assert all(g < MAX_REQUEST_BYTES / 20 for g in groottes), groottes


def test_de_beschrijving_kent_ook_de_base64_vorm_van_plotly():
    """Een figuur uit een script komt als dict terug; Plotly 6+ zet een numpy-array daarin als `bdata`."""
    figuur = go.Figure(json.loads(pio.to_json(go.Figure(go.Bar(x=["a", "b"], y=pd.Series([3, 4]).to_numpy())))))

    assert "a: 3; b: 4" in beschrijf(figuur)


def test_de_stap_van_een_figuur_staat_in_de_sessie(sessie):
    figuur_id = figuur_in_gesprek(sessie, TOOL_RUN_ANALYSIS, _SANKEY)

    [stap] = figuurstappen.stappen(sessie)
    assert stap["id"] == figuur_id and stap["keys"][0] == _KEY
