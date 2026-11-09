"""Het bewijs per afgerond antwoord (ADR-009, #875): klaarzetten bij `message_end`, schrijven na de PUT, herstellen bij
heropenen en herverbinden, en de levenscyclus in het geheugen.

De rijen zelf (DDL, opschonen, export, verwijderen) staan in tests/test_persistence_beurtbewijs.py en de
tests van de levenscyclus (test_opschonen, test_mijn_gegevens_*).
"""

import asyncio
import hashlib
import importlib
import json
import logging
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException

from agent import beurtbewijs, report
from agent.datasetcontext import build_dataset_context
from agent.kaarten import kaarten_in_gesprek
from agent.loop import LoopResult
from agent.session_data import data_lineage, gebruikersvragen, record_data_key, record_rekenbewijs, rekenbewijs
from routes import chat
from routes import persistence as put_route
from tests.test_report_kaart import _ANTWOORD, _GEOJSON, _KAART, _KEY, _kaartbeurt, _stil
from tools import store

_LAAD = {"name": "get_cbs_data", "arguments": {"dataset_id": "85423NED", "filters": None}}
_REKEN = {"name": "compute_kpi", "arguments": {"data_key": _KEY, "kpi": "som"}}
_ONBEKEND = "onbekend (niet vastgelegd in dit gesprek)"


@pytest.fixture(autouse=True)
def _kaartdata():
    store.put(_KEY, pd.DataFrame({"PROVINCIE": ["Utrecht", "Drenthe", "Groningen"], "AANTAL": [41230, 12040, 20500]}))
    with patch("tools.plot._load_geojson", side_effect=lambda niveau: _GEOJSON):
        yield


@pytest.fixture(autouse=True)
def _leeg_geheugen():
    beurtbewijs.wis()
    yield
    beurtbewijs.wis()


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


def _sessie(gebruiker: str = "alice") -> dict:
    return chat._new_session(username=gebruiker)


async def _niets(event: dict) -> None:
    return None


def _beurt(
    monkeypatch,
    sessie: dict,
    vraag: str,
    tekst: str,
    *,
    laad: str | None = None,
    reken: bool = False,
    kaart: bool = False,
    stop: bool = False,
) -> list[dict]:
    """Eén beurt door `_process_message`, met een model dat doet wat de vlaggen zeggen. Geeft de events terug."""
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    async def nep_run(messages, session, emit, stop_event, model=None):
        if laad:
            record_data_key(session, json.dumps({"data_key": laad}), _LAAD)
        if reken:
            record_rekenbewijs(session, json.dumps({"waarde": 74770}), _REKEN)
        if kaart:
            beurt = _kaartbeurt(_KAART)
            session["_last_turn_tool_calls"] = beurt["tool_calls"]
            session["turn_figures"] = beurt["figures"]
        if stop:
            stop_event.set()
        await emit({"type": "message_end", "content": tekst, "actions": [], "bronnen": []})
        return tekst

    monkeypatch.setattr(chat, "agent_run", nep_run)
    asyncio.run(chat._process_message(vraag, sessie, emit, None))
    return events


def _antwoord(tekst: str, **extra) -> dict:
    return {"id": 2, "role": "assistant", "content": tekst, "done": True, **extra}


def _gesprek(*paren: tuple[str, str]) -> list[dict]:
    """Berichten zoals de client ze bewaart: vraag, antwoord, vraag, antwoord."""
    return [
        bericht
        for vraag, tekst in paren
        for bericht in ({"id": 1, "role": "user", "content": vraag, "done": True}, _antwoord(tekst))
    ]


def _put(gebruiker: str, conv_id: str, berichten: list[dict]) -> dict:
    return put_route.upsert_conversation(
        conv_id, {"title": "Titel", "timestamp": 1_700_000_000, "messages": berichten}, gebruiker
    )


def _heropen(gebruiker: str, berichten: list[dict], conv_id: str | None = None) -> dict:
    """Het `history`-frame van de client op een nieuwe verbinding; de sessie die de server ervan maakt."""
    sessie = _sessie(gebruiker)
    asyncio.run(chat._handle_history({"messages": berichten, "conv_id": conv_id}, sessie, _niets, None))
    return sessie


def _rapportprompt(sessie: dict, monkeypatch) -> str:
    prompts: list[str] = []

    async def loop(messages, **_):
        prompts.append(messages[0]["content"])
        return LoopResult(text=_ANTWOORD)

    monkeypatch.setattr(report, "tool_loop", loop)
    asyncio.run(report.generate(sessie, _stil))
    return prompts[0]


