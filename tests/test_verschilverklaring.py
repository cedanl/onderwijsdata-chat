"""Waarom wijkt dit af van ons eigen cijfer? (#1258): een eigen getal naast het hoofdgetal, met de redenen uit code.

Onder een antwoord met precies één hoofdgetal (een vaste maat of een enkele selectie) staat de knop "Wijkt af van je
eigen cijfer?". Code zet het getal van de gebruiker naast het onze, loopt de redenen af die de teldefinitie van de
geladen key draagt en zegt hoeveel elk ervan verklaart. Het eigen getal is invoer, nooit bewijs.

De stappen zijn hier toolresultaten zoals get_maat en query_data ze geven, met de teldefinities van de recepten in
`tools/maten.py`; de getallen zijn die van mbo-studenten 2024/25 (`docs/domeinregels.md`).
"""

import asyncio
import importlib
import json

import pytest

from agent import beurtbewijs, controlestappen, verschilverklaring
from agent.controles import maak_getalcontrole
from agent.loop import LoopResult
from agent.onder_antwoord import KOP_VERSCHILVERKLARING
from agent.session_data import rekenbewijs
from routes import chat
from tools import andere_definities, maten
from tools.schemas import TOOL_GET_MAAT, TOOL_QUERY_DATA

_CBS_TEL = maten.MATEN[maten.MBO_STUDENTEN_LANDELIJK].teldefinitie + "; Leerweg: Totaal mbo (incl. extranei)"
_DUO_TEL = maten.MATEN[maten.MBO_STUDENTEN].teldefinitie
_HO_TEL = maten.MATEN[maten.PERSONEN_HO].teldefinitie


def _maat(waarde: int, teldefinitie: str, *, key: str = "k:maat", jaren=(2024,), extra: dict | None = None) -> str:
    rijen = [{"JAAR": jaar, "AANTAL": waarde, **(extra or {})} for jaar in jaren]
    return json.dumps(
        {
            "data_key": key,
            "maat": maten.MBO_STUDENTEN,
            "teldefinitie": teldefinitie,
            "vorm": "alle",
            "periodekolom": "JAAR",
            "waardekolom": "AANTAL",
            "rijen": rijen,
            "recept": {"bron": "duo", "dataset": "mbo-studenten-per-instelling"},
        }
    )


def _controles_met(key: str, hoofd: float, **alternatieven: float) -> controlestappen.Controles:
    """De andere definities zoals controlestappen ze na het antwoord rekende (#1256)."""
    definitie = controlestappen.Definitiecontrole(andere_definities.Hoofdgetal(hoofd, 2024, key), None)
    for naam, waarde in alternatieven.items():
        pct = andere_definities.verschil_pct(waarde, hoofd) or 0.0
        definitie.uitkomsten.append(controlestappen.Alternatiefuitkomst(naam.replace("_", " "), "", waarde, pct, None))
    return controlestappen.Controles(definities=[definitie])


# --- 7. de knop alleen bij precies één hoofdgetal ---------------------------------------------------------------------


def test_een_vaste_maat_met_een_rij_geeft_een_hoofdgetal():
    session: dict = {}
    uit = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, _maat(474963, _DUO_TEL))], controlestappen.Controles())

    assert uit == {"id": "k:maat", "waarde": 474963.0}
    assert session["hoofdgetallen"]["k:maat"]["teldefinitie"] == _DUO_TEL


@pytest.mark.parametrize(
    "stappen",
    [
        [(TOOL_GET_MAAT, _maat(474963, _DUO_TEL, jaren=(2023, 2024)))],  # een reeks: geen hoofdgetal
        [(TOOL_GET_MAAT, _maat(1, _DUO_TEL, key="a")), (TOOL_GET_MAAT, _maat(2, _DUO_TEL, key="b"))],  # twee getallen
        [
            (TOOL_QUERY_DATA, json.dumps({"data_key": "q", "rijen": [{"JAAR": 2024, "BBL": 1, "BOLVT": 2}]}))
        ],  # twee waarden
        [("search_catalog", json.dumps({"status": "candidates"}))],
        [],
    ],
    ids=["reeks", "twee-maten", "selectie-met-twee-waarden", "geen-data", "geen-stappen"],
)
def test_geen_knop_zonder_precies_een_hoofdgetal(stappen):
    assert verschilverklaring.onthoud({}, stappen, controlestappen.Controles()) is None


