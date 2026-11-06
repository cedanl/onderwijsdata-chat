"""Fusies in woorden en binnen een meerjarige DUO-reeks, uit RIO (#728); zonder netwerk.

DUO rekent elke reeks per instelling om naar de huidige code: Firda telt in 2021 en 2022 ook Friesland College mee,
dat pas op 1-8-2023 in Firda opging. Valt zo'n fusie binnen de reeks, dan zegt het antwoord dat in een vaste regel.
"""

import json
import logging

import httpx
import pandas as pd
import pytest
from onderwijsbronnen.rio import Stap

from agent.telling import telling_blok
from core import actualiteit
from tools import dekking, fusies, query, store
from tools.store import KeyMeta

_FRIESLAND = Stap(
    "25LG", "Regionaal Opleidingen Centrum Friesland College", "volledig", "2023-08-01", via="08PG", wet="WEB"
)
# Wat RIO op 05-11-2026 gaf voor de zes instellingen met een fusie na 1-10-2021 (onderzoek 04-11), met de wet van de
# voorganger op de dag vóór de overgang: Morgen College (02EX) is een vmbo-school (WVO), de rest mbo (WEB) (#937).
_VOORGANGERS = {
    "25EF": [
        Stap(
            "04EU",
            "Regionaal Opleidingen Centrum Kop van Noord-Holland voor VAVO MBO VW",
            "volledig",
            "2022-08-01",
            "25EF",
            wet="WEB",
        ),
        Stap(
            "30RA", "Regionaal Opleidingen Centrum Kop van Noord-Holland", "volledig", "2022-08-01", "25EF", wet="WEB"
        ),
    ],
    "04FO": [Stap("28DE", "ROC de Leijgraaf", "volledig", "2022-08-01", "04FO", wet="WEB")],
    "08PG": [_FRIESLAND],
    "25PW": [Stap("01NJ", "Agrarisch Opleidingscentrum Terra", "volledig", "2024-08-01", "25PW", wet="WEB")],
    "25PT": [
        Stap(
            "25RA",
            "Regio College voor Beroepsonderwijs en Educatie Zaanstreek-Waterland",
            "volledig",
            "2024-08-01",
            "25PT",
            wet="WEB",
        )
    ],
    "01AA": [
        Stap(
            "02EX",
            "Morgen College christelijke scholengemeenschap voor vmbo",
            "volledig",
            "2025-08-01",
            "01AA",
            wet="WVO",
        )
    ],
    # Yuverta: de fusie (1-8-2021) ligt vóór de eerste telling van de reeks (1-10-2021).
    "01OE": [Stap("26CC", "Helicon Opleidingen", "gedeeltelijk", "2021-08-01", "01OE", wet="WEB")],
}


@pytest.fixture
def rio(monkeypatch):
    """RIO als woordenboek; onthoudt de aanroepen."""
    aanroepen: list[tuple] = []

    def nep(code, sinds=None, peildatum=None):
        aanroepen.append((code, sinds))
        return [s for s in _VOORGANGERS.get(code, []) if sinds is None or s.datum >= sinds]

    monkeypatch.setattr(fusies, "voorgangers", nep)
    fusies._voorgangers.cache_clear()
    return aanroepen


def test_een_fusie_binnen_de_reeks_geeft_de_vaste_regel(rio):
    assert fusies.in_reeks({"08PG": "Firda"}, (2021, 2022, 2023, 2024, 2025)) == (
        "Fusie bij Firda (08PG): DUO telt de jaren vóór de fusie (1 augustus 2023) bij de huidige instelling "
        "(voorgangers: Regionaal Opleidingen Centrum Friesland College (25LG)).",
    )


def test_twee_voorgangers_op_dezelfde_dag_staan_in_een_regel(rio):
    (regel,) = fusies.in_reeks({"25EF": "Vonk"}, (2021, 2025))
    assert "(1 augustus 2022)" in regel
    assert "voorgangers: Regionaal Opleidingen Centrum Kop van Noord-Holland voor VAVO MBO VW (04EU), " in regel
    assert regel.endswith("Regionaal Opleidingen Centrum Kop van Noord-Holland (30RA)).")


@pytest.mark.parametrize("code", ["25EF", "04FO", "08PG", "25PW", "25PT"])
def test_vijf_van_de_zes_instellingen_uit_het_onderzoek_krijgen_de_regel(rio, code):
    assert len(fusies.in_reeks({code: code}, (2021, 2022, 2023, 2024, 2025))) == 1


