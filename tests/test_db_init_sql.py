"""scripts/db-init.sql maakt alleen gebruiker en database; de tabellen maakt init_db (#825)."""

import re
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent / "scripts" / "db-init.sql").read_text()


def test_het_script_maakt_geen_tabellen():
    # Een derde kopie van het schema liep achter op persistence/db.py (geen laatst_gebruikt, geen feedback).
    assert not re.search(r"CREATE\s+(TABLE|INDEX)", SCRIPT, re.IGNORECASE)


def test_het_wachtwoord_komt_als_psql_variabele():
    assert "change_me" not in SCRIPT
    assert not re.search(r"PASSWORD\s+'", SCRIPT, re.IGNORECASE)
    assert ":'wachtwoord'" in SCRIPT
