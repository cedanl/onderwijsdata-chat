"""Relatielaag stap 1 (#63): sleutels die bronnen delen, als tool; koppelt niets."""

import json
import logging
from unittest.mock import patch

import pandas as pd
import pytest

from tools import relaties as rel
from tools import store
from tools.relaties import norm_gemeente, norm_provincie, norm_schooljaar, relatie

_DUO = pd.DataFrame(
    {
        "STUDIEJAAR": [2021, 2022, 2022],
        "INSTELLINGSCODE_ACTUEEL": ["21PK", "21PK", "99ZZ"],
        "INSTELLINGSNAAM_ACTUEEL": ["Fontys", "Fontys", "Onbekend"],
        "GEMEENTENUMMER": [855, 855, 34],
        "GEMEENTENAAM": ["Tilburg", "Tilburg", "Almere"],
        "PROVINCIENAAM": ["Noord-Brabant", "Noord-Brabant", "Flevoland"],
        "AANTAL": [100, 120, 5],
    }
)
_CBS = pd.DataFrame(
    {
        "RegioS": ["GM0855", "GM0034", "GM0344"],
        "RegioS_label": ["Tilburg", "Almere", "Utrecht"],
        "Perioden": ["2022SJ00", "2022SJ00", "2022SJ00"],
        "TotaalIngeschrevenen_1": [1, 2, 3],
    }
)
_REGISTER = [{"naam": "Fontys", "instellingscode": "21PK"}, {"naam": "Avans", "instellingscode": "25BE"}]


def _put(key: str, df: pd.DataFrame) -> None:
    store.put(key, df, store.KeyMeta(bron="test", dataset=key))


@pytest.fixture(autouse=True)
def _register():
    with patch("tools.relaties.instellingen.get_all", return_value=_REGISTER):
        yield


# --- vertaling van waarden ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("waarde", "verwacht"),
    [
        ("GM0344", "0344"),
        ("gm0344", "0344"),
        (344, "0344"),
        ("344.0", "0344"),
        (" 34 ", "0034"),
        ("Utrecht", None),
        (None, None),
    ],
)
def test_gemeente_wordt_vier_cijfers(waarde, verwacht):
    assert norm_gemeente(waarde) == verwacht


@pytest.mark.parametrize(
    ("waarde", "verwacht"),
    [
        ("PV26", "PV26"),
        ("Utrecht", "PV26"),
        ("noord-brabant", "PV30"),
        ("Fryslân", "PV21"),
        ("PV99", None),
        ("Elders", None),
    ],
)
def test_provincie_wordt_cbs_code(waarde, verwacht):
    assert norm_provincie(waarde) == verwacht


@pytest.mark.parametrize(
    ("waarde", "verwacht"),
    [
        (2021, "2021"),
        ("2021/2022", "2021"),
        ("2021/22", "2021"),
        ("2015/'16", "2015"),
        ("2021SJ00", "2021"),
        ("2021JJ00", None),
        ("x", None),
        (3000, None),
    ],
)
def test_schooljaar_wordt_startjaar(waarde, verwacht):
    assert norm_schooljaar(waarde) == verwacht


# --- sleutels van één tabel -----------------------------------------------------------------------


def test_sleutels_op_naam_en_wat_eraan_hangt():
    _put("duo:t", _DUO)
    uit = json.loads(relatie("duo:t"))
    per = {s["kolom"]: s for s in uit["sleutels"]}
    assert list(per) == [
        "STUDIEJAAR",
        "INSTELLINGSCODE_ACTUEEL",
        "INSTELLINGSNAAM_ACTUEEL",
        "GEMEENTENUMMER",
        "GEMEENTENAAM",
        "PROVINCIENAAM",
    ]
    assert uit["zonder_sleutel"] == ["AANTAL"]
    code = per["INSTELLINGSCODE_ACTUEEL"]
    assert (code["sleutel"], code["basis"], code["confidence"], code["uniek"]) == (
        "instellingscode",
        "handmatig",
        1.0,
        2,
    )
    assert code["dekking"] == {"naslag": "instellingsregister", "bekend": 1, "van": 2}  # 99ZZ staat er niet in
    assert any("get_rio_instelling" in k for k in code["koppelt_aan"])
    assert per["GEMEENTENUMMER"]["dekking"] == {"naslag": "arbeidsmarktregio-indeling", "bekend": 2, "van": 2}
    assert per["PROVINCIENAAM"]["dekking"] == {"naslag": "CBS-provinciecodes", "bekend": 2, "van": 2}
    assert per["INSTELLINGSNAAM_ACTUEEL"]["confidence"] == 0.8


