"""weighted_mean in query_data (#1017): een score per instelling, gewogen naar respondenten.

Het model aggregeerde per instelling in eigen pandas (run_analysis) of nam een ongewogen gemiddelde over vestigingen
(N07). Hier rekent de code som(waarde * gewicht) / som(gewicht) per groep, over rijen met een waarde én een gewicht.
"""

import json
from typing import Any

import pandas as pd
import pytest

import tools
from tools import canoniek, store
from tools.query import _apply_aggregation, query_data
from tools.schemas import TOOL_QUERY_DATA, TOOL_SCHEMAS

_KEY = "test:nse"
_VESTIGINGEN = [
    {"brin": "21PD", "vestiging": "Breda", "s": 3.5, "n": 100},
    {"brin": "21PD", "vestiging": "Tilburg", "s": 4.0, "n": 300},
    {"brin": "25DW", "vestiging": "Utrecht", "s": 3.0, "n": 50},
]
_GEWOGEN: dict[str, Any] = {"group_by": ["brin"], "aggregate": {"s": "weighted_mean"}, "weights": {"s": "n"}}


def _put(rijen: list[dict], key: str = _KEY) -> None:
    store.put(key, pd.DataFrame(rijen), store.KeyMeta(bron="test", dataset=key))


def _per_brin(uit: str, kolom: str = "s") -> dict:
    return {rij["brin"]: rij[kolom] for rij in json.loads(uit)["rijen"]}


# --- 1. Rekenen ------------------------------------------------------------------------------------------------------


def test_het_gewogen_gemiddelde_weegt_naar_het_gewicht_niet_naar_de_vestiging():
    _put(_VESTIGINGEN)
    uit = _per_brin(query_data(_KEY, **_GEWOGEN))
    assert uit["21PD"] == pytest.approx(3.875)  # ongewogen zou 3,75 zijn
    assert uit["25DW"] == pytest.approx(3.0)


def test_weighted_mean_naast_sum_in_een_aanroep():
    _put(_VESTIGINGEN)
    uit = json.loads(
        query_data(_KEY, group_by=["brin"], aggregate={"s": "weighted_mean", "n": "sum"}, weights={"s": "n"})
    )
    rijen = {rij["brin"]: rij for rij in uit["rijen"]}
    assert rijen["21PD"]["s"] == pytest.approx(3.875) and rijen["21PD"]["n"] == 400
    assert rijen["25DW"]["s"] == pytest.approx(3.0) and rijen["25DW"]["n"] == 50
    assert list(store.get(uit["data_key"]).columns) == ["brin", "s", "n"]


def test_apply_aggregation_zonder_weights_blijft_werken():
    df = pd.DataFrame(_VESTIGINGEN)
    agg = _apply_aggregation(df, ["brin"], {"s": "mean"})
    assert agg.set_index("brin")["s"].to_dict() == pytest.approx({"21PD": 3.75, "25DW": 3.0})


# --- 2. Lege waarden -------------------------------------------------------------------------------------------------


def test_een_rij_zonder_waarde_of_gewicht_telt_niet_mee_en_de_noot_zegt_hoeveel():
    _put(
        [
            *_VESTIGINGEN,
            {"brin": "21PD", "vestiging": "zonder score", "s": None, "n": 900},
            {"brin": "21PD", "vestiging": "zonder gewicht", "s": 1.0, "n": None},
            {"brin": "21PD", "vestiging": "onleesbaar gewicht", "s": 1.0, "n": "onbekend"},
        ]
    )
    uit = json.loads(query_data(_KEY, **_GEWOGEN))
    assert _per_brin(json.dumps(uit))["21PD"] == pytest.approx(3.875)
    noot = next(n for n in uit["databewerking"] if "niet meegeteld" in n)
    assert "'s'" in noot and "'n'" in noot and "3 rijen" in noot


def test_een_groep_zonder_bruikbare_rij_is_null_met_noot_nooit_0():
    _put(
        [
            *_VESTIGINGEN,
            {"brin": "30GB", "vestiging": "x", "s": None, "n": 20},
            {"brin": "30GB", "vestiging": "y", "s": 2.0, "n": None},
            {"brin": "07GR", "vestiging": "z", "s": 4.0, "n": 0},  # gewichtssom 0: geen deling door nul
        ]
    )
    uit = json.loads(query_data(_KEY, **_GEWOGEN))
    per_brin = _per_brin(json.dumps(uit))
    assert per_brin["30GB"] is None and per_brin["07GR"] is None
    noot = next(n for n in uit["databewerking"] if "leeg (null)" in n)
    assert "brin=30GB" in noot and "brin=07GR" in noot and "nooit 0" in noot


def test_een_gewicht_0_telt_niet_bij():
    _put([*_VESTIGINGEN, {"brin": "21PD", "vestiging": "leeg", "s": 1.0, "n": 0}])
    assert _per_brin(query_data(_KEY, **_GEWOGEN))["21PD"] == pytest.approx(3.875)


def test_duo_onderdrukte_cellen_tellen_niet_mee_en_zijn_geen_ondergrens():
    key = "duo:nse_test:0"
    rijen = [*_VESTIGINGEN, {"brin": "21PD", "vestiging": "klein", "s": -1, "n": -1}]
    store.put(key, pd.DataFrame(rijen), store.KeyMeta(bron="duo", dataset="nse_test"))
    uit = json.loads(query_data(key, **_GEWOGEN))
    assert _per_brin(json.dumps(uit))["21PD"] == pytest.approx(3.875)
    noten = " ".join(uit["databewerking"])
    assert "het gewogen gemiddelde is berekend zonder die cellen; dat is geen ondergrens" in noten
    assert "ondergrens bij" not in noten and "is daardoor een ondergrens" not in noten
    rij = next(r for r in uit["rijen"] if r["brin"] == "21PD")
    assert rij["s (onderdrukte cellen)"] == 1
    assert any("Dat is geen ondergrens" in n for n in uit["databewerking"])
    assert not any("alleen dat totaal is een ondergrens" in n for n in uit["databewerking"])


