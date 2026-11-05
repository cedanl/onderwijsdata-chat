"""DUO's financiële verantwoording uit XBRL per bestuur (#935, besluit #725), op synthetische bestanden zonder netwerk.

De fixture heeft vijf mbo-eenheden in 2025, gekozen zodat de mediaan van solvabiliteit I 0,573 is (de "sectormediaan"
uit de verkenning) en het gewogen cijfer van de Inspectie iets anders (0,593): de test bewijst zo dat de code het
gewogen cijfer geeft. ROC Midden Nederland (40597) heeft in 2025 solvabiliteit I 0,69, zoals in de echte editie.
Bestuur 40833 heeft drie eenheden (25PZ, 25LR, 30RM), zoals in de echte bestanden.
"""

import io
import re
import zipfile

import openpyxl
import pytest

from onderwijsbronnen import Bestuurssleutel
from onderwijsbronnen.duo import financien
from onderwijsbronnen.duo.financien import FinancienAfwijkend, FinancienOnbereikbaar

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_SLEUTEL = ["Bevoegd Gezag", "Sector", "Groepering", "Naam", "Verslagjaar", "Geconsolideerd of enkelvoudig"]

# (bevoegd gezag, sector, groepering, naam, jaar, variant, posten). Posten in miljoen euro.
_EENHEDEN = [
    ("40597", "MBO", "ROC", "Stichting ROC Midden Nederland", 2024, "Geconsolideerd",
     dict(ev=68.0, vz=6.0, tp=100.0, va=35.0, ks=10.0, baten=200.0, fb=0.5, res=6.5, rijk=187.0)),
    ("40597", "MBO", "ROC", "Stichting ROC Midden Nederland", 2025, "Geconsolideerd",
     dict(ev=69.0, vz=6.0, tp=100.0, va=32.0, ks=10.0, baten=213.0, fb=0.4, res=4.3, rijk=197.0)),
    ("40001", "MBO", "BER", "Vakcollege Een", 2025, "Enkelvoudig",
     dict(ev=57.3, vz=2.0, tp=100.0, va=12.0, ks=8.0, baten=60.0, fb=None, res=-0.6, rijk=50.0)),
    ("40002", "MBO", "ROC", "ROC Krap", 2025, "Enkelvoudig",
     dict(ev=50.0, vz=1.0, tp=100.0, va=6.0, ks=10.0, baten=20.0, fb=0.0, res=0.2, rijk=18.0)),
    ("40833-25PZ", "MBO", "ROC", "ROC van Amsterdam", 2024, "Geconsolideerd",
     dict(ev=290.0, vz=20.0, tp=500.0, va=120.0, ks=100.0, baten=400.0, fb=1.0, res=3.0, rijk=350.0)),
    ("40833-25PZ", "MBO", "ROC", "ROC van Amsterdam", 2025, "Enkelvoudig",
     dict(ev=300.0, vz=20.0, tp=500.0, va=130.0, ks=100.0, baten=410.0, fb=1.0, res=4.0, rijk=360.0)),
    ("40833-25LR", "MBO", "ROC", "ROC van Flevoland", 2025, "Enkelvoudig",
     dict(ev=10.0, vz=None, tp=20.0, va=5.0, ks=4.0, baten=30.0, fb=None, res=0.3, rijk=25.0)),
    ("40833-30RM", "MBO", "ROC", "ROC TOP", 2025, "Enkelvoudig",
     dict(ev=0.05, vz=None, tp=0.117, va=0.1, ks=0.05, baten=2.5, fb=None, res=0.0, rijk=2.4)),
    ("00009", "WO", "UNIV", "Universiteit Utrecht", 2025, "Geconsolideerd",
     dict(ev=600.0, vz=50.0, tp=1500.0, va=500.0, ks=600.0, baten=1100.0, fb=2.0, res=-10.0, rijk=700.0, wp=115.0)),
    ("30000", "HBO", "HBO", "Hogeschool Dun", 2025, "Enkelvoudig",
     dict(ev=2.0, vz=0.5, tp=10.0, va=3.0, ks=5.0, baten=11.0, fb=None, res=-0.5, rijk=9.0)),
    ("12345", "PO", "PO", "Basisschoolbestuur", 2025, "Enkelvoudig",
     dict(ev=1.0, vz=0.0, tp=2.0, va=1.0, ks=1.0, baten=3.0, fb=None, res=0.0, rijk=2.0)),
]
_M = 1_000_000


