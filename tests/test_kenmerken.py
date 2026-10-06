"""Staat een niet-numeriek kenmerk bij de instelling van zijn eigen rij? (#238)

Live (Opus, RIO Windesheim): "vrijheid van onderwijs BIJZONDER" werd aan Windesheim
(01VU) toegeschreven. Die waarde hoort bij basisschool 07KT in dezelfde uitvoer; bij
01VU is het veld leeg.
"""

import json

import pandas as pd
import pytest

from agent.kenmerken import verkeerde_kenmerken
from tools import store
from tools.store import KeyMeta

_KEY = "rio:erkenningen:volledigeNaam=Windesheim"


@pytest.fixture(autouse=True)
def _rio():
    store.clear()
    df = pd.DataFrame(
        {
            "code": ["01VU", "07KT"],
            "volledigeNaam": ["Christelijke Hogeschool Windesheim", "Basisschool De Wingerd"],
            "vrijheidVanOnderwijs": [None, "BIJZONDER"],
            "soort": ["HBOS", "BAS"],
            "wet": ["WHW", "WPO"],
            "bekostigingscode": ["BEKOSTIGD", "NIET_BEKOSTIGD"],
            "begindatum": ["1986-08-01", "1990-08-01"],
        }
    )
    store.put(_KEY, df, KeyMeta(bron="rio", dataset="erkenningen"))
    yield
    store.clear()


def _beurt() -> list[str]:
    return [json.dumps({"data_key": _KEY})]


def test_kenmerk_van_een_andere_instelling():
    tekst = "Windesheim (01VU) heeft vrijheid van onderwijs BIJZONDER (protestants-christelijk)."
    [probleem] = verkeerde_kenmerken(tekst, _beurt())
    assert "BIJZONDER" in probleem and "07KT" in probleem and "01VU" in probleem


def test_juiste_combinatie_is_goed():
    tekst = "Christelijke Hogeschool Windesheim valt onder de WHW, soort HBOS, en is BEKOSTIGD."
    assert verkeerde_kenmerken(tekst, _beurt()) == []


def test_langere_waarde_gaat_voor():
    assert verkeerde_kenmerken("01VU is NIET_BEKOSTIGD.", _beurt()) != []
    assert verkeerde_kenmerken("07KT is NIET BEKOSTIGD.", _beurt()) == []


def test_gewoon_woord_en_zin_zonder_instelling_geven_niets():
    assert verkeerde_kenmerken("Windesheim (01VU) is een bijzonder grote hogeschool.", _beurt()) == []
    assert verkeerde_kenmerken("Er zijn ook scholen met vrijheid van onderwijs BIJZONDER.", _beurt()) == []


def test_alleen_rio():
    store.put("duo:x", pd.DataFrame({"code": ["01VU"], "soort": ["BAS"]}), KeyMeta(bron="duo", dataset="x"))
    assert verkeerde_kenmerken("01VU is BAS.", [json.dumps({"data_key": "duo:x"})]) == []


def test_chatpad_roept_de_controle_aan():
    """De naad: de check die run() aan de toolloop geeft, moet het kenmerk weigeren."""
    import asyncio
    import importlib
    from types import SimpleNamespace
    from unittest.mock import patch

    run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie
    meegegeven = {}

    async def nep_loop(history, **kwargs):
        meegegeven.update(kwargs)
        return SimpleNamespace(aborted="tools")

    async def emit(_event):
        pass

    vraag = [{"role": "user", "content": "Wat voor instelling is Windesheim?"}]
    with patch.object(run_module, "tool_loop", nep_loop):
        asyncio.run(run_module.run(vraag, session={}, emit=emit))
    problemen = meegegeven["check"]("Windesheim (01VU) is BIJZONDER.", _beurt())
    assert any("BIJZONDER" in str(p) and "07KT" in str(p) for p in problemen)


def test_rapportpad_roept_de_controle_aan():
    from agent.report import ReportSpec
    from agent.report_checks import report_problems

    spec = ReportSpec(
        title="Windesheim",
        onderzoeksvraag="Wat voor instelling is Windesheim?",
        beantwoordt=["Kenmerken van Windesheim"],
        conclusie="Windesheim (01VU) is BIJZONDER.",
    )
    assert any("07KT" in str(p) for p in report_problems(spec, [], _beurt()))


def test_kenmerk_van_een_vestiging_hoort_bij_de_instelling():
    df = pd.DataFrame({"code": ["01VU", "01VU00", "07KT"], "soort": ["HBOS", "VST", "BAS"]})
    store.put("rio:v", df, KeyMeta(bron="rio", dataset="erkenningen"))
    beurt = [json.dumps({"data_key": "rio:v"})]
    assert verkeerde_kenmerken("Windesheim (01VU) heeft een vestiging (VST) in Zwolle.", beurt) == []
    assert verkeerde_kenmerken("07KT heeft een vestiging (VST).", beurt) != []
