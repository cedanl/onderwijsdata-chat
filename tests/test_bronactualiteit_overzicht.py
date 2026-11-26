"""De pagina "Actualiteit van de bronnen" (#1266): `GET /api/bronactualiteit`, de MCP-resource en de regels onder een
antwoord ("Let op: voorlopig cijfer", een verwachte editie die de bron zelf noemt).

Het hoofdrisico is een geraden datum: een volgende editie die de app uit de frequentie afleidt. Daarom toetst dit bestand
dat elke datum in het overzicht letterlijk in de bronvelden staat, met een fixture en met de echte catalogus. Netwerk
staat dicht in de tests (tests/conftest.py): het overzicht vraagt niets bij een bron op.
"""

import functools
import importlib
import json
import re
from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import mcp_server
import server
from agent.bronvermelding import VOORLOPIG_REGEL, actualiteitsregels
from agent.loop import LoopResult
from core import actualiteit, bronstatus
from core import bronactualiteit_overzicht as bao
from data.arbeidsmarkt import ouderdom_tekst, peildatum_ouderdom_maanden
from tools import store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")

NU = datetime(2026, 11, 26, 12, tzinfo=UTC)
BRONNEN = ["cbs", "duo", "rio", "uwv", "roa", "skdb"]
VELDEN = ("laatste_periode", "laatste_wijziging", "status", "frequentie", "verwachte_volgende_editie")
PLANNING = "Op 14 december 2026 verschijnen de definitieve cijfers over het studiejaar 2025/'26."
# Elke vorm van een dag die een bron of de app zou kunnen schrijven: 2026-12-14, 14-12-2026, 14 december 2026.
_MAANDEN = "januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december"
DATUM = re.compile(
    rf"\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}-\d{{1,2}}-\d{{4}}|\d{{1,2}} (?:{_MAANDEN}) \d{{4}}", re.IGNORECASE
)


@pytest.fixture(autouse=True)
def schoon(monkeypatch):
    """Een stilstaande klok, geen stand van de bronbewaking en geen bewaarde datasets van een vorige test."""
    monkeypatch.setattr(bronstatus, "_stand", {})
    monkeypatch.setattr(actualiteit, "nu", lambda: NU)
    bao.vergeet()
    yield
    bao.vergeet()


def _cbs_record(cbs_id: str, *, volgende: str | None = None, frequentie: str = "Perjaar", gearchiveerd: bool = False):
    """Een CBS-record zoals `onderwijsbronnen.cbs.catalog_records()` het geeft, met alleen de velden die tellen."""
    return {
        "dataset_id": f"cbs:{cbs_id}",
        "titel": f"Tabel {cbs_id}",
        "perioden": {
            "frequentie": frequentie,
            "tekst": "2019/'20-2025/'26",
            "codes": {
                "codes": [
                    {"code": "2024SJ00", "titel": "2024/'25", "status": "Definitief"},
                    {"code": "2025SJ00", "titel": "2025/'26", "status": "Voorlopig"},
                ]
            },
        },
        "herkomst": {"laatste_update": "2026-03-12", "gecontroleerd_op": "2026-10-21"},
        "methodiek": {"publicatie": {"status": "gevonden", "volgende_publicatie": volgende}},
        "archief": {"gearchiveerd": gearchiveerd},
    }


@pytest.fixture
def cbs_fixture(monkeypatch):
    """Drie CBS-tabellen: één met planning van CBS, één zonder, één gearchiveerd."""
    records = [
        _cbs_record("85423NED", volgende=PLANNING),
        _cbs_record("85424NED"),
        _cbs_record("80000NED", gearchiveerd=True),
    ]
    echt = bao._opvraagbaar
    monkeypatch.setattr("onderwijsbronnen.cbs.catalog_records", lambda: records)
    monkeypatch.setattr(
        bao, "_opvraagbaar", lambda bron: {r["dataset_id"][4:] for r in records} if bron == "CBS" else echt(bron)
    )
    monkeypatch.setattr(bao, "_link", lambda i: f"https://opendata.cbs.nl/#/CBS/nl/dataset/{i}/table")
    return records


def _bron(overzicht: dict, sleutel: str) -> dict:
    return next(b for b in overzicht["bronnen"] if b["bron"] == sleutel)


def _dataset(overzicht: dict, sleutel: str, id: str) -> dict:
    return next(d for d in _bron(overzicht, sleutel)["datasets"] if d["id"] == id)


