"""
Tests voor CBS-04: validate_selection / resolve_dimensiewaarde / prepare_query.
Offline; CBS-client wordt gestubd.
"""
import httpx
import pytest

import onderwijsdata as od
from onderwijsdata import client, contract, validatie


def _status(res, veld):
    return [c["status"] for c in res["checks"] if c["veld"] == veld]


@pytest.fixture
def nep_cbs(monkeypatch):
    waarden = {"Geslacht": {"T001038": "Totaal mannen en vrouwen", "3000": "Mannen", "4000": "Vrouwen"},
               "Onderwijssoort": {"A": "Hbo", "B": "Hbo bachelor", "C": "Wo"},
               "Perioden": {"2023SJ00": "2023/'24", "2024SJ00": "2024/'25"},
               "Regiokenmerken": {"NL01": "Nederland", "GM0363": "Amsterdam", "PV27": "Noord-Holland"},
               "GeboortelandOuders": {"1": "Nederland", "2": "Buitenland"}}
    titels = {"GeboortelandOuders": "Geboorteland (ouders)"}
    state = {"down": False}

    def definitions(cbs_id):
        return {k: {"title": titels.get(k, k), "type": "Dimension"} for k in waarden}

    def dimension(cbs_id, key):
        if state["down"]:
            raise httpx.ConnectTimeout("timeout")
        return waarden[key]

    monkeypatch.setattr(client, "definitions", definitions)
    monkeypatch.setattr(client, "dimension", dimension)
    contract._dimensie_cache.cache_clear()
    yield state
    contract._dimensie_cache.cache_clear()


class TestSector:
    def test_zuivere_ho_tabel_voor_wo(self):
        assert od.validate_selection("85423NED", {"sector": "wo"})["status"] == "supported"

    def test_mbo_op_ho_tabel_is_unsupported(self):
        assert od.validate_selection("85423NED", {"sector": "mbo"})["status"] == "unsupported"

    def test_brede_tabel_is_unknown_niet_supported(self):
        res = od.validate_selection("85702NED", {"sector": "mbo"})
        assert res["status"] == "unknown"

    def test_ongeldige_sector_geeft_herstelopties(self):
        res = od.validate_selection("85423NED", {"sector": "vo"})
        assert res["checks"][0]["fout"] == "ongeldige_sector"
        assert res["checks"][0]["herstel"] == ["mbo", "hbo", "wo"]

    def test_ho_label_zonder_uitsplitsing_is_geen_bewijs(self, monkeypatch):
        rec = od.get_dataset("85423NED")
        rec["dimensies"] = ["Geslacht", "Perioden"]
        monkeypatch.setattr(contract, "get_dataset", lambda *_a, **_k: rec)
        assert _status(od.validate_selection("85423NED", {"sector": "wo"}), "sector") == ["unknown"]


class TestGeografieEnPeriode:
    def test_landelijk_op_nationale_ho_tabel(self):
        assert od.validate_selection("85423NED", {"geografie": "landelijk"})["status"] == "supported"

    def test_periodejaar_offline_is_unknown(self):
        res = od.validate_selection("85423NED", {"periode": {"type": "schooljaar", "jaar": 2024}})
        assert res["status"] == "unknown" and res["checks"][0]["code"] == "2024SJ00"

    def test_gemeente_niet_ondersteund_zonder_regiodimensie(self):
        res = od.validate_selection("85423NED", {"geografie": "gemeente"})
        assert res["status"] == "unsupported"

    def test_gemeente_wel_ondersteund_met_niveaus(self):
        rec = next(r for r in od.catalog_records() if "gemeente" in (r["geografie"].get("niveaus") or []))
        assert od.validate_selection(rec["dataset_id"], {"geografie": "gemeente"})["status"] == "supported"
        res = od.validate_selection(rec["dataset_id"], {"geografie": "wijk"})
        assert res["status"] == "unsupported" and res["checks"][0]["herstel"]

    def test_jaar_is_niet_schooljaar(self):
        res = od.validate_selection("85423NED", {"periode": {"type": "jaar"}})
        assert res["status"] == "unsupported" and "conversieregel" in res["checks"][0]["reden"]

    def test_schooljaar_op_schooljaartabel(self):
        assert od.validate_selection("85423NED", {"periode": {"type": "schooljaar"}})["status"] == "supported"

    def test_prognosejaar_nooit_gelijkgesteld(self):
        assert od.validate_selection("85423NED", {"periode": {"type": "prognosejaar"}})["status"] == "unsupported"

    def test_kwartaal_op_jaartabel(self):
        assert od.validate_selection("85423NED", {"periode": {"type": "kwartaal"}})["status"] == "unsupported"