def _p(posten, sleutel):
    w = posten.get(sleutel)
    return None if w is None else w * _M


def _kengetallen(posten):
    ev, vz, tp = posten["ev"], posten["vz"] or 0, posten["tp"]
    return [ev / tp, (ev + vz) / tp, posten["va"] / posten["ks"], posten["res"] / (posten["baten"] + (posten["fb"] or 0))]


def _rijen(bouw):
    return [[g, s, gr, n, j, v, *bouw(p)] for g, s, gr, n, j, v, p in _EENHEDEN]


def _xlsx(titel, kop, rijen, dimensie=None) -> bytes:
    boek = openpyxl.Workbook()
    blad = boek.active
    blad.append([titel])
    blad.append(kop)
    for rij in rijen:
        blad.append(rij)
    buf = io.BytesIO()
    boek.save(buf)
    if dimensie is None:
        return buf.getvalue()
    # Zoals de echte bestanden: een bladdimensie die kleiner is dan de data (rijksbijdragen A1:N bij 15 kolommen).
    uit = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as bron, zipfile.ZipFile(uit, "w") as doel:
        for item in bron.infolist():
            data = bron.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(rb'<dimension ref="[^"]+"', f'<dimension ref="{dimensie}"'.encode(), data)
            doel.writestr(item, data)
    return uit.getvalue()


def _bestanden(kengetallen=None, dimensie="A1:F3") -> dict[str, bytes]:
    kg = financien.KOLOMMEN
    return {
        "kengetallen": _xlsx("Kengetallen", [*_SLEUTEL, "Huisvestingsratio", *kg["kengetallen"].values()],
                             kengetallen or _rijen(lambda p: [0.1, *_kengetallen(p)])),
        "rijksbijdragen": _xlsx("Rijksbijdragen", [*_SLEUTEL, *kg["rijksbijdragen"].values()],
                                _rijen(lambda p: [_p(p, "rijk"), _p(p, "wp")]), dimensie=dimensie),
        "balans": _xlsx("Balans", [*_SLEUTEL, *kg["balans"].values()],
                        _rijen(lambda p: [_p(p, k) for k in ("ev", "vz", "tp", "va", "ks")])),
        "baten_en_lasten": _xlsx("Staat van baten en lasten", [*_SLEUTEL, *kg["baten_en_lasten"].values()],
                                 _rijen(lambda p: [_p(p, k) for k in ("baten", "fb", "res")])),
    }


_BESTANDSNAMEN = {
    "kengetallen": "16.-financiele-kengetallen-{}-standaard.xlsx",
    "rijksbijdragen": "12.-rijksbijdragen-{}-standaard.xlsx",
    "balans": "1.-balans-{}-standaard-open-data.xlsx",
    "baten_en_lasten": "2.-staat-van-baten-en-lasten-{}-standaard.xlsx",
}


def _pagina(jaren="2021-2025", extra="") -> str:
    """Een uitsnede van de echte pagina: per onderdeel een tabelrij met link, peildatum en publicatiedatum, plus de
    afleiders die er ook staan (enkelvoudig, begroting, niveau)."""
    rijen = []
    for naam in _BESTANDSNAMEN.values():
        rijen.append(
            f'<tr><td scope="row"><span class="file__title"><a href="/open_onderwijsdata/images/{naam.format(jaren)}" '
            'target="new">x</a></span> (xlsx 934kb)</td><td >31 december 2025</td><td >15 september 2026</td></tr>'
        )
    afleiders = [
        "1.-balans-2021-2025-enkelvoudig.xlsx",
        "20.-staat-van-baten-en-lasten-begroting-2021-2025-standaard.xlsx",
        "25.-balans-niveau-2021-2025-standaard.xlsx",
        "16.-financiele-kengetallen-2021-2025-enkelvoudig.xlsx",
    ]
    rijen += [f'<tr><td><a href="/open_onderwijsdata/images/{a}">y</a></td><td>1 januari 2020</td></tr>' for a in afleiders]
    return "<table>" + "".join(rijen) + extra + "</table>"


def _haler(pagina=None, bestanden=None, soort=_XLSX):
    pagina = pagina or _pagina()
    bestanden = bestanden or _bestanden()
    per_url = {financien.BASIS + "/open_onderwijsdata/images/" + _BESTANDSNAMEN[o].format("2021-2025"): b
               for o, b in bestanden.items()}

    def haal(url):
        if url == financien.PAGINA:
            return pagina.encode(), "text/html;charset=UTF-8"
        return per_url[url], soort

    return haal


