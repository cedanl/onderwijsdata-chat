"""Een onderdrukte cel terugrekenen als totaal min de zichtbare delen, geven we niet (#1265).

De fixtures: een DUO-tabel met delen per sector waarvan één -1 is, een totaalbestand per jaar, een DUO-tabel met een
eigen totaalrij en een CBS-tabel met een lege cel ('.') naast het totaal van dezelfde tabel. De ware waarde van elke
onderdrukte cel is 3 (DUO) of 4.120 (CBS); die mag in geen uitkomst staan.
"""

import json

import pandas as pd
import pytest

from tools import store, terugrekenen
from tools.analysis import run_analysis
from tools.kpi import compute_kpi

DELEN = "duo:delen-per-sector:0:test"
TOTAAL = "duo:totaal-per-jaar:0:test"
MET_TOTAALRIJ = "duo:met-totaalrij:0:test"
CBS = "cbs:99999NED:test"

# Economie + Techniek (-1, echt 3) + Zorg: 2022 is 201, 2023 is 203.
_DELEN = [
    {"JAAR": 2022, "SECTOR": "Economie", "AANTAL": 118},
    {"JAAR": 2022, "SECTOR": "Techniek", "AANTAL": -1},
    {"JAAR": 2022, "SECTOR": "Zorg", "AANTAL": 80},
    {"JAAR": 2023, "SECTOR": "Economie", "AANTAL": 120},
    {"JAAR": 2023, "SECTOR": "Techniek", "AANTAL": -1},
    {"JAAR": 2023, "SECTOR": "Zorg", "AANTAL": 80},
]
_TOTAAL = [{"JAAR": 2022, "AANTAL": 201}, {"JAAR": 2023, "AANTAL": 203}]
_MET_TOTAALRIJ = [
    {"JAAR": 2023, "SECTOR": "Economie", "AANTAL": 120},
    {"JAAR": 2023, "SECTOR": "Techniek", "AANTAL": -1},
    {"JAAR": 2023, "SECTOR": "Zorg", "AANTAL": 80},
    {"JAAR": 2023, "SECTOR": "Totaal", "AANTAL": 203},
]
# CBS: mannen (3000) en vrouwen (4000, '.') naast het totaal (T001038); vrouwen is echt 4.120.
_CBS = [
    {"Geslacht": "3000", "Perioden": "2023SJ00", "Studenten": 5230.0},
    {"Geslacht": "4000", "Perioden": "2023SJ00", "Studenten": None},
    {"Geslacht": "T001038", "Perioden": "2023SJ00", "Studenten": 9350.0},
]
_WAAR = {DELEN: 3, MET_TOTAALRIJ: 3, CBS: 4120}


@pytest.fixture(autouse=True)
def fixtures():
    store.put(DELEN, pd.DataFrame(_DELEN), store.KeyMeta(bron="duo", dataset="delen-per-sector", periodekolom="JAAR"))
    store.put(TOTAAL, pd.DataFrame(_TOTAAL), store.KeyMeta(bron="duo", dataset="totaal-per-jaar", periodekolom="JAAR"))
    store.put(
        MET_TOTAALRIJ,
        pd.DataFrame(_MET_TOTAALRIJ),
        store.KeyMeta(bron="duo", dataset="met-totaalrij", periodekolom="JAAR"),
    )
    store.put(CBS, pd.DataFrame(_CBS), store.KeyMeta(bron="cbs", dataset="99999NED", periodekolom="Perioden"))


def _getallen(uitkomst) -> set[float]:
    tekst = uitkomst[0] if isinstance(uitkomst, tuple) else uitkomst
    figuur = uitkomst[1] if isinstance(uitkomst, tuple) else None
    return {round(g, 6) for g in terugrekenen.getallen([tekst, figuur])}


def _json(uitkomst) -> dict:
    return json.loads(uitkomst[0] if isinstance(uitkomst, tuple) else uitkomst)


# --- criterium 1: run_analysis, totaal uit een ander bestand ---


def test_run_analysis_totaal_min_delen_geeft_de_melding_en_niet_het_getal():
    uitkomst = run_analysis(
        code=(
            f"t = store_get('{TOTAAL}')\n"
            "result = int(t.loc[t['JAAR'] == 2023, 'AANTAL'].sum() - df.loc[df['JAAR'] == 2023, 'AANTAL'].sum())"
        ),
        data_key=DELEN,
    )
    assert uitkomst == terugrekenen.MELDING
    assert "3" not in uitkomst


def test_zonder_onderdrukking_rekent_het_script_gewoon():
    """Dezelfde som op een tabel zonder -1 is gewoon een verschil."""
    store.put(
        "duo:zonder:0:test",
        pd.DataFrame([{"JAAR": 2023, "SECTOR": s, "AANTAL": n} for s, n in (("A", 120), ("B", 3), ("C", 80))]),
        store.KeyMeta(bron="duo", dataset="zonder", periodekolom="JAAR"),
    )
    uitkomst = run_analysis(
        code=(
            f"t = store_get('{TOTAAL}')\n"
            "result = int(t.loc[t['JAAR'] == 2023, 'AANTAL'].sum() - df.loc[df['SECTOR'] != 'B', 'AANTAL'].sum())"
        ),
        data_key="duo:zonder:0:test",
    )
    assert _json(uitkomst)["resultaat"] == 3


