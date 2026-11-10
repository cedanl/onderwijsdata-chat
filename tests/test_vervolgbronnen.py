"""Review 08 (#975): de bronregel bij een vervolgantwoord, en na "niet in deze bron" alleen aanbieden.

- 08-C2 (R09): na een analyse op de Studiekeuzedatabase vroeg de gebruiker welke sleutels de koppeling gebruikte. Het
  antwoord besprak de analyse en noemde LCSK, maar de beurt riep geen tool aan: `bronnen` was leeg, zonder versie en
  zonder de verplichte zin van LCSK. Nu krijgt zo'n antwoord de bronregels van de eerder geladen data die het noemt.
- N08 (reaudit 10-11, #986): na een koppeling van beide noemde het vervolgantwoord "NSE-oordeel, BRIN en DUO" en niet
  de Studiekeuzedatabase zelf: de LCSK-regel viel weg. Een koppeling telt nu als geheel, ook als de store een van haar
  tabellen intussen kwijt is.
- 08-B7 (R11): na de melding dat de Studiekeuzedatabase geen mbo heeft, haalde het model ongevraagd DUO-indicatoren
  op. De melding zegt nu zelf: de beperking noemen, een andere maat hooguit aanbieden, pas ophalen na instemming.

Er staat geen data van LCSK in de repo: `onderwijsbronnen.skdb.proefbestand` bouwt een export met dezelfde vorm.
"""

import asyncio
import importlib
import json
from pathlib import Path

import pandas as pd
import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from agent import beurtbewijs
from agent.bronvermelding import vervolgbronnen
from agent.session_data import vorige_databeurt
from agent.stream import StreamResult
from data import instellingen
from routes import chat
from routes import persistence as put_route
from tools import mbo_indicatoren, store, studiekeuze, wo_personeel
from tools.buiten_de_bron import ALLEEN_AANBIEDEN
from tools.schemas import TOOL_GET_DUO_DATA, TOOL_GET_STUDIEKEUZE, TOOL_RUN_ANALYSIS
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

SYSTEM = (Path(__file__).resolve().parent.parent / "prompts" / "system.md").read_text(encoding="utf-8")

_DUO_KEY = "duo:p01hoinges:0"
_KOPPEL_KEY = "analyse:hu-ict-met-duo"
_PROFIELEN = {
    "hogeschool utrecht": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
    "roc van amsterdam": {"naam": "ROC van Amsterdam", "sector": "mbo", "instellingscode": "25LX"},
}


@pytest.fixture(autouse=True)
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(" ".join(naam.split()).lower()))
    store.put(
        _DUO_KEY,
        pd.DataFrame({"STUDIEJAAR": [2023], "AANTAL": [120]}),
        KeyMeta(bron="duo", dataset="p01hoinges", schooljaren=(2023,)),
    )
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


def _dispatch(name, args):
    if name == TOOL_GET_STUDIEKEUZE:
        return studiekeuze.get_studiekeuze(**args), None
    if name == TOOL_RUN_ANALYSIS:
        # Zoals run_analysis een koppeling teruggeeft: haar key en elke tabel die het script las.
        koppeling = store.meta(_KOPPEL_KEY)
        gelezen = list(koppeling.gelezen or ()) if koppeling else []
        rijen = store.get(_KOPPEL_KEY).to_dict("records")
        return json.dumps({"data_key": _KOPPEL_KEY, "gelezen": gelezen, "resultaat": rijen}), None
    assert name == TOOL_GET_DUO_DATA
    return json.dumps({"data_key": _DUO_KEY, "rijen": [{"STUDIEJAAR": 2023, "AANTAL": 120}]}), None


