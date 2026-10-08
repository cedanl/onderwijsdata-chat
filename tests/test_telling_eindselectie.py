"""De onder- en bovengrens horen bij de selectie waarop het antwoord rust, niet bij de verkenning (#414).

CH-07: ROC Midden Nederland = 17.341, zonder onderdrukte cellen; daaronder stond toch
"Ondergrens", van een eerdere, bredere selectie (provincie Utrecht). De selectie waarop
het antwoord rust is die waarvan de getallen in de tekst staan: dezelfde koppeling als
de citaties (#365). Een eigen berekening (run_analysis) erft de status van wat ze las.
"""

import json

import pandas as pd
import pytest

from agent.telling import met_telling, telling_blok
from tools import duo, store
from tools.analysis import run_analysis
from tools.csv_export import naar_csv
from tools.kpi import compute_kpi
from tools.store import KeyMeta

_BRON = "duo:p01mboinschr:0"


@pytest.fixture(autouse=True)
def _bron():
    store.clear()
    store.put(_BRON, pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p01mboinschr"))
    yield
    store.clear()


def _selectie(naam: str, aantallen: list[int], onderdrukt: int = 0) -> str:
    """Een afgeleide key zoals query_data hem maakt, met `onderdrukt` cellen met -1."""
    key = f"{_BRON}:{naam}"
    store.derive(_BRON, key, pd.DataFrame({"JAAR": [2023] * len(aantallen), "AANTAL": aantallen}))
    duo.record_sentinel_cells(key, pd.DataFrame({"AANTAL": [1] * onderdrukt + [0] * (len(aantallen) - onderdrukt)}))
    return key


def _analyse(code: str, key: str) -> str:
    """Het toolresultaat van run_analysis; deze scripts maken geen grafiek."""
    uit = run_analysis(code=code, data_key=key)
    assert isinstance(uit, str)
    return uit


def _csv(key: str) -> str:
    csv = naar_csv(key)
    assert csv is not None
    return csv


def _query(key: str) -> str:
    """Het toolresultaat van query_data voor deze selectie: data_key plus de rijen."""
    return json.dumps({"data_key": key, "rijen": store.get(key).to_dict(orient="records")})


def test_verkenning_met_onderdrukking_en_eindselectie_zonder_geeft_geen_ondergrens():
    utrecht = _query(_selectie("utrecht", [52000, 9000], onderdrukt=1))
    roc = _query(_selectie("roc", [17341]))

    blok = telling_blok([utrecht, roc], "ROC Midden Nederland had 17.341 inschrijvingen.")

    assert "Ondergrens" not in blok


def test_verkenning_zonder_onderdrukking_en_eindselectie_met_geeft_de_ondergrens():
    utrecht = _query(_selectie("utrecht", [52000, 9000]))
    roc = _query(_selectie("roc", [17341], onderdrukt=1))

    blok = telling_blok([utrecht, roc], "ROC Midden Nederland had 17.341 inschrijvingen.")

    assert "Ondergrens" in blok and "p01mboinschr" in blok


def test_getal_dat_ook_in_een_exacte_selectie_staat_is_geen_ondergrens():
    # De uitsplitsing van Utrecht bevat de ROC-rij; de eindselectie zelf heeft geen -1.
    utrecht = _query(_selectie("utrecht", [52000, 17341], onderdrukt=1))
    roc = _query(_selectie("roc", [17341]))

    assert "Ondergrens" not in telling_blok([utrecht, roc], "Dat waren er 17.341.")


def test_scalaire_analyse_op_de_eindselectie_erft_haar_status():
    utrecht = _query(_selectie("utrecht", [52000, 9000], onderdrukt=1))
    schoon = _selectie("roc", [17000, 341])
    som = _analyse("result = int(df['AANTAL'].sum())", schoon)

    assert json.loads(som)["gelezen"] == [schoon]
    assert "Ondergrens" not in telling_blok([utrecht, _query(schoon), som], "In totaal 17.341.")


def test_scalaire_analyse_op_een_selectie_met_onderdrukking_is_een_ondergrens():
    verkenning = _query(_selectie("utrecht", [52000, 9000]))
    roc = _selectie("roc", [17000, 341], onderdrukt=1)
    som = _analyse("result = int(df['AANTAL'].sum())", roc)

    assert "Ondergrens" in telling_blok([verkenning, som], "In totaal 17.341.")


def test_kpi_erft_de_status_van_zijn_selectie():
    verkenning = _query(_selectie("utrecht", [52000, 9000], onderdrukt=1))
    roc = _selectie("roc", [17341])
    kpi = compute_kpi(data_key=roc, value_column="AANTAL", metric="last", sort_column="JAAR")

    assert "17.341" in json.loads(kpi)["value"]
    assert "Ondergrens" not in telling_blok([verkenning, kpi], "Het laatste jaar: 17.341.")


def test_zonder_getal_uit_een_selectie_geldt_de_hele_beurt():
    # Niets in de tekst wijst een selectie aan: dan niet stilzwijgend de onderdrukking weglaten.
    verkenning = _query(_selectie("utrecht", [52000, 9000], onderdrukt=1))
    roc = _query(_selectie("roc", [17341]))

    assert "Ondergrens" in telling_blok([verkenning, roc], "Daar valt weinig over te zeggen.")


def test_met_telling_gebruikt_de_tekst_van_het_antwoord():
    utrecht = _query(_selectie("utrecht", [52000, 9000], onderdrukt=1))
    roc = _query(_selectie("roc", [17341]))

    assert "Ondergrens" not in met_telling("ROC Midden Nederland: 17.341.", [utrecht, roc])


def test_csv_van_een_analysetabel_noemt_de_onderdrukking_van_wat_ze_las():
    met = _selectie("utrecht", [52000, 9000], onderdrukt=1)
    zonder = _selectie("roc", [17000, 341])
    tabel_met = json.loads(_analyse("result = df[['AANTAL']] * 2", met))["data_key"]
    tabel_zonder = json.loads(_analyse("result = df[['AANTAL']] * 2", zonder))["data_key"]

    assert "DUO-sentinel -1" in _csv(tabel_met)
    assert "DUO-sentinel -1" not in _csv(tabel_zonder)


@pytest.mark.parametrize("onderdrukt", [0, 1])
def test_antwoord_en_csv_van_een_analysetabel_zeggen_hetzelfde(onderdrukt):
    selectie = _selectie("roc", [17000, 341], onderdrukt=onderdrukt)
    tabel = _analyse("result = df[['AANTAL']] * 1", selectie)

    blok = telling_blok([tabel], "Samen 17.000 en 341.")
    csv = _csv(json.loads(tabel)["data_key"])

    assert ("Ondergrens" in blok) == ("DUO-sentinel -1" in csv) == bool(onderdrukt)


def _instelling(naam: str, aantallen: list[int], onderdrukt: int = 0) -> str:
    """Een selectie van één instelling; een onderdrukte cel staat als lege waarde in de rij."""
    key = f"{_BRON}:{naam}"
    df = pd.DataFrame(
        {"INSTELLINGSNAAM": [naam] * len(aantallen), "JAAR": [2023] * len(aantallen), "AANTAL": aantallen}
    )
    store.derive(_BRON, key, df)
    duo.record_sentinel_cells(key, pd.DataFrame({"AANTAL": [0] * (len(aantallen) - onderdrukt) + [1] * onderdrukt}))
    return _query(key)


@pytest.mark.parametrize("volgorde", [1, -1])
def test_de_zin_bindt_het_getal_aan_zijn_selectie_ook_als_een_andere_exact_is(volgorde):
    """CH-07: A = [10000, -1], B = [10000]. De claim over A kreeg geen ondergrens: B maakte hem exact."""
    a = _instelling("Hogeschool A", [10000, 0], onderdrukt=1)
    b = _instelling("Hogeschool B", [10000])

    blok = telling_blok([a, b][::volgorde], "Hogeschool A had 10.000 studenten.")

    assert "Ondergrens" in blok


def test_een_zin_over_de_exacte_selectie_geeft_geen_ondergrens():
    a = _instelling("Hogeschool A", [10000, 0], onderdrukt=1)
    b = _instelling("Hogeschool B", [10000])

    assert "Ondergrens" not in telling_blok([a, b], "Hogeschool B had 10.000 studenten.")
