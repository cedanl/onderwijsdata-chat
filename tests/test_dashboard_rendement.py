"""Het "rendement" in Mijn instelling (#898): wat de tegel betekent, niet alleen hoe hij rekent.

Besluit 05-11: mbo houdt de tegel, als wat hij is: de mbo-diploma's van een instelling drie jaar na het cohort, gedeeld
door haar eerstejaars van dat cohort, met de definitie en wat niet meetelt (zoals het rapport, #736/#743). De instelling
en het regiogemiddelde rekenen met dezelfde regel over dezelfde cohorten, en een cohort dat afvalt, wordt genoemd.
Hbo en wo krijgen geen tegel tot er een echte cohortbron is, alleen de reden en waar het wel kan.

De verwachte getallen zijn met pandas nagerekend uit de bevroren DUO-fixtures (#766), los van data/dashboard.py.
"""

from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from core import domeinregels
from core.sentinels import mask_sentinels
from tools import duo_meta

pytestmark = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")

_CURIO = "Curio"
_TER_AA = "Ter AA"  # Noord-Brabant, zonder eerstejaars in de fixtures; Curio is een peer
_MBO = [_CURIO, "ROC Mondriaan", "Albeda", "Zadkine", "SiNTLUCAS", _TER_AA]
_TERMIJN = 3


def _duo(dataset_id: str, resource: int = 0) -> pd.DataFrame:
    from onderwijsbronnen import duo

    return mask_sentinels(duo.load(dataset_id, resource))[0]


def _codes(naam: str) -> set[str]:
    mbo = _duo("mbo-studenten-per-instelling")
    return set(mbo.loc[mbo["INSTELLINGSNAAM"] == naam, "INSTELLINGSCODE"].astype(str))


def _eerstejaars(naam: str) -> dict[int, int]:
    """Nieuw in het mbo (INSTROOM MBO = J), over alle codes van de instelling."""
    df = pd.concat([_duo("instromende-mbo-studenten", i) for i in dashboard._INSTROMENDE_MBO_HISTORISCH])
    rijen = df[(df["INSTROOM MBO"] == "J") & df["INSTELLINGSCODE"].astype(str).isin(_codes(naam))]
    return {int(j): int(v) for j, v in rijen.groupby("JAAR")["AANTAL"].sum(min_count=1).dropna().items()}


def _diplomas(naam: str) -> dict[int, int]:
    """De diploma's per diplomajaar (de kolommen DIPMAN2024 en DIPVROUW2024 samen), over alle codes."""
    df = _duo("gediplomeerde-mbo-studenten")
    rijen = df[df["INSTELLINGSCODE"].astype(str).isin(_codes(naam))]
    per_jaar: dict[int, int] = {}
    for kolom in (k for k in df.columns if k.startswith("DIP")):
        if rijen[kolom].notna().any():
            per_jaar[int(kolom[-4:])] = per_jaar.get(int(kolom[-4:]), 0) + int(rijen[kolom].sum())
    return per_jaar


# ─── mbo: wat de verhouding is ─────────────────────────────────────────────────────────────────────────────────────


def test_curio_deelt_de_diplomas_drie_jaar_later_door_de_eerstejaars_van_het_cohort():
    result = dashboard.load_dashboard_rendement(_CURIO)
    ej, dipl = _eerstejaars(_CURIO), _diplomas(_CURIO)

    # #923: de eerstejaars van beide codes (21CY en 25LX), niet alleen die van 21CY.
    assert ej[2021] == 4459 and dipl[2024] == 4037
    assert (
        result["rendement_per_jaar"]
        == {c: round(dipl[c + _TERMIJN] / ej[c], 4) for c in (2021, 2022)}
        == {2021: 0.9054, 2022: 0.9042}
    )
    assert result["definitie"]["termijn"] == _TERMIJN
    assert f"na {_TERMIJN} jaar" in result["definitie"]["naam"]
    # De tabel en de tegel gebruiken dezelfde termijn: de KPI leest gediplomeerden_t{termijn}.
    cohort_2021 = next(c for c in result["pseudo_cohorten"] if c["instroom_jaar"] == 2021)
    assert cohort_2021[f"gediplomeerden_t{_TERMIJN}"] == 4037 and cohort_2021["instroom"] == 4459
    for cohort in result["pseudo_cohorten"]:
        assert cohort["instroom"] == ej[cohort["instroom_jaar"]]
        for t in (3, 4, 5):
            # Een diplomajaar dat er (nog) niet is, is None, geen 0 (#902).
            assert cohort[f"gediplomeerden_t{t}"] == dipl.get(cohort["instroom_jaar"] + t)


