import json

import pandas as pd
import pytest

from tools import store
from tools.csv_export import naar_csv
from tools.query import query_data


def _put(key: str, data: list[dict]) -> None:
    store.put(key, pd.DataFrame(data), store.KeyMeta(bron="test", dataset=key))


def test_no_filters_returns_all_rows():
    _put("test:df", [{"A": "1"}, {"A": "2"}, {"A": "3"}])
    result = query_data("test:df")
    assert '"totaal_rijen":3' in result


def test_filter_exact_match():
    _put("test:df", [{"Leerweg": "Voltijd"}, {"Leerweg": "Deeltijd"}])
    result = query_data("test:df", filters={"Leerweg": "Voltijd"})
    assert '"totaal_rijen":1' in result
    assert "Voltijd" in result


def test_filter_case_insensitive():
    _put("test:df", [{"Sector": "Techniek"}, {"Sector": "Zorg"}])
    result = query_data("test:df", filters={"Sector": "techniek"})
    assert '"totaal_rijen":1' in result


def test_column_selection():
    _put("test:df", [{"A": "1", "B": "2"}, {"A": "3", "B": "4"}])
    result = query_data("test:df", columns=["A"])
    assert '"A"' in result
    assert '"B"' not in result


def test_missing_column_returns_error():
    _put("test:df", [{"A": "1"}])
    result = query_data("test:df", columns=["Bestaat_niet"])
    assert "niet gevonden" in result.lower() or "Bestaat_niet" in result


def test_missing_filter_column_returns_error():
    _put("test:df", [{"A": "1"}])
    result = query_data("test:df", filters={"Bestaat_niet": "x"})
    assert "bestaat niet" in result.lower() or "Bestaat_niet" in result


def test_unknown_data_key_returns_error():
    result = query_data("bestaat:niet")
    assert "Geen data gevonden" in result


def test_adaptive_cap_adds_warning():
    # 100 kolommen × 200 rijen > 6000 cellen → cap + waarschuwing
    wide_rows = [{f"k{i}": str(i) for i in range(100)} for _ in range(200)]
    _put("test:wide", wide_rows)
    result = query_data("test:wide")
    assert "waarschuwing" in result.lower() or "rijen" in result


def test_max_rows_respected():
    # Adaptieve cap heeft een vloer van 50; gebruik max_rows > 50 om de limiet te testen.
    _put("test:df", [{"A": str(i)} for i in range(200)])
    result = query_data("test:df", max_rows=60)
    import json

    data = json.loads(result)
    assert len(data["rijen"]) == 60


# --- Fix #39: range-filter operators ---


def test_filter_gte():
    _put("test:df", [{"JAAR": "2020"}, {"JAAR": "2021"}, {"JAAR": "2022"}])
    result = query_data("test:df", filters={"JAAR__gte": "2021"})
    import json

    data = json.loads(result)
    assert data["totaal_rijen"] == 2
    jaren = [r["JAAR"] for r in data["rijen"]]
    assert "2021" in jaren
    assert "2022" in jaren
    assert "2020" not in jaren


def test_filter_lte():
    _put("test:df", [{"JAAR": "2020"}, {"JAAR": "2021"}, {"JAAR": "2022"}])
    result = query_data("test:df", filters={"JAAR__lte": "2021"})
    import json

    data = json.loads(result)
    assert data["totaal_rijen"] == 2
    jaren = [r["JAAR"] for r in data["rijen"]]
    assert "2020" in jaren
    assert "2021" in jaren
    assert "2022" not in jaren


def test_filter_in():
    _put("test:df", [{"JAAR": "2020"}, {"JAAR": "2021"}, {"JAAR": "2022"}, {"JAAR": "2023"}])
    result = query_data("test:df", filters={"JAAR__in": ["2021", "2023"]})
    import json

    data = json.loads(result)
    assert data["totaal_rijen"] == 2
    jaren = {r["JAAR"] for r in data["rijen"]}
    assert jaren == {"2021", "2023"}


def test_filter_unknown_operator_returns_error():
    _put("test:df", [{"JAAR": "2020"}])
    result = query_data("test:df", filters={"JAAR__between": "2020"})
    assert "between" in result.lower() or "onbekende operator" in result.lower()


