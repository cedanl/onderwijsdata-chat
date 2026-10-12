"""Canonieke selectie (#342): dezelfde selectie in een andere spelling is één identiteit.

De digest conflateert alleen spellingen die aantoonbaar hetzelfde uitvoeren; de
periodeherstelroute herschrijft diezelfde spellingen vóór het filteren, zodat
digest-gelijkheid en uitvoerings-gelijkheid samenvallen.
"""

import pandas as pd

from core.config import CBS_ROW_LIMIT, DUO_ROW_LIMIT
from tools import canoniek


def _d(args: dict, name: str = "query_data") -> str:
    return canoniek.digest(name, args)


# --- plan en digest: sleutelvormen -------------------------------------------


def test_sleutelvolgorde_en_filtervorm_delen_een_digest():
    a = {"data_key": "duo:x:1", "filters": {"GESLACHT": "man"}}
    b = {"filters": {"GESLACHT__in": ["Man"]}, "data_key": "DUO:x:1"}
    assert _d(a) == _d(b)


def test_eq_is_gelijk_aan_expliciete_eq_suffix():
    assert _d({"filters": {"SECTOR__eq": "Techniek"}}) == _d({"filters": {"SECTOR": "techniek"}})


def test_in_lijst_volgorde_en_dubbelen_tellen_niet():
    a = {"filters": {"SECTOR__in": ["b", "a", "a"]}}
    b = {"filters": {"SECTOR__in": ["A", "B"]}}
    assert _d(a) == _d(b)


def test_andere_waarden_geven_een_andere_digest():
    assert _d({"filters": {"SECTOR": "a"}}) != _d({"filters": {"SECTOR": "b"}})


def test_andere_kolom_geeft_een_andere_digest():
    assert _d({"filters": {"GESLACHT": "man"}}) != _d({"filters": {"Geslacht": "man"}})


def test_lege_en_afwezige_argumenten_zijn_dezelfde_aanroep():
    assert _d({"data_key": "duo:x:1", "filters": None, "columns": []}) == _d({"data_key": "duo:x:1"})


def test_max_rows_op_de_default_is_geen_andere_selectie():
    assert _d({"data_key": "k", "max_rows": DUO_ROW_LIMIT}) == _d({"data_key": "k"})
    assert _d({"data_key": "k", "max_rows": 5}) != _d({"data_key": "k"})


def test_dubbel_filter_op_een_kolom_is_de_doorsnede():
    a = {"filters": {"SECTOR": "a", "SECTOR__in": ["a", "b"]}}
    b = {"filters": {"SECTOR": "a"}}
    assert _d(a) == _d(b)


def test_getal_en_tekst_op_een_grens_zijn_gelijk():
    assert _d({"filters": {"JAAR__gte": "2020"}}) == _d({"filters": {"JAAR__gte": 2020}})


# --- plan en digest: periodespellingen ---------------------------------------


def test_periodespellingen_op_studiejaar_delen_een_digest():
    digests = {
        _d({"filters": {"STUDIEJAAR": 2024}}),
        _d({"filters": {"STUDIEJAAR": "2024"}}),
        _d({"filters": {"STUDIEJAAR": "2024/25"}}),
        _d({"filters": {"STUDIEJAAR__in": ["2024/2025"]}}),
    }
    assert len(digests) == 1


def test_cbs_code_en_label_spelling_delen_een_digest():
    assert _d({"filters": {"Perioden": "2024SJ00"}}) == _d({"filters": {"Perioden": "2024/'25"}})
    assert _d({"filters": {"Perioden_label": "2024/'25"}}) == _d({"filters": {"Perioden_label": "2024-2025"}})


def test_kaal_jaartal_op_perioden_blijft_apart():
    # 2024 kan 2024JJ00 (kalenderjaar) bedoelen: geen schooljaar, dus geen conflatie.
    assert _d({"filters": {"Perioden": "2024"}}) != _d({"filters": {"Perioden": "2024SJ00"}})


def test_periodespelling_buiten_periodekolommen_blijft_apart():
    # Op een vrije kolom is "2024/25" een tekstwaarde; alleen periodekolommen worden genormaliseerd.
    assert _d({"filters": {"OPLEIDING": "2024/25"}}) != _d({"filters": {"OPLEIDING": "2024/2025"}})


# --- plan en digest: CBS-laadfilters ------------------------------------------


def test_cbs_spatiering_en_top_delen_een_digest():
    a = {"dataset_id": "85353NED", "filters": {"$filter": "Perioden  eq  '2024SJ00'", "$top": CBS_ROW_LIMIT}}
    b = {"dataset_id": "85353NED", "filters": {"$top": str(CBS_ROW_LIMIT), "$filter": "Perioden eq '2024SJ00'"}}
    assert _d(a, "get_cbs_data") == _d(b, "get_cbs_data")