def _teksten(waarde):
    """Elke waarde in het antwoord, diep: om op null, leeg en datums te toetsen."""
    if isinstance(waarde, dict):
        for w in waarde.values():
            yield from _teksten(w)
    elif isinstance(waarde, list):
        for w in waarde:
            yield from _teksten(w)
    else:
        yield waarde


# --- de route ---


def test_de_route_geeft_elke_bron_met_elk_veld_en_nooit_null_of_leeg():
    resp = TestClient(server.app).get("/api/bronactualiteit")

    assert resp.status_code == 200
    data = resp.json()
    assert [b["bron"] for b in data["bronnen"]] == BRONNEN
    for bron in data["bronnen"]:
        for veld in (*VELDEN, "verwachte_volgende_editie_bron"):
            assert isinstance(bron[veld], str) and bron[veld], (bron["bron"], veld)
        assert bron["datasets"], bron["bron"]
        for dataset in bron["datasets"]:
            for veld in (*VELDEN, "verwachte_volgende_editie_bron", "verwachte_volgende_editie_url", "samenvatting"):
                assert isinstance(dataset[veld], str) and dataset[veld], (bron["bron"], dataset["id"], veld)
    for waarde in _teksten(data):
        assert waarde is not None
        assert waarde != ""


def test_de_route_vraagt_geen_inlog_en_wordt_niet_bewaard():
    resp = TestClient(server.app).get("/api/bronactualiteit")
    assert resp.status_code != 401
    assert resp.headers["Cache-Control"] == "no-store"


def test_cbs_toont_de_laatste_periode_haar_status_en_de_laatste_update(cbs_fixture):
    dataset = _dataset(bao.overzicht(), "cbs", "85424NED")

    assert dataset["laatste_periode"] == "2025/'26"
    assert dataset["status"] == "voorlopig"
    assert dataset["laatste_wijziging"] == "2026-03-12"
    assert dataset["frequentie"] == "Jaarlijks"
    assert dataset["gecontroleerd_op"] == "2026-10-21"


def test_een_gearchiveerde_tabel_staat_er_niet(cbs_fixture):
    assert [d["id"] for d in _bron(bao.overzicht(), "cbs")["datasets"]] == ["85423NED", "85424NED"]


# --- een verwachte editie alleen uit de bron ---


def test_zonder_planning_geen_datum_wel_frequentie_en_laatste_update(cbs_fixture):
    dataset = _dataset(bao.overzicht(), "cbs", "85424NED")

    assert dataset["verwachte_volgende_editie"] == "onbekend"
    assert dataset["verwachte_volgende_editie_bron"] == "onbekend"
    assert dataset["samenvatting"] == "frequentie: Jaarlijks, laatste update 2026-03-12"


def test_met_planning_staat_de_zin_van_de_bron_er_met_de_bron_erbij(cbs_fixture):
    dataset = _dataset(bao.overzicht(), "cbs", "85423NED")

    assert dataset["verwachte_volgende_editie"] == PLANNING
    assert "CBS" in dataset["verwachte_volgende_editie_bron"]
    assert "85423NED" in dataset["verwachte_volgende_editie_bron"]
    assert dataset["verwachte_volgende_editie_url"].startswith("https://opendata.cbs.nl/")
    assert PLANNING in dataset["samenvatting"]


def test_een_verwachte_editie_zonder_bron_telt_niet():
    dataset = bao._dataset("x", "Tabel x", verwacht="14 december 2026", verwacht_bron=None)

    assert dataset["verwachte_volgende_editie"] == "onbekend"
    assert dataset["verwachte_volgende_editie_url"] == "onbekend"
    assert "december" not in json.dumps(dataset)


@pytest.mark.parametrize("frequentie", ["Perjaar", "Per kwartaal", "Maandelijks", "Tweejaarlijks", "Kwartaal"])
def test_elke_getoonde_datum_komt_letterlijk_uit_de_fixture(monkeypatch, cbs_fixture, frequentie):
    """Property: welke frequentie ook, het overzicht bevat geen datum die niet letterlijk in de bronvelden staat. Een
    geraden "volgende editie" (laatste update plus een jaar of kwartaal) zou hier een nieuwe datum zijn."""
    for record in cbs_fixture:
        record["perioden"]["frequentie"] = frequentie
    bron = json.dumps(_bron(bao.overzicht(), "cbs"), ensure_ascii=False)
    fixture = json.dumps(cbs_fixture, ensure_ascii=False)

    datums = DATUM.findall(bron)
    assert datums, "de fixture heeft datums: zonder treffers toetst dit niets"
    assert [d for d in datums if d not in fixture] == []


