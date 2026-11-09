"""Koppelsleutels per dataset (#958, relatielaag stap 2): één lijst in `_kern.sleutels`, per catalogusrecord `_sleutels`.

De sleutels in een record komen uit de schema's die al in het pakket staan (DUO-schemasnapshot, CBS-dimensies, RIO-
kolommen) of zijn vast (SKDB, WOPI, financiën); deze tests toetsen ze tegen die echte kolommen. Geen netwerk.
"""

from __future__ import annotations

import onderwijsbronnen
import pytest
from onderwijsbronnen import contract, skdb, unl
from onderwijsbronnen import sleutels as s
from onderwijsbronnen.duo import _schema_snapshot, financien
from onderwijsbronnen.skdb import proefbestand as skdb_proef
from onderwijsbronnen.unl import proefbestand as unl_proef


def _records(bron: str) -> list[dict]:
    return onderwijsbronnen.catalogus()[bron]


def _record(bron: str, veld: str, waarde: str) -> dict:
    return next(r for r in _records(bron) if r.get(veld) == waarde)


def _per_kolom(record: dict) -> dict[str, list[str]]:
    uit: dict[str, list[str]] = {}
    for paar in record["_sleutels"]:
        uit.setdefault(paar["kolom"], []).append(paar["sleutel"])
    return uit


# --- normalisatie per sleutel ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sleutel", "waarde", "verwacht"),
    [
        ("gemeente", "GM0344", "0344"),
        ("gemeente", "gm0344", "0344"),
        ("gemeente", 344, "0344"),
        ("gemeente", "344.0", "0344"),
        ("gemeente", " 34 ", "0034"),
        ("gemeente", "Utrecht", None),
        ("gemeente", None, None),
        ("provincie", "PV26", "PV26"),
        ("provincie", "Utrecht", "PV26"),
        ("provincie", "noord-brabant", "PV30"),
        ("provincie", "Fryslân", "PV21"),
        ("provincie", "PV99", None),
        ("provincie", "BELGIE", None),
        ("schooljaar", 2021, "2021"),
        ("schooljaar", "2021/2022", "2021"),
        ("schooljaar", "2021/22", "2021"),
        ("schooljaar", "2015/'16", "2015"),
        ("schooljaar", "2021SJ00", "2021"),
        ("schooljaar", "2021JJ00", None),
        ("schooljaar", "2021/2023", None),
        ("schooljaar", "x", None),
        ("schooljaar", 3000, None),
        ("brin", "21pk", "21PK"),
        ("brin", " 25DW ", "25DW"),
        ("croho", 30020.0, "30020"),
        ("croho", "30020", "30020"),
        ("croho", "04181", "4181"),
        ("crebo", 25180, "25180"),
        ("bestuur", '="00008"', "00008"),
        ("bestuur", 40597.0, "40597"),
        ("bestuur", "40833-25LR", "40833-25LR"),
        ("bestuur", "geen", None),
        ("vestiging", "00bh01", "00BH01"),
        ("arbeidsmarktregio", "am12", "AM12"),
        ("arbeidsmarktregio", " Achterhoek ", "achterhoek"),
        ("soi", "48100-HBO-Bachelor", "48100"),
        ("soi", 48100, "48100"),
        ("soi", "informatica", None),
        ("instellingsnaam", " Fontys ", "fontys"),
    ],
)
def test_elke_sleutel_normaliseert_naar_een_vorm(sleutel, waarde, verwacht):
    assert s.normaliseer(sleutel, waarde) == verwacht


def test_de_provincies_zijn_de_twaalf_cbs_codes():
    assert sorted(s.PROVINCIES) == [f"PV{n}" for n in range(20, 32)]


# --- kolomnamen ------------------------------------------------------------------------------------------------------


def test_alleen_de_twee_namen_zijn_een_sleutel_op_naam():
    assert {x.naam for x in s.SLEUTELS.values() if x.op_naam} == {"instellingsnaam", "gemeentenaam"}


def test_een_kolomnaam_geeft_zijn_sleutels_hoofdletterongevoelig():
    assert [x.naam for x in s.van_kolom("studiejaar")] == ["schooljaar"]
    assert [x.naam for x in s.van_kolom(" INSTELLINGSCODE_ACTUEEL ")] == ["brin"]
    assert [x.naam for x in s.van_kolom("instellingCode")] == ["brin"]
    assert s.van_kolom("AANTAL") == ()


