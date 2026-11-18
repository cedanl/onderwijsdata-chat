"""Een telling of vergelijking in de tekst wordt nagerekend tegen de tabel eronder (#1013, reaudit C01/N07/M01)."""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent.beweringtelling import onjuiste_tabelbeweringen
from agent.probleem import INGEHOUDEN
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

# Twaalf hogescholen, negen dalen en drie stijgen (N07-vorm): als verschilkolom en als twee jaarkolommen.
_HOGESCHOLEN = [f"Hogeschool {letter}" for letter in "ABCDEFGHIJKL"]
_2023 = [1200, 950, 880, 760, 640, 610, 540, 495, 430, 390, 310, 205]
_2024 = [1080, 915, 851, 752, 639, 596, 480, 493, 421, 430, 322, 210]
_VERSCHIL = [b - a for a, b in zip(_2023, _2024, strict=True)]


def _verschiltabel(verschillen=_VERSCHIL, extra: str = "") -> str:
    rijen = "\n".join(f"| {h} | {v} |" for h, v in zip(_HOGESCHOLEN, verschillen, strict=True))
    return f"| Hogeschool | Verschil 2023/24–2024/25 |\n|---|---:|\n{rijen}{extra}"


def _jaartabel(extra: str = "") -> str:
    rijen = "\n".join(f"| {h} | {a} | {b} |" for h, a, b in zip(_HOGESCHOLEN, _2023, _2024, strict=True))
    return f"| Hogeschool | 2023/24 | 2024/25 |\n|---|---:|---:|\n{rijen}{extra}"


# M01 (reaudit 10-11): wo-gediplomeerden per diplomasoort; in beide jaren meer wo-master- dan bachelordiploma's.
_M01 = """| Studiejaar | Bachelor | Wo-master | Vervolgopleidingen |
|---|---:|---:|---:|
| 2022/23 | 45.590 | 49.730 | 3.750 |
| 2023/24 | 50.110 | 50.690 | 3.790 |
| 2024/25 (voorlopig) | 52.250 | 53.570 | 3.740 |"""
_M01_GEDRAAID = """| Diplomasoort | 2023/24 | 2024/25 |
|---|---:|---:|
| Bachelor | 50.110 | 52.250 |
| Wo-master | 50.690 | 53.570 |"""
_M01_FOUT = "In 2023/24 en 2024/25 waren er meer bachelor- dan wo-masterdiploma's."


def _controle(zin: str, tabel: str, tool_results: list[str] | None = None):
    return onjuiste_tabelbeweringen([f"{zin}\n\n{tabel}"], tool_results or [])


# --- Criterium 1: de telling --------------------------------------------------------------------------------------


@pytest.mark.parametrize("tabel", [_verschiltabel(), _jaartabel()], ids=["verschilkolom", "jaarkolommen"])
def test_een_foute_telling_noemt_de_telling_van_de_tabel(tabel):
    [probleem] = _controle("Opvallend: 10 van de 12 hogescholen is gedaald.", tabel)

    assert probleem.melding == "10 van de 12 hogescholen is gedaald, maar in de tabel zijn het er 9 van de 12."
    assert probleem.hard


@pytest.mark.parametrize("tabel", [_verschiltabel(), _jaartabel()], ids=["verschilkolom", "jaarkolommen"])
@pytest.mark.parametrize(
    "zin",
    [
        "9 van de 12 hogescholen is gedaald.",
        "3 van de 12 hogescholen is gegroeid.",
        "Negen van de twaalf hogescholen daalden, drie van de twaalf hogescholen stegen.",
        "3 van de 12 hogescholen namen toe.",
        "9 van de 12 hogescholen kromp.",
    ],
)
def test_een_juiste_telling_is_in_orde(tabel, zin):
    assert _controle(zin, tabel) == []


@pytest.mark.parametrize(
    ("zin", "juist"),
    [
        ("Tien van de twaalf hogescholen daalden.", "9 van de 12"),
        ("4 van de 12 hogescholen zijn gestegen.", "3 van de 12"),
        ("8 van de 12 hogescholen namen af.", "9 van de 12"),
        ("2 van de 12 hogescholen groeiden.", "3 van de 12"),
    ],
)
def test_elke_werkwoordsvorm_en_een_telwoord_worden_gelezen(zin, juist):
    [probleem] = _controle(zin, _verschiltabel())

    assert f"zijn het er {juist}." in probleem.melding