def test_een_enkele_selectie_en_dezelfde_waarde_uit_de_maat_tellen_een_keer():
    selectie = json.dumps({"data_key": "q", "rijen": [{"JAAR": 2024, "AANTAL": 474963}]})
    stappen = [(TOOL_GET_MAAT, _maat(474963, _DUO_TEL, jaren=(2023, 2024))), (TOOL_QUERY_DATA, selectie)]

    assert verschilverklaring.onthoud({}, stappen, controlestappen.Controles()) == {"id": "q", "waarde": 474963.0}


def test_run_zet_het_hoofdgetal_in_het_einde_van_het_antwoord():
    einde = importlib.import_module("agent.run")._slotbericht  # agent.run is ook de naam van de functie

    met = einde("Er waren 474.963 studenten.", LoopResult(), [], False, ["DUO"], hoofdgetal={"id": "k", "waarde": 1.0})
    assert met["hoofdgetal"] == {"id": "k", "waarde": 1.0}
    zonder = einde("Er waren 474.963 studenten.", LoopResult(), [], False, ["DUO"])
    assert "hoofdgetal" not in zonder


# --- 8 en 9. de redenen uit de teldefinitie, met hun grootte uit code -------------------------------------------------


def _mondriaan() -> tuple[str, int, int]:
    """De vaste maat voor ROC Mondriaan in 2024/25 uit het bevroren DUO-bestand (#766), met het totaal en de
    examendeelnemers (EX) die pandas los uit hetzelfde bestand rekent."""
    import pandas as pd

    from scripts.duo_testfixtures import MAP, bestandsnaam

    ruw = pd.read_csv(MAP / bestandsnaam("mbo-studenten-per-instelling", 0))
    (rij,) = ruw[(ruw["INSTELLINGSNAAM"] == "ROC Mondriaan") & (ruw["JAAR"] == 2024)].to_dict("records")
    totaal = sum(int(rij[k]) for k in ("BBL", "BOLDT", "BOLVT", "EX") if int(rij[k]) > 0)
    stap = maten.get_maat(maten.MBO_STUDENTEN, "ROC Mondriaan", schooljaren=["2024/25"])
    return stap, totaal, int(rij["EX"])


@pytest.mark.usefixtures("gouden")
def test_op_bevroren_duo_data_noemt_de_uitkomst_extranei_met_de_grootte_uit_het_bestand():
    """Ons getal telt de examendeelnemers mee (de teldefinitie van de maat); wie ze niet telt, komt precies zoveel lager.
    De grootte is de EX-cel van het bevroren bestand, niet een getal uit de test."""
    stap, totaal, ex = _mondriaan()
    session: dict = {}
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controlestappen.Controles())
    assert hoofd is not None and hoofd["waarde"] == totaal and ex > 0

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], str(totaal - ex))
    assert isinstance(uitkomst, dict)
    tekst = uitkomst["tekst"]
    nl = controlestappen.nl_getal
    assert f"ligt {nl(ex)} lager dan ons getal {nl(totaal)}" in tekst
    assert f"Extranei (examendeelnemers): ons getal telt ze mee: verklaart ongeveer {nl(ex)}." in tekst
    assert tekst.endswith("Het verschil valt binnen de bekende redenen.")
    assert "fout" not in tekst.lower()