def test_cbs_regios_wordt_aan_de_waarden_herkend_en_een_kalenderjaar_niet_als_schooljaar():
    _put("cbs:t", _CBS.assign(Perioden=["2022JJ00"] * 3))
    uit = json.loads(relatie("cbs:t"))
    per = {s["kolom"]: s for s in uit["sleutels"]}
    assert per["RegioS"]["sleutel"] == "gemeente" and per["RegioS"]["uniek"] == 3
    assert (
        per["Perioden"]["sleutel"] == "schooljaar" and per["Perioden"]["uniek"] == 0
    )  # op naam, maar geen schooljaren
    assert "TotaalIngeschrevenen_1" in uit["zonder_sleutel"]
    _put("cbs:pv", pd.DataFrame({"RegioS": ["PV26", "PV30"], "N": [1, 2]}))
    assert json.loads(relatie("cbs:pv"))["sleutels"][0]["sleutel"] == "provincie"


# Een echte CBS-regiotabel (85701NED, gemeten 3 nov 2026) mengt in één kolom Nederland (NL), landsdelen (LD),
# provincies (PV), COROP-gebieden (CR) en gemeenten (GM): 446 van de 510 waarden waren gemeenten.
_REGIOS_GEMENGD = ["NL01", "LD03", "PV30", "PV26", "CR35", "GM0855", "GM0034", "GM0344", "GM0363", "GM0599", "GM0014"]
_CBS_GEMENGD = pd.DataFrame(
    {
        "Regiokenmerken": _REGIOS_GEMENGD,
        "Perioden": ["2024SJ00"] * len(_REGIOS_GEMENGD),
        "LeerlingenStudenten_1": range(len(_REGIOS_GEMENGD)),
    }
)


def test_gemengde_cbs_regiokolom_is_de_gemeentesleutel_met_alleen_de_gemeenten():
    _put("cbs:mix", _CBS_GEMENGD)
    per = {s["kolom"]: s for s in json.loads(relatie("cbs:mix"))["sleutels"]}
    regio = per["Regiokenmerken"]
    assert regio["sleutel"] == "gemeente"
    assert regio["uniek"] == 6  # Nederland, landsdeel, provincie en COROP zijn geen gemeente
    assert regio["dekking"]["van"] == 6


def test_koppeling_duo_cbs_vindt_de_gemeente_in_een_gemengde_regiokolom():
    _put("duo:t", _DUO)
    _put("cbs:mix", _CBS_GEMENGD)
    uit = json.loads(relatie("duo:t", andere_key="cbs:mix"))
    per = {(k["links"]["kolom"], k["rechts"]["kolom"]): k for k in uit["koppelingen"]}
    gemeente = per[("GEMEENTENUMMER", "Regiokenmerken")]
    assert gemeente["sleutel"] == "gemeente" and gemeente["type"] == "many_to_one"
    assert gemeente["overlap"] == {"gedeeld": 2, "links_in_rechts_pct": 100.0, "rechts_in_links_pct": 33.3}
    assert "melding_koppeling" not in uit


@pytest.mark.parametrize(("aantal_gemeenten", "herkend"), [(5, True), (4, False)])
def test_regiokolom_wordt_herkend_vanaf_de_helft_gemeentecodes(aantal_gemeenten, herkend):
    anders = ["NL01", "LD01", "PV26", "PV27", "CR01", "CR02"][: 10 - aantal_gemeenten]
    waarden = [f"GM{n:04d}" for n in range(1, aantal_gemeenten + 1)] + anders
    _put("cbs:grens", pd.DataFrame({"Regiokenmerken": waarden}))
    uit = json.loads(relatie("cbs:grens"))
    assert bool(uit["sleutels"]) is herkend
    if not herkend:
        assert uit["sleutels"] == [] and uit["zonder_sleutel"] == ["Regiokenmerken"]


def test_provincies_met_nederland_en_landsdelen_blijven_een_provinciesleutel():
    codes = [f"PV{n}" for n in range(20, 32)]
    _put("cbs:pv", pd.DataFrame({"Regiokenmerken": ["NL01", "LD01", *codes]}))
    (sleutel,) = json.loads(relatie("cbs:pv"))["sleutels"]
    assert (sleutel["sleutel"], sleutel["uniek"]) == ("provincie", 12)
    assert sleutel["dekking"] == {"naslag": "CBS-provinciecodes", "bekend": 12, "van": 12}


def test_een_codekolom_zonder_regiocodes_is_geen_regiosleutel():
    _put("cbs:soort", pd.DataFrame({"Onderwijssoort": ["A025294", "A025297", "T001345", "A041867"]}))
    assert json.loads(relatie("cbs:soort"))["sleutels"] == []


def test_zonder_bekende_sleutel_een_melding_en_een_onbekende_key_een_fout():
    _put("x:t", pd.DataFrame({"A": [1], "B": ["q"]}))
    uit = json.loads(relatie("x:t"))
    assert uit["sleutels"] == [] and "Geen bekende sleutelkolom" in uit["melding"]
    assert "weg:t" in relatie("weg:t")


