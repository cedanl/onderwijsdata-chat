"""Gouden tests voor get_uwv_vacatures en get_roa_benchmark op bevroren bronnen (#870).

De bronnen zijn op 02-11-2026 via riodata opgehaald met `scripts/gouden_testfixtures.py` (zie
`tests/fixtures/gouden/bronnen.json`); de fixture `gouden` zet ze klaar en sluit het netwerk af. De verwachte waarden
zijn met pandas op de bevroren bestanden nagerekend, buiten de tools om; de berekening staat bij elke test.
"""

import json

import pytest

from tools.arbeidsmarkt import get_roa_benchmark, get_uwv_vacatures

pytestmark = pytest.mark.usefixtures("gouden")

# Bron: UWV Open Match (riodata uwv.load("latest", rec_type="Vacature"), bevroren stand van 16-05-2023), opgehaald
# 02-11-2026, gefilterd op PROVINCIE Flevoland. Nagerekend met pandas:
#   u = pd.read_csv(gz); u.AANTAL.sum() → 5848; u.BEROEPENCLUSTER.nunique() → 301
#   u.groupby("BEROEPENCLUSTER").AANTAL.sum().nlargest(4)
#     Chauffeurs goederenvervoer 423, Magazijnmedewerkers 353, Monteurs werktuigbouw 225, Productiemedewerkers 204
#   gemeente Almere: u[u.GEMEENTE == "Almere"].AANTAL.sum() → 2573; 241 clusters
#     Chauffeurs goederenvervoer 164, Magazijnmedewerkers 142, Klantenservice- en callcentermedewerkers 106,
#     Monteurs werktuigbouw 94


def test_uwv_vacatures_in_een_provincie():
    uit = json.loads(get_uwv_vacatures("Flevoland"))

    assert (uit["provincie"], uit["peildatum"], uit["totaal_vacatures"]) == ("Flevoland", "2023-05-16", 5848)
    assert list(uit["clusters"].items())[:4] == [
        ("Chauffeurs goederenvervoer", 423),
        ("Magazijnmedewerkers", 353),
        ("Monteurs werktuigbouw", 225),
        ("Productiemedewerkers", 204),
    ]
    assert uit["clusters_getoond"] == "de 15 grootste van 301 beroepenclusters"


def test_uwv_vacatures_in_een_gemeente():
    uit = json.loads(get_uwv_vacatures("Flevoland", gemeente="Almere"))

    assert (uit["gemeente"], uit["totaal_vacatures"]) == ("Almere", 2573)
    assert list(uit["clusters"].items())[:4] == [
        ("Chauffeurs goederenvervoer", 164),
        ("Magazijnmedewerkers", 142),
        ("Klantenservice- en callcentermedewerkers", 106),
        ("Monteurs werktuigbouw", 94),
    ]
    assert uit["clusters_getoond"] == "de 15 grootste van 241 beroepenclusters"


# Bron: ROA AIS 2030 (riodata roa.load("ais2030", "arbeidsmarkt"), versie v20251218), opgehaald 02-11-2026,
# gefilterd op regionaam Nederland, aggregatieniveau "opleidingsniveau (ONR2019)" en de indicatoren van de tool.
# Nagelezen met pandas: r = pd.read_csv(gz); r.pivot_table(index="detailniveau", columns="onderwerp",
# values=["perc", "aantal"]) en de kolom typering:
#                   werkloosheid  vast dienstverband  buiten vakrichting  baanopeningen  instroom  ITA 2030
#   Mbo2                       5                  81                  48         101500    130800  matig
#   Mbo3                       2                  86                  37         141000    168300  matig
#   Mbo4                       3                  81                  34         325800    358700  redelijk
#   Bachelor                   4                  65                  25         435600    533700  matig
#   Master, doctor             4                  49                  24         337900    285200  goed
_SIS = {
    "Mbo2": (5, 81, 48),
    "Mbo3": (2, 86, 37),
    "Mbo4": (3, 81, 34),
    "Bachelor": (4, 65, 25),
    "Master, doctor": (4, 49, 24),
}
_PROGNOSE = {
    "Mbo2": (101500, 130800, "matig"),
    "Mbo3": (141000, 168300, "matig"),
    "Mbo4": (325800, 358700, "redelijk"),
    "Bachelor": (435600, 533700, "matig"),
    "Master, doctor": (337900, 285200, "goed"),
}


