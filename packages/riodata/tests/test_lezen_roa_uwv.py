"""ROA/UWV-loaders: aparte fouten per stap, geen stille eenkolomstabel, herleidbare snapshot."""
import io
import zipfile

import pytest

pytest.importorskip("pandas")

from riodata import _lezen, roa, uwv  # noqa: E402

UWV_CSV = (
    "PEILDATUM;BEROEP_CD;REC_TYPE;AANTAL;OPLNIV_GEM\n"
    "2023-05-16;1;Vacature;5;3,5\n2023-05-16;2;Werkzoekende;7;2,5\n2023-05-09;3;Vacature;1;3,0\n"
).encode()


class Resp:
    def __init__(self, content, url="https://x/f"):
        self.content, self.url = content, url

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def zonder_gevalideerd_schema(monkeypatch, request):
    """De meeste tests gebruiken nep-CSV's; de checksum/kolommen van het echte bestand gelden dan niet."""
    if "echt_schema" not in request.keywords:
        monkeypatch.setattr(roa, "_schema", lambda meta, file_id: None)


def zip_van(naam, inhoud):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(naam, inhoud)
    return buf.getvalue()


def test_roa_leest_csv_met_herkomst(monkeypatch):
    csv = "opleiding;aantal\nA;1\nB;2\n".encode("utf-8")
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(csv, "https://dv/1"))
    df = roa.load("ais2030", 0)
    assert list(df.columns) == ["opleiding", "aantal"]
    bron = df.attrs["bron"]
    assert bron["bron_url"] == "https://dv/1" and len(bron["sha256"]) == 64 and bron["encoding"] == "utf-8-sig"


def test_roa_latin1_wordt_nog_gedecodeerd(monkeypatch):
    csv = "naam;waarde\nCafé;1\n".encode("latin-1")
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(csv))
    assert roa.load("ais2030", 0)["naam"][0] == "Café"


def test_verkeerde_separator_is_geen_succes(monkeypatch):
    csv = b"opleiding,aantal\nA,1\nB,2\n"
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(csv))
    with pytest.raises(_lezen.SchemaFout, match="separator"):
        roa.load("ais2030", 0)


def test_parserfout_wordt_niet_als_decodeerfout_gemeld():
    kapot = b'a;b\n"niet gesloten;1\n'
    with pytest.raises(_lezen.ParserFout):
        _lezen.lees_csv(kapot, defaults={"sep": ";"}, engine="python")
    with pytest.raises(_lezen.ParserFout, match="niet te parseren"):
        _lezen.lees_csv(b"", defaults={"sep": ";"})


def test_echt_ondecodeerbaar_geeft_decodeerfout(monkeypatch):
    monkeypatch.setattr(_lezen, "ENCODINGS", ("utf-8",))
    with pytest.raises(_lezen.DecodeerFout):
        _lezen.lees_csv(b"a;b\n\xff;1\n", defaults={"sep": ";"})


def test_verwachte_kolommen_worden_afgedwongen():
    with pytest.raises(_lezen.SchemaFout, match="ontbreken"):
        _lezen.lees_csv(b"a;b\n1;2\n", defaults={"sep": ";"}, verwacht=("REC_TYPE",))


def test_oude_exceptietypes_blijven_bruikbaar():
    assert issubclass(_lezen.DecodeerFout, RuntimeError) and issubclass(_lezen.SchemaFout, ValueError)


def _uwv(monkeypatch, zipbytes):
    snap = {"naam": "n", "url": "https://x/uwv_20230516.zip", "created": "2023-05-16T00:00:00"}
    monkeypatch.setattr(uwv, "_get_snapshots", lambda: [snap])
    monkeypatch.setattr(uwv.httpx, "get", lambda *a, **k: Resp(zipbytes, snap["url"]))


def test_uwv_latest_geeft_werkelijke_peildatum_en_archiefstatus(monkeypatch):
    _uwv(monkeypatch, zip_van("data.csv", UWV_CSV))
    df = uwv.load()
    s = df.attrs["snapshot"]
    assert s["peildatum"] == "2023-05-16" and s["status"] == "historisch_archief"
    assert "geen actuele vacatures" in s["opmerking"]
    assert s["gevraagd"] == "latest" and s["bron_url"].endswith(".zip") and len(s["sha256"]) == 64


