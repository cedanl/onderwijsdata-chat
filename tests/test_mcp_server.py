"""MCP-server voor de catalogus (#41, stap 1): dezelfde schema's en dezelfde uitvoering als de chat.

De definities en de uitvoering zijn zonder de mcp-package te toetsen; het protocol zelf (initialize,
list_tools, call_tool) over een in-memory verbinding. `mcp` is sinds #938 een gewone dependency.
"""

import json
import os
import urllib.parse

import pytest

import mcp_server
import tools
from core.appversie import app_versie
from tools.schemas import TOOL_SCHEMAS


def _functie(naam: str) -> dict:
    return next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == naam)


CATALOGUS = ["search_catalog", "dataset_details", "dataset_counts"]
DATATOOLS = ["aantallen_per_jaar", "vergelijk_instellingen"]


def test_alleen_stateless_tools():
    """De catalogustools van de chat en de sessieloze datatools (#708); geen tool met een data_key."""
    definities = mcp_server.tooldefinities()
    assert [d["name"] for d in definities] == CATALOGUS + DATATOOLS
    for definitie in definities:
        assert definitie["name"] in tools._HANDLERS or definitie["name"] in DATATOOLS
        assert "data_key" not in definitie["input_schema"]["properties"], "een datastore-tool is niet stateless"


def test_definities_volgen_het_toolschema_van_de_chat():
    for definitie in mcp_server.tooldefinities()[: len(CATALOGUS)]:
        functie = _functie(definitie["name"])
        assert definitie["description"] == f"{functie['description']} {mcp_server.REGEL_GETALLEN}"
        assert definitie["input_schema"] == functie["parameters"]


def test_toolbeschrijvingen_zijn_goed_nederlands_en_zonder_chat():
    """Een MCP-client toont de beschrijvingen aan gebruikers en geeft ze aan een extern model: geen "specifiek dataset",
    geen cijfer en woord door elkaar ("twee tot 8") en geen verwijzing naar "deze chat" in een koppeling zonder chat."""
    beschrijvingen = {d["name"]: d["description"] for d in mcp_server.tooldefinities()}

    assert "één specifieke dataset" in beschrijvingen["dataset_details"]
    assert "Vergelijk 2 tot 8 instellingen" in beschrijvingen["vergelijk_instellingen"]
    for naam, tekst in beschrijvingen.items():
        assert "specifiek dataset" not in tekst, naam
        assert "twee tot 8" not in tekst, naam
        assert "deze chat" not in tekst, naam


def test_telling_verwijst_niet_naar_een_chat():
    tekst, _ = mcp_server.voer_uit("dataset_counts", None)

    assert "deze chat" not in tekst


def test_instructies_noemen_de_regel_voor_getallen():
    assert mcp_server.REGEL_GETALLEN in mcp_server.INSTRUCTIES
    assert "bewijs" in mcp_server.INSTRUCTIES and "vervolg" in mcp_server.INSTRUCTIES


def test_zoeken_geeft_hetzelfde_resultaat_als_de_chat():
    argumenten = {"query": "ingeschrevenen hbo", "top_n": 3}
    tekst, fout = mcp_server.voer_uit("search_catalog", argumenten)
    assert not fout
    envelop = json.loads(tekst)
    assert envelop["status"] == "candidates"
    assert envelop["kandidaten"] and all("status" in hit and "dataset_id" in hit for hit in envelop["kandidaten"])
    zonder_herkomst = {k: v for k, v in envelop.items() if k not in ("bewijs", "vervolg")}
    assert zonder_herkomst == mcp_server.ontsmet(json.loads(tools.dispatch("search_catalog", argumenten)[0]))


def test_lege_zoekuitkomst_is_een_resultaat_geen_fout():
    tekst, fout = mcp_server.voer_uit("search_catalog", {"query": "xyzzyq"})
    assert not fout
    assert json.loads(tekst)["status"] == "no_match"


def test_telling_komt_uit_de_catalogus():
    tekst, fout = mcp_server.voer_uit("dataset_counts", None)
    assert not fout
    assert set(json.loads(tekst)["datasets_per_bron"]) == {"CBS", "DUO", "RIO"}


