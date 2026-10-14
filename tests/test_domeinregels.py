"""Het domeinregelbestand data/domeinregels.toml (#363).

Drie lagen. Het schema: een ongeldig bestand laadt niet, met een melding die de regel noemt, en
dan start ook de app niet (fail-closed). Het contract: elke regel in het echte bestand verwijst naar
iets dat in de gepinde riodata-catalogus staat; hernoemt DUO een kolom, dan faalt de regel hier. Het
effect: elke regel is zichtbaar in wat de tools teruggeven. De parametrisatie leest het echte bestand,
dus een nieuwe regel draait vanzelf mee, en een regelsoort zonder contract of effect faalt.
"""

import importlib
import json
import re
import sys
from datetime import date

import pandas as pd
import pytest

from core import domeinregels
from core.domeinregels import (
    DomeinregelFout,
    HerkomstIsVestiging,
    Kolomcorrectie,
    Opleidingsvormregel,
    Regel,
    Sentinelregel,
)
from core.sentinels import mask_sentinels
from tools import duo_meta, kolomlabel
from tools.catalog import _rio_duo, dataset_details, search_catalog
from tools.duo import column_definitions, count_cells, sentinel_notes

# Een klein, geldig bestand; elke validatietest wijzigt er één ding aan.
_GELDIG = """
[sentinel]
id = "s"
bron = "bron van s"
gecontroleerd = 2026-10-14
waarden = [-1]
betekenis = "onderdrukte cel"
uitgezonderd_als_kolom_bevat = ["MUTATIE"]

[opleidingsvorm]
id = "o"
bron = "bron van o"
gecontroleerd = 2026-10-14
datasets = ["p01hoinges"]
codes = { VT = "voltijd", DT = "deeltijd" }

[[kolomcorrectie]]
id = "k"
bron = "bron van k"
gecontroleerd = 2026-10-08
datasets = ["p04hogdipl"]
kolom = "DIPLOMAJAAR"
definitie = "Jaar van het diploma."

[[herkomst_is_vestiging]]
id = "h"
bron = "bron van h"
gecontroleerd = 2026-10-08
datasets = ["p01hoinges"]
melding = "Niet geschikt voor herkomst."

[herkomst_is_vestiging.voorbeeldvragen]
"Waar wonen ze?" = "Waar liggen de vestigingen?"
"""


def _laad(tmp_path, tekst: str) -> domeinregels.Domeinregels:
    pad = tmp_path / "domeinregels.toml"
    pad.write_text(tekst, encoding="utf-8")
    return domeinregels.laad(pad)


def _gewijzigd(oud: str, nieuw: str) -> str:
    assert oud in _GELDIG, f"{oud!r} staat niet in het testbestand"
    return _GELDIG.replace(oud, nieuw, 1)


# --- schema ---


def test_een_geldig_bestand_laadt(tmp_path):
    regels = _laad(tmp_path, _GELDIG)

    assert regels.sentinel.waarden == (-1,)
    assert dict(regels.opleidingsvorm.codes) == {"VT": "voltijd", "DT": "deeltijd"}
    assert regels.kolomcorrecties[0].datasets == ("p04hogdipl",)
    assert regels.kolomcorrecties[0].gecontroleerd == date(2026, 10, 8)
    assert dict(regels.herkomst_is_vestiging[0].voorbeeldvragen) == {"Waar wonen ze?": "Waar liggen de vestigingen?"}
    assert [r.id for r in regels.alle()] == ["s", "o", "k", "h"]


def test_herschreven_voorbeeldvragen_zijn_optioneel(tmp_path):
    tekst = _gewijzigd(
        '\n[herkomst_is_vestiging.voorbeeldvragen]\n"Waar wonen ze?" = "Waar liggen de vestigingen?"\n', ""
    )

    assert dict(_laad(tmp_path, tekst).herkomst_is_vestiging[0].voorbeeldvragen) == {}


