"""Eén leidend DUO-bestand voor een totaal per instelling, in code (#325).

Hanze telde 26.362 uit het geslacht-bestand en 26.379 uit het opleidingsvorm-bestand van
p01hoinges: zelfde telling, andere uitsplitsing, andere onderdrukte cellen. Het model koos
per gesprek een ander bestand, en de standaard (index 0) was het geslacht-bestand.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from tools import catalog, duo, duo_bestandskeuze, duo_meta, store

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")


@pytest.mark.parametrize("dataset_id", sorted(duo_bestandskeuze._GROEPEN))
def test_elk_bestand_in_een_groep_staat_in_de_gepinde_catalogus(dataset_id):
    # Een catalogusbump die een ID laat vallen, moet hier opvallen en niet stil 'geen keuze' geven.
    ids = {r.get("id") for r in duo_meta.record(dataset_id)["_resources"]}
    for groep in duo_bestandskeuze._GROEPEN[dataset_id]:
        assert set(groep) <= ids


@pytest.mark.parametrize("dataset_id", ["p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"])
def test_een_ho_groep_is_een_sector(dataset_id):
    # De telling is per dataset; een groep mengt nooit hbo en wo.
    namen = {r.get("id"): r["naam"] for r in duo_meta.record(dataset_id)["_resources"]}
    for groep in duo_bestandskeuze._GROEPEN[dataset_id]:
        sectoren = {s for i in groep for s in ("hoger beroepsonderwijs", "wetenschappelijk onderwijs") if s in namen[i]}
        assert len(sectoren) == 1 and len(groep) == 3


@pytest.mark.parametrize(
    ("dataset_id", "resource", "leidend"),
    [
        ("p01hoinges", 0, 2),  # hbo geslacht -> hbo niveau opleiding
        ("p01hoinges", 3, 2),
        ("p01hoinges", 2, 2),
        ("p01hoinges", 1, 4),  # wo geslacht -> wo opleidingsvorm
        ("p02ho1ejrs", 0, 3),
        ("p04hogdipl", 2, 3),
        ("mbo-studenten-per-instelling", 4, 0),
    ],
)
def test_leidend_bestand_in_de_groep(dataset_id, resource, leidend):
    assert duo_bestandskeuze.leidend(dataset_id, resource) == leidend


def test_zonder_groep_geen_leidend_bestand():
    assert duo_bestandskeuze.leidend("adressen_ho", 0) is None
    assert duo_bestandskeuze.leidend("p01hoinges", 99) is None
    assert duo_bestandskeuze.leidend("p01hoinges", "geslacht") is None


def test_standaard_is_het_leidende_bestand_van_de_eerste_groep():
    assert duo_bestandskeuze.standaard("p01hoinges") == 2
    assert duo_bestandskeuze.standaard("mbo-studenten-per-instelling") == 0
    assert duo_bestandskeuze.standaard("adressen_ho") == 0


def test_een_id_dat_de_catalogus_niet_meer_kent_geeft_geen_keuze():
    with patch.object(duo_meta, "record", return_value={"_resources": [{"id": "ander", "naam": "x"}]}):
        assert duo_bestandskeuze.leidend("p01hoinges", 0) is None
        assert duo_bestandskeuze.standaard("p01hoinges") == 0


def test_melding_bij_een_niet_leidend_bestand_wijst_het_leidende_aan():
    melding = duo_bestandskeuze.melding("p01hoinges", 0)
    assert melding is not None
    assert "get_duo_data('p01hoinges', 2)" in melding
    assert "niveau opleiding" in melding


def test_geen_melding_bij_het_leidende_bestand_of_zonder_groep():
    assert duo_bestandskeuze.melding("p01hoinges", 2) is None
    assert duo_bestandskeuze.melding("adressen_ho", 0) is None


def test_prognosebestand_wijst_de_gerealiseerde_aantallen_aan():
    melding = duo_bestandskeuze.melding("studentprognoses-mbo-per-instelling", 3)
    assert melding is not None
    assert "Historie" in melding and "get_duo_data('mbo-studenten-per-instelling', 0)" in melding


def test_meervoudig_naamdeel_noemt_het_leidende_bestand_eerst():
    bestanden = duo_meta.record("p01hoinges")["_resources"]
    with patch.object(duo._duo, "resources", return_value=bestanden), pytest.raises(duo.MeerdereResources) as fout:
        duo._resource_index("p01hoinges", "wetenschappelijk onderwijs")
    tekst = str(fout.value)
    assert "4 = '" in tekst and "(leidend voor totalen)" in tekst
    assert "get_duo_data('p01hoinges', 4)" in tekst


def test_dataset_details_markeert_de_leidende_bestanden():
    details = json.loads(catalog.dataset_details("p01hoinges"))
    leidend = [r["index"] for r in details["_resources"] if r.get("leidend_voor_totalen")]
    assert leidend == [2, 4]


def _laad(dataset_id, *resource):
    df = pd.DataFrame({"STUDIEJAAR": [2025], "AANTAL_INGESCHREVENEN": [10]})
    with patch.object(duo._duo, "load", return_value=df) as load:
        resultaat = json.loads(duo.get_duo_data(dataset_id, *resource))
    return resultaat, load


def test_get_duo_data_zonder_resource_laadt_het_leidende_bestand():
    resultaat, load = _laad("p01hoinges")
    assert load.call_args.args == ("p01hoinges", 2)
    assert resultaat["data_key"] == "duo:p01hoinges:2"
    assert "bestandskeuze" not in resultaat


def test_get_duo_data_met_een_niet_leidend_bestand_zegt_welk_bestand_leidend_is():
    resultaat, _ = _laad("p01hoinges", 0)
    assert "get_duo_data('p01hoinges', 2)" in resultaat["bestandskeuze"]


def _selectie(dataset_id: str, resource: int, df: pd.DataFrame, onderdrukt: bool) -> list[str]:
    """Een beurt met een afgeleide key zoals query_data hem maakt."""
    bron = f"duo:{dataset_id}:{resource}"
    store.put(bron, df, store.KeyMeta(bron="duo", dataset=dataset_id, resource=resource))
    store.derive(bron, f"{bron}:abc", df)
    duo.record_sentinel_cells(f"{bron}:abc", pd.DataFrame({"AANTAL": [int(onderdrukt)] * len(df)}))
    return [json.dumps({"data_key": f"{bron}:abc"})]


def test_telling_noemt_bij_een_ondergrens_het_bestand_en_het_leidende():
    blok = telling_blok(_selectie("p01hoinges", 0, pd.DataFrame({"AANTAL": [26362]}), onderdrukt=True))
    assert "Ondergrens" in blok
    assert "totalen uit bestand 'Ingeschrevenen hoger beroepsonderwijs inclusief geslacht" in blok
    assert "leidend voor totalen per instelling is 'Ingeschrevenen hoger beroepsonderwijs niveau opleiding" in blok
    assert "hun totalen wijken daardoor af" in blok


def test_telling_bij_het_leidende_bestand_zegt_dat_het_leidend_is():
    blok = telling_blok(_selectie("p01hoinges", 2, pd.DataFrame({"AANTAL": [26373]}), onderdrukt=True))
    assert "het leidende bestand voor totalen per instelling" in blok


def test_telling_zonder_onderdrukte_cel_noemt_geen_afwijking():
    # Zonder -1 in de selectie geven alle bestanden hetzelfde totaal.
    blok = telling_blok(_selectie("p01hoinges", 0, pd.DataFrame({"AANTAL": [771]}), onderdrukt=False))
    assert "wijken daardoor af" not in blok


def test_telling_noemt_historiejaren_uit_een_prognosebestand():
    df = pd.DataFrame({"Jaar": [2025, 2030], "Aantal": [14517, 13900], "Type": ["Historie", "Prognose"]})
    blok = telling_blok(_selectie("studentprognoses-mbo-per-instelling", 3, df, onderdrukt=False))
    assert "Historie" in blok and "mbo-studenten-per-instelling" in blok


def test_telling_zonder_historiejaren_geen_prognosenoot():
    df = pd.DataFrame({"Jaar": [2030], "Aantal": [13900], "Type": ["Prognose"]})
    assert "Historie" not in telling_blok(_selectie("studentprognoses-mbo-per-instelling", 3, df, onderdrukt=False))


def test_prognosemelding_zonder_bekend_realisatiebestand_noemt_de_dataset():
    with patch.object(duo_bestandskeuze, "_indexen", return_value=[None]):
        melding = duo_bestandskeuze.melding("studentprognoses-mbo-per-instelling", 3)
    assert melding is not None
    assert "None" not in melding and "mbo-studenten-per-instelling" in melding