def test_details_lezen_door_het_bronvoorvoegsel_heen():
    tekst, fout = mcp_server.voer_uit("dataset_details", {"dataset_id": "duo:p01hoinges"})
    assert not fout
    assert json.loads(tekst)["status"] == "opvraagbaar"


def test_sessietool_is_niet_beschikbaar():
    tekst, fout = mcp_server.voer_uit("query_data", {"data_key": "cbs_85423NED"})
    assert fout
    assert "query_data" in tekst and "search_catalog" in tekst


@pytest.mark.parametrize(
    ("argumenten", "verwacht"),
    [({}, "verplichte parameter ontbreekt: query"), ({"query": "hbo", "onzin": 1}, "onbekende parameter: onzin")],
)
def test_argumenten_worden_vooraf_tegen_het_schema_getoetst(argumenten, verwacht):
    tekst, fout = mcp_server.voer_uit("search_catalog", argumenten)
    assert fout
    assert verwacht in tekst


def test_toolfout_is_een_fout(monkeypatch):
    def kapot():
        raise RuntimeError("geheim argument")

    monkeypatch.setitem(tools._HANDLERS, "dataset_counts", kapot)
    tekst, fout = mcp_server.voer_uit("dataset_counts", {})
    assert fout
    assert "toolfout" in tekst
    assert "geheim" not in tekst, "de fouttekst citeert de uitzondering niet (#502)"


# ── Bewijs, vervolg en ontsmetting (#707, #709) ─────────────────────────────────────────

RESULTATEN = [
    ("search_catalog", {"query": "gediplomeerden mbo", "top_n": 2}),
    ("search_catalog", {"query": "xyzzyq"}),
    ("dataset_details", {"dataset_id": "cbs:85423NED"}),
    ("dataset_details", {"dataset_id": "duo:p01hoinges"}),
    ("dataset_details", {"dataset_id": "cbs:80040ned"}),
    ("dataset_details", {"dataset_id": "onbekend123"}),
    ("dataset_counts", {}),
]
BEWIJS_SLEUTELS = list(mcp_server.BEWIJS_SLEUTELS)


def _teksten(waarde):
    """Elke tekst in een JSON-waarde, sleutels meegeteld."""
    if isinstance(waarde, str):
        yield waarde
    elif isinstance(waarde, list):
        for w in waarde:
            yield from _teksten(w)
    elif isinstance(waarde, dict):
        for k, w in waarde.items():
            yield k
            yield from _teksten(w)


@pytest.mark.parametrize(("naam", "argumenten"), RESULTATEN)
def test_elk_resultaat_is_een_envelope_met_bewijs_en_vervolg(naam, argumenten):
    tekst, fout = mcp_server.voer_uit(naam, argumenten)
    assert not fout
    envelop = json.loads(tekst)
    assert isinstance(envelop, dict), "er staat geen tekst buiten de JSON"
    assert list(envelop["bewijs"]) == BEWIJS_SLEUTELS
    assert envelop["bewijs"]["versie"] == f"catalogus {tools.catalog.catalogus_digest()}"
    assert envelop["vervolg"]["tekst"] == mcp_server.VERVOLG_TEKST
    assert envelop["vervolg"]["url"].startswith(f"{mcp_server.STANDAARD_APP_URL}/chat")


def test_kwaliteit_hoort_bij_de_vaste_sleutels_van_bewijs():
    """#1248: een nieuwe sleutel achteraan, geen bestaande weg of verplaatst (docs/api.md: stabiel)."""
    assert mcp_server.BEWIJS_SLEUTELS == (
        "bron", "dataset_id", "selectie", "maat", "waarde", "peildatum", "versie", "verwijzing", "kwaliteit",
    )  # fmt: skip


@pytest.mark.parametrize(("naam", "argumenten"), RESULTATEN)
def test_een_catalogustool_heeft_geen_kwaliteit(naam, argumenten):
    """De catalogustools geven metadata, geen getallen uit een bestand: `kwaliteit` staat er als null (#1248)."""
    envelop = json.loads(mcp_server.voer_uit(naam, argumenten)[0])
    assert "kwaliteit" in envelop["bewijs"] and envelop["bewijs"]["kwaliteit"] is None