def test_roa_benchmark_landelijk_per_opleidingsniveau():
    uit = json.loads(get_roa_benchmark())

    assert (uit["regio"], uit["versie"]) == ("Nederland", "v20251218")
    assert {
        niveau: tuple(w[i]["perc"] for i in ("werkloosheid", "vast dienstverband", "buiten de vakrichting"))
        for niveau, w in uit["schoolverlaters_sis_2024"].items()
    } == _SIS
    assert {
        niveau: (
            w["verwachte baanopeningen tot 2030"]["aantal"],
            w["verwachte instroom van schoolverlaters tot 2030"]["aantal"],
            w["ITA toekomstige arbeidsmarktsituatie in 2030"]["typering"],
        )
        for niveau, w in uit["prognose_tot_2030"].items()
    } == _PROGNOSE
    assert "ho_opleiding" not in uit  # zonder onderdeel blijft het mbo/hbo/wo-overzicht zoals het was


# ── #745: de opleidingen van de RUG en de arbeidsmarkt in de regio ───────────────────────────────────────────────────
# Dezelfde bron, nu ook de ho-categorieën (sector, subsector, type) in Nederland, Groningen en provincie Groningen
# (`ROA_HO_REGIOS` in scripts/gouden_testfixtures.py). Nagerekend met pandas op het bevroren bestand:
#   r[r.detailniveau == naam].pivot_table(index=["regionaam", "aggregatieniveau"], columns="onderwerp",
#                                         values=["perc", "aantal", "typering"], aggfunc="first")
#   Groningen, ITA 2030: Bachelor matig, Master, doctor redelijk; Master - journalistiek, gedrag en maatschappij
#                        matig; Master - economie en recht redelijk; Bachelor - economie en recht matig
#   Nederland (werkloosheid, vast dienstverband, buiten de vakrichting in %; baanopeningen tot 2030; ITA 2030):
#     Master - journalistiek, gedrag en maatschappij   5  39  30   33300  matig
#     Master - psychologie (type)                       5  41  20   14000  matig
#     Master - recht (type)                             7  52  19   28100  redelijk
#     Bachelor - recht (type)                           5  57  27    6900  slecht
#   Opleidingstypen staan er alleen voor Nederland: geen rij voor Groningen.
_ITA = "ITA toekomstige arbeidsmarktsituatie in 2030"
_GM = "Master - journalistiek, gedrag en maatschappij"


def _sis(blok: dict, naam: str) -> tuple:
    w = blok["schoolverlaters_sis_2024"][naam]
    return tuple(w[i]["perc"] for i in ("werkloosheid", "vast dienstverband", "buiten de vakrichting"))


def test_rug_gedrag_en_maatschappij_in_groningen_krijgt_de_mastersubsector_regionaal():
    uit = json.loads(get_roa_benchmark(regio="Groningen", onderdeel="GEDRAG_EN_MAATSCHAPPIJ"))

    # Het niveau: alleen ho, de prognose voor Groningen, de schoolverlaters landelijk.
    assert set(uit["prognose_tot_2030"]) == {"Bachelor", "Master, doctor"}
    assert uit["prognose_tot_2030"]["Master, doctor"][_ITA]["typering"] == "redelijk"
    assert uit["herkomst"] == {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "Groningen"}
    ho = uit["ho_opleiding"]
    assert ho["koppeling"]["Master, doctor"]["subsector"] == _GM
    assert set(ho["koppeling"]["Bachelor"]) == {"ongekoppeld"}
    # De subsector: de prognose van Groningen, de schoolverlaters van Nederland.
    assert ho["categorie"]["prognose_tot_2030"][_GM][_ITA]["typering"] == "matig"
    assert ho["categorie"]["herkomst"] == {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "Groningen"}
    assert _sis(ho["categorie"], _GM) == (5, 39, 30)


def test_rug_opleidingstypen_zijn_landelijk_en_de_tool_zegt_dat():
    ho = json.loads(get_roa_benchmark(regio="Groningen", onderdeel="GEDRAG_EN_MAATSCHAPPIJ"))["ho_opleiding"]

    typen = ho["opleidingstype"]
    assert list(typen["prognose_tot_2030"]) == [
        "Master - communicatie en journalistiek",
        "Master - psychologie",
        "Master - sociale en maatschappijwetenschappen",
    ]
    assert typen["herkomst"] == {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "Nederland"}
    assert _sis(typen, "Master - psychologie") == (5, 41, 20)
    assert typen["prognose_tot_2030"]["Master - psychologie"]["verwachte baanopeningen tot 2030"]["aantal"] == 14000
    meldingen = " ".join(ho["meldingen"])
    assert "Opleidingstype alleen landelijk" in meldingen and "niet voor Groningen" in meldingen
    assert "GEDRAG_EN_MAATSCHAPPIJ is voor Bachelor niet aan een ROA-categorie te koppelen" in meldingen
    assert "niet naar hbo en wo" in meldingen
    assert "UWV legt bij vacatures geen opleidingsniveau vast" in meldingen


