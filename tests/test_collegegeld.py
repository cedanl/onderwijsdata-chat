"""Het wettelijk collegegeld per studiejaar komt uit een vaste tabel met de wettekst als bron (#729).

Het model onthoudt of berekent geen bedrag: het kiest het studiejaar, de code geeft precies één bedragenpaar met
de wetsversie. Het instellingscollegegeld is geen open data, en dat zegt de tool zelf.
"""

import json
from datetime import date

import pytest

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from agent.citaties import citaties
from agent.grounding import bewijs_getallen
from agent.meetwaarden import meetwaarden
from scripts import bronping
from tools import collegegeld
from tools.schemas import TOOL_GET_COLLEGEGELD, TOOL_SCHEMAS

_VANDAAG = date(2026, 11, 3)

# Nagelezen in artikel 9 van BWBR0024005 op wetten.overheid.nl, per studiejaar in de genoemde versie ("geldend van"):
# (volledig, gedeeltelijk minimum, gedeeltelijk maximum, versie).
_WETTEKST = {
    2023: (2314, 1377, 2314, "01-09-2024"),
    2024: (2530, 1506, 2530, "01-09-2025"),
    2025: (2601, 1548, 2601, "18-09-2026"),
    2026: (2694, 1604, 2694, "18-09-2026"),
    2027: (2771, 1650, 2771, "01-09-2027"),
}


def _uit(**kwargs) -> dict:
    return json.loads(collegegeld.get_collegegeld(vandaag=_VANDAAG, **kwargs))


@pytest.mark.parametrize("startjaar", sorted(_WETTEKST))
def test_per_studiejaar_precies_een_bedragenpaar_uit_de_wettekst(startjaar):
    volledig, minimum, maximum, versie = _WETTEKST[startjaar]
    uit = _uit(studiejaar=startjaar)

    assert uit["studiejaar"] == f"{startjaar}/{startjaar + 1}"
    assert uit["voltijd"]["bedrag_euro"] == volledig
    assert (uit["deeltijd_en_duaal"]["minimum_euro"], uit["deeltijd_en_duaal"]["maximum_euro"]) == (minimum, maximum)
    assert uit["bron"]["versie"] == versie and uit["bron"]["opgehaald"] == "03-11-2026"
    assert uit["bron"]["url"].startswith(f"https://wetten.overheid.nl/BWBR0024005/{versie[6:]}-{versie[3:5]}-")


def test_de_tabel_dekt_alleen_wat_in_de_wettekst_staat():
    assert {b.startjaar for b in collegegeld.TABEL} == set(_WETTEKST)
    for b in collegegeld.TABEL:
        # In artikel 9 is het maximum van het gedeeltelijke bedrag het volledige bedrag.
        assert b.gedeeltelijk_min < b.gedeeltelijk_max == b.volledig


def test_zonder_studiejaar_het_lopende_studiejaar():
    assert _uit()["studiejaar"] == "2026/2027"
    vlak_voor_september = json.loads(collegegeld.get_collegegeld(vandaag=date(2026, 8, 31)))
    assert vlak_voor_september["studiejaar"] == "2025/2026"


@pytest.mark.parametrize("spelling", ["2025", "2025/26", "2025-2026", "2025/2026"])
def test_een_studiejaar_in_elke_spelling(spelling):
    assert _uit(studiejaar=spelling)["voltijd"]["bedrag_euro"] == 2601


def test_een_studiejaar_buiten_de_tabel_geeft_geen_bedrag():
    uit = collegegeld.get_collegegeld(studiejaar=2019, vandaag=_VANDAAG)

    assert not uit.startswith("{") and "2019/2020" in uit and "Noem geen bedrag" in uit
    assert not {"2314", "2530", "2601", "2694", "2771"} & set(bewijs_getallen(uit))
    assert collegegeld.GEEN_OPEN_BRON in uit


def test_geen_studiejaar_geeft_een_melding():
    uit = collegegeld.get_collegegeld(studiejaar="volgend jaar", vandaag=_VANDAAG)
    assert not uit.startswith("{") and "geen studiejaar" in uit


def test_het_instellingscollegegeld_heeft_geen_open_bron():
    assert "instellingscollegegeld" in _uit()["geen_open_bron"]
    assert "geen open bron" in _uit()["geen_open_bron"]


def test_een_toekomstige_versie_krijgt_een_noot_tot_ze_geldt():
    assert any("vastgestelde wijziging" in n and "01-09-2027" in n for n in _uit(studiejaar=2027)["noot"])
    later = json.loads(collegegeld.get_collegegeld(studiejaar=2027, vandaag=date(2027, 9, 2)))
    assert "noot" not in later


def test_tot_en_met_2023_een_noot_over_verlaagd_collegegeld():
    assert any("verlaagd" in n for n in _uit(studiejaar=2023)["noot"])
    assert "noot" not in _uit(studiejaar=2024)


def test_de_bedragen_zijn_bewijs_voor_de_getalcontrole():
    assert {"2694", "1604"} <= bewijs_getallen(collegegeld.get_collegegeld(studiejaar=2026, vandaag=_VANDAAG))