# --- criterium 2: compute_kpi en een CBS-cel ---


def test_compute_kpi_verschil_dat_de_cel_teruggeeft_wordt_geweigerd():
    # Een eigen tabel met de som van de delen en het totaal: dat mag, er staat geen cel in.
    tussen = run_analysis(
        code=(
            f"t = store_get('{TOTAAL}')\n"
            "result = [{'STAP': 1, 'AANTAL': int(df.loc[df['JAAR'] == 2023, 'AANTAL'].sum())},"
            " {'STAP': 2, 'AANTAL': int(t.loc[t['JAAR'] == 2023, 'AANTAL'].sum())}]"
        ),
        data_key=DELEN,
    )
    key = _json(tussen)["data_key"]
    uitkomst = compute_kpi(data_key=key, value_column="AANTAL", metric="delta", sort_column="STAP")
    assert json.loads(uitkomst) == {"fout": terugrekenen.MELDING}


def test_compute_kpi_op_een_cbs_tabel_met_totaal_en_lege_cel():
    uitkomst = compute_kpi(data_key=CBS, value_column="Studenten", metric="delta", sort_column="Geslacht")
    assert json.loads(uitkomst) == {"fout": terugrekenen.MELDING}
    assert "4120" not in uitkomst


def test_run_analysis_op_een_cbs_cel():
    uitkomst = run_analysis(
        code=(
            "t = df.loc[df['Geslacht'] == 'T001038', 'Studenten'].sum()\n"
            "m = df.loc[df['Geslacht'] == '3000', 'Studenten'].sum()\n"
            "result = {'vrouwen': float(t - m)}"
        ),
        data_key=CBS,
    )
    assert uitkomst == terugrekenen.MELDING


# --- criterium 3: elke kleine reconstructie, als getal, tabel (CSV) en grafiek ---

_RECONSTRUCTIES = {
    # totaal uit een ander bestand
    "ander bestand": (
        DELEN,
        f"t = store_get('{TOTAAL}')\nx = t.loc[t['JAAR'] == 2023, 'AANTAL'].sum() - df.loc[df['JAAR'] == 2023, 'AANTAL'].sum()",
    ),
    "ander bestand, 2022": (
        DELEN,
        f"t = store_get('{TOTAAL}')\nx = t.loc[t['JAAR'] == 2022, 'AANTAL'].sum() - df.loc[df['JAAR'] == 2022, 'AANTAL'].sum()",
    ),
    # totaal uit dezelfde tabel
    "eigen totaalrij": (
        MET_TOTAALRIJ,
        "x = df.loc[df['SECTOR'] == 'Totaal', 'AANTAL'].sum() - df.loc[df['SECTOR'] != 'Totaal', 'AANTAL'].sum()",
    ),
    "eigen totaalrij, per deel": (
        MET_TOTAALRIJ,
        "d = df.set_index('SECTOR')['AANTAL']\nx = d['Totaal'] - d['Economie'] - d['Zorg']",
    ),
    # totaal dat het model eerder las en in het script typte
    "getypt totaal": (DELEN, "x = 203 - df.loc[df['JAAR'] == 2023, 'AANTAL'].sum()"),
    "cbs eigen totaal": (
        CBS,
        "x = df.loc[df['Geslacht'] == 'T001038', 'Studenten'].sum() - df.loc[df['Geslacht'] == '3000', 'Studenten'].sum()",
    ),
}
_VORMEN = {
    "getal": "result = float(x)",
    "tekst": "result = f'Techniek: {int(x)}'",
    "tabel": "result = [{'SECTOR': 'Techniek', 'AANTAL': float(x)}]",
    "grafiek": "figure = px.bar(x=['Techniek'], y=[float(x)])\nresult = 'grafiek'",
}


@pytest.mark.parametrize("vorm", sorted(_VORMEN))
@pytest.mark.parametrize("geval", sorted(_RECONSTRUCTIES))
def test_geen_reconstructie_als_exact_getal_in_uitkomst_csv_of_grafiek(geval, vorm):
    key, rekenen = _RECONSTRUCTIES[geval]
    uitkomst = run_analysis(code=f"{rekenen}\n{_VORMEN[vorm]}", data_key=key)
    assert uitkomst == terugrekenen.MELDING, uitkomst
    assert _WAAR[key] not in _getallen(uitkomst)
    # Er ontstond ook geen key met de cel: niets om als CSV te exporteren of te tekenen.
    assert not any(k.startswith("analysis:") for k in store.list_keys())


def test_de_reconstructies_van_de_fixtures():
    waarden = {(r.key, r.waarde) for r in terugrekenen.reconstructies([DELEN, TOTAAL, MET_TOTAALRIJ, CBS])}
    assert waarden == {(DELEN, 3.0), (MET_TOTAALRIJ, 3.0), (CBS, 4120.0)}