def _beurt(monkeypatch, vraag: str, stappen: list[StreamResult], session: dict) -> tuple[dict, list[list[dict]]]:
    """Eén chatbeurt met een nagebootst model, zoals de chatroute hem draait: de sessie houdt de berichten bij.

    Geeft het message_end-event en de berichten die het model per ronde kreeg."""
    gezien: list[list[dict]] = []

    async def fake_completion(*args, **kwargs):
        gezien.append(list(kwargs.get("messages") or []))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "dispatch", _dispatch)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    messages = session.setdefault("messages", [])
    messages.append({"role": "user", "content": vraag})
    antwoord = asyncio.run(run_module.run(messages, session, emit, asyncio.Event(), model="openai/gpt-4o"))
    messages.append({"role": "assistant", "content": antwoord})
    return next(e for e in reversed(events) if e["type"] == "message_end"), gezien


_HU_ICT = json.dumps({"weergave": "opleidingen", "instelling": "Hogeschool Utrecht", "opleiding": "30020"})
_DUO = json.dumps({"dataset_id": "p01hoinges"})


def _analyse(monkeypatch, session: dict) -> dict:
    """C1: een beurt die de Studiekeuzedatabase en DUO laadt."""
    stappen = [
        StreamResult(
            text="",
            tool_calls=[
                {"id": "s1", "name": TOOL_GET_STUDIEKEUZE, "arguments": _HU_ICT},
                {"id": "d1", "name": TOOL_GET_DUO_DATA, "arguments": _DUO},
            ],
        ),
        StreamResult(text="ICT bij de Hogeschool Utrecht, naast de inschrijvingen van DUO.", tool_calls=[]),
    ]
    einde, _ = _beurt(monkeypatch, "Vergelijk ICT bij de HU met de DUO-inschrijvingen.", stappen, session)
    return einde


def _lcsk_regel(bronnen: list[str]) -> str:
    return next(regel for regel in bronnen if skdb.VERPLICHTE_ZIN in regel)


_SLEUTELS = (
    "Ik koppelde de Studiekeuzedatabase van het Landelijk Centrum Studiekeuze aan de DUO-data via de BRIN-code en de "
    "CROHO-code van de opleiding."
)


def test_een_vervolgantwoord_zonder_tool_houdt_de_lcsk_regel_met_versie_en_zin(monkeypatch):
    """08-C2, van begin tot eind over twee beurten: de tweede beurt roept geen tool aan."""
    session: dict = {}
    eerste = _analyse(monkeypatch, session)
    assert any(skdb.VERPLICHTE_ZIN in regel for regel in eerste["bronnen"])

    einde, _ = _beurt(
        monkeypatch,
        "Welke sleutels heb je gebruikt om die twee te koppelen?",
        [StreamResult(text=_SLEUTELS, tool_calls=[])],
        session,
    )

    versie = proefbestand.standaard()[1].versie
    regel = _lcsk_regel(einde["bronnen"])
    assert f"versie {versie}" in regel
    assert skdb.DOCUMENTATIE in regel  # de link staat in de regel zelf, ook zonder catalogusrecord
    assert any("p01hoinges" in regel for regel in einde["bronnen"])  # het antwoord noemt DUO ook


def test_de_bronregel_blijft_ook_in_een_derde_beurt_die_erop_voortbouwt(monkeypatch):
    """De vorige beurt die data laadde is de context, ook met een beurt zonder data ertussen."""
    session: dict = {}
    _analyse(monkeypatch, session)
    _beurt(monkeypatch, "Dank je.", [StreamResult(text="Graag gedaan.", tool_calls=[])], session)

    einde, _ = _beurt(
        monkeypatch,
        "En welke versie van die bron was het?",
        [StreamResult(text="Dat was de export van de Studiekeuzedatabase.", tool_calls=[])],
        session,
    )

    assert _lcsk_regel(einde["bronnen"])
    assert not any("p01hoinges" in regel for regel in einde["bronnen"])  # DUO noemt het niet


def test_een_losse_vervolgvraag_zonder_bron_krijgt_geen_bronregel(monkeypatch):
    session: dict = {}
    _analyse(monkeypatch, session)

    einde, _ = _beurt(
        monkeypatch, "Bedankt, dat was duidelijk.", [StreamResult(text="Graag gedaan.", tool_calls=[])], session
    )

    assert einde["bronnen"] == []
    assert "bronlinks" not in einde


