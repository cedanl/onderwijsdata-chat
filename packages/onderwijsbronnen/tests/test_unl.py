"""UNL: het WOPI-personeelsbestand uit de records van de draaitabellen (#936), op een synthetisch bestand.

Er staat geen data van UNL in de repo; `unl.proefbestand` bouwt een xlsx met dezelfde XML-vorm en verzonnen getallen
die de controlewaarden uit het onderzoek (#731) reproduceren.
"""

import hashlib

import httpx
import pytest

import onderwijsbronnen
from onderwijsbronnen import unl
from onderwijsbronnen.unl import proefbestand


@pytest.fixture(scope="module")
def wopi():
    return unl.lees(*proefbestand.standaard())


def _som(rijen, maat, **filters):
    return round(sum(r[maat] for r in rijen if all(r[k] == v for k, v in filters.items())), 2)


# --- de controlewaarden ----------------------------------------------------------------------------------------


def test_universiteit_utrecht_zonder_gezo(wopi):
    rijen = wopi.rijen("functie", "excl", "totaal")
    assert _som(rijen, "fte", jaar=2025, brin="21PD") == 6184.36
    obp = _som(rijen, "fte", jaar=2025, brin="21PD", functie="OBP")
    assert round(6184.36 - obp, 2) == 3584.05


def test_landelijk_zonder_en_met_gezo(wopi):
    assert _som(wopi.rijen("functie", "excl"), "fte", jaar=2025) == 58462.07
    assert _som(wopi.rijen("functie", "incl"), "fte", jaar=2025) == 61371.30


def test_personen_per_universiteit(wopi):
    assert _som(wopi.rijen("personen", "excl"), "personen", jaar=2025) == 66723
    assert _som(wopi.rijen("personen", "incl"), "personen", jaar=2025) == 70266


# --- de vorm van de records ------------------------------------------------------------------------------------


def test_de_records_zijn_tidy(wopi):
    functie = wopi.rijen("functie")[0]
    assert set(functie) == {"jaar", "brin", "instelling", "functie", "functieomschrijving", "aanstelling", "fte"}
    assert isinstance(functie["jaar"], int) and isinstance(functie["fte"], float)
    personen = wopi.rijen("personen")[0]
    assert set(personen) == {"jaar", "brin", "instelling", "leeftijd", "personen"}
    assert isinstance(personen["personen"], int)


def test_aanstelling_in_woorden_en_onbekend_voor_2003(wopi):
    rijen = wopi.rijen("functie")
    assert {r["aanstelling"] for r in rijen if r["jaar"] >= 2003} == {"vast", "tijdelijk"}
    assert {r["aanstelling"] for r in rijen if r["jaar"] < 2003} == {"onbekend"}


def test_een_lege_leeftijd_is_onbekend(wopi):
    assert any(r["leeftijd"] == "onbekend" for r in wopi.rijen("personen"))


def test_vrouwen_is_een_eigen_variant(wopi):
    totaal = _som(wopi.rijen("functie", "excl", "totaal"), "fte", jaar=2025)
    vrouwen = _som(wopi.rijen("functie", "excl", "vrouwen"), "fte", jaar=2025)
    assert 0 < vrouwen < totaal


def test_een_mix_of_onbekende_keuze_is_een_fout(wopi):
    for args in [("functie", "beide"), ("functie", "excl", "mannen"), ("hoop", "excl")]:
        with pytest.raises(ValueError):
            wopi.rijen(*args)


def test_rijen_geeft_kopieen(wopi):
    wopi.rijen()[0]["fte"] = -1
    assert wopi.rijen()[0]["fte"] != -1


def test_frame_heeft_dezelfde_rijen(wopi):
    df = wopi.frame("functie", "incl")
    assert len(df) == len(wopi.rijen("functie", "incl"))
    assert round(df[df["jaar"] == 2025]["fte"].sum(), 2) == 61371.30


# --- kiezen op naam, controles ---------------------------------------------------------------------------------


def test_de_cache_wordt_op_naam_gekozen_niet_op_nummer():
    """Het proefbestand begint met een cache van een andere tabel; de volgorde mag niet uitmaken."""
    caches = proefbestand.caches()
    omgekeerd = dict(reversed(list(caches.items())))
    a = unl.lees(*proefbestand.standaard())
    inhoud = proefbestand.maak(omgekeerd)
    b = unl.lees(inhoud, proefbestand.herkomst(inhoud))
    assert a.records == b.records


def test_een_ontbrekende_brontabel_is_een_fout():
    caches = proefbestand.caches()
    del caches["DL_reeks_Functie_geslacht_Uni_VT v"]
    inhoud = proefbestand.maak(caches)
    with pytest.raises(unl.WopiFout, match="ontbreekt"):
        unl.lees(inhoud, proefbestand.herkomst(inhoud))


def test_andere_velden_zijn_een_fout():
    caches = proefbestand.caches()
    naam = "DL_reeks_Functie_geslacht_Uni_VT_exGezo"
    caches[naam] = [{**r, "HOOPgeb": "GEZO"} for r in caches[naam]]
    inhoud = proefbestand.maak(caches)
    with pytest.raises(unl.WopiFout, match="velden"):
        unl.lees(inhoud, proefbestand.herkomst(inhoud))


