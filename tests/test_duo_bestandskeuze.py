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
    assert duo_bestandskeuze.standaard("instromende-mbo-studenten") == 0  # geen groep en geen vaste standaard


# Meting #1009 (#1033): zonder resource gaf adressen_ho het bestand van de besturen (index 0), zonder BRIN.
_INSTELLINGENBESTAND = {
    "adressen_ho": "bf1da9c6-c688-4873-91b1-b12c9ac2c132",  # Adressen van instellingen in het hoger onderwijs
    "adressen_mbo": "1a946297-a7ca-48d5-9ae8-19ad73bf8176",  # Adressen instellingen
}


@pytest.mark.parametrize("dataset_id", sorted(_INSTELLINGENBESTAND))
def test_standaard_van_een_adressenbestand_is_het_instellingenbestand(dataset_id):
    assert duo_bestandskeuze.standaard(dataset_id) == 1
    assert duo_bestandskeuze._STANDAARD[dataset_id] == _INSTELLINGENBESTAND[dataset_id]


@pytest.mark.parametrize("dataset_id", sorted(_INSTELLINGENBESTAND))
def test_het_instellingenbestand_staat_in_de_gepinde_catalogus(dataset_id):
    # Een catalogusbump die het ID laat vallen, moet hier opvallen en niet stil weer de besturen geven.
    bestanden = {r.get("id"): r.get("naam", "") for r in duo_meta.record(dataset_id)["_resources"]}
    assert "instellingen" in bestanden[_INSTELLINGENBESTAND[dataset_id]].lower()


@pytest.mark.parametrize("dataset_id", sorted(_INSTELLINGENBESTAND))
def test_een_adressenbestand_heeft_geen_leidend_bestand_en_geen_melding(dataset_id):
    # Geen groep: de adressenbestanden tellen niets, dus geen tekst over onderdrukte cellen.
    for resource in (0, 1):
        assert duo_bestandskeuze.leidend(dataset_id, resource) is None
        assert duo_bestandskeuze.melding(dataset_id, resource) is None
        assert duo_bestandskeuze.noot(dataset_id, resource) is None


def test_een_vaste_standaard_die_de_catalogus_niet_meer_kent_valt_terug_op_nul():
    with patch.object(duo_meta, "record", return_value={"_resources": [{"id": "ander", "naam": "x"}]}):
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


_ADRESSEN = {
    0: pd.DataFrame({"BEVOEGD GEZAG NUMMER": [30588], "BEVOEGD GEZAG NAAM": ["Stichting Hanzehogeschool"]}),
    1: pd.DataFrame({"INSTELLINGSCODE": ["25BE"], "INSTELLINGSNAAM": ["Hanzehogeschool Groningen"]}),
}


@pytest.mark.parametrize("dataset_id", sorted(_INSTELLINGENBESTAND))
def test_get_duo_data_zonder_resource_laadt_de_adressen_van_de_instellingen(dataset_id):
    with patch.object(duo.duo_laden, "laad", side_effect=lambda _d, r: _ADRESSEN[r].copy()) as laad:
        resultaat = json.loads(duo.get_duo_data(dataset_id))
    assert laad.call_args.args == (dataset_id, 1)
    assert resultaat["data_key"] == f"duo:{dataset_id}:1"
    assert "INSTELLINGSCODE" in {k["kolom"] for k in resultaat["kolommen"]}
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


# --- De keuze per instelling en jaar (#1238) -------------------------------------------------------------------------

T = duo_bestandskeuze.Telling


@pytest.mark.parametrize(
    ("tellingen", "gekozen"),
    [
        ([T(2, 1000), T(1, 990), T(3, 1010)], 1),  # eerst de minste onderdrukte cellen, ook bij een lager totaal
        ([T(1, 1000), T(1, 1004), T(2, 1010)], 1),  # gelijk aantal: het hoogste totaal
        ([T(0, 700), T(0, 700), T(0, 700)], 0),  # nog gelijk: het eerste bestand van de groep
        ([T(1, 500), T(0, 700), T(0, 700)], 1),  # gelijk na het eerste: het eerste van de gelijke
        ([None, T(3, 10), None], 1),  # een bestand zonder rijen doet niet mee
        ([None, None], None),  # geen enkel bestand: geen keuze
        ([], None),
    ],
)
def test_kies_minste_onderdrukte_cellen_dan_hoogste_totaal_dan_het_eerste(tellingen, gekozen):
    assert duo_bestandskeuze.kies(tellingen) == gekozen


