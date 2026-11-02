"""De sweep van de bron-ping over elke dataset die de chat kan opvragen (#869).

De pings halen per bron één dataset op; een verdwenen CBS-tabel, een verschoven DUO-kolom of een RIO-register dat
niet antwoordt viel daarbuiten. De sweep meldt zulke afwijkingen als waarschuwing, zonder de job rood te maken.
"""

import json

import httpx
import pytest
from riodata import duo as riodata_duo

from scripts import bronping, bronsweep
from tools import catalog, duo_laden

_CBS = "85423NED"
_DUO = "p01hoinges"


def _status(code: int) -> httpx.HTTPStatusError:
    verzoek = httpx.Request("GET", "https://bron.test/")
    return httpx.HTTPStatusError(f"HTTP {code}", request=verzoek, response=httpx.Response(code, request=verzoek))


# --- CBS -------------------------------------------------------------------------------------


def test_cbs_modified_gelijk_aan_de_catalogus_is_ok(monkeypatch):
    datum = catalog.catalogus_laatste_update(_CBS)
    assert datum is not None
    monkeypatch.setattr(bronsweep, "cbs_get", lambda id, pad: [{"Modified": f"{datum}T02:00:00"}])
    [b] = bronsweep.cbs_tabel(_CBS)
    assert b.ok and datum in b.detail


def test_cbs_een_latere_modified_is_een_afwijking_met_beide_datums(monkeypatch):
    datum = catalog.catalogus_laatste_update(_CBS)
    monkeypatch.setattr(bronsweep, "cbs_get", lambda id, pad: [{"Modified": "2099-01-01T02:00:00"}])
    [b] = bronsweep.cbs_tabel(_CBS)
    assert not b.ok
    assert "2099-01-01" in b.detail and str(datum) in b.detail


def test_cbs_gebruikt_dezelfde_herhaling_als_de_chat(monkeypatch):
    """#867: ook de sweep probeert een tijdelijke 503 opnieuw."""
    datum = catalog.catalogus_laatste_update(_CBS)
    antwoorden = [_status(503), [{"Modified": f"{datum}T02:00:00"}]]

    def get(id, pad):
        uit = antwoorden.pop(0)
        if isinstance(uit, Exception):
            raise uit
        return uit

    monkeypatch.setattr(bronsweep, "cbs_get", get)
    [b] = bronsweep.cbs_tabel(_CBS)
    assert b.ok and not antwoorden


def test_een_verdwenen_tabel_is_een_afwijking_met_de_status(monkeypatch):
    def weg(id, pad):
        raise _status(404)

    monkeypatch.setattr(bronsweep, "cbs_get", weg)
    [b] = bronsweep.voer_uit([bronsweep.Controle("cbs", _CBS, lambda: bronsweep.cbs_tabel(_CBS))])
    assert (b.ok, b.detail) == (False, "HTTP 404")


# --- DUO -------------------------------------------------------------------------------------


@pytest.fixture
def duo_live(monkeypatch):
    """De bestanden van p01hoinges zoals in de snapshot, met hun kopregel; een test verandert er één ding aan."""
    schemas = [s for s in riodata_duo.resource_schemas(_DUO) if s["inspectie"]["status"] == "ok"]
    bestanden = [
        {"id": s["resource_id"], "naam": s["naam"], "url": f"https://duo.test/{i}.csv", "format": "CSV"}
        for i, s in enumerate(schemas)
    ]
    koppen = {f"https://duo.test/{i}.csv": [k["naam"] for k in s["kolommen"]] for i, s in enumerate(schemas)}
    monkeypatch.setattr(riodata_duo, "resources", lambda dataset_id: bestanden)
    monkeypatch.setattr(duo_laden, "kolommen_uit_kop", lambda url, bron="": koppen[url])
    return bestanden, koppen


def test_duo_bestanden_gelijk_aan_de_snapshot_zijn_ok(duo_live):
    bevindingen = bronsweep.duo_dataset(_DUO)
    assert len(bevindingen) == len(duo_live[0])
    assert all(b.ok for b in bevindingen), bevindingen


