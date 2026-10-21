"""De vaste envelope van search_catalog (#358, stap 2): elke uitkomst heeft dezelfde vorm, ook een fout."""

import json
from unittest.mock import patch

import pytest

from tests.zoekuitkomst import STATUSSEN, envelop
from tools import catalog, ho_markers, scopeprofiel
from tools.catalog import search_catalog

_SLEUTELS = {"status", "catalogus", "gezocht", "melding", "meldingen", "kandidaten", "vervolgstap"}


def _zoek(query: str, cbs=(), rio=(), **kwargs) -> str:
    with patch("tools.catalog._cbs", return_value=list(cbs)), patch("tools.catalog._rio_duo", return_value=list(rio)):
        return search_catalog(query, **kwargs)


def _controleer_vorm(tekst: str) -> dict:
    """Geldige compacte JSON, alleen bekende sleutels, `status` en `catalogus` altijd aanwezig."""
    uitkomst = envelop(tekst)
    assert set(uitkomst) <= _SLEUTELS, set(uitkomst) - _SLEUTELS
    assert tekst == json.dumps(uitkomst, ensure_ascii=False, separators=(",", ":"))  # compact, vaste volgorde
    return uitkomst


_STUDENTEN = [{"_cbs_id": "85423NED", "bron": "Ingeschrevenen hbo en wo", "title": "studenten hbo wo"}]
_ZWAK = [{"_cbs_id": f"{i}NED", "title": "ingeschrevenen", "bron": f"Ingeschrevenen {i}"} for i in range(10000, 10005)]


def test_candidates_heeft_kandidaten_catalogus_en_vervolgstap():
    uitkomst = _controleer_vorm(_zoek("studenten hbo", cbs=_STUDENTEN, source="cbs"))

    assert uitkomst["status"] == "candidates"
    assert uitkomst["catalogus"] == catalog.catalogus_digest()
    assert [k["dataset_id"] for k in uitkomst["kandidaten"]] == ["85423NED"]
    assert "dataset_details" in uitkomst["vervolgstap"]


def test_een_kandidaat_draagt_dataset_id_en_de_geraakte_zoektermen():
    (kandidaat,) = envelop(_zoek("studenten hbo", cbs=_STUDENTEN, source="cbs"))["kandidaten"]

    assert kandidaat["dataset_id"] == "85423NED" and kandidaat["_cbs_id"] == "85423NED"
    assert kandidaat["geraakt"] == ["hbo", "studenten"]


def test_no_match_laat_de_gezochte_termen_zien_en_zegt_sector_periode_en_populatie_te_houden():
    uitkomst = _controleer_vorm(_zoek("leraren tekort mbo", cbs=_STUDENTEN, source="cbs"))

    assert uitkomst["status"] == "no_match" and uitkomst["kandidaten"] == []
    assert {"leraren", "tekort", "mbo"} <= set(uitkomst["gezocht"])
    assert "Dat zegt niet dat de data ontbreekt" in uitkomst["melding"]
    # Een tweede poging mag de vraag niet breder maken dan hij is.
    assert "de sector (mbo, hbo, wo), de periode en de populatie" in uitkomst["vervolgstap"]
    assert "hooguit één keer" in uitkomst["vervolgstap"]


def test_needs_clarification_biedt_hooguit_drie_suggesties_met_id_en_titel():
    uitkomst = _controleer_vorm(_zoek("studenten", cbs=_ZWAK, source="cbs"))

    assert uitkomst["status"] == "needs_clarification"
    assert len(uitkomst["kandidaten"]) == 3
    assert all(set(k) == {"dataset_id", "bron"} for k in uitkomst["kandidaten"])
    assert "Laad geen van deze" in uitkomst["melding"]


def test_out_of_scope_bij_een_vraag_over_basisonderwijs_zonder_mbo_hbo_of_wo():
    uitkomst = _controleer_vorm(_zoek("basisschool leerlingen groep 8", cbs=_STUDENTEN, source="cbs"))

    assert uitkomst["status"] == "out_of_scope" and uitkomst["kandidaten"] == []
    assert uitkomst["melding"] == scopeprofiel.MELDING
    assert "alleen mbo, hbo en wo" in uitkomst["vervolgstap"]


def test_een_vo_woord_naast_mbo_of_hbo_is_geen_out_of_scope():
    for query in ("vmbo naar mbo doorstroom", "havo naar hbo instroom"):
        assert envelop(_zoek(query, cbs=_STUDENTEN, source="cbs"))["status"] != "out_of_scope", query


def test_metadata_unknown_als_de_geodekking_van_alles_onbekend_is():
    onbekend = [{"_cbs_id": "99999NED", "title": "instroom data"}]
    uitkomst = _controleer_vorm(_zoek("instroom", cbs=onbekend, source="cbs", geo_niveau="gemeente"))

    assert uitkomst["status"] == "metadata_unknown" and uitkomst["kandidaten"] == []
    assert "99999NED" in uitkomst["melding"] and "dataset_details" in uitkomst["vervolgstap"]


def test_no_match_als_geen_dataset_het_gevraagde_geo_niveau_heeft():
    landelijk = [{"_cbs_id": "a", "title": "instroom data", "_geo_niveau": ["landelijk"]}]
    uitkomst = _controleer_vorm(_zoek("instroom", cbs=landelijk, source="cbs", geo_niveau="gemeente"))

    assert uitkomst["status"] == "no_match" and uitkomst["kandidaten"] == []
    assert "gemeente" in uitkomst["melding"] and "hoger aggregatieniveau" in uitkomst["vervolgstap"]
    assert "instroom" in uitkomst["gezocht"]