@pytest.mark.parametrize(("naam", "argumenten"), RESULTATEN)
def test_geen_tekst_die_in_de_client_actief_wordt(naam, argumenten):
    tekst, _ = mcp_server.voer_uit(naam, argumenten)
    actief = [
        t
        for t in _teksten(json.loads(tekst))
        if any(teken in t.replace("\\[", "").replace("\\]", "") for teken in "<>[]")
    ]
    assert actief == []


def test_bewijs_van_een_cbs_tabel_noemt_bron_peildatum_en_verwijzing():
    envelop = json.loads(mcp_server.voer_uit("dataset_details", {"dataset_id": "cbs:85423NED"})[0])
    bewijs = envelop["bewijs"]
    assert bewijs["bron"] == "CBS"
    assert bewijs["dataset_id"] == "85423NED"
    assert bewijs["selectie"] == {"dataset_id": "cbs:85423NED"}
    assert bewijs["peildatum"] == tools.catalog.catalogus_laatste_update("85423NED")
    assert bewijs["verwijzing"] == envelop["documentatie"]["url"]


def test_bewijs_van_een_onbekende_dataset_noemt_geen_bron():
    envelop = json.loads(mcp_server.voer_uit("dataset_details", {"dataset_id": "onbekend123"})[0])
    assert "niet gevonden" in envelop["melding"], "een resultaat in gewone tekst staat in de envelope"
    assert envelop["bewijs"]["bron"] == "catalogus"
    assert envelop["bewijs"]["dataset_id"] is None
    assert envelop["vervolg"]["url"] == f"{mcp_server.STANDAARD_APP_URL}/chat", "geen vraag over een onbekende dataset"


