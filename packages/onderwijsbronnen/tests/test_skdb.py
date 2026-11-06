"""De Studiekeuzedatabase (#957): ophalen met een sleutel, de vorm van de export toetsen en de overzichten.

Er staat geen data van LCSK in de repo; `skdb.proefbestand` bouwt een export met dezelfde ZIP-vorm en verzonnen getallen.
"""

from __future__ import annotations

import httpx
import pytest

import onderwijsbronnen
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

SLEUTEL = "geheime-proefsleutel"


@pytest.fixture
def export():
    return skdb.lees(*proefbestand.standaard())


# --- ophalen en sleutel ----------------------------------------------------------------------------------------


def test_zonder_sleutel_geen_request(monkeypatch):
    monkeypatch.delenv(skdb.SLEUTEL_ENV, raising=False)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("geen request zonder sleutel"))
    with pytest.raises(skdb.GeenSleutel, match=skdb.SLEUTEL_ENV):
        skdb.haal_op()


def test_de_sleutel_gaat_alleen_in_de_header_en_de_herkomst_komt_uit_de_bestandsnaam(monkeypatch):
    monkeypatch.setenv(skdb.SLEUTEL_ENV, SLEUTEL)
    gezien = {}

    def get(url, headers, **kwargs):
        gezien.update(url=url, headers=headers)
        return httpx.Response(
            200,
            content=proefbestand.zip_bytes(),
            headers={"content-disposition": f'attachment; filename="{proefbestand.BESTAND}"'},
        )

    monkeypatch.setattr(httpx, "get", get)
    inhoud, herkomst = skdb.haal_op()
    assert gezien["url"] == skdb.EXPORT
    assert gezien["headers"]["Authorization"] == f"Bearer {SLEUTEL}"
    assert SLEUTEL not in gezien["url"]
    assert (herkomst.versie, herkomst.datum, herkomst.bestand) == ("26.6", "2026-11-06", proefbestand.BESTAND)
    assert skdb.lees(inhoud, herkomst).tabellen


@pytest.mark.parametrize("status", [401, 403])
def test_een_geweigerde_sleutel_is_een_fout_zonder_de_sleutel(monkeypatch, status):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(status, text='{"error":"Token is invalid"}'))
    with pytest.raises(skdb.SkdbFout, match=f"weigert de sleutel \\(HTTP {status}\\)") as fout:
        skdb.haal_op(SLEUTEL)
    assert SLEUTEL not in str(fout.value)


def test_een_netwerkfout_noemt_de_sleutel_niet(monkeypatch):
    def get(*a, **k):
        raise httpx.ConnectError(f"kapot met {SLEUTEL}")

    monkeypatch.setattr(httpx, "get", get)
    with pytest.raises(skdb.SkdbFout, match="niet bereikbaar") as fout:
        skdb.haal_op(SLEUTEL)
    assert SLEUTEL not in str(fout.value) and fout.value.__cause__ is None


def test_een_export_zonder_vereiste_tabel_geeft_geen_uitkomst():
    inhoud = proefbestand.zip_bytes(weglaten=("opleidingvormen",))
    with pytest.raises(skdb.SkdbFout, match="opleidingvormen"):
        skdb.lees(inhoud, skdb.herkomst(inhoud, proefbestand.BESTAND))


def test_geen_zip_geen_uitkomst():
    with pytest.raises(skdb.SkdbFout, match="geen ZIP"):
        skdb.lees(b"<html>", skdb.herkomst(b"<html>", ""))


def test_de_ingekorte_bestandsnaam_heet_voluit(export):
    assert "lotingopleidingendecentraleselecties" in export.tabellen
    assert export.rijen("lotingopleidingendecentraleselecties")
    with pytest.raises(skdb.SkdbFout, match="staat niet in de export"):
        export.rijen("studieroutes")


def test_een_onbekende_bestandsnaam_geeft_geen_versie():
    assert skdb.herkomst(b"x", "iets.zip").versie is None


# --- overzichten ------------------------------------------------------------------------------------------------


def test_opleidingen_per_vorm_met_het_landelijke_oordeel_ernaast(export):
    rijen = skdb.opleidingen(export, brin="25DW", croho=30020)
    assert [(r["vorm"], r["nse_oordeel"], r["nse_oordeel_landelijk"]) for r in rijen] == [
        ("deeltijd", 3.7, 3.66),
        ("voltijd", 3.61, 3.53),
    ]
    voltijd = rijen[1]
    assert voltijd["plaats"] == "Utrecht"
    assert (voltijd["doorstroom_jaar2_pct"], voltijd["diploma_opleiding_pct"]) == (70.0, 45.5)
    # Wat een andere bron leidend heeft, staat er niet in (#878).
    assert not {"studenten", "eerstejaars", "collegegeld_wettelijk", "accreditatiebesluit"} & set(voltijd)


def test_numerus_fixus_neemt_het_nieuwste_studiejaar(export):
    (rij,) = skdb.opleidingen(export, brin="21PB", alleen_numerus_fixus=True)
    assert (rij["opleiding"], rij["numerus_fixus_capaciteit"], rij["numerus_fixus_studiejaar"]) == (
        "Biomedische Wetenschappen",
        71,
        2027,
    )
    assert rij["nse_oordeel"] is None  # leeg in de bron blijft leeg


