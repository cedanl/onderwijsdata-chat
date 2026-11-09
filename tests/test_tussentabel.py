"""Een foutieve tussentabel komt niet in het definitieve antwoord (#982, F3, ROC Midden Nederland).

F3 gaf eerst een tabel met één rij "2022/23 | 70,6%*", daarna de juiste reeks (71,2% voor 2022/23, 70,6% voor 2024/25)
en de zin "De eerste tabel hierboven is een vergissing; gebruik de tweede tabel." Beide bleven staan. 70,6% staat in de
bron, als diplomaresultaat van 2024/25 en als jaarresultaat van 2022/23: de getalcontrole vroeg alleen of het getal
ergens voorkomt.
"""

import asyncio
import importlib
import json
from decimal import Decimal

import pytest

from agent.citaties import citaties
from agent.controles import antwoordcontrole
from agent.meetwaarden import meetwaarden
from agent.stream import StreamResult
from agent.tabelbinding import verkeerde_tabeljaren
from agent.zelfcorrectie import onvervangen_tabelcorrectie, zonder_zelfcorrectie
from tools import mbo_indicatoren
from tools.schemas import TOOL_GET_MBO_INDICATOREN

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_JAREN = ("2022/23", "2023/24", "2024/25")
# ROC Midden Nederland (25LH) en alle roc's, editie 2026: dezelfde waarden als in tests/test_mbo_indicatoren.py.
_EIGEN = {
    "jaarresultaat": (0.706069880132619, 0.703268713739918, 0.70130783293489),
    "diplomaresultaat": (0.712116991643454, 0.71285140562249, 0.705518627299428),
    "nieuwe_vsv": (0.0638, 0.064, 0.0614),
}
_GROEP = {
    "jaarresultaat": (0.690877991916243, 0.708770249234506, 0.717899163108854),
    "diplomaresultaat": (0.704058436638075, 0.719388888536265, 0.72440228349962),
    "nieuwe_vsv": (0.0667601480282179, 0.0632719250278129, 0.0603722239308115),
}


@pytest.fixture
def indicatoren(monkeypatch) -> str:
    """Het resultaat van get_mbo_indicatoren voor ROC Midden Nederland, zoals de tool het teruggeeft."""
    waarden: dict[tuple[str, str], float | None] = {
        (i, j): w for i, ws in _EIGEN.items() for j, w in zip(_JAREN, ws, strict=True)
    }
    inst = mbo_indicatoren.Instelling("25LH", "ROC Midden Nederland", "ROC", waarden)
    groep: dict[tuple[str, str, str], float | None] = {
        (i, j, "ROC"): w for i, ws in _GROEP.items() for j, w in zip(_JAREN, ws, strict=True)
    }
    editie = mbo_indicatoren.Editie(
        2026, "https://duo.nl/x.xlsx", "1 oktober 2025", {"25LH": inst}, groep, dict.fromkeys(_EIGEN, _JAREN)
    )
    profiel = {"naam": "ROC Midden Nederland", "sector": "mbo", "instellingscode": "25LH"}
    monkeypatch.setattr(mbo_indicatoren.instellingen, "instellingsprofiel", lambda naam: profiel)
    monkeypatch.setattr(mbo_indicatoren, "editie", lambda: editie)
    return mbo_indicatoren.get_mbo_indicatoren("ROC Midden Nederland")


_INLEIDING = (
    "Het diplomaresultaat van ROC Midden Nederland (BRIN 25LH) was in 2024/25 70,6%. Dat is 1,8 procentpunt lager "
    "dan het gemiddelde van alle roc's (72,4%). In 2022/23 lag de instelling nog 0,8 procentpunt boven dat gemiddelde."
)
_KOP = "| Schooljaar | ROC Midden Nederland | Alle roc's | Verschil (procentpunt) |\n|---|---|---|---|"
_FOUTE_TABEL = f"{_KOP}\n| 2022/23 | 70,6%* | - | - |"
_JUISTE_TABEL = "\n".join(
    [
        _KOP,
        "| 2022/23 | 71,2% | 70,4% | 0,8 |",
        "| 2023/24 | 71,3% | 71,9% | -0,6 |",
        "| 2024/25 | 70,6% | 72,4% | -1,8 |",
    ]
)
_CORRECTIE = "De eerste tabel hierboven is een vergissing; gebruik de tweede tabel."
# Het antwoord van F3, zoals de her-audit van 06-11 het zag (testprompts/resultaten, R16).
F3 = f"{_INLEIDING}\n\n{_FOUTE_TABEL}\n\nHieronder de volledige reeks:\n\n{_JUISTE_TABEL}\n\n{_CORRECTIE}"
SCHOON = f"{_INLEIDING}\n\nHieronder de volledige reeks:\n\n{_JUISTE_TABEL}"


