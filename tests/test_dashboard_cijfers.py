"""Dashboardcijfers heten wat ze tellen en tellen op zoals de chat (#899, #902, #903).

Elk verwacht getal is met pandas nagerekend uit dezelfde bevroren DUO-fixtures (#766), los van data/dashboard.py.
"""

import pandas as pd
import pytest

import data.dashboard as dashboard
from core import domeinregels
from core.sentinels import mask_sentinels

pytestmark = pytest.mark.usefixtures("duo_fixtures")

_MONDRIAAN = "ROC Mondriaan"


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
    snap = _duo("instromende-mbo-studenten")
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
    snap = _duo("instromende-mbo-studenten")
    ingeschreven = snap[snap["INSTELLINGSNAAM"] == _MONDRIAAN].groupby("HOOFDGROEP NAAM")["TOTAAL MBO"].sum()
    assert sum(verwacht.values()) < ingeschreven.sum() / 2, "het aanbod is niet meer het aantal ingeschrevenen"


@pytest.mark.parametrize("laden", [dashboard.load_dashboard_regio, dashboard.load_dashboard])
def test_de_leerwegen_tellen_op_tot_het_totaal_ingeschrevenen(laden):
    result = laden(_MONDRIAAN)

    laatste = result["laatste_jaar"]
    assert "Extraneus" in result["sectoren"]
    assert sum(result["sectoren"].values()) == result["ingeschrevenen"][laatste]


def test_regio_en_instellingsdashboard_geven_dezelfde_mbo_verdeling():
    regio = dashboard.load_dashboard_regio(_MONDRIAAN)
    instelling = dashboard.load_dashboard(_MONDRIAAN)

    assert regio["sectoren"] == instelling["sectoren"]
    assert regio["ingeschrevenen"] == instelling["ingeschrevenen"]
    assert regio["gediplomeerden"] == instelling["gediplomeerden"]
    for jaar, per_leerweg in regio["leerwegen"].items():
        assert set(per_leerweg) == {"BBL", "BOL voltijd", "BOL deeltijd", "Extraneus"}
        assert sum(per_leerweg.values()) == regio["ingeschrevenen"][jaar]
