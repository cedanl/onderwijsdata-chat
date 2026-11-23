"""De onderdelen van de regiokaart (#1079): ondergrond, plaatsen met meer instellingen, bereik en labelplek."""

import pytest

from data import kaart_regio
from data.kaart_regio import Groep, bereik, groepeer, labelpositie, ondergrond

UTRECHT = (52.091, 5.114)
HAAG = (52.081, 4.313)


def test_instellingen_op_dezelfde_coordinaat_vormen_een_groep_op_naam_gesorteerd():
    groepen = groepeer(
        [
            (UTRECHT, "Utrecht", "Nimeto"),
            (HAAG, "Den Haag", "Hogeschool Inholland"),
            (UTRECHT, "Utrecht", "Grafisch Lyceum"),
        ]
    )

    assert groepen == [
        Groep(UTRECHT, "Utrecht", ("Grafisch Lyceum", "Nimeto")),
        Groep(HAAG, "Den Haag", ("Hogeschool Inholland",)),
    ]


def test_plaatsnamen_met_hetzelfde_coordinaat_zijn_een_plaats():
    # 's-Gravenhage en Den Haag staan in de lijst op dezelfde plek.
    groepen = groepeer([(HAAG, "'S-Gravenhage", "A"), (HAAG, "Den Haag", "B")])

    assert [g.namen for g in groepen] == [("A", "B")]


def _ringen(geometrie):
    polygonen = [geometrie["coordinates"]] if geometrie["type"] == "Polygon" else geometrie["coordinates"]
    return [(i, ring) for polygoon in polygonen for i, ring in enumerate(polygoon)]


def test_de_ondergrond_draait_de_ringen_zoals_plotly_ze_leest():
    # Een buitenrand tegen de klok in kleurt in Plotly alles behalve de provincie (#1079).
    grond = ondergrond([51.5, 52.8], [4.0, 6.0])
    assert grond is not None

    ringen = [r for f in grond.geojson["features"] for r in _ringen(f["geometry"])]
    assert ringen
    for i, ring in ringen:
        oppervlak = kaart_regio._oppervlak(ring)
        assert (oppervlak < 0) == (i == 0), "buitenrand met de klok mee, gaten ertegenin"


def test_de_ondergrond_noemt_alleen_de_provincies_in_beeld():
    grond = ondergrond([53.0, 53.6], [6.2, 7.2])
    assert grond is not None

    assert "PV20" in grond.locations
    assert not set(grond.locations) & {"PV26", "PV31"}


def test_zonder_provincie_in_beeld_geen_ondergrond():
    assert ondergrond([40.0, 41.0], [0.0, 1.0]) is None


def test_het_bereik_is_minstens_twee_keer_zo_breed_als_hoog():
    # Plotly houdt de verhouding vast: een vierkant bereik geeft op een telefoon een kader van de halve breedte.
    lat, lon = bereik([UTRECHT, (52.03, 5.10), (52.374, 4.899)])

    assert (lon[1] - lon[0]) >= 2 * (lat[1] - lat[0]) - 1e-9
    assert lon[0] < 4.899 and lon[1] > 5.114


def test_een_regio_die_al_breed_is_houdt_haar_bereik():
    _lat, lon = bereik([(53.2, 3.5), (53.3, 7.0)])

    assert lon == pytest.approx([3.5 - 3.5 * 0.65, 7.0 + 3.5 * 0.65])


def test_zonder_punten_is_het_bereik_heel_nederland():
    assert bereik([]) == ([50.3, 53.9], [3.0, 7.8])


def test_de_naam_bij_de_ster_staat_links_in_de_rechterhelft():
    assert labelpositie(4.5, [4.0, 6.0]) == "top right"
    assert labelpositie(5.0, [4.0, 6.0]) == "top right"
    assert labelpositie(5.8, [4.0, 6.0]) == "top left"