def test_rug_recht_krijgt_het_opleidingstype_recht_en_niet_de_hele_subsector():
    ho = json.loads(get_roa_benchmark(regio="Groningen", onderdeel="RECHT"))["ho_opleiding"]

    assert ho["categorie"]["prognose_tot_2030"] == {
        "Bachelor - economie en recht": {_ITA: {"typering": "matig"}},
        "Master - economie en recht": {_ITA: {"typering": "redelijk"}},
    }
    assert set(ho["opleidingstype"]["prognose_tot_2030"]) == {"Bachelor - recht", "Master - recht"}
    assert _sis(ho["opleidingstype"], "Master - recht") == (7, 52, 19)
    assert _sis(ho["opleidingstype"], "Bachelor - recht") == (5, 57, 27)
    assert ho["opleidingstype"]["prognose_tot_2030"]["Master - recht"][_ITA]["typering"] == "redelijk"
    assert not any("onderverdeling" in m for m in ho["meldingen"])


def test_rug_natuur_is_niet_te_koppelen_en_houdt_alleen_het_niveau():
    uit = json.loads(get_roa_benchmark(regio="Groningen", onderdeel="NATUUR"))

    ho = uit["ho_opleiding"]
    assert set(ho["koppeling"]["Bachelor"]) == set(ho["koppeling"]["Master, doctor"]) == {"ongekoppeld"}
    assert "categorie" not in ho and "opleidingstype" not in ho
    assert sum("NATUUR is voor" in m for m in ho["meldingen"]) == 2
    assert uit["prognose_tot_2030"]["Bachelor"][_ITA]["typering"] == "matig"


def test_landelijk_onderdeel_zonder_melding_over_de_regio():
    ho = json.loads(get_roa_benchmark(onderdeel="Gedrag en maatschappij"))["ho_opleiding"]

    assert ho["onderdeel"] == "GEDRAG_EN_MAATSCHAPPIJ"
    assert ho["categorie"]["prognose_tot_2030"][_GM]["verwachte baanopeningen tot 2030"]["aantal"] == 33300
    assert not any("alleen landelijk" in m for m in ho["meldingen"])


def test_tabel_meetwaarden_recept_en_snippet_dragen_de_ho_cijfers(monkeypatch):
    from riodata import roa

    from agent.meetwaarden import meetwaarden
    from data import arbeidsmarkt
    from tools import snippet, store

    resultaat = get_roa_benchmark(regio="Groningen", onderdeel="GEDRAG_EN_MAATSCHAPPIJ")
    key = json.loads(resultaat)["data_key"]

    assert key == "roa:groningen:gedrag-en-maatschappij"
    tabel = store.get(key)
    rijen = {(r["REGIO"], r["OPLEIDING"], r["INDICATOR"]): r for r in tabel.to_dict("records")}
    assert rijen[("Groningen", _GM, _ITA)]["TYPERING"] == "matig"
    assert rijen[("Nederland", "Master - psychologie", "werkloosheid")]["PERCENTAGE"] == 5
    psychologie = [w for w in meetwaarden(resultaat) if "Opleiding: Master - psychologie" in w.selectie]
    assert psychologie and {w.selectie[1] for w in psychologie} == {"Regio: Nederland"}
    known = store.meta(key)
    assert known is not None and known.laad == (
        "get_roa_benchmark",
        {"regio": "Groningen", "onderdeel": "GEDRAG_EN_MAATSCHAPPIJ"},
    )

    # De snippet haalt dezelfde categorieën uit het ROA-bestand (hier: de bevroren rijen), zonder de app.
    monkeypatch.setattr(roa, "load", lambda *a, **k: arbeidsmarkt._roa())
    ruimte: dict = {}
    exec("\n".join(snippet._laadregels(key)), ruimte)
    assert set(ruimte["df"]["detailniveau"]) == set(tabel["OPLEIDING"])


def test_uwv_bij_een_ho_onderdeel_zegt_dat_vacatures_geen_opleidingsniveau_hebben():
    uit = json.loads(get_uwv_vacatures("Flevoland", sector="GEDRAG_EN_MAATSCHAPPIJ"))

    assert uit["opleidingsniveau"].startswith("onbekend: UWV legt bij vacatures geen opleidingsniveau vast")
