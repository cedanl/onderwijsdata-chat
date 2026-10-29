"""RIO is een levend register: de aanroep legt de dag vast waarop hij bevroeg (#718)."""

import json
from datetime import date
from unittest.mock import patch

import pytest

from tools import snippet, store
from tools.rio import get_rio_data

_VANDAAG = date.today().isoformat()
_RECORDS = [{"code": "01XX", "volledigeNaam": "Instelling 1"}]
_CATALOG = [{"_rio_resource": "erkenningen", "bron": "Erkenningen", "filters": ["type", "datumGeldigOp"]}]


@pytest.fixture(autouse=True)
def _schone_store():
    store.clear()
    yield
    store.clear()


def _meta(key: str) -> store.KeyMeta:
    known = store.meta(key)
    assert known is not None
    return known


class _Fetch:
    def __init__(self):
        self.aanroepen: list[tuple[str, dict]] = []

    def __call__(self, resource, **params):
        self.aanroepen.append((resource, params))
        return _RECORDS


def _laad(resource: str, filters: dict | None = None, peildag: bool = True) -> tuple[dict, _Fetch]:
    """`peildag=False` doet alsof de resource geen datumGeldigOp kent: in het echte contract van riodata heeft elke
    resource die je kunt opvragen het filter (aangeboden-opleiding-cohorten heeft geen lijst-endpoint)."""
    nep = _Fetch()
    with (
        patch("tools.rio.rio_filters", lambda r: ["type", "datumGeldigOp"] if peildag else ["type"]),
        patch("tools.rio.fetch", nep),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=_CATALOG),
    ):
        return json.loads(get_rio_data(resource, filters)), nep


def test_zonder_eigen_datum_vraagt_de_aanroep_de_stand_van_vandaag():
    _, nep = _laad("erkenningen", {"type": "BEVOEGD_GEZAG"})

    assert nep.aanroepen[0][1]["datumGeldigOp"] == _VANDAAG


def test_de_key_en_het_recept_blijven_die_van_de_filters_van_de_aanroeper():
    """Een herstart haalt het recept opnieuw op: de key mag niet met de dag meeschuiven."""
    result, _ = _laad("erkenningen", {"type": "BEVOEGD_GEZAG"})

    assert result["data_key"] == "rio:erkenningen:type=BEVOEGD_GEZAG"
    assert _meta(result["data_key"]).laad == (
        "get_rio_data",
        {"resource": "erkenningen", "filters": {"type": "BEVOEGD_GEZAG"}},
    )


def test_het_manifest_krijgt_de_dag_als_peilmoment():
    result, _ = _laad("erkenningen")

    known = _meta(result["data_key"])
    assert known.geldig_op == _VANDAAG
    assert known.peilmoment == f"stand van {date.today():%d-%m-%Y}"


def test_een_eigen_datum_van_de_gebruiker_blijft_en_wordt_het_peilmoment():
    result, nep = _laad("erkenningen", {"datumGeldigOp": "2024-01-01"})

    assert nep.aanroepen[0][1]["datumGeldigOp"] == "2024-01-01"
    assert _meta(result["data_key"]).geldig_op == "2024-01-01"
    assert _meta(result["data_key"]).peilmoment == "stand van 01-01-2024"


def test_een_resource_zonder_datumgeldigop_krijgt_het_filter_niet_en_de_laaddatum_als_peilmoment():
    result, nep = _laad("erkenningen", peildag=False)

    assert "datumGeldigOp" not in nep.aanroepen[0][1]
    known = _meta(result["data_key"])
    assert known.geldig_op is None
    assert known.peilmoment == f"opgehaald op {date.today():%d-%m-%Y}"


def test_de_snippet_zet_de_dag_in_de_aanroep_zodat_hij_dezelfde_stand_ophaalt():
    result, _ = _laad("erkenningen", {"type": "BEVOEGD_GEZAG"})

    tekst = "\n".join(snippet._laadregels(result["data_key"]))

    assert f"'datumGeldigOp': '{_VANDAAG}'" in tekst
    assert "'type': 'BEVOEGD_GEZAG'" in tekst
    assert "NB" not in tekst


def test_de_snippet_van_een_resource_zonder_peildag_zegt_dat_de_uitkomst_kan_afwijken():
    result, _ = _laad("erkenningen", peildag=False)

    tekst = "\n".join(snippet._laadregels(result["data_key"]))

    assert "datumGeldigOp'" not in tekst
    assert "# NB: deze RIO-resource kent geen datumGeldigOp" in tekst


def test_een_eigen_datum_staat_maar_een_keer_in_de_snippet():
    result, _ = _laad("erkenningen", {"datumGeldigOp": "2024-01-01"})

    tekst = "\n".join(snippet._laadregels(result["data_key"]))

    assert tekst.count("datumGeldigOp") == 1 and "2024-01-01" in tekst


def test_een_selectie_op_een_rio_bron_herhaalt_de_dag_van_de_bron_in_de_snippet():
    result, _ = _laad("erkenningen")
    bron = result["data_key"]
    store.derive(bron, "rio:erkenningen:sel", store.get(bron).head(1), stap="eerste rij")
    recept = {"afgeleid_van": bron, "tool": "query_data", "args": {"filters": {"code": "01XX"}}}

    tekst = "\n".join(snippet._laadregels("rio:erkenningen:sel", lambda key: recept if key.endswith(":sel") else None))

    assert f"'datumGeldigOp': '{_VANDAAG}'" in tekst
