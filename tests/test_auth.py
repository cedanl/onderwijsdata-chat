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
