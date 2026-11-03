"""DUO-catalogus en -zoeken pagineren op CKAN's count (onderwijsdata-chat#26), offline."""
from riodata import duo


def _ckan_met(monkeypatch, aantal: int) -> list[dict]:
    pakketten = [{"name": f"ds-{i}"} for i in range(aantal)]
    vragen = []

    def ckan(endpoint, **params):
        vragen.append(params)
        start, rows = params.get("start", 0), params["rows"]
        return {"count": aantal, "results": pakketten[start:start + rows]}

    monkeypatch.setattr(duo, "_ckan", ckan)
    monkeypatch.setattr(duo, "_pkg_to_record", lambda p: p["name"])
    return vragen


def test_catalogus_haalt_meer_dan_een_pagina(monkeypatch):
    vragen = _ckan_met(monkeypatch, 230)
    assert duo.catalog() == [f"ds-{i}" for i in range(230)]
    assert [v["start"] for v in vragen] == [0, 100, 200]


def test_zoeken_haalt_alle_treffers(monkeypatch):
    vragen = _ckan_met(monkeypatch, 120)
    assert len(duo.search("studenten")) == 120
    assert all(v["q"] == "studenten" for v in vragen)


def test_een_pagina_is_een_vraag(monkeypatch):
    vragen = _ckan_met(monkeypatch, 56)
    assert len(duo.catalog()) == 56
    assert len(vragen) == 1
