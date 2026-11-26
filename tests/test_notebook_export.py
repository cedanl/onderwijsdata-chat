"""Het notebook van "Exporteer gesprek" is geldig en draait (#1247).

`tests/fixtures/notebook/gesprek.ipynb` is wat `conversationNotebook` (frontend/src/conversationExport.js) van
`gesprek.json` maakt; vitest (`conversationNotebook.test.js`) faalt als de export ervan afwijkt. Het gesprek draagt de
snippets die tools/snippet.py maakt voor de vraag van `tests/test_readme_voorbeeld.py`. Hier draait het notebook
headless in een echte kernel (nbclient) tegen de bevroren DUO-fixture, zonder netwerk, en geeft het dezelfde tabel
als dat voorbeeld. Alleen de installcel draait niet: die haalt het pakket van internet; de kernel heeft het al.
"""

import ast
import json
import textwrap
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

import tests.test_readme_voorbeeld as readme
from agent.codeverzoek import GEEN_CODE
from scripts.duo_testfixtures import MAP
from tools import store
from tools.snippet import generate

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = _ROOT / "tests" / "fixtures" / "notebook"
_EXPORT_JS = _ROOT / "frontend" / "src" / "conversationExport.js"

# In de kernel leest `duo.load` de bevroren bestanden, zoals de fixture `duo_fixtures` in tests/conftest.py.
_ZONDER_NETWERK = textwrap.dedent(
    f"""\
    import json
    import sys

    import pandas as pd

    sys.path.insert(0, {str(_ROOT)!r})
    from onderwijsbronnen import duo
    from scripts.duo_testfixtures import MAP, bestandsnaam

    _tekst = json.loads((MAP / "tekstkolommen.json").read_text())


    def _load(dataset_id, resource=0, **kwargs):
        naam = bestandsnaam(dataset_id, resource)
        return pd.read_csv(MAP / naam, dtype=dict.fromkeys(_tekst[naam], str))


    duo.load = _load
    """
)


def _bron(cel) -> str:
    return cel["source"] if isinstance(cel["source"], str) else "".join(cel["source"])


def _notebook() -> dict:
    return json.loads((_FIXTURES / "gesprek.ipynb").read_text())


def _code(bron: str) -> str:
    return ast.dump(ast.parse(bron))


def _zet_p02ho1ejrs_in_de_store() -> None:
    store.put(
        readme._KEY,
        pd.read_csv(MAP / "p02ho1ejrs_0.csv.gz"),
        store.KeyMeta(
            bron="duo",
            dataset="p02ho1ejrs",
            resource=0,
            laad=("get_duo_data", {"dataset_id": "p02ho1ejrs", "resource": 0}),
        ),
    )


def test_fixture_is_een_geldig_nbformat_4_notebook():
    nbformat = pytest.importorskip("nbformat", reason="nbformat ontbreekt: uv sync installeert de dev-groep")
    notebook = nbformat.reads((_FIXTURES / "gesprek.ipynb").read_text(), as_version=4)

    nbformat.validate(notebook)
    assert notebook.metadata.kernelspec.name == "python3"


def test_de_zin_bij_een_stap_zonder_code_is_die_van_een_codeverzoek():
    # De frontend dupliceert de zin van #969 letterlijk; deze test houdt ze gelijk.
    assert f"export const GEEN_CODE = '{GEEN_CODE}'" in _EXPORT_JS.read_text()
    assert any(_bron(c).endswith(GEEN_CODE) for c in _notebook()["cells"] if c["cell_type"] == "markdown")


def test_de_codecel_is_de_snippet_die_de_app_voor_de_vraag_maakt():
    _zet_p02ho1ejrs_in_de_store()
    snippet = generate("query_data", readme._VRAAG)
    assert snippet is not None

    code = [_bron(c) for c in _notebook()["cells"] if c["cell_type"] == "code"]
    # Na de installcel: de query_data-stap. De versiekop en de staplabel zijn commentaar en vallen in de AST weg.
    assert _code(code[1]) == _code(snippet) == _code(readme._voorbeeld())


@pytest.mark.usefixtures("duo_fixtures")
def test_het_notebook_draait_en_geeft_de_tabel_van_het_readme_voorbeeld():
    nbformat = pytest.importorskip("nbformat", reason="nbformat ontbreekt: uv sync installeert de dev-groep")
    nbclient = pytest.importorskip("nbclient", reason="nbclient ontbreekt: uv sync installeert de dev-groep")
    from jupyter_client.kernelspec import NoSuchKernel

    namespace: dict = {}
    exec(readme._voorbeeld(), namespace)
    verwacht = namespace["df"]

    notebook = nbformat.reads((_FIXTURES / "gesprek.ipynb").read_text(), as_version=4)
    cellen = notebook.cells
    install = [i for i, c in enumerate(cellen) if c.cell_type == "code" and "%pip install" in c.source]
    assert install == [1], "precies één installcel, direct onder de titel"
    vraag = next(i for i, c in enumerate(cellen) if c.source.startswith("# Stap 2: Data gefilterd"))
    cellen[vraag + 1 : vraag + 1] = [nbformat.v4.new_code_cell('print(df.to_json(orient="split"))')]
    cellen.append(nbformat.v4.new_code_cell('print(result.to_json(orient="split"))'))
    cellen[1] = nbformat.v4.new_code_cell(_ZONDER_NETWERK)

    client = nbclient.NotebookClient(
        notebook, timeout=300, startup_timeout=120, kernel_name="python3", resources={"metadata": {"path": str(_ROOT)}}
    )
    try:
        client.execute()
    except NoSuchKernel as fout:
        pytest.skip(f"geen python3-kernel: {fout}")

    def tabel(cel) -> pd.DataFrame:
        tekst = "".join(o["text"] for o in cel.outputs if o.get("name") == "stdout")
        return pd.read_json(StringIO(tekst), orient="split")

    kolommen = ["STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"]
    df = tabel(cellen[vraag + 1])
    assert list(df["STUDIEJAAR"]) == [2021, 2022, 2023, 2024, 2025]
    assert (df["AANTAL_EERSTEJAARS_INGESCHREVENEN"] > 0).all()
    assert df[kolommen].values.tolist() == verwacht[kolommen].values.tolist()
    # De eigen analyse (run_analysis) rekent op hetzelfde bestand dezelfde aantallen uit.
    assert tabel(cellen[-1])[kolommen].values.tolist() == verwacht[kolommen].values.tolist()