def test_duo_een_hernoemde_kolom_is_kolomdrift_per_bestand(duo_live):
    _, koppen = duo_live
    kop = koppen["https://duo.test/1.csv"]
    oud = kop[0]
    kop[0] = "HERNOEMD"
    afwijkingen = [b for b in bronsweep.duo_dataset(_DUO) if not b.ok]
    assert [(b.id, b.detail) for b in afwijkingen] == [
        (f"{_DUO}[1]", f"kolomdrift: ontbreekt: {oud}; nieuw: HERNOEMD"),
    ]


def test_duo_een_nieuw_en_een_verdwenen_bestand_zijn_afwijkingen(duo_live):
    bestanden, _ = duo_live
    weg = bestanden.pop(0)
    bestanden.append({"id": "nieuw-id", "naam": "Nieuw bestand", "url": "https://duo.test/nieuw.csv", "format": "CSV"})
    details = [b.detail for b in bronsweep.duo_dataset(_DUO) if not b.ok]
    assert any("nieuw bestand" in d and "Nieuw bestand" in d for d in details)
    assert any("niet meer bij DUO" in d and weg["naam"][:40] in d for d in details)


# --- RIO en de sweep -----------------------------------------------------------------------------


def test_rio_een_register_zonder_records_is_een_afwijking(monkeypatch):
    monkeypatch.setattr(bronsweep, "rio_fetch", lambda resource, **kw: [])
    assert not bronsweep.rio_register("opleidingen")[0].ok
    monkeypatch.setattr(bronsweep, "rio_fetch", lambda resource, **kw: [{"code": "1"}])
    assert bronsweep.rio_register("opleidingen")[0].ok


def test_de_sweep_loopt_dezelfde_lijst_langs_als_de_telling_van_de_chat():
    telling = catalog.dataset_counts()
    lijst = bronsweep.controles(bronsweep.BRONNEN)
    assert {b: sum(1 for c in lijst if c.bron == b) for b in bronsweep.BRONNEN} == {
        "cbs": telling["CBS"],
        "duo": telling["DUO"],
        "rio": telling["RIO"],
    }


def test_na_de_tijdsgrens_start_geen_controle_meer():
    tijden = iter([0.0, 10.0, 200.0])
    lijst = [bronsweep.Controle("rio", f"r{i}", lambda: [bronsweep.Bevinding("rio", "r", True, "")]) for i in range(2)]
    bevindingen = bronsweep.voer_uit(lijst, tijdsgrens_s=150, klok=lambda: next(tijden), werkers=1)
    assert [b.ok for b in bevindingen] == [True, False]
    assert "niet gecontroleerd" in bevindingen[1].detail


# --- in de bron-ping -------------------------------------------------------------------------


def test_een_afwijking_in_de_sweep_laat_de_bron_ping_groen_en_staat_in_het_rapport(monkeypatch, capsys, tmp_path):
    ping = bronping.Ping("cbs-a", "cbs", "t", haal=lambda: json.dumps({"totaal_rijen": 3}), bewijs=lambda u: None)
    monkeypatch.setattr(bronping, "PINGS", (ping,))
    afwijking = bronsweep.Bevinding("duo", f"{_DUO}[1]", False, "kolomdrift: nieuw: X")
    monkeypatch.setattr(bronsweep, "controles", lambda bronnen: [])
    monkeypatch.setattr(bronsweep, "voer_uit", lambda lijst: [afwijking])
    rapport = tmp_path / "sweep.json"

    assert bronping.main(["--sweep", "--rapport", str(rapport)]) == 0
    uit = capsys.readouterr().out
    assert "kolomdrift: nieuw: X" in uit
    assert "1 afwijking(en), als waarschuwing" in uit
    assert json.loads(rapport.read_text())["bevindingen"] == [
        {"bron": "duo", "id": f"{_DUO}[1]", "ok": False, "detail": "kolomdrift: nieuw: X"}
    ]


def test_zonder_sweep_geen_sweep(monkeypatch, capsys):
    ping = bronping.Ping("cbs-a", "cbs", "t", haal=lambda: json.dumps({"totaal_rijen": 3}), bewijs=lambda u: None)
    monkeypatch.setattr(bronping, "PINGS", (ping,))
    monkeypatch.setattr(bronsweep, "voer_uit", lambda lijst: pytest.fail("de sweep draait alleen met --sweep"))
    assert bronping.main([]) == 0
    assert "Sweep" not in capsys.readouterr().out