@pytest.mark.usefixtures("gouden")
def test_een_reden_die_de_andere_kant_op_werkt_verklaart_het_verschil_niet():
    """Ons getal telt extranei al mee: een hoger eigen getal verklaren ze niet. De reden staat er met haar grootte,
    maar telt niet mee in de slotzin (audit van #1271: eerst telde elke reden mee, ongeacht haar richting)."""
    stap, totaal, ex = _mondriaan()
    session: dict = {}
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controlestappen.Controles())
    assert hoofd is not None

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], str(totaal + ex))
    assert isinstance(uitkomst, dict)
    tekst = uitkomst["tekst"]
    nl = controlestappen.nl_getal
    assert (
        f"Extranei (examendeelnemers): ons getal telt ze mee: scheelt ongeveer {nl(ex)}, maar de andere kant op"
        in tekst
    )
    assert "valt binnen de bekende redenen" not in tekst
    assert tekst.endswith(f"Na deze redenen blijft een verschil van {nl(ex)} over.")
    (extranei,) = [r for r in json.loads(uitkomst["stap"]["output"])["redenen"] if r["tekst"].startswith("Extranei")]
    assert (extranei["richting"], extranei["telt_mee"]) == (-1, False)


def test_naast_ons_duo_getal_noemt_de_uitkomst_extranei_met_de_berekende_grootte():
    """475.460 (CBS, incl. extranei) naast ons 474.963 (DUO, incl. examendeelnemers): extranei heeft een grootte, maar
    verklaart een hoger getal niet, want ons getal telt ze al mee. Het bevroren DUO-bestand heeft geen landelijk totaal
    van 474.963 (dat kwam uit het bestand per sectorkamer); de rij en haar EX-waarde (9.640) zijn hier synthetisch. De
    grootte uit het bevroren bestand toetst `test_op_bevroren_duo_data_noemt_de_uitkomst_extranei_…` hierboven."""
    session: dict = {}
    stap = json.dumps({**json.loads(_maat(474963, _DUO_TEL)), "rijen": [{"JAAR": 2024, "EX": 9640, "AANTAL": 474963}]})
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controlestappen.Controles())
    assert hoofd is not None

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], "475.460")
    assert isinstance(uitkomst, dict)
    tekst = uitkomst["tekst"]
    assert tekst.startswith(KOP_VERSCHILVERKLARING)
    assert "475.460" in tekst and "497 hoger dan ons getal 474.963" in tekst and "+0,1%" in tekst
    assert "Extranei (examendeelnemers): ons getal telt ze mee: scheelt ongeveer 9.640, maar de andere kant op" in tekst
    assert tekst.endswith("Na deze redenen blijft een verschil van 497 over.")
    assert "fout" not in tekst.lower()


def test_het_audit_voorbeeld_480000_heet_niet_verklaard():
    """De proef uit de audit: ons 474.963 telt extranei mee, de gebruiker zegt 480.000 (5.037 hoger)."""
    session: dict = {}
    stap = json.dumps({**json.loads(_maat(474963, _DUO_TEL)), "rijen": [{"JAAR": 2024, "EX": 9640, "AANTAL": 474963}]})
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controlestappen.Controles())
    assert hoofd is not None

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], "480.000")
    assert isinstance(uitkomst, dict)
    assert "valt binnen de bekende redenen" not in uitkomst["tekst"]
    assert uitkomst["tekst"].endswith("Na deze redenen blijft een verschil van 5.037 over.")


def test_naast_ons_cbs_getal_komt_de_grootte_van_extranei_uit_de_andere_definitie():
    session: dict = {}
    stap = json.dumps(
        {
            **json.loads(_maat(475460, _CBS_TEL, key="k:cbs")),
            "maat": maten.MBO_STUDENTEN_LANDELIJK,
            "periodekolom": "Perioden",
            "waardekolom": "MboStudenten_1",
            "rijen": [{"Perioden": "2024SJ00", "MboStudenten_1": 475460}],
            "recept": {"bron": "cbs", "dataset": "85354NED"},
        }
    )
    controles = _controles_met("k:cbs", 475460, zonder_extranei=465820)
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controles)
    assert hoofd is not None

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], "474963")
    assert isinstance(uitkomst, dict)
    assert "Extranei (examendeelnemers): ons getal telt ze mee: verklaart ongeveer 9.640." in uitkomst["tekst"]
    assert uitkomst["tekst"].endswith("Het verschil valt binnen de bekende redenen.")


