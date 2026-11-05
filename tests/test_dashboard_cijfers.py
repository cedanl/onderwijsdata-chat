"""Dashboardcijfers heten wat ze tellen en tellen op zoals de chat (#899, #902, #903).

Elk verwacht getal is met pandas nagerekend uit dezelfde bevroren DUO-fixtures (#766), los van data/dashboard.py.
"""

import pandas as pd
import pytest

import data.dashboard as dashboard
from core import domeinregels
from core.sentinels import mask_sentinels

# UWV en ROA uit fixtures (#915): de regio- en arbeidsmarktdashboards halen ze anders live op.
pytestmark = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")

_MONDRIAAN = "ROC Mondriaan"
_HOOFDGROEP_2025 = 8  # het hoofdgroep-bestand van instromende-mbo-studenten van 2025, het laatste jaar (#934)


def _duo(dataset_id: str, resource: int = 0) -> pd.DataFrame:
    from riodata import duo

    return mask_sentinels(duo.load(dataset_id, resource))[0]


# ─── #899: TOTAAL MBO is ingeschrevenen, geen eerstejaars of gediplomeerden ──────────────────────────────────────────


def test_de_hoofdgroepsom_telt_ingeschrevenen_zoals_de_domeinregel_zegt():
    regel = next(r for r in domeinregels.laad().kolomcorrecties if r.id == "mbo-instroom-totaal-mbo")
    assert regel.kolom == dashboard._MBO_INGESCHREVEN_KOLOM
    assert "ingeschreven" in regel.definitie and "geen instroom" in regel.definitie

    result = dashboard.load_dashboard_regio(_MONDRIAAN)

    assert "sectorkamers" not in result  # heette "sectorkamers" en stond in de UI als eerstejaars
    snap = _duo("instromende-mbo-studenten", _HOOFDGROEP_2025)
    per_hoofdgroep = snap[snap["INSTELLINGSNAAM"] == _MONDRIAAN].groupby("HOOFDGROEP NAAM")["TOTAAL MBO"].sum()
    verwacht = {k: int(v) for k, v in per_hoofdgroep.sort_values(ascending=False).items() if v > 0}
    assert len(verwacht) > 5
    assert result["ingeschrevenen_per_hoofdgroep"] == verwacht
    assert list(result["ingeschrevenen_per_hoofdgroep"]) == list(verwacht)  # aflopend


def test_de_arbeidsmarktmatch_mbo_telt_gediplomeerden_per_hoofdgroep():
    dipl = _duo("gediplomeerde-mbo-studenten")
    rijen = dipl[dipl["INSTELLINGSNAAM"] == _MONDRIAAN]
    # Diploma's per hoofdgroep in de laatste drie diplomajaren (2023-2025), man en vrouw samen, gemiddeld.
    per_jaar = pd.DataFrame(
        {jaar: rijen[f"DIPMAN{jaar}"].fillna(0) + rijen[f"DIPVROUW{jaar}"].fillna(0) for jaar in (2023, 2024, 2025)}
    )
    gem = per_jaar.groupby(rijen["HOOFDGROEP NAAM"]).sum().mean(axis=1)
    verwacht = {k: int(round(v)) for k, v in gem.items() if v > 0}  # noqa: RUF046

    result = dashboard.load_dashboard_arbeidsmarktmatch(_MONDRIAAN)

    assert result["gediplomeerden_per_sector"] == verwacht
    snap = _duo("instromende-mbo-studenten", _HOOFDGROEP_2025)
    ingeschreven = snap[snap["INSTELLINGSNAAM"] == _MONDRIAAN].groupby("HOOFDGROEP NAAM")["TOTAAL MBO"].sum()
    assert sum(verwacht.values()) < ingeschreven.sum() / 2, "het aanbod is niet meer het aantal ingeschrevenen"


def test_de_leerwegen_tellen_op_tot_het_totaal_ingeschrevenen():
    regio = dashboard.load_dashboard_regio(_MONDRIAAN)

    laatste = regio["laatste_jaar"]
    assert "Extraneus" in regio["sectoren"]
    assert sum(regio["sectoren"].values()) == regio["ingeschrevenen"][laatste]
    for jaar, per_leerweg in regio["leerwegen"].items():
        assert set(per_leerweg) == {"BBL", "BOL voltijd", "BOL deeltijd", "Extraneus"}
        assert sum(per_leerweg.values()) == regio["ingeschrevenen"][jaar]


# ─── #902: een onderdrukte of ontbrekende cel is geen 0 ─────────────────────────────────────────────────────────────


def test_een_reeks_telt_onderdrukte_cellen_niet_mee_en_meldt_ze():
    ruw = pd.DataFrame({"JAAR": [2023, 2023, 2024, 2025], "AANTAL": [10, -1, -1, 5]})
    som, leeg = dashboard._reeks(mask_sentinels(ruw)[0], "JAAR", "AANTAL")

    assert som == {2023: 10, 2025: 5}  # 2024 heeft alleen een onderdrukte cel: een gat, geen 0
    assert leeg == {2023: 1, 2024: 1}  # 2023 is een ondergrens


