"""Een resourcenaam kiest nooit stilzwijgend het eerste van meerdere bestanden (#382).

Ketenaudit A2: 'Ingeschrevenen hoger beroepsonderwijs' paste op de bestanden met
geslacht, niveau en vorm; de resolver nam het eerste (geslacht). De data was geldig,
alleen de verkeerde uitsplitsing, dus geen controle achteraf zag het.
"""

from unittest.mock import patch

import pytest

from tools import duo

_BESTANDEN = [
    {"naam": "Ingeschrevenen hbo inclusief geslacht", "id": "uuid-geslacht"},
    {"naam": "Ingeschrevenen wo inclusief geslacht", "id": "uuid-wo"},
    {"naam": "Ingeschrevenen hbo niveau opleiding", "id": "uuid-niveau"},
    {"naam": "Ingeschrevenen hbo", "id": "uuid-hbo"},
]


def _index(resource, bestanden=_BESTANDEN):
    with patch.object(duo._duo, "resources", return_value=bestanden):
        return duo._resource_index("p01hoinges", resource)


def test_index_blijft_een_index():
    assert _index(2) == 2
    assert _index("3") == 3


def test_stabiel_resource_id():
    assert _index("uuid-niveau") == 2


def test_exacte_naam_gaat_voor_een_naamdeel():
    # 'Ingeschrevenen hbo' staat ook in bestand 0 en 2; de exacte naam is bestand 3.
    assert _index("ingeschrevenen HBO") == 3


def test_uniek_naamdeel():
    assert _index("niveau") == 2


def test_meervoudig_naamdeel_kiest_niet_en_noemt_de_opties():
    with pytest.raises(duo.MeerdereResources) as fout:
        _index("geslacht")
    assert "0 = 'Ingeschrevenen hbo inclusief geslacht'" in str(fout.value)
    assert "1 = 'Ingeschrevenen wo inclusief geslacht'" in str(fout.value)


def test_volgorde_van_de_resources_verandert_de_keuze_niet():
    omgekeerd = list(reversed(_BESTANDEN))
    assert _BESTANDEN[_index("uuid-niveau")] == omgekeerd[_index("uuid-niveau", omgekeerd)]
    assert _BESTANDEN[_index("niveau")] == omgekeerd[_index("niveau", omgekeerd)]


def test_onbekende_naam_blijft_voor_de_bron():
    assert _index("bestaat niet") == "bestaat niet"


def test_get_duo_data_laadt_niets_bij_meervoudige_treffer():
    with (
        patch.object(duo._duo, "resources", return_value=_BESTANDEN),
        patch.object(duo._duo, "load") as load,
    ):
        resultaat = duo.get_duo_data("p01hoinges", "geslacht")
    load.assert_not_called()
    assert "meerdere bestanden" in resultaat
