"""De metamorfe relaties (#1263) als tests: elke relatie uit relaties.py houdt op de bevroren fixtures."""

import pytest

from .relaties import RELATIES, Relatie


def _param(relatie: Relatie):
    if relatie.breekt:
        return pytest.param(relatie, id=relatie.naam, marks=pytest.mark.xfail(reason=relatie.breekt, strict=True))
    return pytest.param(relatie, id=relatie.naam)


@pytest.mark.parametrize("relatie", [_param(r) for r in RELATIES])
def test_relatie_houdt(relatie: Relatie):
    relatie()


def test_elke_relatie_uit_de_tabel_heeft_een_test_op_duo_en_op_cbs():
    """De relaties uit #1263 dekken DUO en CBS; Fusie heeft een bron die omrekent en een die dat niet doet."""
    bronnen: dict[str, set[str]] = {}
    for r in RELATIES:
        bronnen.setdefault(r.soort, set()).add(r.bron)
    for soort in (
        "Delen en totaal",
        "Sectoren en landelijk",
        "Reeks en los jaar",
        "Volgorde",
        "Verschil",
        "Onderdrukte cel",
    ):
        assert {"duo", "cbs"} <= bronnen[soort], (soort, bronnen.get(soort))
    assert {"duo", "duo-xbrl"} <= bronnen["Fusie"], bronnen["Fusie"]
    assert {r.tool for r in RELATIES} >= {"query_data", "compute_kpi", "get_maat", "koppel_data"}
