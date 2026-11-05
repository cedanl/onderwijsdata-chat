"""Elke verwachte dataset in tests/e2e/evaluations.json is een ID dat de chat kan laden (#909).

`score.js` zoekt het deel na de `:` als tekst in het antwoord en de tooluitvoer. Een ID dat niet in de catalogus
staat (`duo:01.-ingeschrevenen-ho`, `cbs:71037ned`) of buiten het profiel valt, kan dus nooit gevonden worden: de vraag
blijft "verwachte dataset niet gebruikt", welke bron het model ook kiest.
"""

import json
from pathlib import Path

import pytest

from tools import catalog

_EVALS = json.loads((Path(__file__).parent / "e2e" / "evaluations.json").read_text(encoding="utf-8"))["evaluations"]
_VERWACHT = [
    pytest.param(ev["label"], verwacht, id=f"{ev['label']}-{verwacht}")
    for ev in _EVALS
    for veld in ("datasets", "datasets_alt")
    for verwacht in ev["expected"].get(veld) or []
]


def test_er_zijn_verwachte_datasets():
    assert len(_VERWACHT) >= 20


@pytest.mark.parametrize(("label", "verwacht"), _VERWACHT)
def test_een_verwachte_dataset_laadt_in_de_chat(label, verwacht):
    bron, _, kaal = verwacht.partition(":")
    assert kaal, f"{label}: {verwacht} mist het voorvoegsel <bron>: (score.js leest alleen het deel erna)"
    assert catalog.scope_blokkade(verwacht) is None, f"{label}: {verwacht} laadt niet in de chat"
    assert catalog.bron_id(kaal) == kaal, f"{label}: {verwacht} heeft niet de spelling van de catalogus"
    assert catalog.leverancier(kaal) == bron.upper(), f"{label}: {verwacht} hoort bij {catalog.leverancier(kaal)}"
