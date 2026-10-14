"""Server-side preflight op het CBS-contract (#370, AC3 en AC5): codes, periode en sector vóór de datacall.

Het contract (`onderwijsdata.validate_selection`) is hier een nep: per (dimensie, code) of periode-jaar
een oordeel in de vorm die de package teruggeeft. De oordelen hieronder zijn letterlijk wat de package
op 14-10-2026 voor 85423NED gaf.
"""

import json
from unittest.mock import patch

import pytest
from onderwijsdata.contract import DatasetNietGevonden

from tools import cbs_preflight
from tools.cbs import get_cbs_data
from tools.cbs_preflight import eisen, preflight
from tools.cbs_selectie import compileer

_COL_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Onderwijssoort": {"type": "Dimension", "title": "Onderwijssoort"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "TotaalIngeschrevenen_1": {"type": "Topic", "title": "Totaal ingeschrevenen"},
}


def _oordeel(status: str, *checks: dict) -> dict:
    return {"dataset_id": "cbs:85423NED", "status": status, "checks": list(checks)}


_GOED = _oordeel("supported", {"veld": "dimensiecode", "status": "supported", "reden": None})
_ONBEKEND = _oordeel(
    "unknown", {"veld": "dimensiecode", "status": "unknown", "reden": "codes alleen live te verifiëren"}
)
_ONGELDIGE_CODE = _oordeel(
    "unsupported",
    {
        "veld": "dimensiecode",
        "status": "unsupported",
        "reden": "'XXXX' is geen geldige code van Geslacht",
        "fout": "ongeldige_code",
        "dimensie": "Geslacht",
        "herstel": [],
    },
)
_ONGELDIGE_PERIODE = _oordeel(
    "unsupported",
    {
        "veld": "periode",
        "status": "unsupported",
        "reden": "periode 2031SJ00 komt niet voor in deze tabel",
        "fout": "ongeldige_periode",
        "herstel": ["2023SJ00", "2024SJ00", "2025SJ00"],
    },
)
_HBO_MET_WO_CODE = _oordeel(
    "unsupported",
    {"veld": "sector", "status": "supported", "reden": None, "sector": "hbo", "dimensie": "Onderwijssoort"},
    {"veld": "dimensiecode", "status": "supported", "reden": None, "dimensie": "Onderwijssoort", "code": "A025297"},
    {
        "veld": "samenhang",
        "status": "unsupported",
        "reden": "tegenstrijdige waarden voor Onderwijssoort: sector hbo (Onderwijssoort=A025294) vs Onderwijssoort='A025297'",
        "fout": "tegenstrijdige_selectie",
        "dimensie": "Onderwijssoort",
        "herstel": ["A025294", "A025297"],
    },
)


class _Contract:
    """Een nep-contract: een oordeel per (dimensie, code) of ('periode', jaar); de rest is supported."""

    def __init__(self, **oordelen):
        self.oordelen = oordelen
        self.gevraagd: list[dict] = []

    @staticmethod
    def _sleutel(eis: dict) -> str:
        if "periode" in eis:
            return f"periode_{eis['periode']['jaar']}"
        ((dimensie, code),) = eis.get("dimensies", {"sector": eis.get("sector")}).items()
        return f"{dimensie}_{code}"

    def __call__(self, dataset_id: str, eis: dict, live: bool = False) -> dict:
        assert live, "de preflight toetst live: codes en perioden staan alleen in de dimensietabellen"
        self.gevraagd.append(eis)
        return self.oordelen.get(self._sleutel(eis), _GOED)


def _selectie(**wijzigingen) -> dict:
    basis = {"dimensies": {"Geslacht": "T001038", "Onderwijssoort": "A025294"}, "periode": ["2024/25"]}
    return {**basis, **wijzigingen}


def _laden(selectie: dict, contract) -> tuple[str, bool]:
    """get_cbs_data met nep-metadata en nep-data; (resultaat, of de datacall is gedaan)."""
    rij = {"Geslacht": "T001038", "Onderwijssoort": "A025294", "Perioden": "2024SJ00", "TotaalIngeschrevenen_1": 10}
    with (
        patch("tools.cbs.definitions", return_value=_COL_DEFS),
        patch("tools.cbs.data", return_value=[rij]) as datacall,
        patch.object(cbs_preflight, "validate_selection", contract),
    ):
        return get_cbs_data("85423NED", selectie=selectie), datacall.called


# --- de eisen aan het contract -------------------------------------------------------------------


def test_een_eis_per_code_lijsten_uitgesplitst_en_ster_overgeslagen():
    selectie = {"dimensies": {"Geslacht": ["T001038", "3000"], "Opleidingsfase": "*", "RegioS": " 4000 "}}
    assert eisen(selectie, "Perioden") == [
        {"dimensies": {"Geslacht": "T001038"}},
        {"dimensies": {"Geslacht": "3000"}},
        {"dimensies": {"RegioS": "4000"}},
    ]


def test_periode_als_schooljaar_jaar_of_code_van_de_tijddimensie():
    assert eisen({"periode": ["2024/25", "2020JJ00", "2024KW01"]}, "Perioden") == [
        {"periode": {"type": "jaar", "jaar": 2020}},
        {"dimensies": {"Perioden": "2024KW01"}},
        {"periode": {"type": "schooljaar", "jaar": 2024}},
    ]
    assert eisen({"periode": {"van": "2023/24", "tot": "2024/25"}}, "Perioden") == [
        {"periode": {"type": "schooljaar", "jaar": 2023}},
        {"periode": {"type": "schooljaar", "jaar": 2024}},
    ]
    assert eisen({"periode": "*"}, "Perioden") == []