def test_zonder_register_geen_dekking_en_geen_gok(caplog):
    _put("duo:t", _DUO)
    with patch("tools.relaties.instellingen.get_all", side_effect=ConnectionError("https://duo/adressen?x=geheim")):
        caplog.set_level(logging.WARNING, logger="tools.relaties")
        uit = json.loads(relatie("duo:t"))
    code = next(s for s in uit["sleutels"] if s["kolom"] == "INSTELLINGSCODE_ACTUEEL")
    assert "dekking" not in code
    assert any("ConnectionError" in r.getMessage() and "geheim" not in r.getMessage() for r in caplog.records)


# --- koppelkandidaten tussen twee tabellen ------------------------------------------------------


def test_koppelingen_duo_cbs_op_gemeente_en_schooljaar_met_vertaling_en_overlap(caplog):
    _put("duo:t", _DUO)
    _put("cbs:t", _CBS)
    caplog.set_level(logging.INFO, logger="tools.relaties")
    uit = json.loads(relatie("duo:t", andere_key="cbs:t"))
    per = {(k["links"]["kolom"], k["rechts"]["kolom"]): k for k in uit["koppelingen"]}
    gemeente = per[("GEMEENTENUMMER", "RegioS")]
    assert gemeente["sleutel"] == "gemeente" and gemeente["type"] == "many_to_one"
    assert gemeente["overlap"] == {"gedeeld": 2, "links_in_rechts_pct": 100.0, "rechts_in_links_pct": 66.7}
    assert (gemeente["basis"], gemeente["confidence"]) == ("gedetecteerd", 1.0)
    jaar = per[("STUDIEJAAR", "Perioden")]
    assert jaar["type"] == "many_to_many" and jaar["overlap"]["gedeeld"] == 1
    assert ("GEMEENTENAAM", "RegioS_label") not in per  # een labelkolom is geen sleutel
    assert "rijen" not in uit and "data" not in uit  # de tool koppelt niets
    (regel,) = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert regel.startswith("RELATIE kandidaten=2") and "0855" not in regel and "Tilburg" not in regel


def test_zonder_gedeelde_sleutel_een_melding_om_niet_te_koppelen():
    _put("duo:t", _DUO)
    _put("rio:t", pd.DataFrame({"opleidingseenheidcode": ["1001"], "volledigeNaam": ["Verpleegkunde"]}))
    uit = json.loads(relatie("duo:t", andere_key="rio:t"))
    assert uit["koppelingen"] == []
    assert "Geen gedeelde sleutel" in uit["melding_koppeling"]


def test_dezelfde_kolomnaam_in_beide_tabellen_is_handmatig_een_op_een():
    _put("a:t", pd.DataFrame({"INSTELLINGSCODE": ["21PK", "25BE"], "N": [1, 2]}))
    _put("b:t", pd.DataFrame({"INSTELLINGSCODE": ["25be", "21pk"], "PROVINCIE": ["Noord-Brabant", "Noord-Brabant"]}))
    (k,) = json.loads(relatie("a:t", andere_key="b:t"))["koppelingen"]
    assert (k["sleutel"], k["type"], k["basis"], k["overlap"]["gedeeld"]) == (
        "instellingscode",
        "one_to_one",
        "handmatig",
        2,
    )


def test_connector_kolommen_zijn_hoofdletterongevoelig_en_uniek_per_naam():
    namen = [kolom for c in rel.CONNECTOREN for kolom in c.kolommen]
    assert len(namen) == len({n.upper() for n in namen})
    assert rel.connector_van("studiejaar", pd.Series([2021])) is rel.connector_van("STUDIEJAAR", pd.Series([2021]))


def test_een_skdb_tabel_koppelt_op_brin_en_croho_aan_duo():
    """De Studiekeuzedatabase (#957): `brin` en `croho` uit get_studiekeuze zijn dezelfde sleutels als de DUO-kolommen;
    een CROHO-code die als getal met lege cellen is gelezen (30020.0) telt als 30020."""
    _put(
        "skdb:opleidingen:x",
        pd.DataFrame(
            {"brin": ["25DW", "21PB"], "croho": [30020, 56604], "studiecode": [30020, 56604], "nse": [3.6, 4.0]}
        ),
    )
    _put(
        "duo:ho",
        pd.DataFrame(
            {
                "INSTELLINGSCODE_ACTUEEL": ["25DW", "25DW", "30GB"],
                "OPLEIDINGSCODE_ACTUEEL": [30020.0, None, 34139.0],
                "AANTAL": [10, 20, 30],
            }
        ),
    )
    uit = json.loads(relatie("skdb:opleidingen:x", andere_key="duo:ho"))
    per = {(k["links"]["kolom"], k["rechts"]["kolom"]): k for k in uit["koppelingen"]}
    assert per[("brin", "INSTELLINGSCODE_ACTUEEL")]["overlap"]["gedeeld"] == 1
    assert per[("croho", "OPLEIDINGSCODE_ACTUEEL")]["overlap"]["gedeeld"] == 1
    assert "studiecode" in uit["zonder_sleutel"]