# ── De sleutel: de tekst van message_end ─────────────────────────────────────


def test_de_hash_is_de_sha256_van_de_utf8_tekst():
    assert beurtbewijs.tekst_hash("Antwoord é") == hashlib.sha256("Antwoord é".encode()).hexdigest()


def test_een_onbruikbaar_teken_breekt_de_hash_niet():
    assert len(beurtbewijs.tekst_hash("half \ud83d")) == 64


def test_de_hashes_van_een_gesprek_zijn_die_van_de_antwoorden_in_volgorde_en_uniek():
    berichten = [
        *_gesprek(("a?", "Eerste"), ("b?", "Tweede")),
        _antwoord("Eerste"),
        _antwoord(""),
        {"role": "assistant", "content": None},
    ]
    assert beurtbewijs.antwoord_hashes(berichten) == [
        beurtbewijs.tekst_hash("Eerste"),
        beurtbewijs.tekst_hash("Tweede"),
    ]
    assert beurtbewijs.antwoord_hashes("geen lijst") == []


def test_de_content_van_message_end_is_de_tekst_die_de_client_bewaart(monkeypatch):
    """De hash vindt niets als de tekst onderweg verandert: `message_end` -> bericht -> PUT-body (JSON) -> hash.

    Het echte `run` (het vaste antwoord op "-1") stuurt zijn `message_end`; de client zet `ev.content` ongewijzigd in
    het bericht (frontend/src/__tests__/messageEndContent.test.js) en de body gaat als JSON over de lijn."""
    from agent.run import run

    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    sessie = _sessie()
    antwoord = asyncio.run(run([{"role": "user", "content": "Wat betekent -1 in de data?"}], sessie, emit))

    [eind] = [e for e in events if e["type"] == "message_end"]
    assert eind["content"] == antwoord
    bericht = {"role": "assistant", "content": eind["content"], "done": True}
    body = json.loads(json.dumps({"messages": [bericht]}))
    assert beurtbewijs.antwoord_hashes(body["messages"]) == [beurtbewijs.tekst_hash(eind["content"])]


def test_de_chatroute_zet_het_bewijs_klaar_onder_de_hash_van_message_end(monkeypatch):
    sessie = _sessie()
    events = _beurt(monkeypatch, sessie, "Hoeveel?", "Het zijn 74.770.", laad=_KEY, reken=True)

    [eind] = [e for e in events if e["type"] == "message_end"]
    assert list(beurtbewijs._klaar) == [("alice", beurtbewijs.tekst_hash(eind["content"]))]


# ── Klaarzetten ──────────────────────────────────────────────────────────────


def test_een_rij_draagt_wat_de_beurt_opleverde(monkeypatch):
    sessie = _sessie()
    _beurt(monkeypatch, sessie, "Maak een kaart", "Hier is de kaart.", laad=_KEY, reken=True, kaart=True)

    [rij] = beurtbewijs._klaar.values()
    assert rij["lineage"] == {_KEY: _LAAD}
    assert [r["tool"] for r in rij["rekenbewijs"]] == ["compute_kpi"]
    assert rij["kaarten"] == {_KEY: {"data_key": _KEY, "location_col": "PROVINCIE", "value_col": "AANTAL"}}
    assert rij["created_at"].endswith("+00:00")


def test_een_rij_draagt_de_controle_van_haar_message_end(monkeypatch):
    """De rij bewaart de controle van de server, niet die uit het gesprek dat de client schreef (#876)."""
    sessie = _sessie()
    melding = "28.355 staat alleen in een eerder bericht van de gebruiker, niet in de opgehaalde data."

    async def met_controle(messages, session, emit, stop_event, model=None):
        await emit({"type": "message_end", "content": "Nee.", "actions": [], "bronnen": [], "controle": [melding]})
        return "Nee."

    monkeypatch.setattr(chat, "agent_run", met_controle)
    asyncio.run(chat._process_message("Toch 28355?", sessie, _niets, None))
    _beurt(monkeypatch, sessie, "En verder?", "Zonder melding.")

    assert beurtbewijs._klaar["alice", beurtbewijs.tekst_hash("Nee.")]["controle"] == [melding]
    assert beurtbewijs._klaar["alice", beurtbewijs.tekst_hash("Zonder melding.")]["controle"] == []