def _mbo_rij(jaar, naam, code, bbl, boldt, bolvt, ex):
    return {
        "JAAR": jaar,
        "PROVINCIE INSTELLING": "Zuid-Holland",
        "INSTELLINGSNAAM": naam,
        "INSTELLINGSCODE": code,
        "BBL": bbl,
        "BOLDT": boldt,
        "BOLVT": bolvt,
        "EX": ex,
    }


@pytest.fixture
def mbo_studenten(monkeypatch):
    """Vervangt alleen mbo-studenten-per-instelling; de rest komt uit de fixtures van duo_fixtures."""
    from riodata import duo

    fixtures = duo.load
    rijen: list[dict] = []

    def load(dataset_id: str, resource: int = 0, **kwargs):
        if dataset_id == "mbo-studenten-per-instelling":
            return pd.DataFrame(rijen)
        return fixtures(dataset_id, resource, **kwargs)

    monkeypatch.setattr(duo, "load", load)
    for functie in vars(dashboard).values():
        if hasattr(functie, "cache_clear"):
            functie.cache_clear()
    return rijen


def test_het_mbo_dashboard_meldt_onderdrukte_cellen_en_laat_een_leeg_jaar_weg(mbo_studenten):
    mbo_studenten += [
        _mbo_rij(2023, "Grafisch Lyceum", "1", 300, -1, 2000, -1),
        _mbo_rij(2024, "Grafisch Lyceum", "1", -1, -1, -1, -1),
        _mbo_rij(2025, "Grafisch Lyceum", "1", 310, 0, 2100, 5),
    ]

    result = dashboard.load_dashboard_regio("Grafisch Lyceum")

    assert result["gevonden"] is True
    assert result["ingeschrevenen"] == {2023: 2300, 2025: 2415}
    assert result["onderdrukt"]["ingeschrevenen"] == {2023: 2, 2024: 4}
    assert result["leerwegen"][2023] == {"BBL": 300, "BOL voltijd": 2000}  # geen 0 voor de onderdrukte leerwegen
    assert result["leerwegen"].get(2024, {}) == {}


def test_landelijk_meldt_ondergrens_onzekere_positie_en_weggelaten_sectoren(mbo_studenten):
    mbo_studenten += [
        _mbo_rij(2025, "Instelling A", "A", 500, 0, -1, 3),
        _mbo_rij(2025, "Instelling B", "B", -1, 0, 1000, 2),
    ]

    result = dashboard.load_dashboard_nationaal("Instelling A")

    assert result["type"] == "mbo"
    assert result["alle_instellingen"] == [
        {"naam": "Instelling B", "ingeschrevenen": 1002, "type": "mbo", "onderdrukt": 1},
        {"naam": "Instelling A", "ingeschrevenen": 503, "type": "mbo", "onderdrukt": 1},
    ]
    # BBL: B is onderdrukt, dus A staat eerste, maar dat kan verschuiven; EX: 3 tegen 2, zeker.
    assert result["eigen_positie"] == {"BBL": 1, "EX": 1}
    assert result["onderdrukt"]["eigen_positie"] == {"BBL": 1}
    # BOLVT: A onderdrukt; BOLDT: A heeft 0. Geen positie, wel genoemd.
    assert sorted(result["positie_weggelaten"]) == ["BOLDT", "BOLVT"]
    assert result["sectoren_landelijk"]["BOLVT"] == {2025: 1000}
    assert result["onderdrukt"]["sectoren_landelijk"] == {"BBL": {2025: 1}, "BOLVT": {2025: 1}}


def test_een_pseudocohort_zonder_diplomajaar_is_none_geen_nul():
    cohorten = dashboard._pseudo_cohorten({2023: 100, 2024: 120}, {2026: 60})

    assert cohorten[0] == {
        "instroom_jaar": 2023,
        "instroom": 100,
        "gediplomeerden_t3": 60,
        "gediplomeerden_t4": None,
        "gediplomeerden_t5": None,
    }
    assert cohorten[1]["gediplomeerden_t3"] is None
    assert dashboard._rendement([2023], {2023: 100, 2024: 120}, {2026: 60}) == ({2023: 0.6}, {})


def test_een_sector_zonder_inschrijvingen_in_een_jaar_is_een_gat_in_de_trend():
    result = dashboard.load_dashboard_regio("Hogeschool Utrecht")

    ins = pd.concat([_duo("p01hoinges", 0), _duo("p01hoinges", 1)])
    hu = ins[ins["INSTELLINGSNAAM_ACTUEEL"] == "Hogeschool Utrecht"]
    for onderdeel, trend in result["sectoren_trend"].items():
        jaren = set(hu.loc[hu["ONDERDEEL"] == onderdeel, "STUDIEJAAR"].astype(int))
        assert set(trend) <= jaren, onderdeel  # geen jaar dat in de data ontbreekt, ook niet als 0


# ─── #903: dashboard en chat, en het aantal peers achter een gemiddelde ─────────────────────────────────────────────


