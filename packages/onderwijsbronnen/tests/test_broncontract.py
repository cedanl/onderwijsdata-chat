"""Contracttest per bron (#911): elke bron levert dezelfde interface en dezelfde metadatavelden.

Interface: `BRON`, `catalogusrecords()`, `laad` en `metadata(record)` (`_kern/broncontract.py`). Metadata: bron, ID,
titel, peildatum of editie, voorlopig en laatste update. Wat een bron niet kan leveren, is `None` met een reden;
nooit stil leeg.
"""

import importlib

import pytest

import onderwijsbronnen
from onderwijsbronnen._kern import broncontract

BRONNEN = ("cbs", "duo", "rio", "roa", "uwv", "inspectie", "sbb", "unl", "skdb")


def _bron(naam):
    return importlib.import_module(f"onderwijsbronnen.{naam}")


def test_alle_acht_bronnen_doen_mee():
    assert sorted(onderwijsbronnen.BRONNEN) == sorted(BRONNEN)


@pytest.mark.parametrize("naam", BRONNEN)
def test_elke_bron_heeft_de_interface(naam):
    bron = _bron(naam)
    ontbreekt = [deel for deel in broncontract.INTERFACE if not hasattr(bron, deel)]
    assert not ontbreekt, f"{naam} mist {ontbreekt}"
    assert bron.BRON == naam
    assert callable(bron.catalogusrecords) and callable(bron.laad) and callable(bron.metadata)


@pytest.mark.parametrize("naam", BRONNEN)
def test_elke_bron_levert_catalogusrecords_zonder_netwerk(naam):
    records = _bron(naam).catalogusrecords()
    assert records and all(isinstance(r, dict) for r in records)


@pytest.mark.parametrize("naam", BRONNEN)
def test_elk_record_heeft_de_metadatavelden_of_een_reden(naam):
    bron = _bron(naam)
    fouten = {}
    for record in bron.catalogusrecords():
        meta = bron.metadata(record)
        if problemen := broncontract.controleer(meta, naam):
            fouten[meta.get("id")] = problemen
    assert not fouten, fouten


@pytest.mark.parametrize("naam", BRONNEN)
def test_een_id_komt_binnen_een_bron_een_keer_voor(naam):
    bron = _bron(naam)
    ids = [bron.metadata(r)["id"] for r in bron.catalogusrecords()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("naam", ["rio", "duo", "roa", "uwv", "inspectie", "sbb", "unl", "skdb"])
def test_de_catalogusrecords_van_een_bron_zijn_die_van_de_gezamenlijke_catalogus(naam):
    """Geen tweede bron van waarheid: `catalog(source=...)` is precies wat de bron zelf levert."""
    assert onderwijsbronnen.catalog(source=naam) == _bron(naam).catalogusrecords()


def test_de_laders_zijn_de_bestaande_functies():
    """`laad` is een naam voor de lader die de bron al had, geen tweede implementatie."""
    assert onderwijsbronnen.cbs.laad is onderwijsbronnen.cbs.client.data
    assert onderwijsbronnen.rio.laad is onderwijsbronnen.rio.client.fetch
    for naam in ("duo", "roa", "uwv", "inspectie", "sbb", "unl", "skdb"):
        assert _bron(naam).laad is _bron(naam).load


# --- de toets zelf -------------------------------------------------------------------------------------------


def _meta(**over):
    basis = broncontract.metadata(
        "duo", "p01hoinges", "Ingeschrevenen", peildatum_of_editie="1 oktober", voorlopig=False,
        laatste_update="2026-01-01",
    )
    return {**basis, **over}


def test_een_volledig_record_voldoet():
    assert broncontract.controleer(_meta(), "duo") == []


@pytest.mark.parametrize(
    ("meta", "fout"),
    [
        (_meta(laatste_update=None), "laatste_update is None zonder reden"),
        (_meta(peildatum_of_editie=""), "stil leeg"),
        (_meta(voorlopig="nee"), "voorlopig is geen bool"),
        (_meta(bron="cbs"), "bron is 'cbs'"),
        (_meta(id=""), "id is verplicht"),
        (_meta(redenen={"titel": "x"}), "titel heeft een waarde én een reden"),
    ],
)
def test_de_toets_ziet_wat_ontbreekt(meta, fout):
    assert any(fout in f for f in broncontract.controleer(meta, "duo"))


def test_een_reden_telt_alleen_voor_een_leeg_veld():
    meta = broncontract.metadata("rio", "erkenningen", "Erkenningen", voorlopig=True,
                                 redenen={"voorlopig": "x", "laatste_update": "live API"})
    assert meta["redenen"] == {"laatste_update": "live API"}
    assert any("peildatum_of_editie is None zonder reden" in f for f in broncontract.controleer(meta, "rio"))
