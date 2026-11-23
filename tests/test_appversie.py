"""Het versielabel van de app (#1105): een release alleen als de omgeving die zegt, anders een ontwikkelversie."""

import subprocess
import tomllib
from pathlib import Path

import pytest

from core import appversie
from core.appversie import app_versie

_WORTEL = Path(__file__).resolve().parent.parent
_PYPROJECT = tomllib.loads((_WORTEL / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
_COMMIT = "7d3488aa0da386a087f6363b3f2ffa40049f604b"


@pytest.fixture(autouse=True)
def _geen_gecachte_commit():
    appversie._werkboom_commit.cache_clear()
    yield
    appversie._werkboom_commit.cache_clear()


def _git(monkeypatch, uitkomst):
    """`git rev-parse HEAD` geeft `uitkomst` (een tekst) of faalt (een uitzondering)."""

    def run(cmd, **kwargs):
        assert cmd[:2] == ["git", "-C"] and cmd[-2:] == ["rev-parse", "HEAD"]
        if isinstance(uitkomst, Exception):
            raise uitkomst
        return subprocess.CompletedProcess(cmd, 0, stdout=uitkomst + "\n", stderr="")

    monkeypatch.setattr(appversie.subprocess, "run", run)


def test_een_release_uit_het_chart_is_het_label(monkeypatch):
    _git(monkeypatch, _COMMIT)
    assert app_versie("2.8.1-rc.3033+406a4f57") == "2.8.1-rc.3033+406a4f57"
    assert app_versie("2.8.0") == "2.8.0"


def test_zonder_release_is_het_label_de_pyprojectversie_met_dev_en_de_korte_commit(monkeypatch):
    _git(monkeypatch, _COMMIT)
    assert app_versie(None) == f"{_PYPROJECT}+dev.7d3488aa"
    assert app_versie("") == f"{_PYPROJECT}+dev.7d3488aa"


def test_zonder_release_en_zonder_commit_blijft_het_label_een_ontwikkelversie(monkeypatch):
    """Een container of tarball zonder .git, of zonder git: nog steeds geen releaselabel."""
    for fout in (
        FileNotFoundError("git"),
        subprocess.CalledProcessError(128, "git"),
        subprocess.TimeoutExpired("git", 2),
    ):
        appversie._werkboom_commit.cache_clear()
        _git(monkeypatch, fout)
        assert app_versie(None) == f"{_PYPROJECT}+dev"


def test_een_ontwikkelversie_is_nooit_gelijk_aan_een_release(monkeypatch):
    _git(monkeypatch, FileNotFoundError("git"))
    assert app_versie(None) != _PYPROJECT
    assert "+dev" in app_versie(None)


def test_de_commit_uit_git_komt_uit_de_werkboom_van_de_app(monkeypatch):
    opgeroepen = []

    def run(cmd, **kwargs):
        opgeroepen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_COMMIT + "\n", stderr="")

    monkeypatch.setattr(appversie.subprocess, "run", run)
    app_versie(None)
    app_versie(None)
    assert len(opgeroepen) == 1  # één keer per proces
    assert opgeroepen[0][2] == str(_WORTEL)