# --- criterium 4: geen valse weigering ---


def test_verschil_van_twee_totalen_met_de_cel_erin_blijft_mogelijk():
    """2023 min 2022 van het totaalbestand: beide totalen bevatten de onderdrukte cel, die valt weg."""
    uitkomst = run_analysis(
        code=(
            f"t = store_get('{TOTAAL}').set_index('JAAR')['AANTAL']\n"
            "s = df.groupby('JAAR')['AANTAL'].sum()\n"
            "result = {'verschil_totaal': int(t[2023] - t[2022]), 'som_delen': int(s[2023])}"
        ),
        data_key=DELEN,
    )
    assert _json(uitkomst)["resultaat"] == {"verschil_totaal": 2, "som_delen": 200}


def test_compute_kpi_verschil_van_twee_totalen_blijft_mogelijk():
    uitkomst = compute_kpi(data_key=TOTAAL, value_column="AANTAL", metric="delta", sort_column="JAAR")
    assert json.loads(uitkomst)["raw"] == 2


def test_de_tabel_zelf_tonen_mag():
    """De delen met de lege cel en de totaalrij: dat publiceert de bron zelf, het is geen eigen reconstructie."""
    uitkomst = run_analysis(code="result = df", data_key=MET_TOTAALRIJ)
    assert [r["AANTAL"] for r in _json(uitkomst)["rijen"]] == [120, None, 80, 203]


def test_twee_onderdrukte_cellen_in_een_groep_zijn_niet_exact():
    store.put(
        "duo:twee:0:test",
        pd.DataFrame(
            [
                {"JAAR": 2023, "SECTOR": "A", "AANTAL": 120},
                {"JAAR": 2023, "SECTOR": "B", "AANTAL": -1},
                {"JAAR": 2023, "SECTOR": "C", "AANTAL": -1},
                {"JAAR": 2023, "SECTOR": "Totaal", "AANTAL": 124},
            ]
        ),
        store.KeyMeta(bron="duo", dataset="twee", periodekolom="JAAR"),
    )
    assert not terugrekenen.reconstructies(["duo:twee:0:test"])


def test_een_afgeleide_som_van_de_delen_is_geen_totaal():
    """De som per jaar van de delen zelf (een ondergrens) is geen totaal waartegen de cel terug te rekenen is."""
    from tools.query import query_data

    som = json.loads(query_data(data_key=DELEN, group_by=["JAAR"], aggregate={"AANTAL": "sum"}))
    assert not terugrekenen.reconstructies([DELEN, som["data_key"]])


# --- het eindantwoord: ook als het model zelf rekent (criterium 3 en 5) ---


def _toolresultaten() -> list[str]:
    return [json.dumps({"data_key": k}) for k in (DELEN, TOTAAL, CBS)]


def test_een_teruggerekende_cel_in_het_antwoord_is_een_hard_probleem():
    from agent.terugrekening import teruggerekende_cellen

    tekst = "Het totaal in 2023 is 203. Economie telt 120 en Zorg 80, dus Techniek telt 3 studenten."
    [probleem] = teruggerekende_cellen(tekst, _toolresultaten())
    assert probleem.melding == terugrekenen.MELDING


def test_een_klein_getal_zonder_de_cel_is_geen_probleem():
    from agent.terugrekening import teruggerekende_cellen

    tekst = "Het totaal in 2023 is 203 studenten in 3 sectoren; Techniek is door DUO onderdrukt."
    assert teruggerekende_cellen(tekst, _toolresultaten()) == []


def test_de_getalcontrole_telt_een_teruggerekend_verschil_niet_als_gedekt():
    """9.350 - 5.230 = 4.120 is een afgeleid verschil (#409), maar hier is het de onderdrukte cel vrouwen."""
    from agent.controles import maak_getalcontrole

    resultaat = json.dumps(
        {"data_key": CBS, "rijen": [{"Geslacht": "T001038", "Studenten": 9350}, {"Studenten": 5230}]}
    )
    tekst = "Er zijn 9.350 studenten, van wie 5.230 mannen: 4.120 vrouwen."
    problemen = maak_getalcontrole([], [])(tekst, [resultaat])
    assert [p.getal for p in problemen] == ["4.120"]
    assert problemen[0].hard


def test_de_getalcontrole_laat_een_gewoon_verschil_door():
    from agent.controles import maak_getalcontrole

    resultaat = json.dumps({"data_key": TOTAAL, "rijen": [{"JAAR": 2022, "N": 478660}, {"JAAR": 2023, "N": 475460}]})
    tekst = "Van 478.660 naar 475.460, 3.200 minder."
    assert maak_getalcontrole([], [])(tekst, [resultaat]) == []


def test_ook_zonder_label_telt_totaal_min_delen():
    from agent.terugrekening import teruggerekende_cellen

    assert teruggerekende_cellen("Het totaal is 203 en de delen samen 200: dus blijft 3 over.", _toolresultaten())