@pytest.fixture(scope="module")
def data():
    return financien.laad(_haler())


# --- de sleutel ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("waarde", "sleutel"),
    [
        ("00008", Bestuurssleutel(8)),
        ('="00008"', Bestuurssleutel(8)),
        (8, Bestuurssleutel(8)),
        (40597.0, Bestuurssleutel(40597)),
        ("40597.0", Bestuurssleutel(40597)),
        ("40833-25LR", Bestuurssleutel(40833, "25LR")),
        ("40833-25pz", Bestuurssleutel(40833, "25PZ")),
    ],
)
def test_elke_schrijfwijze_van_een_bestuur_geeft_dezelfde_sleutel(waarde, sleutel):
    assert Bestuurssleutel.parse(waarde) == sleutel


@pytest.mark.parametrize("waarde", [None, True, "", "abc", "25PZ", 8.5, "123456", "40833-XYZ", -1])
def test_geen_bestuursnummer_is_none(waarde):
    assert Bestuurssleutel.parse(waarde) is None


def test_het_suffix_van_40833_blijft_en_de_rio_code_heeft_vijf_tekens():
    sleutel = Bestuurssleutel.parse("40833-30RM")
    assert (sleutel.nummer, sleutel.brin, str(sleutel)) == (40833, "30RM", "40833-30RM")
    assert Bestuurssleutel(9).rio_code == "00009" and str(Bestuurssleutel(9)) == "00009"
    assert sleutel.bestuur == Bestuurssleutel(40833)


# --- de pagina en de bestanden -----------------------------------------------------------------------------------


def test_de_editie_komt_uit_de_bestandsnamen_met_peil_en_publicatiedatum():
    editie = financien.lees_editie(_pagina())
    assert (editie.eerste_jaar, editie.laatste_jaar, editie.jaren) == (2021, 2025, "2021-2025")
    assert (editie.peildatum, editie.publicatiedatum) == ("31 december 2025", "15 september 2026")
    assert editie.urls["balans"].endswith("/1.-balans-2021-2025-standaard-open-data.xlsx")
    assert editie.urls["baten_en_lasten"].endswith("/2.-staat-van-baten-en-lasten-2021-2025-standaard.xlsx")
    assert all("enkelvoudig" not in u and "begroting" not in u and "niveau" not in u for u in editie.urls.values())


def test_de_nieuwste_editie_wint():
    editie = financien.lees_editie(_pagina("2020-2024") + _pagina("2021-2025"))
    assert editie.jaren == "2021-2025" and "2021-2025" in editie.urls["kengetallen"]


def test_onderdelen_uit_verschillende_edities_is_een_weigering():
    pagina = _pagina().replace("12.-rijksbijdragen-2021-2025", "12.-rijksbijdragen-2022-2026")
    with pytest.raises(FinancienAfwijkend, match="verschillende edities"):
        financien.lees_editie(pagina)


def test_een_pagina_zonder_kengetallen_is_onbereikbaar():
    with pytest.raises(FinancienOnbereikbaar, match="financiele-kengetallen"):
        financien.lees_editie(_pagina().replace("16.-financiele-kengetallen", "16.-iets-anders"))


@pytest.mark.parametrize(("inhoud", "soort"), [(b"<html>404</html>", "text/html"), (b"<html>", ""), (b"PK..", "text/html")])
def test_een_soft_404_is_geen_bestand(inhoud, soort):
    with pytest.raises(FinancienOnbereikbaar, match="soft 404"):
        financien.xlsx(inhoud, soort, "https://duo.nl/x/16.-financiele-kengetallen-2020-2024-standaard.xlsx")


def test_laad_herkent_de_soft_404_van_een_vervallen_bestand():
    with pytest.raises(FinancienOnbereikbaar, match="soft 404"):
        financien.laad(_haler(soort="text/html;charset=UTF-8"))


def test_een_http_fout_wordt_onbereikbaar():
    import httpx

    def kapot(url):
        raise httpx.ConnectTimeout("te laat")

    with pytest.raises(FinancienOnbereikbaar, match="ConnectTimeout"):
        financien.laad(kapot)


