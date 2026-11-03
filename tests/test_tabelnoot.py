"""Onder een tabel met "niet beschikbaar"-cellen staat wat -1 betekent, uit code (#811, besluit C).

Mobiel N39: een DUO-selectie met onderdrukte cellen gaf een tabel met "niet beschikbaar", zonder totaal in de tekst.
De Ondergrens-regel van het Telling-blok rust op de getallen in de tekst (#414) en verscheen dus niet, en nergens
stond waarom die cellen leeg waren.
"""

import importlib
import json

import pandas as pd
import pytest

from agent.loop import LoopResult
from agent.tabelnoot import NOTEN, met_tabelnoot
from core.sentinels import BETEKENIS, CBS_BETEKENIS
from tools import store
from tools.query import query_data
from tools.schemas import TOOL_QUERY_DATA
from tools.store import KeyMeta

_BRON = "duo:p02ho1ejrs:0"

# Een antwoord dat alleen een tabel toont: geen totaal, dus geen getal waarop een Ondergrens-regel kan rusten.
_TABEL = (
    "Eerstejaars per opleiding bij de instelling:\n"
    "\n"
    "| Opleiding | 2023/2024 | 2024/2025 |\n"
    "|---|---:|---:|\n"
    "| Rechtsgeleerdheid | 412 | 398 |\n"
    "| Sterrenkunde | niet beschikbaar | 21 |\n"
    "\n"
    "Sterrenkunde groeit licht."
)


@pytest.fixture(autouse=True)
def _bron():
    store.clear()
    df = pd.DataFrame(
        {
            "OPLEIDINGSNAAM": ["Rechtsgeleerdheid", "Rechtsgeleerdheid", "Sterrenkunde", "Sterrenkunde"],
            "STUDIEJAAR": [2023, 2024, 2023, 2024],
            "AANTAL": [412, 398, -1, 21],
        }
    )
    store.put(_BRON, df, KeyMeta(bron="duo", dataset="p02ho1ejrs"))
    yield
    store.clear()


def _selectie() -> str:
    """Het toolresultaat van query_data, zoals de chat het krijgt: de -1 is gemaskeerd en de rij staat er als null."""
    uit = query_data(_BRON, filters={"OPLEIDINGSNAAM": ["Rechtsgeleerdheid", "Sterrenkunde"]})
    assert '"AANTAL":null' in uit
    return uit


def test_de_noot_staat_direct_onder_de_tabel_met_de_betekenis_van_min_een():
    tekst = met_tabelnoot(_TABEL, [_selectie()])

    regels = tekst.split("\n")
    laatste_rij = regels.index("| Sterrenkunde | niet beschikbaar | 21 |")
    assert regels[laatste_rij + 1 : laatste_rij + 4] == ["", NOTEN["duo"], ""]
    assert BETEKENIS in NOTEN["duo"] and "-1" in NOTEN["duo"]
    # De tekst onder de tabel blijft staan, na de noot.
    assert tekst.endswith("Sterrenkunde groeit licht.")


def test_ook_zonder_totaal_in_de_tekst_en_naast_het_telling_blok():
    run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie
    result = LoopResult(text=_TABEL, steps=[(TOOL_QUERY_DATA, _selectie())])

    tekst = run_module._antwoordtekst(result, result.text, [], [])

    assert NOTEN["duo"] in tekst
    assert tekst.index("| Sterrenkunde |") < tekst.index(NOTEN["duo"]) < tekst.index("Sterrenkunde groeit licht.")


@pytest.mark.parametrize("cel", ["niet beschikbaar", "–", "-", "", "-1", "n.b.", "*niet beschikbaar*", "<5"])
def test_elke_schrijfwijze_van_een_lege_cel_krijgt_de_noot(cel):
    tabel = f"| Opleiding | 2023 |\n|---|---|\n| Sterrenkunde | {cel} |"
    assert met_tabelnoot(tabel, [_selectie()]).endswith(f"\n\n{NOTEN['duo']}")


def test_geen_noot_zonder_lege_cel_in_de_tabel():
    tabel = "| Opleiding | 2024/2025 |\n|---|---:|\n| Sterrenkunde | 21 |"
    assert met_tabelnoot(tabel, [_selectie()]) == tabel


def test_geen_noot_zonder_onderdrukte_cel_in_de_beurt():
    schoon = query_data(_BRON, filters={"OPLEIDINGSNAAM": "Rechtsgeleerdheid"})
    assert met_tabelnoot(_TABEL, [schoon]) == _TABEL
    assert met_tabelnoot(_TABEL, []) == _TABEL


def test_geen_noot_bij_een_tabel_in_een_codeblok():
    tekst = "```\n| a | b |\n|---|---|\n| x | niet beschikbaar |\n```"
    assert met_tabelnoot(tekst, [_selectie()]) == tekst


def test_een_tweede_keer_verwerken_geeft_geen_tweede_noot():
    eenmaal = met_tabelnoot(_TABEL, [_selectie()])
    assert met_tabelnoot(eenmaal, [_selectie()]) == eenmaal


def test_onder_elke_tabel_met_een_lege_cel():
    tweede = "| Jaar | Aantal |\n|---|---|\n| 2023 | 412 |"
    tekst = met_tabelnoot(f"{_TABEL}\n\n{tweede}\n\n{_TABEL}", [_selectie()])
    assert tekst.count(NOTEN["duo"]) == 2
    assert f"| 2023 | 412 |\n\n{NOTEN['duo']}" not in tekst


def test_een_lege_cbs_cel_krijgt_de_woorden_van_cbs():
    store.put(
        "cbs:85701NED",
        pd.DataFrame({"Perioden": ["2023SJ00", "2024SJ00"], "Studenten_1": [None, 120.0]}),
        KeyMeta(bron="cbs", dataset="85701NED"),
    )
    uit = query_data("cbs:85701NED", filters={"Perioden": ["2023SJ00", "2024SJ00"]})
    assert json.loads(uit)["data_key"] != "cbs:85701NED"

    tekst = met_tabelnoot("| Jaar | Studenten |\n|---|---|\n| 2023/24 | niet beschikbaar |", [uit])

    assert tekst.endswith(f"\n\n{NOTEN['cbs']}") and CBS_BETEKENIS in NOTEN["cbs"]
    assert NOTEN["duo"] not in tekst
