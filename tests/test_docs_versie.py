"""De versieregel van de documentatie komt uit pyproject.toml en staat op de startpagina en op "Over" (audit G2)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "docs_versie.py"


def test_het_versiebestand_loopt_niet_achter_op_pyproject():
    klaar = subprocess.run([sys.executable, str(SCRIPT), "--controle"], capture_output=True, text=True, check=False)

    assert klaar.returncode == 0, klaar.stderr


def test_de_versieregel_staat_op_de_startpagina_en_op_over():
    for pagina in ("docs/index.md", "docs/product/over.md"):
        assert '--8<-- "docs/.versie.md"' in (ROOT / pagina).read_text(encoding="utf-8"), pagina


def test_de_docs_workflow_schrijft_de_versieregel_voor_de_build():
    workflow = (ROOT / ".github/workflows/docs.yml").read_text(encoding="utf-8")

    assert workflow.index("scripts/docs_versie.py") < workflow.index("zensical build")