@pytest.mark.parametrize("min", ["-", "−"])
def test_een_procent_met_minteken_is_een_daling_en_nul_is_geen_van_beide(min):
    verschillen = [f"{min}3,2%"] * 8 + ["0,0%", "+1,5%", "2,0%", "4%"]

    assert _controle("8 van de 12 hogescholen is gedaald.", _verschiltabel(verschillen)) == []
    assert _controle("3 van de 12 hogescholen is gestegen.", _verschiltabel(verschillen)) == []
    [probleem] = _controle("9 van de 12 hogescholen is gedaald.", _verschiltabel(verschillen))
    assert "zijn het er 8 van de 12" in probleem.melding


@pytest.mark.parametrize("leeg", ["-", "n.v.t.", "*", ""])
def test_een_rij_zonder_cijfer_telt_niet_mee(leeg):
    tabel = _verschiltabel(extra=f"\n| Hogeschool M | {leeg} |")

    assert _controle("9 van de 12 hogescholen is gedaald.", tabel) == []
    [probleem] = _controle("10 van de 12 hogescholen is gedaald.", tabel)
    assert "9 van de 12" in probleem.melding


@pytest.mark.parametrize("totaal", ["Totaal", "**Landelijk**", "Gemiddelde"])
def test_een_totaalrij_telt_niet_mee_tenzij_m_daar_beter_bij_past(totaal):
    tabel = _verschiltabel(extra=f"\n| {totaal} | -330 |")

    [zonder] = _controle("10 van de 12 hogescholen is gedaald.", tabel)
    assert "9 van de 12" in zonder.melding and zonder.hard
    [met] = _controle("9 van de 13 hogescholen is gedaald.", tabel)
    assert "10 van de 13" in met.melding and not met.hard


def test_jaarkolommen_en_verschilkolom_die_elkaar_tegenspreken_geven_geen_melding():
    verschillen = ["-1"] * 12  # de jaarkolommen zeggen 9 dalers, de verschilkolom 12
    rijen = "\n".join(
        f"| {h} | {a} | {b} | {v} |" for h, a, b, v in zip(_HOGESCHOLEN, _2023, _2024, verschillen, strict=True)
    )
    tabel = f"| Hogeschool | 2023/24 | 2024/25 | Verschil |\n|---|---:|---:|---:|\n{rijen}"

    assert _controle("10 van de 12 hogescholen is gedaald.", tabel) == []


def test_jaarkolommen_en_verschilkolom_die_overeenkomen_geven_een_melding():
    rijen = "\n".join(
        f"| {h} | {a} | {b} | {v} |" for h, a, b, v in zip(_HOGESCHOLEN, _2023, _2024, _VERSCHIL, strict=True)
    )
    tabel = f"| Hogeschool | 2023/24 | 2024/25 | Verschil |\n|---|---:|---:|---:|\n{rijen}"

    [probleem] = _controle("10 van de 12 hogescholen is gedaald.", tabel)
    assert "9 van de 12" in probleem.melding


# --- Criterium 2: de vergelijking ---------------------------------------------------------------------------------


@pytest.mark.parametrize("tabel", [_M01, _M01_GEDRAAID], ids=["jaren-in-rijen", "jaren-in-kolommen"])
def test_de_m01_vergelijking_wordt_gemeld(tabel):
    [probleem] = _controle(_M01_FOUT, tabel)

    assert "'meer bachelor- dan wo-masterdiploma's' voor 2023/24 en 2024/25" in probleem.melding
    assert "in 2023/24 Bachelor 50.110 en Wo-master 50.690" in probleem.melding
    assert "in 2024/25 Bachelor 52.250 en Wo-master 53.570" in probleem.melding
    assert not probleem.hard


@pytest.mark.parametrize("tabel", [_M01, _M01_GEDRAAID], ids=["jaren-in-rijen", "jaren-in-kolommen"])
@pytest.mark.parametrize(
    "zin",
    [
        "In 2023/24 en 2024/25 waren er meer wo-master- dan bachelordiploma's.",
        "In 2024/25 waren er iets meer wo-master dan bachelor.",
        "In 2023/24 en 2024/25 waren er minder bachelor- dan wo-masterdiploma's.",
        "In 2019/20 waren er meer bachelor- dan wo-masterdiploma's.",
        "In 2024/25 waren er meer bachelor- dan wo-masterdiploma's niet.",
    ],
)
def test_een_juiste_vergelijking_of_een_onbekend_jaar_geeft_geen_melding(tabel, zin):
    assert _controle(zin, tabel) == []


