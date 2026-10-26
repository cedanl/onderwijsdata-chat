"""De afspraken over toolgrenzen heen (#701): data_key, metadata en gesloten invoer.

test_tool_schema_contract.py bewaakt dat schema, prompt en handlersignatuur hetzelfde zeggen. Hier gaat het om wat
tussen de tools doorgegeven wordt: een data_key uit de ene tool werkt in de volgende, de herkomst reist mee, en een
parameter buiten het schema komt als nette fout terug in plaats van als crash. Alles zonder netwerk of model.
"""

import json
import re

import pandas as pd
import pytest

from tools import _HANDLERS, dispatch, fouten, store
from tools.schemas import TOOL_SCHEMAS
from tools.store import KeyMeta

_GEHEIM = "geheime-waarde-9f3c"
_BRON_KEY = "duo:keten"


@pytest.fixture(autouse=True)
def _schone_store():
    store.clear()
    yield
    store.clear()


@pytest.fixture
def bron_key() -> str:
    df = pd.DataFrame(
        {
            "JAAR": [2021, 2021, 2022, 2022, 2023, 2023],
            "OPLEIDINGSVORM": ["VT", "DT"] * 3,
            "AANTAL": [10, 5, 12, 6, 14, 7],
        }
    )
    store.put(_BRON_KEY, df, KeyMeta(bron="duo", dataset="keten", volledig=True))
    return _BRON_KEY


def _json(result: str) -> dict:
    return json.loads(result)


def test_de_keten_query_kpi_grafiek_werkt_op_een_data_key(bron_key):
    """Eén data_key loopt van filter via aggregatie naar KPI en grafiek, zonder dat een stap een andere key nodig heeft."""
    result, _ = dispatch(
        "query_data",
        {"data_key": bron_key, "group_by": ["JAAR"], "aggregate": {"AANTAL": "sum"}},
    )
    afgeleid = _json(result)["data_key"]

    assert afgeleid != bron_key
    assert store.get(afgeleid) is not None

    kpi, _ = dispatch("compute_kpi", {"data_key": afgeleid, "value_column": "AANTAL", "metric": "last"})
    assert fouten.code(kpi) is None, kpi
    assert _json(kpi)["raw"] == 21  # 2023: 14 + 7
    assert _json(kpi)["bron"]["data_key"] == afgeleid  # het getal wijst terug naar de key waarop het rust

    plot, figuur = dispatch(
        "create_plot", {"data_key": afgeleid, "x": "JAAR", "y": "AANTAL", "title": "Aantal per jaar"}
    )
    assert fouten.code(plot) is None, plot
    assert figuur is not None


def test_de_herkomst_reist_mee_over_toolgrenzen(bron_key):
    result, _ = dispatch("query_data", {"data_key": bron_key, "filters": {"OPLEIDINGSVORM": "VT"}})
    afgeleid = _json(result)["data_key"]

    meta = store.meta(afgeleid)
    assert meta is not None
    assert meta.afgeleid_van == bron_key
    assert meta.bron == "duo"


@pytest.mark.parametrize("variant", ["DUO:keten", "duo_keten", "duo/keten"])
def test_een_variant_van_de_data_key_wordt_aan_de_ingang_canoniek(bron_key, variant):
    result, _ = dispatch("query_data", {"data_key": variant})

    assert _json(result)["data_key"] == bron_key


@pytest.mark.parametrize("naam", sorted(_HANDLERS))
def test_een_parameter_buiten_het_schema_geeft_een_toolfout_zonder_de_waarde(naam):
    """dispatch() doet handler(**tool_input): een onbekende parameter mag nooit de loop breken of de waarde teruggeven."""
    result, _ = dispatch(naam, {"bestaat_niet": _GEHEIM})

    assert fouten.code(result) == "toolfout", result
    assert _GEHEIM not in result


# Een geldige waarde voor wat de tool vóór de key controleert: een script dat data leest, een toegestane maat.
_GELDIGE_INVOER = {"code": "result = len(df)"}


def _invoer_met_onbekende_key(parameters: dict) -> dict:
    invoer = {}
    for naam in parameters.get("required", []):
        spec = parameters["properties"][naam]
        invoer[naam] = _GELDIGE_INVOER.get(naam) or (spec.get("enum") or ["x"])[0]
    return invoer | {"data_key": "duo:bestaat_niet"}


@pytest.mark.parametrize("naam", sorted(_HANDLERS))
def test_een_onbekende_key_geeft_overal_dezelfde_foutcode(naam):
    parameters = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == naam)["function"]["parameters"]
    if "data_key" not in parameters["properties"]:
        pytest.skip(f"{naam} neemt geen data_key")

    result, _ = dispatch(naam, _invoer_met_onbekende_key(parameters))

    assert fouten.code(result) == "onbekende_data_key", f"{naam}: {result[:200]}"


def test_elke_data_key_in_het_schema_is_een_string():
    """Een tool met een ander type voor data_key breekt de keten stilletjes, ook als de handler het slikt."""
    afwijkend = [
        (s["function"]["name"], param)
        for s in TOOL_SCHEMAS
        for param, spec in s["function"]["parameters"]["properties"].items()
        if re.fullmatch(r"(andere_)?data_key", param) and spec.get("type") != "string"
    ]

    assert not afwijkend, f"data_key is geen string in: {afwijkend}"