def test_landstede_noemt_de_vmbo_voorganger_niet(rio):
    """Een mbo-reeks van DUO telt geen vmbo-leerlingen: Morgen College (02EX, WVO) is geen voorganger in die reeks,
    en zonder andere voorganger binnen de reeks komt er geen regel (#937, besluit A)."""
    assert fusies.in_reeks({"01AA": "Landstede"}, (2021, 2022, 2023, 2024, 2025)) == ()
    assert rio == [("01AA", "2021-10-01")]


def test_naast_een_vo_voorganger_blijft_de_mbo_voorganger_staan(rio, monkeypatch):
    stappen = [
        Stap("02EX", "Morgen College", "volledig", "2025-08-01", "01AA", wet="WVO"),
        Stap("99ZZ", "ROC Voorbeeld", "volledig", "2025-08-01", "01AA", wet="WEB"),
    ]
    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: stappen)
    (regel,) = fusies.in_reeks({"01AA": "Landstede"}, (2021, 2025))
    assert "(voorgangers: ROC Voorbeeld (99ZZ))" in regel
    assert "02EX" not in regel


@pytest.mark.parametrize("wet", ["WPO", "WVO", "WEC", "WVO 2020"])
def test_een_voorganger_uit_po_vo_of_so_valt_weg(rio, monkeypatch, wet):
    stap = Stap("02EX", "Een school", "volledig", "2023-08-01", "08PG", wet=wet)
    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: [stap])
    assert fusies.in_reeks({"08PG": "Firda"}, (2021, 2025)) == ()


def test_een_voorganger_met_onbekende_wet_blijft_staan(rio, monkeypatch):
    """RIO kent de erkenning niet (meer): de regel noemt haar, zoals vóór #937."""
    stap = Stap("25LG", None, "volledig", "2023-08-01", "08PG", wet=None)
    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: [stap])
    assert len(fusies.in_reeks({"08PG": "Firda"}, (2021, 2025))) == 1


def test_een_fusie_voor_de_eerste_telling_geeft_geen_regel(rio):
    assert fusies.in_reeks({"01OE": "Yuverta"}, (2021, 2022, 2023, 2024, 2025)) == ()


def test_een_fusie_na_de_laatste_telling_geeft_geen_regel(rio):
    assert fusies.in_reeks({"08PG": "Firda"}, (2021, 2022)) == ()


def test_een_jaar_is_geen_reeks(rio):
    assert fusies.in_reeks({"08PG": "Firda"}, (2024,)) == ()
    assert rio == []


def test_een_instelling_zonder_fusie_geeft_geen_regel(rio):
    assert fusies.in_reeks({"27GZ": "ROC Mondriaan"}, (2021, 2025)) == ()


def test_een_brede_selectie_vraagt_rio_niets(rio):
    """Een ranglijst van alle instellingen is geen reeks per instelling: geen 55 aanroepen bij RIO."""
    alle = {f"{i:02d}XX": f"Instelling {i}" for i in range(fusies.MAX_INSTELLINGEN + 1)}
    assert fusies.in_reeks(alle, (2021, 2025)) == ()
    assert rio == []


def test_de_voorgangers_staan_een_dag_in_de_cache(rio, monkeypatch):
    nu = actualiteit.nu()
    monkeypatch.setattr(actualiteit, "nu", lambda: nu)
    fusies.in_reeks({"08PG": "Firda"}, (2021, 2025))
    fusies.in_reeks({"08PG": "Firda"}, (2021, 2025))
    assert len(rio) == 1

    monkeypatch.setattr(actualiteit, "nu", lambda: nu + actualiteit.TTL)
    fusies.in_reeks({"08PG": "Firda"}, (2021, 2025))
    assert len(rio) == 2


def test_een_storing_geeft_een_vaste_regel_en_een_warning_en_komt_niet_in_de_cache(monkeypatch, caplog):
    """Geen stille uitval (#970): de regel zegt welk deel ontbreekt en waarom, de WARNING blijft."""
    pogingen = []

    def kapot(code, sinds=None, peildatum=None):
        pogingen.append(code)
        raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(fusies, "voorgangers", kapot)
    fusies._voorgangers.cache_clear()

    with caplog.at_level(logging.WARNING, logger="tools.fusies"):
        (regel,) = fusies.in_reeks({"08PG": "Firda"}, (2021, 2025))
    assert regel == (
        "Fusies niet nagegaan voor Firda (08PG): RIO gaf een storing, dus een fusie binnen de reeks 2021-2025 staat "
        "hier niet bij. Een sprong in de reeks kan door een fusie komen; zeg dat erbij."
    )
    assert fusies.niet_nagegaan((regel, "Fusie bij X: ...")) == [regel]
    assert any("FUSIES_ONBEKEND" in r.getMessage() and "08PG" in r.getMessage() for r in caplog.records)
    assert "geen netwerk" not in caplog.text

    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: [_FRIESLAND])
    assert len(fusies.in_reeks({"08PG": "Firda"}, (2021, 2025))) == 1


