"""Wat het model aan de CBS-tools meegeeft, en wat het terugkrijgt als het net naast de interface zit (#891, #892).

Testrapport §4.1 van !756: `sector` stond vijf keer naast `selectie` in plaats van erin en gaf een kale TypeError;
en `get_cbs_dimension` kende de leesbare dimensienaam uit dataset_details niet. Alles zonder netwerk of model.
"""

import json
from unittest.mock import patch

import pytest

from tools import cbs, cbs_preflight, dispatch, fouten
from tools.cbs import get_cbs_data, get_cbs_dimension
from tools.cbs_selectie import dimensiesleutel

_GEHEIM = "geheime-waarde-9f3c"

_COL_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "GeboortelandOuders": {"type": "Dimension", "title": "Geboorteland (ouders)"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "Gediplomeerden_1": {"type": "Topic", "title": "Gediplomeerden"},
}
_RIJ = {"Geslacht": "T001038", "GeboortelandOuders": "T001638", "Perioden": "2024SJ00", "Gediplomeerden_1": 10}
_DIMENSIES = {"Geslacht": "T001038", "GeboortelandOuders": "T001638"}
_OORDEEL = {"dataset_id": "cbs:85357NED", "status": "supported", "checks": []}


@pytest.fixture(autouse=True)
def _zonder_cache():
    cbs._dimension_rows.cache_clear()
    yield
    cbs._dimension_rows.cache_clear()


# ── #891: `sector` naast `selectie` ──────────────────────────────────────────────────────────────────────


def _laad(*, selectie: dict, **extra) -> tuple[str, list[dict]]:
    """get_cbs_data met nep-metadata en nep-data; (resultaat, de eisen die het contract kreeg)."""
    eisen: list[dict] = []

    def contract(dataset_id: str, eis: dict, live: bool = False) -> dict:
        eisen.append(eis)
        return _OORDEEL

    with (
        patch("tools.cbs.scope_blokkade", return_value=None),
        patch("tools.cbs.definitions", return_value=_COL_DEFS),
        patch("tools.cbs.data", return_value=[_RIJ]),
        patch.object(cbs_preflight, "validate_selection", contract),
    ):
        return get_cbs_data("85357NED", selectie=selectie, **extra), eisen


def _selectie(**wijzigingen) -> dict:
    return {"dimensies": dict(_DIMENSIES), "periode": ["2024/25"], **wijzigingen}


def test_sector_op_het_hoogste_niveau_geeft_dezelfde_uitkomst_als_sector_in_selectie():
    binnen, eisen_binnen = _laad(selectie=_selectie(sector="mbo"))
    buiten, eisen_buiten = _laad(selectie=_selectie(), sector="mbo")

    assert buiten == binnen
    assert fouten.code(buiten) is None, buiten
    assert eisen_buiten == eisen_binnen
    assert eisen_buiten and {eis["sector"] for eis in eisen_buiten} == {"mbo"}  # de sector bereikte het contract


def test_staat_sector_op_beide_plekken_dan_wint_selectie():
    wint, _ = _laad(selectie=_selectie(sector="hbo"))
    gemengd, eisen = _laad(selectie=_selectie(sector="hbo"), sector="mbo")

    assert gemengd == wint
    assert eisen and {eis["sector"] for eis in eisen} == {"hbo"}


def test_sector_op_het_hoogste_niveau_verandert_de_selectie_van_de_aanroeper_niet():
    selectie = _selectie()
    _laad(selectie=selectie, sector="mbo")

    assert "sector" not in selectie


def test_een_ongeldige_sector_op_het_hoogste_niveau_krijgt_dezelfde_weigering_als_in_selectie():
    binnen, _ = _laad(selectie=_selectie(sector="po"))
    buiten, _ = _laad(selectie=_selectie(), sector="po")

    assert buiten == binnen
    assert "'sector' is 'mbo', 'hbo' of 'wo'" in buiten


def test_een_onbekend_argument_noemt_de_naam_en_zegt_waar_het_hoort_en_geeft_de_waarde_niet_terug():
    result, _ = dispatch("get_cbs_data", {"dataset_id": "85357NED", "periode": _GEHEIM, "selectie": {"dimensies": {}}})

    assert fouten.code(result) == "toolfout", result
    assert "`periode`" in result
    assert "hoort binnen `selectie`" in result
    assert _GEHEIM not in result


def test_een_echt_onbekend_argument_noemt_de_naam_en_de_toegestane_argumenten():
    result, _ = dispatch("get_cbs_dimension", {"dataset_id": "85357NED", "dimension_name": "Geslacht", "jaar": _GEHEIM})

    assert fouten.code(result) == "toolfout", result
    assert "`jaar`" in result
    assert "dataset_id" in result and "dimension_name" in result
    assert "hoort binnen" not in result
    assert _GEHEIM not in result


def test_een_argumentnaam_die_geen_naam_is_wordt_niet_teruggegeven():
    vreemd = f"x; {_GEHEIM} {'y' * 80}"
    result, _ = dispatch("get_cbs_dimension", {"dataset_id": "85357NED", "dimension_name": "Geslacht", vreemd: 1})

    assert fouten.code(result) == "toolfout", result
    assert _GEHEIM not in result


# ── #892: de leesbare dimensienaam uit dataset_details ───────────────────────────────────────────────────


def _bron(dimensie: str):
    if dimensie == "GeboortelandOuders":
        return [{"Key": "T001638 ", "Title": "Totaal", "Description": ""}]
    raise RuntimeError("CBS weigerde de aanvraag (HTTP 404)")


def _dimensie(naam: str) -> str:
    with (
        patch("tools.cbs.scope_blokkade", return_value=None),
        patch("tools.cbs.definitions", return_value=_COL_DEFS),
        patch("tools.cbs.get", side_effect=lambda _id, dimensie: _bron(dimensie)),
    ):
        return get_cbs_dimension("85357NED", naam)


@pytest.mark.parametrize(
    "naam", ["GeboortelandOuders", "Geboorteland (ouders)", "geboorteland (ouders)", "geboortelandouders"]
)
def test_get_cbs_dimension_kent_de_naam_zoals_dataset_details_hem_toont(naam):
    result = _dimensie(naam)

    assert fouten.code(result) is None, result
    assert json.loads(result) == {"T001638": "Totaal"}


def test_get_cbs_dimension_met_een_echt_onbekende_naam_noemt_de_beschikbare_dimensies():
    result = _dimensie("Bestaat niet")

    assert fouten.code(result) == "bron_fout", result
    assert "GeboortelandOuders" in result


def test_de_dimensiesleutel_volgt_sleutel_of_titel_en_alleen_bij_een_dimensie():
    assert dimensiesleutel(_COL_DEFS, "Geboorteland (ouders)") == "GeboortelandOuders"
    assert dimensiesleutel(_COL_DEFS, " GESLACHT ") == "Geslacht"
    assert dimensiesleutel(_COL_DEFS, "Perioden") == "Perioden"  # ook de tijddimensie: get_cbs_dimension kent haar
    assert dimensiesleutel(_COL_DEFS, "Gediplomeerden") is None  # een onderwerp is geen dimensie
    assert dimensiesleutel(_COL_DEFS, "Bestaat niet") is None
    assert dimensiesleutel({}, "Geslacht") is None