def test_een_jongste_jaar_dat_niet_de_editie_is_is_een_fout():
    inhoud = proefbestand.maak()
    with pytest.raises(unl.WopiFout, match="editie is 2026"):
        unl.lees(inhoud, proefbestand.herkomst(inhoud, editiejaar=2026))


def test_minder_dan_veertien_universiteiten_is_een_fout():
    caches = proefbestand.caches()
    naam = "DL_reeks_Functie_geslacht_Uni_VT_exGezo"
    caches[naam] = [r for r in caches[naam] if r["brincode"] != "21PD"]
    inhoud = proefbestand.maak(caches)
    with pytest.raises(unl.WopiFout, match="13 BRIN-codes"):
        unl.lees(inhoud, proefbestand.herkomst(inhoud))


def test_geen_xlsx_is_een_fout():
    with pytest.raises(unl.WopiFout, match="geen xlsx"):
        unl.lees(b"<html>", proefbestand.herkomst(b"<html>"))


def test_de_xml_gaat_door_defusedxml():
    """Een extern bestand: een entiteitsdefinitie wordt geweigerd, niet uitgevoerd."""
    caches = proefbestand.caches()
    inhoud = proefbestand.maak(caches)
    import io
    import zipfile

    bom = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><connections>&a;</connections>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(inhoud)) as bron, zipfile.ZipFile(buffer, "w") as doel:
        for naam in bron.namelist():
            doel.writestr(naam, bom if naam == "xl/connections.xml" else bron.read(naam))
    with pytest.raises(Exception, match="(?i)entit"):
        unl.lees(buffer.getvalue(), proefbestand.herkomst(buffer.getvalue()))


# --- ophalen ---------------------------------------------------------------------------------------------------


_PAGINA = """<a href="/files/publications/Feiten%20en%20cijfers_DISCLAIMER_Personeelsgegevens_WOPI.pdf">pdf</a>
<a href="/files/publications/Feiten%20en%20cijfers_WOPI_draaitabellen_tm_2024.xlsx">oud</a>
<a href='/files/publications/Feiten%20en%20cijfers_WOPI_draaitabellen_tm_2025.xlsx'>nieuw</a>"""


def test_de_link_wordt_gelezen_en_de_nieuwste_editie_gekozen():
    url, jaar = unl.bestandslink(_PAGINA)
    assert jaar == 2025
    assert url == (
        "https://www.universiteitenvannederland.nl/files/publications/"
        "Feiten%20en%20cijfers_WOPI_draaitabellen_tm_2025.xlsx"
    )


def test_een_pagina_zonder_link_is_een_fout():
    with pytest.raises(unl.WopiFout, match="geen link"):
        unl.bestandslink("<html>geen bestand</html>")


def test_haal_op_leest_de_pagina_en_legt_de_herkomst_vast():
    inhoud = proefbestand.maak()
    verzoeken = []

    def antwoord(verzoek: httpx.Request) -> httpx.Response:
        verzoeken.append(verzoek)
        if verzoek.url.path.endswith(".xlsx"):
            return httpx.Response(200, content=inhoud, headers={"Last-Modified": "Thu, 28 May 2026 10:45:00 GMT"})
        return httpx.Response(200, text=_PAGINA)

    gekregen, herkomst = unl.haal_op(transport=httpx.MockTransport(antwoord))

    assert gekregen == inhoud
    assert herkomst.editiejaar == 2025 and herkomst.peildatum == "31-12-2025"
    assert herkomst.sha256 == hashlib.sha256(inhoud).hexdigest() and herkomst.bytes == len(inhoud)
    assert herkomst.last_modified == "Thu, 28 May 2026 10:45:00 GMT"
    assert str(verzoeken[0].url) == unl.PAGINA
    # Een eerlijke User-Agent: een kale `Mozilla/5.0` geeft 403 (#721).
    assert all(v.headers["user-agent"] == unl.USER_AGENT for v in verzoeken)
    assert "onderwijsbronnen" in unl.USER_AGENT and "Mozilla" not in unl.USER_AGENT


def test_load_is_lees_van_haal_op(monkeypatch):
    monkeypatch.setattr(unl.wopi, "haal_op", proefbestand.standaard)
    df = unl.load("functie", gezo="excl")
    assert round(df[df["jaar"] == 2025]["fte"].sum(), 2) == 58462.07
    with pytest.raises(ValueError):
        unl.load("functie", gezo="beide")


# --- broncontract en register ----------------------------------------------------------------------------------


def test_het_catalogusrecord_en_de_metadata():
    [record] = unl.catalog()
    meta = unl.metadata(record)
    assert (meta["bron"], meta["id"], meta["voorlopig"]) == ("unl", "wopi", False)
    assert set(meta["redenen"]) == {"peildatum_of_editie", "laatste_update"}


def test_unl_staat_in_het_register_maar_niet_in_all():
    assert onderwijsbronnen.normaliseer_bron_id("unl:wopi") == "unl:wopi"
    assert onderwijsbronnen.normaliseer_bron_id("WOPI") == "unl:wopi"
    assert onderwijsbronnen.catalog(source="unl") == unl.catalog()
    assert not any(r.get("_unl_id") for r in onderwijsbronnen.catalog(source="all"))
