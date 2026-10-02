"""Wat de gebruiker van een controle ziet, is een melding, geen instructie aan het model (#215).

Live-audit 9: onder een definitieve antwoordkaart stond "Let op: p01hoinges telt
personen ..., maar de tekst spreekt van inschrijvingen. Noem de teleenheid zoals de
bron hem telt." De eerste zin is voor de gebruiker, de tweede voor het model.
Audit 10 en 11: na een correctieronde opende het antwoord zelf met "ik schreef ...",
"De correctie is terecht" of "Volledig antwoord op basis van opgehaalde data:".
"""
import json
import re

import pandas as pd
import pytest

from agent.keuze import genegeerde_keuze
from agent.labels import onbekende_datasets, ongebruikte_bronnen, verkeerde_teleenheid
from agent.metatekst import metatekst
from agent.probleem import Probleem, meldingen
from agent.selectie import ontbrekende_instellingen, ontbrekende_schooljaren
from tools import store
from tools.query import query_data
from tools.schemas import TOOL_SCHEMAS
from tools.store import KeyMeta

_INSTRUCTIE = re.compile(r"(?:^|[.;]\s+)(?:Noem|Neem|Gebruik|Lees|Selecteer|Filter|Zoek|Geef)\b")
_TOOLS = [t["function"]["name"] for t in TOOL_SCHEMAS]


def _zonder_modeltaal(melding: str) -> bool:
    return not _INSTRUCTIE.search(melding) and not any(tool in melding for tool in _TOOLS)


@pytest.fixture(autouse=True)
def _data():
    store.clear()
    df = pd.DataFrame({
        "STUDIEJAAR": [2024, 2025, 2024, 2025],
        "INSTELLINGSCODE_ACTUEEL": ["25DW", "25DW", "30TX", "30TX"],
        "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht", "Hogeschool Utrecht", "Aeres Hogeschool", "Aeres Hogeschool"],
        "AANTAL": [7418, 7408, 880, 900],
    })
    store.put("duo:p01hoinges:3", df, KeyMeta(
        bron="duo", dataset="p01hoinges", resource=3, periodekolom="STUDIEJAAR", schooljaren=(2024, 2025),
        instellingskolom="INSTELLINGSCODE_ACTUEEL", instellingen=("25DW", "30TX"),
        teldefinitie="Ingeschrevenen: de hoofdinschrijvingen als personen.",
    ))
    yield
    store.clear()


def test_een_probleem_is_als_tekst_de_volledige_correctie_en_heeft_een_losse_melding():
    p = Probleem("p01hoinges telt personen.", "Noem de teleenheid.")
    assert p == "p01hoinges telt personen. Noem de teleenheid."
    assert p.melding == "p01hoinges telt personen."


def test_meldingen_neemt_een_kale_tekst_over_en_dubbelt_niet():
    assert meldingen([Probleem("A.", "Doe B."), "C.", Probleem("A.", "Doe D.")]) == ["A.", "C."]


def _beurt_problemen() -> list[str]:
    sel_2024 = query_data("duo:p01hoinges:3", filters={"STUDIEJAAR": 2024, "INSTELLINGSCODE_ACTUEEL": "30TX"})
    beurt = [sel_2024]
    return [
        *ontbrekende_schooljaren("Hoeveel studenten in 2025/26?", beurt),
        *ontbrekende_instellingen("Hoeveel studenten had Hogeschool Utrecht?", beurt),
        *verkeerde_teleenheid("Het waren 900 inschrijvingen.", beurt),
        *onbekende_datasets("Bron: p01hoenges."),
        *ongebruikte_bronnen("**Bronnen**\n- p03hoinschr", beurt),
        *genegeerde_keuze(["2023"], "In 2018 waren het er 900."),
        *metatekst("Ik schreef eerder 3.400; compute_kpi bevestigt 900."),
    ]


def test_elke_controle_heeft_een_melding_zonder_modelinstructie():
    problemen = _beurt_problemen()
    assert len(problemen) >= 7
    for p in problemen:
        assert isinstance(p, Probleem), p
        assert _zonder_modeltaal(p.melding), p.melding


def test_de_volledige_tekst_houdt_de_instructie_voor_de_herkansing():
    [teleenheid] = verkeerde_teleenheid("Het waren 900 inschrijvingen.", [json.dumps({"data_key": "duo:p01hoinges:3"})])
    assert "Noem de teleenheid" in teleenheid
    assert "Noem" not in teleenheid.melding


@pytest.mark.parametrize("tekst", [
    "Ik schreef eerder 'ruim 3.400', maar het zijn er 3.380.",
    "De correctie is terecht: het zijn er 900.",
    "Volledig antwoord op basis van opgehaalde data: 900 studenten.",
    "Het verschil is bevestigd door compute_kpi.",
    "Met query_data heb ik gefilterd op 2025.",
])
def test_metatekst_over_de_controle_of_de_tools_wordt_gemeld(tekst):
    assert metatekst(tekst)


@pytest.mark.parametrize("tekst", [
    "Hogeschool Utrecht had in 2025/26 7.408 deeltijdstudenten.",
    "Na correctie voor inflatie stijgt het budget.",
    "**Bronnen**\n- DUO p01hoinges",
])
def test_gewone_antwoordtekst_is_geen_metatekst(tekst):
    assert metatekst(tekst) == []
