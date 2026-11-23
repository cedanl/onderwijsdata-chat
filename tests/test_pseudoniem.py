"""Een pseudoniem voor wat de database in gaat (#1112, #1117): een HMAC met een servergeheim, geen kale SHA-256."""

import hashlib
import hmac

from core.pseudoniem import VERSIE, pseudoniem


def test_het_pseudoniem_is_niet_de_kale_sha256_van_de_waarde(monkeypatch):
    monkeypatch.setenv("CHAT_SECRET", "geheim")
    waarde = "jan.jansen@example.nl"
    p = pseudoniem("tokengebruik", waarde)
    assert p.startswith(VERSIE)
    assert hashlib.sha256(waarde.encode()).hexdigest() not in p


def test_zelfde_waarde_en_geheim_geven_hetzelfde_pseudoniem(monkeypatch):
    monkeypatch.setenv("CHAT_SECRET", "geheim")
    assert pseudoniem("tokengebruik", "anna") == pseudoniem("tokengebruik", "anna")
    assert pseudoniem("tokengebruik", "anna") != pseudoniem("tokengebruik", "bob")


def test_een_ander_geheim_geeft_een_ander_pseudoniem(monkeypatch):
    monkeypatch.setenv("CHAT_SECRET", "geheim-1")
    een = pseudoniem("tokengebruik", "anna")
    monkeypatch.setenv("CHAT_SECRET", "geheim-2")
    assert pseudoniem("tokengebruik", "anna") != een


def test_een_ander_domein_geeft_een_ander_pseudoniem(monkeypatch):
    """Dezelfde accountnaam is zo in twee tabellen niet aan elkaar te koppelen."""
    monkeypatch.setenv("CHAT_SECRET", "geheim")
    assert pseudoniem("tokengebruik", "anna") != pseudoniem("ratelimit", "anna")


def test_het_pseudoniem_gebruikt_niet_de_sleutel_die_een_sessietoken_tekent(monkeypatch):
    """De sleutel is uit `CHAT_SECRET` afgeleid: een token en een pseudoniem delen geen HMAC-sleutel."""
    monkeypatch.setenv("CHAT_SECRET", "geheim")
    ruw = hmac.new(b"geheim", b"tokengebruik\0anna", hashlib.sha256).hexdigest()
    assert pseudoniem("tokengebruik", "anna") != VERSIE + ruw


# ─── buiten lokaal zonder geheim: een waarschuwing (#1112) ───────────────────────────────────────────────────────────


def _valideer(monkeypatch, caplog, *, omgeving: str, geheim: str | None) -> list[str]:
    import logging

    from config import Config
    from core import auth

    monkeypatch.setattr(Config, "APP_ENV", omgeving)
    monkeypatch.setattr(Config, "ALLOW_ANONYMOUS", True)
    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    if geheim is None:
        monkeypatch.delenv("CHAT_SECRET", raising=False)
    else:
        monkeypatch.setenv("CHAT_SECRET", geheim)
    with caplog.at_level(logging.WARNING, logger="config"):
        Config.validate()
    return [r.getMessage() for r in caplog.records if "CHAT_SECRET" in r.getMessage()]


def test_buiten_lokaal_zonder_geheim_waarschuwt_de_start(monkeypatch, caplog):
    berichten = _valideer(monkeypatch, caplog, omgeving="playground", geheim=None)
    assert len(berichten) == 1 and "playground" in berichten[0]


def test_met_geheim_of_lokaal_geen_waarschuwing(monkeypatch, caplog):
    assert not _valideer(monkeypatch, caplog, omgeving="playground", geheim="geheim")
    assert not _valideer(monkeypatch, caplog, omgeving="local", geheim=None)
