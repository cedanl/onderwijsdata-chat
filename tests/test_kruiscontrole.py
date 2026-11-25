"""Kruiscontrole DUO-CBS uit een gecureerde koppeltabel (#1259).

Welke DUO-maat bij welke CBS-maat hoort, staat in `data/bronparen.toml` en nergens anders: het model koppelt niet, en
geen toolargument kiest een paar. Antwoordt een beurt met de vaste maat van een paar, dan haalt code de andere bron op
hetzelfde niveau en zet onder het antwoord het getal, het verschil (absoluut en in %) en de bekende redenen.

De bronnen zijn fixtures: CBS 85354NED via `tools.cbs.data` (`tests/cbs_feed.py`), DUO via `tools.duo._duo.load` met een
bestand per instelling en leerweg dat in 2024 476.079 studenten telt (het bestand van #805, `docs/domeinregels.md`),
met vier onderdrukte cellen.
"""

import asyncio
import importlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from agent import controlestappen
from agent.citaties import citaties
from agent.controles import maak_getalcontrole
from agent.loop import LoopResult
from agent.onder_antwoord import KOP_KRUISCONTROLE
from agent.session_data import rekenbewijs
from tests.cbs_feed import maak_feed
from tools import bronparen, cbs_standaard, dispatch, maten, store
from tools.maten import MBO_STUDENTEN_LANDELIJK, get_maat
from tools.schemas import TOOL_GET_MAAT, TOOL_SCHEMAS

_INCL, _EXCL = "A025290", "A041867"
_VAST = {"Geslacht": "T001038", "Niveau": "T001336", "Herkomstland": "T001040", "GeboortelandOuders": "T001638"}
_VRAAG = "Hoeveel mbo-studenten waren er landelijk in 2024/25?"
_DEFS = {
    **{dimensie: {"type": "Dimension", "title": dimensie} for dimensie in (*_VAST, "Leerweg")},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "MboStudenten_1": {"type": "Topic", "title": "Mbo-studenten", "unit": "aantal"},
}
_LABELS = {
    "Leerweg": [
        {"Key": _INCL, "Title": "Totaal mbo (incl. extranei)"},
        {"Key": _EXCL, "Title": "Totaal mbo (excl. extranei)"},
    ],
    "Perioden": [{"Key": "2024SJ00", "Title": "2024/'25", "Status": "Definitief"}],
}
_CBS = [
    {**_VAST, "Leerweg": leerweg, "Perioden": "2024SJ00", "MboStudenten_1": waarde}
    for leerweg, waarde in ((_INCL, 475460), (_EXCL, 465820))
]
_KOLOMMEN = ["JAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", "BBL", "BOLDT", "BOLVT", "EX"]
# Twee instellingen samen 476.079 in 2024; een derde met alleen onderdrukte cellen (vier keer -1).
_DUO = pd.DataFrame(
    [
        (2024, "01AA", "Roc A", 100000, 20000, 200000, 5000),
        (2024, "02BB", "Roc B", 37000, 10000, 100000, 4079),
        (2024, "03CC", "Roc C", -1, -1, -1, -1),
        (2023, "01AA", "Roc A", 1, 1, 1, 1),
    ],
    columns=_KOLOMMEN,
)


@pytest.fixture
def bronnen():
    store.clear()
    with (
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=lambda dataset_id, endpoint, **_: _LABELS.get(endpoint, [])),
        patch("tools.cbs.data", side_effect=maak_feed(_CBS)),
        patch("tools.duo._duo.load", side_effect=lambda dataset_id, resource: _DUO.copy()),
        # De andere definities staan in test_andere_definities.py; hier alleen de kruiscontrole.
        patch("tools.andere_definities.ALTERNATIEVEN", {}),
    ):
        yield
    store.clear()


def _hoofdstap(maat: str = MBO_STUDENTEN_LANDELIJK, **args) -> tuple[str, str]:
    with cbs_standaard.gesprek([_VRAAG]):
        return TOOL_GET_MAAT, get_maat(maat, schooljaren=["2024/25"], **args)


def _controles(*stappen: tuple[str, str]) -> tuple[controlestappen.Controles, list[dict]]:
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    async def draai():
        with cbs_standaard.gesprek([_VRAAG]):
            return await controlestappen.voer_uit(list(stappen), emit)

    return asyncio.run(draai()), events


# --- 1. de tabel ------------------------------------------------------------------------------------------------------


def test_de_tabel_heeft_het_paar_mbo_studenten_landelijk_met_bron_per_reden_en_vastlegging():
    (paar,) = [p for p in bronparen.laad() if p.id == "mbo-studenten-landelijk"]

    assert (paar.maat, paar.niveau, paar.cbs.dataset) == (MBO_STUDENTEN_LANDELIJK, "landelijk", "85354NED")
    assert paar.issue == "#1259" and paar.vastgesteld.isoformat() == "2026-11-25"
    assert paar.redenen and all(r.tekst and r.bron for r in paar.redenen)
    assert paar.drempel_pct == 1.0