def test_de_sector_gaat_met_elke_eis_mee_en_staat_anders_alleen():
    assert eisen({"sector": "hbo", "dimensies": {"Onderwijssoort": "A025297"}}, "Perioden") == [
        {"sector": "hbo", "dimensies": {"Onderwijssoort": "A025297"}}
    ]
    assert eisen({"sector": "hbo", "dimensies": {"Onderwijssoort": "*"}}, "Perioden") == [{"sector": "hbo"}]
    assert eisen({"dimensies": {"Onderwijssoort": "*"}, "periode": "*"}, "Perioden") == []


# --- het oordeel ---------------------------------------------------------------------------------


def test_een_ongeldige_code_wordt_geweigerd_zonder_datacall():
    resultaat, geladen = _laden(
        _selectie(dimensies={"Geslacht": "XXXX", "Onderwijssoort": "*"}), _Contract(Geslacht_XXXX=_ONGELDIGE_CODE)
    )
    assert not geladen
    assert "geweigerd door het CBS-contract" in resultaat
    assert "'XXXX' is geen geldige code van Geslacht" in resultaat


def test_hbo_met_een_wo_code_is_tegenstrijdig():
    """AC3: hbo + Onderwijssoort=A025297 (wo) komt niet tot de datacall; de weigering noemt beide codes."""
    contract = _Contract(Onderwijssoort_A025297=_HBO_MET_WO_CODE)
    resultaat, geladen = _laden(
        _selectie(sector="hbo", dimensies={"Geslacht": "*", "Onderwijssoort": "A025297"}), contract
    )
    assert not geladen
    assert "tegenstrijdige waarden voor Onderwijssoort" in resultaat
    assert "A025294" in resultaat and "A025297" in resultaat
    assert all(eis.get("sector") == "hbo" for eis in contract.gevraagd)


def test_een_periode_buiten_de_tabel_noemt_de_perioden_die_er_wel_zijn():
    resultaat, geladen = _laden(_selectie(periode=["2031/32"]), _Contract(periode_2031=_ONGELDIGE_PERIODE))
    assert not geladen
    assert "2031SJ00 komt niet voor" in resultaat
    assert "wel in de tabel: 2023SJ00, 2024SJ00, 2025SJ00" in resultaat


def test_een_passende_selectie_laadt_en_elke_code_is_gevraagd():
    contract = _Contract()
    resultaat, geladen = _laden(_selectie(), contract)
    assert geladen
    assert "data_key" in json.loads(resultaat)
    assert contract.gevraagd == [
        {"dimensies": {"Geslacht": "T001038"}},
        {"dimensies": {"Onderwijssoort": "A025294"}},
        {"periode": {"type": "schooljaar", "jaar": 2024}},
    ]


@pytest.mark.parametrize(
    "contract",
    [
        _Contract(Geslacht_T001038=_ONBEKEND),
        lambda dataset_id, eis, live=False: (_ for _ in ()).throw(DatasetNietGevonden(dataset_id)),
        lambda dataset_id, eis, live=False: (_ for _ in ()).throw(ConnectionError("bron weg")),
    ],
    ids=["unknown", "onbekende tabel", "bronuitval"],
)
def test_geen_oordeel_laat_de_selectie_door(contract):
    """Bronuitval of een tabel die het contract niet kent is geen onvolledige selectie."""
    _, geladen = _laden(_selectie(), contract)
    assert geladen


def test_bronuitval_in_het_log_zonder_de_fouttekst(caplog):
    def kapot(dataset_id, eis, live=False):
        raise ConnectionError("https://bron/85423NED?$filter=trim(Geslacht) eq 'T001038'")

    caplog.set_level("WARNING", logger="tools.cbs_preflight")
    with patch.object(cbs_preflight, "validate_selection", kapot):
        assert preflight("85423NED", _selectie(), _COL_DEFS) is None
    (regel,) = [r.getMessage() for r in caplog.records if r.name == "tools.cbs_preflight"]
    assert "ConnectionError" in regel and "T001038" not in regel


def test_de_weigering_bundelt_redenen_zonder_dubbelen():
    contract = _Contract(Geslacht_XXXX=_ONGELDIGE_CODE, Geslacht_YYYY=_ONGELDIGE_CODE, periode_2031=_ONGELDIGE_PERIODE)
    selectie = {"dimensies": {"Geslacht": ["XXXX", "YYYY"]}, "periode": ["2031/32"]}
    with patch.object(cbs_preflight, "validate_selection", contract):
        weigering = preflight("85423NED", selectie, _COL_DEFS)
    assert weigering is not None
    assert weigering.count("geen geldige code van Geslacht") == 1
    assert "2031SJ00 komt niet voor" in weigering


# --- wat vóór het contract al vaststaat ----------------------------------------------------------


def test_een_tijddimensie_naast_periode_komt_niet_tot_het_contract():
    """AC5: de tegenstrijdige periode (periode én Perioden) weigert de selectiepoort al, zonder datacall."""
    contract = _Contract()
    selectie = _selectie(
        dimensies={"Geslacht": "*", "Onderwijssoort": "*", "Perioden": "2022SJ00"}, periode=["2023/24"]
    )
    resultaat, geladen = _laden(selectie, contract)
    assert not geladen and not contract.gevraagd
    assert "periode" in resultaat


def test_een_sector_buiten_mbo_hbo_wo_wordt_geweigerd():
    fout = compileer("85423NED", _selectie(sector="po"), _COL_DEFS)
    assert isinstance(fout, str)
    assert "'sector' is 'mbo', 'hbo' of 'wo'" in fout