def test_een_vergelijking_zonder_jaar_geeft_geen_melding():
    assert _controle("Er waren meer bachelor- dan wo-masterdiploma's.", _M01) == []


def test_een_vergelijking_die_in_een_van_de_jaren_klopt_geeft_geen_melding():
    tabel = _M01.replace("| 2024/25 (voorlopig) | 52.250 |", "| 2024/25 (voorlopig) | 54.250 |")

    assert _controle(_M01_FOUT, tabel) == []


# --- Criterium 3: zwijgen bij twijfel -----------------------------------------------------------------------------


def test_twee_tabellen_die_beide_passen_geven_geen_melding():
    assert _controle("10 van de 12 hogescholen is gedaald.", f"{_verschiltabel()}\n\n{_jaartabel()}") == []
    assert _controle(_M01_FOUT, f"{_M01}\n\n{_M01_GEDRAAID}") == []


def test_een_passende_en_een_andere_tabel_geven_wel_een_melding():
    andere = "| Instelling | Studenten |\n|---|---:|\n| Hogeschool A | 1200 |"

    assert len(_controle("10 van de 12 hogescholen is gedaald.", f"{andere}\n\n{_verschiltabel()}")) == 1


def test_zonder_verschilkolom_of_jaarkolommen_geen_melding():
    rijen = "\n".join(f"| {h} | {a} |" for h, a in zip(_HOGESCHOLEN, _2023, strict=True))
    tabel = f"| Hogeschool | Studenten |\n|---|---:|\n{rijen}"

    assert _controle("10 van de 12 hogescholen is gedaald.", tabel) == []


def test_meer_dan_twee_jaarkolommen_geven_geen_melding():
    rijen = "\n".join(f"| {h} | {a} | {a} | {b} |" for h, a, b in zip(_HOGESCHOLEN, _2023, _2024, strict=True))
    tabel = f"| Hogeschool | 2022/23 | 2023/24 | 2024/25 |\n|---|---:|---:|---:|\n{rijen}"

    assert _controle("10 van de 12 hogescholen is gedaald.", tabel) == []


@pytest.mark.parametrize("m", [11, 14, 20])
def test_een_m_die_bij_geen_rijtelling_past_geeft_geen_melding(m):
    assert _controle(f"10 van de {m} hogescholen is gedaald.", _verschiltabel(extra="\n| Totaal | -330 |")) == []


def test_zonder_tabel_en_zonder_key_geen_melding():
    assert onjuiste_tabelbeweringen(["10 van de 12 hogescholen is gedaald."], []) == []
    assert onjuiste_tabelbeweringen([_M01_FOUT], []) == []


def test_een_zin_in_een_codeblok_geeft_geen_melding():
    tekst = f"```\n10 van de 12 hogescholen is gedaald.\n{_M01_FOUT}\n```\n\n{_verschiltabel()}\n\n{_M01}"

    assert onjuiste_tabelbeweringen([tekst], []) == []


def test_een_tabel_in_een_codeblok_telt_niet():
    assert _controle("10 van de 12 hogescholen is gedaald.", f"```\n{_verschiltabel()}\n```") == []


@pytest.mark.parametrize(
    "zin",
    [
        "De meeste hogescholen is gedaald.",
        "Bijna alle hogescholen zijn gedaald.",
        "Twee derde van de hogescholen is gedaald.",
        "Van de 12 hogescholen daalden er 10.",
        "10 van de 12 hogescholen met meer dan 5.000 studenten is gedaald.",
        "Bijna 10 van de 12 hogescholen is gedaald.",
        "Niet 10 van de 12 hogescholen is gedaald.",
        "Is 10 van de 12 hogescholen gedaald?",
        "10 van de 12 hogescholen is gedaald of gelijk gebleven.",
        "Tussen 2020/21 en 2024/25 is 10 van de 12 hogescholen gedaald.",
        "Een van de 12 hogescholen is gedaald.",
        "Het is `10 van de 12 hogescholen is gedaald`.",
    ],
)
def test_een_andere_formulering_geeft_geen_melding(zin):
    assert _controle(zin, _verschiltabel()) == []


