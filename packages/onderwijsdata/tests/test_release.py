"""
Release-test (CBS-06): catalogus en manifest worden uit de *gebouwde* wheel en sdist
gelezen en bij installatie in een schone omgeving, niet uit de editable checkout.
Bouwt met `uv`; overgeslagen als uv ontbreekt.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MANIFEST = json.loads((ROOT / "src/onderwijsdata/data/cbs_manifest.json").read_text(encoding="utf-8"))
UV = shutil.which("uv")

pytestmark = pytest.mark.skipif(UV is None, reason="uv niet beschikbaar")


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    subprocess.run([UV, "build", "--out-dir", str(out)], cwd=ROOT, check=True, capture_output=True, timeout=300)
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _controleer(lees):
    """`lees(naam)` geeft de bytes van een databestand in het artefact."""
    manifest = json.loads(lees("cbs_manifest.json"))
    assert manifest["catalogusrevisie"] == MANIFEST["catalogusrevisie"]
    for naam, b in manifest["bestanden"].items():
        assert _sha(lees(naam)) == b["sha256"], f"{naam} wijkt af van het manifest"
        assert len(json.loads(lees(naam))) == b["records"]


def test_wheel_bevat_catalogus_en_manifest_consistent(dist):
    wheel = next(dist.glob("*.whl"))
    with zipfile.ZipFile(wheel) as z:
        _controleer(lambda n: z.read(f"onderwijsdata/data/{n}"))


def test_sdist_bevat_catalogus_en_manifest_consistent(dist):
    sdist = next(dist.glob("*.tar.gz"))
    with tarfile.open(sdist) as t:
        prefix = next(m.name for m in t.getmembers() if m.name.endswith("src/onderwijsdata/data/cbs_manifest.json"))
        basis = prefix.rsplit("/", 1)[0]
        _controleer(lambda n: t.extractfile(f"{basis}/{n}").read())


def test_schone_installatie_levert_verwachte_packagedata(dist, tmp_path):
    venv = tmp_path / "venv"
    subprocess.run([UV, "venv", str(venv)], check=True, capture_output=True)
    py = venv / "bin" / "python"
    wheel = next(dist.glob("*.whl"))
    subprocess.run([UV, "pip", "install", "--python", str(py), str(wheel)], check=True, capture_output=True, timeout=300)
    code = (
        "import onderwijsdata as o, json, pathlib;"
        "m=o.catalog_manifest();"
        "print(json.dumps({'consistent': m['consistent'], 'revisie': m['catalogusrevisie'],"
        " 'aantal': m['aantal'], 'pad': str(pathlib.Path(o.__file__).resolve()),"
        " 'rec': o.get_dataset('cbs:85423NED')['meetwaarden'][0]['key']}))"
    )
    # andere cwd: de editable checkout mag niet meespelen
    res = subprocess.run([str(py), "-c", code], cwd=tmp_path, check=True, capture_output=True, text=True)
    info = json.loads(res.stdout)
    assert info["consistent"] is True
    assert info["revisie"] == MANIFEST["catalogusrevisie"]
    assert info["aantal"] == MANIFEST["aantallen"]["breed"]
    assert info["rec"] == "TotaalIngeschrevenen_1"
    assert str(ROOT) not in info["pad"] and "site-packages" in info["pad"]