# --- de tussentabel gaat naar de redeneerkaart ----------------------------------------------------------------------


def test_de_herziene_tabel_en_de_correctiezin_gaan_uit_het_antwoord():
    schoon, weg = zonder_zelfcorrectie(F3)

    assert schoon == SCHOON
    assert weg == [_FOUTE_TABEL, _CORRECTIE]


@pytest.mark.parametrize(
    "correctie",
    [
        "De tabel hierboven klopt niet; hieronder de juiste.",
        "Negeer de eerste tabel.",
        "Mijn eerste tabel was onjuist.",
        "Gebruik de tweede tabel.",
    ],
)
def test_ook_andere_woorden_voor_een_herziene_tabel(correctie):
    schoon, weg = zonder_zelfcorrectie(f"{_FOUTE_TABEL}\n\n{correctie}\n\n{_JUISTE_TABEL}")

    assert schoon == _JUISTE_TABEL
    assert weg == [_FOUTE_TABEL, correctie]


def test_zonder_correctiezin_blijven_twee_tabellen_met_dezelfde_kop_staan():
    """Twee tabellen met dezelfde kolommen kunnen gewoon twee instellingen zijn: alleen de herziening haalt er een weg."""
    tekst = f"**ROC Midden Nederland**\n\n{_JUISTE_TABEL}\n\n**Alle roc's**\n\n{_JUISTE_TABEL}"

    assert zonder_zelfcorrectie(tekst) == (tekst, [])


def test_een_tabel_met_een_andere_kop_blijft_staan():
    andere = "| Schooljaar | Jaarresultaat |\n|---|---|\n| 2024/25 | 70,1% |"
    tekst = f"{andere}\n\n{_FOUTE_TABEL}\n\n{_CORRECTIE}\n\n{_JUISTE_TABEL}"

    schoon, weg = zonder_zelfcorrectie(tekst)

    assert schoon == f"{andere}\n\n{_JUISTE_TABEL}"
    assert weg == [_FOUTE_TABEL, _CORRECTIE]


@pytest.mark.parametrize(
    "tekst",
    [
        "De tweede tabel toont de vergelijkingsgroep.",
        "In de eerste tabel staat het diplomaresultaat, in de tweede het jaarresultaat.",
        "De eerste tabel van DUO is per instelling.",
    ],
)
def test_een_zin_over_een_tabel_is_geen_herziening(tekst):
    assert zonder_zelfcorrectie(tekst) == (tekst, [])


def test_een_correctie_zonder_vervangende_tabel_vraagt_een_nieuw_antwoord():
    """Is de foute tabel niet als vervangen te herkennen, dan bouwt het model het antwoord opnieuw op (herkansing)."""
    (probleem,) = onvervangen_tabelcorrectie(f"{_FOUTE_TABEL}\n\n{_CORRECTIE}")

    assert not probleem.hard
    assert "tabel" in probleem.melding and _CORRECTIE in probleem.melding
    assert onvervangen_tabelcorrectie(F3) == []
    assert onvervangen_tabelcorrectie(SCHOON) == []


# --- binding van schooljaar, maat en instelling in een tabelrij ------------------------------------------------------


def test_de_foute_tabelrij_van_f3_hoort_bij_een_ander_schooljaar(indicatoren):
    tekst = f"{_INLEIDING}\n\n{_FOUTE_TABEL}"

    (probleem,) = verkeerde_tabeljaren([tekst], [indicatoren])

    assert not probleem.hard  # een decimaal botst vaker toevallig dan een groot getal: twijfel, geen inhouden
    assert "70,6" in probleem.melding and "2022/23" in probleem.melding
    assert "Diplomaresultaat" in probleem.melding and "2024/25" in probleem.melding


