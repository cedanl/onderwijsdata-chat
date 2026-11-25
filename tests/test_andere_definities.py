"""Andere definities onder een vaste maat (#1256): hetzelfde getal onder de gangbare andere keuze, uit code.

"Hoeveel mbo-studenten waren er in 2024/25?" telt CBS 85354NED incl. extranei (475.460); zonder extranei is het 465.820.
Beide kloppen. Onder het antwoord zet code de regel "**Andere definities:**" met beide getallen, elk uit een eigen
get_maat-stap die code zette; het model kiest er niets van. Onder de drempel (1%) de vaste zin zonder getallen.

De bron is een fixture (`tools.cbs.data` filtert op de `$filter` zoals CBS, `tests/cbs_feed.py`); de catalogus is echt.
"""

import asyncio
import importlib
import json
from unittest.mock import patch

import pytest

from agent import controlestappen
from agent.citaties import citaties
from agent.controles import maak_getalcontrole
from agent.history import zonder_vaste_blokken
from agent.loop import LoopResult
from agent.onder_antwoord import KOP_DEFINITIES
from agent.session_data import rekenbewijs
from tests.cbs_feed import maak_feed
from tools import andere_definities, cbs_standaard, maten, store
from tools.maten import MATEN, MBO_STUDENTEN_LANDELIJK, get_maat
from tools.schemas import TOOL_GET_MAAT

_INCL, _EXCL, _BOL, _BBL = "A025290", "A041867", "A041868", "A025293"
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
        {"Key": _BOL, "Title": "Bol totaal"},
        {"Key": _BBL, "Title": "Bbl totaal"},
    ],
    "Perioden": [{"Key": "2024SJ00", "Title": "2024/'25", "Status": "Definitief"}],
}
# De live waarden van 29-10-2026 (CBS 85354NED, elke andere dimensie op haar totaal; tests/test_maten_ijk.py).
_WAARDEN = {_INCL: 475460, _EXCL: 465820, _BOL: 328610, _BBL: 137220}


def _feed(waarden: dict[str, int]):
    rijen = [
        {**_VAST, "Leerweg": leerweg, "Perioden": "2024SJ00", "MboStudenten_1": waarde}
        for leerweg, waarde in waarden.items()
    ]
    return maak_feed(rijen)


@pytest.fixture
def bron():
    """CBS 85354NED in het klein; de waarden zijn per test te vervangen (`bron(waarden)`)."""
    store.clear()
    feed = {"f": _feed(_WAARDEN)}
    with (
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=lambda dataset_id, endpoint, **_: _LABELS.get(endpoint, [])),
        patch("tools.cbs.data", side_effect=lambda *a, **k: feed["f"](*a, **k)),
        # Geen kruiscontrole in deze tests: die staat in test_kruiscontrole.py.
        patch("tools.bronparen.paren", return_value=()),
    ):

        def zet(waarden: dict[str, int]):
            store.clear()
            feed["f"] = _feed(waarden)

        yield zet
    store.clear()


def _hoofdstap() -> tuple[str, str]:
    with cbs_standaard.gesprek([_VRAAG]):
        return TOOL_GET_MAAT, get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"])


def _controles(stap: tuple[str, str], vragen: tuple[str, ...] = (_VRAAG,)) -> tuple[controlestappen.Controles, list]:
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    async def draai():
        with cbs_standaard.gesprek(list(vragen)):
            return await controlestappen.voer_uit([stap], emit)

    return asyncio.run(draai()), events


# --- 1. de tabel: elke maat met een definitiekeuze, elk alternatief met uitleg en recept ----------------------------


def test_elke_maat_heeft_een_tot_drie_alternatieven_met_uitleg():
    assert set(andere_definities.ALTERNATIEVEN) == set(MATEN)
    for maat, alternatieven in andere_definities.ALTERNATIEVEN.items():
        assert 1 <= len(alternatieven) <= 3, maat
        for alternatief in alternatieven:
            assert alternatief.naam and alternatief.uitleg and "\n" not in alternatief.uitleg, (maat, alternatief)


# Een afbakening per maat waarop het recept van elk alternatief te plannen is.
_AFBAKENING = {
    maten.PERSONEN_HO: {"instelling": "Hogeschool Utrecht"},
    maten.INSCHRIJVINGEN_HO: {"instelling": "Hogeschool Utrecht"},
    maten.EERSTEJAARS_HO: {"instelling": "Hogeschool Utrecht"},
    maten.DEELNEMERS_HO_LANDELIJK: {"sector": "hbo"},
    maten.MBO_STUDENTEN: {"instelling": "ROC Mondriaan"},
    maten.MBO_STUDENTEN_LANDELIJK: {},
    maten.DOORSTROOM_VMBO_MBO: {},
}
_REGISTER = {
    "hogeschool utrecht": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
    "roc mondriaan": {"naam": "ROC Mondriaan", "sector": "mbo", "instellingscode": "27GZ"},
}