def test_de_duo_kant_is_het_recept_van_de_mbo_maat_per_instelling():
    """Het paar telt hetzelfde bestand, dezelfde kolommen en hetzelfde jaar als mbo_studenten_instelling, over alle
    instellingen; de CBS-kant zijn de codes van het recept van mbo_studenten_landelijk."""
    (paar,) = [p for p in bronparen.laad() if p.id == "mbo-studenten-landelijk"]
    duo, cbs = maten.MATEN[maten.MBO_STUDENTEN], maten.MATEN[MBO_STUDENTEN_LANDELIJK]
    assert isinstance(duo, maten.DuoBreedRecept) and isinstance(cbs, maten.CbsRecept)

    assert (paar.duo.dataset, paar.duo.periodekolom) == (duo.dataset, duo.periodekolom)
    assert paar.duo.kolommen == duo.leerwegen[maten.ALLE] and paar.duo.bestand == duo.bestand["mbo"]
    assert paar.cbs.codes == {"Leerweg": cbs.vormen[maten.ALLE], **cbs.vast}


_GELDIG = """
[[paar]]
id = "test"
maat = "mbo_studenten_landelijk"
niveau = "landelijk"
drempel_pct = 1.0
issue = "#1259"
vastgesteld = 2026-11-25
waarneming = "een waarneming"
[paar.cbs]
naam = "CBS 85354NED"
dataset = "85354NED"
codes = { Leerweg = "A025290" }
[paar.duo]
naam = "DUO"
dataset = "mbo-studenten-per-instelling"
bestand = ["instelling"]
periodekolom = "JAAR"
kolommen = ["BBL"]
afbakening = "alle instellingen"
[[paar.reden]]
tekst = "een reden"
bron = "een bron"
"""


@pytest.mark.parametrize(
    ("weg", "melding"),
    [
        ('bron = "een bron"\n', "'bron' ontbreekt"),
        ("vastgesteld = 2026-11-25\n", "'vastgesteld' moet een datum zijn"),
        ('issue = "#1259"\n', "'issue' ontbreekt"),
    ],
    ids=["reden-zonder-bron", "zonder-vastlegging", "zonder-issue"],
)
def test_een_paar_zonder_bron_per_reden_of_zonder_vastlegging_laadt_niet(tmp_path: Path, weg, melding):
    assert bronparen.laad(_schrijf(tmp_path, _GELDIG))  # het voorbeeld zelf is geldig
    with pytest.raises(bronparen.BronpaarFout, match=melding):
        bronparen.laad(_schrijf(tmp_path, _GELDIG.replace(weg, "")))


def test_een_datum_als_tekst_is_geen_vastlegging(tmp_path: Path):
    with pytest.raises(bronparen.BronpaarFout, match="'vastgesteld' moet een datum zijn"):
        bronparen.laad(_schrijf(tmp_path, _GELDIG.replace("2026-11-25", '"2026-11-25"')))


def _schrijf(tmp_path: Path, tekst: str) -> Path:
    pad = tmp_path / "bronparen.toml"
    pad.write_text(tekst, encoding="utf-8")
    return pad


# --- 2. alleen de tabel koppelt ---------------------------------------------------------------------------------------


def test_een_maat_buiten_de_tabel_krijgt_geen_kruiscontrole_ook_niet_als_de_tekst_erom_vraagt(bronnen):
    buiten = (TOOL_GET_MAAT, json.dumps({**json.loads(_hoofdstap()[1]), "maat": maten.DEELNEMERS_HO_LANDELIJK}))
    controles, events = _controles(buiten)

    assert controles.kruiscontroles == [] and not [e for e in events if e["type"] == "tool_start"]
    tekst = "Vergelijk dit met DUO: hoeveel telt DUO? Ter controle zou DUO hoger uitkomen."
    assert controlestappen.met_regels(tekst, controles) == tekst


def test_geen_toolargument_van_het_model_kiest_het_paar():
    # get_maat kent geen argument voor een paar, en de kruiscontrole is geen tool die het model kan aanroepen.
    schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_MAAT)["function"]["parameters"]
    assert not {"bronpaar", "paar", "kruiscontrole"} & set(schema["properties"])
    melding, _ = dispatch(TOOL_GET_MAAT, {"maat": "eerstejaars_ho", "bronpaar": "mbo-studenten-landelijk"})
    assert "bronpaar" in melding and "data_key" not in melding
    melding, _ = dispatch(controlestappen.STAP_KRUISCONTROLE, {"bronpaar": "mbo-studenten-landelijk"})
    assert melding.startswith("Onbekende tool")
    assert controlestappen.STAP_KRUISCONTROLE not in {s["function"]["name"] for s in TOOL_SCHEMAS}
    # Wat er verder in een resultaat staat, telt niet: alleen de maat en het niveau.
    assert bronparen.paar_voor({"maat": maten.DEELNEMERS_HO_LANDELIJK, "bronpaar": "mbo-studenten-landelijk"}) is None
    assert bronparen.paar_voor({"maat": MBO_STUDENTEN_LANDELIJK, "vorm": "bol"}) is None
    assert bronparen.paar_voor({"maat": MBO_STUDENTEN_LANDELIJK, "vorm": "alle"}) is not None