# --- 3. Validatie ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "in_melding"),
    [
        ({"group_by": ["brin"], "aggregate": {"s": "weighted_mean"}}, "weights"),
        ({"group_by": ["brin"], "aggregate": {"s": "weighted_mean"}, "weights": {}}, "weights"),
        ({"group_by": ["brin"], "aggregate": {"s": "mean"}, "weights": {"s": "n"}}, "weighted_mean"),
        ({"group_by": ["brin"], "aggregate": {"s": "weighted_mean"}, "weights": {"s": "bestaat_niet"}}, "bestaat_niet"),
        ({"group_by": ["brin"], "aggregate": {"s": "weighted_mean"}, "weights": {"s": "vestiging"}}, "niet numeriek"),
        ({"group_by": ["brin"], "aggregate": {"s": "weighted_mean"}, "weights": {"s": "min"}}, "negatie"),
        ({"group_by": ["brin", "n"], "aggregate": {"s": "weighted_mean"}, "weights": {"s": "n"}}, "group_by"),
        ({"weights": {"s": "n"}}, "aggregate"),
        ({"filters": {"brin": "21PD"}, "weights": {"s": "n"}}, "aggregate"),
    ],
)
def test_een_onbruikbaar_gewicht_is_een_melding_zonder_afgeleide_key(args: dict[str, Any], in_melding: str):
    _put([{**rij, "min": -5 if i == 0 else 5} for i, rij in enumerate(_VESTIGINGEN)])
    voor = store.list_keys()
    uit = query_data(_KEY, **args)
    with pytest.raises(json.JSONDecodeError):
        json.loads(uit)
    assert in_melding in uit
    assert store.list_keys() == voor


def test_weighted_mean_over_een_mutatiekolom_wordt_niet_geweigerd():
    _put([{**rij, "MUTATIE": rij["s"]} for rij in _VESTIGINGEN])
    uit = query_data(_KEY, group_by=["brin"], aggregate={"MUTATIE": "weighted_mean"}, weights={"MUTATIE": "n"})
    assert _per_brin(uit, "MUTATIE")["21PD"] == pytest.approx(3.875)


def test_een_som_over_een_percentage_blijft_geweigerd():
    _put([{**rij, "PERCENTAGE": 10} for rij in _VESTIGINGEN])
    uit = query_data(_KEY, group_by=["brin"], aggregate={"s": "weighted_mean", "PERCENTAGE": "sum"}, weights={"s": "n"})
    assert "betekent niets" in uit


# --- 5. Herkomst -----------------------------------------------------------------------------------------------------


def test_zonder_weights_blijft_de_digest_van_een_bestaande_selectie_gelijk():
    # Vastgelegd vóór #1017: een bewaarde selectie houdt haar key.
    args = ({"JAAR": 2024}, None, ["brin"], {"s": "mean", "n": "sum"})
    assert canoniek.selectie_digest(*args) == "12b14242"
    assert canoniek.selectie_digest(*args, None) == "12b14242"
    assert canoniek.selectie_digest(*args, {}) == "12b14242"


def test_zonder_of_met_lege_weights_dezelfde_key():
    _put(_VESTIGINGEN)
    zonder = json.loads(query_data(_KEY, group_by=["brin"], aggregate={"s": "mean"}))["data_key"]
    leeg = json.loads(query_data(_KEY, group_by=["brin"], aggregate={"s": "mean"}, weights={}))["data_key"]
    assert zonder == leeg == f"{_KEY}:{canoniek.selectie_digest(None, None, ['brin'], {'s': 'mean'})}"


def test_twee_gewichtskolommen_geven_twee_keys_en_de_stap_noemt_het_gewicht():
    _put([{**rij, "m": 1} for rij in _VESTIGINGEN])
    met_n = json.loads(query_data(_KEY, **_GEWOGEN))["data_key"]
    naar_m: dict[str, Any] = {**_GEWOGEN, "weights": {"s": "m"}}
    met_m = json.loads(query_data(_KEY, **naar_m))["data_key"]
    assert met_n != met_m
    meta = store.meta(met_n)
    assert meta is not None and meta.stap is not None
    assert "gewichten" in meta.stap and '"n"' in meta.stap


# --- 7. Schema en dispatch -------------------------------------------------------------------------------------------


def _schema() -> dict:
    return next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_QUERY_DATA)


def test_het_schema_kent_weighted_mean_en_weights():
    schema = _schema()
    eigenschappen = schema["parameters"]["properties"]
    assert "weighted_mean" in eigenschappen["aggregate"]["additionalProperties"]["enum"]
    assert eigenschappen["weights"]["type"] == "object"
    assert eigenschappen["weights"]["additionalProperties"] == {"type": "string"}
    tekst = json.dumps(schema, ensure_ascii=False)
    assert '{"nse_algemeen": "weighted_mean"}' in tekst.replace('\\"', '"')
    assert '{"nse_algemeen": "nse_respondenten"}' in tekst.replace('\\"', '"')


def test_dispatch_geeft_weights_door():
    _put(_VESTIGINGEN)
    uit, _ = tools.dispatch(TOOL_QUERY_DATA, {"data_key": _KEY, **_GEWOGEN})
    assert _per_brin(uit)["21PD"] == pytest.approx(3.875)
