"""De regel van de getalcontrole voor de browser (#1254): één bron, die JavaScript ook leest."""

import json
import re
from pathlib import Path

import pytest

from agent.grounding import getalregel, unverified

_FIXTURE = Path(__file__).parent.parent / "frontend" / "src" / "__tests__" / "fixtures" / "getalregel.json"


def test_de_vitest_fixture_is_de_regel_van_de_server():
    """De frontendtests lezen deze fixture; verandert de regel, draai dan het commando in de melding."""
    assert json.loads(_FIXTURE.read_text(encoding="utf-8")) == getalregel(), (
        "frontend/src/__tests__/fixtures/getalregel.json loopt achter: schrijf hem opnieuw met "
        '`uv run python -c "import json; from agent.grounding import getalregel; '
        'print(json.dumps(getalregel(), ensure_ascii=False, indent=2))"`'
    )


@pytest.mark.parametrize("sleutel", ["getal", "procent", "scheiding"])
def test_de_patronen_gebruiken_alleen_wat_javascript_ook_kent(sleutel):
    patroon = getalregel()[sleutel]
    re.compile(patroon)
    # Benoemde groepen, inline vlaggen, commentaar, \\A en \\Z en bezittelijke kwantoren kent JavaScript niet zo.
    for alleen_python in ("(?P<", "(?#", "(?i", "(?x", "\\A", "\\Z", "*+", "++", "?+"):
        assert alleen_python not in patroon


@pytest.mark.parametrize(
    ("tekst", "getoetst"),
    [("Er zijn 27.135 studenten.", True), ("Dat is 70,6%.", True), ("In 2024/25 waren het er 812.", False)],
)
def test_de_regel_toetst_wat_de_getalcontrole_toetst(tekst, getoetst):
    """Wat de regel aanwijst, is wat unverified zonder bron afkeurt."""
    regel = getalregel()
    getal, procent = re.compile(regel["getal"]), re.compile(regel["procent"])
    laag, hoog = regel["jaren"]

    def telt(m: re.Match) -> bool:
        cijfers = re.sub(regel["scheiding"], "", m.group(1))
        return len(cijfers) >= regel["min_cijfers"] and not laag <= int(cijfers) <= hoog

    aangewezen = bool(procent.search(tekst)) or any(telt(m) for m in getal.finditer(tekst))
    assert aangewezen is getoetst
    assert bool(unverified(tekst, [])) is getoetst
