"""Resource-schema's per CKAN-UUID (RIO-10), offline."""
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus"))

import resource_schemas as rs  # noqa: E402
import sync_kolommen  # noqa: E402

import riodata  # noqa: E402
from riodata import duo  # noqa: E402

SNAP = duo._schema_snapshot()


def _alle():
    for ds, d in SNAP["datasets"].items():
        for r in d["resources"]:
            yield ds, r


def test_alle_datasets_en_resources_hebben_inspectiestatus():
    assert {r["_ckan_id"] for r in riodata.catalog(source="duo")} <= set(SNAP["datasets"])
    for ds, r in _alle():
        assert r["inspectie"]["status"] in {"ok", "mislukt", "geen_tabel", "alleen_kop", "schema_conflict"}, (ds, r["naam"])
        assert r["resource_id"]
        if r["inspectie"]["status"] == "mislukt":
            assert r["inspectie"]["fout"]


def test_alle_resources_van_p01_beschreven():
    """Niet meer alleen de eerste vijf: p01 heeft zes resources."""
    assert len(duo.resource_schemas("p01hoinges")) == 6
    assert all(r["inspectie"]["status"] == "ok" for r in duo.resource_schemas("p01hoinges"))


def test_steekproef_is_nooit_een_domein():
    for ds, r in _alle():
        w = r.get("waarden")
        if not w:
            continue
        if w["methode"] == "steekproef":
            assert w["volledig"] is False
            for info in w["kolommen"].values():
                assert set(info) == {"voorbeeldwaarden"}, (ds, r["naam"])
        else:
            assert w["methode"] == "volledige_scan" and w["volledig"] is True
            for info in w["kolommen"].values():
                assert "voorbeeldwaarden" not in info


def test_volledig_jaardomein_p01():
    """Oude sample zei 2021-2021; de volledige scan geeft vijf studiejaren."""
    s = duo.resource_schema("p01hoinges", "c454d7e1-b9b1-4460-b9ff-55938c85788e")
    info = s["waarden"]["kolommen"]["STUDIEJAAR"]
    assert info["domein"] == ["2021", "2022", "2023", "2024", "2025"]
    assert (info["min"], info["max"]) == (2021, 2025)


def test_gemeentenummer_blijft_tekst():
    s = duo.resource_schema("p01hoinges", 0)
    kol = {k["naam"]: k for k in s["kolommen"]}
    assert kol["GEMEENTENUMMER"]["type"] == "text" and kol["GEMEENTENUMMER"]["type_bron"] == "datastore"
    assert "0106" in s["waarden"]["kolommen"]["GEMEENTENUMMER"]["domein"]
    cat = next(r for r in riodata.catalog(source="duo") if r["_ckan_id"] == "p01hoinges")
    for res, types in cat["_kolomtypes"].items():
        assert types["GEMEENTENUMMER"].startswith("tekst"), res
        assert all(isinstance(v, str) and len(v) == 4 for v in cat["_kolommen"][res]["GEMEENTENUMMER"])


def test_reader_leest_tekstkolommen_als_tekst(monkeypatch):
    pd = pytest.importorskip("pandas")
    rid = "c454d7e1-b9b1-4460-b9ff-55938c85788e"
    monkeypatch.setattr(duo, "resources", lambda ds: [{"naam": "x", "url": "u", "format": "CSV", "id": rid}])

    class R:
        content = b"STUDIEJAAR,GEMEENTENUMMER,AANTAL_INGESCHREVENEN\n2021,0106,33\n"
        headers = {}
        def raise_for_status(self): pass

    monkeypatch.setattr(duo.httpx, "get", lambda *a, **k: R())
    df = duo.load("p01hoinges", rid)
    assert df["GEMEENTENUMMER"].tolist() == ["0106"]
    assert df["AANTAL_INGESCHREVENEN"].dtype.kind in "iu"
    assert df.attrs["bron"]["resource_id"] == rid and df.attrs["bron"]["schema_sha256"]
    # expliciete dtype van de gebruiker wint
    df2 = duo.load("p01hoinges", rid, dtype={"GEMEENTENUMMER": "int64"})
    assert df2["GEMEENTENUMMER"].tolist() == [106]


def test_schema_alleen_op_exacte_uuid():
    assert duo._schema_voor("p01hoinges", "c454d7e1-b9b1-4460-b9ff-55938c85788e")
    assert duo._schema_voor("p01hoinges", "00000000-0000-0000-0000-000000000000") is None