def test_filter_numeric_comparison():
    _put("test:df", [{"WAARDE": "10"}, {"WAARDE": "20"}, {"WAARDE": "5"}])
    result = query_data("test:df", filters={"WAARDE__gte": "10"})
    import json

    data = json.loads(result)
    assert data["totaal_rijen"] == 2


def test_filter_range_missing_column_returns_error():
    _put("test:df", [{"A": "1"}])
    result = query_data("test:df", filters={"BESTAAT_NIET__gte": "5"})
    assert "bestaat niet" in result.lower() or "BESTAAT_NIET" in result


# --- group_by / aggregate ---


def test_groupby_sum():
    _put(
        "test:agg",
        [
            {"JAAR": "2021", "INSTELLING": "VU", "AANTAL": 100},
            {"JAAR": "2021", "INSTELLING": "VU", "AANTAL": 200},
            {"JAAR": "2022", "INSTELLING": "VU", "AANTAL": 150},
        ],
    )
    result = json.loads(
        query_data(
            "test:agg",
            group_by=["JAAR"],
            aggregate={"AANTAL": "sum"},
        )
    )
    assert result["totaal_rijen"] == 2
    rows = {r["JAAR"]: r["AANTAL"] for r in result["rijen"]}
    assert rows["2021"] == 300
    assert rows["2022"] == 150


def test_groupby_mean():
    _put(
        "test:agg",
        [
            {"CAT": "A", "VAL": 10},
            {"CAT": "A", "VAL": 20},
            {"CAT": "B", "VAL": 30},
        ],
    )
    result = json.loads(
        query_data(
            "test:agg",
            group_by=["CAT"],
            aggregate={"VAL": "mean"},
        )
    )
    rows = {r["CAT"]: r["VAL"] for r in result["rijen"]}
    assert rows["A"] == pytest.approx(15.0)
    assert rows["B"] == pytest.approx(30.0)


def test_groupby_multiple_agg_functions():
    _put(
        "test:agg",
        [
            {"G": "X", "A": 10, "B": 5},
            {"G": "X", "A": 20, "B": 15},
        ],
    )
    result = json.loads(
        query_data(
            "test:agg",
            group_by=["G"],
            aggregate={"A": "sum", "B": "max"},
        )
    )
    assert result["rijen"][0]["A"] == 30
    assert result["rijen"][0]["B"] == 15


def test_groupby_string_numbers_coerced():
    _put(
        "test:agg",
        [
            {"JAAR": "2021", "AANTAL": "100"},
            {"JAAR": "2021", "AANTAL": "200"},
        ],
    )
    result = json.loads(
        query_data(
            "test:agg",
            group_by=["JAAR"],
            aggregate={"AANTAL": "sum"},
        )
    )
    assert result["rijen"][0]["AANTAL"] == 300


def test_groupby_with_filters():
    _put(
        "test:agg",
        [
            {"JAAR": "2021", "TYPE": "bachelor", "N": 10},
            {"JAAR": "2021", "TYPE": "master", "N": 5},
            {"JAAR": "2022", "TYPE": "bachelor", "N": 20},
        ],
    )
    result = json.loads(
        query_data(
            "test:agg",
            filters={"TYPE": "bachelor"},
            group_by=["JAAR"],
            aggregate={"N": "sum"},
        )
    )
    assert result["totaal_rijen"] == 2
    rows = {r["JAAR"]: r["N"] for r in result["rijen"]}
    assert rows["2021"] == 10
    assert rows["2022"] == 20


def test_groupby_without_aggregate_returns_error():
    _put("test:agg", [{"A": "1", "B": 2}])
    result = query_data("test:agg", group_by=["A"])
    assert "aggregate" in result.lower()


def test_aggregate_without_groupby_returns_error():
    _put("test:agg", [{"A": "1", "B": 2}])
    result = query_data("test:agg", aggregate={"B": "sum"})
    assert "group_by" in result.lower()


def test_groupby_invalid_column_returns_error():
    _put("test:agg", [{"A": "1", "B": 2}])
    result = query_data("test:agg", group_by=["NOPE"], aggregate={"B": "sum"})
    assert "NOPE" in result


