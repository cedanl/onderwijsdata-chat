"""De gebruiker kiest bij "Genereer rapport" welke beurten met data in het rapport komen (#908).

Een zijsprong, een verkeerde dataset of een vervangen vraag ging mee in het rapport, tenzij de gebruiker de afbakening
typte. Nu stuurt de client de beurten die aanstaan mee, en rapporteert de server alleen daarover: een uitgezette beurt
komt nergens terug, ook niet in de bronnen, het rekenbewijs of de controles.

Het gesprek hieronder heeft drie beurten met data en één zonder:
1. de DUO-inschrijvingen (key `_UU`), met een berekend aantal;
2. een zijsprong naar het CBS-rendement (key `_CBS`), met een berekend groeipercentage (+8 %);
3. alleen de vrouwen bij de UU: een selectie op key 1 (key `_VROUW`, afgeleid van `_UU`);
4. een bedankje, zonder data.
"""

import asyncio
import json

import pandas as pd
import pytest

from agent import beurtbewijs, rapportselectie, report
from agent.loop import LoopResult, ToolCall
from agent.rapportselectie import LEGE_SELECTIE, VEROUDERDE_SELECTIE, beperk, beurten_met_data, kies
from agent.report import RapportGeweigerd
from agent.session_data import gebruikersvragen, record_data_key, record_rekenbewijs
from core.errors import Gebruikersfout
from routes import chat
from tools import store
from tools.kpi import compute_kpi
from tools.schemas import TOOL_COMPUTE_KPI, TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_QUERY_DATA
from tools.store import KeyMeta

_UU = "duo:p01hoinges:3"
_VROUW = f"{_UU}:ab12cd34"
_CBS = "cbs:83285NED"

_V1 = "Hoeveel studenten heeft de UU?"
_V2 = "Even wat anders: hoe groeit het wo-rendement?"
_V3 = "Alleen de vrouwen bij de UU"
_V4 = "Dank, tot zo!"

_LAAD_UU = {"name": TOOL_GET_DUO_DATA, "arguments": {"dataset_id": "p01hoinges", "resource": 3}}
_LAAD_CBS = {"name": TOOL_GET_CBS_DATA, "arguments": {"dataset_id": "83285NED"}}
_SELECTIE = {"name": TOOL_QUERY_DATA, "arguments": {"data_key": _UU, "filters": {"GESLACHT": "V"}}}

_ANTWOORD = json.dumps(
    {
        "onderzoeksvraag": "Hoeveel studenten heeft de UU?",
        "beantwoordt": ["Het aantal studenten"],
        "beantwoordt_niet": ["De oorzaken"],
        "visualisaties": [],
        "conclusie": "De UU heeft 128.000 inschrijvingen.",
    }
)


def _frame(n: int) -> pd.DataFrame:
    return pd.DataFrame({"STUDIEJAAR": [2021, 2022, 2023, 2024, 2025], "AANTAL": [25000 + n * i for i in range(5)]})


def _vraag(sessie: dict, tekst: str) -> None:
    sessie.setdefault("messages", []).append({"role": "user", "content": tekst})


def _antwoord(sessie: dict, tekst: str) -> None:
    sessie["messages"].append({"role": "assistant", "content": tekst})


def _laad(sessie: dict, key: str, call: dict) -> None:
    record_data_key(sessie, json.dumps({"data_key": key}), call)


@pytest.fixture
def sessie():
    store.put(_UU, _frame(300), KeyMeta("duo", "p01hoinges", resource=3))
    store.derive(_UU, _VROUW, _frame(100))
    store.put(_CBS, _frame(500), KeyMeta("cbs", "83285NED"))
    s: dict = {"username": "tester"}
    _vraag(s, _V1)
    _laad(s, _UU, _LAAD_UU)
    record_rekenbewijs(s, compute_kpi(_UU, "AANTAL", "sum"), {"name": TOOL_COMPUTE_KPI, "arguments": {"data_key": _UU}})
    _antwoord(s, "Zie de tabel.")
    _vraag(s, _V2)
    _laad(s, _CBS, _LAAD_CBS)
    groei = compute_kpi(_CBS, "AANTAL", "pct_change", "STUDIEJAAR")
    record_rekenbewijs(s, groei, {"name": TOOL_COMPUTE_KPI, "arguments": {"data_key": _CBS}})
    _antwoord(s, "Zie de grafiek.")
    _vraag(s, _V3)
    _laad(s, _VROUW, _SELECTIE)
    _antwoord(s, "Zie de selectie.")
    _vraag(s, _V4)
    _antwoord(s, "Graag gedaan.")
    return s


# ── De checklist ─────────────────────────────────────────────────────────────


def test_de_checklist_heeft_een_regel_per_beurt_met_data(sessie):
    items = beurten_met_data(sessie)

    assert [i["beurt"] for i in items] == [1, 2, 3]
    assert [i["vraag"] for i in items] == [_V1, _V2, _V3]
    assert "p01hoinges" in items[0]["bronnen"][0] and "83285NED" in items[1]["bronnen"][0]


def test_een_beurt_die_voortbouwt_op_een_eerdere_zegt_dat(sessie):
    """De bron van beurt 1 blijft in het rapport als alleen beurt 3 aanstaat: de gebruiker moet dat vooraf weten."""
    items = beurten_met_data(sessie)

    assert [i["bouwt_voort_op"] for i in items] == [[], [], [1]]
    assert items[2]["bronnen"] == items[0]["bronnen"]


def test_een_lange_vraag_staat_ingekort_op_een_regel_in_de_checklist(sessie):
    sessie["messages"][0]["content"] = "Hoeveel   studenten\nheeft de UU " * 40

    [eerste, *_] = beurten_met_data(sessie)

    assert "\n" not in eerste["vraag"] and eerste["vraag"].endswith("…")
    assert len(eerste["vraag"]) == rapportselectie.MAX_VRAAG_TEKENS


def test_zonder_data_geen_checklist():
    s: dict = {}
    _vraag(s, _V4)

    assert beurten_met_data(s) == []


def test_een_gesprek_met_een_key_zonder_vraagnummer_krijgt_geen_checklist(sessie):
    """Een gesprek van vóór #875 of een antwoord buiten de geschiedenis: we weten niet bij welke beurt de key hoort."""
    del sessie["data_vraag"][_CBS]

    assert beurten_met_data(sessie) == []


def _heropen(sessie: dict, rijen: dict | None = None) -> dict:
    """Het gesprek zoals de server het na heropenen kent: de tekst van de client en het bewijs per antwoord."""
    heropend = chat._new_session(username="tester")
    chat._open_conversation(heropend, sessie["messages"], sessie["data_keys"], rijen)
    return heropend


def _rijen(sessie: dict) -> dict[str, dict]:
    """De rijen van `beurtbewijs` die de levende sessie per antwoord klaarzette."""
    rijen: dict[str, dict] = {}
    nummer = 0
    for bericht in sessie["messages"]:
        if bericht["role"] == "user":
            nummer += 1
        else:
            keys = [k for k, n in sessie["data_vraag"].items() if n == nummer]
            rijen[beurtbewijs.tekst_hash(bericht["content"])] = {
                "lineage": {k: sessie["data_provenance"][k] for k in keys},
                "rekenbewijs": [],
                "kaarten": {},
                "created_at": "2026-11-03T10:00:00+00:00",
            }
    return rijen


def test_een_heropend_gesprek_geeft_dezelfde_checklist_als_het_levende(sessie):
    heropend = _heropen(sessie, _rijen(sessie))

    assert beurten_met_data(heropend) == beurten_met_data(sessie)


def test_een_heropend_gesprek_zonder_bewijs_per_beurt_valt_terug_op_het_huidige_gedrag(sessie):
    heropend = _heropen(sessie, {})

    assert heropend["data_keys"] == sessie["data_keys"]
    assert beurten_met_data(heropend) == []
    assert kies(heropend, None) is None
    with pytest.raises(Gebruikersfout, match=VEROUDERDE_SELECTIE):
        kies(heropend, [1])


# ── De selectie controleren ──────────────────────────────────────────────────


def test_zonder_selectie_of_met_alles_aan_blijft_het_rapport_zoals_het_was(sessie):
    assert kies(sessie, None) is None
    assert kies(sessie, [1, 2, 3]) is None
    assert kies(sessie, [3, 3, 2, 1]) is None


def test_een_deel_van_de_beurten_is_een_selectie(sessie):
    assert kies(sessie, [3, 1]) == frozenset({1, 3})


def test_een_selectie_die_niets_overlaat_wordt_geweigerd_met_de_reden(sessie):
    with pytest.raises(Gebruikersfout) as fout:
        kies(sessie, [])

    assert str(fout.value) == LEGE_SELECTIE and "minstens één" in LEGE_SELECTIE