@pytest.mark.parametrize(
    ("oud", "nieuw", "melding"),
    [
        pytest.param(
            'bron = "bron van k"\n', "", r"regel 'k' \(kolomcorrectie\): 'bron' ontbreekt", id="bron-ontbreekt"
        ),
        pytest.param(
            'bron = "bron van k"', 'bron = "  "', r"regel 'k' \(kolomcorrectie\): 'bron' is leeg", id="bron-leeg"
        ),
        pytest.param('id = "k"\n', "", r"kolomcorrectie nr\. 1 \(zonder id\): 'id' ontbreekt", id="id-ontbreekt"),
        pytest.param(
            'id = "h"', 'id = "k"', r"regel 'k' \(herkomst_is_vestiging\): id 'k' staat ook bij", id="id-dubbel"
        ),
        pytest.param(
            'kolom = "DIPLOMAJAAR"', 'kollom = "DIPLOMAJAAR"', r"regel 'k'.*onbekende sleutel 'kollom'", id="typefout"
        ),
        pytest.param(
            "waarden = [-1]",
            'waarden = ["-1"]',
            r"regel 's'.*'waarden' element 1 moet een geheel getal",
            id="verkeerd-type",
        ),
        pytest.param("waarden = [-1]", "waarden = -1", r"regel 's'.*'waarden' moet een lijst", id="geen-lijst"),
        pytest.param("waarden = [-1]", "waarden = []", r"regel 's'.*'waarden' is een lege lijst", id="lege-lijst"),
        pytest.param(
            "gecontroleerd = 2026-10-08",
            'gecontroleerd = "2026-10-08"',
            r"regel 'k'.*'gecontroleerd' moet een datum",
            id="datum-als-tekst",
        ),
        pytest.param("[[kolomcorrectie]]", "[[kolomcorectie]]", r"onbekende regelsoort 'kolomcorectie'", id="soort"),
        pytest.param("[sentinel]", "[[sentinel]]", r"'sentinel' moet één regel zijn", id="sentinel-als-lijst"),
        pytest.param(
            "[[kolomcorrectie]]", "[kolomcorrectie]", r"'kolomcorrectie' moet een lijst", id="lijst-als-tabel"
        ),
        pytest.param("[[kolomcorrectie]]", "[[kolomcorrectie", r"geen geldige TOML", id="toml"),
    ],
)
def test_validatie_weigert(tmp_path, oud, nieuw, melding):
    with pytest.raises(DomeinregelFout, match=melding):
        _laad(tmp_path, _gewijzigd(oud, nieuw))


def test_een_onmisbare_regelsoort_mag_niet_ontbreken(tmp_path):
    """Zonder [sentinel] zou -1 als telwaarde meetellen; geen standaardwaarde, een fout."""
    zonder_sentinel = _GELDIG[_GELDIG.index("[opleidingsvorm]") :]

    with pytest.raises(DomeinregelFout, match=r"regelsoort 'sentinel' ontbreekt"):
        _laad(tmp_path, zonder_sentinel)


def test_twee_correcties_op_dezelfde_kolom_worden_geweigerd(tmp_path):
    """Anders wint stil de laatste; de beheerder ziet de eerste niet meer terug."""
    tweede = '\n[[kolomcorrectie]]\nid = "k2"\nbron = "b"\ngecontroleerd = 2026-10-08\n'
    tweede += 'datasets = ["p04hogdipl"]\nkolom = "DIPLOMAJAAR"\ndefinitie = "Anders."\n'

    with pytest.raises(DomeinregelFout, match=r"regel 'k2'.*DIPLOMAJAAR van p04hogdipl.*regel 'k'"):
        _laad(tmp_path, _GELDIG + tweede)


def test_een_ontbrekend_bestand_laadt_niet(tmp_path):
    with pytest.raises(DomeinregelFout, match="niet te lezen"):
        domeinregels.laad(tmp_path / "bestaat-niet.toml")


# --- fail-closed ---


@pytest.fixture
def ongeldig_standaardbestand(tmp_path, monkeypatch):
    """Het standaardpad wijst naar een bestand waarin één regel geen bron heeft; de cache is ervoor en erna leeg."""
    pad = tmp_path / "domeinregels.toml"
    pad.write_text(_gewijzigd('bron = "bron van k"\n', ""), encoding="utf-8")
    monkeypatch.setattr(domeinregels, "PAD", pad)
    domeinregels.laad.cache_clear()
    yield
    domeinregels.laad.cache_clear()