def test_een_rij_bevat_wat_sinds_de_vorige_beurt_bijkwam(monkeypatch):
    sessie = _sessie()
    _beurt(monkeypatch, sessie, "Eerste?", "Eerste antwoord.", laad=_KEY, reken=True)
    _beurt(monkeypatch, sessie, "Tweede?", "Tweede antwoord.")
    _beurt(monkeypatch, sessie, "Derde?", "Derde antwoord.", laad=_KEY, reken=True)

    eerste, tweede, derde = (
        beurtbewijs._klaar["alice", beurtbewijs.tekst_hash(t)]
        for t in ("Eerste antwoord.", "Tweede antwoord.", "Derde antwoord.")
    )
    assert list(eerste["lineage"]) == [_KEY] and len(eerste["rekenbewijs"]) == 1
    assert tweede["lineage"] == {} and tweede["rekenbewijs"] == []
    # De key bestond al: de eerste maker wint en de tweede keer staat hij niet opnieuw in een rij.
    assert derde["lineage"] == {} and len(derde["rekenbewijs"]) == 1


def test_een_gestopte_beurt_krijgt_geen_rij_en_haar_lineage_gaat_naar_de_volgende(monkeypatch):
    sessie = _sessie()
    _beurt(monkeypatch, sessie, "Eerste?", "Half antwoord", laad=_KEY, reken=True, stop=True)
    assert beurtbewijs._klaar == {}

    _beurt(monkeypatch, sessie, "Opnieuw?", "Volledig antwoord.")

    [rij] = beurtbewijs._klaar.values()
    assert list(rij["lineage"]) == [_KEY] and len(rij["rekenbewijs"]) == 1


def test_een_mislukte_beurt_en_een_verduidelijkingskaart_krijgen_geen_rij(monkeypatch):
    sessie = _sessie()

    async def stuk(messages, session, emit, stop_event, model=None):
        record_data_key(session, json.dumps({"data_key": _KEY}), _LAAD)
        raise RuntimeError("model weg")

    monkeypatch.setattr(chat, "agent_run", stuk)
    asyncio.run(chat._process_message("Vraag?", sessie, _niets, None))

    async def verduidelijk(messages, session, emit, stop_event, model=None):
        session["_clarified"] = True
        return ""

    monkeypatch.setattr(chat, "agent_run", verduidelijk)
    asyncio.run(chat._process_message("Welke?", sessie, _niets, None))

    assert beurtbewijs._klaar == {}


def test_dezelfde_tekst_twee_keer_geeft_een_rij_met_beide_beurten(monkeypatch):
    sessie = _sessie()
    ander = {"name": "get_cbs_data", "arguments": {"dataset_id": "anders"}}
    _beurt(monkeypatch, sessie, "Eerste?", "Gelijk antwoord.", laad=_KEY, reken=True)
    record_data_key(sessie, json.dumps({"data_key": "cbs:anders"}), ander)
    _beurt(monkeypatch, sessie, "Tweede?", "Gelijk antwoord.", reken=True)

    [rij] = beurtbewijs._klaar.values()
    assert set(rij["lineage"]) == {_KEY, "cbs:anders"}
    assert rij["lineage"][_KEY] == _LAAD


def test_samenvoegen_kan_zo_vaak_als_je_wilt():
    a = {
        "lineage": {"k": 1},
        "rekenbewijs": [{"r": 1}],
        "kaarten": {"k": {"v": 1}},
        "controle": ["eerste melding"],
        "created_at": "eerst",
    }
    b = {
        "lineage": {"k": 2, "l": 3},
        "rekenbewijs": [{"r": 1}, {"r": 2}],
        "kaarten": {"k": {"v": 2}},
        "controle": ["eerste melding", "tweede melding"],
        "created_at": "laat",
    }

    samen = beurtbewijs.voeg_samen(a, b)

    assert samen == {
        "lineage": {"k": 1, "l": 3},  # de eerste maker wint
        "rekenbewijs": [{"r": 1}, {"r": 2}],
        "kaarten": {"k": {"v": 2}},  # de latere kaart wint
        "controle": ["eerste melding", "tweede melding"],  # elke melding één keer
        "created_at": "eerst",
    }
    assert beurtbewijs.voeg_samen(samen, b) == samen


