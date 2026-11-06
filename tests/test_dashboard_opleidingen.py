"""Het dashboard Opleidingen (#957): per opleiding van een hogeschool of universiteit de cijfers uit de
Studiekeuzedatabase van LCSK, naast het landelijke cijfer van LCSK, zonder rangorde.

Er staat geen data van LCSK in de repo: `onderwijsbronnen.skdb.proefbestand` is een export met dezelfde vorm en
verzonnen getallen. Het register (DUO) staat hier als woordenboek, zonder netwerk.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

import data.dashboard_opleidingen as opleidingen
from core import actualiteit, config
from data import instellingen
from tools import studiekeuze

_NU = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)

_REGISTER = {
    "hogeschool utrecht": ("Hogeschool Utrecht", "hbo", "25DW"),
    "hu": ("Hogeschool Utrecht", "hbo", "25DW"),
    "universiteit leiden": ("Universiteit Leiden", "wo", "21PB"),
    "universiteit utrecht": ("Universiteit Utrecht", "wo", "21PD"),
    "proefhogeschool particulier": ("Proefhogeschool Particulier", "hbo", "99XX"),
    "roc midden nederland": ("ROC Midden Nederland", "mbo", "25PZ"),
}


def _profiel(naam: str) -> dict | None:
    gevonden = _REGISTER.get(" ".join(naam.split()).lower())
    return None if gevonden is None else {"naam": gevonden[0], "sector": gevonden[1], "instellingscode": gevonden[2]}


def _register() -> list[dict]:
    return [{"naam": n, "type": t, "instellingscode": c} for n, t, c in set(_REGISTER.values())]


@pytest.fixture(autouse=True)
def proefexport_en_register(monkeypatch):
    """De proefexport achter de sleutel, het register als woordenboek; `opgehaald` telt de downloads."""
    opgehaald: list[int] = []

    def haal_op(*a, **k):
        opgehaald.append(1)
        return proefbestand.standaard()

    monkeypatch.setattr(skdb, "haal_op", haal_op)
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "proefsleutel")
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)
    monkeypatch.setattr(instellingen, "resolve_alias", lambda naam: (_profiel(naam) or {}).get("naam", naam))
    monkeypatch.setattr(instellingen, "get_all", _register)
    monkeypatch.setattr(actualiteit, "nu", lambda: _NU)
    studiekeuze._export.cache_clear()
    yield opgehaald
    studiekeuze._export.cache_clear()


def _rij(uit: dict, opleiding: str, vorm: str) -> dict:
    (rij,) = [r for r in uit["opleidingen"] if r["opleiding"] == opleiding and r["vorm"] == vorm]
    return rij


# --- de opleidingentabel ---------------------------------------------------------------------------------------------


def test_per_opleiding_en_vorm_de_kerncijfers_uit_het_pakket():
    uit = opleidingen.load_dashboard_opleidingen("HU")

    assert uit["gevonden"] is True
    assert (uit["instelling"], uit["type"], uit["brin"]) == ("Hogeschool Utrecht", "hbo", "25DW")
    # Dezelfde rijen en afronding als het pakket (en dus de chat en de snippet): niet opnieuw gerekend.
    pakket = skdb.opleidingen(skdb.lees(*proefbestand.standaard()), brin="25DW")
    assert [(r["opleiding"], r["vorm"]) for r in uit["opleidingen"]] == [(r["opleiding"], r["vorm"]) for r in pakket]
    ict = _rij(uit, "ICT", "voltijd")
    ict_pakket = _rij({"opleidingen": pakket}, "ICT", "voltijd")
    for veld in (*opleidingen.KOLOMMEN, *opleidingen.THEMANAMEN):
        assert ict[veld] == ict_pakket[veld], veld
    assert (ict["croho"], ict["graad"], ict["plaats"]) == (30020, "Bachelor", "Utrecht")
    assert (ict["nse_oordeel"], ict["nse_respondenten"], ict["nse_oordeel_landelijk"]) == (3.61, 120, 3.53)
    assert (ict["studenten"], ict["eerstejaars"], ict["doorstroom_jaar2_pct"]) == (900, 250, 70.0)


def test_op_naam_en_niet_op_een_cijfer():
    # Geen rangorde (art. 5): op naam, plaats en vorm, ook al heeft Verpleegkunde het hogere oordeel.
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")

    assert [(r["opleiding"], r["vorm"]) for r in uit["opleidingen"]] == [
        ("ICT", "deeltijd"),
        ("ICT", "voltijd"),
        ("Verpleegkunde", "voltijd"),
    ]


def test_het_landelijke_diplomarendement_staat_ernaast_en_een_leeg_veld_blijft_leeg():
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")

    deeltijd = _rij(uit, "ICT", "deeltijd")
    assert deeltijd["diploma_opleiding_pct"] is None  # leeg in de bron: geen 0
    assert deeltijd["doorstroom_jaar2_pct"] is None
    assert deeltijd["diploma_opleiding_pct_landelijk"] == 50.0  # studievormen van dezelfde studie en vorm
    assert _rij(uit, "Verpleegkunde", "voltijd")["diploma_opleiding_pct_landelijk"] == 50.0


def test_enige_aanbieder_zegt_dat_landelijk_deze_opleiding_zelf_is():
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")

    # ICT voltijd bieden HU en de proefhogeschool aan; deeltijd alleen de HU.
    assert _rij(uit, "ICT", "voltijd")["aanbieders_landelijk"] == 2
    assert _rij(uit, "ICT", "deeltijd")["aanbieders_landelijk"] == 1


def test_een_oordeel_op_minder_dan_30_respondenten_is_onzeker_zoals_in_de_chat():
    uit = opleidingen.load_dashboard_opleidingen("Proefhogeschool Particulier")

    (ict,) = uit["opleidingen"]
    assert ict["nse_respondenten"] == 15 and ict["nse_onzeker"] is True
    assert uit["min_respondenten"] == studiekeuze.MIN_RESPONDENTEN == 30
    hu = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")
    assert all(not r.get("nse_onzeker") for r in hu["opleidingen"])  # 40 respondenten en meer


def test_zonder_oordeel_is_niets_onzeker():
    bmw = _rij(opleidingen.load_dashboard_opleidingen("Universiteit Leiden"), "Biomedische Wetenschappen", "voltijd")
    assert bmw["nse_oordeel"] is None and not bmw.get("nse_onzeker")


# --- NSE-thema's (B4) ------------------------------------------------------------------------------------------------


def test_de_nse_themas_per_vorm_in_de_volgorde_van_het_pakket():
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")

    assert [t["veld"] for t in uit["themas"]] == list(skdb.NSE_THEMAS.values())
    assert all(t["naam"] for t in uit["themas"])
    assert _rij(uit, "ICT", "voltijd")["nse_docenten"] == 3.8
    assert _rij(uit, "ICT", "voltijd")["nse_sfeer"] is None


# --- arbeidsmarkt van de opleidingsrichting (D1) ---------------------------------------------------------------------


def test_arbeidsmarkt_per_opleiding_landelijk_per_rubriek():
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")

    markt = {r["opleiding"]: r for r in uit["arbeidsmarkt"]}
    assert list(markt) == ["ICT", "Verpleegkunde"]  # per opleiding, niet per vorm
    ict = markt["ICT"]
    assert (ict["croho"], ict["soi_rubriek"], ict["aansluiting_studie_baan"]) == (30020, "informatica", "goede")
    assert (ict["salaris_mediaan_bruto_maand"], ict["werkloos_pct"], ict["baan_op_niveau_pct"]) == (3295, 2.5, 80.0)
    assert ict["reden_leeg"] is None
    assert markt["Verpleegkunde"]["salaris_mediaan_bruto_maand"] == 3100.5
    assert markt["Verpleegkunde"]["baan_op_niveau_pct"] is None  # leeg in de bron


def test_de_arbeidsmarktcijfers_zijn_die_van_de_voltijdafgestudeerden():
    # De SOI-rubriek van ICT heeft voor deeltijd geen cijfers: de rij per opleiding neemt voltijd, zoals LCSK ze geeft.
    markt = {r["opleiding"]: r for r in opleidingen.load_dashboard_opleidingen("HU")["arbeidsmarkt"]}
    voltijd = next(r for r in skdb.studie(skdb.lees(*proefbestand.standaard()), 30020) if r["vorm"] == "voltijd")
    assert markt["ICT"]["salaris_mediaan_bruto_maand"] == voltijd["salaris_mediaan_bruto_maand"]


def test_een_wo_bachelor_heeft_geen_arbeidsmarktcijfers_en_zegt_waarom():
    uit = opleidingen.load_dashboard_opleidingen("Universiteit Leiden")

    psy = next(r for r in uit["arbeidsmarkt"] if r["opleiding"] == "Psychologie")
    assert psy["salaris_mediaan_bruto_maand"] is None and psy["werkloos_pct"] is None
    assert psy["aansluiting_studie_baan"] is None  # "(missing, …)" van LCSK is geen waarde
    assert psy["reden_leeg"] == opleidingen.GEEN_ARBEIDSMARKT_WO_BACHELOR


def test_de_uitleg_zegt_dat_het_landelijke_cijfers_per_rubriek_zijn():
    uitleg = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")["uitleg"]

    assert studiekeuze.ARBEIDSMARKT in uitleg["arbeidsmarkt"]
    assert "niet over de eigen afgestudeerden" in uitleg["arbeidsmarkt"]
    assert studiekeuze.DIPLOMARENDEMENT in uitleg["diplomarendement"]
    assert studiekeuze.DOORSTROOM_JAAR2 in uitleg["doorstroom"]
    assert "Nationale Studenten Enquête 2026" in uitleg["nse"] and "30" in uitleg["nse"]
    assert "2025/26" in uitleg["aantallen"]
    assert "geen 0" in uitleg["leeg"]
    assert "rangschikt" in uitleg["volgorde"]


# --- numerus fixus (B5) ----------------------------------------------------------------------------------------------


def test_numerus_fixus_met_capaciteit_studiejaar_en_voertaal():
    uit = opleidingen.load_dashboard_opleidingen("Universiteit Leiden")

    assert [(r["opleiding"], r["studiejaar"], r["capaciteit"], r["voertaal"]) for r in uit["numerus_fixus"]] == [
        ("Biomedische Wetenschappen", 2026, 60, "Voertaal-overstijgend"),
        ("Biomedische Wetenschappen", 2027, 71, "Voertaal-overstijgend"),
    ]
    bmw = _rij(uit, "Biomedische Wetenschappen", "voltijd")
    assert (bmw["numerus_fixus_capaciteit"], bmw["numerus_fixus_studiejaar"]) == (71, 2027)
    assert opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")["numerus_fixus"] == []


def test_de_kerncijfers_tellen_zonder_te_rangschikken():
    assert opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")["aantallen"] == {
        "opleidingen": 2,
        "vormen": 3,
        "met_nse": 3,
        "numerus_fixus": 0,
    }


# --- wie geen cijfers krijgt -----------------------------------------------------------------------------------------


def test_een_mbo_instelling_krijgt_de_vaste_melding_zonder_de_export_te_laden(proefexport_en_register):
    uit = opleidingen.load_dashboard_opleidingen("ROC Midden Nederland")

    assert uit["gevonden"] is True and uit["type"] == "mbo"
    assert uit["melding"] == opleidingen.ALLEEN_HO
    assert "opleidingen" not in uit and uit["bronnen"] == []
    assert proefexport_en_register == []


def test_een_hogeschool_die_niet_in_de_studiekeuzedatabase_staat():
    uit = opleidingen.load_dashboard_opleidingen("Universiteit Utrecht")

    assert uit["gevonden"] is True and uit["opleidingen"] == []
    assert (
        uit["melding"]
        == "Universiteit Utrecht (21PD) staat niet in de Studiekeuzedatabase: er zijn geen cijfers per opleiding."
    )


def test_een_onbekende_instelling_is_niet_gevonden_met_suggesties():
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrect")

    assert uit["gevonden"] is False
    assert uit["beschikbare_instellingen"][0] == "Hogeschool Utrecht"


def test_een_onbekende_instelling_zonder_lijkende_naam():
    uit = opleidingen.load_dashboard_opleidingen("qqq")

    assert uit["gevonden"] is False and uit["beschikbare_instellingen"] == []
    assert uit["geen_suggesties"]


def test_een_leeg_register_is_een_storing_geen_niet_gevonden(monkeypatch):
    from data.dashboard import BronNietBeschikbaar

    monkeypatch.setattr(instellingen, "instellingsprofiel", lambda naam: None)
    monkeypatch.setattr(instellingen, "get_all", list)
    with pytest.raises(BronNietBeschikbaar):
        opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")


def test_een_export_die_niet_laadt_is_een_storing_met_de_naam_van_de_bron(monkeypatch):
    def kapot(*a, **k):
        raise skdb.SkdbFout("De Studiekeuzedatabase gaf HTTP 502 op de export.")

    monkeypatch.setattr(skdb, "haal_op", kapot)
    with pytest.raises(opleidingen.StudiekeuzeNietBeschikbaar) as fout:
        opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")
    assert str(fout.value) == opleidingen.EXPORT_NIET_BESCHIKBAAR
    assert "HTTP" not in str(fout.value) and "proefsleutel" not in str(fout.value)


# --- één export, met haar bronvermelding ------------------------------------------------------------------------------


def test_het_dashboard_en_de_chat_delen_een_lading(proefexport_en_register):
    opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")
    opleidingen.load_dashboard_opleidingen("Universiteit Leiden")
    studiekeuze.get_studiekeuze(instelling="Hogeschool Utrecht")

    assert proefexport_en_register == [1]


def test_het_bronblok_noemt_versie_jaren_en_de_verplichte_zin_van_lcsk():
    uit = opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")

    (bron,) = uit["bronnen"]
    assert (bron["bron"], bron["dataset"]) == ("LCSK", "studiekeuzedatabase")
    assert bron["titel"] == "Studiekeuzedatabase (hbo en wo)"
    assert bron["url"] == skdb.DOCUMENTATIE == "https://www.studiekeuze123.nl/studiekeuzedata"
    assert bron["editie"] == "26.6"
    assert bron["peilmoment"] == "versie 26.6, export van 2026-11-06, NSE 2026, 1cijferHO 2025/26"
    herkomst = skdb.herkomst(*proefbestand.standaard()[:1], proefbestand.BESTAND)
    assert bron["vermelding"] == studiekeuze.bronregel(herkomst)
    assert skdb.VERPLICHTE_ZIN in bron["vermelding"]
    assert bron["voorlopig"] is False
    assert uit["jaren"] == {"nse": 2026, "1cijferho": 2025}


def test_ook_een_tweede_lading_uit_de_cache_noemt_de_bron():
    opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")
    assert [b["bron"] for b in opleidingen.load_dashboard_opleidingen("Hogeschool Utrecht")["bronnen"]] == ["LCSK"]


# --- het eindpunt -----------------------------------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import routes.instellingen
    import server
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    monkeypatch.setattr(routes.instellingen, "DASHBOARDS_ENABLED", True)
    return TestClient(server.app)


def test_het_eindpunt_geeft_de_payload(client):
    resp = client.get("/api/dashboard/opleidingen", params={"instelling": "Hogeschool Utrecht"})

    assert resp.status_code == 200
    assert resp.json()["brin"] == "25DW" and len(resp.json()["opleidingen"]) == 3


def test_zonder_sleutel_is_het_dashboard_er_niet_en_laadt_het_niets(client, monkeypatch, proefexport_en_register):
    import routes.instellingen

    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "")
    resp = client.get("/api/dashboard/opleidingen", params={"instelling": "Hogeschool Utrecht"})

    # Zoals financien en personeel: een eindpunt op een bron die hier uit staat, bestaat niet (404).
    assert resp.status_code == 404
    assert resp.json() == {"error": routes.instellingen.BRON_UIT}
    assert proefexport_en_register == []


def test_een_export_die_niet_laadt_geeft_503_met_de_naam_van_de_bron(client, monkeypatch):
    def kapot(*a, **k):
        raise skdb.SkdbFout("De Studiekeuzedatabase weigert de sleutel (HTTP 401).")

    monkeypatch.setattr(skdb, "haal_op", kapot)
    resp = client.get("/api/dashboard/opleidingen", params={"instelling": "Hogeschool Utrecht"})

    assert resp.status_code == 503
    assert resp.json() == {"error": opleidingen.EXPORT_NIET_BESCHIKBAAR}


# --- de fixture van de frontend ---------------------------------------------------------------------------------------

_FIXTURE = Path(__file__).resolve().parent.parent / "frontend/src/__tests__/fixtures/dashboardOpleidingen.json"
_FIXTURE_INSTELLINGEN = {
    "hbo": "Hogeschool Utrecht",
    "wo": "Universiteit Leiden",
    "onzeker": "Proefhogeschool Particulier",
    "mbo": "ROC Midden Nederland",
}


def fixture_payloads() -> dict[str, dict]:
    """De payloads op de proefexport, zoals frontend/src/__tests__/dashboardOpleidingen.test.js ze leest, met een vast
    moment van ophalen. Na een wijziging aan de payload: zet `_SCHRIJF` op True, draai deze test en zet hem terug."""
    uit = {}
    for soort, naam in _FIXTURE_INSTELLINGEN.items():
        payload = opleidingen.load_dashboard_opleidingen(naam)
        for bron in payload.get("bronnen", []):
            bron["opgehaald_op"] = "2026-11-06T06:00:00+00:00"
        uit[soort] = payload
    return uit


_SCHRIJF = False


def test_de_fixture_van_de_frontend_is_de_payload_van_nu():
    payloads = json.loads(json.dumps(fixture_payloads(), ensure_ascii=False))
    if _SCHRIJF:
        _FIXTURE.write_text(json.dumps(payloads, ensure_ascii=False, indent=1) + "\n")
    assert json.loads(_FIXTURE.read_text()) == payloads