def test_elke_datum_in_het_echte_overzicht_staat_in_de_catalogus():
    """Dezelfde property op de echte catalogus: elke datum van elke bron staat letterlijk in haar catalogusrecords."""
    from onderwijsbronnen import duo, rio, roa, skdb, uwv
    from onderwijsbronnen.cbs import catalog_records

    catalogus = json.dumps(
        [catalog_records(), *(m.catalogusrecords() for m in (duo, rio, uwv, roa, skdb))], ensure_ascii=False
    )
    tekst = json.dumps(bao.overzicht(), ensure_ascii=False)

    datums = set(DATUM.findall(tekst))
    assert datums
    assert sorted(d for d in datums if d not in catalogus) == []


# --- de regel onder een antwoord ---


def _cbs_lading(key: str, statussen: dict[str, str], dataset: str = "85423NED") -> tuple[str, str]:
    """Een CBS-lading in de store met per periode haar Periodestatus, en de stap die haar laadde."""
    df = pd.DataFrame(
        {"Perioden": list(statussen), "Periodestatus": list(statussen.values()), "AANTAL": [1] * len(statussen)}
    )
    store.put(key, df, KeyMeta(bron="cbs", dataset=dataset, periodekolom="Perioden", opgehaald_op=NU))
    return "get_cbs_data", json.dumps({"data_key": key})


def test_een_voorlopig_cbs_cijfer_krijgt_de_regel_voorlopig():
    stap = _cbs_lading("cbs:85423NED:v", {"2024SJ00": "Definitief", "2025SJ00": "Voorlopig"})

    [regel] = actualiteitsregels([stap])
    assert regel.startswith(VOORLOPIG_REGEL)
    assert "2025/26" in regel
    assert "85423NED" in regel


def test_alleen_definitieve_cijfers_geven_geen_regel():
    stap = _cbs_lading("cbs:85423NED:d", {"2023SJ00": "Definitief", "2024SJ00": "Definitief"})
    assert actualiteitsregels([stap]) == []


def test_het_antwoord_met_een_voorlopig_cbs_cijfer_draagt_de_regel():
    """Het message_end van een data-antwoord op voorlopige CBS-cijfers heeft de regel; zonder zou de gebruiker een
    voorlopig cijfer als definitief lezen."""
    stap = _cbs_lading("cbs:85423NED:a", {"2025SJ00": "Voorlopig"})
    einde = run_module._slotbericht("Er zijn 12.345 studenten.", LoopResult(steps=[stap]), [], False, ["CBS · tabel"])

    assert any(regel.startswith(VOORLOPIG_REGEL) for regel in einde["actualiteit"])


def test_een_antwoord_zonder_bronnen_krijgt_geen_regel():
    stap = _cbs_lading("cbs:85423NED:z", {"2025SJ00": "Voorlopig"})
    einde = run_module._slotbericht("Geen data.", LoopResult(steps=[stap]), [], False, [])
    assert "actualiteit" not in einde


@pytest.fixture
def planning(monkeypatch):
    """De TableInfos van 85423NED met een eigen zin van CBS over de volgende cijfers."""
    zinnen = {"85423NED": PLANNING}

    def get_dataset(dataset_id):
        from onderwijsbronnen.cbs import contract

        if dataset_id not in zinnen:
            raise contract.DatasetNietGevonden(dataset_id)
        return _cbs_record(dataset_id, volgende=zinnen[dataset_id])

    monkeypatch.setattr("onderwijsbronnen.cbs.contract.get_dataset", get_dataset)
    return zinnen


def test_een_dag_die_cbs_noemt_binnen_30_dagen_komt_onder_het_antwoord(planning):
    regel = bao.verwacht_binnenkort("85423NED")

    assert regel == f"Nieuwe editie verwacht op 14 december 2026 (bron: {bao.cbs_bron('85423NED')})"
    stap = _cbs_lading("cbs:85423NED:p", {"2025SJ00": "Definitief"})
    assert actualiteitsregels([stap]) == [regel]


@pytest.mark.parametrize(
    ("zin", "nu"),
    [
        (PLANNING, datetime(2026, 10, 1, 12, tzinfo=UTC)),  # verder dan 30 dagen weg
        (PLANNING, datetime(2026, 12, 20, 12, tzinfo=UTC)),  # al voorbij
        ("In het eerste kwartaal van 2027 komen de voorlopige cijfers beschikbaar.", NU),  # geen dag
    ],
    ids=["te-ver", "voorbij", "kwartaal"],
)
def test_geen_regel_zonder_dag_binnen_30_dagen(planning, zin, nu):
    planning["85423NED"] = zin
    assert bao.verwacht_binnenkort("85423NED", nu) is None


