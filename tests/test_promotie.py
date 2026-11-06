import pytest

import scripts.promotie as promotie
from scripts.promotie import fouten, release_tags, schrijf_pin

RANGE = ">=0.0.1-0.0"


def test_release_tags_alleen_kale_semver_gesorteerd():
    tags = ["v2.1.0", "1.10.0", "1.9.0", "2.0.0", "env/playground/2.0.0", "2.0.0-staging-1", "1.8.6"]
    assert release_tags(tags) == ["1.8.6", "1.9.0", "1.10.0", "2.0.0"]


def test_geldige_ladder_geeft_geen_fouten():
    assert fouten(RANGE, "2.0.0", ["1.8.6", "2.0.0"]) == []


def test_playground_op_range_is_fout():
    assert any("vaste release" in f for f in fouten(RANGE, RANGE, ["2.0.0"]))


def test_playground_op_rc_build_is_fout():
    assert fouten(RANGE, "2.0.1-rc.5+abc1234", ["2.0.0"])


def test_playground_zonder_tag_op_remote_is_fout():
    assert any("bestaat niet" in f for f in fouten(RANGE, "2.0.0", ["1.8.6"]))


def test_test_moet_range_houden():
    assert any("open range" in f for f in fouten("2.0.0", "2.0.0", ["2.0.0"]))


def test_schrijf_pin_raakt_alleen_de_versieregel(tmp_path, monkeypatch):
    env = tmp_path / "playground"
    env.mkdir()
    (env / "helmrelease.yaml").write_text(
        'spec:\n  chart:\n    spec:\n      chart: x\n      # let op\n      version: ">=0.0.1-0.0"\n  interval: 1m\n'
    )
    monkeypatch.setattr(promotie, "MANIFESTS", tmp_path)
    schrijf_pin("playground", "2.0.0")
    assert (env / "helmrelease.yaml").read_text() == (
        'spec:\n  chart:\n    spec:\n      chart: x\n      # let op\n      version: "2.0.0"\n  interval: 1m\n'
    )


def test_promote_weigert_release_zonder_chart(tmp_path, monkeypatch):
    # De tag 2.0.0 bestaat, maar heeft geen chart (Agents.md); een pin erop laat Flux falen (#844).
    env = tmp_path / "playground"
    env.mkdir()
    origineel = 'spec:\n  chart:\n    spec:\n      chart: x\n      version: "2.2.0"\n'
    (env / "helmrelease.yaml").write_text(origineel)
    monkeypatch.setattr(promotie, "MANIFESTS", tmp_path)
    monkeypatch.setattr(promotie, "remote_tags", lambda: ["2.0.0", "2.2.0"])
    with pytest.raises(SystemExit, match="geen chart"):
        promotie.promote("2.0.0")
    assert (env / "helmrelease.yaml").read_text() == origineel


@pytest.mark.parametrize(
    ("huidig", "nieuw", "melden"),
    [
        ("2.8.0", "2.9.0", True),  # de eerste release met de Studiekeuzedatabase
        ("2.7.0", "2.8.1", True),  # ook als een release wordt overgeslagen
        (RANGE, "2.9.0", True),  # een range zegt niet wat er draaide: liever één melding te veel
        ("2.9.0", "2.10.0", False),  # al gemeld bij de vorige promotie
        ("2.7.0", "2.8.0", False),  # nog zonder SKDB
        ("2.9.0", "2.8.0", False),  # terug naar een release zonder SKDB
    ],
)
def test_lcsk_melding_alleen_bij_de_eerste_release_met_skdb(huidig, nieuw, melden):
    melding = promotie.lcsk_melding(huidig, nieuw)

    assert (melding is not None) == melden
    if melding is not None:
        assert "info@lcsk.nl" in melding and "drie weken" in melding


def test_de_grens_van_de_lcsk_melding_volgt_de_changelog():
    # LAATSTE_ZONDER_SKDB is de laatste release in CHANGELOG.md zonder de Studiekeuzedatabase (#957); de eerste release
    # erna noemt hem.
    import re
    from pathlib import Path

    tekst = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text()
    secties = dict(re.findall(r"^## (\d+\.\d+\.\d+) — [^\n]*\n(.*?)(?=^## |\Z)", tekst, flags=re.MULTILINE | re.DOTALL))
    grens = promotie._volgorde(promotie.LAATSTE_ZONDER_SKDB)
    tot_grens = [v for v in secties if promotie._volgorde(v) <= grens]
    erna = sorted((v for v in secties if promotie._volgorde(v) > grens), key=promotie._volgorde)

    assert promotie.LAATSTE_ZONDER_SKDB in secties
    assert not any("Studiekeuzedatabase" in secties[v] for v in tot_grens)
    if erna:
        assert "Studiekeuzedatabase" in secties[erna[0]]


def test_promote_meldt_lcsk_bij_de_eerste_release_met_skdb(tmp_path, monkeypatch, capsys):
    env = tmp_path / "playground"
    env.mkdir()
    (env / "helmrelease.yaml").write_text('spec:\n  chart:\n    spec:\n      chart: x\n      version: "2.8.0"\n')
    monkeypatch.setattr(promotie, "MANIFESTS", tmp_path)
    monkeypatch.setattr(promotie, "remote_tags", lambda: ["2.8.0", "2.9.0"])

    assert promotie.promote("2.9.0") == 0

    assert "info@lcsk.nl" in capsys.readouterr().out