def test_de_tools_lezen_geen_ongeldig_bestand(ongeldig_standaardbestand):
    with pytest.raises(DomeinregelFout, match="'bron' ontbreekt"):
        duo_meta.regels()


def test_core_sentinels_laadt_niet_met_een_ongeldig_bestand(ongeldig_standaardbestand, monkeypatch):
    """core.sentinels laadt de regels bij import: de app start niet, in plaats van -1 mee te tellen."""
    monkeypatch.delitem(sys.modules, "core.sentinels")

    with pytest.raises(DomeinregelFout, match="'bron' ontbreekt"):
        importlib.import_module("core.sentinels")


def test_tools_en_core_delen_een_cache():
    assert duo_meta.regels() is domeinregels.laad()


# --- contract en effect, per regel in het echte bestand ---


def _in_scope(dataset: str) -> dict:
    record = next((e for e in _rio_duo() if e.get("_ckan_id") == dataset), None)
    assert record, f"{dataset} staat niet in de gepinde catalogus binnen mbo/hbo/wo"
    return record


def _beschrijving(record: dict) -> str:
    return str((record.get("_details") or {}).get("notes") or "")


def _contract_sentinel(regel: Sentinelregel) -> None:
    beschrijvingen = [_beschrijving(e) for e in _rio_duo() if e.get("leverancier") == "DUO"]
    for waarde in regel.waarden:
        passage = re.compile(rf"vervangen door\W*{re.escape(str(waarde))}(?!\d)")
        assert any(passage.search(t) for t in beschrijvingen), f"geen DUO-beschrijving noemt {waarde} als sentinel"
    # mask_sentinels vergelijkt met de kolomnaam in hoofdletters: een deel in kleine letters past nooit.
    assert all(deel == deel.upper() for deel in regel.uitgezonderd_als_kolom_bevat)


def _contract_kolomcorrectie(regel: Kolomcorrectie) -> None:
    for dataset in regel.datasets:
        kolommen = {k for per_bestand in _in_scope(dataset)["_kolommen"].values() for k in per_bestand}
        assert regel.kolom in kolommen, f"{regel.kolom} staat niet in _kolommen van {dataset}"


def _contract_herkomst(regel: HerkomstIsVestiging) -> None:
    catalogusvragen = set()
    for dataset in regel.datasets:
        _in_scope(dataset)
        catalogusvragen |= set(duo_meta.record(dataset).get("voorbeeldvragen") or [])
    weg = set(regel.voorbeeldvragen) - catalogusvragen
    assert not weg, f"te herschrijven vragen die de catalogus niet (meer) stelt: {sorted(weg)}"


def _contract_opleidingsvorm(regel: Opleidingsvormregel) -> None:
    # agent/labels.py en agent/report_definities.py zetten codes en woorden ongeëscaped in een regex.
    assert all(re.fullmatch(r"\w+", tekst) for paar in regel.codes.items() for tekst in paar), "alleen losse woorden"
    for dataset in regel.datasets:
        beschrijving = _beschrijving(_in_scope(dataset))
        assert "OPLEIDINGSVORM" in beschrijving, f"de beschrijving van {dataset} noemt OPLEIDINGSVORM niet"
        for code, vorm in regel.codes.items():
            assert re.search(rf"\b{re.escape(code)} {re.escape(vorm)}\b", beschrijving), f"{code} {vorm} in {dataset}"


def _effect_sentinel(regel: Sentinelregel) -> None:
    rij = [10, *regel.waarden]
    df = pd.DataFrame({"AANTAL": rij} | {f"{deel}_AANTAL": rij for deel in regel.uitgezonderd_als_kolom_bevat})

    gemaskeerd, cellen = mask_sentinels(df)

    assert gemaskeerd["AANTAL"].isna().sum() == len(regel.waarden)
    for deel in regel.uitgezonderd_als_kolom_bevat:
        assert list(gemaskeerd[f"{deel}_AANTAL"]) == rij
    assert regel.betekenis in sentinel_notes(count_cells(cellen))[0]