def test_zonder_eerdere_data_geen_bronregel(monkeypatch):
    einde, _ = _beurt(
        monkeypatch,
        "Wat is de Studiekeuzedatabase?",
        [StreamResult(text="De Studiekeuzedatabase is een bron van het LCSK.", tool_calls=[])],
        {},
    )

    assert einde["bronnen"] == []


def test_een_beurt_met_een_toolaanroep_leest_alleen_haar_eigen_stappen(monkeypatch):
    """Roept de beurt een tool aan, dan beslissen haar stappen: een melding zonder data krijgt geen oude regel."""
    session: dict = {}
    _analyse(monkeypatch, session)
    roc = json.dumps({"weergave": "opleidingen", "instelling": "ROC van Amsterdam"})

    einde, _ = _beurt(
        monkeypatch,
        "Hoe tevreden zijn studenten van ROC van Amsterdam over hun opleiding?",
        [
            StreamResult(text="", tool_calls=[{"id": "r1", "name": TOOL_GET_STUDIEKEUZE, "arguments": roc}]),
            StreamResult(text="De Studiekeuzedatabase heeft alleen hbo en wo.", tool_calls=[]),
        ],
        session,
    )

    assert einde["bronnen"] == []


def test_vorige_databeurt_is_de_laatste_eerdere_vraag_met_data():
    sessie = {
        "messages": [{"role": "user", "content": v} for v in ("a", "b", "c", "d")],
        "data_vraag": {"cbs:1": 1, "duo:2": 2, "duo:3": 2, "skdb:4": 4},
    }
    assert vorige_databeurt(sessie) == ["duo:2", "duo:3"]  # vraag 4 is de huidige
    assert vorige_databeurt({"messages": sessie["messages"]}) == []


@pytest.mark.parametrize(
    "tekst",
    [
        "Volgens het LCSK is dat zo.",
        "In de studiekeuzedatabase staat het per opleiding.",
        "De SKDB-tabel koppelt op BRIN.",
        "Het Landelijk Centrum Studiekeuze levert de data.",
    ],
)
def test_elke_naam_van_de_bron_telt(tekst):
    bronnen, _ = vervolgbronnen(tekst, [_skdb_proefkey()])
    assert len(bronnen) == 1 and skdb.VERPLICHTE_ZIN in bronnen[0]


def _skdb_proefkey() -> str:
    key = "skdb:opleidingen:proef"
    store.put(
        key,
        pd.DataFrame({"brin": ["25DW"]}),
        KeyMeta(bron="skdb", dataset=studiekeuze.DATASET, peilmoment=f"versie 26.6; {skdb.VERPLICHTE_ZIN}"),
    )
    return key


def test_een_woord_dat_een_naam_bevat_telt_niet():
    """Alleen hele woorden: "duo" in "duozitting" noemt DUO niet."""
    assert vervolgbronnen("Een duozitting met de decaan.", [_DUO_KEY]) == ([], {})


# --- N08 (#986): een koppeling is een geheel ---------------------------------------------------------------------------

_KOPPELVRAAG = (
    "Welke sleutels heb je gebruikt om die twee te koppelen? Antwoord kort op basis van je vorige antwoord, zonder nieuwe "
    "gegevens op te halen."
)
_KOPPELSLEUTELS = "Ik koppelde het NSE-oordeel aan de DUO-inschrijvingen via de BRIN-code en de opleiding CROHO 30020."