def test_de_juiste_reeks_van_f3_geeft_niets(indicatoren):
    assert verkeerde_tabeljaren([SCHOON], [indicatoren]) == []
    assert verkeerde_tabeljaren([_JUISTE_TABEL], [indicatoren]) == []


def test_de_maat_in_de_kolomkop_gaat_voor_de_tekst_erboven(indicatoren):
    """70,6% is ook het jaarresultaat van 2022/23: noemt de kop die maat, dan klopt de rij."""
    tekst = f"{_INLEIDING}\n\n| Schooljaar | Jaarresultaat ROC Midden Nederland |\n|---|---|\n| 2022/23 | 70,6% |"

    assert verkeerde_tabeljaren([tekst], [indicatoren]) == []


def test_de_kolom_van_de_vergelijkingsgroep_bindt_aan_de_groep(indicatoren):
    """70,6% is in 2024/25 de waarde van de instelling, niet die van alle roc's (72,4%): het jaar alleen is niet genoeg."""
    tekst = (
        "Het diplomaresultaat per jaar:\n\n"
        "| Schooljaar | ROC Midden Nederland | Alle roc's |\n|---|---|---|\n"
        "| 2023/24 | 71,3% | 71,9% |\n| 2024/25 | 70,6% | 70,6% |"
    )

    (probleem,) = verkeerde_tabeljaren([tekst], [indicatoren])

    assert "70,6" in probleem.melding and "Alle roc's" in probleem.melding and "2024/25" in probleem.melding
    assert "Instelling: ROC Midden Nederland" in probleem.melding


def test_een_jaar_in_de_kolomkop_telt_als_het_jaar_van_de_cel(indicatoren):
    tekst = (
        "| Indicator | 2022/23 | 2024/25 |\n|---|---|---|\n"
        "| Diplomaresultaat | 71,2% | 70,6% |\n| Jaarresultaat | 70,6% | 70,1% |"
    )

    assert verkeerde_tabeljaren([tekst], [indicatoren]) == []
    verwisseld = tekst.replace("| 71,2% | 70,6% |", "| 70,6% | 71,2% |")
    assert len(verkeerde_tabeljaren([verwisseld], [indicatoren])) == 2


def test_zonder_schooljaar_of_bekende_waarde_geen_oordeel(indicatoren):
    zonder_jaar = "| Indicator | ROC Midden Nederland |\n|---|---|\n| Diplomaresultaat | 70,6% |"
    onbekend = "| Schooljaar | ROC Midden Nederland |\n|---|---|\n| 2022/23 | 12,3% |"

    assert verkeerde_tabeljaren([zonder_jaar, onbekend], [indicatoren]) == []
    assert verkeerde_tabeljaren([F3], ["geen json"]) == []


def test_de_antwoordcontrole_toetst_wat_de_gebruiker_ziet(indicatoren):
    """De herziene tabel gaat naar de redeneerkaart: de controle meldt hem niet, de losse foute tabel wel."""
    check = antwoordcontrole("Wat is het diplomaresultaat van ROC Midden Nederland?", [], [], [], [])

    assert not [p for p in check(F3, [indicatoren]) if getattr(p, "controle", None) == "verkeerde_tabeljaren"]
    gevonden = check(f"{_INLEIDING}\n\n{_FOUTE_TABEL}", [indicatoren])
    assert [getattr(p, "controle", None) for p in gevonden] == ["verkeerde_tabeljaren"]


def test_een_engelse_decimale_punt_wordt_ook_gelezen(indicatoren):
    check = antwoordcontrole("Wat is het diplomaresultaat van ROC Midden Nederland?", [], [], [], [])
    tekst = f"{_INLEIDING}\n\n{_FOUTE_TABEL.replace('70,6%', '70.6%')}"

    assert [getattr(p, "controle", None) for p in check(tekst, [indicatoren])] == ["verkeerde_tabeljaren"]


# --- meetwaarden en citaties van de mbo-indicatoren -----------------------------------------------------------------