def test_de_tool_staat_in_de_dispatch_en_de_wettekst_onder_het_antwoord():
    uit, _ = tools.dispatch(TOOL_GET_COLLEGEGELD, {"studiejaar": 2026})
    stap = (TOOL_GET_COLLEGEGELD, uit)

    regel = (
        "wetten.nl · Regeling financiën hoger onderwijs (BWBR0024005), artikel 9, versie van 18-09-2026, "
        "opgehaald op 03-11-2026"
    )
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: "https://wetten.overheid.nl/BWBR0024005/2026-09-18#Paragraaf5_Artikel9"}
    assert TOOL_GET_COLLEGEGELD in tools.LABELS
    schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_COLLEGEGELD)
    assert "geen open bron" in schema["description"] and "geheugen" in schema["description"]


def test_de_bron_ping_wordt_rood_als_het_lopende_studiejaar_ontbreekt():
    ping = next(p for p in bronping.PINGS if p.id == "collegegeld-tabel")
    assert ping.bron == "collegegeld"

    assert bronping.beoordeel(ping, collegegeld.get_collegegeld(vandaag=_VANDAAG)).ok
    rood = bronping.beoordeel(ping, collegegeld.get_collegegeld(vandaag=date(2028, 9, 1)))
    assert not rood.ok and "2028/2029" in rood.detail


# --- #970: de bedragen als meetwaarden, met citatie en export ---------------------------------------------------------

# Een beurt die ook andere data laadde: zonder vertaler kregen de bedragen "herkomst niet vastgesteld" en liet de
# CSV-export van de citaties ze weg (frontend/src/citatieCsv.js neemt alleen vastgestelde citaties).
_ANDERE_DATA = (
    "query_data",
    json.dumps(
        {"data_key": "duo:p01hoinges:1:abc", "rijen": [{"INSTELLINGSNAAM": "Hogeschool Utrecht", "AANTAL": 37218}]}
    ),
)


def _stappen(studiejaar: int = 2026) -> list[tuple[str, str]]:
    return [_ANDERE_DATA, (TOOL_GET_COLLEGEGELD, collegegeld.get_collegegeld(studiejaar=studiejaar, vandaag=_VANDAAG))]


def test_de_bedragen_zijn_getypeerde_meetwaarden_met_studiejaar_vorm_en_wettekst():
    waarden = meetwaarden(collegegeld.get_collegegeld(studiejaar=2026, vandaag=_VANDAAG), TOOL_GET_COLLEGEGELD)

    per_maat = {(w.maat, w.selectie): w for w in waarden}
    assert len(waarden) == 3
    voltijd = per_maat[("Volledig wettelijk collegegeld", ("Studiejaar: 2026/2027", "Vorm: voltijd"))]
    assert "2694" in voltijd.cijfers and voltijd.eenheid == "€"
    assert (
        voltijd.bron == "wetten.nl, Regeling financiën hoger onderwijs (BWBR0024005), artikel 9, versie van 18-09-2026"
    )
    deeltijd = ("Studiejaar: 2026/2027", "Vorm: deeltijd", "Vorm: duaal")
    assert "1604" in per_maat[("Gedeeltelijk wettelijk collegegeld", (*deeltijd, "Bedrag: minimum"))].cijfers
    assert "2694" in per_maat[("Gedeeltelijk wettelijk collegegeld", (*deeltijd, "Bedrag: maximum"))].cijfers


def test_de_bedragen_krijgen_een_vastgestelde_citatie_naast_andere_data():
    tekst = (
        "Hogeschool Utrecht telt 37.218 studenten.\n"
        "Het volledig wettelijk collegegeld voor voltijd is in 2026/2027 € 2.694.\n"
        "Voor deeltijd en duaal ligt het gedeeltelijk wettelijk collegegeld tussen € 1.604 en € 2.694."
    )

    gevonden = citaties(tekst, _stappen())

    assert [(c["getal"], c["vastgesteld"]) for c in gevonden] == [
        ("37.218", True),
        ("2.694", True),
        ("1.604", True),
        ("2.694", True),
    ]
    _, voltijd, minimum, maximum = gevonden
    assert voltijd["maat"] == "Volledig wettelijk collegegeld" and "Vorm: voltijd" in voltijd["selectie"]
    assert "Bedrag: minimum" in minimum["selectie"] and "Bedrag: maximum" in maximum["selectie"]
    assert all(c["tool"] == TOOL_GET_COLLEGEGELD and "BWBR0024005" in c["bron"] for c in gevonden[1:])
    assert all(c["eenheid"] == "€" for c in gevonden[1:])


def test_een_bedrag_in_een_zin_zonder_vorm_blijft_twijfel():
    """Het maximum is in de wet het volledige bedrag: zonder voltijd of deeltijd in de zin kiest de code niet."""
    [citatie] = citaties("Het bedrag is € 2.694.", _stappen())
    assert citatie == {"getal": "2.694", "vastgesteld": False, "reden": "meerdere"}


def test_een_melding_zonder_bedrag_geeft_geen_meetwaarde():
    assert meetwaarden(collegegeld.get_collegegeld(studiejaar=2019, vandaag=_VANDAAG), TOOL_GET_COLLEGEGELD) == []