def test_uwv_rec_type_filter_behoudt_snapshotinfo(monkeypatch):
    _uwv(monkeypatch, zip_van("data.csv", UWV_CSV))
    df = uwv.load(rec_type="vacature")
    assert set(df["REC_TYPE"]) == {"Vacature"} and df.attrs["snapshot"]["peildatum"] == "2023-05-16"


def test_uwv_ontbrekende_csv_en_kapotte_zip(monkeypatch):
    _uwv(monkeypatch, zip_van("leesmij.txt", "x"))
    with pytest.raises(_lezen.ParserFout, match="Geen CSV"):
        uwv.load()
    _uwv(monkeypatch, b"geen zip")
    with pytest.raises(_lezen.ParserFout, match="geldige ZIP"):
        uwv.load()


def test_uwv_rec_type_zonder_kolom_is_schemafout(monkeypatch):
    _uwv(monkeypatch, zip_van("data.csv", "A;B\n1;2\n"))
    with pytest.raises(_lezen.SchemaFout, match="REC_TYPE"):
        uwv.load(rec_type="Vacature")


def test_uwv_limiet_op_uitgepakte_omvang(monkeypatch):
    monkeypatch.setattr(_lezen, "MAX_BYTES", 10)
    _uwv(monkeypatch, zip_van("data.csv", UWV_CSV))
    with pytest.raises(_lezen.LimietFout):
        uwv.load()


def test_gebruikerskwargs_overschrijven_defaults_zonder_typeerror(monkeypatch):
    """Review F5: sep/encoding/decimal/low_memory van de gebruiker moeten blijven werken."""
    csv = "opleiding;aantal\nA;1\n".encode("utf-8")
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(csv))
    assert list(roa.load("ais2030", "uitkomsten", sep=";").columns) == ["opleiding", "aantal"]
    df = roa.load("ais2030", "uitkomsten", encoding="utf-8")
    assert df.attrs["bron"]["encoding"] == "utf-8"
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp("a,b\n1.5,2\n".encode()))
    assert roa.load("ais2030", 0, sep=",")["a"][0] == 1.5
    _uwv(monkeypatch, zip_van("data.csv", UWV_CSV.decode().replace(",", ".")))
    assert uwv.load(decimal=".")["OPLNIV_GEM"].iloc[0] == 3.5
    _uwv(monkeypatch, zip_van("data.csv", UWV_CSV))
    assert len(uwv.load(low_memory=True)) == 3
    assert len(uwv.load(sep=";", encoding="utf-8")) == 3


def test_opgegeven_encoding_wordt_niet_stil_vervangen():
    with pytest.raises(_lezen.DecodeerFout):
        _lezen.lees_csv("a;b\nCafé;1\n".encode("latin-1"), defaults={"sep": ";"}, encoding="utf-8")


# ── RIO-06: inhoudelijke schema's per bestand ────────────────────────────────

import json  # noqa: E402

import riodata  # noqa: E402


def _roa_res(ds, naam):
    rec = next(r for r in riodata.catalog(source="roa") if r["_roa_id"] == ds)
    return next(x for x in rec["_resources"] if x["naam"] == naam)


def test_elk_roa_bestand_heeft_gevalideerd_schema():
    for rec in riodata.catalog(source="roa"):
        for x in rec["_resources"]:
            s = x["schema"]
            assert s["kolommen"] and s["aantal_rijen"] > 0 and len(s["dataverse_sha1"]) == 40
            assert s["granulariteit"] and s["beperkingen"] and s["decimaal"] == ","
            assert all(b["bron"] for b in s["beperkingen"])
        recentst = [x for x in rec["_resources"] if x["schema"]["meest_recente_editie"]]
        assert len({x["schema"]["soort"] for x in recentst}) == len(recentst)  # één per soort


def test_roa_beschrijving_spreekt_schema_niet_tegen():
    for rec in riodata.catalog(source="roa"):
        tekst = (rec["samenvatting"] + " " + rec["niet_geschikt_voor"]).lower()
        assert "uitsluitend nationale" not in tekst and "uitsluitend als landelijk" not in tekst
        regio = [x for x in rec["_resources"] if x["schema"]["soort"] == "arbeidsmarkt"]
        assert all(x["schema"]["uitsplitsingen"]["regio"]["aantal"] > 12 for x in regio)
        assert "regio" in tekst and "instelling" in tekst
        for x in rec["_resources"]:
            if x["schema"]["soort"] in ("uitkomsten", "schoolverlaters"):
                assert not any("regio" in k.lower() for k in x["schema"]["kolommen"])


