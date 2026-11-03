"""Tijdmetadata: gesplitste velden met bronzin, conflicten expliciet, geen verzonnen claims."""
import riodata


def duo(i):
    return next(r for r in riodata.catalog("duo") if r["_ckan_id"] == i)


def test_prognose_horizon_komt_uit_de_bron_en_oude_claim_blijft_zichtbaar():
    r = duo("studentprognoses-mbo-per-instelling")
    t = r["_tijd"]
    assert r["periode"] == "2021-2040" == t["periode"]["waarde"] and t["periode"]["soort"] == "prognose"
    assert "2021-2040" in t["periode"]["bronzin"]
    assert {"veld": "periode", "waarde": "2021-2030", "reviewstatus": "onjuist volgens bron (2021-2040)"} in t["eerdere_catalogusclaims"]


def test_editie_is_niet_het_voorspelde_jaar():
    t = duo("studentprognoses-mbo-per-instelling")["_tijd"]
    assert t["editie"]["publicatiedatum"] == "2026-04-29"
    assert "versie 1" in t["editie"]["versies"] and "versie 2" in t["editie"]["versies"]
    assert not t["periode"]["waarde"].startswith("2026")          # editiejaar != prognosehorizon
    assert "peildatum 01-10-2025" in t["peildatum"]["bronzin"]    # peildatum van de bron, apart veld


def test_verversingsconflict_is_expliciet():
    r = duo("studentprognoses-mbo-per-instelling")
    t = r["_tijd"]
    assert t["verversing"]["waarde"] == "twee keer per jaar" and "Twee keer" in r["frequentie"]
    (c,) = t["claims_in_conflict"]
    assert c["waarde"] == "jaarlijks" and "ANNUAL" in c["bron"] and c["reviewstatus"].startswith("conflict")


def test_mbo_aanbod_frequentie_is_dagelijks_met_bronzin():
    r = duo("mbo_opleidingsaanbod")
    assert r["frequentie"] == "Dagelijks" and r["_tijd"]["verversing"]["waarde"] == "dagelijks"
    assert "dagelijks geactualiseerd" in r["_tijd"]["verversing"]["bronzin"]
    assert r["_tijd"]["periode"]["waarde"] is None       # actueel overzicht, geen waarnemingsperiode
    assert r["_tijd"]["editie"] is None


GECONTROLEERD = {
    "studentprognoses-mbo-per-instelling", "mbo_opleidingsaanbod",
    "p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl",
    "mbo-studenten-per-instelling", "mbo-studenten-per-sectorkamer-en-leerweg",
    "instromende-mbo-studenten", "gediplomeerde-mbo-studenten", "adressen_mbo", "adressen_ho",
}


def test_andere_records_hebben_geen_verzonnen_tijdclaims():
    met = {r["_ckan_id"] for r in riodata.catalog("duo") if "_tijd" in r}
    assert met == GECONTROLEERD


def test_historie_en_prognose_per_rij_te_scheiden():
    t = duo("studentprognoses-mbo-per-instelling")["_tijd"]
    hp = t["historie_prognose"]
    assert hp["kolom"] == "Type" and hp["historie"] == "2021-2025" and hp["prognose"] == "2026-2040"
    assert (t["data_dekking"]["van"], t["data_dekking"]["tot"]) == (2021, 2040)
    kaart = duo("studentprognoses-mbo-per-instelling")["_zoekkaart"]["tijd"]
    assert "historie 2021-2025, prognose 2026-2040" in kaart["historie_prognose"]


def test_zoekkaart_en_details_spreken_elkaar_niet_tegen():
    for i in GECONTROLEERD:
        r = duo(i)
        kaart, t = r["_zoekkaart"]["tijd"], r["_tijd"]
        assert kaart["conflicten"] == [c["reviewstatus"] for c in t["claims_in_conflict"]]
        if t["periode"]["waarde"]:
            assert kaart["periode"] == t["periode"]["waarde"]
        if t.get("data_dekking") and kaart["periode"]:
            van, tot = (int(x) for x in kaart["periode"].split("-"))
            dek = t["data_dekking"]
            assert (van, tot) == (dek["van"], dek["tot"]) or kaart["conflicten"], i


def test_conflict_tussen_bron_en_data_wordt_gemeld():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus"))
    import tijdmetadata
    tijd = {"periode": {"waarde": "2021-2030"}}
    (c,) = tijdmetadata.conflicten(tijd, {"van": 2021, "tot": 2040})
    assert c["bron"] == "data_dekking" and "2021-2030" in c["reviewstatus"]
    assert tijdmetadata.conflicten(tijd, {"van": 2021, "tot": 2030}) == []
    assert tijdmetadata.conflicten({"periode": {"waarde": None}}, {"van": 1, "tot": 2}) == []


def test_mbo_peildatum_en_voorlopig_per_dataset():
    for i in ("mbo-studenten-per-instelling", "instromende-mbo-studenten", "gediplomeerde-mbo-studenten"):
        t = duo(i)["_tijd"]
        assert t["peildatum"]["waarde"] == "1 oktober van het studiejaar"
        assert t["editie"]["voorlopig"] == ["2025"]
    assert duo("adressen_ho")["_tijd"]["peildatum"]["waarde"] == "moment van aanmaak van de levering"


def test_definities_kloppen_met_volledige_domeinen():
    """Codes die een scoped definitie noemt, komen in de data van die dataset voor."""
    snap = riodata.duo._schema_snapshot()["datasets"]
    def domein(ds, kolom):
        waarden = set()
        for r in snap[ds]["resources"]:
            info = ((r.get("waarden") or {}).get("kolommen") or {}).get(kolom) or {}
            waarden |= set(info.get("domein") or [])
        return waarden
    assert domein("mbo_opleidingsaanbod", "OPLEIDINGSVORM") == {
        "KLASSIKAAL", "KLASSIKAAL_EN_ONLINE", "ONLINE", "COACHING", "LEZING", "ZELFSTUDIE"}
    assert domein("p01hoinges", "OPLEIDINGSVORM") == {"VT", "DT", "DU"}
    assert domein("p01hoinges", "GESLACHT") == {"MAN", "VROUW", "ONBEKEND"}
    assert domein("gediplomeerde-mbo-studenten", "LEERWEG") == {"BBL", "BOLDT", "BOLVT", "EX", "OVO"}
    assert domein("studentprognoses-mbo-per-instelling", "Type") == {"Historie", "Prognose"}
    assert "HERKOMST" not in riodata.duo.DUO_COLUMN_GLOSSARY  # VZP/VZP_MTGO, geen NL/EU


def test_elke_claim_heeft_herkomst():
    for i in ("studentprognoses-mbo-per-instelling", "mbo_opleidingsaanbod"):
        t = duo(i)["_tijd"]
        assert t["bron"]["url"].startswith("https://onderwijsdata.duo.nl/api/3/action/package_show")
        assert t["bron"]["opgehaald_op"] and t["reviewstatus"].startswith("bronverificatie")
