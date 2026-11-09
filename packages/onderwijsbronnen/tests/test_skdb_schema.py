"""Het schema van de Studiekeuzedatabase uit de export zelf (#978).

De export heeft twee beschrijvende tabellen, `exporttabellen` en `exportkolommen`; daaruit komt de schemacatalogus.
De omschrijvingen daarin zijn het gegevenswoordenboek van LCSK en staan niet in de repo: de proefexport heeft verzonnen
omschrijvingen met dezelfde vorm. Wat de chat met een tabel kan (`MOGELIJKHEDEN`) is van ons en staat wel in de code.
"""

from __future__ import annotations

import json
from collections import defaultdict
from importlib.resources import files

import pytest

from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand, schemakaart
from onderwijsbronnen.skdb.export import Export


@pytest.fixture
def export():
    return skdb.lees(*proefbestand.standaard())


def _tabel(uit: dict, naam: str) -> dict:
    return next(t for t in uit["tabellen"] if t["tabel"] == naam)


def test_per_tabel_omschrijving_kolommen_en_types_uit_de_export(export):
    tracks = _tabel(skdb.schema(export), "tracks")
    assert tracks["omschrijving"] == "Proef: een track"
    assert tracks["kolommen"] == [
        {"kolom": "instellingSkdb", "type": "number", "omschrijving": "Proef: instellingSkdb"},
        {"kolom": "vestigingSkdb", "type": "number", "omschrijving": "Proef: vestigingSkdb"},
        {"kolom": "hoviProductId", "type": "string", "omschrijving": "Proef: hoviProductId"},
        {"kolom": "trackNaam", "type": "string", "omschrijving": "Proef: trackNaam"},
    ]


def test_de_korrel_is_de_reeks_parameters_van_het_endpoint(export):
    uit = skdb.schema(export)
    assert _tabel(uit, "tracks")["korrel"] == ["instellingSkdb", "vestigingSkdb", "hoviProductId"]
    assert _tabel(uit, "instellingen")["korrel"] == ["instellingSkdb"]


def test_relaties_zijn_de_tabellen_waarvan_de_korrel_in_deze_tabel_staat(export):
    uit = skdb.schema(export)
    assert _tabel(uit, "tracks")["relaties"] == [
        {"tabel": "vestigingen", "via": ["instellingSkdb", "vestigingSkdb"]},
        {"tabel": "instellingen", "via": ["instellingSkdb"]},
    ]
    # Een tabel is geen relatie van zichzelf, en een kindtabel (fijnere korrel) is geen relatie van de ouder.
    assert [r["tabel"] for r in _tabel(uit, "instellingen")["relaties"]] == []


def test_jaarkolommen_en_de_editie_van_de_export(export):
    uit = skdb.schema(export)
    assert _tabel(uit, "opleidingvormen")["jaarkolommen"] == ["enqueteJaar"]
    assert _tabel(uit, "lotingopleidingendecentraleselecties")["jaarkolommen"] == ["studieJaar"]
    assert uit["editie"] == {"versie": "26.6", "exportdatum": "2026-11-06", "nse": 2026, "1cijferho": 2025}
    assert "geen 0" in uit["null"]


def test_een_kolom_waarvoor_een_andere_bron_leidend_is_draagt_die_bron_en_geen_omschrijving(export):
    """Afspraken #878: de velden die de chat niet toont, komen niet als gewone kolom in de catalogus."""
    kolommen = {k["kolom"]: k for k in _tabel(skdb.schema(export), "vestigingen")["kolommen"]}
    assert "omschrijving" not in kolommen["studentenAantal"]
    assert "DUO" in kolommen["studentenAantal"]["andere_bron"]
    assert kolommen["gemeenteCode"]["omschrijving"] == "Proef: gemeenteCode"


def test_de_mogelijkheid_per_tabel(export):
    uit = skdb.schema(export)
    assert _tabel(uit, "opleidingvormen")["mogelijkheid"] == {"soort": "overzicht", "overzichten": ["opleidingen", "studie"]}
    assert _tabel(uit, "tracks")["mogelijkheid"] == {"soort": "pakket"}
    collegegelden = _tabel(uit, "collegegelden")["mogelijkheid"]
    assert collegegelden["soort"] == "andere_bron" and "wettekst" in collegegelden["andere_bron"]


