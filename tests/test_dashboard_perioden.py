"""Het soort jaar per reeks in de dashboards (#904, #847): een schooljaar (2025/26) of een diplomajaar (CH-41).

Eerder gingen STUDIEJAAR, DIPLOMAJAAR en het mbo-JAAR als kaal jaartal naar de frontend: op één pagina betekende
"2025" zowel schooljaar 2025/26 (ingeschrevenen) als diplomajaar 2025 (gediplomeerden).
"""

import pytest

import data.dashboard as dashboard
from tools import periode

pytestmark = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")

_HU = "Hogeschool Utrecht"
_MONDRIAAN = "ROC Mondriaan"


@pytest.mark.parametrize("kolom", ["STUDIEJAAR", "JAAR"])
def test_een_duo_periodekolom_is_een_schooljaar(kolom):
    assert periode.jaarsoort(kolom) == periode.SCHOOLJAAR == "schooljaar"


def test_een_diplomajaar_blijft_een_diplomajaar():
    # De chat zet diplomajaar 2023 niet om naar studiejaar 2023/24 (domeinregel p04-diplomajaar); het dashboard ook niet.
    assert "DIPLOMAJAAR" in periode.GEEN_SCHOOLJAAR
    assert periode.jaarsoort("DIPLOMAJAAR") == "diplomajaar"


def test_een_onbekende_jaarkolom_krijgt_geen_soort():
    with pytest.raises(ValueError, match="AANTAL"):
        periode.jaarsoort("AANTAL")


@pytest.mark.parametrize(
    ("lader", "instelling"),
    [
        (dashboard.load_dashboard_regio, _HU),
        (dashboard.load_dashboard_regio, _MONDRIAAN),
        (dashboard.load_dashboard_rendement, _HU),
        (dashboard.load_dashboard_rendement, _MONDRIAAN),
        (dashboard.load_dashboard_nationaal, _HU),
        (dashboard.load_dashboard_arbeidsmarktmatch, _HU),
    ],
)
def test_elk_dashboard_zegt_welk_soort_jaar_zijn_reeksen_hebben(lader, instelling):
    result = lader(instelling)

    assert result["gevonden"] is True
    assert result["perioden"] == {
        "ingeschrevenen": "schooljaar",
        "eerstejaars": "schooljaar",
        "cohorten": "schooljaar",
        "gediplomeerden": "diplomajaar",
    }


def test_een_onbekende_instelling_krijgt_geen_perioden():
    result = dashboard.load_dashboard_regio("Hogeschool Nergenshuizen")

    assert result["gevonden"] is False
    assert "perioden" not in result