def test_een_erkende_opleidingscode_is_croho_of_crebo_en_de_sector_beslist():
    """RIO en DUO schrijven de CROHO-code (ho) en de crebo-code (mbo) in dezelfde kolom ERKENDEOPLEIDINGSCODE."""
    assert {x.naam for x in s.van_kolom("ERKENDEOPLEIDINGSCODE")} == {"croho", "crebo"}
    kolommen = ["ERKENDEOPLEIDINGSCODE", "INSTELLINGSCODE"]
    assert s.paren(kolommen, ["MBO"])[0] == {"kolom": "ERKENDEOPLEIDINGSCODE", "sleutel": "crebo"}
    assert s.paren(kolommen, ["HO"])[0] == {"kolom": "ERKENDEOPLEIDINGSCODE", "sleutel": "croho"}
    assert [p["sleutel"] for p in s.paren(kolommen, ["MBO", "HBO", "WO"])] == ["croho", "crebo", "brin"]
    # Een kolom met één sleutel versmalt nooit: een CROHO-kolom in een mbo-record blijft CROHO.
    assert s.paren(["OPLEIDINGSCODE_ACTUEEL"], ["MBO"]) == [{"kolom": "OPLEIDINGSCODE_ACTUEEL", "sleutel": "croho"}]


def test_paren_zijn_uniek_en_in_kolomvolgorde():
    kolommen = ["STUDIEJAAR", "AANTAL", "INSTELLINGSCODE_ACTUEEL", "STUDIEJAAR"]
    assert s.paren(kolommen) == [
        {"kolom": "STUDIEJAAR", "sleutel": "schooljaar"},
        {"kolom": "INSTELLINGSCODE_ACTUEEL", "sleutel": "brin"},
    ]


def test_elke_sleutel_staat_maar_een_keer_bij_een_kolom_behalve_de_erkende_opleidingscode():
    dubbel = {k for k in s.KOLOMMEN if len(s.van_kolom(k)) > 1}
    assert dubbel == {"ERKENDEOPLEIDINGSCODE"}


def test_in_record_eist_een_reden_zonder_sleutels_en_kent_alleen_canonieke_sleutels():
    assert s.in_record({"x": 1}, [], "geen kolommen")["_sleutels_reden"] == "geen kolommen"
    met = s.in_record({"x": 1}, [{"kolom": "BRIN", "sleutel": "brin"}], "ongebruikt")
    assert met["_sleutels"] == [{"kolom": "BRIN", "sleutel": "brin"}] and "_sleutels_reden" not in met
    with pytest.raises(ValueError, match="instellingscode"):
        s.in_record({}, [{"kolom": "BRIN", "sleutel": "instellingscode"}], "x")
    with pytest.raises(ValueError, match="reden"):
        s.in_record({}, [], "")


# --- per catalogusrecord ---------------------------------------------------------------------------------------------


def test_elk_record_van_elke_bron_heeft_sleutels_of_een_reden():
    for bron, records in onderwijsbronnen.catalogus().items():
        for r in records:
            assert isinstance(r.get("_sleutels"), list), (bron, r.get("bron"))
            assert r["_sleutels"] or r.get("_sleutels_reden"), (bron, r.get("bron"))
            assert all(p["sleutel"] in s.SLEUTELS for p in r["_sleutels"])


def test_duo_sleutels_zijn_echte_kolommen_uit_de_schemasnapshot():
    snapshot = _schema_snapshot()["datasets"]
    getoetst = 0
    for r in _records("duo"):
        if not (ds := snapshot.get(r.get("_ckan_id"))):
            continue
        kolommen = {k["naam"] for res in ds["resources"] for k in res["kolommen"]}
        assert {p["kolom"] for p in r["_sleutels"]} <= kolommen, r["_ckan_id"]
        getoetst += 1
    assert getoetst > 40
    assert _per_kolom(_record("duo", "_ckan_id", "p01hoinges")) == {
        "STUDIEJAAR": ["schooljaar"],
        "PROVINCIENAAM": ["provincie"],
        "GEMEENTENUMMER": ["gemeente"],
        "GEMEENTENAAM": ["gemeentenaam"],
        "INSTELLINGSCODE_ACTUEEL": ["brin"],
        "INSTELLINGSNAAM_ACTUEEL": ["instellingsnaam"],
        "OPLEIDINGSCODE_ACTUEEL": ["croho"],
    }


