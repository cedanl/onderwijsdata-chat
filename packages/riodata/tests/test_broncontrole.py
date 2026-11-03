"""Broncontrole: wijzigingsdetectie op fixtures, zonder netwerk."""
import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("broncontrole", ROOT / "catalogus" / "broncontrole.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

T1 = dt.datetime(2026, 10, 5, 5, 0, tzinfo=dt.timezone.utc)
T2 = dt.datetime(2026, 10, 12, 5, 0, tzinfo=dt.timezone.utc)


def pkg(naam, mod="2026-01-01T00:00:00", notes="n", res=("r1",)):
    return {"name": naam, "metadata_modified": mod, "notes": notes, "resources": [{"id": r} for r in res]}


def run(oud, pkgs, ids, nu=T1):
    return bc.controleer(oud, duo_pkgs=pkgs, catalogus_ids=set(ids), nu=nu)


def test_ongewijzigde_bron_geeft_geen_melding_ook_na_lange_tijd():
    m1, meld1 = run(None, [pkg("a"), pkg("b")], ["a", "b"], T1)
    assert meld1 == []
    m2, meld2 = run(m1, [pkg("a"), pkg("b")], ["a", "b"], T2)
    assert meld2 == []
    assert m2["bronnen"]["duo_ckan"]["inhoud_sha256"] == m1["bronnen"]["duo_ckan"]["inhoud_sha256"]
    # wél een nieuwe controledatum, maar dezelfde bronwijzigingsdatum
    assert m2["bronnen"]["duo_ckan"]["laatste_succesvolle_controle"] > m1["bronnen"]["duo_ckan"]["laatste_succesvolle_controle"]
    assert m2["bronnen"]["duo_ckan"]["bron_laatst_gewijzigd"] == "2026-01-01T00:00:00"


def test_verwijderde_en_nieuwe_dataset_geven_reviewmelding():
    _, meld = run(None, [pkg("a"), pkg("nieuw")], ["a", "weg"])
    assert any("nieuwe dataset" in m and "nieuw" in m for m in meld)
    assert any("niet meer in CKAN" in m and "weg" in m for m in meld)


def test_gewijzigde_resource_en_beschrijving_worden_benoemd():
    m1, _ = run(None, [pkg("a")], ["a"])
    _, meld = run(m1, [pkg("a", mod="2026-09-01T00:00:00", res=("r1", "r2"))], ["a"], T2)
    assert len(meld) == 1 and "resources" in meld[0] and "2026-09-01" in meld[0]
    _, meld = run(m1, [pkg("a", notes="andere tekst")], ["a"], T2)
    assert "beschrijving" in meld[0]


def test_verplaatste_resource_is_zichtbaar():
    m1, _ = run(None, [pkg("a", res=("r1",))], ["a"])
    _, meld = run(m1, [pkg("a", res=("r9",))], ["a"], T2)
    assert "resources" in meld[0]


def test_vier_tijdstempels_staan_los_van_elkaar():
    m, _ = bc.controleer(None, duo_pkgs=[pkg("a", mod="2025-05-05T00:00:00")], catalogus_ids={"a"}, nu=T1,
                         catalogus_gebouwd="2026-07-16")
    duo = m["bronnen"]["duo_ckan"]
    assert duo["laatste_succesvolle_controle"].startswith("2026-10-05")
    assert duo["bron_laatst_gewijzigd"] == "2025-05-05T00:00:00"
    assert m["catalogus_gebouwd"] == "2026-07-16" and duo["aantal"] == 1


def test_nietgecontroleerde_bronnen_worden_expliciet_genoemd(tmp_path):
    m, _ = bc.controleer(None, duo_pkgs=[pkg("a")], catalogus_ids={"a"}, nu=T1,
                         spec_pad=tmp_path / "ontbreekt.yml", contract_pad=tmp_path / "ontbreekt.json")
    # review F8: een stil overgeslagen contractcheck moet zichtbaar zijn
    assert set(m["niet_gecontroleerd"]) == {"rio_contract", "rio_live", "sbb", "roa", "uwv", "inspectie"}
    assert m["niet_gecontroleerd"][0] == "rio_live"  # zonder statussen is RIO live niet gecontroleerd
    assert "rio_contract" not in m["bronnen"]


def test_rio_spec_die_afwijkt_van_contract_is_review(tmp_path):
    spec = tmp_path / "spec.yml"
    spec.write_text("openapi: 3.0.0\n")
    contract = tmp_path / "c.json"
    contract.write_text(json.dumps({"resources": {"x": {}}, "spec_sha256": "anders"}))
    _, meld = bc.controleer(None, duo_pkgs=[pkg("a")], catalogus_ids={"a"}, spec_pad=spec, contract_pad=contract, nu=T1)
    assert any(m.startswith("RIO:") for m in meld)


def test_meegeleverde_spec_komt_overeen_met_contract():
    _, meld = run(None, [pkg("a")], ["a"])
    assert not any(m.startswith("RIO:") for m in meld)


def test_mislukte_controle_laat_manifest_staan(tmp_path, monkeypatch):
    pad = tmp_path / "m.json"
    pad.write_text('{"oud": true}')

    def stuk(client):
        raise RuntimeError("CKAN down")
    monkeypatch.setattr(bc, "fetch_duo", stuk)
    assert bc.main(["--manifest", str(pad), "--schrijf"]) == 1
    assert pad.read_text() == '{"oud": true}'


def test_exitcodes_en_schrijven(tmp_path, monkeypatch):
    pad = tmp_path / "m.json"
    monkeypatch.setattr(bc, "fetch_duo", lambda c: [pkg("a")])
    monkeypatch.setattr(bc, "_catalogus_ids", lambda: {"a"})
    assert bc.main(["--manifest", str(pad), "--schrijf"]) in (0, 10)
    assert json.loads(pad.read_text())["schema_versie"] == 1
    monkeypatch.setattr(bc, "_catalogus_ids", lambda: {"a", "weg"})
    assert bc.main(["--manifest", str(pad)]) == 10


class FakeCkan:
    """Fake HTTP-client die CKAN-pagina's levert."""

    def __init__(self, paginas, count):
        self.paginas, self.count, self.aanroepen = paginas, count, 0

    def get(self, url, params=None, timeout=None):
        i = self.aanroepen
        self.aanroepen += 1
        batch = self.paginas[i] if i < len(self.paginas) else []
        body = {"success": True, "result": {"count": self.count, "results": batch}}

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return body
        return R()


def test_volledige_paginering_wordt_geaccepteerd():
    assert [p["name"] for p in bc.fetch_duo(FakeCkan([[pkg("a")], [pkg("b")]], 2))] == ["a", "b"]


def test_lege_pagina_voor_het_einde_is_een_mislukte_controle():
    """Review F8: count=2, pagina 2 onverwacht leeg."""
    with pytest.raises(RuntimeError, match="onvolledig"):
        bc.fetch_duo(FakeCkan([[pkg("a")], []], 2))


def test_count_wijkt_af_of_dubbele_namen_is_mislukt():
    with pytest.raises(RuntimeError, match="inconsistent"):
        bc.fetch_duo(FakeCkan([[pkg("a"), pkg("a")]], 2))
    with pytest.raises(RuntimeError, match="inconsistent"):
        bc.fetch_duo(FakeCkan([[pkg("a"), pkg("b"), pkg("c")]], 2))


def test_onvolledige_inventaris_overschrijft_het_manifest_niet(tmp_path, monkeypatch):
    pad = tmp_path / "m.json"
    pad.write_text('{"oud": true}')
    monkeypatch.setattr(bc, "_catalogus_ids", lambda: {"a", "b"})

    class Client:
        def __enter__(self):
            return FakeCkan([[pkg("a")], []], 2)

        def __exit__(self, *a):
            return False

    import httpx
    monkeypatch.setattr(httpx, "Client", Client)
    assert bc.main(["--manifest", str(pad), "--schrijf"]) == 1
    assert pad.read_text() == '{"oud": true}'


def test_rio_live_statussen_anders_dan_200_zijn_review():
    m, meld = bc.controleer(None, duo_pkgs=[pkg("a")], catalogus_ids={"a"}, nu=T1,
                            rio_statussen={"erkenningen": 200, "opleidingen": 410, "onderwijslocaties": 0})
    assert "rio_live" not in m["niet_gecontroleerd"]
    assert m["bronnen"]["rio_live"]["aantal"] == 3
    assert meld == [
        "RIO: onderwijslocaties antwoordt HTTP 0 op https://lod.onderwijsregistratie.nl/api/rio/v3/onderwijslocaties?pageSize=1",
        "RIO: opleidingen antwoordt HTTP 410 op https://lod.onderwijsregistratie.nl/api/rio/v3/opleidingen?pageSize=1",
    ]


def test_rio_live_alle_200_geeft_geen_melding():
    m, meld = bc.controleer(None, duo_pkgs=[pkg("a")], catalogus_ids={"a"}, nu=T1, rio_statussen={"erkenningen": 200})
    assert meld == [] and m["bronnen"]["rio_live"]["items"] == {"erkenningen": 200}


def test_ping_rio_vraagt_alleen_lijstresources(tmp_path):
    contract = {"resources": {"erkenningen": {"lijst_endpoint": True}, "contactadressen": {"lijst_endpoint": False, "via": []},
                              "opleidingen": {}}}
    pad = tmp_path / "c.json"
    pad.write_text(json.dumps(contract), encoding="utf-8")

    class Antwoord:
        def __init__(self, code):
            self.status_code = code

    class Client:
        def __init__(self):
            self.urls = []

        def get(self, url, params=None, timeout=None):
            self.urls.append(url)
            if url.endswith("/opleidingen"):
                raise OSError("time-out")
            return Antwoord(200)

    client = Client()
    assert bc.ping_rio(client, pad) == {"erkenningen": 200, "opleidingen": 0}
    assert all("/api/rio/v3/" in u for u in client.urls) and not any("contactadressen" in u for u in client.urls)
