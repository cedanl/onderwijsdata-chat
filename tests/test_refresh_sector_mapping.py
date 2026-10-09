"""Het refresh-script kent alle sectoren van beide indelingen (#455).

Het kende alleen de 6 oude hbo/wo-sectoren: opnieuw draaien wiste de andere 4, de 17 mbo-sectoren
en `_indelingen` uit data/sector_cluster_mapping.json.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from data import arbeidsmarkt
from scripts import refresh_sector_mapping as script

_CLUSTERS = ["Accountants", "Chauffeurs", "Programmeurs"]


def _vastgelegd() -> dict:
    return json.loads(arbeidsmarkt.SECTOR_CLUSTER_PATH.read_text())


def _sectoren(mapping: dict) -> list[str]:
    return sorted(k for k in mapping if not k.startswith("_"))


def _antwoord(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _model(*, model, messages, **_):
    """Nepmodel: antwoordt per indeling, met code fences, een onbekende sector en een verzonnen cluster."""
    prompt = messages[0]["content"]
    if "- TECHNIEK:" in prompt:
        antwoord = {"TECHNIEK": ["Programmeurs", "Chauffeurs"], "ECONOMIE": ["Accountants"], "KUNST": ["Chauffeurs"]}
    else:
        antwoord = {"Transport, scheepvaart en logistiek": ["Chauffeurs", "Piloten"]}
    return _antwoord(f"```json\n{json.dumps(antwoord)}\n```")


@pytest.fixture
def ververst(tmp_path, capsys):
    uitvoer = tmp_path / "sector_cluster_mapping.json"
    with (
        patch.object(script, "laad_clusters", return_value=_CLUSTERS),
        patch.object(script.litellm, "completion", side_effect=_model) as completion,
    ):
        script.main(uitvoer)
    return uitvoer, [c.kwargs["messages"][0]["content"] for c in completion.call_args_list], capsys.readouterr().out


def test_het_script_houdt_alle_sectoren_en_de_indelingen(ververst):
    uitvoer, _, _ = ververst
    ruw = json.loads(uitvoer.read_text())

    assert _sectoren(ruw) == _sectoren(_vastgelegd())
    assert ruw["_indelingen"] == _vastgelegd()["_indelingen"]
    assert set(ruw["_manifest"]) == set(script.manifest())


def test_het_resultaat_voldoet_aan_de_mappingregels(ververst):
    uitvoer, _, _ = ververst
    ruw = json.loads(uitvoer.read_text())
    indeling = arbeidsmarkt.load_sector_indeling(uitvoer)

    assert all(s in indeling for s in arbeidsmarkt.load_sector_cluster_map(uitvoer))
    # Elke sector hoort bij precies één indeling.
    toegewezen = [s for sectoren in ruw["_indelingen"].values() for s in sectoren]
    assert sorted(toegewezen) == sorted(arbeidsmarkt.load_sector_cluster_map(uitvoer))


def test_onbekende_sectoren_en_clusters_vallen_weg_en_lege_sectoren_blijven(ververst):
    uitvoer, _, uitvoer_tekst = ververst
    ruw = json.loads(uitvoer.read_text())

    assert ruw["TECHNIEK"] == ["Programmeurs", "Chauffeurs"]
    assert ruw["ECONOMIE"] == ["Accountants"]
    assert "KUNST" not in ruw
    assert ruw["Transport, scheepvaart en logistiek"] == ["Chauffeurs"]
    assert ruw["RECHT"] == [] and ruw["Zorg en welzijn"] == []
    # Wat wegvalt, staat in de uitvoer van het script.
    assert "onbekende sectoren genegeerd: ['KUNST']" in uitvoer_tekst
    assert "onbekende clusters genegeerd: ['Piloten']" in uitvoer_tekst


def test_een_aanroep_per_indeling_met_al_haar_sectoren(ververst):
    _, prompts, _ = ververst

    assert len(prompts) == len(script.SECTOREN) == 2
    for prompt, (indeling, sectoren) in zip(prompts, script.SECTOREN.items(), strict=True):
        assert indeling in prompt
        assert all(f"- {s}:" in prompt for s in sectoren)
        andere = [s for i, ss in script.SECTOREN.items() if i != indeling for s in ss]
        assert not [s for s in andere if f"- {s}:" in prompt]
        assert all(f"- {c}" in prompt for c in _CLUSTERS)


def test_de_sectoren_van_het_script_zijn_de_vastgelegde_indelingen():
    """Loopt het script uit de pas met de mapping, dan faalt CI in plaats van een volgende refresh."""
    assert {i: list(s) for i, s in script.SECTOREN.items()} == _vastgelegd()["_indelingen"]
    assert [len(s) for s in script.SECTOREN.values()] == [10, 17]
    assert all(beschrijving.strip() for s in script.SECTOREN.values() for beschrijving in s.values())


def test_zonder_antwoord_schrijft_het_script_niets(tmp_path):
    uitvoer = tmp_path / "sector_cluster_mapping.json"
    with (
        patch.object(script, "laad_clusters", return_value=_CLUSTERS),
        patch.object(script.litellm, "completion", return_value=_antwoord(None)),
        pytest.raises(RuntimeError, match="geen antwoord"),
    ):
        script.main(uitvoer)

    assert not uitvoer.exists()


@pytest.mark.parametrize(
    "inhoud",
    ['{"TECHNIEK": ["ICT"]}', '```json\n{"TECHNIEK": ["ICT"]}\n```', '  ```\n{"TECHNIEK": ["ICT"]}\n```  '],
)
def test_lees_antwoord_haalt_het_json_object_uit_code_fences(inhoud):
    assert script.lees_antwoord(inhoud) == {"TECHNIEK": ["ICT"]}