@pytest.mark.parametrize(
    "selectie",
    [[4], [0], [-1], [1, 99], ["1"], [1.0], [True], [None], [[1]], "1", {"1": True}, 1],
    ids=repr,
)
def test_een_onbekende_of_misvormde_selectie_wordt_geweigerd_niet_geraden(sessie, selectie):
    """Een beurt zonder data (4), een nummer dat er niet is of iets dat geen lijst getallen is: niet stil negeren,
    want dan krijgt de gebruiker een ander rapport dan hij op zijn scherm kiest."""
    with pytest.raises(Gebruikersfout) as fout:
        kies(sessie, selectie)

    assert str(fout.value) == VEROUDERDE_SELECTIE


# ── De weergave zonder de uitgezette beurten ─────────────────────────────────


def test_de_weergave_laat_de_uitgezette_beurt_weg_en_nummert_opnieuw(sessie):
    uitgave = beperk(sessie, frozenset({1, 3}))

    assert gebruikersvragen(uitgave) == [_V1, _V3, _V4]
    assert uitgave["data_keys"] == [_UU, _VROUW]
    assert uitgave["data_vraag"] == {_UU: 1, _VROUW: 2}
    assert _V2 not in json.dumps(uitgave) and _CBS not in json.dumps(uitgave)


def test_de_herkomst_van_een_gekozen_key_blijft_tot_zijn_laadaanroep(sessie):
    """Beurt 1 staat uit, maar beurt 3 is daaruit afgeleid: de bron van de laadaanroep is de bron van het rapport."""
    uitgave = beperk(sessie, frozenset({3}))

    assert uitgave["data_keys"] == [_VROUW]
    assert set(uitgave["data_provenance"]) == {_UU, _VROUW}
    assert gebruikersvragen(uitgave) == [_V3, _V4]


def test_het_rekenbewijs_van_een_uitgezette_beurt_valt_weg(sessie):
    uitgave = beperk(sessie, frozenset({1, 3}))

    assert [b["argumenten"]["data_key"] for b in uitgave["rekenbewijs"]] == [_UU]


def test_rekenbewijs_zonder_herleidbare_key_gaat_niet_mee_bij_een_selectie(sessie):
    record_rekenbewijs(sessie, json.dumps({"raw": 7}), {"name": TOOL_COMPUTE_KPI, "arguments": {}})

    assert len(beperk(sessie, frozenset({1, 3}))["rekenbewijs"]) == 1


def test_een_kaart_van_een_uitgezette_beurt_valt_weg(sessie):
    sessie["kaarten"] = {_CBS: {"data_key": _CBS, "location_col": "REGIO", "value_col": "AANTAL"}}

    assert beperk(sessie, frozenset({1, 3}))["kaarten"] == {}
    assert _CBS in beperk(sessie, frozenset({1, 2}))["kaarten"]


def test_de_weergave_neemt_alleen_de_velden_van_het_rapport_mee(sessie):
    sessie["turns"] = [{"question": _V2}]
    sessie["geheim_veld"] = _V2

    uitgave = beperk(sessie, frozenset({1}))

    assert uitgave["turns"] == [] and "geheim_veld" not in uitgave


# ── Het rapport ──────────────────────────────────────────────────────────────


def _rapport(
    sessie,
    monkeypatch,
    conclusie: str = "De UU heeft 128.000 inschrijvingen.",
    beurten=None,
    lees=(_UU, _CBS),
):
    """Draai `generate` met een nagebootste rapportlus; geeft het rapport en wat de lus zag.

    De lus bevraagt de keys in `lees`, ook een die de gebruiker uitzette: een model dat zo'n key raadt, mag er
    niets mee in het rapport krijgen."""
    gezien: dict = {}

    async def lus(messages, *, check, on_tool_result, **_):
        gezien["prompt"] = messages[0]["content"]
        gezien["scope"] = store.eigen_keys()
        for key in lees:
            args = {"data_key": key}
            call = ToolCall(id=key, name=TOOL_QUERY_DATA, arguments=json.dumps(args), args=args)
            await on_tool_result(call, json.dumps({"data_key": key, "rijen": []}), None)
        tekst = json.dumps({**json.loads(_ANTWOORD), "conclusie": conclusie})
        gezien["problemen"] = check(tekst, [])
        return LoopResult(text=tekst)

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", lus)
    with store.gesprek(lambda: sessie["data_keys"]):
        spec = asyncio.run(report.generate(sessie, stil, beurten=beurten))
    return spec, gezien


