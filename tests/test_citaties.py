"""Gecontroleerde getallen linken naar de meetwaarde waar ze vandaan komen (#365, #415)."""

import json

import pandas as pd
import pytest

from agent.citaties import citaties
from agent.meetwaarden import meetwaarden
from tools import periode, store
from tools.store import KeyMeta

_CBS = json.dumps({"data_key": "cbs:1", "rijen": [{"Onderwijssoort_label": "Hbo", "Totaal": 378490}]})
_DUO = json.dumps({"data_key": "duo:2", "rijen": [{"aantal": 27135}]})
_BRONLOOS = json.dumps({"bron": None, "resultaat": 55555})
# Dezelfde cijfers als code, rijtelling en key-fragment: geen van drieën is een meetwaarde.
_CODE = json.dumps(
    {
        "data_key": "duo:p01hoinges:3:36201e2d",
        "totaal_rijen": 36201,
        "preview": [{"OPLEIDINGSCODE": 36201, "INSTELLINGSCODE": "36201", "OPLEIDINGSNAAM": "Rechten"}],
    }
)
_MAAT = json.dumps(
    {
        "data_key": "duo:p01hoinges:3:abc",
        "rijen": [{"STUDIEJAAR": 2023, "OPLEIDING_NAAM": "Rechten", "AANTAL_INGESCHREVENEN": 36201}],
    }
)


def test_code_met_hetzelfde_getal_is_geen_herkomst():
    [citatie] = citaties("Er zijn 36.201 studenten.", [("get_duo_data", _CODE)])
    assert citatie == {"getal": "36.201", "vastgesteld": False, "reden": "geen_meetwaarde"}


def test_maat_wint_van_code_met_hetzelfde_getal():
    [citatie] = citaties("Er zijn 36.201 studenten.", [("get_duo_data", _CODE), ("query_data", _MAAT)])
    assert citatie["vastgesteld"] is True
    assert (citatie["stap"], citatie["tool"], citatie["maat"]) == (2, "query_data", "Aantal ingeschrevenen")
    assert citatie["selectie"] == "Studiejaar: 2023 · Opleiding naam: Rechten"


def test_getal_krijgt_de_eerste_stap_waarin_het_als_maat_staat():
    steps = [("get_cbs_data", _CBS), ("get_duo_data", _DUO)]
    result = citaties("Er zijn 378.490 en 27.135 studenten.", steps)
    assert [(c["getal"], c["stap"], c["data_key"]) for c in result] == [("378.490", 1, "cbs:1"), ("27.135", 2, "duo:2")]
    assert result[0]["selectie"] == "Onderwijssoort: Hbo"