def test_een_tabel_die_de_code_niet_kent_is_alleen_in_het_pakket_leesbaar():
    tabellen = {
        **proefbestand.TABELLEN,
        "exporttabellen": [*proefbestand.EXPORTTABELLEN, {"Tabel": "nieuw", "Endpoint": "/nieuw/{nieuwId}", "Omschrijving": "x"}],
    }
    inhoud = proefbestand.zip_bytes(tabellen)
    nieuw = _tabel(skdb.schema(skdb.lees(inhoud, skdb.herkomst(inhoud, proefbestand.BESTAND))), "nieuw")
    assert nieuw["mogelijkheid"] == {"soort": "pakket"}
    assert nieuw["in_export"] is False  # beschreven, maar zonder databestand


def test_een_databestand_zonder_beschrijving_staat_er_ook_in(export):
    doorstroom = _tabel(skdb.schema(export), "doorstroommbohbo")
    assert doorstroom["in_export"] is True
    assert doorstroom["omschrijving"] is None and doorstroom["kolommen"] == []


def test_zonder_beschrijving_in_de_export_geen_schema():
    inhoud = proefbestand.zip_bytes(weglaten=("exporttabellen", "exportkolommen"))
    with pytest.raises(skdb.SkdbFout, match="exporttabellen"):
        skdb.schema(skdb.lees(inhoud, skdb.herkomst(inhoud, proefbestand.BESTAND)))


def test_de_ingekorte_bestandsnaam_heet_in_het_schema_voluit(export):
    namen = [t["tabel"] for t in skdb.schema(export)["tabellen"]]
    assert "lotingopleidingendecentraleselecties" in namen
    assert "lotingopleidingendecentralesele" not in namen
    assert namen == sorted(namen)


class _Spion(Export):
    """Een export die bijhoudt welke tabellen een overzicht leest."""

    gelezen: set[str]

    def rijen(self, tabel: str) -> list[dict]:
        self.gelezen.add(tabel)
        return super().rijen(tabel)


_AANROEPEN = {
    "opleidingen": {"brin": "25DW"},
    "studie": {"studiecode": 30020},
    "toelating": {"croho": 30020},
    "numerus_fixus": {},
    "doorstroom_mbo_hbo": {"mbo": "b0589"},
    "doorstroom_bachelor_master": {"studiecode": 56604},
}


def test_de_overzichten_per_tabel_zijn_de_tabellen_die_elk_overzicht_echt_leest():
    """`MOGELIJKHEDEN` mag niet uit de pas lopen met de zes overzichten: een overzicht dat een tabel gaat lezen, of
    niet meer, laat deze toets falen."""
    gemeten: dict[str, set[str]] = defaultdict(set)
    for functie, kwargs in _AANROEPEN.items():
        spion = _Spion(*proefbestand.standaard())
        spion.gelezen = set()
        getattr(skdb, functie)(spion, **kwargs)
        for tabel in spion.gelezen:
            gemeten[tabel].add(functie)
    vastgelegd = {t: set(m.overzichten) for t, m in schemakaart.MOGELIJKHEDEN.items() if m.overzichten}
    assert vastgelegd == dict(gemeten)
    assert set(schemakaart.OVERZICHTEN) == set(_AANROEPEN)


def test_elke_tabel_van_de_export_staat_in_de_mogelijkheden():
    """De tabelnamen (geen omschrijvingen) van de 45 tabellen van export 26.6; de proefexport heeft er een deel van."""
    assert len(schemakaart.MOGELIJKHEDEN) == 45
    assert {t["Tabel"] for t in proefbestand.EXPORTTABELLEN} <= set(schemakaart.MOGELIJKHEDEN)
    assert skdb.VEREIST <= set(schemakaart.MOGELIJKHEDEN)


def test_het_catalogusrecord_noemt_de_tabellen_maar_niet_hun_omschrijving():
    [record] = skdb.catalog()
    assert record["tabellen"] == sorted(schemakaart.MOGELIJKHEDEN)
    assert "skdb" in record["tags"]
    # In de pakketdata staat geen schema: dat komt alleen uit een opgehaalde export.
    ruw = files("onderwijsbronnen.skdb.data").joinpath("skdb_resources.json").read_text(encoding="utf-8")
    assert "Omschrijving" not in ruw and "tabellen" not in json.loads(ruw)[0]
