"""Alledaagse po- en vo-woorden vallen buiten de scope, net als "havo" en "basisschool" (#1076).

"middelbare school eindexamen", "brugklas leerlingen", "gymnasium leerlingen" en "basisschoolleerlingen aantal" gaven
mbo- en ho-treffers zonder scope-melding: `PO_SO_VO` kende alleen de vaktermen (havo, vwo, basisschool). Met een
doorstroomwoord of het ho erbij blijft zo'n vraag open: dan is het vo-niveau context voor vervolgonderwijs (#877).
"""

import pytest

from agent import scopevraag as scopevraag_module
from agent import vervolgvragen, vo_school
from agent.po_vraag import po_vraag
from agent.vaste_antwoorden import SCOPE_UITLEG, scope_uitleg
from tests.test_scopevraag import _REGISTER
from tests.zoekuitkomst import envelop
from tools import instelling, scopeprofiel
from tools.catalog import search_catalog

# Zonder doorstroomwoord of ho-woord: buiten de scope.
BUITEN_SCOPE = [
    "middelbare school eindexamen",
    "middelbare scholieren zakken voor eindexamen",
    "brugklas leerlingen",
    "gymnasium leerlingen",
    "lyceum leerlingen",
    "basisschoolleerlingen aantal",
    "Hoeveel kleuters zijn er?",
]
# Met een doorstroomwoord of het ho: de vo-context gaat open (#877, #1039, #957).
OPEN = [
    "middelbare school naar hbo",
    "vmbo naar mbo",
    "Waar gaan middelbare scholieren heen na hun eindexamen?",
    "Waar gaan gymnasiasten heen na hun diploma?",
    "Hoeveel gymnasiumleerlingen gaan naar de universiteit?",
    "Hoeveel lyceum leerlingen stromen door naar het mbo?",
]
# Wat een tool zegt als hij de selectie weigert: de vaste uitleg achteraf kijkt daarnaar (`_TOOLWEIGERING`).
_TOOLWEIGERING = "De tool weigert deze selectie."


@pytest.fixture(autouse=True)
def register(monkeypatch):
    """Geen netwerk: het register uit de scopevraagtests."""
    for module in (scopevraag_module, vo_school, instelling):
        monkeypatch.setattr(module, "get_all", lambda: _REGISTER)


@pytest.mark.parametrize("vraag", BUITEN_SCOPE)
def test_het_woord_is_een_po_of_vo_woord(vraag):
    assert scopeprofiel.PO_SO_VO.search(vraag)


@pytest.mark.parametrize("vraag", BUITEN_SCOPE)
def test_search_catalog_geeft_out_of_scope(vraag):
    uitkomst = envelop(search_catalog(vraag))

    assert uitkomst["status"] == "out_of_scope"
    assert uitkomst["kandidaten"] == []


@pytest.mark.parametrize("vraag", BUITEN_SCOPE)
def test_de_chat_geeft_de_vaste_scope_uitleg(vraag):
    assert po_vraag(vraag) == SCOPE_UITLEG
    assert scope_uitleg(_TOOLWEIGERING, [], vraag) == SCOPE_UITLEG
    assert vervolgvragen._buiten_scope(vraag, None)


@pytest.mark.parametrize("vraag", OPEN)
def test_met_een_doorstroomwoord_blijft_de_vraag_open(vraag):
    assert envelop(search_catalog(vraag))["status"] != "out_of_scope"
    assert po_vraag(vraag) is None
    assert scope_uitleg(_TOOLWEIGERING, [], vraag) is None


def test_het_grafisch_lyceum_is_een_mbo_instelling():
    """Een mbo-instelling met "Lyceum" in de naam: geen vo-woord, dus geen scope-uitleg en geen out_of_scope."""
    vraag = "Hoeveel deelnemers heeft het Grafisch Lyceum Rotterdam?"
    assert not scopeprofiel.PO_SO_VO.search(vraag)
    assert envelop(search_catalog(vraag))["status"] != "out_of_scope"
    assert po_vraag(vraag) is None
