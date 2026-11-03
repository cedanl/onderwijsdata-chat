"""Een door CBS afgekapte titel krijgt zijn volledige naam terug (#895).

CBS kapt de Title van een dimensiewaarde zelf af op circa 40 tekens ("04 Recht, administratie, handel en za…"). De
volledige naam staat als eerste regel of zin van de Description. Zonder die naam toonde een grafiek de afkorting.
"""

import json
from unittest.mock import patch

from tools import cbs
from tools.cbs import get_cbs_dimension

_STUDIERICHTING = [
    {"Key": "A010289", "Title": "01 Onderwijs", "Description": "Het gaat hierbij om lerarenopleidingen."},
    {
        "Key": "A010293",
        "Title": "02 Vormgeving, kunst, talen en gesch... ",
        "Description": "Vormgeving, kunst, talen en geschiedenis. Het gaat hier onder meer om grafische vormgeving.",
    },
    {
        "Key": "A010290",
        "Title": "04 Recht, administratie, handel en za…",
        "Description": "Recht, administratie, handel en zakelijke dienstverlening.\r\n\r\nHet gaat hier om recht.",
    },
    {
        "Key": "A028037",
        "Title": "0212 Mode-, interieur- en industriële...",
        "Description": "Mode-, interieur- en industriële vormgeving\r\n\r\nDit omvat het onderwijs in de richting mode.",
    },
    {"Key": "A099", "Title": "09 Iets onbekends...", "Description": "Totaal ander verhaal zonder dezelfde woorden."},
    {"Key": "A098", "Title": "020 Vormgeving, kunst, talen… z.n.d.", "Description": "Brede programma's."},
    {"Key": "A097", "Title": "07 Techniek...", "Description": None},
]


def _titels() -> dict[str, str]:
    cbs._dimension_rows.cache_clear()
    with patch("tools.cbs.get", return_value=_STUDIERICHTING):
        return {r["Key"]: r["Title"] for r in cbs._dimension_rows("85421NED", "Studierichting")}


def test_een_afgekapte_titel_krijgt_zijn_volledige_naam_uit_de_omschrijving():
    titels = _titels()

    assert titels["A010293"] == "02 Vormgeving, kunst, talen en geschiedenis"
    assert titels["A010290"] == "04 Recht, administratie, handel en zakelijke dienstverlening"
    assert titels["A028037"] == "0212 Mode-, interieur- en industriële vormgeving"


def test_een_titel_zonder_afkapping_of_zonder_passende_omschrijving_blijft_zoals_hij_is():
    titels = _titels()

    assert titels["A010289"] == "01 Onderwijs"
    assert titels["A099"] == "09 Iets onbekends..."
    assert titels["A098"] == "020 Vormgeving, kunst, talen… z.n.d."
    assert titels["A097"] == "07 Techniek..."


def test_get_cbs_dimension_toont_de_volledige_naam():
    cbs._dimension_rows.cache_clear()
    with (
        patch("tools.cbs.get", return_value=_STUDIERICHTING),
        patch("tools.cbs.scope_blokkade", return_value=None),
    ):
        waarden = json.loads(get_cbs_dimension("85421NED", "Studierichting"))

    assert waarden["A010290"] == "04 Recht, administratie, handel en zakelijke dienstverlening"
