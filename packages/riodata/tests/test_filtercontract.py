"""Contracttests voor de RIO-filters (v3): catalogus en spec mogen niet ongemerkt uiteenlopen."""
import importlib.util
import json
from importlib.resources import files
from pathlib import Path

import httpx
import pytest

import riodata
from riodata import _filtercontract as fc
from riodata import filtercontract, typewaarden, valideer_filters

ROOT = Path(__file__).resolve().parent.parent
CATALOGI = ("rio_resources.json", "rio_resources_ai.json", "rio_resources_enriched.json")
SERVER = "https://lod.onderwijsregistratie.nl/api/rio/v3"
ZONDER_LIJST = {"aangeboden-opleiding-cohorten", "contactadressen", "onderwijslocatiegebruiken"}
V2_NAMEN = {"erkenningtype", "opleidingseenheidtype", "opleidingserkenningtype", "organisatorischeEenheidType"}


def _laad(naam):
    return json.loads(files("riodata.data").joinpath(naam).read_text(encoding="utf-8"))


def _generator():
    spec = importlib.util.spec_from_file_location("genereer", ROOT / "catalogus" / "genereer_filtercontract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("bestand", CATALOGI)
def test_catalogusfilters_komen_overeen_met_spec(bestand):
    """Extra of ontbrekende filters in de catalogus laten deze test falen."""
    res = filtercontract()["resources"]
    for r in _laad(bestand):
        spec = res[r["_rio_resource"]]
        verwacht = {f["naam"] for f in spec["filters"]} | {f["naam"] for f in spec.get("catalogus_zonder_spec", [])}
        assert set(r["filters"]) == verwacht, f"{bestand}: {r['_rio_resource']}"
        assert len(r["filters"]) == len(set(r["filters"]))


@pytest.mark.parametrize("bestand", CATALOGI)
def test_v2_filternamen_komen_niet_meer_voor(bestand):
    """v2 → v3: elk typefilter heet ``type``; de oude namen zijn uit de catalogus."""
    for r in _laad(bestand):
        assert not V2_NAMEN & set(r["filters"]), r["_rio_resource"]


@pytest.mark.parametrize("bestand", CATALOGI)
def test_sub_resources_en_documentatie_volgen_de_spec(bestand):
    contract = filtercontract()
    for r in _laad(bestand):
        res = contract["resources"][r["_rio_resource"]]
        assert r["sub_resources"] == res["sub_resources"], r["_rio_resource"]
        if res["lijst_endpoint"]:
            assert r["documentatie"]["url"] == f"{SERVER}/{r['_rio_resource']}"
            assert r["documentatie"]["tekst"] == f"RIO LOD API v3 — {r['_rio_resource']}"
        else:
            assert r["documentatie"]["url"] == "https://lod.onderwijsregistratie.nl/rio-api"
            assert "alleen als sub-resource" in r["documentatie"]["tekst"]


def test_alle_14_resources_in_contract():
    assert {r["_rio_resource"] for r in riodata.catalog("rio")} == set(filtercontract()["resources"])
    assert set(fc.lijstresources()) == set(filtercontract()["resources"]) - ZONDER_LIJST
    assert filtercontract()["server"] == SERVER
    assert filtercontract()["spec_versie"] == "3.0.0"


def test_typefilters_heten_type():
    per_res = {r["_rio_resource"]: r["filters"] for r in riodata.catalog("rio")}
    assert per_res["erkenningen"] == ["type", "volledigeNaam", "plaatsnaam", "datumGeldigOp"]
    assert per_res["opleidingen"] == ["datumGeldigOp", "type"]  # hernoemd op zijn plaats
    assert per_res["organisatorische-eenheden"][0] == "type"
    f = {x["naam"]: x for x in filtercontract()["resources"]["erkenningen"]["filters"]}
    assert f["type"]["enum"] == [
        "BEVOEGD_GEZAG", "ERKENDE_ONDERWIJSINSTELLING", "ERKENDE_ONDERWIJSONDERSTEUNER",
        "ERKENDE_SAMENWERKING", "ERKENDE_VESTIGING"]
    assert len({x["naam"]: x for x in filtercontract()["resources"]["opleidingen"]["filters"]}["type"]["enum"]) == 34


def test_resources_zonder_lijstendpoint_zijn_alleen_subresource():
    res = filtercontract()["resources"]
    for naam in ZONDER_LIJST:
        assert res[naam]["lijst_endpoint"] is False and res[naam]["paginering"] == []
        assert res[naam]["catalogus_zonder_spec"] == []
    assert res["aangeboden-opleiding-cohorten"]["via"] == ["/aangeboden-opleidingen/{id}/aangeboden-opleiding-cohorten"]
    assert [f["naam"] for f in res["aangeboden-opleiding-cohorten"]["filters"]] == ["aanmeldperiode"]
    assert res["contactadressen"]["via"] == ["/organisatorische-eenheden/{id}/contactadressen"]
    assert res["onderwijslocatiegebruiken"]["via"] == [
        "/erkenningen/{id}/onderwijslocatiegebruiken",
        "/onderwijslocaties/{id}/onderwijslocatiegebruiken",
        "/organisatorische-eenheden/{id}/onderwijslocatiegebruiken",
    ]
    assert [f["naam"] for f in res["onderwijslocatiegebruiken"]["filters"]] == ["datumGeldigOp"]
    assert all(f["bron"] == "openapi (sub-resource)" for f in res["onderwijslocatiegebruiken"]["filters"])
    for naam in set(res) - ZONDER_LIJST:
        assert res[naam]["lijst_endpoint"] is True and "via" not in res[naam]


def test_geen_lijstendpoint_is_een_probleem_en_fetch_weigert_voor_het_netwerk(monkeypatch):
    (p,) = valideer_filters("contactadressen", {"datumGeldigOp": "2026-01-01"})
    assert p["probleem"] == "geen lijst-endpoint" and "/organisatorische-eenheden/{id}/contactadressen" in p["herstel"]

    def geen_netwerk(*a, **k):
        raise AssertionError("fetch mag voor een resource zonder lijst-endpoint geen request doen")

    monkeypatch.setattr(httpx, "get", geen_netwerk)
    with pytest.raises(ValueError, match="related"):
        riodata.fetch("aangeboden-opleiding-cohorten", aanmeldperiode="2026-09-01")
    assert riodata.client.zonder_lijstendpoint("erkenningen") is None
    assert riodata.client.zonder_lijstendpoint("bestaat-niet") is None  # onbekend: de API beslist


def test_sub_resources_uit_de_spec():
    res = filtercontract()["resources"]
    assert res["erkenningen"]["sub_resources"] == [
        "examenlicenties", "financieringsbesluiten", "instellingsrelaties", "onderwijslicenties",
        "onderwijslocatiegebruiken", "organisatorische-eenheden"]
    assert res["aangeboden-opleidingen"]["sub_resources"] == [
        "aangeboden-opleiding-cohorten", "onderwijslocatie", "opleiding", "opleidingsfase", "opleidingsgroep",
        "opleidingsonderdeel", "organisatorische-eenheid"]  # v2: onderwijsaanbieder
    assert res["opleidingen"]["sub_resources"] == ["aangeboden-opleidingen", "opleidingserkenningen", "opleidingsrelaties"]
    assert res["onderwijslocaties"]["sub_resources"] == ["onderwijslocatiegebruiken"]


def test_sort_zonder_waarden_in_spec_is_vastgelegd():
    for naam in fc.lijstresources():
        res = filtercontract()["resources"][naam]
        assert "sort" in res["paginering"]
        assert res["sort_schema_in_spec"] is False
        assert "sort" not in {f["naam"] for f in res["filters"]}


def test_contract_is_actueel_met_spec():
    """Het contractbestand moet gelijk zijn aan wat de generator nu uit de spec maakt."""
    pytest.importorskip("yaml")
    nieuw = _generator().bouw_contract(ROOT / "RIO_LOD_API_v3.yml")
    assert nieuw == filtercontract(), "Draai catalogus/genereer_filtercontract.py opnieuw"


def test_generator_laat_de_catalogus_ongewijzigd_als_hij_al_klopt(tmp_path):
    """Idempotent: nog een keer draaien verandert niets, ook niet aan de bronbestanden in data/02-prepared."""
    pytest.importorskip("yaml")
    mod = _generator()
    contract = mod.bouw_contract()
    for bron in [*(mod.DATA / n for n in mod.CATALOGI), *mod.BRONCATALOGI]:
        kopie = tmp_path / bron.name
        kopie.write_bytes(bron.read_bytes())
        assert mod.sync_catalogus(contract, kopie) == 0, bron
        assert kopie.read_bytes() == bron.read_bytes(), bron


def test_generator_hernoemt_op_zijn_plaats_en_behoudt_opmaak(tmp_path):
    pytest.importorskip("yaml")
    mod = _generator()
    contract = mod.bouw_contract()
    pad = tmp_path / "c.json"
    pad.write_text(
        '[\n  {\n    "documentatie": {\n      "tekst": "RIO LOD API v2 — opleidingen",\n'
        '      "url": "https://lod.onderwijsregistratie.nl/api/rio/v2/opleidingen"\n    },\n'
        '    "filters": ["datumGeldigOp", "opleidingseenheidtype", "eigenFilter"],\n'
        '    "sub_resources": [],\n    "_rio_resource": "opleidingen"\n  }\n]\n', encoding="utf-8")
    assert mod.sync_catalogus(contract, pad) == 1
    tekst = pad.read_text(encoding="utf-8")
    (r,) = json.loads(tekst)
    assert r["filters"] == ["datumGeldigOp", "type", "eigenFilter"]
    assert r["sub_resources"] == ["aangeboden-opleidingen", "opleidingserkenningen", "opleidingsrelaties"]
    assert r["documentatie"] == {"tekst": "RIO LOD API v3 — opleidingen", "url": f"{SERVER}/opleidingen"}
    assert '"filters": ["datumGeldigOp", "type", "eigenFilter"]' in tekst  # één regel blijft één regel


def test_enums_komen_uit_spec_en_niet_uit_voorbeelden():
    f = {x["naam"]: x for x in filtercontract()["resources"]["aangeboden-opleidingen"]["filters"]}
    assert len(f["type"]["enum"]) == 10
    assert f["datumGeldigOp"]["format"] == "date"
    assert f["onderwijslocatieId"]["enum"] is None


def test_mbo_selectie_volgt_spec_enum():
    waarden = typewaarden("aangeboden-opleidingen", "mbo")
    assert waarden == ["AANGEBODENMBOOPLEIDING", "AANGEBODENMBOOPLEIDINGSONDERDEEL"]
    opl = typewaarden("opleidingen", "mbo")
    assert "MBOKWALIFICATIE" in opl and all(w.startswith("MBO") for w in opl)
    assert not any(w.startswith("HO") for w in opl)


def test_ho_breed_en_geen_gegokt_hbo_wo():
    assert typewaarden("aangeboden-opleidingen", "ho") == [
        "AANGEBODENHOOPLEIDING", "AANGEBODENHOOPLEIDINGSONDERDEEL"]
    for sector in ("hbo", "wo"):
        with pytest.raises(ValueError, match="onderscheiden"):
            typewaarden("aangeboden-opleidingen", sector)


def test_typewaarden_onbekende_sector_en_resource():
    with pytest.raises(ValueError, match="Onbekend sector"):
        typewaarden("opleidingen", "vo-ish")
    with pytest.raises(ValueError, match="Onbekend resource"):
        typewaarden("opleidingn", "mbo")
    with pytest.raises(ValueError, match="geen type-filter"):
        typewaarden("examenlicenties", "mbo")


def test_valideer_geldig():
    assert valideer_filters("opleidingen", {"type": "HOOPLEIDING", "pageSize": 5}) == []
    assert valideer_filters("erkenningen", {"type": "BEVOEGD_GEZAG", "volledigeNaam": "ROC Mondriaan",
                                            "datumGeldigOp": "2026-10-19"}) == []


def test_valideer_geeft_herstelopties():
    (p,) = valideer_filters("erkenningen", {"type": "X"})
    assert p["probleem"] == "ongeldige waarde" and "BEVOEGD_GEZAG" in p["herstel"]
    (p,) = valideer_filters("erkenningen", {"erkenningtype": "BEVOEGD_GEZAG"})  # de v2-naam
    assert p["probleem"] == "onbekend filter" and "type" in p["herstel"]
    (p,) = valideer_filters("opleidingen", {"typ": "HOOPLEIDING"})
    assert "type" in p["herstel"]
    (p,) = valideer_filters("opleidingen", {"datumGeldigOp": "01-01-2024"})
    assert p["probleem"] == "ongeldige datum" and "YYYY-MM-DD" in p["herstel"]


def test_valideer_catalogusfilter_zonder_spec_is_waarschuwing(monkeypatch):
    """Een filter dat de catalogus noemt maar de spec niet: geen weigering, wel een waarschuwing."""
    contract = json.loads(json.dumps(filtercontract()))
    contract["resources"]["opleidingen"]["catalogus_zonder_spec"] = [
        {"naam": "eigenFilter", "status": "niet in spec; live ondersteuning niet vastgesteld"}]
    monkeypatch.setattr(fc, "filtercontract", lambda: contract)
    (p,) = valideer_filters("opleidingen", {"eigenFilter": "x"})
    assert p["probleem"] == "waarschuwing"


def test_onmogelijke_datum_en_ongeldige_uuid_zijn_niet_geldig():
    """Review F6: de oude regex liet 2026-02-31 en een rij streepjes door."""
    (p,) = valideer_filters("opleidingen", {"datumGeldigOp": "2026-02-31"})
    assert p["probleem"] == "ongeldige datum"
    (p,) = valideer_filters("onderwijslocaties", {"aangebodenOpleidingId": "-" * 36})
    assert p["probleem"] == "ongeldige uuid"
    assert valideer_filters("opleidingen", {"datumGeldigOp": "2024-02-29"}) == []        # schrikkeljaar
    assert valideer_filters("opleidingen", {"datumGeldigOp": "2023-02-29"})[0]["probleem"] == "ongeldige datum"
    assert valideer_filters("onderwijslocaties", {"aangebodenOpleidingId": "123e4567-e89b-12d3-a456-426614174000"}) == []
    assert valideer_filters("onderwijslocaties", {"aangebodenOpleidingId": "123e4567e89b12d3a456426614174000"})[0]["probleem"] == "ongeldige uuid"


def test_aangeboden_types_worden_gevalideerd():
    assert valideer_filters("opleidingen", {"datumGeldigOp": 20260101})[0]["probleem"] == "ongeldig type"
    assert valideer_filters("opleidingen", {"type": ["HOOPLEIDING"]})[0]["probleem"] == "ongeldig type"
    assert valideer_filters("opleidingen", {"pageSize": "10"})[0]["probleem"] == "ongeldig type"
    assert valideer_filters("opleidingen", {"page": True})[0]["probleem"] == "ongeldig type"
    assert valideer_filters("opleidingen", {"page": 0, "pageSize": 50, "sort": "naam"}) == []