@pytest.mark.parametrize("naam", _MBO)
def test_instelling_en_peers_rekenen_met_dezelfde_regel_over_dezelfde_cohorten(naam):
    echte_regel = dashboard._rendement
    aanroepen: list[tuple] = []

    def regel(cohorten, instroom, dipl):
        aanroepen.append((tuple(cohorten), instroom, dipl))
        return echte_regel(cohorten, instroom, dipl)

    with patch.object(dashboard, "_rendement", regel):
        result = dashboard.load_dashboard_rendement(naam)

    peers = set(result["peers_rendement"]) | set(result["peers_weggelaten"])
    assert len(aanroepen) == 1 + len(peers)  # de instelling en elke peer, door dezelfde functie
    assert len({cohorten for cohorten, _, _ in aanroepen}) == 1  # over dezelfde cohorten
    for peer in result["peers_rendement"]:
        # Elke peer zoals de instelling zelf: wie peer is, krijgt hetzelfde cijfer als op zijn eigen dashboard.
        if peer in _MBO:
            assert result["peers_rendement"][peer] == dashboard.load_dashboard_rendement(peer)["rendement_per_jaar"]


@pytest.mark.parametrize("naam", _MBO)
def test_elk_cohort_met_een_diplomajaar_heeft_een_verhouding_of_een_reden(naam):
    result = dashboard.load_dashboard_rendement(naam)
    cohorten = {2021, 2022}  # eerstejaars 2021-2025, diploma's t/m 2025: alleen 2021 en 2022 hebben er een na 3 jaar

    assert set(result["rendement_per_jaar"]) | set(result["weggelaten"]) == cohorten
    assert not set(result["rendement_per_jaar"]) & set(result["weggelaten"])
    for peer, weg in result["peers_weggelaten"].items():
        assert set(result["peers_rendement"].get(peer, {})) | set(weg) == cohorten, peer


def test_een_instelling_zonder_eerstejaars_zegt_waarom_er_geen_verhouding_staat():
    result = dashboard.load_dashboard_rendement(_TER_AA)

    assert result["rendement_per_jaar"] == {}
    assert result["weggelaten"] == {2021: dashboard._GEEN_EERSTEJAARS, 2022: dashboard._GEEN_EERSTEJAARS}
    assert result["definitie"] == dashboard._RENDEMENT_MBO  # de uitleg staat er ook zonder één cohort


def test_het_regiogemiddelde_is_het_gemiddelde_van_de_peers_met_hun_aantal_en_label():
    result = dashboard.load_dashboard_rendement(_TER_AA)
    peers = result["peers_rendement"]

    assert set(peers) == {_CURIO, "SiNTLUCAS"}
    for cohort in (2021, 2022):
        waarden = [p[cohort] for p in peers.values() if cohort in p]
        assert result["benchmark_rendement"][cohort] == round(sum(waarden) / len(waarden), 4)
        assert result["benchmark_n_per_jaar"][cohort] == len(waarden)
    assert result["benchmark_label"].startswith("Provincie Noord-Brabant, ")  # label van de vergelijkingsgroep (#926)
    assert "BBO de Schalm" in result["peers_weggelaten"]  # een peer zonder eerstejaars valt niet stil weg


def test_het_label_telt_de_peers_in_het_gemiddelde_niet_de_gevonden():
    # F1 (#951): Curio heeft 7 andere mbo-instellingen in Noord-Brabant; live heeft BBO de Schalm geen eerstejaars en
    # valt af. De kerncijfers zeiden "6 andere", de rendementgrafiek "7 andere" met 6 in de legenda. In de bevroren
    # fixtures hebben minder peers een verhouding; het label telt er net zoveel als het gemiddelde.
    result = dashboard.load_dashboard_rendement(_CURIO)
    vergeleken = result["peers_rendement"]

    assert "BBO de Schalm" in result["peers_weggelaten"] and "BBO de Schalm" not in vergeleken
    assert len(vergeleken) == max(result["benchmark_n_per_jaar"].values())
    soort = "mbo-instelling" if len(vergeleken) == 1 else "mbo-instellingen"
    assert result["benchmark_label"].startswith(f"Provincie Noord-Brabant, {len(vergeleken)} andere {soort}")
    # De legenda noemt de groep, zonder aantal en terugvalreden.
    assert result["benchmark_populatie"] == "mbo-instellingen in provincie Noord-Brabant"


