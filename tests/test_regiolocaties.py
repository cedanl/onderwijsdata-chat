"""Een regiovergelijking van mbo-instellingen kiest de instellingen via hun onderwijslocaties (#744); zonder netwerk.

Filtert het model een mbo-bestand op de plaats, de gemeente of de provincie van de instelling, dan neemt de code ook
de instellingen mee met een onderwijslocatie in dat gebied, en zegt een vaste regel welke dat zijn en dat de aantallen
per instelling gelden. Het niveau volgt uit de kolom van het filter, niet uit een vaste keuze.

Bevroren: de DUO-rijen van 2025 voor zes instellingen (mbo-studenten-per-instelling, 05-11-2026), het aanbod per
locatie in Doetinchem, Lochem, Hardenberg en Velp (`scripts/duo_testfixtures.py`) en de aanbieders per instelling uit
RIO (`tests/fixtures/rio/organisatorische_eenheden.json`, 05-11-2026).
"""

import json
import logging
from pathlib import Path

import httpx
import pandas as pd
import pytest
from onderwijsbronnen import duo

from agent.telling import telling_blok
from core import actualiteit
from tools import instellingsprovincie, regiolocaties, store
from tools.query import query_data
from tools.snippet import generate
from tools.store import KeyMeta

_RIO = json.loads((Path(__file__).parent / "fixtures" / "rio" / "organisatorische_eenheden.json").read_text())
_KEY = "duo:mbo-studenten-per-instelling:0"
_KOLOMMEN = ["JAAR", "PROVINCIE INSTELLING", "INSTELLINGSCODE", "INSTELLINGSNAAM", "PLAATSNAAM INSTELLING"]
_KOLOMMEN += ["GEMEENTENUMMER INSTELLING", "GEMEENTE INSTELLING", "BBL", "BOLVT"]
# mbo-studenten-per-instelling, bestand 0, JAAR 2025 (DUO, 05-11-2026).
_RIJEN = [
    [2025, "Gelderland", "24ZZ", "ROC Graafschap College", "DOETINCHEM", "0222", "DOETINCHEM", 2692, 5431],
    [2025, "Gelderland", "25LF", "Rijn IJssel", "ARNHEM", "0202", "ARNHEM", 2196, 7786],
    [2025, "Gelderland", "31JC", "Zone.college", "LOCHEM", "0262", "LOCHEM", 659, 2262],
    [2025, "Gelderland", "25PM", "ROC A12", "EDE", "0228", "EDE", 1935, 3659],
    [2025, "Groningen", "25LU", "Alfa-college", "GRONINGEN", "0014", "GRONINGEN", 3483, 7558],
    [2025, "Overijssel", "27YU", "ROC van Twente", "HENGELO OV", "0164", "HENGELO", 5462, 11872],
]
_ZONE = "Zone.college (31JC, hoofdvestiging Lochem)"


def _aanbieders(brin, peildatum=None):
    return [e["code"] for e in _RIO.get(brin, []) if e["type"] == "ONDERWIJSAANBIEDER"]


@pytest.fixture
def rio(duo_fixtures, monkeypatch):
    """Het aanbod per locatie uit de DUO-fixture, de aanbieders uit de RIO-fixture; onthoudt de RIO-aanroepen."""
    aanroepen: list[str] = []

    def aanbieders(brin, peildatum=None):
        aanroepen.append(brin)
        return _aanbieders(brin)

    monkeypatch.setattr(regiolocaties, "_laad_aanbod", lambda: duo.load(*regiolocaties.AANBOD))
    monkeypatch.setattr(regiolocaties, "onderwijsaanbieders", aanbieders)
    regiolocaties.wis_caches()
    yield aanroepen
    regiolocaties.wis_caches()


def _zet_studenten() -> None:
    meta = KeyMeta(
        bron="duo",
        dataset="mbo-studenten-per-instelling",
        resource=0,
        periodekolom="JAAR",
        instellingskolom="INSTELLINGSCODE",
    )
    df = instellingsprovincie.met_regio(pd.DataFrame(_RIJEN, columns=_KOLOMMEN), "mbo-studenten-per-instelling")
    store.put(_KEY, df, meta)


@pytest.fixture
def studenten():
    _zet_studenten()
    return _KEY


def _selectie(filters: dict, key: str = _KEY) -> dict:
    return json.loads(query_data(key, filters=filters, columns=["INSTELLINGSCODE", "INSTELLINGSNAAM", "BOLVT"]))


def _codes(uit: dict) -> set[str]:
    return {r["INSTELLINGSCODE"] for r in uit["rijen"]}


def _blok(uit: dict) -> str:
    return telling_blok([json.dumps({"data_key": uit["data_key"]})])


# --- plaats, gemeente, provincie: het niveau volgt uit de kolom van het filter ---


def test_in_doetinchem_telt_zone_college_mee_via_zijn_locatie(rio, studenten):
    uit = _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})

    assert _codes(uit) == {"24ZZ", "31JC"}
    blok = _blok(uit)
    assert f"in de plaats Doetinchem (RIO): {_ZONE}." in blok
    assert "niet per locatie" in blok
    assert "Graafschap" not in blok