@pytest.mark.parametrize(
    "zin",
    [
        "In 2024/25 groeiden er meer bachelor- dan wo-masterdiploma's.",
        "In 2023/24 waren er meer bachelor- dan wo-masterdiploma's en meer bachelor- dan vervolgdiploma's.",
        "In 2023/24 en 2024/25 waren er meer studenten dan vorig jaar.",
    ],
)
def test_een_andere_vergelijking_geeft_geen_melding(zin):
    assert _controle(zin, _M01) == []


def test_een_voorzetsel_wijst_geen_kolom_aan():
    """'dan in 2023/24' is geen kolom 'Instroom': 'in' is te kort en geen soort."""
    tabel = "| Studiejaar | Studenten | Instroom |\n|---|---:|---:|\n| 2023/24 | 300 | 900 |\n| 2024/25 | 310 | 950 |"

    assert _controle("In 2024/25 waren er meer studenten dan in 2023/24.", tabel) == []
    assert len(_controle("In 2024/25 waren er meer studenten dan instroom.", tabel)) == 1


def test_een_bewering_die_in_een_lezing_klopt_is_niet_fout():
    fout, goed = f"10 van de 12 hogescholen is gedaald.\n\n{_verschiltabel()}", _verschiltabel()

    assert onjuiste_tabelbeweringen([fout, f"9 van de 12 hogescholen is gedaald.\n\n{goed}"], []) == []
    assert len(onjuiste_tabelbeweringen([fout, fout], [])) == 1


# --- De afgeleide key als bron, alleen zonder bruikbare tabel -----------------------------------------------------

_LAAD = "duo:p01hoinges"
_SELECTIE = f"{_LAAD}:verschil"