def test_een_key_zonder_extraneiregel_laat_die_reden_weg_en_noemt_wat_overblijft():
    session: dict = {}
    stap = json.dumps({**json.loads(_maat(38288, _HO_TEL)), "maat": maten.PERSONEN_HO})
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controlestappen.Controles())
    assert hoofd is not None

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], "40.000")
    assert isinstance(uitkomst, dict)
    tekst = uitkomst["tekst"]
    assert "xtranei" not in tekst and "fout" not in tekst.lower()
    # Personen: de grootte is zonder de andere definitie niet te bepalen; de peildatum ook niet.
    assert "Personen of inschrijvingen: ons getal telt personen" in tekst and verschilverklaring.ONBEKEND in tekst
    assert tekst.endswith("Na deze redenen blijft een verschil van 1.712 over.")


def test_de_grootte_van_personen_of_inschrijvingen_komt_uit_de_andere_definitie():
    session: dict = {}
    stap = json.dumps({**json.loads(_maat(38288, _HO_TEL, key="k:ho")), "maat": maten.PERSONEN_HO})
    controles = _controles_met("k:ho", 38288, inschrijvingen=40100, alleen_voltijd=30000)
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, stap)], controles)
    assert hoofd is not None

    uitkomst = verschilverklaring.behandel(session, hoofd["id"], "40.000")
    assert isinstance(uitkomst, dict)
    assert "telt personen, wie inschrijvingen telt komt hoger: verklaart ongeveer 1.812." in uitkomst["tekst"]
    # Alleen voltijd komt lager uit (30.000): dat verklaart een hoger eigen getal niet, en telt niet mee.
    assert (
        "Opleidingsvorm: ons getal telt voltijd, deeltijd en duaal samen: scheelt ongeveer 8.288, maar de andere kant op"
        in uitkomst["tekst"]
    )
    assert uitkomst["tekst"].endswith("Het verschil valt binnen de bekende redenen.")


# --- 10. het eigen getal is invoer, nooit bewijs ----------------------------------------------------------------------


def _uitgelegd(session: dict) -> dict:
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, _maat(474963, _DUO_TEL))], controlestappen.Controles())
    assert hoofd is not None
    uitkomst = verschilverklaring.behandel(session, hoofd["id"], "475.460")
    assert isinstance(uitkomst, dict)
    return uitkomst


def test_het_eigen_getal_staat_in_de_stap_en_het_bewijs_als_invoer_zonder_citatie():
    session: dict = {"username": None}
    uitkomst = _uitgelegd(session)

    stap = json.loads(uitkomst["stap"]["output"])
    assert stap["eigen_getal"] == {"waarde": 475460, "invoer": "gebruiker", "citatie": None}
    assert stap["verschil"] == 497 and stap["ons_getal"]["waarde"] == 474963
    (bewijs,) = session["rekenbewijs"]
    assert bewijs["tool"] == verschilverklaring.STAP and bewijs["argumenten"]["eigen_getal"]["invoer"] == "gebruiker"
    # Het rapport en elk ander bewijs krijgen het niet: rekenbewijs() laat invoer van de gebruiker weg.
    assert rekenbewijs(session) == []


