"""Een rapport onder een bronstoring eindigt zichtbaar en snel (#1050).

Een rapport roept zelf geen bron aan (de rapporttools rekenen op de store). De enige bronaanroepen zitten in
`herstel_data` vóór het rapport: keys van een heropend gesprek die de store kwijt is, komen uit hun recept terug.
Vóór #1050 liep `herstel_data_keys` die keys één voor één af, elk met de herhalingen van #867 (drie pogingen, 0,5-1 s
en 1-2 s wachten) en de timeouts van de bron per poging (DUO: 30 s voor CKAN, 120 s voor een CSV). Met een paar
DUO-keys onder een storing telden die wachttijden op tot minuten zonder enig event, en pas daarna kwam de
`report_error`. Nu stopt het herladen bij de eerste bronfout: de bron gaat één keer (met haar herhalingen) uit, en de
gebruiker leest meteen welke bron het tegenhield.

De bron is een nepserver die altijd 503 geeft; de echte `httpx.get` van het bronpakket loopt ertegen. De wachttijd van
de herhalingen wordt geteld, niet geslapen.
"""

import asyncio
import importlib
import math
import re
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import onderwijsbronnen.duo
import pytest

from agent import recepten
from agent.session_data import herstel_data_keys
from core.config import GENEREER_TIMEOUT_S
from routes import chat
from tests.nepserver import Antwoord, nepserver
from tools import bronretry, store
from tools.schemas import TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

loop_module = importlib.import_module("agent.loop")

_DATASETS = ("p01hoinges", "p02ho1ejrs", "p04hogdipl")
_KEYS = [f"duo:{dataset}:0" for dataset in _DATASETS]
_CBS_KEY = "cbs:85423NED"
_GEBRUIKER = "alice"


class _Klok:
    """Telt de wachttijd van de herhalingen in plaats van te slapen."""

    def __init__(self):
        self.nu = 0.0
        self.geslapen: list[float] = []

    def __call__(self) -> float:
        return self.nu

    def slaap(self, s: float) -> None:
        self.geslapen.append(s)
        self.nu += s


@pytest.fixture
def klok(monkeypatch):
    klok = _Klok()
    monkeypatch.setattr(bronretry, "STANDAARD", bronretry.Beleid(slaap=klok.slaap, klok=klok, toeval=lambda: 0.5))
    return klok


@pytest.fixture
def duo_storing(monkeypatch):
    """DUO antwoordt op alles met 503; `verzoeken` telt wat er binnenkwam."""
    with nepserver(lambda _pad: Antwoord(503, b"Service Unavailable")) as bron:
        monkeypatch.setattr(onderwijsbronnen.duo, "CKAN_BASE", bron.url)
        yield bron


@pytest.fixture(autouse=True)
def _heropend_na_herstart():
    """Na een herstart: de store is leeg, de recepten van alice zijn er nog."""
    store.clear()
    recepten.wis()
    for key, dataset in zip(_KEYS, _DATASETS, strict=True):
        recepten.onthoud(_GEBRUIKER, key, {"laad": [TOOL_GET_DUO_DATA, {"dataset_id": dataset, "resource": 0}]})
    recepten.onthoud(_GEBRUIKER, _CBS_KEY, {"laad": [TOOL_GET_CBS_DATA, {"dataset_id": "85423NED"}]})
    yield
    store.clear()
    recepten.wis()


def _sessie(*keys: str) -> dict:
    return {"username": _GEBRUIKER, "data_keys": list(keys), "messages": [{"role": "user", "content": "Hoeveel?"}]}


def _geen_model(monkeypatch):
    """Het rapport komt niet aan het model toe: een aanroep laat de test falen in plaats van te wachten."""

    async def nooit(*args, **kwargs):
        raise AssertionError("het model werd aangeroepen")

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", nooit)