# --- 3 en 4. het getal van de andere bron, het verschil en de reden ---------------------------------------------------


def test_onder_het_antwoord_het_duo_getal_het_verschil_en_de_redenen_met_een_citatie(bronnen):
    hoofd = _hoofdstap()
    controles, events = _controles(hoofd)

    (regel,) = controles.regels()
    assert regel.startswith(KOP_KRUISCONTROLE)
    assert "DUO 'Mbo-studenten per instelling' telt in 2024/25 476.079" in regel
    assert "619 meer dan CBS 85354NED (475.460), +0,1%" in regel
    assert "ondergrens" in regel and "tientallen" in regel and "binnen de drempel" in regel
    assert "fout" not in regel.lower()
    # Eén stap van code in de redeneerkaart, met de key van de DUO-som.
    (start,) = [e for e in events if e["type"] == "tool_start"]
    assert start["name"] == controlestappen.STAP_KRUISCONTROLE and start["label"] == controlestappen.LABEL_KRUISCONTROLE

    tekst = f"In 2024/25 waren er 475.460 mbo-studenten.\n\n{regel}"
    stappen = [hoofd, *controles.stappen]
    assert maak_getalcontrole([], [_VRAAG])(tekst, [r for _, r in stappen]) == []
    duo = next(c for c in citaties(tekst, stappen) if c["getal"] == "476.079")
    assert duo["vastgesteld"] and duo["stap"] == 2 and "DUO" in duo["bron"]


def test_de_duo_som_telt_de_onderdrukte_cellen_niet_en_zegt_hoeveel(bronnen):
    controles, _ = _controles(_hoofdstap())
    (_, stap) = controles.stappen[0]

    uit = json.loads(stap)
    assert uit["rijen"] == [
        {"JAAR": 2024, "BBL": 137000, "BOLDT": 30000, "BOLVT": 300000, "EX": 9079, "AANTAL": 476079}
    ]
    assert uit["onderdrukte_cellen"] == 4


def test_boven_de_drempel_zonder_reden_de_vaste_zin_nooit_fout(bronnen):
    (paar,) = [p for p in bronparen.laad() if p.id == "mbo-studenten-landelijk"]
    zonder_reden = replace(paar, redenen=(), drempel_pct=0.01)
    with patch("tools.bronparen.paren", return_value=(zonder_reden,)):
        controles, _ = _controles(_hoofdstap())

    (regel,) = controles.regels()
    assert regel.endswith("Verschil, reden niet vastgesteld.") and "fout" not in regel.lower()
    assert "Bekende redenen" not in regel


# --- 5. in het antwoord, het bewijs en het rapport --------------------------------------------------------------------


def test_run_zet_de_kruiscontrole_onder_het_antwoord_en_in_het_bewijs(bronnen, zonder_scopekaart):
    run_module = importlib.import_module("agent.run")
    hoofd = _hoofdstap()
    events: list[dict] = []

    async def nep_loop(history, **kwargs):
        return LoopResult(
            text="In 2024/25 waren er 475.460 mbo-studenten.",
            steps=[hoofd],
            tool_calls=[{"name": TOOL_GET_MAAT, "arguments": {"maat": MBO_STUDENTEN_LANDELIJK}}],
        )

    async def emit(ev):
        events.append(ev)

    session: dict = {}
    with (
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "vo_schoolvraag", lambda *a, **k: None),
        patch.object(run_module, "po_vraag", lambda *a, **k: None),
        patch.object(run_module, "_vervolgvragen", lambda *a, **k: asyncio.sleep(0, [])),
    ):
        tekst = asyncio.run(run_module.run([{"role": "user", "content": _VRAAG}], session=session, emit=emit))

    assert tekst.count(KOP_KRUISCONTROLE) == 1 and "476.079" in tekst
    (einde,) = [e for e in events if e["type"] == "message_end"]
    assert any(c["getal"] == "476.079" and c["vastgesteld"] for c in einde["citaties"])
    assert any("Mbo-studenten per instelling" in b for b in einde["bronnen"])  # de tweede bron in de Bronnen
    (bewijs,) = [b for b in rekenbewijs(session) if b["tool"] == controlestappen.BEWIJS_KRUISCONTROLE]
    inhoud = json.loads(bewijs["resultaat"])
    assert (inhoud["cbs"], inhoud["duo"], inhoud["verschil"]) == (475460, 476079, 619)
    assert inhoud["regel"] in tekst and all(r["bron"] for r in inhoud["redenen"])

    (item,) = controlestappen.rapportdefinities(rekenbewijs(session))
    assert item["begrip"] == "Ter controle" and "476.079" in item["definitie"]