def test_groupby_invalid_agg_function_returns_error():
    _put("test:agg", [{"A": "1", "B": 2}])
    result = query_data("test:agg", group_by=["A"], aggregate={"B": "median"})
    assert "median" in result.lower()


def test_aggregation_does_not_mutate_store():
    _put(
        "test:mut",
        [
            {"JAAR": "2021", "AANTAL": "100"},
            {"JAAR": "2022", "AANTAL": "200"},
        ],
    )
    query_data("test:mut", group_by=["JAAR"], aggregate={"AANTAL": "sum"})
    original = store.get("test:mut")
    assert not pd.api.types.is_numeric_dtype(original["AANTAL"])


def test_different_filters_produce_different_result_keys():
    _put(
        "test:dk",
        [
            {"TYPE": "bachelor", "N": 10},
            {"TYPE": "master", "N": 20},
        ],
    )
    r1 = json.loads(query_data("test:dk", filters={"TYPE": "bachelor"}))
    r2 = json.loads(query_data("test:dk", filters={"TYPE": "master"}))
    assert r1["data_key"] != r2["data_key"]
    assert r1["rijen"][0]["N"] == 10
    df2 = store.get(r2["data_key"])
    assert df2.iloc[0]["N"] == 20


def test_leeg_filterresultaat_geeft_melding_en_suggesties():
    """Een filter zonder treffers moet het model op weg helpen, niet zwijgen."""
    df = pd.DataFrame(
        {
            "INSTELLINGSNAAM_ACTUEEL": ["Vrije Universiteit Amsterdam", "Universiteit Utrecht"],
            "STUDIEJAAR": [2023, 2024],
            "AANTAL": [10, 20],
        }
    )
    store.put("duo:test:leeg", df, store.KeyMeta(bron="duo", dataset="test:leeg"))

    result = json.loads(
        query_data("duo:test:leeg", filters={"INSTELLINGSNAAM_ACTUEEL": "Vrije Universitiet Amsterdam"})
    )

    assert result["totaal_rijen"] == 0
    assert "melding" in result
    assert "Vrije Universiteit Amsterdam" in result["suggesties"]["INSTELLINGSNAAM_ACTUEEL"]


def test_leeg_filterresultaat_geeft_bereik_bij_numeriek_filter():
    df = pd.DataFrame({"STUDIEJAAR": [2021, 2022], "AANTAL": [1, 2]})
    store.put("duo:test:leeg-numeriek", df, store.KeyMeta(bron="duo", dataset="test:leeg-numeriek"))

    result = json.loads(query_data("duo:test:leeg-numeriek", filters={"STUDIEJAAR__gte": 2030}))

    assert result["totaal_rijen"] == 0
    assert "2021" in result["suggesties"]["STUDIEJAAR"]


def test_gevuld_filterresultaat_heeft_geen_suggesties():
    df = pd.DataFrame({"NAAM": ["a", "b"], "AANTAL": [1, 2]})
    store.put("duo:test:gevuld", df, store.KeyMeta(bron="duo", dataset="test:gevuld"))

    result = json.loads(query_data("duo:test:gevuld", filters={"NAAM": "a"}))

    assert result["totaal_rijen"] == 1
    assert "suggesties" not in result


def test_aggregation_filters_duo_sentinel_minus_one():
    """DUO sentinel -1 (empty/n.a.) should not count toward sums."""
    df = pd.DataFrame(
        {
            "groep": ["A", "A", "B", "B", "B"],
            "aantal": [100, -1, 50, 60, -1],  # -1 is privacy/empty sentinel in DUO
        }
    )
    store.put("duo:test:sentinels", df, store.KeyMeta(bron="duo", dataset="test:sentinels"))

    result = json.loads(query_data("duo:test:sentinels", group_by=["groep"], aggregate={"aantal": "sum"}))

    # Verify sentinels were filtered: A→100 (not 99), B→110 (not 109)
    rows = {row["groep"]: row["aantal"] for row in result["rijen"]}
    assert rows["A"] == 100, "DUO sentinel -1 should not be counted"
    assert rows["B"] == 110, "DUO sentinel -1 should not be counted"

    # Verify databewerking notes were generated
    assert "databewerking" in result
    assert any("sentinel" in note.lower() for note in result["databewerking"])


