"""Hoeveel datasets per bron: een telling uit code, niet uit zoekresultaten (#168).

Live-audit 4: gpt-oss weigerde terecht een DUO-totaal uit zoekresultaten af te leiden,
maar had geen tool die het door de app zelf getoonde getal (56) gaf. Een zoekopdracht
zonder treffers leidde tot "geen geschikte DUO-bron", terwijl het bestand er was.
"""

import json
from unittest.mock import patch

import pytest

from tests.zoekuitkomst import envelop
from tools import catalog, dispatch
from tools.catalog import _rio_duo, _rio_duo_alles, dataset_counts, dataset_details, search_catalog

_CBS = [{"_cbs_id": "a", "bron": "x"}, {"_cbs_id": "b", "bron": "y", "_archief": True}]
_RIO_DUO = [
    {"leverancier": "DUO", "_ckan_id": "p01hoinges", "bron": "Ingeschrevenen hoger onderwijs", "onderwijstype": ["HO"]},
    {"leverancier": "DUO", "_ckan_id": "p03hoinges", "bron": "Ingeschrevenen hbo", "onderwijstype": ["HO"]},
    {
        "leverancier": "RIO",
        "_rio_resource": "onderwijslocaties",
        "bron": "Onderwijslocaties",
        "onderwijstype": ["Allen"],
    },
    {"leverancier": "SBB", "_ckan_id": "sbb", "bron": "Stages", "onderwijstype": ["MBO"]},
]


def _catalogus():
    return patch("tools.catalog._cbs", return_value=_CBS), patch("tools.catalog._rio_duo", return_value=_RIO_DUO)


def test_dataset_counts_is_een_tool_met_de_telling_per_bron():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        result, _ = dispatch("dataset_counts", {})
    telling = json.loads(result)

    assert telling["datasets_per_bron"] == {"CBS": 2, "DUO": 2, "RIO": 1}
    assert telling["cbs_gearchiveerd"] == 1


def test_een_zoekopdracht_zonder_treffers_zegt_niet_dat_de_bron_ontbreekt():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        result = search_catalog("eindexamencijfers")

    uitkomst = envelop(result)
    assert uitkomst["status"] == "no_match"
    assert "zegt niet dat" in uitkomst["melding"] or "ontbreekt" in uitkomst["melding"]
    assert "dataset_details" in uitkomst["vervolgstap"]
    assert "bestaat niet" not in result


def test_een_zoekopdracht_over_vo_is_out_of_scope_en_zegt_niet_dat_de_bron_ontbreekt():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        result = search_catalog("eindexamencijfers vmbo")

    uitkomst = envelop(result)
    assert uitkomst["status"] == "out_of_scope"
    assert "zeg niet dat de bron niet bestaat" in uitkomst["melding"]
    assert "alleen mbo, hbo en wo" in uitkomst["vervolgstap"]


# ── Scopebesluit uit riodata (#375) ───────────────────────────────────────────

_BUITEN_SCOPE = {
    "leverancier": "DUO",
    "_ckan_id": "vo-examens",
    "bron": "Examenkandidaten vo",
    "onderwijstype": ["MBO"],
    "_scope": {"mbo_hbo_wo": "buiten_scope", "reden": "Beschrijft VO."},
}


def test_een_dataset_buiten_scope_is_voor_de_chat_onzichtbaar():
    """riodata legt per record vast wat buiten mbo/hbo/wo valt; de chat volgt dat besluit,
    ook bij een ondersteunde leverancier."""
    with (
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo_alles", return_value=[*_RIO_DUO, _BUITEN_SCOPE]),
    ):
        _rio_duo_alles.cache_clear()
        _rio_duo.cache_clear()
        try:
            assert dataset_counts()["DUO"] == 2
            # Het besluit van riodata geldt ook als onderwijstype mbo zegt (#355).
            assert json.loads(dataset_details("vo-examens"))["buiten_scope"] is True
            assert "vo-examens" not in search_catalog("examenkandidaten")
        finally:
            _rio_duo_alles.cache_clear()
            _rio_duo.cache_clear()


@pytest.mark.parametrize(
    "vraag",
    [
        "Welk profiel heb ik met havo nodig voor Verpleegkunde?",
        "Kan ik met een vwo-diploma naar de bachelor Psychologie?",
        "Kan ik met een havo-diploma naar de opleiding Geneeskunde?",
        "Welke vakken moet ik met vwo hebben voor de bachelor Psychologie?",
        "Wat zijn de toelatingseisen met havo voor Biomedische Wetenschappen?",
    ],
)
def test_een_toelatingsvraag_over_een_ho_opleiding_is_niet_buiten_het_profiel(vraag):
    """Dezelfde regel als de vaste scope-uitleg (ho_markers.vervolgcontext, #957): havo/vwo is hier de vooropleiding."""
    assert catalog._buiten_profiel(vraag) is False
    assert catalog._buiten_profiel("Hoeveel leerlingen zitten er op het vwo?") is True


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel leerlingen worden toegelaten tot het vwo?",
        "Hoeveel basisschoolleerlingen krijgen een vwo-advies na de toelatingstoets?",
        "Hoeveel leraren in het vo hebben een master?",
        "Hoeveel vwo-leerlingen volgen een masterclass?",
    ],
)
def test_een_los_toelatingswoord_of_een_losse_graad_houdt_een_vo_vraag_buiten_het_profiel(vraag):
    """Alleen een ho-opleiding of havo/vwo als vooropleiding maakt een toelatingsvraag ho-context (#968)."""
    assert catalog._buiten_profiel(vraag) is True