def _datasets_in(spec) -> set[str]:
    return {d["dataset"] for d in spec.manifest["data_as_of"]}


def test_zonder_selectie_ziet_het_rapport_het_hele_gesprek(sessie, monkeypatch):
    spec, gezien = _rapport(sessie, monkeypatch)

    assert _V2 in gezien["prompt"] and _CBS in gezien["prompt"]
    assert any("83285NED" in b for b in spec.bronnen)
    assert _datasets_in(spec) == {"p01hoinges", "83285NED"}


def test_een_uitgezette_beurt_komt_nergens_in_het_rapport_terug(sessie, monkeypatch):
    spec, gezien = _rapport(sessie, monkeypatch, beurten=frozenset({1, 3}))

    prompt = gezien["prompt"]
    assert _V2 not in prompt and _CBS not in prompt and "83285NED" not in prompt
    assert f"1. {_V1}" in prompt and f"2. {_V3}" in prompt
    # De vraagnummers volgen de overgebleven vragen.
    assert f"### {_VROUW}\n- Rijen: 5\n- Ontstaan bij vraag: 2\n" in prompt
    assert not any("83285NED" in b for b in spec.bronnen) and any("p01hoinges" in b for b in spec.bronnen)
    assert len(spec.bronnen) == 1
    assert _datasets_in(spec) == {"p01hoinges"}
    assert "83285NED" not in json.dumps(spec.to_dict())


def test_een_uitgezette_beurt_is_ook_niet_te_zien_aan_wat_een_tool_beschikbaar_noemt(sessie, monkeypatch):
    _, gezien = _rapport(sessie, monkeypatch, beurten=frozenset({1, 3}))

    assert gezien["scope"] == [_UU, _VROUW]


def test_zonder_beurt_1_noemt_het_rapport_de_bron_van_beurt_3_en_niet_die_van_de_zijsprong(sessie, monkeypatch):
    spec, gezien = _rapport(sessie, monkeypatch, beurten=frozenset({3}))

    assert _V1 not in gezien["prompt"] and _V3 in gezien["prompt"]
    assert _datasets_in(spec) == {"p01hoinges"} and any("p01hoinges" in b for b in spec.bronnen)


def test_het_onderwerp_is_de_eerste_vraag_die_overblijft(sessie, monkeypatch):
    """Zonder bevestigde onderzoeksvraag is de eerste vraag het onderwerp, dus de titel: niet een die de gebruiker
    uitzette."""
    antwoord = json.loads(_ANTWOORD)
    antwoord["onderzoeksvraag"] = ""  # het model formuleert niets: de vraag van de gebruiker is de terugval

    async def lus(messages, **_):
        return LoopResult(text=json.dumps(antwoord))

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", lus)
    spec = asyncio.run(report.generate(sessie, stil, beurten=frozenset({2, 3})))

    assert spec.onderzoeksvraag == _V2 and _V1 not in json.dumps(spec.to_dict())


def test_het_rekenbewijs_van_een_uitgezette_beurt_dekt_geen_getal_in_het_rapport(sessie, monkeypatch):
    """Percentage-toets (#872) en getalcontrole (#754): een +8 % uit de uitgezette zijsprong is geen bewijs meer."""
    conclusie = "De UU heeft 128.000 inschrijvingen; het wo-rendement groeide met +8 % van 2021 tot 2025."

    _, aan = _rapport(sessie, monkeypatch, conclusie, beurten=None)
    _, uit = _rapport(sessie, monkeypatch, conclusie, beurten=frozenset({1, 3}))

    assert aan["problemen"] == []
    assert any("8 %" in str(p) for p in uit["problemen"])


def test_een_rapport_dat_alleen_op_uitgezet_bewijs_rust_wordt_geweigerd(sessie, monkeypatch):
    conclusie = "De UU heeft 128.000 inschrijvingen; het wo-rendement groeide met +8 % van 2021 tot 2025."

    async def lus(messages, *, check, **_):
        tekst = json.dumps({**json.loads(_ANTWOORD), "conclusie": conclusie})
        return LoopResult(text=tekst, problems=check(tekst, []))

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", lus)
    with pytest.raises(RapportGeweigerd):
        asyncio.run(report.generate(sessie, stil, beurten=frozenset({1, 3})))


def test_de_dataversie_van_het_rapport_noemt_geen_uitgezette_bron(sessie, monkeypatch):
    spec, _ = _rapport(sessie, monkeypatch, beurten=frozenset({2}))

    assert _datasets_in(spec) == {"83285NED"}
