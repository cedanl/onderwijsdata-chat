import base64
import importlib
import time

import pytest

from core.auth import check_credentials, parse_users
from routes.auth import (
    _extract_domain_from_email,
    _extract_institution_from_affiliation,
    _extract_org_from_entitlement,
)


def test_extract_domain_from_email():
    assert _extract_domain_from_email("j.vermeer@hu.nl") == "hu.nl"
    assert _extract_domain_from_email("i.am@HVA.NL") == "hva.nl"


def test_extract_domain_from_email_invalid():
    assert _extract_domain_from_email(None) is None
    assert _extract_domain_from_email("geen-email") is None
    assert _extract_domain_from_email("") is None


def test_extract_org_from_entitlement():
    eduperson = "urn:mace:surf.nl:sram:group:example_org:delftlandscapes:admins"
    assert _extract_org_from_entitlement(eduperson) == "example_org"


def test_extract_org_from_entitlement_list():
    eduperson = ["urn:mace:surf.nl:sram:label:example_org:x:l", "urn:mace:surf.nl:sram:group:other_org:co:g"]
    assert _extract_org_from_entitlement(eduperson) == "other_org"


def test_extract_org_from_entitlement_none():
    assert _extract_org_from_entitlement(None) is None
    assert _extract_org_from_entitlement([]) is None


def test_extract_institution_from_affiliation():
    assert _extract_institution_from_affiliation("employee@surf.nl") == "surf.nl"


def test_extract_institution_from_affiliation_list():
    assert _extract_institution_from_affiliation(["member@example.org", "employee@surf.nl"]) == "example.org"


def test_extract_institution_from_affiliation_none():
    assert _extract_institution_from_affiliation(None) is None
    assert _extract_institution_from_affiliation("geen-domein") is None


def test_parse_users_empty_string():
    assert parse_users("") == {}


def test_parse_users_whitespace_only():
    assert parse_users("   ") == {}


def test_parse_users_single_entry():
    assert parse_users("admin:geheim") == {"admin": "geheim"}


def test_parse_users_multiple_entries():
    assert parse_users("alice:ww1,bob:ww2") == {"alice": "ww1", "bob": "ww2"}


def test_parse_users_trims_whitespace():
    assert parse_users(" alice : ww1 , bob : ww2 ") == {"alice": "ww1", "bob": "ww2"}


def test_parse_users_colon_in_password():
    assert parse_users("admin:pass:word") == {"admin": "pass:word"}


def test_check_credentials_valid():
    assert check_credentials("admin", "geheim", {"admin": "geheim"}) is True


def test_check_credentials_wrong_password():
    assert check_credentials("admin", "fout", {"admin": "geheim"}) is False


def test_check_credentials_unknown_user():
    assert check_credentials("onbekend", "geheim", {"admin": "geheim"}) is False


def test_check_credentials_empty_users():
    assert check_credentials("admin", "geheim", {}) is False


# ── Tokenformaat en sessieduur (#479) ────────────────────────────────────────


@pytest.fixture
def auth_module(monkeypatch, tmp_path):
    """core.auth, herlaadbaar met andere env; na de test weer zoals hij was."""
    from core import auth

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
    yield auth
    monkeypatch.undo()
    importlib.reload(auth)


def _payload(token: str) -> str:
    return base64.urlsafe_b64decode(token.rsplit(".", 1)[0] + "==").decode()


def _signed(auth, payload_text: str) -> str:
    payload = base64.urlsafe_b64encode(payload_text.encode()).decode().rstrip("=")
    return f"{payload}.{auth._token_sign(payload)}"


def test_ttl_standaard_acht_uur(auth_module, monkeypatch):
    monkeypatch.delenv("SESSION_TTL_HOURS", raising=False)
    monkeypatch.delenv("SESSION_MAX_HOURS", raising=False)
    auth = importlib.reload(auth_module)

    assert (auth.SESSION_TTL, auth.SESSION_MAX) == (8 * 3600, 24 * 3600)
    voor = int(time.time())
    user, start, exp = _payload(auth.make_token("alice")).split("|")
    assert user == "alice"
    assert voor <= int(start) <= int(time.time())
    assert int(exp) == int(start) + 8 * 3600


