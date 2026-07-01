from core.auth import check_credentials, parse_users


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
