"""Het voorbeeld onder "Reproduceerbare analyses" in README.md draait en is wat de app maakt (#848).

Het oude voorbeeld filterde op kolommen die p02ho1ejrs niet heeft (OPLEIDINGSVORM, AANTAL_INGESCHREVENEN) en zocht
een opleiding in ONDERDEEL, waar sectoren staan. Nu is het de snippet die tools/snippet.py voor dezelfde vraag maakt,
zonder de versiekop (die verschuift met elke riodata-versie), en draait het tegen de bevroren DUO-fixture. Ruff
formatteert de codeblokken in README.md, dus de vergelijking gaat over de code (de AST), niet over aanhalingstekens of
regelafbreking.
"""

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from scripts.duo_testfixtures import MAP
from tools import store
from tools.snippet import generate

_README = Path(__file__).resolve().parent.parent / "README.md"
_KEY = "duo:p02ho1ejrs:0"
# "Hoeveel eerstejaars hbo-studenten kozen per studiejaar voor techniek?"
_VRAAG = {
    "data_key": _KEY,
    "filters": {"ONDERDEEL": "TECHNIEK"},
    "group_by": ["STUDIEJAAR"],
    "aggregate": {"AANTAL_EERSTEJAARS_INGESCHREVENEN": "sum"},
}


def _voorbeeld() -> str:
    sectie = _README.read_text().split("## Reproduceerbare analyses", 1)[1].split("\n## ", 1)[0]
    blok = re.search(r"```python\n(.*?)```", sectie, re.DOTALL)
    assert blok, "geen python-voorbeeld onder 'Reproduceerbare analyses' in README.md"
    return blok.group(1)


def _code(bron: str) -> str:
    return ast.dump(ast.parse(bron))


def test_readme_voorbeeld_is_de_snippet_van_de_app():
    store.put(
        _KEY,
        pd.read_csv(MAP / "p02ho1ejrs_0.csv.gz"),
        store.KeyMeta(
            bron="duo",
            dataset="p02ho1ejrs",
            resource=0,
            laad=("get_duo_data", {"dataset_id": "p02ho1ejrs", "resource": 0}),
        ),
    )
    snippet = generate("query_data", _VRAAG)
    assert snippet is not None
    # De versiekop is commentaar en valt in de AST weg.
    assert _code(_voorbeeld()) == _code(snippet)


@pytest.mark.usefixtures("duo_fixtures")
def test_readme_voorbeeld_draait_tegen_de_duo_fixture():
    namespace: dict = {}
    exec(_voorbeeld(), namespace)

    df = namespace["df"]
    assert list(df["STUDIEJAAR"]) == [2021, 2022, 2023, 2024, 2025]
    assert (df["AANTAL_EERSTEJAARS_INGESCHREVENEN"] > 0).all()