def test_een_tabel_zonder_planning_geeft_geen_regel(planning):
    assert bao.verwacht_binnenkort("85424NED") is None


# --- een bron die niet live is ---


def test_een_bron_die_niet_live_is_staat_er_als_niet_bereikbaar(monkeypatch):
    monkeypatch.setattr(bronstatus, "niet_live", lambda: [{"bron": "duo", "naam": "DUO", "tekst": "…"}])

    resp = TestClient(server.app).get("/api/bronactualiteit")

    assert resp.status_code == 200
    duo = _bron(resp.json(), "duo")
    assert duo["bereikbaar"] == "niet bereikbaar"
    assert "niet bereikbaar" in duo["melding"]
    assert _bron(resp.json(), "cbs")["bereikbaar"] != "niet bereikbaar"


def test_de_stand_van_de_bewaking_per_bron():
    bronstatus._stand["cbs"] = bronstatus._Stand(live=False)
    bronstatus._stand["rio"] = bronstatus._Stand(live=True)
    overzicht = bao.overzicht()

    assert _bron(overzicht, "cbs")["bereikbaar"] == "niet bereikbaar"
    assert _bron(overzicht, "rio")["bereikbaar"] == "bereikbaar"
    assert _bron(overzicht, "roa")["bereikbaar"] == "onbekend"  # niet bewaakt


def test_een_bron_die_niet_leest_geeft_onbekend_en_geen_500(monkeypatch):
    @functools.cache
    def kapot() -> list[dict]:
        raise OSError("catalogus onleesbaar")

    monkeypatch.setitem(bao.LEZERS, "rio", kapot)

    resp = TestClient(server.app).get("/api/bronactualiteit")

    assert resp.status_code == 200
    rio = _bron(resp.json(), "rio")
    assert rio["datasets"] == []
    assert all(rio[veld] == "onbekend" for veld in VELDEN)
    assert "RIO" in rio["melding"]
    assert "onleesbaar" not in json.dumps(resp.json())
    assert _bron(resp.json(), "cbs")["datasets"]


# --- UWV: de ouderdom uit #1219 ---


def test_uwv_toont_de_ouderdom_met_de_tekst_van_de_dashboards():
    uwv = _bron(TestClient(server.app).get("/api/bronactualiteit").json(), "uwv")

    maanden = peildatum_ouderdom_maanden(uwv["laatste_periode"])
    assert maanden is not None
    assert uwv["ouderdom"]["tekst"] == ouderdom_tekst(maanden)
    assert uwv["ouderdom"]["maanden"] == maanden
    assert uwv["ouderdom"]["verouderd"] is True
    assert uwv["datasets"][0]["ouderdom"] == uwv["ouderdom"]


# --- MCP: dezelfde inhoud als resource ---


def test_de_mcp_resource_geeft_hetzelfde_overzicht():
    [resource] = mcp_server.resources()
    assert resource["uri"] == mcp_server.BRONACTUALITEIT_URI

    gelezen = json.loads(mcp_server.lees_resource(mcp_server.BRONACTUALITEIT_URI))
    assert gelezen == mcp_server.ontsmet(bao.overzicht())
    assert mcp_server.BRONACTUALITEIT_URI in mcp_server.INSTRUCTIES


def test_een_onbekende_resource_is_een_fout():
    with pytest.raises(ValueError, match="Onbekende resource"):
        mcp_server.lees_resource("onderwijscatalogus://iets-anders")


def test_de_resource_via_het_protocol():
    import anyio
    from mcp.client.session import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    async def draai():
        server_mcp = mcp_server.maak_server()
        async with (
            create_client_server_memory_streams() as (client_streams, server_streams),
            anyio.create_task_group() as groep,
        ):
            groep.start_soon(server_mcp.run, *server_streams, server_mcp.create_initialization_options())
            async with ClientSession(*client_streams) as sessie:
                await sessie.initialize()
                lijst = await sessie.list_resources()
                gelezen = await sessie.read_resource(mcp_server.BRONACTUALITEIT_URI)
            groep.cancel_scope.cancel()
        return lijst, gelezen

    lijst, gelezen = anyio.run(draai)
    assert [str(r.uri) for r in lijst.resources] == [mcp_server.BRONACTUALITEIT_URI]
    [inhoud] = gelezen.contents
    assert [b["bron"] for b in json.loads(inhoud.text)["bronnen"]] == BRONNEN