def test_de_regel_staat_ook_in_de_toolresponse_voor_het_model(rio, studenten):
    uit = _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})

    assert any(_ZONE in noot for noot in uit["databewerking"])


@pytest.mark.parametrize(
    "filters",
    [{"GEMEENTE INSTELLING": "DOETINCHEM"}, {"GEMEENTE INSTELLING": "Doetinchem"}, {"GEMEENTENUMMER INSTELLING": 222}],
)
def test_de_gemeente_doetinchem_op_naam_of_nummer(rio, studenten, filters):
    uit = _selectie(filters)

    assert _codes(uit) == {"24ZZ", "31JC"}
    assert f"in de gemeente Doetinchem (RIO): {_ZONE}." in _blok(uit)


def test_in_overijssel_tellen_zone_college_en_alfa_college_mee_via_hardenberg(rio, studenten):
    uit = _selectie({"PROVINCIE INSTELLING": "Overijssel"})

    assert _codes(uit) == {"27YU", "31JC", "25LU"}
    assert (
        "in de provincie Overijssel (RIO): Alfa-college (25LU, hoofdvestiging Groningen), "
        "Zone.college (31JC, hoofdvestiging Gelderland)." in _blok(uit)
    )


def test_wie_al_via_de_hoofdvestiging_meedoet_krijgt_geen_regel(rio, studenten):
    uit = _selectie({"PROVINCIE INSTELLING": "Gelderland"})

    assert _codes(uit) == {"24ZZ", "25LF", "31JC", "25PM"}
    assert "RIO" not in _blok(uit)
    assert "databewerking" not in uit


def test_twee_waarden_in_een_filter(rio, studenten):
    uit = _selectie({"PLAATSNAAM INSTELLING__in": ["DOETINCHEM", "ARNHEM"]})

    assert _codes(uit) == {"24ZZ", "25LF", "31JC"}
    assert "in de plaats Doetinchem of Arnhem (RIO)" in _blok(uit)


def test_een_regio_zonder_locaties_vraagt_rio_niets(rio, studenten):
    _selectie({"PLAATSNAAM INSTELLING": "ARNHEM"})

    assert rio == []


def test_in_de_arbeidsmarktregio_achterhoek_telt_zone_college_mee_via_doetinchem(rio, studenten):
    """Lochem ligt in Veluwe Stedendriehoek; de locatie in Doetinchem ligt in de Achterhoek."""
    uit = _selectie({"ARBEIDSMARKTREGIO INSTELLING": "Achterhoek"})

    assert _codes(uit) == {"24ZZ", "31JC"}
    assert (
        "in de arbeidsmarktregio Achterhoek (RIO): Zone.college (31JC, hoofdvestiging Veluwe Stedendriehoek)."
        in _blok(uit)
    )


def test_in_regio_zwolle_tellen_drie_instellingen_mee_via_hardenberg(rio, studenten):
    uit = _selectie({"ARBEIDSMARKTREGIO INSTELLING": "regio zwolle"})

    assert _codes(uit) == {"25LU", "27YU", "31JC"}
    assert "in de arbeidsmarktregio Regio Zwolle (RIO)" in _blok(uit)


# --- alleen een vergelijking per instelling verbreedt; een totaal blijft bij de hoofdvestiging ---


def _som(filters: dict, group_by: list[str]) -> dict:
    return json.loads(query_data(_KEY, filters=filters, group_by=group_by, aggregate={"BBL": "sum", "BOLVT": "sum"}))


def test_een_totaal_per_provincie_blijft_het_totaal_van_de_hoofdvestigingen(rio, studenten):
    """Een som over de instellingen heen telt alleen wie zijn hoofdvestiging in Overijssel heeft, zoals vóór #744."""
    (rij,) = _som({"PROVINCIE INSTELLING": "Overijssel"}, ["JAAR"])["rijen"]

    assert (rij["BBL"], rij["BOLVT"]) == (5462, 11872)  # alleen ROC van Twente


def test_een_totaal_zegt_wie_er_niet_in_zit(rio, studenten):
    uit = _som({"PROVINCIE INSTELLING": "Overijssel"}, ["JAAR"])

    assert (
        "Het totaal telt de instellingen met hun hoofdvestiging in de provincie Overijssel; 2 instellingen met alleen "
        "een onderwijslocatie daar tellen niet mee (vergelijk per instelling om ze te zien)." in uit["databewerking"]
    )
    assert "RIO" not in _blok(uit)


def test_een_totaal_zonder_nevenlocaties_krijgt_geen_regel(rio, studenten):
    assert "databewerking" not in _som({"PROVINCIE INSTELLING": "Gelderland"}, ["JAAR"])


def test_een_som_per_arbeidsmarktregio_blijft_bij_de_hoofdvestiging(rio, studenten):
    uit = _som({"ARBEIDSMARKTREGIO INSTELLING": "Achterhoek"}, ["JAAR"])

    assert uit["rijen"][0]["BOLVT"] == 5431  # alleen Graafschap College
    assert any("1 instelling met alleen een onderwijslocatie daar telt niet mee" in n for n in uit["databewerking"])


