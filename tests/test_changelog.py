"""Changelog-fragmenten per MR, samengevoegd bij een release (#797)."""

import difflib

import pytest

from scripts.changelog import CHANGELOG, FRAGMENTEN, breng_uit, lees_fragmenten, voeg_samen

KOP = """\
# Changelog

Inleiding.

## Niet uitgebracht

Nieuwe items komen in `changelog.d/`.
"""

OUD_ITEM = """\
### Oud item van vóór de fragmenten (#5)
- Stond al onder Niet uitgebracht.
"""

EERDERE_VERSIE = """\
## 2.5.0 — 2026-10-22

### Eerder uitgebracht (#3)
- Blijft staan.
"""


def _repo(tmp_path, changelog: str, fragmenten: dict[str, str]):
    pad = tmp_path / "CHANGELOG.md"
    pad.write_text(changelog, encoding="utf-8")
    map_ = tmp_path / "changelog.d"
    map_.mkdir()
    for naam, tekst in fragmenten.items():
        (map_ / naam).write_text(tekst, encoding="utf-8")
    return pad, map_


def test_release_zet_fragmenten_op_issuenummer_onder_de_versiekop_en_verwijdert_ze(tmp_path):
    pad, map_ = _repo(
        tmp_path,
        KOP + "\n" + OUD_ITEM + "\n" + EERDERE_VERSIE,
        {
            "12-klein.md": "### Klein (#12)\n- twaalf\n",
            "797-fragmenten.md": "\n### Fragmenten (#797)\n- zevenhonderd\n  vervolgregel\n\n",
            "100-b.md": "### Honderd b (#100)\n- b\n",
            "100-a.md": "### Honderd a (#100)\n- a\n",
        },
    )

    breng_uit(pad, map_, "2.6.0", "2026-10-30")

    assert pad.read_text(encoding="utf-8") == (
        KOP
        + "\n## 2.6.0 — 2026-10-30\n\n"
        + "### Fragmenten (#797)\n- zevenhonderd\n  vervolgregel\n\n"
        + "### Honderd a (#100)\n- a\n\n"
        + "### Honderd b (#100)\n- b\n\n"
        + "### Klein (#12)\n- twaalf\n\n"
        + OUD_ITEM
        + "\n"
        + EERDERE_VERSIE
    )
    assert list(map_.iterdir()) == []


def test_tweede_release_komt_tussen_niet_uitgebracht_en_de_vorige_versie(tmp_path):
    pad, map_ = _repo(tmp_path, KOP + "\n" + EERDERE_VERSIE, {"801-nieuw.md": "### Nieuw (#801)\n- x\n"})

    breng_uit(pad, map_, "2.6.0", "2026-10-30")

    assert pad.read_text(encoding="utf-8") == (
        KOP + "\n## 2.6.0 — 2026-10-30\n\n### Nieuw (#801)\n- x\n\n" + EERDERE_VERSIE
    )


def test_droge_modus_toont_de_versiesectie_en_schrijft_niets(tmp_path, capsys):
    origineel = KOP + "\n" + OUD_ITEM
    pad, map_ = _repo(tmp_path, origineel, {"797-fragmenten.md": "### Fragmenten (#797)\n- x\n"})

    breng_uit(pad, map_, "2.6.0", "2026-10-30", droog=True)

    uit = capsys.readouterr().out
    assert uit.startswith("## 2.6.0 — 2026-10-30\n\n### Fragmenten (#797)\n- x\n\n### Oud item")
    assert "changelog.d/797-fragmenten.md" in uit
    assert pad.read_text(encoding="utf-8") == origineel
    assert [p.name for p in map_.iterdir()] == ["797-fragmenten.md"]


@pytest.mark.parametrize(
    ("naam", "tekst", "melding"),
    [
        ("fragmenten.md", "### Kop (#1)\n- x\n", "geen geldige naam"),
        ("797-Fragmenten.md", "### Kop (#1)\n- x\n", "geen geldige naam"),
        ("797-fragmenten.txt", "### Kop (#1)\n- x\n", "geen geldige naam"),
        ("797-fragmenten.md", "- alleen een bullet\n", "###-kopje"),
        ("797-fragmenten.md", "### Kop (#1)\n- x\n\n## 2.6.0\n", "kop van niveau 1 of 2"),
    ],
)
def test_ongeldig_fragment_faalt_met_de_bestandsnaam(tmp_path, naam, tekst, melding):
    pad, map_ = _repo(tmp_path, KOP, {naam: tekst})
    with pytest.raises(SystemExit, match=melding):
        breng_uit(pad, map_, "2.6.0", "2026-10-30")
    assert pad.read_text(encoding="utf-8") == KOP


def test_bestaande_versie_faalt(tmp_path):
    pad, map_ = _repo(tmp_path, KOP + "\n" + EERDERE_VERSIE, {"797-x.md": "### X (#797)\n- x\n"})
    with pytest.raises(SystemExit, match=r"al een kop voor 2\.5\.0"):
        breng_uit(pad, map_, "2.5.0", "2026-10-30")
    assert (map_ / "797-x.md").exists()


def test_versie_met_v_faalt(tmp_path):
    pad, map_ = _repo(tmp_path, KOP, {"797-x.md": "### X (#797)\n- x\n"})
    with pytest.raises(SystemExit, match=r"kale X\.Y\.Z"):
        breng_uit(pad, map_, "v2.6.0", "2026-10-30")


def test_zonder_fragmenten_en_oude_items_valt_er_niets_uit_te_brengen(tmp_path):
    pad, map_ = _repo(tmp_path, KOP + "\n" + EERDERE_VERSIE, {})
    with pytest.raises(SystemExit, match="niets uit te brengen"):
        breng_uit(pad, map_, "2.6.0", "2026-10-30")


def test_zonder_kop_niet_uitgebracht_faalt(tmp_path):
    pad, map_ = _repo(tmp_path, "# Changelog\n\n" + EERDERE_VERSIE, {"797-x.md": "### X (#797)\n- x\n"})
    with pytest.raises(SystemExit, match="Niet uitgebracht"):
        breng_uit(pad, map_, "2.6.0", "2026-10-30")


def test_fragmenten_in_de_repo_zijn_geldig():
    # Een fragment met een foute naam of vorm valt hier in de MR op, niet pas bij de release.
    lees_fragmenten(FRAGMENTEN)


def test_release_op_de_echte_changelog_voegt_alleen_regels_toe():
    # De bestaande inhoud van CHANGELOG.md blijft staan; de release zet er alleen de kop en de fragmenten bij.
    origineel = CHANGELOG.read_text(encoding="utf-8")
    fragmenten = [tekst for _, tekst in lees_fragmenten(FRAGMENTEN)] + ["### Proef (#1)\n- x"]

    nieuw, sectie = voeg_samen(origineel, "99.0.0", "2099-01-01", fragmenten)

    diff = difflib.unified_diff(origineel.splitlines(), nieuw.splitlines(), lineterm="", n=0)
    assert not [r for r in diff if r.startswith("-") and not r.startswith("---")]
    assert sectie.startswith("## 99.0.0 — 2099-01-01\n\n")
    assert all(fragment in sectie for fragment in fragmenten)
