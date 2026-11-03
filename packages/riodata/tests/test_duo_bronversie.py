"""De versie van een geladen DUO-bestand in ``df.attrs["bron"]``: wanneer DUO het verving, de md5 die
DUO opgeeft, de ETag van de download en de md5 van de bytes zelf. Zonder extra aanroep: alles komt uit
de package_show en de GET die ``load()`` al doet.

De live-test draait alleen op verzoek (``RIODATA_LIVE=1``), zoals tests/test_rio_live.py.
"""
import hashlib
import os

import pytest

from riodata import duo

INHOUD = b"STUDIEJAAR,GEMEENTENUMMER,AANTAL_INGESCHREVENEN\n2021,0106,33\n"
MD5 = hashlib.md5(INHOUD).hexdigest()
RID = "c454d7e1-b9b1-4460-b9ff-55938c85788e"


def _pakket(**resource) -> dict:
    return {"resources": [{"id": RID, "name": "Ingeschrevenen hbo", "format": "csv", "url": "https://x/download/a.csv", **resource}]}


class _Antwoord:
    content = INHOUD

    def __init__(self, headers: dict):
        self.headers = headers

    def raise_for_status(self):
        pass


def _laad(monkeypatch, pakket: dict, headers: dict):
    pytest.importorskip("pandas")
    monkeypatch.setattr(duo, "_ckan", lambda endpoint, **p: pakket)
    monkeypatch.setattr(duo.httpx, "get", lambda *a, **k: _Antwoord(headers))
    return duo.load("p01hoinges", RID)


def test_resources_geeft_de_bestandsversie_van_ckan(monkeypatch):
    monkeypatch.setattr(duo, "_ckan", lambda endpoint, **p: _pakket(last_modified="2026-04-08T12:51:36.650779", hash=MD5))
    (res,) = duo.resources("p01hoinges")
    assert res["last_modified"] == "2026-04-08T12:51:36.650779"
    assert res["hash"] == MD5


def test_resources_zonder_versie_is_none(monkeypatch):
    # Een datastore-dump: CKAN geeft last_modified None en hash ''.
    monkeypatch.setattr(duo, "_ckan", lambda endpoint, **p: _pakket(last_modified=None, hash=""))
    (res,) = duo.resources("p01hoinges")
    assert res["last_modified"] is None and res["hash"] is None


def test_load_legt_versie_hash_etag_en_md5_vast(monkeypatch):
    pakket = _pakket(last_modified="2026-04-08T12:51:36.650779", hash=MD5)
    df = _laad(monkeypatch, pakket, {"ETag": '"1775652696.7191002-782095-2030899828"'})
    bron = df.attrs["bron"]
    assert bron["last_modified"] == "2026-04-08T12:51:36.650779"
    assert bron["hash"] == MD5
    assert bron["etag"] == '"1775652696.7191002-782095-2030899828"'
    assert bron["md5"] == MD5, "md5 is van de geladen bytes; gelijk aan hash als DUO dit bestand registreerde"
    assert {"dataset_id", "resource_id", "resource_naam", "url", "schema_sha256"} <= set(bron), "bestaande sleutels blijven"


def test_load_van_een_dump_heeft_alleen_md5(monkeypatch):
    df = _laad(monkeypatch, _pakket(last_modified=None, hash=""), {})
    bron = df.attrs["bron"]
    assert bron["last_modified"] is None and bron["hash"] is None and bron["etag"] is None
    assert bron["md5"] == MD5


def test_md5_volgt_de_bytes_niet_de_opgave(monkeypatch):
    df = _laad(monkeypatch, _pakket(last_modified="2026-04-08T12:51:36", hash="0" * 32), {})
    assert df.attrs["bron"]["hash"] == "0" * 32
    assert df.attrs["bron"]["md5"] == MD5


@pytest.mark.skipif(not os.environ.get("RIODATA_LIVE"), reason="live DUO-test: zet RIODATA_LIVE=1")
def test_live_hash_van_duo_is_de_md5_van_het_bestand():
    pytest.importorskip("pandas")
    df = duo.load("p01hoinges", RID)
    bron = df.attrs["bron"]
    assert bron["last_modified"] and bron["etag"]
    assert bron["hash"] == bron["md5"]
