"""De vergelijkingsgroep van het dashboard ook in de chat (#1267), met dezelfde peerregels en terugval.

"Hoe doen wij het ten opzichte van vergelijkbare instellingen?" liet het model zelf peers kiezen. De tool
`vergelijkingsgroep` geeft de groep van Mijn instelling uit dezelfde functie als het dashboard (`data/dashboard.py`):
dezelfde peers, dezelfde regio-trede, dezelfde terugval en hetzelfde peergemiddelde. Een eigen groep kan, en dan zegt de
zin uit code dat het niet de dashboardgroep is.

Op de bevroren DUO-bestanden (`duo_fixtures`) voor een hogeschool, een universiteit en een mbo-instelling, en op een
verzonnen register voor de terugval onder drie peers met cijfers.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from agent import controlestappen
from agent.onder_antwoord import KOP_GROEP
from data import dashboard
from tools import LABELS, dispatch
from tools.schemas import TOOL_SCHEMAS, TOOL_VERGELIJKINGSGROEP
from tools.vergelijkingsgroep import vergelijkingsgroep

_met_duo = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")
_INSTELLINGEN = [("Hogeschool Utrecht", "hbo"), ("Universiteit Utrecht", "wo"), ("Curio", "mbo")]


def _chat(instelling: str, **args) -> dict:
    uit = json.loads(vergelijkingsgroep(instelling, **args))
    assert "peers" in uit, uit
    return uit


# --- 19. dezelfde peers als het dashboard -----------------------------------------------------------------------------


@_met_duo
@pytest.mark.parametrize(("instelling", "soort"), _INSTELLINGEN)
def test_de_chat_geeft_dezelfde_peers_regio_en_terugval_als_het_dashboard(instelling, soort):
    bm = dashboard.load_dashboard_regio(instelling)["benchmark"]
    chat = _chat(instelling)

    dashboardpeers = set(bm["peers"]["ingeschrevenen"]) | set(bm.get("geen_gegevens", {}).get("ingeschrevenen", []))
    assert {p["naam"] for p in chat["peers"]} == dashboardpeers
    assert (chat["regio_trede"], chat["regio"], chat["terugval"]) == (
        bm["regio_type"],
        bm["regio_naam"],
        bm["terugval"],
    )
    assert chat["groep"] == "dashboard"
    # Per peer naam, code en waarom hij erin zit: hetzelfde type, de regio en de omvangsdrempel.
    for peer in chat["peers"]:
        assert peer["code"] and peer["reden"].startswith(dashboard._SOORTNAAM[soort][0])
        assert "ten minste 10% van de eigen omvang" in peer["reden"]


# --- 21. hetzelfde peergemiddelde; een eigen groep zegt dat ------------------------------------------------------------


@_met_duo
@pytest.mark.parametrize(("instelling", "soort"), _INSTELLINGEN)
def test_chat_en_dashboard_geven_hetzelfde_peergemiddelde_per_jaar(instelling, soort):
    bm = dashboard.load_dashboard_regio(instelling)["benchmark"]
    chat = _chat(instelling)

    per_jaar = {int(r["Schooljaar"][:4]): r["Peergemiddelde ingeschrevenen"] for r in chat["rijen"]}
    assert per_jaar and per_jaar == bm["ingeschrevenen"]
    assert {int(r["Schooljaar"][:4]): r["Peers met cijfers"] for r in chat["rijen"]} == bm["n_per_jaar"][
        "ingeschrevenen"
    ]


@_met_duo
def test_een_eigen_groep_is_niet_de_dashboardgroep():
    # Een eigen groep blijft binnen het onderwijstype van de bestanden (ho: hbo en wo); een mbo-instelling kan niet mee.
    chat = _chat(
        "Hogeschool Utrecht", eigen_groep=["Hogeschool van Amsterdam", "Universiteit Utrecht", "Curio", "Bestaat Niet"]
    )

    assert chat["groep"] == "eigen"
    assert [p["naam"] for p in chat["peers"]] == ["Hogeschool van Amsterdam", "Universiteit Utrecht"]
    assert all(p["reden"] == "gekozen door de gebruiker" for p in chat["peers"])
    assert "niet de dashboardgroep" in chat["zin"]
    assert chat["ander_type"] == ["Curio"] and chat["onbekend"] == ["Bestaat Niet"]
    # Het peergemiddelde rekent dezelfde reeksfunctie als het dashboard, over de gekozen peers.
    assert all(r["Peers met cijfers"] <= 2 for r in chat["rijen"])
    regel = controlestappen.met_regels("Antwoord.", controlestappen.Controles(groepen=[chat["zin"]]))
    assert regel.endswith(f"{KOP_GROEP} {chat['zin']}")


# --- 22. de groep in een vaste zin uit code ---------------------------------------------------------------------------


@_met_duo
def test_het_antwoord_noemt_de_groep_in_een_vaste_zin_onder_het_antwoord():
    chat = _chat("Hogeschool Utrecht")

    assert chat["zin"] == (
        "Vergeleken met de dashboardgroep van Mijn instelling: 3 hogescholen landelijk, van hetzelfde type en met ten "
        "minste 10% van de eigen omvang; terugval: te weinig hogescholen in provincie Utrecht (1 andere)."
    )
    stap = (TOOL_VERGELIJKINGSGROEP, json.dumps(chat))
    assert controlestappen.groepzinnen([stap]) == [chat["zin"]]
    tekst = controlestappen.met_regels(
        "De HU is groter dan het gemiddelde.", controlestappen.Controles(groepen=[chat["zin"]])
    )
    assert tekst.splitlines()[-1] == f"{KOP_GROEP} {chat['zin']}"


# --- 23. onder drie peers met cijfers volgt de chat de terugval van het dashboard -------------------------------------


@pytest.fixture
def klein_register(monkeypatch):
    """Vier hogescholen in één arbeidsmarktregio, van wie maar één peer cijfers heeft."""
    registry = [
        {"naam": n, "instellingscode": c, "type": "hbo"}
        for n, c in (("Eigen", "EE"), ("B", "BB"), ("C", "CC"), ("D", "DD"))
    ]
    adres = {c: {"provincie": "Utrecht", "arbeidsmarktregio": "Midden-Utrecht"} for c in ("EE", "BB", "CC", "DD")}
    rijen = [
        (jaar, code, naam, n)
        for jaar in (2023, 2024)
        for code, naam, n in (("EE", "Eigen", 1000), ("BB", "B", 500), ("CC", "C", 0), ("DD", "D", 0))
    ]
    inges = pd.DataFrame(
        rijen, columns=["STUDIEJAAR", "INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL", "AANTAL_INGESCHREVENEN"]
    )
    inges = inges.assign(GESLACHT="VROUW", ONDERDEEL="Techniek", PROVINCIENAAM="Utrecht")
    ej = inges.rename(columns={"AANTAL_INGESCHREVENEN": "AANTAL_EERSTEJAARS_INGESCHREVENEN"})
    dipl = inges.rename(columns={"STUDIEJAAR": "DIPLOMAJAAR", "AANTAL_INGESCHREVENEN": "AANTAL_GEDIPLOMEERDEN"})
    monkeypatch.setattr(dashboard, "get_all_instellingen", lambda: registry)
    monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: adres)
    monkeypatch.setattr(dashboard, "_omvang_per_code", lambda _type: {})  # geen omvang: geen omvangsdrempel
    monkeypatch.setattr(dashboard, "_load_ho_full", lambda: (inges, ej, dipl))
    monkeypatch.setattr(dashboard, "resolve_alias", lambda naam: naam)


def test_onder_drie_peers_met_cijfers_geen_gemiddelde_zoals_het_dashboard(klein_register):
    chat = _chat("Eigen")

    assert {p["code"] for p in chat["peers"]} == {"BB", "CC", "DD"}
    assert chat["te_weinig_peers"] == dashboard.TE_WEINIG_PEERS
    assert all("Peergemiddelde ingeschrevenen" not in r for r in chat["rijen"])
    assert (
        "minder dan 3 peers cijfers: het dashboard toont dan geen gemiddelde, en dit antwoord ook niet" in chat["zin"]
    )
    assert "1 hogeschool in arbeidsmarktregio Midden-Utrecht" in chat["zin"]
    assert "Zonder cijfers en dus niet in het gemiddelde: C, D." in chat["zin"]


# --- de tool zelf -----------------------------------------------------------------------------------------------------


def test_de_tool_staat_in_het_schema_met_een_label_en_weigert_een_onbekende_instelling(monkeypatch):
    functie = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_VERGELIJKINGSGROEP)["function"]
    assert functie["parameters"]["required"] == ["instelling"]
    assert "vergelijkbare instellingen" in functie["description"] and "Mijn instelling" in functie["description"]
    assert TOOL_VERGELIJKINGSGROEP in LABELS

    monkeypatch.setattr(dashboard, "vergelijkingsgroep", lambda *a, **k: None)
    melding, _ = dispatch(TOOL_VERGELIJKINGSGROEP, {"instelling": "Bestaat Niet"})
    assert melding.startswith("Onbekende instelling")
    melding, _ = dispatch(TOOL_VERGELIJKINGSGROEP, {"instelling": "HU", "peers": ["x"]})
    assert "peers" in melding  # een onbekend argument: het model vult de groep niet zelf aan


def test_de_prompt_stuurt_vergelijkbare_instellingen_naar_de_tool():
    prompt = (Path(__file__).resolve().parents[1] / "prompts" / "system.md").read_text(encoding="utf-8")
    assert TOOL_VERGELIJKINGSGROEP in prompt and "vergelijkbare instellingen" in prompt


def test_de_eval_vraagt_de_tool_met_must_call():
    evals = json.loads((Path(__file__).resolve().parent / "e2e" / "evaluations.json").read_text(encoding="utf-8"))
    (ev,) = [e for e in evals["evaluations"] if e["label"] == "vergelijkingsgroep-chat"]
    assert ev["expected"]["must_call"] == [TOOL_VERGELIJKINGSGROEP] and ev.get("instelling")
    assert "vergelijk" in ev["message"].lower() and "vergelijkbare instellingen" in ev["message"].lower()