def test_een_te_kleine_bladdimensie_laat_geen_kolom_vallen(data):
    """De echte rijksbijdragen zeggen A1:N bij 15 kolommen; de fixture zegt A1:F3."""
    utrecht = data.van("00009")[0]
    assert utrecht.waarden["rijksbijdragen"] == 700 * _M and utrecht.waarden["werkplaatsfunctie"] == 115 * _M


def test_een_ontbrekende_kolom_is_een_weigering():
    bestanden = _bestanden()
    bestanden["balans"] = _xlsx("Balans", [*_SLEUTEL, "Eigen vermogen"], [])
    with pytest.raises(FinancienAfwijkend, match="Totaal van passiva"):
        financien.lees(financien.lees_editie(_pagina()), bestanden)


def test_een_dubbele_eenheid_is_een_weigering():
    rijen = _rijen(lambda p: [0.1, *_kengetallen(p)])
    with pytest.raises(FinancienAfwijkend, match="twee keer"):
        financien.lees(financien.lees_editie(_pagina()), _bestanden(kengetallen=[*rijen, rijen[0]]))


# --- scope, variant en leeg --------------------------------------------------------------------------------------


def test_alleen_mbo_hbo_en_wo(data):
    assert {r.sector for r in data.rijen} == {"MBO", "HBO", "WO"}
    assert data.van("12345") == [] and financien.overzicht(data, "12345") == []


def test_40833_is_drie_eenheden_en_nooit_een_som(data):
    assert sorted({str(r.sleutel) for r in data.van("40833")}) == ["40833-25LR", "40833-25PZ", "40833-30RM"]
    assert [r.verslagjaar for r in data.van("40833-25PZ")] == [2024, 2025]
    assert all(r["eenheid"] != "40833" for r in financien.overzicht(data, "40833"))


def test_de_variant_staat_per_jaar(data):
    assert [r.variant for r in data.van("40833-25PZ")] == ["geconsolideerd", "enkelvoudig"]


def test_een_lege_cel_is_none_geen_nul():
    rijen = _rijen(lambda p: [0.1, *_kengetallen(p)])
    rijen[1][len(_SLEUTEL) + 1] = None  # solvabiliteit I van 40597 in 2025 leeg
    data = financien.lees(financien.lees_editie(_pagina()), _bestanden(kengetallen=rijen))
    assert data.van("40597")[1].waarden["solvabiliteit_1"] is None
    assert data.van("40597")[1].waarden["solvabiliteit_2"] == pytest.approx(0.75)
    # Het sectorcijfer rekent met de posten, niet met het lege kengetal.
    assert data.sectorcijfer("MBO", 2025, "solvabiliteit_1").eenheden == 6


def test_varianten_die_per_onderdeel_verschillen_zijn_een_weigering():
    bestanden = _bestanden()
    kg = financien.KOLOMMEN
    rijen = [[g, s, gr, n, j, "Enkelvoudig" if g == "40597" else v, *[_p(p, k) for k in ("ev", "vz", "tp", "va", "ks")]]
             for g, s, gr, n, j, v, p in _EENHEDEN]
    bestanden["balans"] = _xlsx("Balans", [*_SLEUTEL, *kg["balans"].values()], rijen)
    with pytest.raises(FinancienAfwijkend, match="variant"):
        financien.lees(financien.lees_editie(_pagina()), bestanden)


# --- rekenen -----------------------------------------------------------------------------------------------------


