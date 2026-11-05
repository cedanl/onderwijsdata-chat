"""De mbo-reeksen per instelling en de peers achter een regiogemiddelde (#923, #924, #925).

- #923: een mbo-instelling kan meer instellingscodes hebben (Curio: 21CY en 25LX). Eerstejaars, peers en rendement
  tellen over al haar codes, zoals de ingeschrevenen al deden.
- #924: de eerstejaars lopen even ver als wat DUO publiceert; een nieuw bestand bij CKAN valt op in de bron-ping.
- #925: een peer met alleen 0 of ontbrekende waarden telt niet mee in het gemiddelde en in `n_per_jaar`, maar staat
  wel in de payload, onder `geen_gegevens`.

De verwachte getallen zijn met pandas nagerekend uit de bevroren DUO-fixtures (#766), los van data/dashboard.py; de
getallen van Curio en BBO de Schalm staan ook in de dashboardaudit van 04-11-2026 (V-02, V-05, bijlage D).
"""

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from core.sentinels import mask_sentinels

# UWV en ROA uit fixtures (#915): het regiodashboard haalt ze anders live op.
pytestmark = pytest.mark.usefixtures("arbeidsmarkt_fixtures")

_CURIO = "Curio"
_SCHALM = "BBO de Schalm"
_TER_AA = "Ter AA"  # Noord-Brabant, met Curio als peer


def _duo(dataset_id: str, resource: int = 0) -> pd.DataFrame:
    from riodata import duo

    return mask_sentinels(duo.load(dataset_id, resource))[0]


def _instroom() -> pd.DataFrame:
    df = pd.concat([_duo("instromende-mbo-studenten", i) for i in dashboard._INSTROMENDE_MBO_HISTORISCH])
    return df[df["INSTROOM MBO"] == "J"]


def _codes(naam: str) -> set[str]:
    mbo = _duo("mbo-studenten-per-instelling")
    return set(mbo.loc[mbo["INSTELLINGSNAAM"] == naam, "INSTELLINGSCODE"].astype(str))


def _eerstejaars(naam: str) -> tuple[dict[int, int], dict[int, int]]:
    """({jaar: som}, {jaar: onderdrukte cellen}) over alle codes van de instelling."""
    rijen = _instroom()[_instroom()["INSTELLINGSCODE"].astype(str).isin(_codes(naam))]
    som = rijen.groupby("JAAR")["AANTAL"].sum(min_count=1).dropna()
    leeg = rijen.groupby("JAAR")["AANTAL"].apply(lambda s: int(s.isna().sum()))
    return {int(j): int(v) for j, v in som.items()}, {int(j): int(v) for j, v in leeg.items() if v}


# ─── #923: alle instellingscodes van een instelling ──────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("duo_fixtures")
def test_curio_telt_de_eerstejaars_van_beide_instellingscodes():
    result = dashboard.load_dashboard_regio(_CURIO)

    assert _codes(_CURIO) == {"21CY", "25LX"}
    # Audit V-02: 244 (21CY) + 4.696 (25LX) als ondergrens; eerder alleen de 244 van 21CY.
    assert result["eerstejaars"][2024] == 244 + 4696 == 4940
    assert result["onderdrukt"]["eerstejaars"][2024] == 37 + 213
    assert (result["eerstejaars"], result["onderdrukt"]["eerstejaars"]) == _eerstejaars(_CURIO)


@pytest.mark.usefixtures("duo_fixtures")
def test_elke_mbo_instelling_telt_de_eerstejaars_van_al_haar_codes():
    mbo = _duo("mbo-studenten-per-instelling")
    met_instroom = set(_instroom()["INSTELLINGSCODE"].astype(str))
    namen = sorted(set(mbo.loc[mbo["INSTELLINGSCODE"].astype(str).isin(met_instroom), "INSTELLINGSNAAM"]))
    assert _CURIO in namen and len(namen) >= 4

    for naam in namen:
        som, leeg = _eerstejaars(naam)
        regio = dashboard.load_dashboard_regio(naam)
        assert regio.get("eerstejaars", {}) == som, naam
        if som:  # zonder één waarde geen reeks, en dus ook geen lege cellen erbij (BBO de Schalm)
            assert regio.get("onderdrukt", {}).get("eerstejaars", {}) == leeg, naam
        rendement = dashboard.load_dashboard_rendement(naam)
        assert {c["instroom_jaar"]: c["instroom"] for c in rendement["pseudo_cohorten"]} == som, naam


