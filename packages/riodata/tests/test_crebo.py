"""CREBO-loader: XLSX-fixture, normalisatie, cache en lookup (zonder netwerk)."""
import datetime as dt
import io

import pytest

openpyxl = pytest.importorskip("openpyxl")

from riodata import crebo, sbb  # noqa: E402


def xlsx(kwalificaties, *, kop="Opleidingscode", vanaf="01-08-2026", vervallen=(), volgorde=("Complete lijst", "Vervallen"),
         entree=()):
    """Nabootsing van het echte SBB-formaat (zie ``crebo.py``): titelrij met kolomkoppen, dossierkop,
    domeinrijen, dossier- en kwalificatierijen, optioneel Entree-sectie en werkblad Vervallen.

    ``kwalificaties``: (dossiercode of None, dossiernaam, crebo, naam, niveau)
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for titel in volgorde:
        ws = wb.create_sheet(titel)
        if titel == "Complete lijst":
            ws.append([f"Overzicht vastgestelde kwalificatiedossiers en kwalificaties geldig vanaf {vanaf}", None, None,
                       kop, "Kwalificatie", "Niveau", "Prijsfactor", "Soort opleiding", "Beroepsvereisten", "Leerweg"])
            ws.append([kop, "Prijsfactor", "Kwalificatiedossier"])
            ws.append([None, None, None, None, "Opleidingsdomein"])
            ws.append([None, None, None, None, "1. Bouw en infra   79000"])
            ws.append([79000, None, None, None, None, None, 1])
            for d_code, d_naam, crebo, naam, niveau in kwalificaties:
                ws.append([d_code, 1.3 if d_code else None, d_naam, crebo, naam, niveau, 1.3, "Vakopleiding\xa0", None, "BOL/BBL\xa0"])
            if entree:
                ws.append(["Overzicht Entree kwalificatiedossier geldig vanaf 01-08-2025", None, None,
                           kop, "Kwalificatie", "Niveau", "Prijsfactor", "Soort o-pleiding", "Beroepsvereisten", "Leerweg"])
                for crebo, naam in entree:
                    ws.append([None, None, "Entree", crebo, naam, 1, 1, "Entreeopleiding", None, "BOL"])
        elif titel == "Vervallen":
            ws.append(["Vervallen"])
            ws.append([])
            ws.append(["Opleidingscode dossier", "Dossiernaam", "Datum einde instroom", "Datum einde opleiding",
                       "Wordt vervangen door", "Opleidingscode dossier nieuw"])
            for rij in vervallen:
                ws.append(list(rij))
        else:
            ws.append(["Bijlage"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def groot(extra=(), **kw):
    basis = [(23000 + i, f"Dossier {i}", 25000 + i, f"Opleiding {i}", 4) for i in range(120)]
    return xlsx(basis + list(extra), **kw)


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("RIODATA_CACHE", str(tmp_path))


class FakeClient:
    def __init__(self, content, ctype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        self.content, self.ctype = content, ctype

    def get(self, url, **kw):
        c = self

        class R:
            content = c.content
            headers = {"content-type": c.ctype}

            def raise_for_status(self):
                pass
        return R()


def test_echte_layout_codes_dossiers_domein_en_geldigheid():
    inhoud = xlsx(
        [
            (23045, "Betonboren", 25078, "Betonboorder", 3),
            (None, "Betonreparatie", "27020\xa0", "Allround Betonreparateur\xa0", "3\xa0"),  # tekst met nbsp
            (23250, "Boulangerie", 25614.0, None, None),                                     # numerieke cel, geen naam
        ],
        vervallen=[(23250, "Boulangerie", dt.datetime(2026, 8, 1), dt.datetime(2031, 8, 1), "Nieuw", 23999)],
        entree=[(98765, "Entreeopleiding X")],
    )
    lijst = crebo.parse_xlsx(inhoud, "test")
    assert lijst.geldig_vanaf == "2026-08-01"
    r = {x["crebo"]: x for x in lijst.rijen}
    assert list(r) == ["25078", "27020", "25614", "98765"]           # tekst blijft tekst, geen nbsp
    assert r["27020"]["niveau"] == "3" and r["27020"]["naam"] == "Allround Betonreparateur"
    assert r["25078"]["dossier_code"] == "23045" and r["25078"]["domein"] == "1. Bouw en infra 79000"
    assert r["27020"]["dossier_code"] is None and r["27020"]["dossier_naam"] == "Betonreparatie"
    assert r["25614"]["naam"] is None and r["25614"]["niveau"] is None
    assert r["25614"]["geldig_tot"] == "2031-08-01" and r["25614"]["dossier_vervallen"]["vervangen_door"] == "Nieuw"
    assert r["25078"]["geldig_van"] == "2026-08-01" and r["25078"]["geldig_tot"] is None
    assert r["25078"]["leerweg"] == "BOL/BBL" and r["25078"]["soort_opleiding"] == "Vakopleiding"
    # Entree-sectie heeft eigen kopregel en eigen ingangsdatum, en is geen domein
    assert r["98765"]["geldig_van"] == "2025-08-01" and r["98765"]["domein"] is None
    assert lijst.rijen[0]["bron"]["Kwalificatie"] == "Betonboorder"


def test_oudere_editie_crebonummer_en_werkblad_niet_eerst():
    inhoud = xlsx([(23045, "Betonboren", 25078, "Betonboorder", 3)], kop="Crebonummer", vanaf="01-08-2021",
                  volgorde=("Bijlage 1", "Complete lijst"))
    lijst = crebo.parse_xlsx(inhoud, "2021")
    assert [r["crebo"] for r in lijst.rijen] == ["25078"] and lijst.geldig_vanaf == "2021-08-01"


def test_onbekend_werkblad_of_kop_geeft_schemafout_met_wat_er_staat():
    with pytest.raises(crebo.CreboSchemaFout, match="Aanwezig: \\['Blad1'\\]"):
        crebo.parse_xlsx(xlsx([], volgorde=("Blad1",)), "test")
    wb = openpyxl.Workbook()
    wb.active.title = "Complete lijst"
    wb.active.append(["A", "B"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(crebo.CreboSchemaFout, match="Eerste rijen"):
        crebo.parse_xlsx(buf.getvalue(), "test")


def test_lookup_found_not_found_ambiguous():
    lijst = crebo.parse_xlsx(xlsx(
        [(1, "D", 25604, "Oud", 3), (2, "D", 25604, "Nieuw", 3), (3, "D", 25000, "Enkel", 4)],
        vervallen=[(1, "D", dt.datetime(2021, 8, 1), dt.datetime(2024, 7, 31), None, None)],
        vanaf="01-08-2020",
    ), "test")
    assert crebo.zoek("99999", lijst)["status"] == "not_found"
    assert crebo.zoek("25000", lijst)["status"] == "found"
    amb = crebo.zoek("25604", lijst)
    assert amb["status"] == "ambiguous" and [m["naam"] for m in amb["matches"]] == ["Oud", "Nieuw"]
    # na het einde van de opleiding van het eerste dossier blijft er één geldige rij over
    r = crebo.zoek("25604", lijst, peildatum="2025-01-01")
    assert r["status"] == "found" and r["matches"][0]["naam"] == "Nieuw" and r["editie"] == "test"
    # voor de ingangsdatum van de editie is er niets geldig
    assert crebo.zoek("25000", lijst, peildatum="2019-01-01")["status"] == "not_found"


def test_latest_zonder_gevalideerde_editie_valt_niet_terug():
    with pytest.raises(crebo.CreboEditieOnbekend, match="ververs"):
        crebo.laad("latest")
    with pytest.raises(crebo.CreboEditieOnbekend):
        crebo.zoek("25604")


def test_ververs_cachet_en_latest_is_nieuwste_gecontroleerde():
    crebo.ververs("codelijst_2025_april", client=FakeClient(groot([(None, "Speciaal", 77777, "Speciaal", 2)])))
    m = crebo.manifest()["codelijst_2025_april"]
    assert m["rijen"] == 121 and len(m["sha256"]) == 64 and m["bron_url"].endswith("/58905")
    r = crebo.zoek("77777")
    assert r["status"] == "found" and r["editie"] == "codelijst_2025_april" and r["gecontroleerd_op"]


def test_afgekeurde_editie_komt_niet_in_manifest():
    kort = xlsx([(None, "D", 25604, "Te klein", 3)])
    with pytest.raises(crebo.CreboSchemaFout, match="rijen"):
        crebo.ververs("codelijst_2025_april", client=FakeClient(kort))
    assert crebo.manifest() == {}
    with pytest.raises(crebo.CreboSchemaFout, match="contenttype"):
        crebo.ververs("codelijst_2025_april", client=FakeClient(groot(), ctype="text/html"))
    with pytest.raises(crebo.CreboSchemaFout, match="signatuur|leesbaar"):
        crebo.ververs("codelijst_2025_april", client=FakeClient(b"<html>fout</html>"))
    assert crebo.manifest() == {}


def test_onbekende_editie():
    with pytest.raises(crebo.CreboEditieOnbekend, match="Bekend"):
        crebo.ververs("codelijst_1999", client=FakeClient(b""))


def test_gewijzigd_cachebestand_wordt_geweigerd():
    crebo.ververs("codelijst_2025_april", client=FakeClient(groot()))
    (crebo.cache_dir() / "codelijst_2025_april.xlsx").write_bytes(groot([(None, "D", 1, "x", 1)]))
    with pytest.raises(crebo.CreboSchemaFout, match="checksum"):
        crebo.laad("latest")


def test_loaderconfig_komt_uit_catalogus():
    cat = {r["_sbb_id"]: {x["naam"]: x["output_id"] for x in r["_resources"]} for r in sbb.catalog()}
    for ds, res in cat.items():
        assert {r["naam"]: r["output_id"] for r in sbb.resources(ds)} == res


@pytest.mark.skipif(not __import__("os").environ.get("RIODATA_LIVE"), reason="live-test: zet RIODATA_LIVE=1")
def test_live_smoke_nieuwe_editie_wordt_pas_vrijgegeven_na_validatie():
    """Niet lokaal gedraaid (geen netwerk bij ontwikkeling): controleert contenttype, kolommen en omvang."""
    lijst = crebo.ververs("codelijst_2025_april")
    assert lijst.rijen and crebo.manifest()["codelijst_2025_april"]["rijen"] == len(lijst.rijen)


class MeerdereBestanden(FakeClient):
    """Fake client die per editie-URL een ander bestand levert."""

    def __init__(self, per_id):
        self.per_id = per_id

    def get(self, url, **kw):
        self.content = self.per_id[url.rsplit("/", 1)[-1]]
        self.ctype = "application/octet-stream"
        return super().get(url, **kw)


def test_latest_wordt_niet_teruggedraaid_door_hercontrole_van_een_oudere_editie():
    """Review F3: opnieuw controleren van april 2025 mocht latest niet naar 2025 terugzetten."""
    bestanden = MeerdereBestanden({"58905": groot(vanaf="01-08-2025"), "58909": groot(vanaf="01-08-2026")})
    crebo.ververs("codelijst_2026_april", client=bestanden)
    crebo.ververs("codelijst_2025_april", client=bestanden)          # later gecontroleerd, maar oudere editie
    assert crebo.laad("latest").editie == "codelijst_2026_april"
    assert crebo.laad("last_verified").editie == "codelijst_2025_april"   # expliciet, niet vermomd als nieuwste
    r = crebo.zoek("25000")
    assert r["editie"] == "codelijst_2026_april" and r["geldig_vanaf"] == "2026-08-01"
    assert r["bron_url"].endswith("/58909") and len(r["sha256"]) == 64


def test_latest_bij_gelijke_ingangsdatum_volgt_catalogusvolgorde():
    bestanden = MeerdereBestanden({"58905": groot(vanaf="01-08-2025"), "58907": groot(vanaf="01-08-2025")})
    crebo.ververs("codelijst_2025_oktober", client=bestanden)
    crebo.ververs("codelijst_2025_april", client=bestanden)
    assert crebo.laad("latest").editie == "codelijst_2025_oktober"


def test_manifest_bewaart_geldig_vanaf_los_van_controledatum():
    crebo.ververs("codelijst_2025_april", client=FakeClient(groot(vanaf="01-08-2025")))
    m = crebo.manifest()["codelijst_2025_april"]
    assert m["geldig_vanaf"] == "2025-08-01" and m["gecontroleerd_op"] != m["geldig_vanaf"]