def test_het_geheugen_is_begrensd(monkeypatch):
    monkeypatch.setattr(beurtbewijs, "_MAX_KLAAR", 3)
    sessie = _sessie()
    for i in range(5):
        _beurt(monkeypatch, sessie, f"Vraag {i}?", f"Antwoord {i}")

    assert [h for _, h in beurtbewijs._klaar] == [beurtbewijs.tekst_hash(f"Antwoord {i}") for i in (2, 3, 4)]


def test_zonder_gebruikersnaam_staat_er_niets_klaar():
    beurtbewijs.zet_klaar({"username": ""}, {}, "tekst")

    assert beurtbewijs._klaar == {}


# ── Schrijven na de PUT ──────────────────────────────────────────────────────


def test_de_put_schrijft_een_rij_per_antwoord_waarvan_de_hash_klaarstaat(db, monkeypatch):
    sessie = _sessie()
    _beurt(monkeypatch, sessie, "Eerste?", "Antwoord een.", laad=_KEY, reken=True)
    _beurt(monkeypatch, sessie, "Tweede?", "Antwoord twee.")

    _put(
        "alice",
        "c1",
        [*_gesprek(("Eerste?", "Antwoord een."), ("Tweede?", "Antwoord twee.")), *_gesprek(("x", "Vreemd"))],
    )

    assert set(db.beurtbewijs_voor("alice", "c1")) == {
        beurtbewijs.tekst_hash(t) for t in ("Antwoord een.", "Antwoord twee.")
    }
    assert db.beurtbewijs_voor("bob", "c1") == {}


def test_een_antwoord_waarvan_de_client_de_tekst_veranderde_krijgt_geen_rij(db, monkeypatch):
    _beurt(monkeypatch, _sessie(), "Eerste?", "Antwoord een.", laad=_KEY)

    _put("alice", "c1", _gesprek(("Eerste?", "Antwoord een. Aangepast door de client.")))

    assert db.beurtbewijs_voor("alice", "c1") == {}
    sessie = _heropen("alice", _gesprek(("Eerste?", "Antwoord een. Aangepast door de client.")), "c1")
    assert sessie["data_provenance"] == {} and sessie.get("rekenbewijs") is None


def test_een_klaarstaande_rij_blijft_staan_en_opnieuw_opslaan_verandert_niets(db, monkeypatch):
    _beurt(monkeypatch, _sessie(), "Eerste?", "Antwoord een.", laad=_KEY, reken=True)
    berichten = _gesprek(("Eerste?", "Antwoord een."))
    _put("alice", "c1", berichten)
    eerste = db.beurtbewijs_voor("alice", "c1")

    schrijfacties: list[dict] = []
    echt = db.save_beurtbewijs
    monkeypatch.setattr(db, "save_beurtbewijs", lambda u, c, rijen: (schrijfacties.append(rijen), echt(u, c, rijen)))
    _put("alice", "c1", [*berichten, *_gesprek(("Tweede?", "Antwoord zonder rij."))])

    assert db.beurtbewijs_voor("alice", "c1") == eerste
    assert schrijfacties == [{}]
    assert len(beurtbewijs._klaar) == 1


def test_een_put_die_409_geeft_schrijft_geen_rij_en_de_afsplitsing_wel(db, monkeypatch):
    _put("alice", "c1", _gesprek(("Eerste vraag?", "Oud antwoord.")))
    _beurt(monkeypatch, _sessie(), "Andere vraag?", "Nieuw antwoord.", laad=_KEY)
    nieuw = _gesprek(("Andere vraag?", "Nieuw antwoord."))

    with pytest.raises(HTTPException) as fout:
        _put("alice", "c1", nieuw)

    assert fout.value.status_code == 409
    assert db.beurtbewijs_voor("alice", "c1") == {}
    _put("alice", "c1-afsplitsing", nieuw)
    assert list(db.beurtbewijs_voor("alice", "c1-afsplitsing")) == [beurtbewijs.tekst_hash("Nieuw antwoord.")]


# ── Herstellen ───────────────────────────────────────────────────────────────


def _live_gesprek(monkeypatch) -> tuple[dict, list[dict]]:
    """Een levend gesprek: een antwoord op data met een berekening en een kaart, en een vervolgvraag."""
    sessie = _sessie()
    _beurt(
        monkeypatch,
        sessie,
        "Hoeveel mbo-studenten zijn er per provincie?",
        "Dit is de kaart.",
        laad=_KEY,
        reken=True,
        kaart=True,
    )
    _beurt(monkeypatch, sessie, "En wat is het totaal?", "Samen zijn het er 74.770.", reken=True)
    return sessie, _gesprek(
        ("Hoeveel mbo-studenten zijn er per provincie?", "Dit is de kaart."),
        ("En wat is het totaal?", "Samen zijn het er 74.770."),
    )


