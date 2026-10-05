"""De handgemaakte referentielijsten: gedateerd en zonder stille botsingen (#316).

Een dubbele sleutel in een dict-literal overschrijft de eerste zonder fout: zo
ontbrak nhlstenden.nl (#202). Ruff F601 vangt dat alleen bij letterlijk gelijke
sleutels; deze tests lezen de bron zelf en kijken ook over de lijsten heen.
"""

import ast
import inspect
from collections import defaultdict
from datetime import date

import pytest

import data.dashboard as dashboard
import data.instellingen as instellingen
from data.instellingen import ALIASSEN, DOMEINEN, SRAM_ORGS

_LIJSTEN = [(module, naam) for module in (instellingen, dashboard) for naam in module.REFERENTIELIJSTEN]


def _sleutels(module, naam: str) -> list:
    """De sleutels van de dict-literal `naam` zoals ze in de bron staan, dubbele inbegrepen."""
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Assign):
            doel = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            doel = node.target
        else:
            continue
        if isinstance(doel, ast.Name) and doel.id == naam and isinstance(node.value, ast.Dict):
            return [ast.literal_eval(k) for k in node.value.keys if k is not None]
    raise AssertionError(f"{naam} staat niet als dict-literal in {module.__name__}")


@pytest.mark.parametrize(("module", "naam"), _LIJSTEN, ids=lambda x: getattr(x, "__name__", x))
def test_elke_lijst_heeft_een_datum_en_een_bron(module, naam):
    manifest = module.REFERENTIELIJSTEN[naam]
    date.fromisoformat(manifest["bijgewerkt"])
    assert manifest["bron"].strip()
    assert isinstance(getattr(module, naam), dict)


@pytest.mark.parametrize(("module", "naam"), _LIJSTEN, ids=lambda x: getattr(x, "__name__", x))
def test_geen_dubbele_sleutels_in_de_bron(module, naam):
    sleutels = _sleutels(module, naam)
    dubbel = sorted({s for s in sleutels if sleutels.count(s) > 1})
    assert not dubbel, f"{naam}: dubbele sleutels {dubbel}"


def _botsingen(paren) -> dict[str, set[str]]:
    """Waarden (zonder hoofdletters) die naar meer dan één instelling wijzen."""
    naar: dict[str, set[str]] = defaultdict(set)
    for waarde, instelling in paren:
        naar[waarde.lower()].add(instelling)
    return {w: i for w, i in naar.items() if len(i) > 1}


def test_een_domein_hoort_bij_een_instelling():
    assert not _botsingen((d, naam) for naam, doms in DOMEINEN.items() for d in doms)


def test_een_alias_of_sram_naam_hoort_bij_een_instelling():
    # SRAM-korte namen worden aliassen (_apply_sram_mappings): ze delen één naamruimte.
    paren = [*((a, naam) for naam, aliassen in ALIASSEN.items() for a in aliassen), *SRAM_ORGS.items()]
    assert not _botsingen(paren)


def test_elke_sram_instelling_heeft_een_domein():
    assert set(SRAM_ORGS.values()) <= set(DOMEINEN)