def test_acceptatie_roc_midden_nederland_2025_naast_het_gewogen_sectorcijfer(data):
    """Solvabiliteit I 0,69; de mediaan van de mbo-eenheden is 0,573, het sectorcijfer van de Inspectie 0,593."""
    [rij] = [r for r in financien.overzicht(data, "40597") if r["verslagjaar"] == 2025]
    assert round(rij["solvabiliteit_1"], 2) == 0.69
    mbo = sorted(r.waarden["solvabiliteit_1"] for r in data.rijen if r.sector == "MBO" and r.verslagjaar == 2025)
    assert round(mbo[len(mbo) // 2], 3) == 0.573  # de mediaan: niet wat de code geeft
    gewogen = (69 + 57.3 + 50 + 300 + 10 + 0.05) / (100 + 100 + 100 + 500 + 20 + 0.117)
    assert rij["solvabiliteit_1_sector"] == pytest.approx(gewogen)
    assert round(rij["solvabiliteit_1_sector"], 3) == 0.593
    assert rij["solvabiliteit_1_sector_eenheden"] == 6  # 40833 telt als drie eenheden


def test_het_sectorcijfer_is_som_gedeeld_door_som_per_kengetal(data):
    liq = data.sectorcijfer("MBO", 2025, "liquiditeit")
    assert liq.waarde == pytest.approx((32 + 12 + 6 + 130 + 5 + 0.1) / (10 + 8 + 10 + 100 + 4 + 0.05))
    rent = data.sectorcijfer("MBO", 2025, "rentabiliteit")
    # Een lege financiële bate telt als afwezig, zoals in DUO's eigen kengetal.
    assert rent.waarde == pytest.approx((4.3 - 0.6 + 0.2 + 4 + 0.3 + 0) / (213.4 + 60 + 20 + 411 + 30 + 2.5))
    solv2 = data.sectorcijfer("MBO", 2025, "solvabiliteit_2")
    assert solv2.waarde == pytest.approx((69 + 6 + 57.3 + 2 + 50 + 1 + 300 + 20 + 10 + 0.05) / 820.117)
    assert data.sectorcijfer("MBO", 2024, "liquiditeit").eenheden == 2
    assert data.sectorcijfer("PO", 2025, "liquiditeit").waarde is None


def test_een_eenheid_zonder_verplichte_post_blijft_buiten_het_sectorcijfer():
    rijen = [[g, s, gr, n, j, v, *[None if (g == "40002" and k == "tp") else _p(p, k)
                                 for k in ("ev", "vz", "tp", "va", "ks")]] for g, s, gr, n, j, v, p in _EENHEDEN]
    bestanden = _bestanden()
    bestanden["balans"] = _xlsx("Balans", [*_SLEUTEL, *financien.KOLOMMEN["balans"].values()], rijen)
    data = financien.lees(financien.lees_editie(_pagina()), bestanden)
    s = data.sectorcijfer("MBO", 2025, "solvabiliteit_1")
    assert (s.eenheden, s.zonder_posten) == (5, 1)
    assert s.waarde == pytest.approx((69 + 57.3 + 300 + 10 + 0.05) / (100 + 500 + 20 + 0.117 + 100))


@pytest.mark.parametrize(
    ("baten", "grens"),
    [(2_999_999, 1.50), (3_000_000, 1.00), (12_000_000, 1.00), (12_000_001, 0.75), (25_000_000, 0.75),
     (25_000_001, 0.50)],
)
def test_de_liquiditeitsgrens_hangt_af_van_de_baten(baten, grens):
    assert financien.liquiditeitsgrens(baten)[0] == grens
    assert financien.liquiditeitsgrens(None) is None


def test_signalering_solvabiliteit_ii_en_liquiditeit(data):
    [dun] = financien.overzicht(data, "30000")
    assert dun["solvabiliteit_2_onder_signaleringswaarde"] is True  # 0,25 < 0,30
    assert (dun["liquiditeit_signaleringswaarde"], dun["liquiditeit_trede"]) == (
        1.00, "totale baten van € 3 tot en met € 12 miljoen")
    assert dun["liquiditeit_onder_signaleringswaarde"] is True  # 0,60 < 1,00 bij € 11 mln baten
    [top] = financien.overzicht(data, "40833-30RM")
    assert top["liquiditeit_signaleringswaarde"] == 1.50 and top["liquiditeit_onder_signaleringswaarde"] is False
    rmn = financien.overzicht(data, "40597")
    assert not any(r["solvabiliteit_2_onder_signaleringswaarde"] or r["liquiditeit_onder_signaleringswaarde"]
                   for r in rmn)


def test_overzicht_is_plat_en_onafgerond(data):
    [rij] = [r for r in financien.overzicht(data, "40597") if r["verslagjaar"] == 2025]
    assert rij["eenheid"] == "40597" and rij["sector"] == "MBO" and rij["groepering"] == "ROC"
    assert rij["rentabiliteit"] == pytest.approx(4.3 / 213.4)
    assert rij["rijksbijdragen"] == 197 * _M and rij["werkplaatsfunctie"] is None
    assert all(not isinstance(v, dict | list) for v in rij.values())


def test_de_catalogus_kent_financien_als_duo_record():
    from onderwijsbronnen import duo

    [record] = [r for r in duo.catalogusrecords() if r["_ckan_id"] == "financien"]
    assert duo.metadata(record)["id"] == "financien"
    assert record["documentatie"]["url"] == financien.PAGINA
    assert set(record["onderwijstype"]) == {"MBO", "HBO", "WO"}