def _rapport(session: dict) -> tuple[list[dict], float]:
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    start = time.monotonic()
    asyncio.run(chat._generate_report(session, emit, model="openai/gpt-4o"))
    return events, time.monotonic() - start


@pytest.mark.parametrize("keys", [_KEYS[:1], _KEYS], ids=["een DUO-key", "drie DUO-keys"])
def test_het_rapport_eindigt_snel_met_een_foutmelding_die_duo_noemt(monkeypatch, duo_storing, klok, keys):
    _geen_model(monkeypatch)

    events, duur = _rapport(_sessie(*keys))

    soorten = [e["type"] for e in events]
    assert soorten == ["report_generating", "report_error"], soorten
    assert "report_ready" not in soorten
    melding = events[-1]["message"]
    assert "DUO" in melding
    assert duur < 5, f"{duur:.1f} s"
    # Alleen de herhalingen van de eerste key: 0,75 s en 1,5 s. Vóór #1050 kwam dat er per key bij.
    assert klok.geslapen == [0.75, 1.5]


def test_de_bron_gaat_alleen_voor_de_eerste_key_uit(duo_storing, klok):
    herstel = herstel_data_keys(_sessie(*_KEYS), _GEBRUIKER)

    # Drie pogingen (#867), alle drie voor de eerste dataset; vóór #1050 negen, drie per key.
    assert duo_storing.verzoeken == ["/package_show?id=p01hoinges"] * 3
    assert list(herstel.onherstelbaar) == [_KEYS[0]]
    assert all(store.get(key) is None for key in _KEYS)


def test_na_een_bronfout_wordt_ook_een_key_van_een_andere_bron_niet_meer_opgehaald(duo_storing, klok):
    """Het rapport stopt toch op de eerste bronfout: een andere bron erna aanroepen voegt alleen wachttijd toe."""
    cbs = MagicMock(return_value=[])
    with patch("tools.cbs.data", cbs):
        herstel = herstel_data_keys(_sessie(_KEYS[0], _CBS_KEY), _GEBRUIKER)

    cbs.assert_not_called()
    assert list(herstel.onherstelbaar) == [_KEYS[0]]


def test_de_reden_is_leesbaar_nederlands_zonder_url_of_fouttekst(monkeypatch, duo_storing, klok):
    _geen_model(monkeypatch)

    events, _ = _rapport(_sessie(*_KEYS))

    melding = events[-1]["message"]
    assert melding.startswith("De data van dit gesprek is niet meer beschikbaar.")
    assert "DUO gaf de data voor key duo:p01hoinges:0 niet opnieuw: DUO gaf een serverfout (HTTP 503)." in melding
    assert "Stel je vraag opnieuw" in melding
    for technisch in ("http://", "https://", "127.0.0.1", duo_storing.url, "Traceback", "HTTPStatusError", "Error"):
        assert technisch not in melding
    # Alleen de eerste key: de andere zijn niet geprobeerd en staan er niet in.
    assert _KEYS[1] not in melding and _KEYS[2] not in melding


def _report_timeout_ms() -> int:
    """REPORT_TIMEOUT_MS uit de frontend: een product van gehele getallen, zoals `10 * 60 * 1000`."""
    bron = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "hooks" / "useChat.js").read_text("utf-8")
    gevonden = re.search(r"^export const REPORT_TIMEOUT_MS = ([\d\s*]+)$", bron, re.MULTILINE)
    assert gevonden, "REPORT_TIMEOUT_MS staat niet meer als product van getallen in useChat.js"
    return math.prod(int(factor) for factor in gevonden.group(1).split("*"))


def test_de_servergrens_van_een_rapport_ligt_onder_die_van_de_browser():
    """De server sluit een rapport af met een eigen report_error vóór de browser het na REPORT_TIMEOUT_MS opgeeft
    (#759, #1050): anders leest de gebruiker de afbreekmelding van de browser in plaats van de reden."""
    assert _report_timeout_ms() > GENEREER_TIMEOUT_S * 1000