def test_roa_editie_2026_aanwezig_en_oude_namen_blijven():
    assert _roa_res("ais2030", "arbeidsmarkt_editie2026")["schema"]["meest_recente_editie"]
    assert _roa_res("ais2030", "arbeidsmarkt")["file_id"] == 572235
    assert _roa_res("ais2030", "uitkomsten")["schema"]["sentinels"]["-9"]["betekenis"] == "niet gedocumenteerd"


@pytest.mark.echt_schema
def test_roa_checksum_afwijking_is_fout(monkeypatch):
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(b"a;b\n1;2\n"))
    with pytest.raises(_lezen.ChecksumFout):
        roa.load("ais2030", "uitkomsten")


@pytest.mark.echt_schema
def test_roa_decimale_komma_en_verwachte_kolommen(monkeypatch):
    s = _roa_res("ais2030", "uitkomsten")["schema"]
    rij = ";".join("1" for _ in s["kolommen"])
    csv = (";".join(s["kolommen"]) + "\n" + rij.replace("1", "42,6", 1) + "\n").encode()
    monkeypatch.setattr(roa, "_schema", lambda meta, fid: {**s, "dataverse_sha1": None})
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(csv))
    df = roa.load("ais2030", "uitkomsten")
    assert df.iloc[0, 0] == 42.6  # geen tekst '42,6'
    assert df.attrs["schema"]["editie"] == "2025"
    kapot = (";".join(s["kolommen"][:-1]) + "\n" + ";".join("1" for _ in s["kolommen"][:-1]) + "\n").encode()
    monkeypatch.setattr(roa.httpx, "get", lambda *a, **k: Resp(kapot))
    with pytest.raises(_lezen.SchemaFout, match="ontbreken"):
        roa.load("ais2030", "uitkomsten")


def test_uwv_schema_vacature_versus_werkzoekenden():
    s = riodata.catalog(source="uwv")[0]["_schema"]
    assert set(s["rec_types"]) == {"Vacature", "ErvaringsBeroep", "WensBeroep"}
    vac, erv, wens = (s["rec_types"][k] for k in ("Vacature", "ErvaringsBeroep", "WensBeroep"))
    assert not vac["opleidingsniveau"] and erv["opleidingsniveau"] and wens["opleidingsniveau"]
    assert "AANT_OPLNIV_1" in vac["kolommen_altijd_leeg"] and "AANT_OPLNIV_1" in erv["kolommen_met_waarden"]
    assert "AANT_JR_ERV_GEM" in wens["kolommen_altijd_leeg"]
    assert s["laatste_peildatum"] == "2023-05-16" and s["status"] == "historisch_archief"
    assert len(s["schema_gelijk_in_snapshots"]) >= 4


def test_uwv_catalogus_noemt_geen_onbestaand_rec_type():
    rec = riodata.catalog(source="uwv")[0]
    tekst = json.dumps({k: rec[k] for k in ("niet_geschikt_voor", "samenvatting", "kolomtoelichting")})
    assert "rec_type='Werkzoekende'" not in tekst and "'Werkzoekende' (geregistreerde" not in tekst
    for kolom in ("PC4", "BEROEPSGROEP", "ANTAL"):
        assert kolom not in rec["kolomtoelichting"]


def test_uwv_onbekend_rec_type_geeft_opties(monkeypatch):
    csv = "PEILDATUM;REC_TYPE;AANTAL\n16-05-2023;Vacature;1\n16-05-2023;ErvaringsBeroep;2\n".encode()
    _uwv(monkeypatch, zip_van("data.csv", csv))
    with pytest.raises(ValueError, match="ErvaringsBeroep of WensBeroep"):
        uwv.load(rec_type="Werkzoekende")
    df = uwv.load()
    assert df.attrs["snapshot"]["peildatum"] == "2023-05-16"  # ISO uit DD-MM-YYYY