def _effect_kolomcorrectie(regel: Kolomcorrectie) -> None:
    for dataset in regel.datasets:
        assert column_definitions([regel.kolom], dataset)[regel.kolom] == regel.definitie
        details = json.loads(dataset_details(dataset))
        assert details["_kolomdefinities"][regel.kolom].startswith(regel.definitie)


def _effect_herkomst(regel: HerkomstIsVestiging) -> None:
    for dataset in regel.datasets:
        assert json.loads(dataset_details(dataset))["niet_geschikt_voor"] == regel.melding
        treffer = next(h for h in json.loads(search_catalog(dataset)) if h.get("_ckan_id") == dataset)
        assert treffer["niet_geschikt_voor"] == regel.melding
        vragen = _in_scope(dataset).get("voorbeeldvragen") or []
        for vraag in duo_meta.record(dataset).get("voorbeeldvragen") or []:
            if vraag in regel.voorbeeldvragen:
                assert vraag not in vragen
                assert regel.voorbeeldvragen[vraag] in vragen


def _effect_opleidingsvorm(regel: Opleidingsvormregel) -> None:
    for dataset in regel.datasets:
        definitie = column_definitions(["OPLEIDINGSVORM"], dataset)["OPLEIDINGSVORM"]
        labels = kolomlabel.waardelabels("OPLEIDINGSVORM", dataset)
        for code, vorm in regel.codes.items():
            assert f"{code} = {vorm}" in definitie
            assert labels[code] == vorm.capitalize()


_CONTRACT = {
    Sentinelregel: _contract_sentinel,
    Kolomcorrectie: _contract_kolomcorrectie,
    HerkomstIsVestiging: _contract_herkomst,
    Opleidingsvormregel: _contract_opleidingsvorm,
}
_EFFECT = {
    Sentinelregel: _effect_sentinel,
    Kolomcorrectie: _effect_kolomcorrectie,
    HerkomstIsVestiging: _effect_herkomst,
    Opleidingsvormregel: _effect_opleidingsvorm,
}
_REGELS = domeinregels.laad().alle()


def _controle(controles: dict, regel: Regel):
    if (controle := controles.get(type(regel))) is None:
        pytest.fail(f"geen test voor regelsoort {type(regel).__name__} (regel '{regel.id}')")
    return controle


@pytest.mark.parametrize("regel", _REGELS, ids=[r.id for r in _REGELS])
def test_contract(regel):
    """De regel verwijst naar wat de gepinde catalogus kent, en is niet in de toekomst gecontroleerd."""
    assert regel.gecontroleerd <= date.today()
    _controle(_CONTRACT, regel)(regel)


@pytest.mark.parametrize("regel", _REGELS, ids=[r.id for r in _REGELS])
def test_effect(regel):
    """De regel is zichtbaar in de tools: column_definitions, dataset_details, search_catalog of mask_sentinels."""
    _controle(_EFFECT, regel)(regel)


def test_elke_regelsoort_heeft_regels_in_het_bestand():
    """Een regelsoort zonder regels test hier niets; dan hoort de soort ook niet in het schema."""
    assert {type(r) for r in _REGELS} == set(_CONTRACT) == set(_EFFECT)


_HERNOEMDE_KOLOM = """
[[kolomcorrectie]]
id = "test-hernoemde-kolom"
bron = "test"
gecontroleerd = 2026-10-14
datasets = ["p01hoinges"]
kolom = "PROVINCIE_NAAM_OUD"
definitie = "Een kolom die DUO heeft hernoemd."
"""


def test_een_correctie_op_een_hernoemde_kolom_valt_op(tmp_path):
    """Hernoemt DUO een kolom, dan past de correctie nergens meer en zou ze stil wegvallen."""
    regels = _laad(tmp_path, domeinregels.PAD.read_text(encoding="utf-8") + _HERNOEMDE_KOLOM)
    regel = next(r for r in regels.kolomcorrecties if r.id == "test-hernoemde-kolom")

    with pytest.raises(AssertionError, match="PROVINCIE_NAAM_OUD"):
        _contract_kolomcorrectie(regel)