def test_een_som_per_jaar_verbreedt_niet(rio, studenten):
    (rij,) = _som({"PLAATSNAAM INSTELLING": "DOETINCHEM"}, ["JAAR"])["rijen"]

    assert rij["BOLVT"] == 5431  # alleen Graafschap College


@pytest.mark.parametrize("kolom", ["INSTELLINGSNAAM", "INSTELLINGSCODE"])
def test_een_som_per_instelling_verbreedt(rio, studenten, kolom):
    uit = _som({"PLAATSNAAM INSTELLING": "DOETINCHEM"}, [kolom])

    assert len(uit["rijen"]) == 2
    assert _ZONE in _blok(uit)


def test_een_vergelijking_per_instelling_neemt_zone_college_mee(rio, studenten):
    uit = _selectie({"GEMEENTE INSTELLING": "DOETINCHEM"})

    assert _codes(uit) == {"24ZZ", "31JC"}


# --- wat de code niet raadt ---


def test_velp_ligt_in_twee_gemeenten_en_telt_daar_niet(rio, studenten):
    """Velp is een woonplaats in Rheden én in Land van Cuijk: de gemeente van een locatie in Velp is onbekend."""
    uit = json.loads(query_data(_KEY, filters={"GEMEENTE INSTELLING": "RHEDEN"}))

    assert uit["rijen"] == []


def test_als_plaats_telt_velp_wel(rio, studenten):
    uit = _selectie({"PLAATSNAAM INSTELLING": "VELP"})

    assert _codes(uit) == {"25PM"}
    assert "in de plaats Velp (RIO): ROC A12 (25PM, hoofdvestiging Ede)." in _blok(uit)


def test_een_filter_op_de_instellingscode_is_geen_regio(rio, studenten):
    uit = _selectie({"INSTELLINGSCODE": "24ZZ"})

    assert _codes(uit) == {"24ZZ"}
    assert rio == []


def test_een_cbs_tabel_kent_geen_regio_via_locaties(rio):
    df = pd.DataFrame(_RIJEN, columns=_KOLOMMEN)
    store.put("cbs:x", df, KeyMeta(bron="cbs", dataset="x"))

    assert _codes(_selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"}, "cbs:x")) == {"24ZZ"}
    assert rio == []


# --- storing en cache ---


def test_een_rio_storing_geeft_geen_regel_een_warning_en_niets_in_de_cache(rio, studenten, monkeypatch, caplog):
    def kapot(brin, peildatum=None):
        raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(regiolocaties, "onderwijsaanbieders", kapot)
    with caplog.at_level(logging.WARNING, logger="tools.regiolocaties"):
        uit = _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})

    assert _codes(uit) == {"24ZZ"}
    assert "RIO" not in _blok(uit)
    assert any("REGIOLOCATIES_ONBEKEND" in r.getMessage() for r in caplog.records)
    assert "geen netwerk" not in caplog.text

    monkeypatch.setattr(regiolocaties, "onderwijsaanbieders", _aanbieders)
    assert _codes(_selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})) == {"24ZZ", "31JC"}


def test_een_dag_in_de_cache(rio, studenten, monkeypatch):
    nu = actualiteit.nu()
    monkeypatch.setattr(actualiteit, "nu", lambda: nu)
    _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})
    eerst = len(rio)
    _selectie({"PROVINCIE INSTELLING": "Overijssel"})

    assert eerst == len(_RIJEN)
    assert len(rio) == eerst

    monkeypatch.setattr(actualiteit, "nu", lambda: nu + actualiteit.TTL)
    _zet_studenten()
    _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})
    assert len(rio) == 2 * eerst


# --- de regel reist mee met de selectie, de snippet doet hetzelfde ---


def test_een_som_over_de_selectie_houdt_de_regel(rio, studenten):
    sel = _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})
    som = json.loads(query_data(sel["data_key"], group_by=["INSTELLINGSNAAM"], aggregate={"BOLVT": "sum"}))

    assert _ZONE in _blok(som)


def test_een_selectie_zonder_zone_college_verliest_de_regel(rio, studenten):
    sel = _selectie({"PLAATSNAAM INSTELLING": "DOETINCHEM"})
    alleen = json.loads(query_data(sel["data_key"], filters={"INSTELLINGSCODE": "24ZZ"}))

    assert "RIO" not in _blok(alleen)


def test_de_snippet_neemt_dezelfde_instellingen_mee(rio, studenten):
    filters = {"PLAATSNAAM INSTELLING": "DOETINCHEM"}
    uit = query_data(_KEY, filters=filters)
    snippet = generate("query_data", {"data_key": _KEY, "filters": filters}, uit)

    assert snippet is not None
    assert "isin(['31JC'])" in snippet
    regels = snippet.splitlines()
    begin = regels.index("_voor = df")
    plaats = {"df": pd.DataFrame(_RIJEN, columns=_KOLOMMEN), "pd": pd}
    exec("\n".join(regels[begin : begin + 4]), plaats)
    assert set(plaats["df"]["INSTELLINGSCODE"]) == {"24ZZ", "31JC"}
