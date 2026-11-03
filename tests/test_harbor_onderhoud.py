from datetime import UTC, datetime, timedelta

import pytest

from scripts.harbor_onderhoud import (
    IMMUTABLE_PATROON,
    Artifact,
    hoogste_in_range,
    immutability_problemen,
    lees_pins,
    maak_plan,
    semver_sleutel,
)

NU = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
RANGE = ">=0.0.1-0.0"


def art(*tags, dagen=10, digest=None):
    return Artifact(digest or f"sha256:{'-'.join(tags)}", tuple(tags), NU - timedelta(days=dagen), 350 * 2**20)


def plan(images, charts, pins=None, **kw):
    pins = pins if pins is not None else {"test": RANGE, "playground": "2.5.2"}
    return maak_plan(images, charts, pins, NU, **{"behoud_main": 1, "behoud_mr": 1, "min_uren": 24, **kw})


def weg(p):
    return {t for a in p.weg_images for t in a.tags}


@pytest.fixture
def harbor():
    """Twee releases, drie main-builds, drie MR-builds; de nieuwste main-build is wat test draait."""
    images = [
        art("2.5.2", dagen=30),
        art("2.5.3", dagen=20),
        art("latest", dagen=1.5),
        art("aaaaaaa1", dagen=9),
        art("aaaaaaa2", dagen=8),
        art("aaaaaaa3", dagen=7),
        art("bbbbbbb1", dagen=6),
        art("bbbbbbb2", dagen=5),
        art("bbbbbbb3", dagen=4),
    ]
    charts = [
        art("2.5.2", dagen=30),
        art("2.5.3", dagen=20),
        art("2.5.4-rc.9_aaaaaaa1", dagen=9),
        art("2.5.4-rc.10_aaaaaaa2", dagen=8),
        art("2.5.4-rc.11_aaaaaaa3", dagen=7),
        art("0.0.1-build.12_featx.bbbbbbb1", dagen=6),
        art("0.0.1-build.13_featx.bbbbbbb2", dagen=5),
        art("0.0.1-build.14_featy.bbbbbbb3", dagen=4),
    ]
    return images, charts


def test_semver_prerelease_numeriek_en_build_telt_niet():
    assert semver_sleutel("2.5.4-rc.10_aaaa") > semver_sleutel("2.5.4-rc.9_ffff")
    assert semver_sleutel("2.5.4") > semver_sleutel("2.5.4-rc.999")
    assert semver_sleutel("2.5.4-rc.1") > semver_sleutel("2.5.4-build.99")


def test_range_kiest_hoogste_zoals_flux():
    tags = ["2.5.3", "2.5.4-rc.9_aaaaaaa1", "2.5.4-rc.10_aaaaaaa2", "0.0.1-build.14_featy.bbbbbbb3", "rommel"]
    assert hoogste_in_range(tags, RANGE) == "2.5.4-rc.10_aaaaaaa2"


def test_omgevingen_releases_en_latest_blijven(harbor):
    p = plan(*harbor)
    assert p.fouten == []
    assert p.omgevingen == {"test": ("2.5.4-rc.11_aaaaaaa3", "aaaaaaa3"), "playground": ("2.5.2", "2.5.2")}
    verwijderd = weg(p)
    assert not verwijderd & {"2.5.2", "2.5.3", "latest", "aaaaaaa3"}
    assert verwijderd == {"aaaaaaa1", "aaaaaaa2", "bbbbbbb1", "bbbbbbb2"}


def test_chart_gaat_mee_met_zijn_image_releasecharts_nooit(harbor):
    p = plan(*harbor)
    charts = {t for a in p.weg_charts for t in a.tags}
    assert charts == {
        "2.5.4-rc.9_aaaaaaa1",
        "2.5.4-rc.10_aaaaaaa2",
        "0.0.1-build.12_featx.bbbbbbb1",
        "0.0.1-build.13_featx.bbbbbbb2",
    }


def test_nieuwste_builds_per_soort_blijven(harbor):
    p = plan(*harbor, behoud_main=2, behoud_mr=3)
    assert weg(p) == {"aaaaaaa1"}


def test_jonger_dan_grens_blijft(harbor):
    images, charts = harbor
    images.append(art("ccccccc1", dagen=0.5))
    p = plan(images, charts, behoud_mr=0)
    assert "ccccccc1" not in weg(p)


def test_onbekende_tag_blijft(harbor):
    images, charts = harbor
    images.append(art("handmatig-debug", dagen=60))
    assert "handmatig-debug" not in weg(plan(images, charts))


def test_ontbrekende_pin_verwijdert_niets(harbor):
    images, charts = harbor
    p = plan(images, charts, pins={"test": RANGE, "playground": "2.5.0"})
    assert any("2.5.0" in f for f in p.fouten)
    assert p.weg_images == [] and p.weg_charts == []


def test_image_achter_testchart_ontbreekt_verwijdert_niets(harbor):
    images, charts = harbor
    images = [a for a in images if a.tags != ("aaaaaaa3",)]
    p = plan(images, charts)
    assert any("aaaaaaa3" in f for f in p.fouten)
    assert p.weg_images == []


def test_pins_uit_de_manifests():
    pins = lees_pins()
    assert set(pins) >= {"test", "playground"}
    assert all(isinstance(v, str) and v for v in pins.values())


def regel(patroon, disabled=False):
    return {"disabled": disabled, "tag_selectors": [{"decoration": "matches", "pattern": patroon}]}


def test_immutability_release_regel_aanwezig():
    assert immutability_problemen([regel(IMMUTABLE_PATROON)]) == []
    assert IMMUTABLE_PATROON == (
        "{[0-9],[0-9][0-9],[0-9][0-9][0-9]}.{[0-9],[0-9][0-9],[0-9][0-9][0-9]}.{[0-9],[0-9][0-9],[0-9][0-9][0-9]}"
    )


def test_immutability_ontbreekt_of_staat_uit():
    assert immutability_problemen([])
    assert immutability_problemen([regel(IMMUTABLE_PATROON, disabled=True)])


def test_immutability_met_ster_blokkeert_opruimen():
    problemen = immutability_problemen([regel(IMMUTABLE_PATROON), regel("[0-9]*.[0-9]*.[0-9]*")])
    assert len(problemen) == 1 and "*" in problemen[0]