def test_het_eigen_getal_dekt_geen_ander_getal_in_de_getalcontrole():
    session: dict = {}
    uitkomst = _uitgelegd(session)
    berichten = [
        {"role": "user", "content": "Hoeveel mbo-studenten?"},
        {"role": "assistant", "content": uitkomst["tekst"]},
    ]

    earlier = beurtbewijs.eerdere_antwoorden(berichten, session)
    assert earlier == []  # de uitkomst bij een eigen getal is geen eerder antwoord dat als bron telt
    controle = maak_getalcontrole(earlier, ["Hoeveel mbo-studenten?"])
    assert [p.getal for p in controle("Jouw 475.460 klopt dus.", [])] == ["475.460"]
    # En het model ziet haar niet in een heropend gesprek.
    ruw = [*berichten, {"role": "user", "content": "En in 2023?"}]
    assert [m["content"] for m in chat._parse_history(ruw)] == ["Hoeveel mbo-studenten?", "En in 2023?"]


# --- 11. alleen een getal, hoogstens 12 cijfers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invoer", "verwacht"),
    [
        ("475.460", 475460),
        ("475 460", 475460),
        ("475460", 475460),
        (475460, 475460),
        ("999999999999", 999999999999),
        ("1234567890123", verschilverklaring.TE_LANG),
        ("ongeveer 475.000", verschilverklaring.GEEN_GETAL),
        ("475,5", verschilverklaring.GEEN_GETAL),
        ("-12", verschilverklaring.GEEN_GETAL),
        ("", verschilverklaring.GEEN_GETAL),
        (None, verschilverklaring.GEEN_GETAL),
        (True, verschilverklaring.GEEN_GETAL),
        ("1" * 60, verschilverklaring.TE_LANG),
        # Een punt of spatie scheidt alleen groepen van drie cijfers (Nederlandse notatie): de rest is geen heel getal.
        ("1.234.567", 1234567),
        ("1\u00a0234\u00a0567", 1234567),  # een harde spatie, zoals een spreadsheet hem kopieert
        ("1.5", verschilverklaring.GROEPERING),
        ("475.46", verschilverklaring.GROEPERING),
        ("4.7.5", verschilverklaring.GROEPERING),
        ("1234.567", verschilverklaring.GROEPERING),
        ("475.460 123", verschilverklaring.GROEPERING),
        ("475\n460", verschilverklaring.GEEN_GETAL),
        (".", verschilverklaring.GEEN_GETAL),
    ],
)
def test_alleen_een_heel_getal_van_hoogstens_twaalf_cijfers(invoer, verwacht):
    assert verschilverklaring.invoer(invoer) == verwacht


def _actie(session: dict, msg: dict) -> list[dict]:
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    asyncio.run(chat._handle_eigen_getal(msg, session, emit, None))
    return events


def test_de_websocketactie_weigert_een_niet_getal_met_een_melding():
    session: dict = {}
    hoofd = verschilverklaring.onthoud(session, [(TOOL_GET_MAAT, _maat(474963, _DUO_TEL))], controlestappen.Controles())
    assert hoofd is not None

    (fout,) = _actie(session, {"action": "eigen_getal", "id": hoofd["id"], "getal": "veel"})
    assert fout == {"type": "eigen_getal_fout", "melding": verschilverklaring.GEEN_GETAL, "id": hoofd["id"]}
    (te_lang,) = _actie(session, {"action": "eigen_getal", "id": hoofd["id"], "getal": "1234567890123"})
    assert te_lang["melding"] == verschilverklaring.TE_LANG
    (onbekend,) = _actie(session, {"action": "eigen_getal", "id": "niet-van-deze-sessie", "getal": "5"})
    assert onbekend["melding"] == verschilverklaring.GEEN_HOOFDGETAL
    assert "eigen_getal" in chat.ACTIES and "eigen_getal" not in chat.RUN_ACTIES

    (ok,) = _actie(session, {"action": "eigen_getal", "id": hoofd["id"], "getal": "475.460"})
    assert ok["type"] == "verschilverklaring" and ok["content"].startswith(KOP_VERSCHILVERKLARING)
    assert ok["stap"]["name"] == verschilverklaring.STAP