def test_vervolg_neemt_de_zoekvraag_mee_begrensd(monkeypatch):
    monkeypatch.setenv("APP_URL", "https://app.example.nl/")
    lang = "instroom " * 100
    envelop = json.loads(mcp_server.voer_uit("search_catalog", {"query": lang})[0])
    url = urllib.parse.urlsplit(envelop["vervolg"]["url"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://app.example.nl/chat"
    assert url.query == "", "in het fragment, niet in de query: die komt in toegangslogs"
    vraag = urllib.parse.parse_qs(url.fragment)["vraag"][0]
    assert vraag == lang.strip()[: mcp_server.MAX_VRAAG]


def test_vervolg_bij_een_dataset_vraagt_naar_de_cijfers_ervan():
    envelop = json.loads(mcp_server.voer_uit("dataset_details", {"dataset_id": "duo:p01hoinges"})[0])
    vraag = urllib.parse.parse_qs(urllib.parse.urlsplit(envelop["vervolg"]["url"]).fragment)["vraag"][0]
    assert vraag == "Welke cijfers staan er in p01hoinges?"


def test_tekst_van_een_bron_wordt_ontsmet(monkeypatch):
    kwaad = {
        "toelichting": "Zie [hier](https://kwaad.example/x) ![](https://kwaad.example/p.png) <img src=x onerror=alert(1)>",
        "<b>kolom</b>": ["[a]", 3],
    }
    monkeypatch.setitem(tools._HANDLERS, "dataset_counts", lambda: json.dumps(kwaad))
    envelop = json.loads(mcp_server.voer_uit("dataset_counts", {})[0])
    assert envelop["toelichting"] == (
        "Zie \\[hier\\](https://kwaad.example/x) !\\[\\](https://kwaad.example/p.png) &lt;img src=x onerror=alert(1)&gt;"
    )
    assert envelop["&lt;b&gt;kolom&lt;/b&gt;"] == ["\\[a\\]", 3]


def test_een_fout_krijgt_geen_bewijs():
    tekst, fout = mcp_server.voer_uit("search_catalog", {})
    assert fout
    assert "bewijs" not in tekst


# ── Het protocol zelf, over een in-memory verbinding ────────────────────────────────────


def _via_protocol(actie):
    import anyio
    from mcp.client.session import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    async def draai():
        server = mcp_server.maak_server()
        async with (
            create_client_server_memory_streams() as (client_streams, server_streams),
            anyio.create_task_group() as groep,
        ):
            groep.start_soon(server.run, *server_streams, server.create_initialization_options())
            async with ClientSession(*client_streams) as sessie:
                init = await sessie.initialize()
                uitkomst = await actie(sessie)
            groep.cancel_scope.cancel()
        return init, uitkomst

    return anyio.run(draai)


def test_protocol_noemt_naam_versie_en_instructies():
    init, _ = _via_protocol(lambda sessie: sessie.list_tools())
    assert init.server_info.name == "onderwijscatalogus"
    assert init.server_info.version == app_versie(os.getenv("APP_VERSION"))
    assert "search_catalog" in (init.instructions or "")


def test_protocol_volgt_het_versielabel_van_version(monkeypatch):
    """#1105: met APP_VERSION de release, zonder een ontwikkellabel dat nooit een release is (HTTP en stdio)."""
    monkeypatch.setenv("APP_VERSION", "2.8.1-rc.3033+406a4f57")
    init, _ = _via_protocol(lambda sessie: sessie.list_tools())
    assert init.server_info.version == "2.8.1-rc.3033+406a4f57"

    monkeypatch.delenv("APP_VERSION")
    init, _ = _via_protocol(lambda sessie: sessie.list_tools())
    assert "+dev" in init.server_info.version
    assert init.server_info.version == mcp_server._versie()


def test_protocol_toont_de_tools_met_hun_schema():
    _, resultaat = _via_protocol(lambda sessie: sessie.list_tools())
    per_naam = {t.name: t for t in resultaat.tools}
    assert list(per_naam) == CATALOGUS + DATATOOLS
    for definitie in mcp_server.tooldefinities():
        assert per_naam[definitie["name"]].input_schema == definitie["input_schema"]


def test_protocol_voert_een_zoekactie_uit():
    _, resultaat = _via_protocol(lambda sessie: sessie.call_tool("search_catalog", {"query": "ingeschrevenen hbo"}))
    assert not resultaat.is_error
    envelop = json.loads(resultaat.content[0].text)
    assert envelop["kandidaten"]
    assert list(envelop["bewijs"]) == BEWIJS_SLEUTELS
    assert envelop["vervolg"]["url"].startswith(mcp_server.STANDAARD_APP_URL)


def test_protocol_markeert_een_sessietool_als_fout():
    _, resultaat = _via_protocol(lambda sessie: sessie.call_tool("query_data", {"data_key": "x"}))
    assert resultaat.is_error
    assert "query_data" in resultaat.content[0].text


# ── Bronregels als prompt en resource (#1249) ───────────────────────────────────────────


def test_bronregels_noemen_de_vaste_gebruiksregels():
    from tools import kernvragen

    tekst = mcp_server.bronregels_tekst()

    assert mcp_server.REGEL_GETALLEN in tekst
    assert "reken niet zelf" in tekst.lower()
    assert "`bewijs.versie`" in tekst
    assert "ondergrens" in tekst and kernvragen.ondergrens_zin() in tekst
    assert "niet dat de data niet bestaat" in tekst, "een miss is geen 'bestaat niet'"
    assert "`no_match`" in tekst and "`niet_gevonden`" in tekst and "`ontbrekende_schooljaren`" in tekst


def test_bronregels_noemen_de_domeinregels_met_hun_eigen_tekst():
    """Onderdrukte cel = ondergrens, DT = deeltijd, vestiging is niet woonplaats: de tekst uit data/domeinregels.toml."""
    from core import domeinregels

    regels = domeinregels.laad()
    tekst = mcp_server.bronregels_tekst()

    assert regels.sentinel.betekenis in tekst
    assert "DT = deeltijd" in tekst and "VT = voltijd" in tekst and "DU = duaal" in tekst
    for regel in regels.herkomst_is_vestiging:
        assert regel.melding in tekst


def test_elke_domeinregel_staat_in_de_bronregels_of_is_uitgezonderd():
    """Een nieuwe regel in data/domeinregels.toml die de tekst niet noemt, laat deze test falen, tot hij in de tekst
    komt of met een reden in BRONREGELS_UITGEZONDERD staat."""
    from core import domeinregels

    regels = domeinregels.laad()
    assert mcp_server.ontbrekende_domeinregels(regels) == []
    ids = {regel.id for regel in regels.alle()}
    assert set(mcp_server.BRONREGELS_UITGEZONDERD) <= ids, "een uitzondering voor een regel die er niet meer is"
    tekst = mcp_server.bronregels_tekst(regels)
    for regel_id, reden in mcp_server.BRONREGELS_UITGEZONDERD.items():
        assert f"`{regel_id}`" not in tekst, regel_id
        assert reden.strip(), regel_id


def test_een_nieuwe_domeinregel_buiten_de_datatools_valt_op():
    """De bewaking zelf: een kolomcorrectie voor een bestand dat de datatools niet laden, komt niet vanzelf in de tekst
    en is dan een ontbrekende regel; een voor een bestand dat ze wel laden, staat er meteen in."""
    import dataclasses
    from datetime import date

    from core import domeinregels

    regels = domeinregels.laad()

    def met(regel_id: str, dataset: str) -> domeinregels.Domeinregels:
        nieuw = domeinregels.Kolomcorrectie(
            id=regel_id, bron="test", gecontroleerd=date(2026, 11, 26), datasets=(dataset,), kolom="X", definitie="Y"
        )
        return dataclasses.replace(regels, kolomcorrecties=(*regels.kolomcorrecties, nieuw))

    assert mcp_server.ontbrekende_domeinregels(met("nieuw-p04", "p04hogdipl")) == ["nieuw-p04"]
    assert mcp_server.ontbrekende_domeinregels(met("nieuw-p01", "p01hoinges")) == []
    assert "`nieuw-p01`" in mcp_server.bronregels_tekst(met("nieuw-p01", "p01hoinges"))


def test_bronregels_hebben_geen_tekst_die_in_de_client_actief_wordt():
    tekst = mcp_server.bronregels_tekst()
    assert not any(teken in tekst.replace("\\[", "").replace("\\]", "") for teken in "<>[]")


def test_instructies_verwijzen_naar_de_prompt_bronregels():
    assert "`bronregels`" in mcp_server.INSTRUCTIES
    assert mcp_server.BRONREGELS_URI in mcp_server.INSTRUCTIES


def test_protocol_noemt_prompt_en_resource_bronregels():
    async def lijsten(sessie):
        return await sessie.list_prompts(), await sessie.list_resources()

    _, (prompts, resources) = _via_protocol(lijsten)
    assert [p.name for p in prompts.prompts] == ["bronregels"]
    assert [(r.name, r.uri) for r in resources.resources] == [("bronregels", "onderwijsdata://bronregels")]


def test_protocol_geeft_dezelfde_tekst_als_prompt_en_als_resource():
    async def lees(sessie):
        return await sessie.get_prompt("bronregels"), await sessie.read_resource("onderwijsdata://bronregels")

    _, (prompt, resource) = _via_protocol(lees)
    assert [m.content.text for m in prompt.messages] == [mcp_server.bronregels_tekst()]
    assert [c.text for c in resource.contents] == [mcp_server.bronregels_tekst()]


@pytest.mark.parametrize("actie", ["prompt", "resource"])
def test_protocol_weigert_een_onbekende_prompt_of_resource(actie):
    from mcp.shared.exceptions import MCPError

    async def vraag(sessie):
        if actie == "prompt":
            return await sessie.get_prompt("iets-anders")
        return await sessie.read_resource("onderwijsdata://iets-anders")

    with pytest.raises((MCPError, ExceptionGroup)):
        _via_protocol(vraag)


# ── Resultaatgrootte over HTTP (#940) ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "vulling", ["x", '"', "\\", "é", "\n"], ids=["kaal", "aanhalingsteken", "backslash", "accent", "regel"]
)
@pytest.mark.parametrize("grens", [600, 1000, 5000])
def test_begrens_blijft_onder_de_grens_ook_als_escapen_de_tekst_langer_maakt(vulling, grens):
    tekst, _ = mcp_server.voer_uit("dataset_counts", {})
    envelop = json.loads(tekst) | {"veld": vulling * 20000}
    begrensd = mcp_server.begrens(json.dumps(envelop, ensure_ascii=False), grens)
    assert len(begrensd) <= grens
    uit = json.loads(begrensd)
    assert uit["bewijs"] == envelop["bewijs"] and uit["vervolg"] == envelop["vervolg"]
    assert uit["begin"], "er blijft een begin over"


def test_begrens_laat_een_klein_resultaat_ongemoeid():
    tekst, _ = mcp_server.voer_uit("dataset_counts", {})
    assert mcp_server.begrens(tekst, len(tekst)) == tekst
