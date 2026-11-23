"""De antwoordcontrole krijgt wat ze van het gesprek moet weten als parameter, niet uit de sessie (#694)."""

import ast
import inspect
import json
import logging
from unittest.mock import patch

import pytest

from agent import controles
from agent.controles import antwoordcontrole

_VRAAG = "Hoeveel eerstejaars?"
_DATA = [json.dumps({"data_key": "duo:p02:a", "rijen": [{"JAAR": 2023, "AANTAL": 5943}]})]


def _problemen(tekst: str, clarify_keuzes: list[str] | None = None) -> list[str]:
    return antwoordcontrole(_VRAAG, [], [], clarify_keuzes or [], [])(tekst, _DATA)


def test_een_gekozen_jaar_dat_het_antwoord_niet_noemt_wordt_gemeld():
    problemen = _problemen("Het zijn er 5943 in 2018.", clarify_keuzes=["2023"])

    assert any("Gekozen was '2023'" in p for p in problemen), problemen


def test_zonder_gekozen_opties_is_er_geen_keuzeprobleem():
    assert not any("Gekozen was" in p for p in _problemen("Het zijn er 5943 in 2018."))


def test_een_ongedekt_getal_wordt_nog_steeds_gemeld():
    assert any("1234" in p or "1.234" in p for p in _problemen("Het zijn er 1234."))


def test_de_controlemodule_kent_geen_sessie_en_geen_emit():
    """Wat de controle nodig heeft, staat in de signatuur; dat houdt haar zonder transport te testen."""
    namen = {n.id for n in ast.walk(ast.parse(inspect.getsource(controles))) if isinstance(n, ast.Name)} | {
        n.arg for n in ast.walk(ast.parse(inspect.getsource(controles))) if isinstance(n, ast.arg)
    }

    assert not namen & {"session", "emit"}


def test_een_foute_rekensom_is_een_hard_probleem_en_staat_in_het_log(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="agent.run"):
        problemen = _problemen("Dat zijn 3 × 3 × 3 × 4 × 15 = 540 combinaties.")

    [som] = [p for p in problemen if getattr(p, "controle", None) == "onjuiste_rekensommen"]
    assert "is 1.620, niet 540" in som and getattr(som, "hard", False)
    assert "onjuiste_rekensommen=hard" in caplog.text


def test_een_juiste_rekensom_geeft_ok_in_het_log(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="agent.run"):
        problemen = _problemen("Dat zijn 3 × 3 × 3 × 4 × 15 = 1.620 combinaties.")

    assert not [p for p in problemen if getattr(p, "controle", None) == "onjuiste_rekensommen"]
    assert "onjuiste_rekensommen=ok" in caplog.text


# --- #1013: telling en vergelijking tegen de tabel in het antwoord ---------------------------------------------------

_HOGESCHOLEN = "\n".join(f"| Hogeschool {i} | {v} |" for i, v in enumerate([-5] * 9 + [4] * 3, 1))
_TELTABEL = f"| Hogeschool | Verschil |\n|---|---:|\n{_HOGESCHOLEN}"
_M01 = (
    "| Diplomasoort | 2023/24 | 2024/25 |\n|---|---:|---:|\n"
    "| Bachelor | 50.110 | 52.250 |\n| Wo-master | 50.690 | 53.570 |"
)


def _tabelbeweringen(problemen: list[str]) -> list[str]:
    return [p for p in problemen if getattr(p, "controle", None) == "onjuiste_tabelbeweringen"]


def test_een_foute_telling_tegen_de_tabel_is_hard_en_staat_in_het_log(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="agent.run"):
        problemen = _problemen(f"10 van de 12 hogescholen is gedaald.\n\n{_TELTABEL}")

    [telling] = _tabelbeweringen(problemen)
    assert "zijn het er 9 van de 12" in telling and getattr(telling, "hard", False)
    assert "onjuiste_tabelbeweringen=hard" in caplog.text


def test_een_foute_vergelijking_is_zacht_en_staat_in_het_log(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="agent.run"):
        problemen = _problemen(f"In 2023/24 en 2024/25 waren er meer bachelor- dan wo-masterdiploma's.\n\n{_M01}")

    [vergelijking] = _tabelbeweringen(problemen)
    assert not getattr(vergelijking, "hard", False)
    assert "onjuiste_tabelbeweringen=zacht" in caplog.text


def test_een_juiste_telling_geeft_ok_in_het_log(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="agent.run"):
        problemen = _problemen(f"9 van de 12 hogescholen is gedaald.\n\n{_TELTABEL}")

    assert not _tabelbeweringen(problemen)
    assert "onjuiste_tabelbeweringen=ok" in caplog.text


def test_een_fout_in_de_tabelcontrole_wordt_niet_gecontroleerd(monkeypatch, caplog: pytest.LogCaptureFixture):
    def onjuiste_tabelbeweringen(lezingen, tool_results):
        raise ValueError("kapot")

    monkeypatch.setattr(controles, "onjuiste_tabelbeweringen", onjuiste_tabelbeweringen)
    with caplog.at_level(logging.INFO, logger="agent.run"):
        problemen = _problemen(f"10 van de 12 hogescholen is gedaald.\n\n{_TELTABEL}")

    [probleem] = _tabelbeweringen(problemen)
    assert getattr(probleem, "niet_gecontroleerd", False) and not getattr(probleem, "hard", False)
    assert "onjuiste_tabelbeweringen=niet gecontroleerd" in caplog.text


# --- onbekende dataset-ID's (#1084, #1088) ---


def _onbekend(tekst: str, vraag: str = _VRAAG, tool_results: list[str] | None = None, eerder: list[str] | None = None):
    with patch("agent.labels.catalogus_titel", side_effect=lambda d: f"titel {d}" if d == "85354NED" else d):
        problemen = antwoordcontrole(vraag, [], eerder or [], [], [])(tekst, tool_results or _DATA)
    return [p for p in problemen if getattr(p, "controle", None) == "onbekende_datasets"]


def test_een_verzonnen_bron_in_de_lopende_tekst_is_een_hard_probleem():
    """#1084: na een mislukte herkansing bleef de verzonnen tabel staan, met alleen een "Let op"."""
    [probleem] = _onbekend("Volgens CBS-tabel 85999NED telde het mbo 5943 studenten.")

    assert getattr(probleem, "hard", False)
    assert probleem.melding == "Dataset 85999NED bestaat niet in de catalogus."


def test_een_id_uit_de_vraag_of_een_eerder_bericht_van_de_gebruiker_geeft_geen_probleem():
    tekst = "CBS-tabel 99999NED staat niet in de catalogus."

    assert _onbekend(tekst, vraag="Wat staat in tabel 99999NED?") == []
    assert _onbekend(tekst, eerder=["Wat staat in tabel 99999NED?"]) == []


def test_een_id_dat_een_tool_als_onbekend_teruggaf_geeft_geen_probleem():
    """#1088: het antwoord zegt terecht dat de tabel niet bestaat."""
    tool = json.dumps({"fout": "Dataset '99999NED' staat niet in de catalogus."})

    assert _onbekend("CBS-tabel 99999NED staat niet in de catalogus.", tool_results=[*_DATA, tool]) == []


def test_een_bestaand_id_geeft_geen_probleem():
    assert _onbekend("Volgens CBS-tabel 85354NED telde het mbo 5943 studenten.") == []