@pytest.mark.parametrize(
    ("maat", "alternatief"),
    [(maat, a) for maat, alternatieven in andere_definities.ALTERNATIEVEN.items() for a in alternatieven],
    ids=lambda x: x if isinstance(x, str) else x.naam,
)
def test_elk_alternatief_heeft_een_recept_dat_get_maat_kan_plannen(maat, alternatief):
    """Faalt zodra een alternatief geen recept heeft: geen argumenten, of argumenten die get_maat niet plant."""
    assert alternatief.recept, f"{maat}: {alternatief.naam} heeft geen recept"
    args = {"maat": maat, **_AFBAKENING[maat], **alternatief.recept}
    with (
        patch("tools.maten.instellingen.instellingsprofiel", side_effect=lambda n: _REGISTER.get(n.strip().lower())),
        patch(
            "tools.maten.tabelbestanden",
            return_value=[(0, "instelling en leerweg"), (3, "hoger beroepsonderwijs opleidingsvorm")],
        ),
        maten.codestap(),
    ):
        uitkomst = maten.plan(**args)
    assert isinstance(uitkomst, maten.Plan), uitkomst


def test_het_model_kiest_de_telling_zonder_extranei_niet_zelf(bron):
    # De interne vormen zijn voor code (#653): het model krijgt een melding, en het schema noemt ze niet.
    uitkomst = get_maat(MBO_STUDENTEN_LANDELIJK, vorm=maten.ZONDER_EXTRANEI, schooljaren=["2024/25"])
    assert isinstance(uitkomst, str) and "kiest de app zelf" in uitkomst
    assert not set(maten.INTERNE_VORMEN) & set(maten.vormen(MATEN[MBO_STUDENTEN_LANDELIJK]))


# --- 2 en 3. de regel bij mbo-studenten landelijk 2024/25, uit code ----------------------------------------------------


def test_de_regel_noemt_het_cbs_getal_met_en_zonder_extranei(bron):
    controles, events = _controles(_hoofdstap())

    (regel,) = controles.regels()
    assert regel.startswith(KOP_DEFINITIES)
    assert "475.460" in regel and "zonder extranei 465.820" in regel and "-2,0%" in regel and "2024/25" in regel
    # De stap staat in de redeneerkaart, met een eigen label: code zette haar, niet het model.
    starts = [e for e in events if e["type"] == "tool_start"]
    assert [e["label"] for e in starts] == [f"{controlestappen.LABEL_DEFINITIE}: zonder extranei"]
    assert starts[0]["input"]["vorm"] == maten.ZONDER_EXTRANEI


def test_beide_getallen_gaan_door_de_getalcontrole_en_hebben_een_citatie(bron):
    hoofd = _hoofdstap()
    controles, _ = _controles(hoofd)
    (regel,) = controles.regels()
    tekst = f"In 2024/25 waren er 475.460 mbo-studenten.\n\n{regel}"
    stappen = [hoofd, *controles.stappen]

    controle = maak_getalcontrole([], [_VRAAG])
    assert controle(tekst, [r for _, r in stappen]) == []
    gevonden = {c["getal"]: c for c in citaties(tekst, stappen)}
    assert gevonden["465.820"]["vastgesteld"] and gevonden["465.820"]["stap"] == 2
    assert gevonden["475.460"]["vastgesteld"]
    (alternatief,) = controles.definities[0].uitkomsten
    assert gevonden["465.820"]["data_key"] == alternatief.data_key != json.loads(hoofd[1])["data_key"]


def test_de_stripgetallen_zijn_die_van_een_losse_get_maat_aanroep_met_het_alternatieve_recept(bron):
    controles, _ = _controles(_hoofdstap())
    (definitie,) = controles.definities
    (zonder,) = definitie.uitkomsten

    with maten.codestap():
        los = json.loads(get_maat(MBO_STUDENTEN_LANDELIJK, vorm=maten.ZONDER_EXTRANEI, schooljaren=["2024/25"]))
    # En dezelfde telling als een gesprek dat extranei zelf uitsluit (#653): één definitie, twee wegen.
    with cbs_standaard.gesprek([_VRAAG, "En zonder extranei?"]):
        gesprek = json.loads(get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"]))
    assert zonder.waarde == los["rijen"][0]["MboStudenten_1"] == gesprek["rijen"][0]["MboStudenten_1"] == 465820
    assert definitie.hoofd.waarde == 475460


def test_een_stripgetal_in_de_modeltekst_zonder_toolstap_faalt_de_getalcontrole(bron):
    hoofd = _hoofdstap()
    controle = maak_getalcontrole([], [_VRAAG])

    problemen = controle("Zonder extranei waren het er 465.820.", [hoofd[1]])
    assert [p.getal for p in problemen] == ["465.820"]


def test_een_gesprek_zonder_extranei_krijgt_de_telling_met_extranei_als_alternatief(bron):
    vragen = (_VRAAG, "En zonder extranei?")
    with cbs_standaard.gesprek(list(vragen)):
        hoofd = (TOOL_GET_MAAT, get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"]))
    controles, _ = _controles(hoofd, vragen)

    (regel,) = controles.regels()
    assert "telt dit antwoord 465.820" in regel and "met extranei 475.460 (+2,1%)" in regel


# --- 4. onder de drempel: de vaste zin, zonder getallen ---------------------------------------------------------------


def test_onder_de_drempel_de_vaste_zin_zonder_getallen(bron):
    bron({**_WAARDEN, _EXCL: 474000})  # 0,3% minder: onder de drempel van 1%
    controles, _ = _controles(_hoofdstap())

    (regel,) = controles.regels()
    assert regel == f"{KOP_DEFINITIES} {controlestappen.HETZELFDE_BEELD} (zonder extranei)."
    assert not any(teken.isdigit() for teken in regel)


def test_een_alternatief_zonder_waarde_geeft_geen_regel(bron):
    bron({_INCL: 475460})  # de bron heeft de telling zonder extranei niet
    controles, _ = _controles(_hoofdstap())

    assert controles.regels() == [] and controles.bewijs() == []


# --- 5. in het antwoord, de historie, het bewijs, het rapport -----------------------------------------------------


def test_run_zet_de_regel_onder_het_antwoord_met_citaties_en_bewijs(bron, zonder_scopekaart):
    run_module = importlib.import_module("agent.run")
    hoofd = _hoofdstap()
    resultaat = LoopResult(
        text="In 2024/25 waren er 475.460 mbo-studenten.",
        steps=[hoofd],
        tool_calls=[{"name": TOOL_GET_MAAT, "arguments": {"maat": MBO_STUDENTEN_LANDELIJK}}],
    )
    events: list[dict] = []

    async def nep_loop(history, **kwargs):
        return resultaat

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

    assert tekst.rstrip().splitlines()[-1].startswith(KOP_DEFINITIES) and tekst.count(KOP_DEFINITIES) == 1
    (einde,) = [e for e in events if e["type"] == "message_end"]
    assert einde["content"] == tekst
    assert any(c["getal"] == "465.820" and c["vastgesteld"] for c in einde["citaties"])
    # Het bewijs (#1244): de regel en haar getallen, op de key van het hoofdgetal.
    (bewijs,) = [b for b in rekenbewijs(session) if b["tool"] == controlestappen.BEWIJS_DEFINITIES]
    inhoud = json.loads(bewijs["resultaat"])
    assert inhoud["regel"] in tekst and inhoud["data_key"] == json.loads(hoofd[1])["data_key"]
    # De historie naar het model houdt de regel niet: het model schrijft haar nooit over.
    assert KOP_DEFINITIES not in zonder_vaste_blokken({"role": "assistant", "content": tekst})["content"]


def test_een_regel_die_het_model_overnam_vervalt(bron):
    controles, _ = _controles(_hoofdstap())
    (regel,) = controles.regels()

    tekst = controlestappen.met_regels(f"Er waren 475.460 studenten.\n{KOP_DEFINITIES} eigen tekst 1.234.", controles)
    assert tekst == f"Er waren 475.460 studenten.\n\n{regel}"
    leeg = controlestappen.Controles()
    assert controlestappen.met_regels(f"Tekst.\n\n{KOP_DEFINITIES} eigen tekst.", leeg) == "Tekst."


def test_het_rapport_neemt_de_regel_uit_het_bewijs_over(bron):
    controles, _ = _controles(_hoofdstap())
    (regel,) = controles.regels()

    (item,) = controlestappen.rapportdefinities(controles.bewijs())
    assert item == {"begrip": "Andere definities", "definitie": regel.removeprefix(KOP_DEFINITIES).strip()}
    assert controlestappen.rapportdefinities([{"tool": "compute_kpi", "resultaat": "{}"}]) == []