def test_bron_in_woorden_met_de_hash_ernaast():
    store.put("duo:2", pd.DataFrame({"aantal": [27135]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    store.derive("duo:2", "duo:2:sel", pd.DataFrame({"aantal": [27135]}))
    steps = [("query_data", json.dumps({"data_key": "duo:2:sel", "rijen": [{"aantal": 27135}]}))]
    [citatie] = citaties("Het waren 27.135 studenten.", steps)
    assert citatie["bron"].startswith("DUO · ")
    assert citatie["data_key"] == "duo:2:sel"


def test_eenheid_uit_het_schema_van_de_laadstap():
    laad = json.dumps({"data_key": "cbs:1", "kolommen": [{"kolom": "Totaal", "eenheid": "aantal"}], "preview": []})
    [citatie] = citaties("Er zijn 378.490 studenten.", [("get_cbs_data", laad), ("query_data", _CBS)])
    assert citatie["eenheid"] == "aantal"


def test_ongebonden_getal_in_dataantwoord_krijgt_herkomst_niet_vastgesteld():
    assert citaties("Het waren 99.999 studenten.", [("get_cbs_data", _CBS)]) == [
        {"getal": "99.999", "vastgesteld": False, "reden": "geen_meetwaarde"}
    ]


def test_zonder_gelezen_data_geen_citaties():
    assert citaties("Het waren 55.555 studenten.", [("run_analysis", _BRONLOOS)]) == []
    assert citaties("Er zijn 1.234 datasets.", [("search_catalog", json.dumps({"resultaten": []}))]) == []


def test_jaartallen_en_kleine_getallen_krijgen_er_geen():
    assert [c["getal"] for c in citaties("In 2024 waren er 12 van 378490.", [("get_cbs_data", _CBS)])] == ["378490"]


def test_elk_voorkomen_van_een_getal_krijgt_een_eigen_citatie():
    """CH-08 (#462): de tweede claim met hetzelfde getal kreeg nooit een eigen citatie."""
    assert len(citaties("378.490 is 378.490.", [("get_cbs_data", _CBS)])) == 2


def test_aantal_citaties_hangt_alleen_van_de_tekst_af():
    tekst = "Er zijn 378.490 studenten, 27.135 in het hbo en 36.201 met code."
    steps = [("get_duo_data", _CODE), ("get_cbs_data", _CBS), ("get_duo_data", _DUO)]
    runs = [citaties(tekst, steps) for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    assert len(runs[0]) == 3


def test_kpi_uitkomst_is_een_meetwaarde():
    kpi = json.dumps(
        {
            "label": "Groei",
            "value": "+5.000",
            "raw": 5000,
            "periode": {"van": "2020/21", "tot": "2024/25"},
            "bron": {"data_key": "duo:2", "kolom": "AANTAL", "metric": "delta"},
        }
    )
    [citatie] = citaties("Een groei van 5.000 studenten.", [("compute_kpi", kpi)])
    assert (citatie["maat"], citatie["data_key"]) == ("Groei", "duo:2")
    assert "Periode: 2020/21 – 2024/25" in citatie["selectie"]


def test_analyse_resultaat_is_een_meetwaarde():
    assert citaties("Samen 12.345.", [("run_analysis", "12345")])[0]["vastgesteld"] is True
    gelezen = json.dumps({"gelezen": ["duo:2"], "resultaat": {"totaal": 12345}})
    assert citaties("Samen 12.345.", [("run_analysis", gelezen)])[0]["data_key"] == "duo:2"


def test_een_getal_dat_niet_van_de_data_afhangt_is_geen_meetwaarde():
    """CH-27: `a = 987650; result = a + 4 + len(df) * 0` gaf vastgesteld:true met bron DUO."""
    eigen = json.dumps({"gelezen": ["duo:2"], "resultaat": 987654, "scriptconstanten": [987654]})
    rijen = json.dumps(
        {"gelezen": ["duo:2"], "resultaat": {"totaal": 4600, "drempel": 1000}, "scriptconstanten": [1000]}
    )

    assert not any(c["vastgesteld"] for c in citaties("Samen 987.654.", [("run_analysis", eigen)]))
    assert [w.maat for w in meetwaarden(rijen, "run_analysis")] == ["totaal"]


def test_metadata_van_een_laadstap_is_geen_meetwaarde():
    assert meetwaarden(_CODE, "get_duo_data") == []
    assert meetwaarden("Fout (onbekende_key): 12345", "query_data") == []


def test_duo_labelkolom_wint_van_de_jaarcode():
    rij = {"STUDIEJAAR": 2023, "STUDIEJAAR_LABEL": "2023/2024", "AANTAL": 4567}
    [waarde] = meetwaarden(json.dumps({"data_key": "duo:1", "rijen": [rij]}))
    assert waarde.selectie == ("Studiejaar: 2023/2024",)


_A = json.dumps({"data_key": "duo:a", "rijen": [{"INSTELLINGSNAAM": "Hogeschool A", "AANTAL": 10000}]})
_B = json.dumps({"data_key": "duo:b", "rijen": [{"INSTELLINGSNAAM": "Hogeschool B", "AANTAL": 10000}]})


@pytest.mark.parametrize("volgorde", [1, -1])
def test_de_zin_bepaalt_de_selectie_niet_de_toolvolgorde(volgorde):
    """CH-08: met B vóór A wees 'Instelling A had 10.000' naar B (eerste numerieke match)."""
    steps = [("query_data", _B), ("query_data", _A)][::volgorde]

    [citatie] = citaties("Hogeschool A had 10.000 studenten.", steps)

    assert citatie["vastgesteld"] is True
    assert citatie["data_key"] == "duo:a"
    assert "Hogeschool A" in citatie["selectie"]


@pytest.mark.parametrize("volgorde", [1, -1])
def test_niet_te_onderscheiden_kandidaten_geven_herkomst_niet_vastgesteld(volgorde):
    steps = [("query_data", _B), ("query_data", _A)][::volgorde]

    assert citaties("Het waren 10.000 studenten.", steps) == [
        {"getal": "10.000", "vastgesteld": False, "reden": "meerdere"}
    ]


# --- CH-38 (#458): één getal in een selectie én in een analyse op die selectie ---


@pytest.fixture
def keten():
    """De HAN-route uit audit 17: query_data op p04hogdipl, run_analysis op die selectie."""
    store.clear()
    store.put("duo:p04:0", pd.DataFrame({"x": [1]}), KeyMeta(bron="duo", dataset="p04hogdipl"))
    store.derive("duo:p04:0", "duo:p04:0:sel", pd.DataFrame({"x": [1]}))
    store.derive("duo:p04:0:sel", "analysis:han", pd.DataFrame({"x": [1]}), gelezen=("duo:p04:0:sel",))
    yield
    store.clear()


_SELECTIE = json.dumps(
    {
        "data_key": "duo:p04:0:sel",
        "rijen": [{"DIPLOMAJAAR": 2020, "INSTELLINGSNAAM": "HAN", "AANTAL_GEDIPLOMEERDEN": 6323}],
    }
)
_ANALYSE = json.dumps({"data_key": "analysis:han", "rijen": [{"DIPLOMAJAAR": 2020, "HAN": 6323, "andere": 1910}]})


@pytest.mark.parametrize("volgorde", [1, -1])
def test_een_getal_in_een_selectie_en_een_analyse_daarop_krijgt_de_bron(keten, volgorde):
    """Audit 17: 6.323 stond in beide en kreeg 'staat niet als meetwaarde in de opgehaalde data'."""
    steps = [("query_data", _SELECTIE), ("run_analysis", _ANALYSE)][::volgorde]

    [citatie] = citaties("| 2020 | 6.323 | 76,8% |", steps)

    assert citatie["vastgesteld"] is True
    assert citatie["data_key"] == "duo:p04:0:sel"  # het dichtst bij de bron


def test_twijfel_tussen_losse_selecties_blijft_twijfel(keten):
    """De afleidingsketen beslist alleen binnen één keten; Hogeschool A en B blijven onbeslist (CH-08)."""
    steps = [("query_data", _B), ("query_data", _A), ("run_analysis", _ANALYSE)]

    assert citaties("Het waren 10.000 studenten.", steps)[0]["reden"] == "meerdere"


# --- CH-39 (#459): arbeidsmarktantwoorden hadden nul citaties ---

_UWV = json.dumps(
    {
        "bron": "UWV Open Match",
        "dataset": "uwv-open-match-data",
        "peildatum": "mei 2023",
        "provincie": "Gelderland",
        "totaal_vacatures": 23574,
        "clusters": {"Zorg en welzijn": 9607, "Techniek": 5426},
    }
)
_ROA = json.dumps(
    {
        "bron": "ROA, AIS tot 2030",
        "dataset": "ais2030",
        "versie": "v20251218",
        "regio": "provincie Gelderland",
        "herkomst": {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "provincie Gelderland"},
        "schoolverlaters_sis_2024": {"Bachelor": {"werkloosheid": {"perc": 4}}},
        "prognose_tot_2030": {
            "Bachelor": {
                "verwachte baanopeningen tot 2030": {"aantal": 435600},
                "ITA toekomstige arbeidsmarktsituatie in 2030": {"typering": "matig"},
            }
        },
    }
)


def test_uwv_vacatures_krijgen_een_citatie_met_provincie_en_cluster():
    [totaal, zorg] = citaties(
        "In Gelderland stonden 23.574 vacatures open, waarvan 9.607 in Zorg en welzijn.",
        [("get_uwv_vacatures", _UWV)],
    )
    assert totaal["vastgesteld"] is True and "UWV" in totaal["bron"] and "Gelderland" in totaal["selectie"]
    assert zorg["vastgesteld"] is True and "Zorg en welzijn" in zorg["selectie"]


_UWV_SECTOR = json.dumps(
    {
        "bron": "UWV Open Match",
        "dataset": "uwv-open-match-data",
        "peildatum": "mei 2023",
        "provincie": "Utrecht",
        "totaal_vacatures": 25225,
        "uwv_broncijfer": {"toelichting": "Ongewogen", "clusters": {"Chauffeurs": 2104, "Programmeurs": 1530}},
        "lokale_classificatie": {"sector": "TECHNIEK", "clusters": ["Chauffeurs", "Programmeurs"]},
        "gewogen_aandeel": {"vacatures_sector": 2582, "gedeelde_clusters": {"Chauffeurs": ["ECONOMIE"]}},
    }
)


def test_uwv_met_sector_houdt_citaties_en_noemt_het_sectorgetal_lokaal_gewogen():
    """#460: de lagen staan genest; het cluster blijft een UWV-cijfer, het sectorgetal heet lokaal gewogen."""
    [sector, cluster] = citaties(
        "In Utrecht telt TECHNIEK 2.582 vacatures, waarvan 2.104 bij Chauffeurs.",
        [("get_uwv_vacatures", _UWV_SECTOR)],
    )
    assert sector["vastgesteld"] is True and "lokaal gewogen" in sector["maat"]
    assert "TECHNIEK" in sector["selectie"]
    assert cluster["vastgesteld"] is True and cluster["maat"] == "Vacatures"
    assert "Chauffeurs" in cluster["selectie"] and "TECHNIEK" in cluster["selectie"]


def test_een_roa_prognose_krijgt_een_citatie_met_regio_uit_de_herkomst():
    [citatie] = citaties("Tot 2030 verwacht ROA 435.600 baanopeningen voor bachelors.", [("get_roa_benchmark", _ROA)])
    assert citatie["vastgesteld"] is True
    assert "ROA" in citatie["bron"] and "v20251218" in citatie["bron"]
    assert "Bachelor" in citatie["selectie"] and "provincie Gelderland" in citatie["selectie"]
    assert citatie["maat"] == "verwachte baanopeningen tot 2030"


def test_een_ander_getal_in_een_arbeidsmarktantwoord_is_expliciet_onbepaald():
    """Klaar als: elk getal uit een ROA-/UWV-antwoord heeft een citatie of expliciet 'onbepaald'."""
    assert citaties("Er zijn 12.345 vacatures.", [("get_uwv_vacatures", _UWV)]) == [
        {"getal": "12.345", "vastgesteld": False, "reden": "geen_meetwaarde"}
    ]


# --- CH-08 (#462): hetzelfde getal in twee claims ---


@pytest.mark.parametrize("volgorde", [1, -1])
def test_twee_claims_met_hetzelfde_getal_krijgen_elk_hun_eigen_selectie(volgorde):
    """Audit 17: 'Instelling B had 10.000. Instelling A had 10.000.' gaf één B-citatie."""
    steps = [("query_data", _B), ("query_data", _A)][::volgorde]

    b, a = citaties("Hogeschool B had 10.000 studenten. Hogeschool A had 10.000 studenten.", steps)

    assert (b["data_key"], a["data_key"]) == ("duo:b", "duo:a")


# --- #1002: een getal in een tabelcel wordt geduid door de kolomkop, niet door de rij alleen ---

# M01 (reaudit 10-11): CBS 85424NED, wo-gediplomeerden per diplomasoort en studiejaar, zoals de stappen het gaven.
_M01_LAAD = "cbs:85424NED:82c4b5c7"
_M01_QUERY = f"{_M01_LAAD}:4ade59ab"
_M01_ANALYSE = "analysis:29859de89bc3"
_M01_JAREN = ("2020/'21", "2021/'22", "2022/'23", "2023/'24", "2024/'25")
_M01_SOORTEN = {
    "Hbo-associate degree": (None,) * 5,
    "Bachelor": (43070, 41670, 45590, 50110, 52250),
    "Wo-doctoraal": (0,) * 5,
    "Wo-master": (47810, 47900, 49730, 50690, 53570),
    "Vervolgopleidingen": (4040, 3730, 3750, 3790, 3740),
}
_M01_TABELKOLOMMEN = ("Bachelor", "Wo-master", "Vervolgopleidingen")
_M01_ANTWOORD = """**Uitgangspunt:** Wetenschappelijk onderwijs · 2020/21 t/m 2024/25

Het aantal wo-gediplomeerden steeg van 94.920 in 2020/21 naar 109.560 in 2024/25 (voorlopig), met een dip in 2021/22.

| Studiejaar | Bachelor | Wo-master | Vervolgopleidingen | Totaal wo |
|---|---|---|---|---|
| 2020/21 | 43.070 | 47.810 | 4.040 | 94.920 |
| 2021/22 | 41.670 | 47.900 | 3.730 | 93.300 |
| 2022/23 | 45.590 | 49.730 | 3.750 | 99.070 |
| 2023/24 | 50.110 | 50.690 | 3.790 | 104.590 |
| 2024/25 (voorlopig) | 52.250 | 53.570 | 3.740 | 109.560 |

*(CBS, 85424NED, "Ho; gediplomeerden, soort diploma, opleidingsvorm", studiejaren 2020/21 t/m 2024/25.)*

### Wat valt op
- Het aantal bachelordiploma's steeg van 41.670 in 2021/22 naar 52.250 in 2024/25. Het aantal masterdiploma's steeg \
in dezelfde periode van 47.900 naar 53.570."""


def _m01_rij(soort: str, j: int, waarde: int | None) -> dict:
    status = "Voorlopig" if j == 4 else "Definitief"
    return {"Diplomasoort_label": soort, "Perioden_label": _M01_JAREN[j], "Gediplomeerden_1": waarde} | {
        "Periodestatus": status
    }


def _m01_rijen() -> list[dict]:
    return [_m01_rij(soort, j, w) for soort, reeks in _M01_SOORTEN.items() for j, w in enumerate(reeks)]


def _m01_laadrij(rij: dict, id_: int) -> dict:
    """Een rij van get_cbs_data: codes, labels en de periodestatus."""
    vast = {"ID": id_, "Geslacht": "T001038", "Onderwijssoort": "A025297", "Opleidingsvorm": "T001228"}
    labels = {"Geslacht_label": "Totaal mannen en vrouwen", "Onderwijssoort_label": "Wetenschappelijk onderwijs"}
    return vast | {"Gediplomeerden_1": rij["Gediplomeerden_1"]} | labels | rij


def _m01_pivot() -> list[dict]:
    """De draaitabel van run_analysis: per studiejaar een kolom per diplomasoort en het totaal."""
    rijen = []
    for j, jaar in enumerate(_M01_JAREN):
        soorten = {s: reeks[j] for s, reeks in _M01_SOORTEN.items() if s != "Hbo-associate degree"}
        status = "Voorlopig" if j == 4 else "Definitief"
        rijen.append(
            {
                "Perioden_label": jaar,
                "Periodestatus": status,
                **soorten,
                "Totaal": sum(w or 0 for w in soorten.values()),
            }
        )
    return rijen


def _m01_stappen(preview: list[dict]) -> list[tuple[str, str]]:
    kolommen = [{"kolom": "Gediplomeerden_1", "eenheid": "aantal"}]
    laad = {"data_key": _M01_LAAD, "totaal_rijen": 25, "kolommen": kolommen, "preview": preview}
    query = {"data_key": _M01_QUERY, "totaal_rijen": 25, "rijen": _m01_rijen()}
    analyse = {"data_key": _M01_ANALYSE, "rijen": _m01_pivot()}
    return [
        ("get_cbs_data", json.dumps(laad)),
        ("query_data", json.dumps(query)),
        ("run_analysis", json.dumps(analyse)),
    ]


@pytest.fixture
def m01_zusjes():
    """Zoals in M01: query_data en run_analysis lezen allebei de lading; de preview toont alleen de lege Ad-rijen."""
    store.clear()
    store.put(_M01_LAAD, pd.DataFrame({"x": [1]}), KeyMeta(bron="cbs", dataset="85424NED"))
    store.derive(_M01_LAAD, _M01_QUERY, pd.DataFrame({"x": [1]}))
    store.derive(_M01_LAAD, _M01_ANALYSE, pd.DataFrame({"x": [1]}), gelezen=(_M01_LAAD,))
    yield _m01_stappen([_m01_laadrij(rij, 219 + i) for i, rij in enumerate(_m01_rijen()[:5])])
    store.clear()


@pytest.fixture
def m01_keten():
    """Eén afleidingsketen: lading met alle rijen, query_data daarop en run_analysis op de query."""
    store.clear()
    store.put(_M01_LAAD, pd.DataFrame({"x": [1]}), KeyMeta(bron="cbs", dataset="85424NED"))
    store.derive(_M01_LAAD, _M01_QUERY, pd.DataFrame({"x": [1]}))
    store.derive(_M01_QUERY, _M01_ANALYSE, pd.DataFrame({"x": [1]}), gelezen=(_M01_QUERY,))
    yield _m01_stappen([_m01_laadrij(rij, 219 + i) for i, rij in enumerate(_m01_rijen())])
    store.clear()


def _m01_tabelcitaties(stappen: list[tuple[str, str]]) -> list[list[dict]]:
    """De citaties van de twintig tabelcellen, per rij; de eerste zin heeft er twee, de tabel volgt."""
    gevonden = citaties(_M01_ANTWOORD, stappen)
    assert len(gevonden) == 26  # het aantal citaties verandert niet: de frontend telt ze per getal
    return [gevonden[2 + 4 * j : 6 + 4 * j] for j in range(5)]


def _assert_m01_tabel(stappen: list[tuple[str, str]], cel_key: str) -> None:
    for j, rij in enumerate(_m01_tabelcitaties(stappen)):
        assert all(c["vastgesteld"] for c in rij), rij
        for soort, citatie in zip(_M01_TABELKOLOMMEN, rij, strict=False):
            assert citatie["getal"] == f"{_M01_SOORTEN[soort][j]:,}".replace(",", ".")
            assert f"Diplomasoort: {soort}" in citatie["selectie"]
            assert citatie["data_key"] == cel_key
        totaal = rij[3]
        assert (totaal["maat"], totaal["tool"], totaal["data_key"]) == ("Totaal", "run_analysis", _M01_ANALYSE)
        assert all(periode.gevraagde_schooljaren(c["selectie"]) == {2020 + j} for c in rij)


@pytest.mark.parametrize("volgorde", [1, -1])
def test_m01_elke_tabelcel_krijgt_haar_diplomasoort_en_studiejaar(m01_zusjes, volgorde):
    """M01: 19 van de 26 citaties waren 'meerdere'; de rij noemde de kolomkop niet, en de draaitabel van run_analysis
    is een zusje van de query, geen afleiding ervan. Nu wijst de kop de diplomasoort aan en wint de rij van de
    selectie van de draaitabel."""
    _assert_m01_tabel(m01_zusjes[::volgorde], _M01_QUERY)


def test_m01_in_een_afleidingsketen_wint_de_lading(m01_keten):
    """Dezelfde cel in de lading, de query en de draaitabel: de stap het dichtst bij de bron (CH-38)."""
    _assert_m01_tabel(m01_keten, _M01_LAAD)
    lading = _m01_tabelcitaties(m01_keten)[0][0]
    assert (lading["stap"], lading["tool"], lading["eenheid"]) == (1, "get_cbs_data", "aantal")


def test_m01_de_zinnen_onder_de_tabel_krijgen_ook_hun_bron(m01_zusjes):
    """'Het aantal bachelordiploma's steeg van 41.670' noemt geen kolomkop: de rij wint van haar draaitabel."""
    staart = citaties(_M01_ANTWOORD, m01_zusjes)[-4:]
    assert [c["getal"] for c in staart] == ["41.670", "52.250", "47.900", "53.570"]
    assert all(c["vastgesteld"] and c["data_key"] == _M01_QUERY for c in staart)


def _per_jaar(key: str, maat: str, waarde: int) -> tuple[str, str]:
    return ("query_data", json.dumps({"data_key": key, "rijen": [{"Perioden_label": "2020/'21", maat: waarde}]}))


_TWEE_MATEN = [_per_jaar("cbs:in", "Ingeschrevenen", 47810), _per_jaar("cbs:gd", "Gediplomeerden", 47810)]
_TABEL_AANTAL = "| Studiejaar | Aantal |\n|---|---|\n| 2020/21 | 47.810 |"


@pytest.mark.parametrize("volgorde", [1, -1])
def test_een_cel_met_twee_betekenissen_blijft_twijfel(volgorde):
    """Twee maten met dezelfde waarde in hetzelfde jaar, in losse ladingen: kop en rij kiezen niet, de bron ook niet."""
    [citatie] = citaties(f"Per studiejaar:\n\n{_TABEL_AANTAL}", _TWEE_MATEN[::volgorde])
    assert citatie == {"getal": "47.810", "vastgesteld": False, "reden": "meerdere"}


@pytest.mark.parametrize("volgorde", [1, -1])
def test_de_tekst_voor_de_tabel_noemt_de_maat(volgorde):
    """Zoals de tabelcontrole (#982): kiezen kop en rij niet, dan de maat die de tekst vóór de tabel het laatst noemt."""
    tekst = f"Ingeschrevenen telden we ook. Het aantal gediplomeerden per studiejaar:\n\n{_TABEL_AANTAL}"
    [citatie] = citaties(tekst, _TWEE_MATEN[::volgorde])
    assert (citatie["vastgesteld"], citatie["maat"]) == (True, "Gediplomeerden")


def _soort(key: str, soort: str) -> tuple[str, str]:
    rij = {"SOORT": soort, "JAAR_LABEL": "2020", "AANTAL": 12345}
    return ("query_data", json.dumps({"data_key": key, "rijen": [rij]}))


# Hetzelfde getal in hetzelfde jaar, in losse selecties: alleen de soort onderscheidt ze.
_SOORTEN = [_soort("duo:ba", "Bachelor"), _soort("duo:ma", "Master")]


def test_hetzelfde_getal_in_twee_tabellen_volgt_elk_zijn_eigen_kop():
    """De cel van een positie: 12.345 staat in twee tabellen, elk onder een andere kop."""
    tekst = (
        "| Jaar | Bachelor |\n|---|---:|\n| 2020 | 12.345 |\n\n"
        "Daarnaast de masters.\n\n| Jaar | Master |\n|---|---:|\n| 2020 | **12.345** |"
    )
    ba, ma = citaties(tekst, _SOORTEN)
    assert (ba["data_key"], ma["data_key"]) == ("duo:ba", "duo:ma")


def test_zin_en_tabel_door_elkaar():
    """De zin bindt aan wat zij noemt, de cel aan haar kop: de zin vóór de tabel stuurt de cel niet."""
    tekst = "In 2020 haalden 12.345 studenten een Master.\n\n| Jaar | Bachelor |\n|---|---|\n| 2020 | 12.345 |"
    zin, cel = citaties(tekst, _SOORTEN)
    assert (zin["data_key"], cel["data_key"]) == ("duo:ma", "duo:ba")


def test_een_tabel_in_een_codeblok_is_geen_tabel():
    """In een codeblok telt alleen de rij, zoals vroeger: die noemt geen soort."""
    tekst = "```\n| Jaar | Bachelor |\n|---|---|\n| 2020 | 12.345 |\n```"
    [citatie] = citaties(tekst, _SOORTEN)
    assert citatie == {"getal": "12.345", "vastgesteld": False, "reden": "meerdere"}