def test_een_onbekende_dekking_naast_een_bewezen_treffer_wordt_een_melding():
    cbs = [
        {"_cbs_id": "bewezen", "title": "instroom data", "_geo_niveau": [], "_dimensies": ["Perioden"]},
        {"_cbs_id": "onbekend", "title": "instroom data instroom"},
    ]
    uitkomst = _controleer_vorm(_zoek("instroom", cbs=cbs, source="cbs", geo_niveau="landelijk"))

    assert uitkomst["status"] == "candidates"
    assert [k["dataset_id"] for k in uitkomst["kandidaten"]] == ["bewezen"]
    assert any("onbekend" in m and "dataset_details" in m for m in uitkomst["meldingen"])


def test_een_fout_in_de_zoekfunctie_is_een_tool_error_geen_exceptie():
    with patch("tools.catalog._zoek", side_effect=RuntimeError("kapot")):
        uitkomst = _controleer_vorm(search_catalog("studenten hbo"))

    assert uitkomst["status"] == "tool_error"
    assert "kapot" not in json.dumps(uitkomst)  # de foutdetails horen niet bij het model
    assert uitkomst["vervolgstap"]


@pytest.mark.parametrize("fout", [OSError("weg"), ImportError("weg"), json.JSONDecodeError("kapot", "{", 0)])
def test_een_onleesbare_catalogus_is_source_unavailable(fout):
    with patch("tools.catalog._zoek", side_effect=fout):
        uitkomst = _controleer_vorm(search_catalog("studenten hbo"))

    assert uitkomst["status"] == "source_unavailable"
    assert "niet bereikbaar" in uitkomst["vervolgstap"]


def test_alle_statussen_zijn_bekend_en_elke_uitkomst_is_een_envelope():
    uitkomsten = [
        _zoek("studenten hbo", cbs=_STUDENTEN, source="cbs"),
        _zoek("leraren tekort mbo", cbs=_STUDENTEN, source="cbs"),
        _zoek("studenten", cbs=_ZWAK, source="cbs"),
        _zoek("basisschool groep 8", source="cbs"),
        _zoek("instroom", cbs=[{"_cbs_id": "9NED", "title": "instroom"}], source="cbs", geo_niveau="gemeente"),
    ]
    statussen = {_controleer_vorm(u)["status"] for u in uitkomsten}

    assert statussen == {"candidates", "no_match", "needs_clarification", "out_of_scope", "metadata_unknown"}
    assert statussen <= STATUSSEN


def test_het_toolbudget_blijft_gehaald_met_hele_kandidaten_en_een_melding(monkeypatch):
    entries = [
        {"_cbs_id": f"{10000 + i}NED", "bron": f"Ingeschrevenen {i}", "samenvatting": "x" * 150} for i in range(15)
    ]
    monkeypatch.setattr(catalog, "TOOL_RESULT_MAX_CHARS", 1500)
    tekst = _zoek("ingeschrevenen", cbs=entries, source="cbs", top_n=15)

    uitkomst = _controleer_vorm(tekst)  # geldige JSON, geen afgekapte tekst
    assert len(tekst) <= 1500
    assert uitkomst["status"] == "candidates" and 1 <= len(uitkomst["kandidaten"]) < 15
    assert uitkomst["kandidaten"][0]["dataset_id"] == "10000NED"
    assert any("weggelaten" in m and "1500 tekens" in m for m in uitkomst["meldingen"])


_VO_CONTEXT = [{"_cbs_id": "85566NED", "bron": "Doorstroom vo naar hbo", "title": "doorstroom vo hbo"}]


def test_vo_context_blijft_verborgen_zonder_ho_vraag_en_draagt_dan_het_etiket():
    with ho_markers.beurtvraag("Hoeveel leerlingen zitten er op het vwo?"):
        zonder = envelop(_zoek("doorstroom vo", cbs=_VO_CONTEXT, source="cbs"))
    assert "85566NED" not in json.dumps(zonder.get("kandidaten", []))

    with ho_markers.beurtvraag("Hoeveel vwo-leerlingen stromen door naar het hbo?"):
        met = envelop(_zoek("doorstroom vo", cbs=_VO_CONTEXT, source="cbs"))
    (kandidaat,) = met["kandidaten"]
    assert kandidaat["dataset_id"] == "85566NED" and kandidaat["context"] == scopeprofiel.HO_CONTEXT_ETIKET


# ── Herstelopties bij een onbekend dataset-ID (#358) ──────────────────────────


@pytest.mark.parametrize(("fout", "bedoeld"), [("85423NEDX", "85423NED"), ("p01hoingess", "p01hoinges")])
def test_een_tikfout_in_een_dataset_id_noemt_de_bedoelde_dataset(fout, bedoeld):
    """dataset_details en de datatools bieden het dichtstbijzijnde ID aan; het model hoeft niet te raden."""
    assert bedoeld in catalog.dataset_details(fout).split("Bedoelde je")[1]
    assert bedoeld in (catalog.scope_blokkade(fout) or "")


def test_een_onbekend_id_zonder_overeenkomst_verwijst_naar_search_catalog():
    assert "search_catalog" in catalog.dataset_details("zzzqqq")
    assert "search_catalog" in (catalog.scope_blokkade("zzzqqq") or "")
