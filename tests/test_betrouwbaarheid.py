"""De betrouwbaarheid per release op de docs-site (#1246): scripts/betrouwbaarheid.py zet de uitslag van een
eval:bronwaarheid-run (slagingspercentage- en kritiek-JSON) om in een rij en een detailsectie van docs/betrouwbaarheid.md.
"""

import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from scripts import betrouwbaarheid

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "betrouwbaarheid"
SLAGING = FIXTURES / "slagingspercentage-2026-11-25.json"
KRITIEK = FIXTURES / "kritiek-2026-11-25.json"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
PAGINA = ROOT / "docs" / "betrouwbaarheid.md"


def _release(versie: str = "2.9.0", commit: str = COMMIT, slaging: Path = SLAGING) -> betrouwbaarheid.Release:
    return betrouwbaarheid.lees_release(slaging, KRITIEK, versie=versie, commit=commit)


def _overzicht(tekst: str) -> list[str]:
    """De rijen van de overzichtstabel, zonder kop en scheidingsregel."""
    blok = tekst.split(betrouwbaarheid.OVERZICHT_BEGIN)[1].split(betrouwbaarheid.OVERZICHT_EINDE)[0]
    return [r for r in blok.splitlines() if r.startswith("| ") and not r.startswith("| Datum")]


def _regel(pad: Path, patroon: str) -> int:
    return next(i for i, r in enumerate(pad.read_text(encoding="utf-8").splitlines(), 1) if patroon in r)


def test_de_rij_noemt_datum_versie_commit_modellen_herhalingen_en_percentages():
    tekst = betrouwbaarheid.werk_bij(PAGINA.read_text(encoding="utf-8"), _release())
    (rij,) = _overzicht(tekst)
    cellen = [c.strip() for c in rij.strip("|").split("|")]
    assert cellen[0] == "2026-11-25"
    assert cellen[1] == "[2.9.0](#release-2-9-0)"
    assert cellen[2] == f"[`01234567`](https://github.com/cedanl/onderwijsdata-chat/commit/{COMMIT})"
    assert cellen[3] == "claude-haiku-4-5, gpt-oss-120b"
    assert cellen[4] == "3"
    assert cellen[5] == "claude-haiku-4-5: 83% (10 van 12)<br>gpt-oss-120b: 83% (10 van 12)"
    assert cellen[6] == "claude-haiku-4-5: 2 van 3<br>gpt-oss-120b: 3 van 3"
    # De kritieke weigeringen apart: een weigering moet in elke herhaling slagen; rood met naam.
    assert cellen[7] == "claude-haiku-4-5: 1 van 2 (rood: weigering-toekomst)<br>gpt-oss-120b: 2 van 2"


def test_de_detailsectie_per_vraag_met_een_link_naar_de_vraag_en_de_ijkwaarde():
    tekst = betrouwbaarheid.werk_bij(PAGINA.read_text(encoding="utf-8"), _release())
    assert "### 2.9.0 (2026-11-25) {#release-2-9-0}" in tekst
    assert "`azure_ai/claude-haiku-4-5`" in tekst and "`openai/gpt-oss-120b`" in tekst
    spiegel = f"https://github.com/cedanl/onderwijsdata-chat/blob/{COMMIT}"
    evals = ROOT / "tests/e2e/evaluations.json"
    ijk = ROOT / "tests/e2e/ijkwaarden.json"
    trend_regel = _regel(evals, '"label": "trend-analyse"')
    deeltijd_regel = _regel(ijk, '"duo-hu-deeltijd-2025": {')
    trend = f"[trend-analyse]({spiegel}/tests/e2e/evaluations.json#L{trend_regel})"
    deeltijd = f"[7.408 (2025/26)]({spiegel}/tests/e2e/ijkwaarden.json#L{deeltijd_regel})"
    rijen = {r.split("|")[1].strip(): r for r in tekst.splitlines() if r.startswith("| [")}
    # Een referentiewaarde in de vraag zelf staat er zonder eigen link: de link naar de vraag toont haar.
    referenties = "30.280 (2022), 29.941 (2023), 29.620 (2024)"
    assert rijen[trend] == f"| {trend} | nee | geslaagd (3 van 3) | niet geslaagd (1 van 3) | {referenties} |"
    hu = next(r for k, r in rijen.items() if k.startswith("[ijk-hu-deeltijd]"))
    assert hu.endswith(f"| ja | niet geslaagd (2 van 3) | geslaagd (3 van 3) | {deeltijd} |")
    weigering = next(r for k, r in rijen.items() if k.startswith("[weigering-toekomst]"))
    assert "| ja, weigering | niet geslaagd (2 van 3) | geslaagd (3 van 3) | – |" in weigering


