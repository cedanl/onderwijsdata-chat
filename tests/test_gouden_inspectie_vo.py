"""Gouden test voor get_inspectieoordeel_vo op bevroren bronnen, zonder netwerk (#881, in de stijl van #870).

Bronnen, op 03-11-2026 live opgehaald met `scripts/gouden_testfixtures.py` (URL's in `tests/fixtures/gouden/bronnen.json`):
- Onderwijsinspectie, 20261102-oordeel-en-standaard-po-so-vo.ods (peildatum 01-11-2026), gefilterd op de vo-vestigingen
  in de gemeente Utrecht volgens DUO, plus de eerste drie po- en so-rijen van het bestand;
- DUO, Adressen van vestigingen in het voortgezet onderwijs (vestigingenvo.csv), gefilterd op GEMEENTENAAM UTRECHT.

Nagerekend buiten de tool om, met pandas en odfpy op de bevroren bestanden:
    df = pd.read_excel(ods, engine="odf", dtype=str); v = pd.read_csv(csv_gz, dtype=str)
    df["code"] = df.BRIN + df.Vestiging
    m = df[(df.Sector == "VO") & df.OVTNaam.isin(["HAVO", "VWO"])].merge(v, left_on="code", right_on="VESTIGINGSCODE")
    m.groupby(["OVTNaam", "KwaliteitOnderwijs"]).size(); m.code.nunique()
  HAVO  Geen eindoordeel 8, Onvoldoende 3, Voldoende 4;  VWO  Geen eindoordeel 10, Voldoende 3;  17 vestigingen.
  14OY00 Gerrit Rietveld College        HAVO Onvoldoende 20260706, VWO Geen eindoordeel
  00RO00 Amadeus Lyceum voor Vwo Havo Mavo (VLEUTEN)  HAVO en VWO Voldoende 20260609
  24TR03 Nuovo Scholen, ... - X11 media en vormgeving  HAVO Voldoende 20260209 (geen VWO)
De po- en so-rijen in het bestand: De Bolster (SO, Zeer zwak), WereldWijs, basisschool De Maasparel, De Morgenster (PO),
Bergse Veld School, SO Kiem (SO).
"""

import json

import pytest

import tools
from agent.bronvermelding import bronnen_van
from scripts import gouden_testfixtures as g
from tests.test_inspectie_vo import DOORSTROOMVRAAG
from tools import inspectie, inspectie_vo
from tools.ho_markers import beurtvraag
from tools.schemas import TOOL_GET_INSPECTIEOORDEEL_VO

pytestmark = pytest.mark.usefixtures("gouden")

_PO_SO = ("De Bolster", "WereldWijs", "De Maasparel", "De Morgenster", "Bergse Veld School", "SO Kiem")


def _doorstroomvraag(**args) -> tuple[str, dict]:
    with beurtvraag(DOORSTROOMVRAAG):
        tekst, _ = tools.dispatch(TOOL_GET_INSPECTIEOORDEEL_VO, {"gemeente": "Utrecht", **args})
    uit = json.loads(tekst)
    assert isinstance(uit, dict), tekst
    return tekst, uit


def test_de_havo_en_vwo_afdelingen_in_utrecht():
    _, uit = _doorstroomvraag(onderwijssoorten=["havo", "vwo"])

    assert uit["telling"] == {
        "havo": {"Onvoldoende": 3, "Voldoende": 4, "Geen eindoordeel": 8},
        "vwo": {"Voldoende": 3, "Geen eindoordeel": 10},
    }
    assert uit["vestigingen_totaal"] == len(uit["vestigingen"]) == 17
    per_code = {v["vestiging"]: v for v in uit["vestigingen"]}
    assert per_code["14OY00"]["afdelingen"] == {"havo": "Onvoldoende (06-07-2026)", "vwo": "Geen eindoordeel"}
    assert per_code["00RO00"] == {
        "naam": "Amadeus Lyceum voor Vwo Havo Mavo",
        "vestiging": "00RO00",
        "plaats": "Vleuten",
        "afdelingen": {"havo": "Voldoende (09-06-2026)", "vwo": "Voldoende (09-06-2026)"},
    }
    assert per_code["24TR03"]["afdelingen"] == {"havo": "Voldoende (09-02-2026)"}
    assert uit["peildatum"] == uit["bron"]["peildatum"] == "01-11-2026"
    assert uit["bron"]["url"].endswith("20261102-oordeel-en-standaard-po-so-vo.ods")


def test_de_po_en_so_rijen_van_het_bestand_komen_niet_in_het_resultaat():
    rijen = inspectie.lees_ods((g.MAP / g.INSPECTIE_VO).read_bytes())
    assert {r["Sector"] for r in rijen} == {"PO", "SO", "VO"}  # het bevroren bestand heeft ze wel

    tekst, uit = _doorstroomvraag()
    for naam in _PO_SO:
        assert naam not in tekst
    assert set(uit["telling"]) == set(inspectie_vo.ONDERWIJSSOORTEN.values())  # alle zes vo-afdelingen in Utrecht
    assert sum(sum(t.values()) for t in uit["telling"].values()) == 58  # de 58 vo-rijen van het bevroren bestand


def test_het_etiket_in_het_resultaat_en_de_bronnen():
    tekst, uit = _doorstroomvraag(onderwijssoorten=["vwo"])

    assert uit["context"] == inspectie_vo.ETIKET
    assert bronnen_van([(TOOL_GET_INSPECTIEOORDEEL_VO, tekst)]) == [
        "Onderwijsinspectie · Oordelen per school (po/so/vo), vo-context voor vervolgonderwijs, peildatum 01-11-2026"
    ]


def test_zonder_doorstroomvraag_weigert_de_tool_ook_op_de_echte_bestanden():
    with beurtvraag("Wat is het inspectieoordeel van ROC Midden Nederland?"):
        tekst, _ = tools.dispatch(TOOL_GET_INSPECTIEOORDEEL_VO, {"gemeente": "Utrecht"})
    assert tekst == inspectie_vo.POORT_DICHT
