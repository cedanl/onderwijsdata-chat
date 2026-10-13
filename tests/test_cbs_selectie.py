"""Gesloten selectieschema voor CBS (#343): het model kiest codes, de server bouwt OData.

De volledigheidspoort weigert een selectie waarin een dimensie noch gepind noch
bewust uitgesplitst is, vóór er een datacall de deur uitgaat.
"""

import json
from unittest.mock import patch

from tools import store
from tools.cbs import get_cbs_data
from tools.cbs_selectie import compileer

_COL_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Opleidingsfase": {"type": "Dimension", "title": "Opleidingsfase"},
    "RegioS": {"type": "Dimension", "title": "Regio's"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "TotaalIngeschrevenen_1": {"type": "Topic", "title": "Totaal ingeschrevenen"},
}


def _params(uitkomst) -> dict:
    """Narrowing voor ty: compileer geeft een dict, anders faalt de test met de weigering."""
    assert isinstance(uitkomst, dict), uitkomst
    return uitkomst


def _selectie(**wijzigingen) -> dict:
    """Een volledige selectie als basis; tests variëren er één aspect van."""
    basis = {
        "dimensies": {"Geslacht": "T001038", "Opleidingsfase": "*", "RegioS": "*"},
        "periode": ["2024/25"],
    }
    return {**basis, **wijzigingen}


# --- compileren ---------------------------------------------------------------


def test_volledige_selectie_compileert_naar_filter():
    params = _params(compileer("85423NED", _selectie(), _COL_DEFS))
    assert params == {"$filter": "trim(Geslacht) eq 'T001038' and trim(Perioden) eq '2024SJ00'"}


def test_meerdere_codes_worden_een_of_groep():
    params = _params(
        compileer(
            "85423NED",
            _selectie(dimensies={"Geslacht": "*", "Opleidingsfase": "*", "RegioS": ["PV21", "PV20"]}),
            _COL_DEFS,
        )
    )
    assert params["$filter"] == "(trim(RegioS) eq 'PV20' or trim(RegioS) eq 'PV21') and trim(Perioden) eq '2024SJ00'"


def test_periodebereik_wordt_een_lijst_codes():
    params = _params(compileer("85423NED", _selectie(periode={"van": "2020/21", "tot": "2022/23"}), _COL_DEFS))
    assert (
        "(trim(Perioden) eq '2020SJ00' or trim(Perioden) eq '2021SJ00' or trim(Perioden) eq '2022SJ00')"
        in params["$filter"]
    )


def test_periodecode_gaat_ongemoeid_door():
    params = _params(compileer("85423NED", _selectie(periode=["2024JJ00"]), _COL_DEFS))
    assert "trim(Perioden) eq '2024JJ00'" in params["$filter"]


def test_ster_overal_is_geen_filter():
    selectie = _selectie(dimensies={"Geslacht": "*", "Opleidingsfase": "*", "RegioS": "*"}, periode="*")
    assert compileer("85423NED", selectie, _COL_DEFS) == {}


def test_onderwerpen_worden_select():
    params = _params(compileer("85423NED", _selectie(onderwerpen=["TotaalIngeschrevenen_1"]), _COL_DEFS))
    assert params["$select"] == "TotaalIngeschrevenen_1"


def test_quote_in_code_wordt_ontsnapt():
    params = _params(
        compileer("85423NED", _selectie(dimensies={"Geslacht": "a'b", "Opleidingsfase": "*", "RegioS": "*"}), _COL_DEFS)
    )
    assert "trim(Geslacht) eq 'a''b'" in params["$filter"]


# --- volledigheidspoort en vocabulaire -----------------------------------------


def test_onvolledige_selectie_noemt_de_ontbrekende_dimensies():
    fout = compileer("85423NED", {"dimensies": {"Geslacht": "T001038"}}, _COL_DEFS)
    assert isinstance(fout, str)
    assert "Opleidingsfase" in fout and "RegioS" in fout and "periode" in fout
    assert "85423NED" in fout


def test_onbekende_dimensie_noemt_de_beschikbare():
    fout = compileer("85423NED", _selectie(dimensies={"Geslcht": "x", "Opleidingsfase": "*", "RegioS": "*"}), _COL_DEFS)
    assert isinstance(fout, str)
    assert "Geslcht" in fout and "Geslacht" in fout


def test_tijddimensie_hoort_in_periode():
    selectie = _selectie(dimensies={"Geslacht": "*", "Opleidingsfase": "*", "RegioS": "*", "Perioden": "2024SJ00"})
    fout = compileer("85423NED", selectie, _COL_DEFS)
    assert isinstance(fout, str)
    assert "periode" in fout


def test_onbekende_periodespelling_wordt_geweigerd():
    fout = compileer("85423NED", _selectie(periode=["ooit"]), _COL_DEFS)
    assert isinstance(fout, str)
    assert "ooit" in fout


def test_onbekende_sleutel_in_selectie_noemt_de_toegestane():
    fout = compileer("85423NED", {"dims": {"Geslacht": "x"}}, _COL_DEFS)
    assert isinstance(fout, str)
    assert "dimensies" in fout and "periode" in fout and "onderwerpen" in fout


def test_lege_codelijst_wordt_geweigerd():
    fout = compileer("85423NED", _selectie(dimensies={"Geslacht": [], "Opleidingsfase": "*", "RegioS": "*"}), _COL_DEFS)
    assert isinstance(fout, str)
    assert "Geslacht" in fout