@pytest.mark.usefixtures("duo_fixtures")
def test_een_peer_met_twee_codes_telt_als_een_peer_met_beide_codes():
    curio = dashboard.load_dashboard_regio(_CURIO)
    bm = dashboard.load_dashboard_regio(_TER_AA)["benchmark"]

    assert bm["peers"]["ingeschrevenen"][_CURIO] == curio["ingeschrevenen"]  # 15.288 in 2025, niet 901 van 21CY
    assert curio["ingeschrevenen"][2025] == 15288
    assert bm["peers"]["eerstejaars"][_CURIO] == curio["eerstejaars"]
    assert bm["peers"]["gediplomeerden"][_CURIO] == curio["gediplomeerden"]
    # Eerstejaars in de fixtures: Curio en SiNTLUCAS; BBO de Schalm heeft er geen.
    assert bm["n_per_jaar"]["eerstejaars"][2024] == 2
    assert bm["eerstejaars"][2024] == (4940 + 680) / 2

    rendement = dashboard.load_dashboard_rendement(_TER_AA)
    assert rendement["peers_rendement"][_CURIO] == dashboard.load_dashboard_rendement(_CURIO)["rendement_per_jaar"]


@pytest.mark.usefixtures("duo_fixtures")
def test_de_eigen_tweede_code_is_geen_peer():
    bm = dashboard.load_dashboard_regio(_CURIO)["benchmark"]

    for sleutel, peers in bm["peers"].items():
        assert _CURIO not in peers, sleutel


# ─── #924: de eerstejaars lopen tot het laatste jaar dat DUO publiceert ──────────────────────────────────────────────


@pytest.mark.usefixtures("duo_fixtures")
def test_de_eerstejaars_lopen_even_ver_als_de_ingeschrevenen():
    result = dashboard.load_dashboard_regio(_CURIO)
    bm = result["benchmark"]

    assert max(result["eerstejaars"]) == max(result["ingeschrevenen"]) == 2025
    assert max(bm["n_per_jaar"]["eerstejaars"]) == max(bm["n_per_jaar"]["ingeschrevenen"]) == 2025


def _ckan(*jaren: int) -> list[dict]:
    """De resourcelijst van instromende-mbo-studenten zoals CKAN hem geeft: per jaar hoofdgroep, dan soorten instroom."""
    namen = []
    for jaar in jaren:
        namen.append(f"{jaar} nieuw-instromende-studenten-per-instelling-hoofdgroep-leerweg-beroepsopleiding-niveau")
        namen.append(f"{jaar} nieuw-instromende-studenten-per-instelling-niveau-leerweg-met-soorten-instroom")
    return [{"naam": n} for n in namen]


def test_de_vaste_lijst_klopt_met_wat_ckan_nu_publiceert():
    with patch.object(dashboard.duo, "resources", return_value=_ckan(2021, 2022, 2023, 2024, 2025)) as resources:
        assert dashboard.instromende_mbo_afwijkingen() == []
    resources.assert_called_once_with("instromende-mbo-studenten")


def test_een_nieuw_jaar_bij_ckan_is_een_afwijking():
    with patch.object(dashboard.duo, "resources", return_value=_ckan(2021, 2022, 2023, 2024, 2025, 2026)):
        afwijkingen = dashboard.instromende_mbo_afwijkingen()

    assert len(afwijkingen) == 1
    assert "11" in afwijkingen[0] and "2026" in afwijkingen[0]


def test_een_verschoven_volgorde_bij_ckan_is_een_afwijking():
    verschoven = _ckan(2022, 2023, 2024, 2025)  # 2021 weg: elk bestand schuift twee plaatsen op
    with patch.object(dashboard.duo, "resources", return_value=verschoven):
        afwijkingen = dashboard.instromende_mbo_afwijkingen()

    assert afwijkingen == ["bestand 9 uit _INSTROMENDE_MBO_HISTORISCH is bij CKAN geen bestand met soorten instroom"]


def test_de_bronping_meldt_een_afwijking_in_de_instroombestanden():
    from scripts import bronping

    ping = next(p for p in bronping.PINGS if p.id == "duo-instroom-mbo")
    assert ping.bron == "duo"
    with patch.object(dashboard.duo, "resources", return_value=_ckan(2021, 2022, 2023, 2024, 2025, 2026)):
        uitslag = bronping.ping(ping)
    assert not uitslag.ok
    assert "2026" in uitslag.detail
    with patch.object(dashboard.duo, "resources", return_value=_ckan(2021, 2022, 2023, 2024, 2025)):
        assert bronping.ping(ping).ok


