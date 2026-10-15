"""Persoonsgegevens in de invoer (#478, privacy H3/L5): herkenning in code, en geen BSN in een rapporttitel.

Een dummy-BSN in de vraag belandde in de gesprekstitel, de export-bestandsnaam en de
terugvaltitel van een rapport. De herkenning is deterministisch (elfproef, e-mail, telefoon),
waarschuwt en houdt zulke tekst uit titels; ze blokkeert niet, want een 9-cijferige code kan
de elfproef toevallig doorstaan.
"""

import re
from pathlib import Path

import pytest

from agent.report_titel import TITEL_ZONDER_PERSOONSGEGEVENS, rapporttitel
from core import persoonsgegevens
from core.persoonsgegevens import GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS
from prompts import SYSTEM_PROMPT


@pytest.mark.parametrize("bsn", ["123456782", "111222333"])
def test_een_bsn_doorstaat_de_elfproef(bsn):
    assert persoonsgegevens.elfproef(bsn)


@pytest.mark.parametrize("geen", ["123456789", "000000000", "12345678", "1234567890", "85423NED"])
def test_een_ander_getal_niet(geen):
    assert not persoonsgegevens.elfproef(geen)


def test_vindt_bsn_email_en_telefoon_in_volgorde():
    tekst = "Mijn naam is Test Persoon, mijn BSN is 123456782, mail test@voorbeeld.nl of bel 06-12345678."
    assert [(g.soort, g.tekst) for g in persoonsgegevens.vind(tekst)] == [
        ("bsn", "123456782"),
        ("email", "test@voorbeeld.nl"),
        ("telefoon", "06-12345678"),
    ]


@pytest.mark.parametrize(
    "tekst",
    [
        "Hoeveel studenten had de HU in 2024/25 bij opleiding 36201?",
        "CBS-tabel 85423NED, code A025297, instelling 21PL",
        "In totaal 123456789 euro, en 1.234.567.890 inschrijvingen",  # geen elfproef, geen losse negen cijfers
        "Bel 0800 1234 (geen tien cijfers) of kijk op onderwijsdata.nl",
        "",
    ],
)
def test_gewone_onderwijsvragen_bevatten_geen_persoonsgegevens(tekst):
    assert not persoonsgegevens.bevat(tekst)


@pytest.mark.parametrize("telefoon", ["0612345678", "06 12345678", "030-1234567", "+31 6 12345678", "0031612345678"])
def test_nederlandse_telefoonnummers(telefoon):
    [gevonden] = persoonsgegevens.vind(f"bel me op {telefoon} graag")
    assert gevonden.soort == "telefoon"


def test_rapporttitel_laat_persoonsgegevens_weg():
    vraag = "Mijn naam is Test Persoon, mijn BSN is 123456782, kun je zoeken hoeveel studenten de HU heeft?"
    assert rapporttitel(vraag, None) == TITEL_ZONDER_PERSOONSGEGEVENS
    assert rapporttitel(vraag, "Hogeschool Utrecht") == f"{TITEL_ZONDER_PERSOONSGEGEVENS} – Hogeschool Utrecht"
    assert "123456782" not in rapporttitel("mail naar test@voorbeeld.nl: hoeveel studenten?", None)


def test_de_systeemprompt_heeft_een_regel_over_persoonsgegevens_en_kleine_aantallen():
    """Eén regel in code vastgepind: het gedrag was modelgedrag en niet afdwingbaar (#478)."""
    assert "**Persoonsgegevens en kleine aantallen:**" in SYSTEM_PROMPT
    assert "BSN" in SYSTEM_PROMPT and "onderdrukte cel" in SYSTEM_PROMPT


def test_veilige_gesprekstitel():
    assert persoonsgegevens.veilige_gesprekstitel("BSN 111222333") == GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS
    assert persoonsgegevens.veilige_gesprekstitel("Nummer 123456789") == "Nummer 123456789"
    assert persoonsgegevens.veilige_gesprekstitel(None) is None  # geen titel: de database weigert die, zoals voorheen


@pytest.mark.parametrize("titel", [["BSN 111222333"], [111222333], {"t": "BSN 111222333"}, True, False])
def test_een_gesprekstitel_die_tekst_noch_getal_is_wordt_nooit_bewaard(titel):
    """Postgres maakt van een lijst tekst ({"BSN 111222333"}); alleen gecontroleerde tekst gaat erin (#552)."""
    assert persoonsgegevens.veilige_gesprekstitel(titel) == GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS


@pytest.mark.parametrize("getal", [111222333, 111222333.0])
def test_een_getal_als_gesprekstitel_wordt_als_tekst_gecontroleerd(getal):
    """De database maakt van een getal tekst; een BSN als JSON-getal komt er dus ook niet in (#552)."""
    assert persoonsgegevens.veilige_gesprekstitel(getal) == GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS


@pytest.mark.parametrize(("getal", "tekst"), [(123456789, "123456789"), (2.5, "2.5"), (2023.0, "2023")])
def test_een_gewoon_getal_als_gesprekstitel_blijft_staan_als_tekst(getal, tekst):
    assert persoonsgegevens.veilige_gesprekstitel(getal) == tekst


def test_een_lange_gesprekstitel_wordt_ingekort_voor_de_controle(monkeypatch):
    """De herkenning is kwadratisch in de lengte; een titel zonder grens zou de server stilleggen (#552)."""
    gecontroleerd = []
    echte_bevat = persoonsgegevens.bevat
    monkeypatch.setattr(persoonsgegevens, "bevat", lambda tekst: gecontroleerd.append(tekst) or echte_bevat(tekst))
    titel = persoonsgegevens.veilige_gesprekstitel("a" * 100_000)
    assert titel == "a" * persoonsgegevens.MAX_GESPREKSTITEL
    assert gecontroleerd == [titel]  # bewaard wordt wat gecontroleerd is


def test_een_bsn_voorbij_de_grens_wordt_niet_bewaard():
    titel = "a" * (persoonsgegevens.MAX_GESPREKSTITEL - 4) + " 111222333"
    assert persoonsgegevens.veilige_gesprekstitel(titel) == titel[: persoonsgegevens.MAX_GESPREKSTITEL]
    assert "111222333" not in persoonsgegevens.veilige_gesprekstitel(titel)


def test_de_gesprekstitel_zonder_persoonsgegevens_is_die_van_de_frontend():
    """Server en frontend geven hetzelfde gesprek dezelfde titel (#552)."""
    bron = (Path(__file__).parent.parent / "frontend" / "src" / "conversationTitle.js").read_text(encoding="utf-8")
    [frontend] = re.findall(r"export const TITEL_ZONDER_PERSOONSGEGEVENS = '([^']*)'", bron)
    assert frontend == GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS
