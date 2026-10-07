"""Eén Nederlandse getalnotatie voor grafiek, KPI en controlemeldingen (#22, #378, #418)."""

import pytest

from tools.getal import nl_getal


@pytest.mark.parametrize(
    ("waarde", "decimalen", "tekst"),
    [
        (37221, None, "37.221"),
        (3303, None, "3.303"),
        (1234567.5, None, "1.234.567,5"),
        (2.1, None, "2,1"),
        (-8700, 0, "-8.700"),
        (12.345, 1, "12,3"),
        (999, None, "999"),
    ],
)
def test_punt_voor_duizendtallen_komma_voor_decimalen(waarde, decimalen, tekst):
    assert nl_getal(waarde, decimalen) == tekst