def test_de_definitie_zegt_dat_teller_en_noemer_ondergrenzen_zijn():
    # F4 (#951): DUO laat cellen met 1 tot en met 4 studenten leeg, in de teller en in de noemer.
    definitie = str(dashboard._RENDEMENT_MBO["definitie"])

    assert "Teller en noemer zijn ondergrenzen" in definitie
    assert "1 tot en met 4" in definitie
    assert "eerder te laag dan te hoog" in definitie


def test_meer_diplomas_dan_eerstejaars_is_geen_verhouding_maar_een_reden():
    rendement, weggelaten = dashboard._rendement(
        [2020, 2021, 2022, 2023],
        {2020: 100, 2021: 100, 2022: 100},
        {
            2023: 140,  # cohort 2020: meer diploma's dan eerstejaars
            2024: 90,
            2025: 0,  # cohort 2022: 0 is geen verhouding van 0 %, want lege cellen tellen niet mee
        },
    )

    assert rendement == {2021: 0.9}
    assert weggelaten == {
        2020: dashboard._TE_VEEL_DIPLOMAS,
        2022: dashboard._GEEN_DIPLOMAS,
        2023: dashboard._GEEN_EERSTEJAARS,
    }
    # Dezelfde regel voor het gemiddelde: een peer boven 1 telt niet mee, dus het gemiddelde komt nooit boven 1.
    gemiddelde, n = dashboard._benchmark_rendement({"A": rendement, "B": {2020: 0.5, 2021: 0.7}})
    assert gemiddelde == {2020: 0.5, 2021: 0.8} and n == {2020: 1, 2021: 2}


# ─── mbo: de definitie rust op wat DUO zegt ────────────────────────────────────────────────────────────────────────


def test_wat_niet_meetelt_staat_in_de_teldefinities_van_duo():
    niet = str(dashboard._RENDEMENT_MBO["niet_meegeteld"])
    instroom = duo_meta.teldefinitie(duo_meta.record("instromende-mbo-studenten")) or ""
    diplomas = duo_meta.teldefinitie(duo_meta.record("gediplomeerde-mbo-studenten")) or ""
    instroom_mbo = next(r for r in domeinregels.laad().kolomcorrecties if r.id == "mbo-instroom-mbo")

    # "wie een jaar eerder al in het mbo stond ingeschreven"
    assert "een jaar eerder geen mbo-inschrijving" in instroom_mbo.definitie and "een jaar eerder" in niet
    # "een tweede inschrijving van dezelfde student" / "een tweede diploma van dezelfde student"
    assert "per student 1 inschrijving" in instroom and "tweede inschrijving" in niet
    assert "per student 1 diploma" in diplomas and "tweede diploma" in niet
    # "cellen met 1 tot en met 4 studenten, die DUO leeg laat"
    assert "kleine aantallen (1, 2, 3, of 4)" in instroom and "1 tot en met 4" in niet


# ─── hbo en wo: geen tegel, wel de reden ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("naam", ["Hogeschool Utrecht", "Universiteit Utrecht"])
def test_hbo_en_wo_krijgen_geen_rendement_maar_de_reden_en_waar_het_wel_kan(naam):
    result = dashboard.load_dashboard_rendement(naam)

    assert result["gevonden"] is True and result["type"] == "ho"
    assert result["geen_rendement"] == dashboard._GEEN_RENDEMENT_HO
    assert "chat" in result["geen_rendement"] and "rapport" in result["geen_rendement"]
    for sleutel in ("rendement_per_jaar", "benchmark_rendement", "peers_rendement", "pseudo_cohorten", "definitie"):
        assert sleutel not in result
    # Het ho-bestand waarin de naam staat, draagt geen getal: het bronblok noemt het niet.
    assert result["bronnen"] == []
