"""Waarom een rapportcijfer kan afwijken van eigen cijfers, in het definitieblok, uit code (#736).

"Geeft wel duidelijk weer waar data vandaan komt maar wijkt af van VH en niet duidelijk waarom." Het rapport zegt nu
per dataset wat tussen bron en eigen administratie meestal verschilt. Elke zin over DUO rust op de teldefinitie in
de catalogus; de tests lezen dat na, zodat een nieuwe catalogusversie die iets anders telt hier faalt.
"""

import json

import pandas as pd
import pytest

from agent.niet_meegeteld import NIET_MEEGETELD
from agent.report import _parse_spec_from_response
from agent.report_vergelijken import (
    BEGRIP,
    INSCHRIJVINGEN,
    OPLEIDINGSVORM,
    PEILDATUM,
    PERSONEN,
    vergelijken,
)
from tools import duo_meta, store
from tools.duo import OPLEIDINGSVORM_DATASETS
from tools.store import KeyMeta


@pytest.fixture(autouse=True)
def _leeg():
    store.clear()
    yield
    store.clear()


def _teldefinitie(dataset: str) -> str:
    """De teldefinitie van DUO uit de catalogus; een dataset zonder teldefinitie faalt hier, niet verderop."""
    teldefinitie = duo_meta.teldefinitie(duo_meta.record(dataset))
    assert teldefinitie, dataset
    return teldefinitie


def _duo(dataset: str, key: str | None = None) -> dict:
    """Een geladen DUO-key met de echte teldefinitie uit de catalogus."""
    key = key or f"duo:{dataset}:1"
    store.put(
        key, pd.DataFrame({"AANTAL": [10]}), KeyMeta(bron="duo", dataset=dataset, teldefinitie=_teldefinitie(dataset))
    )
    return {"data_key": key}


def _cbs(dataset: str, afronding: int | None) -> dict:
    key = f"cbs:{dataset}"
    store.put(key, pd.DataFrame({"Totaal": [10]}), KeyMeta(bron="cbs", dataset=dataset, afronding=afronding))
    return {"data_key": key}


def _zinnen(item: dict) -> str:
    return item["definitie"]


# ── Elke zin rust op de catalogus ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("dataset", ["p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"])
def test_de_peildatum_alleen_als_duo_hem_noemt(dataset):
    teldefinitie = _teldefinitie(dataset)
    [item, _slot] = vergelijken([_duo(dataset)])
    assert (PEILDATUM in _zinnen(item)) == ("peildatum 1 oktober" in teldefinitie)


def test_ingeschrevenen_en_eerstejaars_tellen_personen():
    for dataset in ("p01hoinges", "p02ho1ejrs"):
        assert "natuurlijke personen" in _teldefinitie(dataset)
        store.clear()
        [item, _slot] = vergelijken([_duo(dataset)])
        assert PERSONEN in _zinnen(item) and INSCHRIJVINGEN not in _zinnen(item)


def test_inschrijvingen_tellen_ook_neveninschrijvingen():
    assert "neveninschrijvingen meegeteld" in _teldefinitie("p03hoinschr")
    [item, _slot] = vergelijken([_duo("p03hoinschr")])
    assert INSCHRIJVINGEN in _zinnen(item) and PERSONEN not in _zinnen(item)


def test_gediplomeerden_zeggen_niets_over_personen_of_inschrijvingen():
    [item, _slot] = vergelijken([_duo("p04hogdipl")])
    assert PERSONEN not in _zinnen(item) and INSCHRIJVINGEN not in _zinnen(item)


@pytest.mark.parametrize("dataset", sorted(NIET_MEEGETELD))
def test_wat_niet_meetelt_is_de_regel_van_het_chatantwoord(dataset):
    [item, _slot] = vergelijken([_duo(dataset)])
    assert f"Niet meegeteld: {NIET_MEEGETELD[dataset]}." in _zinnen(item)


def test_de_opleidingsvorm_bij_de_datasets_die_hem_per_rij_hebben():
    for dataset in sorted(OPLEIDINGSVORM_DATASETS):
        store.clear()
        [item, _slot] = vergelijken([_duo(dataset)])
        assert OPLEIDINGSVORM in _zinnen(item)


# ── Vorm van het blok ────────────────────────────────────────────────────────────────────────


def test_een_item_per_dataset_in_de_vorm_van_het_definitieblok_en_de_slotzin_een_keer_aan_het_eind():
    items = vergelijken([_duo("p02ho1ejrs"), _duo("p01hoinges")])

    assert [i["begrip"] for i in items] == [f"{BEGRIP} (p02ho1ejrs)", f"{BEGRIP} (p01hoinges)", BEGRIP]
    assert items[-1]["definitie"].startswith("Leg bij een verschil")
    assert not any("Leg bij een verschil" in i["definitie"] for i in items[:-1])


def test_een_feit_is_een_zin_zodat_het_rapport_er_een_bolletje_van_maakt():
    for zin in (PEILDATUM, PERSONEN, INSCHRIJVINGEN, OPLEIDINGSVORM):
        assert zin.count(". ") == 0 and zin.endswith(".")


