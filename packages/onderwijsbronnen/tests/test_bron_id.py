"""Het ID-contract `bron:id` (#912): één normalisatie, en elk ID hoort bij precies één bron."""

import pytest

import onderwijsbronnen
from onderwijsbronnen import AmbigueBronId, BronId, OnbekendBronId, Register, bron_van_sleutel


def _alle_records():
    return [(bron, r) for bron, records in onderwijsbronnen.catalogus().items() for r in records]


def test_de_samengevoegde_catalogus_heeft_alle_bronnen_in_vaste_volgorde():
    catalogus = onderwijsbronnen.catalogus()
    assert tuple(catalogus) == onderwijsbronnen.BRONNEN
    assert catalogus["cbs"] == onderwijsbronnen.cbs.catalog()
    alles = [r for bron in ("rio", "duo", "roa", "uwv", "inspectie", "sbb") for r in catalogus[bron]]
    assert alles == onderwijsbronnen.catalog(source="all")


def test_geen_id_komt_in_twee_bronnen_of_twee_records_voor():
    assert onderwijsbronnen.register().dubbel() == {}


def test_elk_record_herleidt_naar_precies_zijn_eigen_bron():
    for bron, record in _alle_records():
        eigen_id = getattr(onderwijsbronnen, bron).metadata(record)["id"]
        gevonden = onderwijsbronnen.parse_bron_id(eigen_id)
        assert (gevonden.bron, gevonden.id) == (bron, eigen_id)
        assert onderwijsbronnen.register().kandidaten(eigen_id) == [gevonden]


def test_heen_en_terug_geeft_hetzelfde_id():
    for bron_id in onderwijsbronnen.register():
        tekst = str(bron_id)
        assert onderwijsbronnen.parse_bron_id(tekst) == bron_id
        assert str(onderwijsbronnen.parse_bron_id(tekst)) == onderwijsbronnen.normaliseer_bron_id(tekst)
        for spelling in (bron_id.id, bron_id.id.upper(), bron_id.id.lower(), f"{bron_id.bron}/{bron_id.id}"):
            assert onderwijsbronnen.parse_bron_id(spelling) == bron_id, spelling


@pytest.mark.parametrize(
    ("invoer", "verwacht"),
    [
        ("85423NED", "cbs:85423NED"),
        ("85423ned", "cbs:85423NED"),
        ("cbs:85423NED", "cbs:85423NED"),
        ("cbs_85423ned", "cbs:85423NED"),
        ("CBS/85423ned", "cbs:85423NED"),
        ("71733NED", "cbs:71733ned"),  # de catalogus spelt deze tabel klein; nooit upper()
        ("80040ned", "cbs:80040ned"),
        (" p01hoinges ", "duo:p01hoinges"),
        ("P01HOINGES", "duo:p01hoinges"),
        ("duo:p01hoinges", "duo:p01hoinges"),
        ("adressen_mbo", "duo:adressen_mbo"),
        ("rio/aangeboden-opleidingen", "rio:aangeboden-opleidingen"),
        ("rio:onderwijslocaties", "rio:onderwijslocaties"),
        ("ais2030", "roa:ais2030"),
        ("roa:ais2030", "roa:ais2030"),
        ("uwv-open-match-data", "uwv:uwv-open-match-data"),
        ("oordelen", "inspectie:oordelen"),
        ("sbb:crebolijst", "sbb:crebolijst"),
        ("unl:wopi", "unl:wopi"),
        ("unl/WOPI", "unl:wopi"),
        ("wopi", "unl:wopi"),
        ("skdb:studiekeuzedatabase", "skdb:studiekeuzedatabase"),
        ("studiekeuzedatabase", "skdb:studiekeuzedatabase"),
    ],
)
def test_elke_vorm_normaliseert_naar_bron_en_catalogusspelling(invoer, verwacht):
    assert onderwijsbronnen.normaliseer_bron_id(invoer) == verwacht


@pytest.mark.parametrize("invoer", ["99999NED", "duo:bestaat-niet", "rio:85423NED", "", "duo_p01hoinges"])
def test_een_onbekend_id_is_een_fout_geen_gok(invoer):
    with pytest.raises(OnbekendBronId):
        onderwijsbronnen.parse_bron_id(invoer)


def test_een_kaal_id_bij_twee_bronnen_is_een_fout_met_opties():
    register = Register({"cbs": ["X1"], "duo": ["x1", "y2"]})
    with pytest.raises(AmbigueBronId) as fout:
        BronId.parse("x1", register)
    assert fout.value.opties == ["cbs:X1", "duo:x1"]
    assert register.dubbel() == {"x1": ["cbs:X1", "duo:x1"]}
    # Met voorvoegsel is het wél eenduidig.
    assert BronId.parse("duo:X1", register) == BronId("duo", "x1")
    assert BronId.parse("y2", register) == BronId("duo", "y2")


def test_een_voorvoegsel_dat_niet_klopt_valt_terug_op_het_hele_id():
    """Een DUO-naam die met `cbs_` begint, is geen CBS-tabel met een voorvoegsel."""
    register = Register({"cbs": ["85423NED"], "duo": ["cbs_overzicht"]})
    assert BronId.parse("cbs_overzicht", register) == BronId("duo", "cbs_overzicht")
    assert BronId.parse("cbs_85423ned", register) == BronId("cbs", "85423NED")


def test_een_onbekende_bron_in_het_register_is_een_fout():
    with pytest.raises(ValueError, match="onbekende bron"):
        Register({"onbekend": ["x"]})


@pytest.mark.parametrize(
    ("sleutel", "bron"),
    [
        ("duo:p01hoinges:4", "duo"),
        ("cbs:85423NED:1e45b6cf:4542528b", "cbs"),
        ("rio:aangeboden-opleidingen:type=AANGEBODENMBOOPLEIDING", "rio"),
        ("uwv:flevoland", "uwv"),
        ("roa:nederland:onderwijs", "roa"),
        ("analysis:0123456789ab", "analysis"),  # eigen berekening: geen bron, het voorvoegsel blijft
        ("analysis:3", "analysis"),
    ],
)
def test_de_bron_van_een_datasleutel_is_haar_voorvoegsel(sleutel, bron):
    assert bron_van_sleutel(sleutel) == bron
