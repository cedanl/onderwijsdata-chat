"""De meting van de dekking van het dashboard Opleidingen (#980): registerdekking en naamdekking, elk apart.

Op de synthetische proefexport (`onderwijsbronnen.skdb.proefbestand`) en een register zonder DUO-download.
"""

import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from data import instellingen
from scripts.meet_skdb_dekking import dekking


@pytest.fixture
def export():
    return skdb.lees(*proefbestand.standaard())


@pytest.fixture(autouse=True)
def register(monkeypatch):
    """Hogeschool Utrecht onder haar eigen naam, Universiteit Leiden onder een andere: Proefuniversiteit en
    Proefhogeschool Particulier staan er niet in."""
    lijst: dict[str, dict] = {}
    instellingen._voeg_toe(lijst, "Hogeschool Utrecht", "25DW", "hbo", {})
    instellingen._voeg_toe(lijst, "Rijksuniversiteit Leiden", "21PB", "wo", {})
    monkeypatch.setattr(instellingen, "_cache", list(lijst.values()))
    monkeypatch.setattr(instellingen, "_alias_lookup", None)
    return lijst


def test_registerdekking_en_naamdekking_staan_apart(export):
    uit = dekking(export)

    assert [i["brin"] for i in uit["bereikt"]] == ["25DW"]
    assert [(i["brin"], i["naam"], i["registernaam"]) for i in uit["naam_onbekend"]] == [
        ("21PB", "Universiteit Leiden", "Rijksuniversiteit Leiden")
    ]
    assert sorted(i["brin"] for i in uit["buiten_register"]) == ["98ZZ", "99XX"]


def test_een_alias_maakt_de_naam_bereikbaar(export, register, monkeypatch):
    monkeypatch.setitem(register["Rijksuniversiteit Leiden"], "aliassen", ["Universiteit Leiden"])

    uit = dekking(export)

    assert uit["naam_onbekend"] == []
    assert sorted(i["brin"] for i in uit["bereikt"]) == ["21PB", "25DW"]