def _koppelbeurt(monkeypatch, session: dict) -> str:
    """Een databeurt waarvan de enige key een koppeling is: afgeleid van de DUO-tabel, met ook de Studiekeuzedatabase
    gelezen, zoals run_analysis haar afleidt. Geeft de key van de geladen SKDB-tabel."""
    skdb_key = json.loads(studiekeuze.get_studiekeuze(**json.loads(_HU_ICT)))["data_key"]
    koppeling = pd.DataFrame({"brin": ["25DW"], "croho": [30020], "STUDIEJAAR": [2023], "AANTAL": [120]})
    store.derive(_DUO_KEY, _KOPPEL_KEY, koppeling, gelezen=(_DUO_KEY, skdb_key), stap="koppeling op BRIN")
    analyse = json.dumps({"code": "resultaat = koppeling"})
    stappen = [
        StreamResult(text="", tool_calls=[{"id": "a1", "name": TOOL_RUN_ANALYSIS, "arguments": analyse}]),
        StreamResult(
            text="ICT (CROHO 30020) bij de Hogeschool Utrecht, gekoppeld aan de inschrijvingen.", tool_calls=[]
        ),
    ]
    _beurt(monkeypatch, "Koppel ICT bij de HU aan de DUO-inschrijvingen.", stappen, session)
    assert session["data_vraag"] == {_KOPPEL_KEY: 1}  # de koppeling is de enige key van die beurt
    return skdb_key


def _koppelantwoord(monkeypatch, session: dict, antwoord: str = _KOPPELSLEUTELS) -> dict:
    einde, _ = _beurt(monkeypatch, _KOPPELVRAAG, [StreamResult(text=antwoord, tool_calls=[])], session)
    return einde


def test_een_vervolgantwoord_over_een_koppeling_krijgt_de_regels_van_alle_bronnen(monkeypatch):
    """N08: het antwoord noemt NSE, BRIN, CROHO en DUO, niet de Studiekeuzedatabase; haar regel blijft."""
    assert not any(naam.lower() in _KOPPELSLEUTELS.lower() for naam in ("SKDB", "LCSK", "Studiekeuzedatabase"))
    session: dict = {}
    _koppelbeurt(monkeypatch, session)

    einde = _koppelantwoord(monkeypatch, session)

    regel = _lcsk_regel(einde["bronnen"])
    assert f"versie {proefbestand.standaard()[1].versie}" in regel
    assert skdb.DOCUMENTATIE in regel or skdb.DOCUMENTATIE in einde.get("bronlinks", {}).values()
    assert any("p01hoinges" in regel for regel in einde["bronnen"])
    assert len(einde["bronnen"]) == 2  # elke bron één keer


def test_de_regel_van_een_gekoppelde_bron_blijft_als_de_store_haar_kwijt_is(monkeypatch):
    """De SKDB-tabel is uit de store (boven STORE_MAX_MB), de koppeling niet: haar meta staat in de keten (#985)."""
    session: dict = {}
    skdb_key = _koppelbeurt(monkeypatch, session)
    store._verwijder(skdb_key, "test")
    assert store.meta(skdb_key) is None

    einde = _koppelantwoord(monkeypatch, session)

    regel = _lcsk_regel(einde["bronnen"])
    assert f"versie {proefbestand.standaard()[1].versie}" in regel
    assert skdb.DOCUMENTATIE in regel


def test_noemt_het_antwoord_alleen_de_studiekeuzedatabase_dan_komt_duo_van_de_koppeling_mee(monkeypatch):
    session: dict = {}
    _koppelbeurt(monkeypatch, session)

    einde = _koppelantwoord(monkeypatch, session, "Ik gebruikte het NSE-oordeel van de opleiding.")

    assert _lcsk_regel(einde["bronnen"])
    assert any("p01hoinges" in regel for regel in einde["bronnen"])


@pytest.mark.parametrize(
    "tekst",
    [
        "Het NSE-oordeel is hoog.",
        "Volgens de Nationale Studenten Enquête is dat zo.",
        "In de Nationale Studentenenquête scoort de opleiding goed.",
        "Uit de studentenenquête blijkt dat.",
        "De opleiding heeft een numerus fixus.",
        "Dat hangt af van je studiekeuze.",
    ],
)
def test_een_kenmerkende_term_noemt_de_studiekeuzedatabase(tekst):
    assert vervolgbronnen(tekst, [_skdb_proefkey()])[0]