def test_de_fixtures_volgen_de_vaste_lijst():
    from scripts.duo_testfixtures import BESTANDEN

    vast = {i for (dataset, i) in BESTANDEN if dataset == "instromende-mbo-studenten"} - {0}
    assert vast == set(dashboard._INSTROMENDE_MBO_HISTORISCH)


# ─── #925: een peer zonder gegevens telt niet mee ────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("duo_fixtures")
def test_een_peer_met_vijf_jaar_nul_telt_niet_mee_in_het_gemiddelde():
    bm = dashboard.load_dashboard_regio(_CURIO)["benchmark"]

    # Audit V-05: (17.801 + 3.030 + 6.233 + 10.097 + 16.851 + 2.804) / 6, niet / 7 met de nul van BBO de Schalm.
    assert bm["ingeschrevenen"][2025] == 9469.3
    assert bm["n_per_jaar"]["ingeschrevenen"] == dict.fromkeys(range(2021, 2026), 6)
    assert bm["n_instellingen"] == 6
    assert bm["totaal_ingeschrevenen"][2025] == 56816
    # BBO de Schalm heeft elk jaar een onderdrukte cel; het gemiddelde van de zes is daardoor geen ondergrens.
    assert bm["onderdrukt"]["ingeschrevenen"] == {2021: 1, 2022: 1}  # SiNTLUCAS, Extraneus

    for sleutel in ("ingeschrevenen", "eerstejaars", "gediplomeerden"):
        assert _SCHALM not in bm["peers"][sleutel], sleutel
        assert bm["geen_gegevens"][sleutel] == [_SCHALM], sleutel
    assert bm["peers"]["gediplomeerden"]["SiNTLUCAS"][2025] > 0


def _peer_df(**reeksen: dict[int, float]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"CODE": naam, "NAAM": naam, "JAAR": j, "N": v} for naam, reeks in reeksen.items() for j, v in reeks.items()]
    )


def test_een_peer_met_een_echt_nuljaar_telt_wel_mee():
    nan = float("nan")
    df = _peer_df(
        A={2021: 0, 2022: 10},
        B={2021: 5, 2022: 5},
        C={2021: 0, 2022: nan},
    )

    reeks = dashboard._peer_reeks(df, "CODE", "NAAM", frozenset("ABC"), "JAAR", "N")

    assert reeks.gemiddelde == {2021: 2.5, 2022: 7.5}
    assert reeks.n_per_jaar == {2021: 2, 2022: 2}
    assert reeks.per_peer == {"A": {2021: 0, 2022: 10}, "B": {2021: 5, 2022: 5}}
    assert reeks.geen_gegevens == ["C"]
    assert reeks.leeg == {}  # de lege cel van C telt niet: C staat niet in het gemiddelde
    assert reeks.totaal == {2021: 5, 2022: 15}


def test_het_ho_gemiddelde_sluit_een_peer_zonder_gegevens_uit():
    def df(jaar_col, kolom):
        return pd.DataFrame(
            [
                {"CODE": c, "NAAM": n, jaar_col: j, kolom: v, "ONDERDEEL": "x"}
                for c, n, v in (("P1", "Peer 1", 100), ("P2", "Peer 2", 300), ("P0", "Leeg", 0))
                for j in (2024, 2025)
            ]
        )

    ctx = SimpleNamespace(peer_codes=frozenset({"P0", "P1", "P2"}), regio_type="provincie", regio_naam="Testland")
    bm = dashboard._ho_regio_benchmark(
        ctx,
        df("STUDIEJAAR", "AANTAL_INGESCHREVENEN"),
        df("STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"),
        df("DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"),
        "CODE",
        "NAAM",
    )

    for sleutel in ("ingeschrevenen", "eerstejaars", "gediplomeerden"):
        assert bm[sleutel] == {2024: 200.0, 2025: 200.0}, sleutel
        assert bm["n_per_jaar"][sleutel] == {2024: 2, 2025: 2}, sleutel
        assert bm["geen_gegevens"][sleutel] == ["Leeg"], sleutel
    assert set(bm["peers"]["ingeschrevenen"]) == set(bm["peers"]["gediplomeerden"]) == {"Peer 1", "Peer 2"}
    assert bm["n_instellingen"] == 2
