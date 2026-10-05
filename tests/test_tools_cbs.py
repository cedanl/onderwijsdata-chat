from unittest.mock import patch

from tools.cbs import get_cbs_data


def test_api_exception_returns_error_string():
    with patch("tools.cbs.data", side_effect=Exception("timeout")):
        result = get_cbs_data("85423NED")
    assert "Fout" in result
    assert "timeout" in result


def test_empty_result_returns_helpful_message():
    with patch("tools.cbs.data", return_value=[]):
        result = get_cbs_data("85423NED", filters={"$filter": "Geslacht eq 'X'"})
    assert "Geen rijen gevonden" in result
    assert "get_cbs_dimension" in result


def test_row_limit_applied():
    from core.config import CBS_ROW_LIMIT

    rows = [{"id": i} for i in range(CBS_ROW_LIMIT + 100)]
    with (
        patch("tools.cbs.data", return_value=rows),
        patch("tools.cbs.definitions", return_value={}),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_cbs_data("85423NED")
    import json

    parsed = json.loads(result)
    # Afgekapt is geen totaal: de bron kan meer rijen hebben (#5).
    assert "totaal_rijen" not in parsed
    assert parsed["opgehaalde_rijen"] == CBS_ROW_LIMIT and parsed["volledig"] is False
    assert "data_key" in parsed
    assert parsed["catalogus_titel"] == "85423NED"


def test_truncation_hint_appended_when_limit_reached():
    from core.config import CBS_ROW_LIMIT

    rows = [{"id": i} for i in range(CBS_ROW_LIMIT)]
    with (
        patch("tools.cbs.data", return_value=rows),
        patch("tools.cbs.definitions", return_value={}),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_cbs_data("85423NED")
    import json

    parsed = json.loads(result)
    assert "waarschuwing" in parsed
    assert "Afgekapt" in parsed["waarschuwing"]


def test_catalogus_titel_included_from_catalog():
    rows = [{"id": 1}]
    cbs_entries = [{"_cbs_id": "85423NED", "bron": "MBO; deelnemers naar geslacht en niveau"}]
    with (
        patch("tools.cbs.data", return_value=rows),
        patch("tools.cbs.definitions", return_value={}),
        patch("tools.catalog._cbs", return_value=cbs_entries),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_cbs_data("85423NED")
    import json

    parsed = json.loads(result)
    assert parsed["catalogus_titel"] == "MBO; deelnemers naar geslacht en niveau"


def test_catalogus_titel_falls_back_to_dataset_id():
    rows = [{"id": 1}]
    with (
        patch("tools.cbs.data", return_value=rows),
        patch("tools.cbs.definitions", return_value={}),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_cbs_data("onbekend-id")
    import json

    parsed = json.loads(result)
    assert parsed["catalogus_titel"] == "onbekend-id"


def test_mislukte_dataproperties_staat_in_de_toolresponse():
    # #229: zonder DataProperties ontbreken labels, eenheden en dimensies; dat werd alleen gelogd.
    import json

    with (
        patch("tools.cbs.data", return_value=[{"Perioden": "2024JJ00", "Waarde": 1}]),
        patch("tools.cbs.definitions", side_effect=Exception("timeout")),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        parsed = json.loads(get_cbs_data("85423NED"))
    assert "metadata_ontbreekt" in parsed


def test_gelukte_dataproperties_geeft_geen_metadatamelding():
    import json

    with (
        patch("tools.cbs.data", return_value=[{"Perioden": "2024JJ00", "Waarde": 1}]),
        patch("tools.cbs.definitions", return_value={}),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        parsed = json.loads(get_cbs_data("85423NED"))
    assert "metadata_ontbreekt" not in parsed


_DEFS_85423 = {
    "Geslacht": {"title": "Geslacht", "type": "Dimension"},
    "Perioden": {"title": "Perioden", "type": "TimeDimension"},
    "TotaalIngeschrevenen_1": {"title": "Totaal ingeschrevenen", "type": "Topic"},
}


def test_titel_in_select_wordt_voor_het_request_gemeld_met_de_sleutel():
    # #354: "Totaal ingeschrevenen" faalde pas bij CBS, met een ruwe providerfout.
    with (
        patch("tools.cbs.data") as data,
        patch("tools.cbs.definitions", return_value=_DEFS_85423),
    ):
        result = get_cbs_data("85423NED", filters={"$select": "Perioden,Totaal ingeschrevenen"})
    data.assert_not_called()
    assert "Onbekende kolom in $select" in result
    assert "'Totaal ingeschrevenen' → gebruik 'TotaalIngeschrevenen_1'" in result


def test_verschreven_sleutel_krijgt_de_dichtstbijzijnde_als_alternatief():
    with patch("tools.cbs.data") as data, patch("tools.cbs.definitions", return_value=_DEFS_85423):
        result = get_cbs_data("85423NED", filters={"$select": "TotaalIngeschrevenen"})
    data.assert_not_called()
    assert "gebruik 'TotaalIngeschrevenen_1'" in result


def test_geldige_sleutels_gaan_door_naar_cbs():
    with (
        patch("tools.cbs.data", return_value=[]) as data,
        patch("tools.cbs.definitions", return_value=_DEFS_85423),
    ):
        get_cbs_data("85423NED", filters={"$select": "ID,Perioden,TotaalIngeschrevenen_1"})
    data.assert_called_once()


def test_zonder_dataproperties_geen_selectcontrole():
    # Bronuitval is geen "bestaat niet": dan beslist CBS zelf.
    with (
        patch("tools.cbs.data", return_value=[]) as data,
        patch("tools.cbs.definitions", side_effect=Exception("timeout")),
    ):
        get_cbs_data("85423NED", filters={"$select": "Totaal ingeschrevenen"})
    data.assert_called_once()
