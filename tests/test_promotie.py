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