def test_een_heropend_gesprek_geeft_hetzelfde_bewijs_als_de_levende_sessie(db, monkeypatch):
    live, berichten = _live_gesprek(monkeypatch)
    _put("alice", "c1", berichten)
    beurtbewijs.wis()  # de server herstartte: alleen de database weet het nog

    heropend = _heropen("alice", berichten, "c1")
    heropend["data_keys"] = [_KEY]  # de recepten (#472) staan buiten dit onderzoek

    assert data_lineage(heropend, _KEY) == data_lineage(live, _KEY) == [_LAAD]
    assert rekenbewijs(heropend) == rekenbewijs(live) and len(rekenbewijs(live)) == 2
    assert kaarten_in_gesprek(heropend) == kaarten_in_gesprek(live) and _KEY in kaarten_in_gesprek(live)
    assert heropend["data_vraag"] == live["data_vraag"] == {_KEY: 1}
    assert gebruikersvragen(heropend) == gebruikersvragen(live)
    assert build_dataset_context(heropend) == build_dataset_context(live)


def test_de_rapportprompt_van_een_heropend_gesprek_is_die_van_het_levende(db, monkeypatch):
    live, berichten = _live_gesprek(monkeypatch)
    _put("alice", "c1", berichten)
    beurtbewijs.wis()
    heropend = _heropen("alice", berichten, "c1")
    heropend["data_keys"] = [_KEY]

    prompt = _rapportprompt(heropend, monkeypatch)

    assert _ONBEKEND not in prompt
    assert "Kaart in het gesprek: create_choropleth_map" in prompt
    assert "Eerder berekend in het gesprek" in prompt
    assert prompt == _rapportprompt(live, monkeypatch)


def test_zonder_bewijs_staat_de_herkomst_als_onbekend_in_de_prompt(db, monkeypatch):
    """Het gedrag van vóór de migratie: dit bewijst dat de test hierboven iets meet."""
    _, berichten = _live_gesprek(monkeypatch)
    beurtbewijs.wis()
    heropend = _heropen("alice", berichten, "c1")
    heropend["data_keys"] = [_KEY]

    assert _ONBEKEND in _rapportprompt(heropend, monkeypatch)


def test_herverbinden_voor_de_eerste_put_herstelt_uit_het_geheugen(db, monkeypatch):
    live, berichten = _live_gesprek(monkeypatch)

    heropend = _heropen("alice", berichten, "c1")  # geen PUT geweest: de rijen staan nog klaar

    assert db.beurtbewijs_voor("alice", "c1") == {}
    assert data_lineage(heropend, _KEY) == data_lineage(live, _KEY) == [_LAAD]
    assert rekenbewijs(heropend) == rekenbewijs(live)
    assert kaarten_in_gesprek(heropend) == kaarten_in_gesprek(live)


def test_herverbinden_zonder_gesprek_id_herstelt_ook_uit_het_geheugen(db, monkeypatch):
    _, berichten = _live_gesprek(monkeypatch)

    assert data_lineage(_heropen("alice", berichten), _KEY) == [_LAAD]


def test_een_gesprek_zonder_rijen_heropent_zoals_nu(db):
    berichten = _gesprek(("Oude vraag?", "Oud antwoord."))
    _put("alice", "c1", berichten)

    sessie = _heropen("alice", berichten, "c1")

    assert sessie["messages"] == [
        {"role": "user", "content": "Oude vraag?"},
        {"role": "assistant", "content": "Oud antwoord."},
    ]
    assert sessie.get("data_provenance") == {} and not rekenbewijs(sessie) and kaarten_in_gesprek(sessie) == {}
    assert sessie.get("data_vraag") is None


def test_het_bewijs_van_een_ander_gesprek_of_gebruiker_komt_niet_mee(db, monkeypatch):
    _, berichten = _live_gesprek(monkeypatch)
    _put("alice", "c1", berichten)
    beurtbewijs.wis()

    assert data_lineage(_heropen("alice", berichten, "ander-gesprek"), _KEY) == []
    assert data_lineage(_heropen("bob", berichten, "c1"), _KEY) == []


