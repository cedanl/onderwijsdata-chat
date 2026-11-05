"""De mbo-reeksen per instelling en de peers achter een regiogemiddelde (#923, #924, #925).

- #923: een mbo-instelling kan meer instellingscodes hebben (Curio: 21CY en 25LX). Eerstejaars, peers en rendement
  tellen over al haar codes, zoals de ingeschrevenen al deden.
- #924: de eerstejaars lopen even ver als wat DUO publiceert; een nieuw bestand bij CKAN valt op in de bron-ping.
- #925: een peer met alleen 0 of ontbrekende waarden telt niet mee in het gemiddelde en in `n_per_jaar`, maar staat
  wel in de payload, onder `geen_gegevens`.

De verwachte getallen zijn met pandas nagerekend uit de bevroren DUO-fixtures (#766), los van data/dashboard.py; de
getallen van Curio en BBO de Schalm staan ook in de dashboardaudit van 04-11-2026 (V-02, V-05, bijlage D).
"""

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