def test_duo_versmalt_de_erkende_opleidingscode_naar_de_sector_van_de_dataset():
    assert _per_kolom(_record("duo", "_ckan_id", "mbo_opleidingsaanbod"))["ERKENDEOPLEIDINGSCODE"] == ["crebo"]
    assert _per_kolom(_record("duo", "_ckan_id", "overzicht-erkenningen-ho"))["ERKENDEOPLEIDINGSCODE"] == ["croho"]
    erkenningen = _per_kolom(_record("duo", "_ckan_id", "overzicht-erkenningen-ho"))
    assert erkenningen["VESTIGINGSCODE"] == ["vestiging"] and erkenningen["BEVOEGD_GEZAG_CODE"] == ["bestuur"]


def test_cbs_sleutels_zijn_dimensies_van_de_tabel():
    for r in _records("cbs"):
        dimensies = set((r.get("_dimensie_sleutels") or {}).values())
        assert {p["kolom"] for p in r["_sleutels"]} <= dimensies, r["_cbs_id"]
    # Een gemengde regiokolom met gemeenten en provincies, en schooljaren in Perioden.
    assert _per_kolom(_record("cbs", "_cbs_id", "85701NED")) == {
        "Regiokenmerken": ["gemeente", "provincie"],
        "Perioden": ["schooljaar"],
    }
    assert _per_kolom(_record("cbs", "_cbs_id", "71898ned")) == {"RegioS": ["gemeente", "provincie"]}


def test_cbs_kalenderjaren_en_overgangen_zijn_geen_schooljaar():
    for r in _records("cbs"):
        if "SJ" not in (r.get("_perioden_formaat") or []):
            assert "schooljaar" not in {p["sleutel"] for p in r["_sleutels"]}, r["_cbs_id"]
    zonder = next(r for r in _records("cbs") if not r["_sleutels"])
    assert "gemeente" in zonder["_sleutels_reden"] and "schooljaren" in zonder["_sleutels_reden"]


def test_rio_sleutels_zijn_kolommen_van_de_resource():
    for r in _records("rio"):
        assert {p["kolom"] for p in r["_sleutels"]} <= set(r.get("_kolommen") or []), r["_rio_resource"]
    assert _per_kolom(_record("rio", "_rio_resource", "opleidingen")) == {
        "opleidingseenheidcode": ["opleidingseenheid"]
    }
    assert set(_per_kolom(_record("rio", "_rio_resource", "opleidingserkenningen"))["erkendeopleidingscode"]) == {
        "croho",
        "crebo",
    }
    assert "RIO" in _record("rio", "_rio_resource", "examenlicenties")["_sleutels_reden"]


def test_studiekeuzedatabase_heeft_vaste_sleutels_uit_de_uitkomst_van_haar_overzichten():
    record = _records("skdb")[0]
    export = skdb.lees(*skdb_proef.standaard())
    rijen = [*skdb.opleidingen(export), *skdb.studie(export, 56604), *skdb.doorstroom_bachelor_master(export, 56604)]
    kolommen = {k for rij in rijen for k in rij}
    assert {p["kolom"] for p in record["_sleutels"]} <= kolommen
    assert _per_kolom(record) == {
        "brin": ["brin"],
        "croho": ["croho"],
        "master_croho": ["croho"],
        "roa_opleidingstype": ["roa_opleidingstype"],
    }


def test_wopi_en_financien_hebben_vaste_sleutels_uit_hun_eigen_bestand():
    wopi = unl.lees(*unl_proef.standaard())
    for tabel in ("functie", "personen"):
        assert {p["kolom"] for p in _records("unl")[0]["_sleutels"]} <= set(wopi.rijen(tabel)[0]), tabel
    assert _per_kolom(_records("unl")[0]) == {"brin": ["brin"]}
    fin = _record("duo", "_buiten_ckan", True)
    assert fin["_sleutels"] == [{"kolom": "Bevoegd Gezag", "sleutel": "bestuur"}]
    assert "Bevoegd Gezag" in financien._SLEUTELKOLOMMEN


def test_het_contract_noemt_dezelfde_sleutels_als_het_record():
    record = _record("duo", "_ckan_id", "p02ho1ejrs")
    join = contract.get_dataset("duo:p02ho1ejrs")["join_sleutels"]
    assert join["status"] == contract.SUPPORTED and join["sleutels"] == record["_sleutels"]
    assert contract.get_dataset("duo:p02ho1ejrs")["instellingseenheden"]["kolommen"] == ["INSTELLINGSCODE_ACTUEEL"]
    assert not hasattr(contract, "_JOIN_SLEUTELS")
