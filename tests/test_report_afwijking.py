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
from tests.rapportfiguren import vaste_figuren
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


def _data(key: str, *schooljaren: int) -> str:
    """Een geladen key met de schooljaren die de store van haar rijen kent; zonder jaren zijn ze onbekend."""
    meta = KeyMeta("cbs", "85421NED", schooljaren=tuple(schooljaren) if schooljaren else None)
    store.put(key, pd.DataFrame({"AANTAL": [1]}), meta)
    return key


# Een rapport zonder grafiek met een tijdas toetst de periode aan de data die het las (#1179).
_VANAF_2010 = "Hoe ontwikkelt het aantal eerstejaars in de techniek zich vanaf 2010 tot nu? Graag een lijngrafiek."


def test_zonder_grafiek_toetst_de_periode_aan_de_schooljaren_van_de_gelezen_data():
    key = _data("cbs:85421NED:a", *range(2011, 2025))

    assert afwijkingen([_VANAF_2010], [], [key], _VANDAAG) == [
        "Gevraagd was vanaf 2010; de data loopt van 2011/12 t/m 2024/25."
    ]


def test_zonder_grafiek_geen_regel_als_de_data_de_gevraagde_periode_dekt():
    key = _data("cbs:85421NED:b", *range(2010, 2025))

    assert afwijkingen([_VANAF_2010], [], [key], _VANDAAG) == []


def test_zonder_grafiek_telt_de_data_van_alle_gelezen_keys():
    eerste, tweede = _data("cbs:85421NED:c", 2011, 2012), _data("cbs:85421NED:d", 2010, 2011)

    assert afwijkingen([_VANAF_2010], [], [eerste, tweede], _VANDAAG) == []


def test_zonder_grafiek_een_aantal_jaren_dat_de_data_niet_heeft():
    key = _data("cbs:85421NED:e", 2022, 2023, 2024)

    [regel] = afwijkingen(["Geef me een trend over de afgelopen 10 jaar."], [], [key], _VANDAAG)

    assert (
        regel
        == "Gevraagd was de afgelopen 10 jaar; de data loopt van 2022/23 t/m 2024/25 (3 jaar), meer staat niet in de bron."
    )


def test_zonder_grafiek_een_bereik_dat_te_vroeg_eindigt():
    key = _data("cbs:85421NED:f", *range(2016, 2022))

    [regel] = afwijkingen(["Van 2016 tot 2025 graag."], [], [key], _VANDAAG)

    assert regel == "Gevraagd was 2016 tot en met 2025; de data loopt van 2016/17 t/m 2021/22."


def test_met_een_grafiek_blijft_de_regel_van_de_grafieken_ook_naast_data():
    key = _data("cbs:85421NED:g", *range(2011, 2025))

    [regel] = afwijkingen(["Vanaf 2010 graag."], [_VIJF_JAAR], [key], _VANDAAG)

    assert regel == "Gevraagd was vanaf 2010; de grafieken tonen 2021/22 t/m 2025/26."


def test_zonder_grafiek_en_zonder_bekende_schooljaren_geen_regel_en_geen_fout():
    onbekend = _data("cbs:85421NED:h")

    assert afwijkingen([_VANAF_2010], [], [onbekend, "cbs:bestaat-niet"], _VANDAAG) == []
    assert afwijkingen([_VANAF_2010], [], [], _VANDAAG) == []


def test_een_grafiek_zonder_tijdas_valt_terug_op_de_data():
    staven = _grafiek("Universiteit Utrecht", "Universiteit Leiden")
    key = _data("cbs:85421NED:i", *range(2011, 2025))

    [regel] = afwijkingen([_VANAF_2010], [staven], [key], _VANDAAG)

    assert "de data loopt van 2011/12" in regel


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
    # De grafiek is een gekozen figuur uit het gesprek (#993).
    vaste_figuren(monkeypatch, (_VIJF_JAAR["figure_json"], _KEY))

    async def loop(messages, **_):
        tekst = {"beantwoordt": ["x"], "beantwoordt_niet": ["y"], "visualisaties": [{"titel": "t"}], "conclusie": "c"}
        return LoopResult(text=json.dumps(tekst))

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    return asyncio.run(report.generate(sessie, stil, onderzoeksvraag=onderzoeksvraag, figuren=("f1",)))


def test_het_rapport_krijgt_de_afwijking_uit_de_vraag_van_de_gebruiker(sessie, monkeypatch):
    spec = _rapport(sessie, monkeypatch)
    assert spec.afwijkingen == [
        "Gevraagd was de afgelopen 10 jaar; de grafieken tonen 2021/22 t/m 2025/26 (5 jaar), meer staat niet in de bron."
    ]
    assert spec.to_dict()["afwijkingen"] == spec.afwijkingen


def test_een_bevestigde_vraag_zonder_periode_gaat_voor(sessie, monkeypatch):
    spec = _rapport(sessie, monkeypatch, onderzoeksvraag="Hoe verhouden mannen en vrouwen zich bij Luchtvaart?")
    assert spec.afwijkingen == []


def test_een_rapport_zonder_grafiek_meldt_dat_de_data_later_begint(sessie, monkeypatch):
    # Zonder gekozen figuur (#993) heeft het rapport geen tijdas; de data die het las, begint in 2021/22 (#1179).
    store.put(
        _KEY,
        pd.DataFrame({"STUDIEJAAR": [2021, 2025], "AANTAL_EERSTEJAARS_INGESCHREVENEN": [174, 170]}),
        KeyMeta("duo", "p02ho1ejrs", resource=2, schooljaren=(2021, 2022, 2023, 2024, 2025)),
    )

    async def loop(messages, **_):
        tekst = {"beantwoordt": ["x"], "beantwoordt_niet": ["y"], "visualisaties": [], "conclusie": "c"}
        return LoopResult(text=json.dumps(tekst))

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    spec = asyncio.run(report.generate(sessie, stil))

    assert spec.visualisaties == []
    assert spec.afwijkingen == [
        "Gevraagd was de afgelopen 10 jaar; de data loopt van 2021/22 t/m 2025/26 (5 jaar), meer staat niet in de bron."
    ]