def test_ttl_uit_de_env(auth_module, monkeypatch):
    monkeypatch.setenv("SESSION_TTL_HOURS", "2")
    monkeypatch.setenv("SESSION_MAX_HOURS", "12")
    auth = importlib.reload(auth_module)

    assert (auth.SESSION_TTL, auth.SESSION_MAX) == (2 * 3600, 12 * 3600)
    _, start, exp = _payload(auth.make_token("alice")).split("|")
    assert int(exp) == int(start) + 2 * 3600


def test_ttl_mag_een_decimaal_getal_zijn(auth_module, monkeypatch):
    monkeypatch.setenv("SESSION_TTL_HOURS", "0.5")
    auth = importlib.reload(auth_module)

    assert auth.SESSION_TTL == 1800


@pytest.mark.parametrize("naam", ["SESSION_TTL_HOURS", "SESSION_MAX_HOURS"])
@pytest.mark.parametrize("waarde", ["0", "-1", "acht", "nan", "inf", "0.0001"])
def test_ongeldige_sessieduur_laat_de_import_falen(auth_module, monkeypatch, naam, waarde):
    monkeypatch.setenv(naam, waarde)

    with pytest.raises(ValueError, match=f"{naam} moet een positief aantal uren zijn"):
        importlib.reload(auth_module)


def test_exp_is_het_laatste_veld(auth_module):
    """frontend/src/auth.js (tokenExpiresAt) leest de vervaltijd na de laatste '|'."""
    token = auth_module.make_token("a|b")
    assert _payload(token).rsplit("|", 1)[1] == str(int(time.time()) + auth_module.SESSION_TTL)
    assert auth_module.verify_token(token) == "a|b"


def test_make_token_met_start_komt_niet_voorbij_het_maximum(auth_module):
    nu = int(time.time())
    token = auth_module.make_token("alice", start=nu - auth_module.SESSION_MAX + 60)

    assert _payload(token) == f"alice|{nu - auth_module.SESSION_MAX + 60}|{nu + 60}"
    assert auth_module.session_start(token) == nu - auth_module.SESSION_MAX + 60


def test_oud_formaat_blijft_geldig(auth_module):
    exp = int(time.time()) + 3600
    oud = _signed(auth_module, f"alice|{exp}")

    assert auth_module.verify_token(oud) == "alice"
    assert auth_module.session_start(oud) == exp - 24 * 3600


def test_oud_formaat_met_pipe_in_de_gebruikersnaam(auth_module):
    exp = int(time.time()) + 3600
    oud = _signed(auth_module, f"a|b|{exp}")

    assert auth_module.verify_token(oud) == "a|b"


def test_verlopen_token_is_ongeldig(auth_module):
    nu = int(time.time())
    assert auth_module.verify_token(_signed(auth_module, f"alice|{nu - 10}")) is None
    assert auth_module.verify_token(_signed(auth_module, f"alice|{nu - 100}|{nu - 10}")) is None
    assert auth_module.session_start(_signed(auth_module, f"alice|{nu - 100}|{nu - 10}")) is None


@pytest.mark.parametrize(
    "maak",
    [
        lambda auth, t: t.rsplit(".", 1)[0] + "." + "0" * 64,
        lambda auth, t: _signed(auth, "alice|nooit"),
        lambda auth, t: _signed(auth, "alice"),
        lambda auth, t: "zonder-punt",
        lambda auth, t: "",
        lambda auth, t: t.rsplit(".", 1)[0] + ".é",
        lambda auth, t: base64.urlsafe_b64encode(b"bob|1|99999999999").decode() + "." + t.rsplit(".", 1)[1],
    ],
)
def test_gemanipuleerd_token_is_ongeldig(auth_module, maak):
    token = maak(auth_module, auth_module.make_token("alice"))

    assert auth_module.verify_token(token) is None
    assert auth_module.session_start(token) is None
