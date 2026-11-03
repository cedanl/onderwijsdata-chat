"""
Tests voor CBS-02: sectorclassificatie en discovery-diff (offline, met fixtures).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "catalogus"))

import pytest
from sector import classificeer_sector, is_toegelaten
import discovery_diff as dd


class TestClassificatie:
    @pytest.mark.parametrize("titel, klasse", [
        ("Mbo; studenten, niveau en leerweg", "mbo"),
        ("Hbo; ingeschrevenen per opleiding", "hbo"),
        ("Wetenschappelijk onderwijs; gediplomeerden", "wo"),
        ("Primair onderwijs; leerlingen per gemeente", "buiten_scope"),
        ("Vo; examenkandidaten, examenresultaten", "buiten_scope"),
    ])
    def test_zuivere_sectoren(self, titel, klasse):
        assert classificeer_sector(titel)["classificatie"] == klasse

    def test_ho_zonder_sectordimensie_is_onbekend(self):
        r = classificeer_sector("Hoger onderwijs; ingeschrevenen", dimensies=["Geslacht", "Perioden"])
        assert r["classificatie"] == "onbekend" and "geen aparte hbo/wo" in r["motivatie"]

    def test_ho_met_sectordimensie(self):
        r = classificeer_sector("Hoger onderwijs; ingeschrevenen", dimensies=["Onderwijssoort", "Perioden"])
        assert r["classificatie"] == "ho" and is_toegelaten(r["classificatie"])

    def test_gemengd_onscheidbaar_wordt_niet_toegelaten(self):
        r = classificeer_sector("Vo en mbo; leerlingen", dimensies=["Geslacht"])
        assert r["classificatie"] == "gemengd_onscheidbaar" and not is_toegelaten(r["classificatie"])

    def test_gemengd_met_uitsplitsing_moet_nog_geverifieerd(self):
        r = classificeer_sector("Vo en mbo; leerlingen", dimensies=["Onderwijssoort"])
        assert r["classificatie"] == "gemengd_met_uitsplitsing" and "te verifiëren" in r["motivatie"]

    def test_arbeidsmarkt_only_is_buiten_scope(self):
        r = classificeer_sector("Werkzame beroepsbevolking; regio", thema="Arbeidsmarkt")
        assert r["classificatie"] == "buiten_scope" and r["arbeidsmarkt_only"] is True

    def test_geen_sector_is_onbekend_niet_toegelaten(self):
        r = classificeer_sector("Kerkelijke gezindte per corop")
        assert r["classificatie"] == "onbekend" and not is_toegelaten("onbekend")

    def test_beslissing_is_gemotiveerd(self):
        assert classificeer_sector("Mbo; studenten")["motivatie"]


def _rec(cbs_id, bron, onderwijstype=("MBO",), archief=False, thema="Mbo studenten"):
    return {"_cbs_id": cbs_id, "bron": bron, "_thema": thema, "onderwijstype": list(onderwijstype),
            "_archief": archief, "_dimensies": []}


SWEEP = {"11111NED": 912, "22222NED": 912, "33333NED": 912, "44444NED": 480, "BEST1NED": 912}
THEMA = {912: "Mbo studenten", 480: "Onderwijs en arbeidsmarkt"}
DETAILS = {
    "11111NED": {"titel": "Mbo; nieuwe tabel studenten", "frequentie": "Jaarlijks", "periode": "2024", "modified": "2026-01-01", "dimensies": []},
    "22222NED": {"titel": "Primair onderwijs; leerlingen", "frequentie": "Jaarlijks", "periode": "2024", "modified": "2026-01-01", "dimensies": []},
    "33333NED": {"titel": "Hoger onderwijs; oude reeks", "frequentie": "Stopgezet", "periode": "1990-2000", "modified": "2005-01-01", "dimensies": ["Onderwijssoort"]},
    "44444NED": {"titel": "Werkzame beroepsbevolking", "frequentie": "Jaarlijks", "periode": "2024", "modified": "2026-01-01", "dimensies": []},
}


@pytest.fixture
def rapport():
    return dd.bouw_rapport([_rec("BEST1NED", "Mbo; bestaand"), _rec("OUD1NED", "Mbo; oud", archief=True)], SWEEP, THEMA, DETAILS)


class TestDiff:
    def test_nieuwe_relevante_tabel_geeft_reviewmelding(self, rapport):
        ids = {n["dataset_id"] for n in rapport["nieuw_voor_review"]}
        assert "cbs:11111NED" in ids
        assert all(n["advies"] == "review" for n in rapport["nieuw_voor_review"])

    def test_buiten_scope_en_arbeidsmarkt_niet_automatisch_toegevoegd(self, rapport):
        uit = {u["dataset_id"]: u for u in rapport["uitgesloten"]}
        assert uit["cbs:22222NED"]["advies"] == "niet_toevoegen"
        assert uit["cbs:44444NED"]["arbeidsmarkt_only"] is True
        assert rapport["samenvatting"]["uitgesloten_arbeidsmarkt_only"] == 1

    def test_historisch_onderscheiden_van_actief(self, rapport):
        s = rapport["samenvatting"]
        assert s["nieuw_voor_review_historisch"] == 1 and s["nieuw_voor_review_actief"] == 1
        assert set(s["bestaand_per_classificatie"]["mbo"]) == {"actief", "historisch"}

    def test_bestaande_items_verdwijnen_niet_stilzwijgend(self, rapport):
        assert "cbs:OUD1NED" in rapport["bestaand_niet_gevonden"]
        assert {b["dataset_id"] for b in rapport["bestaand"]} == {"cbs:BEST1NED", "cbs:OUD1NED"}

    def test_id_vergelijking_hoofdletterongevoelig(self):
        r = dd.bouw_rapport([_rec("11111ned", "Mbo; x")], {"11111NED": 912}, THEMA, {})
        assert r["samenvatting"]["nieuw_voor_review"] == 0 and r["samenvatting"]["al_in_catalogus"] == 1

    def test_ontbrekende_details_geven_review_geen_inname(self):
        r = dd.bouw_rapport([], {"99999NED": 912}, THEMA, {})
        assert r["nieuw_voor_review"][0]["classificatie"] == "onbekend"

    def test_geen_hardcoded_totaal_alleen_afgeleide_aantallen(self, rapport):
        s = rapport["samenvatting"]
        assert s["gevonden_in_sweep"] == s["al_in_catalogus"] + s["nieuw_voor_review"] + s["uitgesloten"]

    def test_rapport_is_json_serialiseerbaar(self, rapport):
        import json
        assert json.loads(json.dumps(rapport)) == rapport

    def test_afwijking_van_curatie_gemeld(self):
        rec = _rec("A1NED", "Primair onderwijs; leerlingen", onderwijstype=("MBO",), thema="")
        r = dd.bouw_rapport([rec], {}, {}, {})
        assert r["bestaand"][0]["afwijkend_van_curatie"] is True
        assert r["samenvatting"]["bestaand_afwijkend_van_curatie"] == 1


@pytest.fixture(scope="module")
def regressie():
    import json
    from pathlib import Path
    pad = Path(__file__).parent / "fixtures" / "discovery" / "regressie_kandidaten.json"
    return json.loads(pad.read_text(encoding="utf-8"))


class TestThemaselectie:
    """Review F7: de sweep volgt de themahiërarchie, geen vaste ID-lijst."""

    def test_caribisch_onderwijsthema_wordt_gesweept(self, regressie):
        gekozen = dd.selecteer_themas(regressie["themas"])
        assert 118 in gekozen and 362 in gekozen and 482 in gekozen

    def test_niet_onderwijsthema_en_miscategorisatie_niet(self, regressie):
        gekozen = dd.selecteer_themas(regressie["themas"])
        assert not {109, 351, 352, 353, 455} & set(gekozen)

    def test_bekende_kandidaten_komen_ter_review(self, regressie):
        sweep = {k["dataset_id"]: k["thema_id"] for k in regressie["kandidaten"]}
        details = {k["dataset_id"]: k["details"] for k in regressie["kandidaten"]}
        namen = {t["ID"]: t["Title"] for t in regressie["themas"]}
        r = dd.bouw_rapport([], sweep, namen, details, sorted(dd.selecteer_themas(regressie["themas"])))
        per_id = {n["dataset_id"]: n for n in r["nieuw_voor_review"]}
        for k in regressie["kandidaten"]:
            item = per_id[f"cbs:{k['dataset_id']}"]
            assert item["classificatie"] == k["verwachte_classificatie"] and item["advies"] == "review"

    def test_rapport_meldt_aangevraagde_themas_en_mislukte_details(self):
        r = dd.bouw_rapport([], {"11111NED": 912, "99999NED": 912}, THEMA, {"11111NED": DETAILS["11111NED"]}, [912, 480])
        assert r["thema_ids_aangevraagd"] == [480, 912]
        assert r["mislukte_details"] == ["cbs:99999NED"]