def test_definities_per_resource_niet_geerfd():
    for s in duo.resource_schemas("p01hoinges"):
        assert set(s["definities"]) <= {k["naam"] for k in s["kolommen"]}
    geslacht = [s for s in duo.resource_schemas("p01hoinges") if "geslacht" in s["naam"]]
    anders = [s for s in duo.resource_schemas("p01hoinges") if "geslacht" not in s["naam"]]
    assert all("GESLACHT" in s["definities"] for s in geslacht)
    assert all("GESLACHT" not in s["definities"] for s in anders)


def test_schemahash_verandert_bij_schemawijziging():
    a = [{"naam": "X", "type": "text"}]
    b = [{"naam": "X", "type": "numeric"}]
    assert rs.schema_hash(a) != rs.schema_hash(b)
    for ds, r in _alle():
        if r["kolommen"]:
            assert r["schema_sha256"] == rs.schema_hash(r["kolommen"])


def test_technisch_aantal_alleen_laadcontrole():
    for ds, r in _alle():
        if r["inspectie"]["methode"] and "volledige" in r["inspectie"]["methode"] and r["technisch_aantal_rijen"]:
            assert r["csv_aantal_rijen"] == r["technisch_aantal_rijen"] or ds == "rio_nfo_po_vo_vavo_mbo_ho"


# ── pure helpers van de generator ────────────────────────────────────────────

def test_datastore_kolommen_zonder_id():
    k = rs.datastore_kolommen([{"id": "_id", "type": "int"}, {"id": "A", "type": "text"}])
    assert k == [{"naam": "A", "type": "text", "type_bron": "datastore"}]


def test_volledige_en_steekproefwaarden_gescheiden():
    kol = [{"naam": "J", "type": "numeric"}, {"naam": "G", "type": "text"}]
    rijen = [{"J": "2021", "G": "0106"}, {"J": "2022", "G": ""}]
    v = rs.volledige_waarden(rijen, kol)
    assert v["kolommen"]["J"] == {"aantal_uniek": 2, "aantal_leeg": 0, "domein": ["2021", "2022"], "min": 2021, "max": 2022}
    assert v["kolommen"]["G"]["domein"] == ["0106"] and v["kolommen"]["G"]["aantal_leeg"] == 1
    s = rs.steekproef_waarden(rijen, kol)
    assert s["volledig"] is False and s["kolommen"]["G"] == {"voorbeeldwaarden": ["0106"]}


def test_lees_csv_en_separator():
    namen, rijen = rs.lees_csv("A;B\n0106;x\n".encode("utf-8"))
    assert namen == ["A", "B"] and rijen[0]["A"] == "0106"
    assert rs.sniff_sep("﻿A,B,C\n") == ","


def test_dataset_meta_themas():
    p = {"title": "T", "groups": [{"name": "hoger-onderwijs"}],
         "extras": [{"key": "theme", "value": '["http://x/Voortgezet_onderwijs_(thema)"]'}]}
    m = rs.dataset_meta(p)
    assert m["ckan_groepen"] == ["hoger-onderwijs"] and m["dcat_themas"] == ["http://x/Voortgezet_onderwijs_(thema)"]


def test_sync_markeert_steekproef():
    schema = {"kolommen": [{"naam": "G", "type": "text"}],
              "waarden": {"methode": "steekproef", "volledig": False, "kolommen": {"G": {"voorbeeldwaarden": ["0106"]}}}}
    kolommen, types = sync_kolommen.kolommen_en_types(schema)
    assert kolommen == {"G": ["0106"]} and types == {"G": "tekst; steekproef"}


def _inspecteer(monkeypatch, velden: list[str], csv_kop: str) -> dict:
    monkeypatch.setattr(rs, "_ckan", lambda client, actie, **p: {
        "fields": [{"id": "_id", "type": "int"}] + [{"id": v, "type": "text"} for v in velden],
        "records": [],
    })

    class R:
        content = f"{csv_kop}\na,b\n".encode()

    monkeypatch.setattr(rs, "_get", lambda client, url, **p: R())
    res = {"id": "r1", "format": "CSV", "size": 10, "datastore_active": True, "url": "https://x/r1.csv"}
    return rs.inspecteer_resource(None, res, max_bytes=1000, vandaag="2026-10-05")


def test_csv_die_afwijkt_van_datastore_is_een_conflict(monkeypatch):
    """#390 A3: een CSV met andere kolommen dan het Datastore-schema is geen 'ok'."""
    uit = _inspecteer(monkeypatch, ["A", "B"], "A,C")
    assert uit["csv_kolommen_gelijk_aan_schema"] is False
    assert uit["inspectie"]["status"] == "schema_conflict"
    assert "C" in uit["inspectie"]["fout"] and "B" in uit["inspectie"]["fout"]


def test_csv_gelijk_aan_datastore_blijft_ok(monkeypatch):
    uit = _inspecteer(monkeypatch, ["A", "B"], "A,B")
    assert uit["inspectie"]["status"] == "ok"
