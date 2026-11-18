"""N07 met de toolroute (#1017): eerst per instelling aggregeren met query_data, dan koppelen met koppel_data.

SKDB geeft per vestiging een NSE-oordeel en het aantal respondenten, DUO per vestiging een aantal. Het model koppelde
ze in eigen pandas of nam een ongewogen gemiddelde over vestigingen (reaudit N07). Hier gaat alles via tools.dispatch:
query_data (weighted_mean + sum per brin) op SKDB, query_data (sum) op DUO, dan koppel_data op brin; run_analysis komt
er niet aan te pas. Er staat geen data van LCSK in de repo: de getallen zijn verzonnen, de vorm niet.
"""

import json

import pandas as pd
import pytest

import tools
from data import instellingen
from tools import store
from tools.schemas import TOOL_KOPPEL_DATA, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS
from tools.store import KeyMeta

_SKDB = "skdb:opleidingen:n07"
_DUO = "duo:p01hoinges:0"
_GEDEELD = ["21PD", "25DW", "28DN", "30GB", "00IC", "01OE", "02GA", "03EP", "09BM", "21RI", "22OJ", "27UM"]
_AVANS, _CAPABEL, _ZONDER_OORDEEL = "07GR", "30HC", "28DN"

# Per brin de vestigingen als (oordeel, respondenten); None is een vestiging zonder oordeel.
_SKDB_VESTIGINGEN: dict[str, list[tuple[float | None, int]]] = {
    brin: [(3.0 + 0.1 * i, 20 + 10 * i), (3.8 - 0.05 * i, 200 - 7 * i)] for i, brin in enumerate(_GEDEELD)
}
_SKDB_VESTIGINGEN["21PD"] = [(3.5, 100), (4.0, 300)]
_SKDB_VESTIGINGEN[_ZONDER_OORDEEL] = [(None, 40), (None, 12)]
_SKDB_VESTIGINGEN[_AVANS] = [(3.2, 80), (3.6, 20), (None, 15)]
_DUO_VESTIGINGEN = {brin: [30 + i, 5 + i, 12] for i, brin in enumerate([*_GEDEELD, _CAPABEL])}


@pytest.fixture(autouse=True)
def geen_register(monkeypatch):
    monkeypatch.setattr(instellingen, "get_all", lambda: [])


@pytest.fixture
def geen_run_analysis(monkeypatch):
    def weiger(**_kwargs):
        raise AssertionError("run_analysis mag in de route van N07 niet nodig zijn")

    monkeypatch.setitem(tools._HANDLERS, TOOL_RUN_ANALYSIS, weiger)


def _laad() -> None:
    skdb_rijen = [
        {"brin": brin, "vestiging": f"{brin}-{v}", "croho": 30020, "nse_algemeen": s, "nse_respondenten": n}
        for brin, vestigingen in _SKDB_VESTIGINGEN.items()
        for v, (s, n) in enumerate(vestigingen)
    ]
    duo_rijen = [
        {"INSTELLINGSCODE_ACTUEEL": brin, "VESTIGINGSNAAM": f"{brin}-{v}", "AANTAL": aantal}
        for brin, aantallen in _DUO_VESTIGINGEN.items()
        for v, aantal in enumerate(aantallen)
    ]
    store.put(_SKDB, pd.DataFrame(skdb_rijen), KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase"))
    store.put(_DUO, pd.DataFrame(duo_rijen), KeyMeta(bron="duo", dataset="p01hoinges", resource=0))


def _roep(naam: str, args: dict) -> dict:
    uit, _ = tools.dispatch(naam, args)
    return json.loads(uit)


def _met_de_hand(brin: str) -> float | None:
    bruikbaar = [(s, n) for s, n in _SKDB_VESTIGINGEN[brin] if s is not None]
    noemer = sum(n for _, n in bruikbaar)
    return sum(s * n for s, n in bruikbaar) / noemer if noemer else None


def test_n07_aggregeren_per_instelling_en_dan_koppelen(geen_run_analysis):
    _laad()
    skdb = _roep(
        TOOL_QUERY_DATA,
        {
            "data_key": _SKDB,
            "group_by": ["brin"],
            "aggregate": {"nse_algemeen": "weighted_mean", "nse_respondenten": "sum"},
            "weights": {"nse_algemeen": "nse_respondenten"},
        },
    )
    duo = _roep(
        TOOL_QUERY_DATA,
        {"data_key": _DUO, "group_by": ["INSTELLINGSCODE_ACTUEEL"], "aggregate": {"AANTAL": "sum"}},
    )
    uit = _roep(TOOL_KOPPEL_DATA, {"data_key": skdb["data_key"], "andere_key": duo["data_key"], "sleutels": ["brin"]})

    df = store.get(uit["data_key"])
    assert len(df) == 14 and df["brin"].is_unique  # precies één rij per instelling
    assert uit["korrel"] == {"SKDB": "one", "DUO": "one", "koppeling": "one_to_one"}
    rijen = df.set_index("brin")
    assert rijen.loc["21PD", "nse_algemeen"] == pytest.approx(3.875)  # niet 3,75 (ongewogen)
    for brin in [*_GEDEELD, _AVANS]:
        verwacht = _met_de_hand(brin)
        if verwacht is None:
            assert pd.isna(rijen.loc[brin, "nse_algemeen"])
        else:
            assert rijen.loc[brin, "nse_algemeen"] == pytest.approx(verwacht)
    assert rijen.loc[_AVANS, "nse_algemeen"] == pytest.approx((3.2 * 80 + 3.6 * 20) / 100)
    assert rijen.loc["21PD", "AANTAL"] == sum(_DUO_VESTIGINGEN["21PD"])

    assert rijen.loc[_AVANS, "koppelstatus"] == "alleen SKDB" and pd.isna(rijen.loc[_AVANS, "AANTAL"])
    assert rijen.loc[_CAPABEL, "koppelstatus"] == "alleen DUO"
    assert pd.isna(rijen.loc[_CAPABEL, "nse_algemeen"]) and pd.isna(rijen.loc[_CAPABEL, "nse_respondenten"])
    assert rijen.loc[_ZONDER_OORDEEL, "koppelstatus"] == "beide" and pd.isna(rijen.loc[_ZONDER_OORDEEL, "nse_algemeen"])
    assert not (df[["nse_algemeen", "AANTAL"]] == 0).any().any()  # leeg, nooit 0
    assert "many" not in uit.get("waarschuwing", "")