def test_alleen_de_antwoorden_in_het_frame_herstellen(db, monkeypatch):
    _, berichten = _live_gesprek(monkeypatch)
    _put("alice", "c1", berichten)
    beurtbewijs.wis()

    sessie = _heropen("alice", berichten[2:], "c1")  # alleen het tweede antwoord: dat had een berekening, geen data

    assert sessie["data_provenance"] == {} and len(rekenbewijs(sessie)) == 1 and kaarten_in_gesprek(sessie) == {}


def test_het_rekenbewijs_na_heropenen_kent_dezelfde_grens_als_live(db, monkeypatch):
    sessie = _sessie()
    paren = []
    for i in range(35):
        _beurt(monkeypatch, sessie, f"Vraag {i}?", f"Antwoord {i}.", reken=True)
        paren.append((f"Vraag {i}?", f"Antwoord {i}."))
    berichten = _gesprek(*paren)
    _put("alice", "c1", berichten)
    beurtbewijs.wis()

    heropend = _heropen("alice", berichten, "c1")

    assert len(rekenbewijs(sessie)) == len(rekenbewijs(heropend)) == 30


def test_het_vraagnummer_volgt_uit_de_plaats_in_de_ingekorte_geschiedenis(db, monkeypatch):
    """Een beurt die uit de modelgeschiedenis valt, houdt haar lineage maar heeft geen vraagnummer."""
    sessie = _sessie()
    _beurt(monkeypatch, sessie, "Vraag 0?", "Antwoord 0.", laad="cbs:oud")
    paren = [("Vraag 0?", "Antwoord 0.")]
    for i in range(1, 30):
        _beurt(monkeypatch, sessie, f"Vraag {i}?", f"Antwoord {i}.")
        paren.append((f"Vraag {i}?", f"Antwoord {i}."))
    _beurt(monkeypatch, sessie, "Laatste?", "Laatste antwoord.", laad="cbs:laat")
    paren.append(("Laatste?", "Laatste antwoord."))
    berichten = _gesprek(*paren)

    heropend = _heropen("alice", berichten)  # 62 berichten: boven MAX_HISTORY, de oudste vallen af

    assert len(heropend["messages"]) < len(berichten)
    assert set(heropend["data_provenance"]) == {"cbs:oud", "cbs:laat"}
    assert "cbs:oud" not in heropend["data_vraag"]
    assert heropend["data_vraag"]["cbs:laat"] == len(gebruikersvragen(heropend))
    assert sessie["data_vraag"]["cbs:laat"] == 31


# ── Levenscyclus in het geheugen ─────────────────────────────────────────────


def test_een_gesprek_verwijderen_haalt_zijn_klaarstaande_rijen_uit_het_geheugen(db, monkeypatch):
    _beurt(monkeypatch, _sessie(), "Eerste?", "Antwoord een.", laad=_KEY)
    _beurt(monkeypatch, _sessie(), "Andere?", "Ander gesprek.", laad=_KEY)
    _put("alice", "c1", _gesprek(("Eerste?", "Antwoord een.")))
    _put("alice", "c2", _gesprek(("Andere?", "Ander gesprek.")))

    put_route.delete_conversation("c1", "alice")

    assert db.beurtbewijs_voor("alice", "c1") == {}
    assert set(db.beurtbewijs_voor("alice", "c2")) == {beurtbewijs.tekst_hash("Ander gesprek.")}
    assert [h for _, h in beurtbewijs._klaar] == [beurtbewijs.tekst_hash("Ander gesprek.")]


def test_verwijder_al_mijn_gegevens_vergeet_ook_wat_nooit_is_opgeslagen():
    beurtbewijs._klaar["alice", "h1"] = {}
    beurtbewijs._klaar["bob", "h2"] = {}

    beurtbewijs.vergeet_gebruiker("alice")

    assert list(beurtbewijs._klaar) == [("bob", "h2")]


def test_op_info_staan_alleen_aantallen(db, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    _beurt(monkeypatch, _sessie(), "Eerste?", "Antwoord een met GEHEIMTEKST.", laad=_KEY, reken=True)
    _put("alice", "c1", _gesprek(("Eerste?", "Antwoord een met GEHEIMTEKST.")))
    _heropen("alice", _gesprek(("Eerste?", "Antwoord een met GEHEIMTEKST.")), "c1")

    regels = [r.getMessage() for r in caplog.records if r.name == "agent.beurtbewijs"]

    assert len(regels) == 3
    for regel in regels:
        assert "GEHEIMTEKST" not in regel and "74770" not in regel and _KEY not in regel and "c1" not in regel