def _per_jaar(uit: str) -> dict[int, int]:
    import json

    rijen = json.loads(uit)
    assert "data_key" in rijen, rijen
    return {int(r[rijen["periodekolom"]]): int(r[rijen["waardekolom"]]) for r in rijen["rijen"]}


def test_landelijk_is_de_duo_som_en_noemt_de_vaste_maat_van_de_chat():
    """Het bewuste verschil: het dashboard telt DUO per instelling op, de chat neemt de vaste CBS-maat (#805)."""
    from tools import maten

    for sector, maat in (("mbo", maten.MBO_STUDENTEN_LANDELIJK), ("ho", maten.DEELNEMERS_HO_LANDELIJK)):
        recept = maten.MATEN[maat]
        bron = dashboard._LANDELIJK[sector]
        assert bron["chat_maat"] == maat
        assert bron["chat_dataset"] == recept.dataset
        assert recept.bron == "cbs"
        # De DUO-som is het DUO-bestand dat de chat per instelling gebruikt.
        assert bron["dataset"] == maten.MATEN[maten._PER_INSTELLING[maat]].dataset
    # Voor het mbo noemt de chat precies dit bestand als alternatieve bron onder het antwoord (#667).
    recept = maten.MATEN[maten.MBO_STUDENTEN_LANDELIJK]
    assert isinstance(recept, maten.CbsRecept)
    alternatief = recept.alternatieve_bron
    assert alternatief is not None
    assert alternatief.dataset == dashboard._LANDELIJK["mbo"]["dataset"]

    for instelling, sector in (("Hogeschool Utrecht", "ho"), (_MONDRIAAN, "mbo")):
        landelijk = dashboard.load_dashboard_nationaal(instelling)["landelijk"]
        assert landelijk["maat"] == "duo_som_per_instelling"
        assert landelijk["chat_dataset"] in landelijk["verschil_met_chat"]
        assert dashboard._LANDELIJK[sector]["dataset"] in landelijk["definitie"]


@pytest.mark.usefixtures("gouden")
def test_een_mbo_instelling_heeft_in_dashboard_en_chat_hetzelfde_aantal():
    from tools import maten
    from tools.maten import get_maat

    chat = _per_jaar(get_maat(maten.MBO_STUDENTEN, _MONDRIAAN))
    regio = dashboard.load_dashboard_regio(_MONDRIAAN)
    nationaal = dashboard.load_dashboard_nationaal(_MONDRIAAN)

    assert regio["ingeschrevenen"] == chat
    eigen = next(i for i in nationaal["alle_instellingen"] if i["naam"] == _MONDRIAAN)
    assert eigen["ingeschrevenen"] == chat[nationaal["laatste_jaar"]]


@pytest.mark.usefixtures("gouden")
def test_een_ho_instelling_wijkt_alleen_af_waar_het_dashboard_een_ondergrens_meldt():
    """Bewust verschil: het dashboard telt p01hoinges per onderdeel en geslacht, de chat het bestand met
    opleidingsvorm (bestand 4). Elk onderdrukt andere cellen; een verschil valt dus in een jaar dat het dashboard als
    ondergrens meldt, en is klein."""
    from tools import maten
    from tools.maten import get_maat

    uu = "Universiteit Utrecht"
    chat = _per_jaar(get_maat(maten.PERSONEN_HO, uu, vorm="alle"))
    regio = dashboard.load_dashboard_regio(uu)

    assert set(regio["ingeschrevenen"]) == set(chat)
    verschil = {j: chat[j] - regio["ingeschrevenen"][j] for j in chat if chat[j] != regio["ingeschrevenen"][j]}
    assert verschil, "de bestanden onderdrukken andere cellen; is dat veranderd, pas dan de test en docs aan"
    for jaar, d in verschil.items():
        assert regio["onderdrukt"]["ingeschrevenen"].get(jaar), jaar
        # Een onderdrukte cel is 1 tot en met 4; het bestand van de chat onderdrukt hier één cel (test_gouden_maten).
        assert abs(d) <= 4 * regio["onderdrukt"]["ingeschrevenen"][jaar] + 4, (jaar, d)


def test_het_aantal_peers_staat_per_jaar_en_telt_alleen_peers_met_data():
    result = dashboard.load_dashboard_regio(_MONDRIAAN)
    bm = result["benchmark"]

    mbo = _duo("mbo-studenten-per-instelling")
    ctx = dashboard._build_regio_context(_MONDRIAAN, "mbo")
    assert ctx is not None
    peers = mbo[mbo["INSTELLINGSCODE"].isin(ctx.peer_codes)]
    verwacht = {int(j): int(n) for j, n in peers.groupby("JAAR")["INSTELLINGSCODE"].nunique().items()}
    assert bm["n_per_jaar"]["ingeschrevenen"] == verwacht
    assert bm["n_instellingen"] == verwacht[max(verwacht)]
    assert bm["n_instellingen"] <= len(ctx.peer_codes)
    assert set(bm["n_per_jaar"]["eerstejaars"]) == set(bm["eerstejaars"])
