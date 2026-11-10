"""De rapporttitel noemt de periode van de data, en is geen afgebroken opdracht (#893).

Testrapport 03-11, vraag 6: de titel was "Maak een grafiek van het aantal hbo-studenten per sector in het meest
recente…", terwijl de data schooljaar 2025/26 was. De titel blijft uit code komen (#416): de vraag, met de opdracht
eraf en het schooljaar uit de data.
"""

import json

import pytest

from agent.report import _parse_spec_from_response
from agent.report_periode import titelperiode
from agent.report_titel import rapporttitel

_VRAAG_6 = "Maak een grafiek van het aantal hbo-studenten per sector in het meest recente schooljaar"


def test_een_relatieve_periode_wordt_het_schooljaar_uit_de_data():
    titel = rapporttitel(_VRAAG_6, None, (2025, 2025))

    assert titel == "Het aantal hbo-studenten per sector in 2025/26"
    assert not titel.endswith("…")


def test_een_vraag_zonder_jaar_krijgt_de_periode_erachter():
    assert rapporttitel("Hoeveel eerstejaars zijn er per sector?", None, (2025, 2025)) == (
        "Hoeveel eerstejaars zijn er per sector (2025/26)"
    )
    assert rapporttitel("Hoe groeit de instroom?", None, (2020, 2024)) == "Hoe groeit de instroom (2020/21–2024/25)"


def test_een_relatief_schooljaar_bij_een_bereik_wordt_niet_vervangen():
    titel = rapporttitel("Instroom sinds het laatste schooljaar", None, (2020, 2024))

    assert titel == "Instroom sinds het laatste schooljaar (2020/21–2024/25)"


def test_een_vraag_met_een_jaar_houdt_haar_eigen_jaar():
    assert rapporttitel("Hoeveel eerstejaars had de HU in 2024/25?", None, (2024, 2024)) == (
        "Hoeveel eerstejaars had de HU in 2024/25"
    )
    assert rapporttitel("Instroom in 2023", None, (2023, 2024)) == "Instroom in 2023"


def test_zonder_periode_uit_de_data_blijft_de_titel_zoals_hij_was():
    assert rapporttitel("Hoeveel eerstejaars?", None) == "Hoeveel eerstejaars"
    assert rapporttitel("Hoeveel eerstejaars?", None, None) == "Hoeveel eerstejaars"


@pytest.mark.parametrize(
    "vraag",
    [
        "Geef me een overzicht van de instroom per sector",
        "Toon een staafgrafiek van de instroom per sector",
        "Maak een rapport over de instroom per sector",
    ],
)
def test_een_opdrachtzin_wordt_een_onderwerp(vraag):
    assert rapporttitel(vraag, None, (2025, 2025)) == "De instroom per sector (2025/26)"


def test_een_vraag_die_met_maak_begint_maar_geen_opdracht_is_blijft_staan():
    assert rapporttitel("Maak ik kans op een plek?", None, None) == "Maak ik kans op een plek"


def test_lange_vraag_met_periode_past_binnen_de_grens_en_houdt_de_periode():
    vraag = "Hoe ontwikkelde de instroom van eerstejaars in het hbo zich per sector en per provincie in de regio?"
    titel = rapporttitel(vraag, None, (2025, 2025))

    assert len(titel) <= 80 and titel.endswith("… (2025/26)")


def test_instelling_komt_na_de_periode():
    assert rapporttitel("Hoeveel eerstejaars?", "Hogeschool Utrecht", (2025, 2025)) == (
        "Hoeveel eerstejaars (2025/26) – Hogeschool Utrecht"
    )


def test_persoonsgegevens_houden_hun_vaste_titel():
    titel = rapporttitel("Instroom van BSN 111222333", None, (2025, 2025))

    assert "111222333" not in titel and "(2025/26)" not in titel


def test_titelperiode_is_de_data_begrensd_door_de_periode_van_de_onderzoeksvraag():
    assert titelperiode([(2015, 2025), None, (2020, 2025)], "Instroom") == (2015, 2025)
    assert titelperiode([(2015, 2025)], "Instroom van 2020/21 t/m 2022/23") == (2020, 2022)
    assert titelperiode([(2015, 2018)], "Instroom van 2020/21 t/m 2022/23") == (2015, 2018)
    assert titelperiode([None], "Instroom") is None
    assert titelperiode([], "Instroom") is None


def test_het_rapport_gebruikt_het_schooljaar_van_zijn_figuur_in_de_titel():
    context = {"topic": _VRAAG_6, "instelling": None}
    spec = _parse_spec_from_response(json.dumps({"conclusie": "c"}), [], context, periode=[(2025, 2025)])

    assert spec.title == "Het aantal hbo-studenten per sector in 2025/26"


# ── Een jaar dat de inkorting wegkapt, telt niet (#1003) ──

_VRAAG_P06 = (
    "Hoeveel hbo-studenten (ingeschreven personen, hoofdinschrijvingen) stonden er in het meest recente studiejaar, "
    "2025/2026, per sector (ONDERDEEL) ingeschreven?"
)


def test_de_vraag_uit_de_reaudit_houdt_haar_schooljaar_binnen_80_tekens():
    titel = rapporttitel(_VRAAG_P06, None, (2025, 2025))

    assert len(titel) <= 80 and "2025/26" in titel
    assert titel == "Hoeveel hbo-studenten stonden er in 2025/26 per sector ingeschreven"


def test_een_jaar_dat_de_inkorting_wegkapt_wordt_de_periode_uit_de_data():
    vraag = "Hoe ontwikkelde de instroom van eerstejaars in het hbo zich per sector en per provincie in 2024?"
    titel = rapporttitel(vraag, None, (2024, 2024))

    assert len(titel) <= 80 and titel.endswith("… (2024/25)")


def test_een_jaar_dat_de_inkorting_overleeft_komt_er_niet_nog_eens_bij():
    vraag = "In 2024: hoe ontwikkelde de instroom van eerstejaars in het hbo zich per sector en per provincie?"
    titel = rapporttitel(vraag, None, (2024, 2024))

    assert len(titel) <= 80 and titel.startswith("In 2024:") and titel.endswith("…")
    assert "2024/25" not in titel


def test_een_tussenzin_valt_weg_als_de_titel_te_lang_is():
    vraag = "Hoeveel hbo-studenten (ingeschreven personen, hoofdinschrijvingen) stonden er per sector ingeschreven?"

    assert (
        rapporttitel(vraag, None, (2025, 2025)) == "Hoeveel hbo-studenten stonden er per sector ingeschreven (2025/26)"
    )


def test_een_tussenzin_in_een_korte_titel_blijft():
    assert rapporttitel("Hoeveel studenten (personen) per sector?", None, (2025, 2025)) == (
        "Hoeveel studenten (personen) per sector (2025/26)"
    )
    assert rapporttitel("Hoeveel studenten (personen) per sector?", None) == "Hoeveel studenten (personen) per sector"


def test_een_tussenzin_met_een_jaar_blijft_ook_in_een_lange_titel():
    vraag = "Hoe ontwikkelde de instroom (cohort 2024) van eerstejaars in het hbo zich per sector en per provincie?"
    titel = rapporttitel(vraag, None, (2024, 2024))

    assert "(cohort 2024)" in titel and "2024/25" not in titel and len(titel) <= 80