def test_kandidaten_zijn_de_groep_van_de_sector_in_groepsvolgorde():
    assert duo_bestandskeuze.kandidaten("p01hoinges", "hbo") == [2, 0, 3]
    assert duo_bestandskeuze.kandidaten("p01hoinges", "wo") == [4, 1, 5]
    assert duo_bestandskeuze.kandidaten("p02ho1ejrs", "hbo") == [3, 0, 2]
    assert duo_bestandskeuze.kandidaten("p01hoinges", "mbo") == []
    assert duo_bestandskeuze.kandidaten("mbo-studenten-per-instelling", "mbo") == []  # mbo valt buiten de keuze


def test_de_geslachtbestanden_zijn_hbo_en_wo_inclusief_geslacht():
    assert duo_bestandskeuze.geslachtbestanden("p01hoinges") == [0, 1]
    assert duo_bestandskeuze.geslachtbestanden("p04hogdipl") == [0, 1]


def _ruw(rijen: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rijen, columns=["STUDIEJAAR", "INSTELLINGSCODE_ACTUEEL", "AANTAL_INGESCHREVENEN"])


def test_tellingen_per_instelling_en_jaar_en_landelijk():
    df = _ruw([(2024, "25DW", 100), (2024, "25DW", -1), (2024, "28DN", 50), (2025, "25DW", 7)])
    per = duo_bestandskeuze.tellingen(df, None, "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    assert per == {("25DW", 2024): T(1, 100.0), ("28DN", 2024): T(0, 50.0), ("25DW", 2025): T(0, 7.0)}
    landelijk = duo_bestandskeuze.tellingen(df, None, "STUDIEJAAR", "AANTAL_INGESCHREVENEN", instellingskolom=None)
    assert landelijk == {2024: T(1, 150.0), 2025: T(0, 7.0)}


def test_kies_rijen_neemt_per_instelling_en_jaar_de_rijen_van_een_bestand():
    a = _ruw([(2024, "25DW", 100), (2024, "25DW", -1), (2025, "25DW", 80), (2024, "28DN", 9)])
    b = _ruw([(2024, "25DW", 101), (2025, "25DW", 40), (2025, "25DW", -1)])
    keuze = duo_bestandskeuze.kies_rijen([(3, a, None), (0, b, None)], "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    assert keuze.bestand == {("25DW", 2024): 0, ("25DW", 2025): 3, ("28DN", 2024): 3}
    som = keuze.rijen.groupby(["INSTELLINGSCODE_ACTUEEL", "STUDIEJAAR"])["AANTAL_INGESCHREVENEN"].sum().to_dict()
    assert som == {("25DW", 2024): 101, ("25DW", 2025): 80, ("28DN", 2024): 9}
    assert keuze.cellen.empty  # de gekozen rijen hebben geen -1
    assert keuze.gebruikt() == [0, 3] and keuze.per_jaar() == {2024: [0, 3], 2025: [3]}


def test_kies_rijen_houdt_de_onderdrukte_cellen_van_de_gekozen_rijen():
    a = _ruw([(2024, "25DW", 100), (2024, "25DW", -1)])
    b = _ruw([(2024, "25DW", 90), (2024, "25DW", -1), (2024, "25DW", -1)])
    keuze = duo_bestandskeuze.kies_rijen([(2, b, None), (0, a, None)], "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    assert keuze.bestand == {("25DW", 2024): 0}
    assert keuze.rijen["AANTAL_INGESCHREVENEN"].isna().sum() == 1
    assert int(keuze.cellen["AANTAL_INGESCHREVENEN"].sum()) == 1
    assert set(keuze.cellen.index) <= set(keuze.rijen.index)


def test_kies_rijen_landelijk_kiest_per_jaar_een_bestand_voor_alle_instellingen():
    a = _ruw([(2024, "25DW", 100), (2024, "28DN", -1)])
    b = _ruw([(2024, "25DW", 90), (2024, "28DN", 5)])
    keuze = duo_bestandskeuze.kies_rijen(
        [(2, a, None), (0, b, None)], "STUDIEJAAR", "AANTAL_INGESCHREVENEN", instellingskolom=None
    )
    assert keuze.bestand == {2024: 0}
    assert int(keuze.rijen["AANTAL_INGESCHREVENEN"].sum()) == 95


def test_kies_rijen_zonder_rijen_geeft_een_lege_keuze():
    leeg = _ruw([])
    keuze = duo_bestandskeuze.kies_rijen([(2, leeg, None)], "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    assert keuze.rijen.empty and keuze.bestand == {} and keuze.gebruikt() == []


def test_de_docstring_beschrijft_de_keuze_en_de_tiebreak():
    tekst = duo_bestandskeuze.__doc__ or ""
    assert "onderdrukte cellen" in tekst and "hoogste totaal" in tekst and "eerst staat" in tekst