def test_sorteren_op_oordeel_zet_lege_waarden_achteraan(export):
    rijen = skdb.opleidingen(export, vorm="voltijd", sorteer="oordeel", themas=False)
    oordelen = [r["nse_oordeel"] for r in rijen]
    assert oordelen == [4.2, 4.05, 3.9, 3.61, None]
    assert "nse_docenten" not in rijen[0]


def test_filters_op_naam_plaats_soort_en_graad(export):
    assert {r["instelling"] for r in skdb.opleidingen(export, naam="ict")} == {"Hogeschool Utrecht", "Proefhogeschool Particulier"}
    assert [r["plaats"] for r in skdb.opleidingen(export, plaats="hertogenbosch")] == ["'s-Hertogenbosch"]
    assert {r["soort_ho"] for r in skdb.opleidingen(export, soort_ho="wo")} == {"WO"}
    assert skdb.opleidingen(export, graad="master") == []


def test_studie_met_arbeidsmarkt_van_de_soi_rubriek(export):
    voltijd, deeltijd = skdb.studie(export, 30020)
    assert (voltijd["vorm"], voltijd["aantal_opleidingen"], voltijd["nse_oordeel"]) == ("voltijd", 2, 3.53)
    assert (voltijd["soi_rubriek"], voltijd["salaris_mediaan_bruto_maand"], voltijd["werkloos_pct"]) == ("informatica", 3295, 2.5)
    assert deeltijd["salaris_mediaan_bruto_maand"] is None
    # Het ROA-opleidingstype als sleutel naar ROA; de aansluiting studie-baan zelf komt uit ROA-AIS (#878).
    assert voltijd["roa_opleidingstype"] == "hbo - ict" and "aansluiting_studie_baan" not in voltijd
    assert skdb.studie(export, 12345) == []


def test_zoek_studies_op_naam_of_code(export):
    assert [(r["studiecode"], r["graad"]) for r in skdb.zoek_studies(export, "psycho")] == [(56604, "Bachelor"), (60260, "Master")]
    assert [r["studiecode"] for r in skdb.zoek_studies(export, "psycho", graad="master")] == [60260]
    assert [r["studie"] for r in skdb.zoek_studies(export, "56604")] == ["Psychologie"]


def test_doorstroom_op_rang(export):
    assert [r["master"] for r in skdb.doorstroom_bachelor_master(export, 56604)] == ["Psychology", "Psychologie"]
    rijen = skdb.doorstroom_mbo_hbo(export, mbo="verpleeg")
    assert [(r["hbo_studie"], r["doorstroom_pct"]) for r in rijen] == [("Opleiding tot Verpleegkundige", 7.1), ("ICT", 0.1)]
    assert [r["mbo_opleiding"] for r in skdb.doorstroom_mbo_hbo(export, studiecode=30020)] == [
        "Mbo-Verpleegkundige",
        "Software Developer",
    ]


def test_toelating_per_opleiding_met_de_instellingen_die_dezelfde_eisen_noemen(export):
    (ict,) = skdb.toelating(export, croho=30020)
    assert (ict["havo"], ict["mbo"]) == ("Havo met profiel EM, CM, NG, NT.", "Direct toelaatbaar")
    assert (ict["instellingen"], ict["aantal_instellingen"]) == ("Hogeschool Utrecht; Proefhogeschool Particulier", 2)
    (psy,) = skdb.toelating(export, naam="psycho")
    assert (psy["havo"], psy["vwo"], psy["graad"]) == ("Niet toelaatbaar", "Vwo met profiel EM, CM, NG, NT.", "Bachelor")
    assert skdb.toelating(export, brin="25DW", soort_ho="wo") == []
    # Een naam kiest de opleiding (code), en dan tellen alle aanbieders, ook als die haar anders noemen.
    (verpleeg,) = skdb.toelating(export, naam="verpleegkunde")
    assert verpleeg["croho"] == 34560 and verpleeg["aantal_instellingen"] == 1


def test_numerus_fixus_lijst(export):
    rijen = skdb.numerus_fixus(export, brin="21PB")
    assert [(r["studiejaar"], r["capaciteit"]) for r in rijen] == [(2026, 60), (2027, 71)]
    assert rijen[0]["instelling"] == "Universiteit Leiden"


def test_jaren_van_nse_en_1cijferho(export):
    assert skdb.jaren(export) == {"nse": 2026, "1cijferho": 2025}


def test_instellingen(export):
    assert [r["brin"] for r in skdb.instellingen(export)] == ["25DW", "99XX", "21PB"]


def test_de_bron_staat_in_de_catalogus_buiten_all():
    assert onderwijsbronnen.catalog(source="skdb") == skdb.catalog()
    assert all(r.get("_skdb_id") is None for r in onderwijsbronnen.catalog(source="all"))
    assert onderwijsbronnen.normaliseer_bron_id("studiekeuzedatabase") == "skdb:studiekeuzedatabase"
