"""De vaste koppeltabel van DUO-onderdeel naar ROA-categorie (#745), op de bevroren ROA-rijen.

Elke categorie in de tabel moet in de bron bestaan, in de laag die de tabel noemt en op het niveau waar ze staat: een
tikfout of een nieuwe ROA-editie met andere namen zou anders stil een lege uitkomst geven.
"""

import pytest

from data import arbeidsmarkt, roa_koppeling
from data.roa_koppeling import BACHELOR, KOPPELING, MASTER

pytestmark = pytest.mark.usefixtures("gouden")


def test_elk_hbo_wo_onderdeel_van_de_app_heeft_een_koppeling_op_beide_niveaus():
    hbo_wo = {s for s, indeling in arbeidsmarkt.SECTOR_INDELING.items() if indeling == "hbo/wo"}

    assert set(KOPPELING) == hbo_wo
    assert all(set(per_niveau) == {BACHELOR, MASTER} for per_niveau in KOPPELING.values())


def test_elke_gekoppelde_categorie_bestaat_in_de_bron_in_haar_laag_en_op_haar_niveau():
    for onderdeel, per_niveau in KOPPELING.items():
        for niveau, k in per_niveau.items():
            if k.categorie is None:
                continue
            assert k.laag in ("sector", "subsector"), onderdeel
            assert k.categorie in arbeidsmarkt.roa_categorieen(k.laag), (onderdeel, niveau)
            assert k.categorie.startswith(niveau.split(",")[0] + " - "), (onderdeel, niveau)


def test_een_gekoppeld_opleidingstype_valt_onder_de_gekoppelde_subsector():
    typen = [(k.categorie or "", k.opleidingstype) for p in KOPPELING.values() for k in p.values() if k.opleidingstype]

    assert typen == [
        ("Bachelor - economie en recht", "Bachelor - recht"),
        ("Master - economie en recht", "Master - recht"),
    ]
    for subsector, type_ in typen:
        assert type_ in arbeidsmarkt.roa_opleidingstypen(subsector)


def test_elke_koppeling_zegt_waarom_en_ongekoppeld_heet_ongekoppeld():
    for per_niveau in KOPPELING.values():
        for k in per_niveau.values():
            uitvoer = k.uitvoer()
            if k.categorie is None:
                assert uitvoer == {"ongekoppeld": k.toelichting} and k.toelichting.startswith("Niet te koppelen")
            else:
                assert uitvoer["kanttekening"] == k.toelichting and k.toelichting


def test_wat_niet_eenduidig_is_blijft_ongekoppeld():
    ongekoppeld = sorted((o, n) for o, p in KOPPELING.items() for n, k in p.items() if k.categorie is None)

    assert ongekoppeld == [
        ("GEDRAG_EN_MAATSCHAPPIJ", BACHELOR),
        ("NATUUR", BACHELOR),
        ("NATUUR", MASTER),
        ("SECTOROVERSTIJGEND", BACHELOR),
        ("SECTOROVERSTIJGEND", MASTER),
    ]
    assert KOPPELING["ECONOMIE"][BACHELOR].laag == "sector"


@pytest.mark.parametrize(
    ("naam", "verwacht"),
    [
        ("GEDRAG_EN_MAATSCHAPPIJ", "GEDRAG_EN_MAATSCHAPPIJ"),
        ("Gedrag en maatschappij", "GEDRAG_EN_MAATSCHAPPIJ"),
        (" natuur ", "NATUUR"),
        ("landbouw_en_natuurlijke_omgeving", "LANDBOUW_EN_NATUURLIJKE_OMGEVING"),
        ("Zorg en welzijn", None),  # een mbo-sector
        ("Psychologie", None),  # een opleiding, geen onderdeel
    ],
)
def test_onderdeel_in_de_spelling_van_duo(naam, verwacht):
    assert roa_koppeling.onderdeel(naam) == verwacht


def test_opleidingstypen_volgen_de_code_van_de_bron():
    assert arbeidsmarkt.roa_opleidingstypen("Master - journalistiek, gedrag en maatschappij") == [
        "Master - communicatie en journalistiek",
        "Master - psychologie",
        "Master - sociale en maatschappijwetenschappen",
    ]
    assert arbeidsmarkt.roa_opleidingstypen("Master - bestaat niet") == []