def test_de_mbo_indicatoren_geven_meetwaarden_met_schooljaar_en_maat(indicatoren):
    waarden = meetwaarden(indicatoren, TOOL_GET_MBO_INDICATOREN)
    per_rij = {(w.maat, w.selectie): w.decimaal for w in waarden}

    assert per_rij[("Diplomaresultaat", ("Instelling: ROC Midden Nederland", "Schooljaar: 2024/25"))] == Decimal("70.6")
    assert per_rij[("Diplomaresultaat", ("Vergelijkingsgroep: roc's", "Schooljaar: 2024/25"))] == Decimal("72.4")
    verschil = ("Instelling: ROC Midden Nederland", "Schooljaar: 2024/25", "Verschil")
    assert per_rij[("Diplomaresultaat", verschil)] == Decimal("1.8")
    assert per_rij[("Nieuwe vsv'ers", ("Instelling: ROC Midden Nederland", "Schooljaar: 2024/25"))] == Decimal("6.1")
    assert {w.eenheid for w in waarden} == {"%", "procentpunt"}


def test_een_percentage_van_de_mbo_indicatoren_krijgt_een_citatie(indicatoren):
    tekst = "In 2024/25 was het diplomaresultaat van ROC Midden Nederland 70,6%."

    (citatie,) = citaties(tekst, [(TOOL_GET_MBO_INDICATOREN, indicatoren)])

    assert citatie["vastgesteld"] and citatie["maat"] == "Diplomaresultaat"
    assert "2024/25" in citatie["selectie"] and citatie["bron"].startswith("DUO")


# --- eindantwoord met een nepmodel ----------------------------------------------------------------------------------


def _chat(monkeypatch, antwoorden: list[str], resultaat: str) -> list[dict]:
    """Eén chatbeurt: het nepmodel haalt de indicatoren op en geeft daarna de antwoorden in volgorde."""
    aanroep = {"id": "m", "name": TOOL_GET_MBO_INDICATOREN, "arguments": '{"instelling": "ROC Midden Nederland"}'}
    stappen = [StreamResult(text="", tool_calls=[aanroep]), *(StreamResult(text=a, tool_calls=[]) for a in antwoorden)]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return resultaat, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = "Wat is het diplomaresultaat van ROC Midden Nederland vergeleken met vergelijkbare instellingen?"
    asyncio.run(run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return events


def test_eindantwoord_tabel_correctie_tweede_tabel(monkeypatch, indicatoren):
    """Het nepmodel geeft een tabel, corrigeert zich en geeft een tweede tabel: alleen de tweede staat in het antwoord."""
    events = _chat(monkeypatch, [F3], indicatoren)

    eind = events[-1]
    assert eind["type"] == "message_end"
    assert _JUISTE_TABEL in eind["content"]
    assert "70,6%*" not in eind["content"] and "vergissing" not in eind["content"]
    assert eind["tussentekst"] == [_FOUTE_TABEL, _CORRECTIE]
    assert "controle" not in eind
    assert not [e for e in events if e["type"] == "message_cancel"]


def test_eindantwoord_foute_tabel_zonder_correctie_krijgt_een_herkansing(monkeypatch, indicatoren):
    """Zonder eigen correctie vangt de binding de foute rij: het model schrijft het antwoord opnieuw."""
    events = _chat(monkeypatch, [f"{_INLEIDING}\n\n{_FOUTE_TABEL}", SCHOON], indicatoren)

    (ingetrokken,) = [e for e in events if e["type"] == "message_cancel"]
    assert any("70,6" in reden and "2022/23" in reden for reden in ingetrokken["reden"])
    eind = events[-1]
    assert _JUISTE_TABEL in eind["content"] and "70,6%*" not in eind["content"]
    assert "controle" not in eind


def test_eindantwoord_blijft_de_foute_tabel_dan_staat_de_melding_eronder(monkeypatch, indicatoren):
    fout = f"{_INLEIDING}\n\n{_FOUTE_TABEL}"
    events = _chat(monkeypatch, [fout, fout], indicatoren)

    eind = events[-1]
    assert any("70,6" in m and "2024/25" in m for m in eind["controle"])


def test_de_tool_noemt_haar_dataset(indicatoren):
    assert json.loads(indicatoren)["dataset"] == mbo_indicatoren.DATASET