def test_zonder_metadata_geen_poort_wel_compilatie():
    """Bronuitval op DataProperties blokkeert het laden niet: compileren wat er is, Perioden als tijddimensie."""
    params = _params(compileer("85423NED", {"dimensies": {"Geslacht": "T001038"}, "periode": ["2024/25"]}, None))
    assert params == {"$filter": "trim(Geslacht) eq 'T001038' and trim(Perioden) eq '2024SJ00'"}


# --- get_cbs_data met selectie --------------------------------------------------


def _mock_data(dataset_id, **params):
    return [{"Geslacht": "T001038", "Perioden": "2024SJ00", "TotaalIngeschrevenen_1": 10}]


def test_onvolledige_selectie_doet_geen_datacall():
    with (
        patch("tools.cbs.definitions", return_value=_COL_DEFS),
        patch("tools.cbs.data", side_effect=_mock_data) as datacall,
    ):
        resultaat = get_cbs_data("85423NED", selectie={"dimensies": {"Geslacht": "T001038"}})

    assert not datacall.called
    assert "Opleidingsfase" in resultaat


def test_selectie_laadt_en_bewaart_het_gecompileerde_recept():
    with (
        patch("tools.cbs.definitions", return_value=_COL_DEFS),
        patch("tools.cbs.data", side_effect=_mock_data),
    ):
        resultaat = json.loads(get_cbs_data("85423NED", selectie=_selectie()))

    known = store.meta(resultaat["data_key"])
    assert known is not None and known.laad is not None
    tool, args = known.laad
    assert tool == "get_cbs_data"
    assert args["filters"] == {"$filter": "trim(Geslacht) eq 'T001038' and trim(Perioden) eq '2024SJ00'"}


def test_zelfde_selectie_in_andere_spelling_deelt_de_key():
    with (
        patch("tools.cbs.definitions", return_value=_COL_DEFS),
        patch("tools.cbs.data", side_effect=_mock_data),
    ):
        r1 = json.loads(get_cbs_data("85423NED", selectie=_selectie(periode=["2024/25"])))
        r2 = json.loads(get_cbs_data("85423NED", selectie=_selectie(periode=["2024SJ00"])))

    assert r1["data_key"] == r2["data_key"]


def test_selectie_die_geen_dict_is_wordt_uitgelegd():
    with patch("tools.cbs.definitions", return_value=_COL_DEFS):
        resultaat = get_cbs_data("85423NED", selectie="Geslacht eq 'T001038'")  # ty: ignore[invalid-argument-type]

    assert "selectie" in resultaat and "dimensies" in resultaat


# --- opgevulde sleutels ----------------------------------------------------------

# CBS vult de sleutels van een dimensie op tot één breedte: naast 'T001038' staat '4000   '.
# De feed en get_cbs_dimension tonen ze gestript; een filter op de kale code matcht dan niets.
_MBO_RIJEN = [
    {"Geslacht": "T001038", "Perioden": "2021SJ00", "MboStudenten_1": 512100},
    {"Geslacht": "3000   ", "Perioden": "2021SJ00", "MboStudenten_1": 263160},
    {"Geslacht": "4000   ", "Perioden": "2021SJ00", "MboStudenten_1": 248930},
]
_MBO_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "MboStudenten_1": {"type": "Topic", "title": "Mbo-studenten"},
}


def _cbs_feed(dataset_id, **params):
    """De CBS-feed in het klein: `trim(Dim) eq 'x'` vergelijkt gestript, `Dim eq 'x'` de ruwe sleutel."""

    def klopt(rij, clausule):
        kolom, _, waarde = clausule.partition(" eq ")
        waarde = waarde.strip("'")
        if kolom.startswith("trim(") and kolom.endswith(")"):
            return str(rij[kolom[5:-1]]).strip() == waarde
        return rij[kolom] == waarde

    clausules = str(params.get("$filter") or "").split(" and ")
    rijen = [r for r in _MBO_RIJEN if all(klopt(r, c) for c in clausules if c)]
    return [{k: v.strip() if isinstance(v, str) else v for k, v in r.items()} for r in rijen]


def test_een_korte_code_naast_een_langere_geeft_rijen():
    """F-10 (#531): 'Alleen vrouwen' op 85353NED gaf 'geen rijen' terwijl CBS 248.930 publiceert."""
    with patch("tools.cbs.definitions", return_value=_MBO_DEFS), patch("tools.cbs.data", side_effect=_cbs_feed):
        resultaat = json.loads(
            get_cbs_data("85353NED", selectie={"dimensies": {"Geslacht": "4000"}, "periode": ["2021/22"]})
        )

    assert "Geen rijen" not in json.dumps(resultaat)
    assert store.get(resultaat["data_key"])["MboStudenten_1"].tolist() == [248930]


def test_de_feed_in_het_klein_geeft_zonder_trim_niets():
    """De proef bewijst alleen iets als de nagebootste feed het echte gedrag vertoont."""
    assert _cbs_feed("85353NED", **{"$filter": "Geslacht eq '4000' and Perioden eq '2021SJ00'"}) == []
    assert len(_cbs_feed("85353NED", **{"$filter": "trim(Geslacht) eq '4000' and Perioden eq '2021SJ00'"})) == 1


# --- modelinterface --------------------------------------------------------------


def test_modelschema_biedt_geen_odata_meer():
    from tools.schemas import TOOL_GET_CBS_DATA, TOOL_SCHEMAS

    schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_CBS_DATA)
    eigenschappen = schema["parameters"]["properties"]
    assert "filters" not in eigenschappen
    assert "selectie" in eigenschappen