def test_dezelfde_dataset_via_twee_keys_een_keer():
    items = vergelijken([_duo("p01hoinges", "duo:p01hoinges:1"), _duo("p01hoinges", "duo:p01hoinges:1:hva")])
    assert len(items) == 2


def test_cbs_noemt_de_afronding_en_zonder_afronding_niets():
    [item, _slot] = vergelijken([_cbs("85423NED", 10)])
    assert item["begrip"] == f"{BEGRIP} (85423NED)"
    assert (
        item["definitie"]
        == "CBS rondt de aantallen af op 10-tallen, dus een optelling of een eigen telling wijkt iets af."
    )

    store.clear()
    assert vergelijken([_cbs("85423NED", None)]) == []


def test_zonder_metadata_geen_blok_en_geen_losse_slotzin():
    assert vergelijken([{"data_key": "duo:onbekend"}]) == []
    assert vergelijken([]) == []


def test_een_dataset_zonder_teldefinitie_of_vaste_regels_geeft_niets():
    store.put("duo:x:1", pd.DataFrame({"A": [1]}), KeyMeta(bron="duo", dataset="adressen_ho"))
    assert vergelijken([{"data_key": "duo:x:1"}]) == []


# ── In het rapport ───────────────────────────────────────────────────────────────────────────


def test_het_rapport_zet_het_blok_na_de_teldefinitie():
    datasets = [_duo("p02ho1ejrs")]
    antwoord = json.dumps({"title": "Instroom HvA", "conclusie": "De instroom daalde."})

    spec = _parse_spec_from_response(antwoord, [], {"datasets": datasets, "topic": "Instroom"})

    begrippen = [d["begrip"] for d in spec.definities]
    assert begrippen[0] == "Telling (p02ho1ejrs)"
    assert begrippen[-2:] == [f"{BEGRIP} (p02ho1ejrs)", BEGRIP]
    assert "hbo-masters" in spec.definities[-2]["definitie"]


# ── De koepel bij de sector van het rapport (#1089) ──────────────────────────────────────────

_VH = "Vereniging Hogescholen"
_MBO_RAAD = "MBO Raad"
_UNL = "Universiteiten van Nederland"


def _slot(*datasets: dict) -> str:
    return vergelijken(list(datasets))[-1]["definitie"]


def test_een_mbo_rapport_noemt_de_mbo_raad_en_niet_de_vereniging_hogescholen():
    # 85354NED: mbo-studenten (CBS), het geval van de audit.
    slot = _slot(_cbs("85354NED", 10))

    assert _MBO_RAAD in slot and _VH not in slot and _UNL not in slot


def test_een_hbo_rapport_houdt_de_vereniging_hogescholen():
    # 83286NED is een hbo-tabel; DUO's hoger onderwijs (p02ho1ejrs) gaat over hbo en wo, dat is het volgende geval.
    slot = _slot(_cbs("83286NED", 10))

    assert _VH in slot and _MBO_RAAD not in slot and _UNL not in slot


def test_een_wo_rapport_noemt_unl_en_niet_de_vereniging_hogescholen():
    slot = _slot(_cbs("83285NED", 10))

    assert _UNL in slot and _VH not in slot and _MBO_RAAD not in slot


def test_ho_gaat_over_hbo_en_wo_dus_beide_koepels():
    slot = _slot(_duo("p02ho1ejrs"))

    assert _VH in slot and _UNL in slot and _MBO_RAAD not in slot


def test_een_gemengd_rapport_noemt_alle_betrokken_koepels_een_keer():
    slot = _slot(_cbs("85354NED", 10), _cbs("83286NED", 10), _cbs("83285NED", 10))

    assert slot.count(_MBO_RAAD) == slot.count(_VH) == slot.count(_UNL) == 1


def test_zonder_bekende_sector_noemt_het_slot_geen_koepel_en_blijft_het_een_zin():
    slot = _slot(_cbs("onbekend", 10))

    assert not any(naam in slot for naam in (_VH, _MBO_RAAD, _UNL))
    assert slot.startswith("Leg bij een verschil met eigen cijfers") and slot.count(". ") == 0 and slot.endswith(".")


def test_het_slot_noemt_in_elk_geval_de_peildatum_de_telwijze_en_de_versie():
    for slot in (_slot(_cbs("85354NED", 10)), _slot(_duo("p02ho1ejrs"))):
        assert "peildatum" in slot and "telwijze" in slot and "versie van de data" in slot


def test_het_rapport_van_een_mbo_dataset_noemt_de_vereniging_hogescholen_niet():
    antwoord = json.dumps({"title": "Mbo-studenten", "conclusie": "Het aantal daalde."})

    spec = _parse_spec_from_response(antwoord, [], {"datasets": [_cbs("85354NED", 10)], "topic": "Mbo-studenten"})

    assert _VH not in " ".join(d["definitie"] for d in spec.definities)
