"""De SRAM-gebruikerscache is begrensd in tijd en omvang (#487, privacy M4).

`_oidc_user_cache` hield naam, e-mail en organisatie per gebruiker vast tot een herstart, zonder
maximum of vervaltijd. Nu vervalt een rij na SESSION_MAX en gaat boven het maximum de langst niet
gebruikte gebruiker eruit. De keuze voor `sub` als sleutel en gehashte wachtwoorden blijft een besluit.
"""

import pytest

from core.auth import SESSION_MAX
from routes import auth


@pytest.fixture(autouse=True)
def lege_cache(monkeypatch):
    monkeypatch.setattr(auth, "_oidc_user_cache", auth._oidc_user_cache.__class__())
    yield


def _klok(monkeypatch, start: float = 1000.0):
    nu = {"t": start}
    monkeypatch.setattr(auth.time, "monotonic", lambda: nu["t"])
    return nu


def test_bewaart_en_geeft_terug():
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna", "organisatie": "HU"})
    assert auth._get_oidc_user("anna@hu.nl") == {"name": "Anna", "organisatie": "HU"}
    assert auth._get_oidc_user("onbekend") is None


def test_een_rij_vervalt_na_de_maximale_sessieduur(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna"})
    nu["t"] += SESSION_MAX - 1
    assert auth._get_oidc_user("anna@hu.nl") == {"name": "Anna"}
    nu["t"] += 2
    assert auth._get_oidc_user("anna@hu.nl") is None
    assert "anna@hu.nl" not in auth._oidc_user_cache


def test_opnieuw_inloggen_verlengt_de_vervaltijd(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna"})
    nu["t"] += SESSION_MAX - 10
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna B"})
    nu["t"] += 20
    assert auth._get_oidc_user("anna@hu.nl") == {"name": "Anna B"}


def test_boven_het_maximum_gaat_de_langst_niet_gebruikte_eruit(monkeypatch):
    monkeypatch.setattr(auth, "_OIDC_CACHE_MAX", 2)
    auth._store_oidc_user("a", {"n": 1})
    auth._store_oidc_user("b", {"n": 2})
    auth._get_oidc_user("a")  # a is weer de jongste
    auth._store_oidc_user("c", {"n": 3})
    assert list(auth._oidc_user_cache) == ["a", "c"]
    assert auth._get_oidc_user("b") is None


def test_verlopen_rijen_verdwijnen_bij_het_opslaan_van_een_ander(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("oud", {"n": 1})
    nu["t"] += SESSION_MAX + 1
    auth._store_oidc_user("nieuw", {"n": 2})
    assert list(auth._oidc_user_cache) == ["nieuw"]