def test_een_tweede_run_van_dezelfde_release_vervangt_haar_rij_oude_releases_blijven(tmp_path):
    leeg = PAGINA.read_text(encoding="utf-8")
    een = betrouwbaarheid.werk_bij(leeg, _release("2.9.0"))
    assert betrouwbaarheid.werk_bij(een, _release("2.9.0")) == een  # idempotent

    twee = betrouwbaarheid.werk_bij(een, _release("2.10.0", commit="f" * 40))
    rijen = _overzicht(twee)
    assert [r.split("|")[2].strip() for r in rijen] == ["[2.10.0](#release-2-10-0)", "[2.9.0](#release-2-9-0)"]
    assert twee.count("{#release-2-9-0}") == 1 and twee.count("{#release-2-10-0}") == 1

    # Dezelfde release opnieuw gemeten: haar rij en sectie wijzigen, de andere blijft staan en de volgorde ook.
    data = json.loads(SLAGING.read_text(encoding="utf-8"))
    data["modellen"]["azure_ai/claude-haiku-4-5"]["percentage"] = 50
    opnieuw = tmp_path / "slagingspercentage-2026-11-25.json"
    opnieuw.write_text(json.dumps(data), encoding="utf-8")
    drie = betrouwbaarheid.werk_bij(twee, _release("2.9.0", slaging=opnieuw))
    rijen = _overzicht(drie)
    assert len(rijen) == 2
    assert rijen[0] == _overzicht(twee)[0]
    assert "claude-haiku-4-5: 50% (10 van 12)" in rijen[1]
    assert drie.count("{#release-2-9-0}") == 1


def test_de_lege_pagina_zegt_dat_er_nog_geen_run_is_en_wat_de_score_meet():
    leeg = PAGINA.read_text(encoding="utf-8")
    assert "Nog geen run gepubliceerd" in leeg
    assert _overzicht(leeg) == []
    for woord in ("vragenset", "testomgeving", "modellen", "slechte score"):
        assert woord in leeg, woord
    gevuld = betrouwbaarheid.werk_bij(leeg, _release())
    assert "Nog geen run gepubliceerd" not in gevuld
    # De vaste tekst boven en onder de blokken blijft staan.
    assert leeg.split(betrouwbaarheid.OVERZICHT_BEGIN)[0] == gevuld.split(betrouwbaarheid.OVERZICHT_BEGIN)[0]


def test_het_script_schrijft_de_pagina_en_leidt_het_kritieke_rapport_af(tmp_path):
    pagina = tmp_path / "betrouwbaarheid.md"
    shutil.copyfile(PAGINA, pagina)
    args = ["--slagingspercentage", str(SLAGING), "--versie", "2.9.0", "--commit", COMMIT, "--pagina", str(pagina)]
    assert betrouwbaarheid.main(args) == 0
    eerst = pagina.read_text(encoding="utf-8")
    assert len(_overzicht(eerst)) == 1
    assert betrouwbaarheid.main(args) == 0
    assert pagina.read_text(encoding="utf-8") == eerst


@pytest.mark.parametrize(
    ("versie", "commit"),
    [("v2.9.0", COMMIT), ("2.9", COMMIT), ("2.9.0", "abc"), ("2.9.0", "x" * 40)],
)
def test_een_versie_zonder_releasevorm_of_een_korte_commit_wordt_geweigerd(versie, commit):
    with pytest.raises(SystemExit):
        _release(versie, commit)


def test_een_onvolledig_rapport_wordt_geweigerd(tmp_path):
    kapot = tmp_path / "slagingspercentage-2026-11-25.json"
    kapot.write_text(json.dumps({"gemeten_op": "2026-11-25"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="modellen"):
        betrouwbaarheid.lees_release(kapot, KRITIEK, versie="2.9.0", commit=COMMIT)


def test_de_pagina_staat_in_de_navigatie_onder_kwaliteit_en_veiligheid():
    nav = yaml.safe_load(
        re.sub(r"!!python/name:\S+", "''", (ROOT / "mkdocs.yml").read_text(encoding="utf-8")),
    )["nav"]

    def vind(items):
        # De nav heeft twee lagen (Product & gebruik, Techniek & beheer): zoek de sectie op elk niveau.
        for item in items:
            if not isinstance(item, dict):
                continue
            if "Kwaliteit & veiligheid" in item:
                return item["Kwaliteit & veiligheid"]
            for waarde in item.values():
                if isinstance(waarde, list) and (gevonden := vind(waarde)):
                    return gevonden
        return None

    sectie = vind(nav)
    assert sectie, "sectie Kwaliteit & veiligheid ontbreekt in de nav"
    assert "kwaliteit-en-veiligheid.md" in sectie
    assert {"Betrouwbaarheid per release": "betrouwbaarheid.md"} in sectie
    assert "betrouwbaarheid.md" in (ROOT / "docs/kwaliteit-en-veiligheid.md").read_text(encoding="utf-8")
    assert "scripts/betrouwbaarheid.py" in (ROOT / "docs/promoten.md").read_text(encoding="utf-8")