def test_een_term_binnen_een_woord_telt_niet():
    """Alleen hele woorden: "nse" in "dense" noemt de Nationale Studenten Enquête niet."""
    assert vervolgbronnen("Een dense tabel met veel kolommen.", [_skdb_proefkey()]) == ([], {})


# --- 08-B7 (R11): na "niet in deze bron" alleen aanbieden ------------------------------------------------------------


def test_de_melding_voor_een_mbo_instelling_zegt_aanbieden_en_niet_ophalen(monkeypatch):
    """Van begin tot eind: de vaste zin staat in het toolresultaat dat het model in de volgende ronde krijgt."""
    roc = json.dumps({"weergave": "opleidingen", "instelling": "ROC van Amsterdam"})
    _, gezien = _beurt(
        monkeypatch,
        "Hoe tevreden zijn studenten van ROC van Amsterdam over hun opleiding?",
        [
            StreamResult(text="", tool_calls=[{"id": "r1", "name": TOOL_GET_STUDIEKEUZE, "arguments": roc}]),
            StreamResult(text="Voor het mbo heeft de Studiekeuzedatabase geen oordeel.", tool_calls=[]),
        ],
        {},
    )

    toolresultaat = next(m["content"] for m in gezien[-1] if m.get("role") == "tool")
    assert "is een mbo-instelling" in toolresultaat
    assert ALLEEN_AANBIEDEN in toolresultaat


@pytest.mark.parametrize(
    "melding",
    [
        studiekeuze.ALLEEN_HO,
        wo_personeel.GEEN_OPEN_BRON_HO_MBO,
    ],
)
def test_elke_vaste_melding_buiten_de_bron_draagt_de_zin(melding):
    assert ALLEEN_AANBIEDEN in melding


def test_mbo_indicatoren_voor_een_hogeschool_bieden_alleen_aan():
    assert ALLEEN_AANBIEDEN in mbo_indicatoren.get_mbo_indicatoren("Hogeschool Utrecht")


def test_de_zin_zegt_aanbieden_en_pas_na_instemming_ophalen():
    assert "geen vervangende cijfers" in ALLEEN_AANBIEDEN
    assert "aan als vraag" in ALLEEN_AANBIEDEN and "Pas als de gebruiker" in ALLEEN_AANBIEDEN


def test_de_systeemprompt_maakt_de_uitzondering_op_eigen_suggesties():
    regel = next(r for r in SYSTEM.splitlines() if "niet in haar bron" in r)
    assert "geen vervangende cijfers" in regel and "pas op als de gebruiker" in regel


# --- #987: na heropenen komt de bronregel uit de rij, niet uit de store -------------------------------------------------


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    beurtbewijs.wis()
    yield db
    beurtbewijs.wis()


async def _niets(event: dict) -> None:
    return None


def _chatbeurt(monkeypatch, session: dict, vraag: str, stappen: list[StreamResult]) -> dict:
    """Eén beurt door de chatroute (`_process_message`): die zet de rij van het antwoord klaar (beurtbewijs.zet_klaar).
    Geeft het message_end-event."""
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    with monkeypatch.context() as m:
        m.setattr(loop_module, "acompletion_with_backoff", fake_completion)
        m.setattr(loop_module, "accumulate_stream", fake_accumulate)
        m.setattr(loop_module, "dispatch", _dispatch)
        asyncio.run(chat._process_message(vraag, session, emit, "openai/gpt-4o"))
    return next(e for e in reversed(events) if e["type"] == "message_end")


def _bewaard_koppelgesprek(monkeypatch) -> list[dict]:
    """Een databeurt met een koppeling van de Studiekeuzedatabase aan DUO, door de chatroute, en het gesprek opgeslagen
    zoals de client het PUT. Geeft het gesprek zoals de client het als `history`-frame terugstuurt."""
    session = chat._new_session(username="alice")
    skdb_key = json.loads(studiekeuze.get_studiekeuze(**json.loads(_HU_ICT)))["data_key"]
    koppeling = pd.DataFrame({"brin": ["25DW"], "croho": [30020], "STUDIEJAAR": [2023], "AANTAL": [120]})
    store.derive(_DUO_KEY, _KOPPEL_KEY, koppeling, gelezen=(_DUO_KEY, skdb_key), stap="koppeling op BRIN")
    vraag = "Koppel ICT bij de HU aan de DUO-inschrijvingen."
    analyse = json.dumps({"code": "resultaat = koppeling"})
    einde = _chatbeurt(
        monkeypatch,
        session,
        vraag,
        [
            StreamResult(text="", tool_calls=[{"id": "a1", "name": TOOL_RUN_ANALYSIS, "arguments": analyse}]),
            StreamResult(
                text="ICT (CROHO 30020) bij de Hogeschool Utrecht, gekoppeld aan de inschrijvingen.", tool_calls=[]
            ),
        ],
    )
    berichten = [
        {"id": 1, "role": "user", "content": vraag, "done": True},
        {"id": 2, "role": "assistant", "content": einde["content"], "done": True},
    ]
    put_route.upsert_conversation("c1", {"title": "HU", "timestamp": 1, "messages": berichten}, "alice")
    return berichten


def _heropend_koppelantwoord(monkeypatch, berichten: list[dict], antwoord: str, *, herstart: bool) -> dict:
    """Heropen het gesprek in een nieuwe sessie (`_handle_history`: rijen_voor en _open_conversation) en stel de
    vervolgvraag zonder toolaanroep. Bij `herstart` zijn de store en de klaarstaande rijen leeg: een nieuw proces."""
    if herstart:
        store.clear()
        beurtbewijs.wis()
    session = chat._new_session(username="alice")
    asyncio.run(chat._handle_history({"messages": berichten, "conv_id": "c1"}, session, _niets, None))
    return _chatbeurt(monkeypatch, session, _KOPPELVRAAG, [StreamResult(text=antwoord, tool_calls=[])])


@pytest.mark.usefixtures("zonder_scopekaart")
def test_na_heropenen_met_een_lege_store_houdt_het_vervolgantwoord_de_bronregels(db, monkeypatch):
    """#987: na heropenen in een nieuw proces was `bronnen` leeg; de regels komen nu uit de rij van de databeurt."""
    berichten = _bewaard_koppelgesprek(monkeypatch)

    einde = _heropend_koppelantwoord(monkeypatch, berichten, _KOPPELSLEUTELS, herstart=True)

    assert store.meta(_DUO_KEY) is None and store.meta(_KOPPEL_KEY) is None
    regel = _lcsk_regel(einde["bronnen"])
    assert f"versie {proefbestand.standaard()[1].versie}" in regel
    assert skdb.DOCUMENTATIE in regel or skdb.DOCUMENTATIE in einde.get("bronlinks", {}).values()
    assert any("p01hoinges" in regel for regel in einde["bronnen"])
    assert len(einde["bronnen"]) == 2


@pytest.mark.usefixtures("zonder_scopekaart")
def test_na_heropenen_met_de_keys_nog_in_de_store_zijn_de_bronregels_gelijk(db, monkeypatch):
    berichten = _bewaard_koppelgesprek(monkeypatch)
    met_store = _heropend_koppelantwoord(monkeypatch, berichten, _KOPPELSLEUTELS, herstart=False)

    zonder_store = _heropend_koppelantwoord(monkeypatch, berichten, _KOPPELSLEUTELS, herstart=True)

    assert met_store["bronnen"] and met_store["bronnen"] == zonder_store["bronnen"]
    assert met_store.get("bronlinks") == zonder_store.get("bronlinks")


@pytest.mark.usefixtures("zonder_scopekaart")
def test_na_heropenen_krijgt_een_vervolgantwoord_zonder_bron_geen_bronregel(db, monkeypatch):
    berichten = _bewaard_koppelgesprek(monkeypatch)

    einde = _heropend_koppelantwoord(monkeypatch, berichten, "Graag gedaan.", herstart=True)

    assert einde["bronnen"] == []
    assert "bronlinks" not in einde