def test_cbs_spaties_binnen_een_literal_blijven_betekenisvol():
    a = {"dataset_id": "x", "filters": {"$filter": "Gemeente eq 'Den  Haag'"}}
    b = {"dataset_id": "x", "filters": {"$filter": "Gemeente eq 'Den Haag'"}}
    assert _d(a, "get_cbs_data") != _d(b, "get_cbs_data")


def test_cbs_top_op_de_default_is_geen_filter():
    assert canoniek.cbs_digest({"$top": CBS_ROW_LIMIT}) is None
    assert canoniek.cbs_digest({"$filter": "Perioden eq '2024SJ00'"}) is not None


# --- data_key-varianten --------------------------------------------------------


def test_sleutel_normaliseert_prefix_en_kast():
    assert canoniek.sleutel("cbs_85353NED") == canoniek.sleutel("CBS:85353ned") == "cbs:85353ned"
    assert canoniek.sleutel("duo/ingeschrevenenwo:0") == "duo:ingeschrevenenwo:0"


# --- herstel_perioden ----------------------------------------------------------


def _df_studiejaar() -> pd.DataFrame:
    return pd.DataFrame({"STUDIEJAAR": [2022, 2023, 2024], "AANTAL": [10, 20, 30]})


def test_label_spelling_wordt_de_waarde_uit_de_data():
    hersteld, fout = canoniek.herstel_perioden({"STUDIEJAAR": "2023/24"}, _df_studiejaar(), None, volledig=True)
    assert fout is None
    assert hersteld == {"STUDIEJAAR": 2023}


def test_cbs_label_spelling_wordt_het_label_uit_de_data():
    df = pd.DataFrame({"Perioden": ["2023SJ00", "2024SJ00"], "Perioden_label": ["2023/'24", "2024/'25"]})
    hersteld, fout = canoniek.herstel_perioden({"Perioden_label__in": ["2024/25"]}, df, "Perioden", volledig=True)
    assert fout is None
    assert hersteld == {"Perioden_label__in": ["2024/'25"]}


def test_spelling_die_al_in_de_data_staat_blijft_staan():
    hersteld, fout = canoniek.herstel_perioden({"STUDIEJAAR": "2023"}, _df_studiejaar(), None, volledig=True)
    assert fout is None
    assert hersteld == {"STUDIEJAAR": "2023"}


def test_weigering_noemt_de_toegestane_waarden():
    _, fout = canoniek.herstel_perioden({"STUDIEJAAR": "2020/21"}, _df_studiejaar(), None, volledig=True)
    assert fout is not None
    assert "2020/21" in fout
    for waarde in ("2022", "2023", "2024"):
        assert waarde in fout


def test_afgekapte_selectie_weigert_niet():
    # Afwezig in één pagina is niet afwezig in de bron: de 0-rijenmelding legt dat uit.
    hersteld, fout = canoniek.herstel_perioden({"STUDIEJAAR": "2020/21"}, _df_studiejaar(), None, volledig=False)
    assert fout is None
    assert hersteld == {"STUDIEJAAR": "2020/21"}


def test_vrije_kolommen_blijven_ongemoeid():
    df = pd.DataFrame({"OPLEIDING": ["2024/25"], "AANTAL": [1]})
    hersteld, fout = canoniek.herstel_perioden({"OPLEIDING": "2024/2025"}, df, None, volledig=True)
    assert fout is None
    assert hersteld == {"OPLEIDING": "2024/2025"}


# --- gesloten selectie (#343) in het plan ---------------------------------------


def test_selectie_spellingen_delen_een_digest():
    a = {"dataset_id": "x", "selectie": {"dimensies": {"Geslacht": "T001038"}, "periode": ["2024/25"]}}
    b = {"selectie": {"periode": ["2024SJ00"], "dimensies": {"Geslacht": ["T001038"]}}, "dataset_id": "x"}
    assert _d(a, "get_cbs_data") == _d(b, "get_cbs_data")


def test_selectie_bereik_is_volgorde_ongevoelig():
    a = {"dataset_id": "x", "selectie": {"dimensies": {}, "periode": {"van": "2020/21", "tot": "2022/23"}}}
    b = {"dataset_id": "x", "selectie": {"dimensies": {}, "periode": {"van": "2022/23", "tot": "2020/21"}}}
    assert _d(a, "get_cbs_data") == _d(b, "get_cbs_data")


def test_selectie_codelijst_volgorde_telt_niet():
    a = {"dataset_id": "x", "selectie": {"dimensies": {"RegioS": ["PV20", "PV21"]}, "periode": "*"}}
    b = {"dataset_id": "x", "selectie": {"dimensies": {"RegioS": ["PV21", "PV20", "PV20"]}, "periode": "*"}}
    assert _d(a, "get_cbs_data") == _d(b, "get_cbs_data")


def test_andere_selectie_geeft_andere_digest():
    a = {"dataset_id": "x", "selectie": {"dimensies": {"Geslacht": "T001038"}, "periode": "*"}}
    b = {"dataset_id": "x", "selectie": {"dimensies": {"Geslacht": "3000"}, "periode": "*"}}
    assert _d(a, "get_cbs_data") != _d(b, "get_cbs_data")