class TestMeetwaarden:
    def test_titel_i_p_v_key_wordt_afgekeurd_met_herstel(self):
        res = od.validate_selection("85423NED", {"meetwaarden": ["Totaal ingeschrevenen"]})
        c = res["checks"][0]
        assert c["fout"] == "titel_i_p_v_key" and c["herstel"] == ["TotaalIngeschrevenen_1"]

    def test_onbekende_meetwaarde_geeft_suggestie(self):
        c = od.validate_selection("85423NED", {"meetwaarden": ["TotaalIngeschreven_1"]})["checks"][0]
        assert c["fout"] == "ongeldige_meetwaarde" and "TotaalIngeschrevenen_1" in c["herstel"]

    def test_eenheid_zichtbaar(self):
        c = od.validate_selection("85423NED", {"meetwaarden": ["TotaalIngeschrevenen_1"]})["checks"][0]
        assert c["eenheid"] == "aantal"

    def test_verschillende_eenheden_zijn_definitieverschil(self, monkeypatch):
        rec = od.get_dataset("85423NED")
        rec["meetwaarden"] = [
            {"key": "A_1", "title": "A", "unit": "aantal", "datatype": "Long", "decimals": 0},
            {"key": "B_1", "title": "B", "unit": "%", "datatype": "Double", "decimals": 1},
        ]
        monkeypatch.setattr(contract, "get_dataset", lambda *_a, **_k: rec)
        res = od.validate_selection("85423NED", {"meetwaarden": ["A_1", "B_1"]})
        assert res["status"] == "unknown"
        assert any(c.get("fout") == "definitieverschil" for c in res["checks"])


class TestDimensies:
    def test_ongeldige_dimensie_live_getypeerd_met_herstel(self, nep_cbs):
        c = od.validate_selection("85423NED", {"dimensies": {"Geslachtt": "x"}}, live=True)["checks"][0]
        assert c["status"] == "unsupported"
        assert c["fout"] == "ongeldige_dimensie" and "Geslacht" in c["herstel"]

    def test_onbekende_naam_offline_zonder_sleutels_is_unknown(self, monkeypatch):
        # Kan nog een officiële key zijn; offline niet te weerleggen (review F6).
        rec = od.get_dataset("85423NED")
        rec["dimensie_sleutels"] = {"status": "unknown", "reden": "niet vastgelegd"}
        monkeypatch.setattr(contract, "get_dataset", lambda *_a, **_k: rec)
        c = od.validate_selection("85423NED", {"dimensies": {"Geslachtt": "x"}})["checks"][0]
        assert c["status"] == "unknown" and c["fout"] == "dimensie_onbevestigd"

    def test_onbekende_naam_offline_met_sleutels_is_unsupported(self, monkeypatch):
        rec = od.get_dataset("85423NED")
        rec["dimensie_sleutels"] = {"status": "supported", "sleutels": {d: d for d in rec["dimensies"]}}
        monkeypatch.setattr(contract, "get_dataset", lambda *_a, **_k: rec)
        c = od.validate_selection("85423NED", {"dimensies": {"Geslachtt": "x"}})["checks"][0]
        assert c["status"] == "unsupported" and c["fout"] == "ongeldige_dimensie"

    def test_officiele_key_wordt_geaccepteerd_live(self, nep_cbs):
        # 85354NED: titel 'Geboorteland (ouders)', key GeboortelandOuders (review F6).
        res = od.validate_selection("85354NED", {"dimensies": {"GeboortelandOuders": "1"}}, live=True)
        assert res["status"] == "supported"

    def test_officiele_key_offline_via_vastgelegde_sleutels(self, monkeypatch):
        rec = od.get_dataset("85354NED")
        rec["dimensie_sleutels"] = {"status": "supported", "sleutels": {"Geboorteland (ouders)": "GeboortelandOuders"}}
        monkeypatch.setattr(contract, "get_dataset", lambda *_a, **_k: rec)
        c = od.validate_selection("85354NED", {"dimensies": {"GeboortelandOuders": "1"}})["checks"][0]
        assert c["veld"] == "dimensiecode" and c["dimensie"] == "Geboorteland (ouders)"
        assert c["sleutel"] == "GeboortelandOuders"

    def test_geleverde_catalogus_kent_officiele_keys_offline(self):
        c = od.validate_selection("85354NED", {"dimensies": {"GeboortelandOuders": "x"}})["checks"][0]
        assert c["veld"] == "dimensiecode" and c["sleutel"] == "GeboortelandOuders"

    def test_query_gebruikt_officiele_key(self, nep_cbs):
        res = od.prepare_query("85354NED", {"dimensies": {"Geboorteland (ouders)": "2"}})
        assert res["query"] == {"$filter": "trim(GeboortelandOuders) eq '2'"}

    def test_code_offline_is_unknown(self):
        res = od.validate_selection("85423NED", {"dimensies": {"Geslacht": "T001038"}})
        assert res["status"] == "unknown"

    def test_geldige_code_live(self, nep_cbs):
        res = od.validate_selection("85423NED", {"dimensies": {"Geslacht": "T001038"}}, live=True)
        assert res["status"] == "supported"

    def test_ongeldige_code_geeft_herstelopties(self, nep_cbs):
        c = od.validate_selection("85423NED", {"dimensies": {"Geslacht": "3001"}}, live=True)["checks"][0]
        assert c["fout"] == "ongeldige_code" and c["status"] == "unsupported"

    def test_bronuitval_is_unknown_niet_bestaat_niet(self, nep_cbs):
        nep_cbs["down"] = True
        c = od.validate_selection("85423NED", {"dimensies": {"Geslacht": "T001038"}}, live=True)["checks"][0]
        assert c["status"] == "unknown" and c["fout"] == "bron_niet_bereikbaar"