def test_opgegaan_in_woorden():
    stap = Stap("08PG", "Firda", "volledig", "2023-08-01", via="25LG")
    assert fusies.opgegaan("25LG", "Regionaal Opleidingen Centrum Friesland College", [stap]) == (
        "Regionaal Opleidingen Centrum Friesland College (25LG) is per 1 augustus 2023 opgegaan in Firda (08PG) "
        "(volledige overgang)."
    )


def test_opgegaan_in_een_keten_noemt_elke_stap():
    stappen = [
        Stap("22BB", "B", "volledig", "2019-08-01", via="11AA"),
        Stap("33CC", None, "gedeeltelijk", "2023-08-01", via="22BB"),
    ]
    assert fusies.opgegaan("11AA", "A", stappen) == (
        "A (11AA) is per 1 augustus 2019 opgegaan in B (22BB) (volledige overgang); "
        "B (22BB) is per 1 augustus 2023 opgegaan in 33CC (gedeeltelijke overgang)."
    )


# --- de selectie draagt haar fusieregels, vastgelegd bij het afleiden (dekking.van) ---


def _firda() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "JAAR": [2021, 2022, 2023, 2024, 2025],
            "INSTELLINGSCODE": ["08PG"] * 5,
            "INSTELLINGSNAAM": ["Firda"] * 5,
            "AANTAL": [23865, 22000, 21000, 20800, 20635],
        }
    )


def _meta(bron="duo") -> KeyMeta:
    return KeyMeta(
        bron=bron, dataset="mbo-studenten-per-instelling", periodekolom="JAAR", instellingskolom="INSTELLINGSCODE"
    )


def test_dekking_legt_de_fusieregels_van_een_duo_reeks_vast(rio):
    gedekt = dekking.van(_firda(), _meta())
    assert gedekt["fusies"] == fusies.in_reeks({"08PG": "Firda"}, (2021, 2022, 2023, 2024, 2025))
    assert gedekt["fusies"]


def test_zonder_naamkolom_noemt_de_regel_de_code(rio):
    gedekt = dekking.van(_firda().drop(columns="INSTELLINGSNAAM"), _meta())
    assert gedekt["fusies"][0].startswith("Fusie bij 08PG:")


def test_cbs_kent_geen_fusieregel(rio):
    assert dekking.van(_firda(), _meta(bron="cbs"))["fusies"] == ()
    assert rio == []


def test_een_reeks_van_firda_via_query_data_krijgt_de_regel_in_het_telling_blok(rio):
    """De hele keten: laden, selecteren op Firda per jaar, en het blok onder het antwoord."""
    alle = pd.concat([_firda(), _firda().assign(INSTELLINGSCODE="27GZ", INSTELLINGSNAAM="ROC Mondriaan")])
    store.put("duo:mbo:0", alle, _meta())

    uit = json.loads(
        query.query_data(
            "duo:mbo:0", filters={"INSTELLINGSCODE": "08PG"}, group_by=["JAAR"], aggregate={"AANTAL": "sum"}
        )
    )
    blok = telling_blok([json.dumps({"data_key": uit["data_key"]})])

    assert "- Fusie bij Firda (08PG): DUO telt de jaren vóór de fusie (1 augustus 2023)" in blok
    assert "ROC Mondriaan" not in blok


def test_een_selectie_erft_haar_fusieregels(rio):
    store.put("duo:laad", _firda(), _meta())
    store.derive("duo:laad", "duo:sel", _firda(), **dekking.van(_firda(), store.meta("duo:laad")))
    store.derive("duo:sel", "duo:som", _firda()[["JAAR", "AANTAL"]])
    som, sel = store.meta("duo:som"), store.meta("duo:sel")
    assert som is not None and sel is not None
    assert som.fusies == sel.fusies != ()


def test_een_rio_storing_staat_in_de_toolresponse_en_het_telling_blok(monkeypatch):
    """Geen stille uitval (#970): het model ziet dat de fusies niet zijn nagegaan, en de lezer ook."""

    def kapot(code, sinds=None, peildatum=None):
        raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(fusies, "voorgangers", kapot)
    fusies._voorgangers.cache_clear()
    store.put("duo:mbo:storing", _firda(), _meta())

    uit = json.loads(
        query.query_data(
            "duo:mbo:storing", filters={"INSTELLINGSCODE": "08PG"}, group_by=["JAAR"], aggregate={"AANTAL": "sum"}
        )
    )

    regel = "Fusies niet nagegaan voor Firda (08PG): RIO gaf een storing"
    assert any(n.startswith(regel) for n in uit["databewerking"])
    assert regel in telling_blok([json.dumps({"data_key": uit["data_key"]})])