def test_volledig_onderdrukte_groep_is_geen_nul():
    """Testaudit L4: ONBEKEND=[-1,-1] werd '0'; onderdrukt is niet nul (#394)."""
    df = pd.DataFrame(
        {
            "GESLACHT": ["ONBEKEND", "ONBEKEND", "MAN", "VROUW", "VROUW", "ANDERS"],
            "AANTAL": [-1, -1, 12, 0, -1, 0],
        }
    )
    store.put("duo:test:onderdrukt", df, store.KeyMeta(bron="duo", dataset="test:onderdrukt"))

    result = json.loads(query_data("duo:test:onderdrukt", group_by=["GESLACHT"], aggregate={"AANTAL": "sum"}))

    rows = {row["GESLACHT"]: row["AANTAL"] for row in result["rijen"]}
    assert rows["ONBEKEND"] is None  # volledig onderdrukt: niet vast te stellen
    assert rows["MAN"] == 12
    assert rows["VROUW"] == 0  # gemengd: echte 0 plus onderdrukte cel, ondergrens
    assert rows["ANDERS"] == 0  # echte bronwaarde 0 blijft 0
    assert any("ONBEKEND" in noot and "onderdrukt" in noot for noot in result["databewerking"])


def test_volledig_onderdrukte_groep_blijft_leeg_in_store_en_csv():
    """Grafiek, KPI en CSV lezen de store: daar moet de groep leeg zijn, geen 0 (#394)."""
    df = pd.DataFrame({"JAAR": [2022, 2023, 2023], "AANTAL": [10, -1, -1]})
    store.put("duo:test:kpi", df, store.KeyMeta(bron="duo", dataset="test:kpi"))
    key = json.loads(query_data("duo:test:kpi", group_by=["JAAR"], aggregate={"AANTAL": "sum"}))["data_key"]

    assert store.get(key)["AANTAL"].isna().tolist() == [False, True]
    csv = naar_csv(key)
    assert csv is not None and csv.splitlines()[-1] == "2023;"


def test_gehele_aantallen_komen_als_gehele_getallen_terug():
    """Door de -1-maskering wordt een telkolom float: 4147.0 belandde zo in het antwoord (#222)."""
    rijen = [{"JAAR": 2024, "AANTAL": 4147}, {"JAAR": 2025, "AANTAL": -1}, {"JAAR": 2025, "PCT": 9.55}]
    store.put("duo:x:0", pd.DataFrame(rijen), store.KeyMeta(bron="duo", dataset="x"))
    rijen = json.loads(query_data("duo:x:0", columns=["JAAR", "AANTAL", "PCT"]))["rijen"]
    assert rijen[0]["AANTAL"] == 4147 and isinstance(rijen[0]["AANTAL"], int)
    assert rijen[1]["AANTAL"] is None  # onderdrukte cel: null, geen NaN (ongeldige JSON)
    assert rijen[2]["PCT"] == 9.55


def test_prognose_aantallen_afgerond_op_hele_personen():
    """Audit 11: '896 098,92 leerlingen' — een prognose heeft geen decimale precisie (#247)."""
    store.put(
        "duo:voprognoses:0",
        pd.DataFrame([{"JAAR": 2030, "AANTAL": 896098.92}]),
        store.KeyMeta(bron="duo", dataset="voprognoses"),
    )
    result = json.loads(query_data("duo:voprognoses:0"))
    assert result["rijen"] == [{"JAAR": 2030, "AANTAL": 896099}]
    assert any("afgerond" in noot for noot in result["databewerking"])


def test_decimalen_buiten_prognoses_blijven_staan():
    store.put("duo:x:0", pd.DataFrame([{"JAAR": 2030, "AANTAL": 12.5}]), store.KeyMeta(bron="duo", dataset="x"))
    assert json.loads(query_data("duo:x:0"))["rijen"] == [{"JAAR": 2030, "AANTAL": 12.5}]