class TestResolve:
    def test_exacte_titel(self, nep_cbs):
        assert od.resolve_dimensiewaarde("85423NED", "Geslacht", "mannen")["code"] == "3000"

    def test_ambiguiteit_vraagt_verduidelijking_geen_eerste_match(self, nep_cbs, monkeypatch):
        monkeypatch.setattr(client, "dimension", lambda *_a: {"1": "Totaal", "2": "Totaal"})
        res = od.resolve_dimensiewaarde("85423NED", "Geslacht", "totaal")
        assert res["fout"] == "ambigu" and len(res["opties"]) == 2

    def test_geen_exacte_match_geeft_opties(self, nep_cbs):
        res = od.resolve_dimensiewaarde("85423NED", "Onderwijssoort", "hb")
        assert res["status"] == "unknown" and res["fout"] == "geen_exacte_match"

    def test_bronuitval(self, nep_cbs):
        nep_cbs["down"] = True
        assert od.resolve_dimensiewaarde("85423NED", "Geslacht", "mannen")["fout"] == "bron_niet_bereikbaar"


class TestPrepareQuery:
    def test_geverifieerde_query(self, nep_cbs):
        res = od.prepare_query("85423NED", {
            "sector": "hbo", "periode": {"type": "schooljaar"},
            "meetwaarden": ["TotaalIngeschrevenen_1"], "dimensies": {"Geslacht": "3000"},
        })
        assert res["query"] == {"$select": "TotaalIngeschrevenen_1",
                                "$filter": "trim(Geslacht) eq '3000' and trim(Onderwijssoort) eq 'A'"}

    def test_sector_die_dimensiecode_tegenspreekt_is_unsupported(self, nep_cbs):
        # Review F1: hbo + WO-code mag nooit 'supported' zijn.
        res = od.prepare_query("85423NED", {"sector": "hbo", "meetwaarden": ["TotaalIngeschrevenen_1"],
                                            "dimensies": {"Onderwijssoort": "C"}})
        assert res["status"] == "unsupported" and res["query"] is None
        assert any(c.get("fout") == "tegenstrijdige_selectie" for c in res["checks"])

    def test_sector_zonder_dimensie_wordt_concreet_filter(self, nep_cbs):
        res = od.prepare_query("85423NED", {"sector": "wo", "meetwaarden": ["TotaalIngeschrevenen_1"]})
        assert res["query"]["$filter"] == "trim(Onderwijssoort) eq 'C'"

    def test_sector_gelijk_aan_opgegeven_code_geeft_een_filter(self, nep_cbs):
        res = od.prepare_query("85423NED", {"sector": "hbo", "dimensies": {"Onderwijssoort": "A"}})
        assert res["query"] == {"$filter": "trim(Onderwijssoort) eq 'A'"}

    def test_geen_eenduidige_sectorcode_is_unknown(self, nep_cbs, monkeypatch):
        echte = client.dimension
        monkeypatch.setattr(client, "dimension",
                            lambda i, k: {"A": "Hoger onderwijs"} if k == "Onderwijssoort" else echte(i, k))
        res = od.prepare_query("85423NED", {"sector": "hbo"})
        assert res["status"] == "unknown" and res["query"] is None

    def test_periodejaar_wordt_geverifieerde_code(self, nep_cbs):
        res = od.prepare_query("85423NED", {"periode": {"type": "schooljaar", "jaar": 2024}})
        assert res["query"] == {"$filter": "trim(Perioden) eq '2024SJ00'"}

    def test_periodejaar_dat_periodecode_tegenspreekt_is_unsupported(self, nep_cbs):
        # Herverificatie H1: jaar 2023 + bestaande code 2024SJ00 mag niet stil 2024 opleveren.
        res = od.prepare_query("85423NED", {"periode": {"type": "schooljaar", "jaar": 2023},
                                            "dimensies": {"Perioden": "2024SJ00"}})
        assert res["status"] == "unsupported" and res["query"] is None
        c = next(c for c in res["checks"] if c.get("fout") == "tegenstrijdige_selectie")
        assert c["dimensie"] == "Perioden" and c["herstel"] == ["2023SJ00", "2024SJ00"]

    def test_periodejaar_gelijk_aan_periodecode_geeft_een_filter(self, nep_cbs):
        res = od.prepare_query("85423NED", {"periode": {"type": "schooljaar", "jaar": 2023},
                                            "dimensies": {"Perioden": "2023SJ00"}})
        assert res["query"] == {"$filter": "trim(Perioden) eq '2023SJ00'"}

    def test_onbestaand_periodejaar_is_unsupported(self, nep_cbs):
        res = od.prepare_query("85423NED", {"periode": {"type": "schooljaar", "jaar": 2099}})
        assert res["status"] == "unsupported" and res["query"] is None

    def test_onbekende_requirement_verdwijnt_niet(self, nep_cbs):
        res = od.prepare_query("85423NED", {"meetwaarden": ["TotaalIngeschrevenen_1"], "instelling": "UvA"})
        assert res["status"] == "unknown" and res["query"] is None
        assert res["checks"][0]["fout"] == "onbekende_requirement"

    def test_onbekend_periodeveld_verdwijnt_niet(self, nep_cbs):
        res = od.prepare_query("85423NED", {"periode": {"type": "schooljaar", "maand": 9}})
        assert res["status"] == "unknown"

    def test_ongeldige_vorm(self, nep_cbs):
        res = od.prepare_query("85423NED", {"meetwaarden": "TotaalIngeschrevenen_1"})
        assert res["status"] == "unsupported" and res["checks"][0]["fout"] == "ongeldige_vorm"

    def test_landelijke_ho_tabel_zonder_regiofilter(self, nep_cbs):
        # Review F5: nationale HO-tabel is landelijk, geen regiodimensie nodig.
        res = od.prepare_query("85423NED", {"geografie": "landelijk", "meetwaarden": ["TotaalIngeschrevenen_1"]})
        assert res["status"] == "supported" and "$filter" not in res["query"]

    def test_landelijk_op_regiotabel_filtert_nl01(self, nep_cbs):
        res = od.prepare_query("85702NED", {"geografie": "landelijk"})
        assert res["query"] == {"$filter": "trim(Regiokenmerken) eq 'NL01'"}

    def test_gemeente_zonder_regiocode_is_onvolledig(self, nep_cbs):
        res = od.prepare_query("85702NED", {"geografie": "gemeente"})
        assert res["status"] == "unknown" and res["checks"][-1]["fout"] == "ontbrekende_selectie"

    def test_gemeente_met_provinciecode_is_tegenstrijdig(self, nep_cbs):
        res = od.prepare_query("85702NED", {"geografie": "gemeente", "dimensies": {"Regiokenmerken": "PV27"}})
        assert res["status"] == "unsupported"

    def test_gemeente_met_gemeentecode(self, nep_cbs):
        res = od.prepare_query("85702NED", {"geografie": "gemeente", "dimensies": {"Regiokenmerken": "GM0363"}})
        assert res["query"] == {"$filter": "trim(Regiokenmerken) eq 'GM0363'"}

    def test_geen_query_bij_niet_supported(self, nep_cbs):
        res = od.prepare_query("85423NED", {"meetwaarden": ["Totaal ingeschrevenen"]})
        assert res["query"] is None and res["status"] == "unsupported"

    def test_geen_query_bij_unknown(self, nep_cbs):
        assert od.prepare_query("85702NED", {"sector": "mbo"})["query"] is None


def test_capability_aan():
    assert od.catalog_manifest()["capabilities"]["validate_selection"] is True


def test_onbekende_dataset_geeft_fout():
    with pytest.raises(contract.DatasetNietGevonden):
        od.validate_selection("99999NED", {})