def _key(df: pd.DataFrame, afgeleid: bool = True) -> list[str]:
    store.put(_LAAD, pd.DataFrame({"x": [1]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    if afgeleid:
        store.derive(_LAAD, _SELECTIE, df)
    else:
        store.put(_SELECTIE, df, KeyMeta(bron="duo", dataset="p01hoinges"))
    return [json.dumps({"data_key": _SELECTIE, "rijen": []})]


def _verschil_df() -> pd.DataFrame:
    return pd.DataFrame({"INSTELLINGSNAAM": _HOGESCHOLEN, "VERSCHIL": _VERSCHIL})


def test_zonder_tabel_rekent_de_controle_na_tegen_de_afgeleide_key():
    tool_results = _key(_verschil_df())

    [probleem] = onjuiste_tabelbeweringen(["10 van de 12 hogescholen is gedaald."], tool_results)
    assert probleem.melding == (
        "10 van de 12 hogescholen is gedaald, maar in de opgehaalde data zijn het er 9 van de 12."
    )
    assert not probleem.hard
    assert onjuiste_tabelbeweringen(["9 van de 12 hogescholen is gedaald."], tool_results) == []


def test_de_vergelijking_tegen_de_afgeleide_key():
    df = pd.DataFrame(
        {"STUDIEJAAR_LABEL": ["2023/2024", "2024/2025"], "Bachelor": [50110, 52250], "Wo-master": [50690, 53570]}
    )

    [probleem] = onjuiste_tabelbeweringen([_M01_FOUT], _key(df))
    assert "in de opgehaalde data staat in 2023/24 Bachelor 50.110 en Wo-master 50.690" in probleem.melding


def test_een_bruikbare_tabel_gaat_voor_de_key():
    tool_results = _key(pd.DataFrame({"INSTELLINGSNAAM": _HOGESCHOLEN, "VERSCHIL": [-1] * 12}))

    [probleem] = _controle("10 van de 12 hogescholen is gedaald.", _verschiltabel(), tool_results)
    assert "in de tabel zijn het er 9 van de 12" in probleem.melding


def test_een_geladen_key_die_niet_afgeleid_is_telt_niet():
    assert onjuiste_tabelbeweringen(["10 van de 12 hogescholen is gedaald."], _key(_verschil_df(), False)) == []


# --- Criterium 6: het nepmodel --------------------------------------------------------------------------------------

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}
_M01_DATA = json.dumps(
    {
        "data_key": "cbs:85424NED:a",
        "rijen": [
            {"Studiejaar": "2023/24", "Bachelor": 50110, "Wo-master": 50690},
            {"Studiejaar": "2024/25", "Bachelor": 52250, "Wo-master": 53570},
        ],
    }
)
_TELLING_DATA = json.dumps({"data_key": "duo:p02:a", "rijen": [{"Verschil": v} for v in _VERSCHIL]})

_TELLING_FOUT = f"10 van de 12 hogescholen is gedaald.\n\n{_verschiltabel()}"
_TELLING_GOED = f"9 van de 12 hogescholen is gedaald.\n\n{_verschiltabel()}"
_VERGELIJKING_FOUT = f"{_M01_FOUT}\n\n{_M01_GEDRAAID}"
_VERGELIJKING_GOED = f"In 2023/24 en 2024/25 waren er meer wo-master- dan bachelordiploma's.\n\n{_M01_GEDRAAID}"


def _chat(monkeypatch, antwoorden: list[str], tool_result: str) -> tuple[str, list[dict]]:
    stappen = [StreamResult(text="", tool_calls=[_QUERY])] + [StreamResult(text=a, tool_calls=[]) for a in antwoorden]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return tool_result, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = [{"role": "user", "content": "Hoeveel eerstejaars?"}]
    text = asyncio.run(run_module.run(vraag, {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return text, events


@pytest.mark.usefixtures("zonder_scopekaart")
@pytest.mark.parametrize(
    ("fout", "goed", "data", "melding"),
    [
        (_TELLING_FOUT, _TELLING_GOED, _TELLING_DATA, "maar in de tabel zijn het er 9 van de 12"),
        (_VERGELIJKING_FOUT, _VERGELIJKING_GOED, _M01_DATA, "Bachelor 50.110 en Wo-master 50.690"),
    ],
    ids=["telling", "vergelijking"],
)
def test_de_herkansing_vervangt_de_foute_bewering(monkeypatch, caplog, fout, goed, data, melding):
    with caplog.at_level("INFO", logger="agent.run"):
        text, events = _chat(monkeypatch, [fout, goed], data)

    assert text == goed
    [cancel] = [e for e in events if e["type"] == "message_cancel"]
    assert any(melding in reden for reden in cancel["reden"])
    assert events[-1]["content"] == goed and "controle" not in events[-1]
    assert fout.split("\n")[0] not in events[-1]["content"]
    controles = [r.getMessage() for r in caplog.records if r.getMessage().startswith("CONTROLES")]
    assert "onjuiste_tabelbeweringen=" in controles[0] and "onjuiste_tabelbeweringen=ok" in controles[-1]


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_telling_die_blijft_wordt_ingehouden(monkeypatch):
    text, events = _chat(monkeypatch, [_TELLING_FOUT, _TELLING_FOUT], _TELLING_DATA)

    assert text == INGEHOUDEN
    assert events[-1]["content"] == INGEHOUDEN
    assert events[-1]["controle"] == ["10 van de 12 hogescholen is gedaald, maar in de tabel zijn het er 9 van de 12."]


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_vergelijking_die_blijft_staat_er_met_de_melding_onder(monkeypatch):
    text, events = _chat(monkeypatch, [_VERGELIJKING_FOUT, _VERGELIJKING_FOUT], _M01_DATA)

    assert text == _VERGELIJKING_FOUT != INGEHOUDEN
    assert events[-1]["content"] == text
    [melding] = events[-1]["controle"]
    assert melding.startswith("Het antwoord zegt 'meer bachelor- dan wo-masterdiploma's' voor 2023/24 en 2024/25")


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_telling_tegen_de_key_die_blijft_is_zacht(monkeypatch):
    tool_results = _key(_verschil_df())
    fout = "10 van de 12 hogescholen is gedaald."

    text, events = _chat(monkeypatch, [fout, fout], tool_results[0])

    # Een DUO-telling krijgt vooraan de regel over wat niet meetelt (#743); het antwoord zelf blijft staan.
    assert text.endswith(fout) and text != INGEHOUDEN
    assert events[-1]["controle"] == [
        "10 van de 12 hogescholen is gedaald, maar in de opgehaalde data zijn het er 9 van de 12."
    ]
