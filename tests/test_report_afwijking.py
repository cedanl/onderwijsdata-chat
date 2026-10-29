"""Een afwijking van de vraag staat vooraan in het rapport, uit code, waar ze meetbaar is (#734).

"Het veranderen van de onderzoeksvraag had veel prominenter in beeld en als eerste genoemd moeten zijn." Een
gebruiker vroeg om een prognose en kreeg een extrapolatie; een ander vroeg om tien jaar en de bron had er vijf.
"""

import asyncio
import json
from datetime import date

import pandas as pd
import pytest

from agent import report
from agent.loop import LoopResult
from agent.report_afwijking import afwijkingen, getekende_jaren
from tools import store
from tools.store import KeyMeta

_VANDAAG = date(2026, 10, 29)


def _grafiek(*jaren) -> dict:
    return {"titel": "t", "figure_json": json.dumps({"data": [{"x": list(jaren), "y": [1] * len(jaren)}]})}


_VIJF_JAAR = _grafiek("2021/22", "2022/23", "2023/24", "2024/25", "2025/26")


@pytest.mark.parametrize(
    ("vraag", "regel"),
    [
        (
            "Geef me een trend over de afgelopen 10 jaar.",
            "Gevraagd was de afgelopen 10 jaar; de grafieken tonen 2021/22 t/m 2025/26 (5 jaar), meer staat niet in de bron.",
        ),
        ("Hoe ontwikkelt de instroom zich de laatste tien jaar?", "Gevraagd was de afgelopen 10 jaar;"),
        ("Hoeveel studenten vanaf 2016?", "Gevraagd was vanaf 2016; de grafieken tonen 2021/22 t/m 2025/26."),
        ("De instroom sinds 2018/19?", "Gevraagd was vanaf 2018;"),
        ("Van 2016 tot 2025 graag.", "Gevraagd was 2016 tot en met 2025; de grafieken tonen 2021/22 t/m 2025/26."),
    ],
)
def test_een_gevraagde_periode_die_de_grafieken_niet_dekken_staat_vooraan(vraag, regel):
    regels = afwijkingen([vraag], [_VIJF_JAAR], [], _VANDAAG)
    assert len(regels) == 1 and regels[0].startswith(regel), regels


@pytest.mark.parametrize(
    "vraag",
    [
        "Geef me een trend over de afgelopen 5 jaar.",
        "Hoeveel studenten vanaf 2021?",
        "Van 2022 tot 2024 graag.",
        "Hoeveel studenten had de HU?",
    ],
)
def test_wat_de_grafieken_dekken_of_zonder_periode_geen_regel(vraag):
    assert afwijkingen([vraag], [_VIJF_JAAR], [], _VANDAAG) == []


def test_zonder_tijdas_geen_periodregel():
    staven = _grafiek("Universiteit Utrecht", "Universiteit Leiden")
    assert afwijkingen(["De afgelopen 10 jaar"], [staven], [], _VANDAAG) == []


def test_de_eerste_vraag_met_een_periode_gaat_voor():
    """Een bijsturing gaat voor (#733): de vragen komen van laatst naar eerst."""
    vragen = ["Alleen het wo, de afgelopen 3 jaar.", "Geef een trend over de afgelopen 10 jaar."]
    assert afwijkingen(vragen, [_VIJF_JAAR], [], _VANDAAG) == []


@pytest.mark.parametrize(
    "vraag",
    ["Maak een prognose van het aantal studenten.", "Hoeveel studenten verwacht je in 2030?", "Voorspel de instroom."],
)
def test_een_prognosevraag_zonder_prognosebron_staat_vooraan(vraag):
    store.put("duo:p01hoinges:3:a", pd.DataFrame({"AANTAL": [1]}), KeyMeta("duo", "p01hoinges", resource=3))
    regels = afwijkingen([vraag], [_VIJF_JAAR], ["duo:p01hoinges:3:a"], _VANDAAG)
    assert regels[-1] == "Gevraagd was een prognose; dit rapport toont het verloop tot nu toe, geen prognose."


def test_met_een_prognosebron_geen_prognoseregel():
    key = "duo:studentprognoses-mbo-per-instelling:0:a"
    store.put(key, pd.DataFrame({"AANTAL": [1]}), KeyMeta("duo", "studentprognoses-mbo-per-instelling", resource=0))
    assert afwijkingen(["Maak een prognose tot 2030."], [], [key], _VANDAAG) == []


def test_getekende_jaren_leest_schooljaren_jaartallen_en_cbs_codes():
    vis = [_grafiek("2021/22", "2022/23"), _grafiek(2023, 2024), _grafiek("2025SJ00"), {"figure_json": "kapot"}]
    assert getekende_jaren(vis) == [2021, 2022, 2023, 2024, 2025]


# --- in het rapport -------------------------------------------------------------------------------------------


_KEY = "duo:p02ho1ejrs:2:lucht"


@pytest.fixture
def sessie():
    store.put(
        _KEY,
        pd.DataFrame({"STUDIEJAAR": [2021, 2025], "AANTAL_EERSTEJAARS_INGESCHREVENEN": [174, 170]}),
        KeyMeta("duo", "p02ho1ejrs", resource=2),
    )
    return {
        "data_keys": [_KEY],
        "messages": [
            {
                "role": "user",
                "content": "Wat is de man-vrouwverhouding bij Luchtvaart? Geef een trend over de afgelopen 10 jaar.",
            },
            {"role": "assistant", "content": "Zie de grafiek."},
        ],
    }


def _rapport(sessie, monkeypatch, onderzoeksvraag=None):
    figuur = report.pio.from_json(_VIJF_JAAR["figure_json"])

    async def loop(messages, *, on_tool_result, **_):
        await on_tool_result(
            report.ToolCall("c1", "create_plot", json.dumps({"data_key": _KEY}), {"data_key": _KEY}), "{}", figuur
        )
        tekst = {"beantwoordt": ["x"], "beantwoordt_niet": ["y"], "visualisaties": [{"titel": "t"}], "conclusie": "c"}
        return LoopResult(text=json.dumps(tekst))

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    return asyncio.run(report.generate(sessie, stil, onderzoeksvraag=onderzoeksvraag))


def test_het_rapport_krijgt_de_afwijking_uit_de_vraag_van_de_gebruiker(sessie, monkeypatch):
    spec = _rapport(sessie, monkeypatch)
    assert spec.afwijkingen == [
        "Gevraagd was de afgelopen 10 jaar; de grafieken tonen 2021/22 t/m 2025/26 (5 jaar), meer staat niet in de bron."
    ]
    assert spec.to_dict()["afwijkingen"] == spec.afwijkingen


def test_een_bevestigde_vraag_zonder_periode_gaat_voor(sessie, monkeypatch):
    spec = _rapport(sessie, monkeypatch, onderzoeksvraag="Hoe verhouden mannen en vrouwen zich bij Luchtvaart?")
    assert spec.afwijkingen == []
