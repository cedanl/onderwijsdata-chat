"""koppel_data: een SKDB-rij zonder DUO-rij krijgt haar reden uit RIO, in code (#1060, #1015).

Het patroon van Avans (07GR): de SKDB toont HBO-ICT (30020), dat volgens RIO op 1-9-2026 begint als opvolger van
Informatica (34479). DUO 2025 (peildatum 1-10-2025) telt 34479 (928) en Technische Informatica (34475, 206), en nog
geen 30020. De koppeling zegt dan "nieuw per 1-9-2026, nog niet in DUO 2025", noemt 34479 met zijn aantal en telt
niets op; 34475 loopt door en is geen voorganger. RIO komt uit een fixture (de licenties zoals gemeten op 19-11-2026,
ingekort); de DUO-aantallen van Avans zijn de gemeten, die van HU (25DW) verzonnen.
"""

import json
from datetime import date

import httpx
import pandas as pd
import pytest
from onderwijsbronnen.rio import Licentie

import tools
from data import instellingen
from tools import opvolger, store
from tools.opvolger import DuoTabel, nieuwe_licentie, te_bepalen, voorgangers
from tools.schemas import TOOL_KOPPEL_DATA
from tools.store import KeyMeta

_SKDB = "skdb:opleidingen:proef1060"
_DUO = "duo:p01hoinges:0"
_DUO2 = "duo:p02ho1ejrs:0"
_SKDB_META = KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase")
_DUO_META = KeyMeta(bron="duo", dataset="p01hoinges", resource=0, periodekolom="STUDIEJAAR")
_PEIL = "2025-10-01"
_REDEN = "nieuw per 1-9-2026, nog niet in DUO 2025"


def _lic(id_, croho, onderdeel, begin, eind=None) -> Licentie:
    return Licentie(id_, begin, eind, f"https://rio/{id_}/opleidingserkenning", croho, onderdeel, eind)


# Avans in RIO: 34475 loopt door, 34479 eindigt op 2026-09-01, vijf licenties beginnen dan (hier drie, één per onderdeel).
_TI = _lic("ti", "34475", "TECHNIEK", "2002-09-01")
_INFORMATICA = _lic("inf", "34479", "TECHNIEK", "2003-09-01", "2026-09-01")
_ICT = _lic("ict", "30020", "TECHNIEK", "2026-09-01")
_GEDRAG = _lic("gm", "45534", "GEDRAG_EN_MAATSCHAPPIJ", "2026-09-01")
_SECTOR = _lic("so", "49512", "SECTOROVERSTIJGEND", "2026-09-01")
_TOEN = (_TI, _INFORMATICA)
_NU = (_TI, _ICT, _GEDRAG, _SECTOR)


def _kaal(lic: Licentie) -> Licentie:
    """Zoals de lijst van RIO een licentie geeft: zonder opleidingscode, die staat in de erkenning."""
    return Licentie(lic.id, lic.begindatum, lic.einddatum, lic.erkenning)


@pytest.fixture(autouse=True)
def geen_register(monkeypatch):
    monkeypatch.setattr(instellingen, "get_all", lambda: [])


@pytest.fixture
def rio(monkeypatch):
    """RIO voor Avans; elke andere brin heeft geen licenties. Houdt bij welke lijsten en erkenningen gevraagd zijn."""
    aanroepen: list[tuple] = []
    volledig = {lic.id: lic for lic in (*_TOEN, *_NU)}

    def lijst(brin, peildatum=None):
        aanroepen.append(("lijst", brin, peildatum))
        if brin != "07GR":
            return ()
        return tuple(_kaal(lic) for lic in (_TOEN if peildatum == _PEIL else _NU))

    def erkenning(lic):
        aanroepen.append(("erkenning", lic.id))
        return volledig[lic.id]

    monkeypatch.setattr(opvolger, "onderwijslicenties", lijst)
    monkeypatch.setattr(opvolger, "met_erkenning", erkenning)
    opvolger.wis_caches()
    return aanroepen


def _koppel(data_key=_SKDB, andere_key=_DUO, sleutels=("brin", "croho")) -> tuple[dict, str]:
    uit, _ = tools.dispatch(
        TOOL_KOPPEL_DATA, {"data_key": data_key, "andere_key": andere_key, "sleutels": list(sleutels)}
    )
    return json.loads(uit), uit


def _avans(skdb_extra=()) -> None:
    """SKDB: Avans ICT (zonder DUO-rij), Avans TI en HU ICT (met DUO-rij). DUO 2025: 34479, 34475 en HU 30020."""
    skdb = [("07GR", 30020), ("07GR", 34475), ("25DW", 30020), *skdb_extra]
    store.put(
        _SKDB,
        pd.DataFrame({"brin": [b for b, _ in skdb], "croho": [c for _, c in skdb], "nse_oordeel": 3.4}),
        _SKDB_META,
    )
    duo = pd.DataFrame(
        {
            "STUDIEJAAR": 2025,
            "INSTELLINGSCODE_ACTUEEL": ["07GR", "07GR", "25DW"],
            "OPLEIDINGSCODE_ACTUEEL": [34479.0, 34475.0, 30020.0],
            "OPLEIDINGSNAAM_ACTUEEL": ["B Informatica", "B Technische Informatica", "B HBO-ICT"],
            "AANTAL_INGESCHREVENEN": [928, 206, 512],
        }
    )
    store.put(_DUO, duo, _DUO_META)


# --- De regels, puur ---------------------------------------------------------------------------------------------------


def test_alleen_de_licenties_die_wisselen_hebben_hun_erkenning_nodig():
    nodig = te_bepalen(_PEIL, _NU, _TOEN)
    assert sorted(lic.croho or "" for lic in nodig) == ["30020", "34479", "45534", "49512"]


def test_een_licentie_die_na_de_peildatum_begint_is_nieuw():
    assert nieuwe_licentie("30020", _PEIL, _NU) == _ICT
    assert nieuwe_licentie("34475", _PEIL, _NU) is None  # loopt door
    assert nieuwe_licentie("99999", _PEIL, _NU) is None  # geen licentie


def test_een_opleiding_met_ook_een_oudere_licentie_is_niet_nieuw():
    oud = _lic("oud", "30020", "TECHNIEK", "2010-09-01")
    assert nieuwe_licentie("30020", _PEIL, (*_NU, oud)) is None


def test_de_voorganger_deelt_het_onderdeel_en_eindigt_op_de_begindatum():
    assert voorgangers(_ICT, _NU, _TOEN) == [_INFORMATICA]
    assert voorgangers(_GEDRAG, _NU, _TOEN) == []  # ander onderdeel
    eerder = _lic("eerder", "34400", "TECHNIEK", "2000-09-01", "2026-02-01")
    assert voorgangers(_ICT, _NU, (*_TOEN, eerder)) == [_INFORMATICA]  # andere einddatum


def test_een_licentie_die_vandaag_nog_geldt_is_geen_voorganger():
    assert voorgangers(_ICT, (*_NU, _INFORMATICA), _TOEN) == []


def test_het_laatste_jaar_komt_uit_de_periodekolom_en_anders_uit_de_meta():
    df = pd.DataFrame({"STUDIEJAAR": [2024, 2025], "BRIN": "07GR", "CROHO": 34479})
    kolommen = {"brin": "BRIN", "croho": "CROHO"}
    met_kolom = DuoTabel.van(df, kolommen, _DUO_META)
    assert met_kolom is not None and met_kolom.jaar == 2025
    zonder_kolom = DuoTabel.van(
        df.drop(columns="STUDIEJAAR"), kolommen, KeyMeta(bron="duo", dataset="x", schooljaren=(2023, 2024))
    )
    assert zonder_kolom is not None and zonder_kolom.jaar == 2024
    assert DuoTabel.van(df.drop(columns="STUDIEJAAR"), kolommen, KeyMeta(bron="duo", dataset="x")) is None


# --- Avans in koppel_data ----------------------------------------------------------------------------------------------


def test_avans_ict_is_nieuw_per_1_9_2026_met_informatica_als_voorganger(rio):
    _avans()
    uit, _ = _koppel()
    assert uit["opvolgers"] == [
        {
            "brin": "07GR",
            "croho": "30020",
            "reden": _REDEN,
            "voorgangers": [
                {"croho": "34479", "einde": "1-9-2026", "duo_jaar": 2025, "naam": "B Informatica", "duo_aantal": 928}
            ],
            "tekst": (
                f"07GR/30020: {_REDEN}. Voorganger volgens RIO: 34479 B Informatica (instroom tot 1-9-2026; in DUO "
                "2025: 928). Genoemd, niet opgeteld bij 30020."
            ),
        }
    ]


def test_technische_informatica_loopt_door_en_wordt_niet_genoemd(rio):
    _avans()
    uit, _ = _koppel()
    assert "34475" not in json.dumps(uit["opvolgers"])
    assert "206" not in json.dumps(uit["opvolgers"])
    assert ("erkenning", "ti") not in rio  # een licentie die doorloopt, kost geen aanroep


def test_er_wordt_niets_opgeteld(rio):
    _avans()
    uit, _ = _koppel()
    df = store.get(uit["data_key"]).set_index(["brin", "croho"])
    assert pd.isna(df.loc[("07GR", "30020"), "AANTAL_INGESCHREVENEN"])  # leeg, niet 928 en niet 928 + 206
    assert df["AANTAL_INGESCHREVENEN"].sum() == 928 + 206 + 512
    assert uit["telling"] == {"beide": 2, "alleen SKDB": 1, "alleen DUO": 1}


def test_de_reden_staat_per_rij_in_de_kolom_koppelreden(rio):
    _avans(skdb_extra=[("07GR", 80000)])
    uit, _ = _koppel()
    df = store.get(uit["data_key"])
    assert list(df.columns[:4]) == ["brin", "croho", "koppelstatus", "koppelreden"]
    reden = df.set_index(["brin", "croho"])["koppelreden"]
    assert reden[("07GR", "30020")] == _REDEN
    assert reden[("07GR", "80000")] == opvolger.GEEN_DUO_RIJ  # zonder licentie die na de peildatum begint
    assert pd.isna(reden[("25DW", "30020")]) and pd.isna(reden[("07GR", "34479")])
    assert [o["croho"] for o in uit["opvolgers"]] == ["30020"]


def test_de_tekst_noemt_een_opvolger_nooit_ontbrekend(rio):
    _avans()
    uit, tekst = _koppel()
    assert "ontbreekt in DUO" not in tekst and "geen data" not in tekst
    assert opvolger.TOELICHTING in uit["toelichting"]["alleen SKDB"]
    assert "niet op bij de nieuwe opleiding" in uit["toelichting"]["alleen SKDB"]


def test_de_kant_van_de_vraag_maakt_niet_uit(rio):
    _avans()
    eerst, _ = _koppel()
    omgekeerd, _ = _koppel(_DUO, _SKDB)
    assert omgekeerd["opvolgers"] == eerst["opvolgers"]


def test_rio_wordt_per_instelling_en_dag_een_keer_gevraagd(rio):
    _avans()
    _koppel()
    _koppel(_DUO, _SKDB)
    lijsten = [a for a in rio if a[0] == "lijst"]
    assert lijsten == [("lijst", "07GR", date.today().isoformat()), ("lijst", "07GR", _PEIL)]
    assert sorted(a[1] for a in rio if a[0] == "erkenning") == ["gm", "ict", "inf", "so"]


# --- Zonder opvolger: zoals voorheen -----------------------------------------------------------------------------------


def test_zonder_opvolger_blijft_het_geen_duo_rij(rio):
    """Een SKDB-rij zonder DUO-rij en zonder licentie die na de peildatum begint: de koppeling zoals voorheen."""
    store.put(_SKDB, pd.DataFrame({"brin": ["07GR", "07GR"], "croho": [80000, 34475]}), _SKDB_META)
    store.put(
        _DUO,
        pd.DataFrame(
            {"STUDIEJAAR": 2025, "INSTELLINGSCODE_ACTUEEL": ["07GR"], "OPLEIDINGSCODE_ACTUEEL": [34475], "AANTAL": 206}
        ),
        _DUO_META,
    )
    uit, _ = _koppel()
    df = store.get(uit["data_key"])
    assert "opvolgers" not in uit and "koppelreden" not in df.columns
    assert opvolger.TOELICHTING not in uit["toelichting"]["alleen SKDB"]
    assert "andere bron" in uit["toelichting"]["alleen SKDB"]
    assert ("lijst", "07GR", _PEIL) in rio  # wel nagegaan


def test_een_storing_bij_rio_laat_de_koppeling_slagen(monkeypatch):
    def storing(brin, peildatum=None):
        raise httpx.ConnectError("RIO onbereikbaar")

    monkeypatch.setattr(opvolger, "onderwijslicenties", storing)
    opvolger.wis_caches()
    _avans()
    uit, tekst = _koppel()
    df = store.get(uit["data_key"])
    assert uit["telling"] == {"beide": 2, "alleen SKDB": 1, "alleen DUO": 1}
    assert "opvolgers" not in uit and "koppelreden" not in df.columns
    assert "niet nagegaan voor 07GR" in uit["waarschuwing"] and opvolger.GEEN_DUO_RIJ in uit["waarschuwing"]
    assert "ontbreekt in DUO" not in tekst


def test_een_storing_komt_niet_in_de_cache(monkeypatch, rio):
    echt = opvolger.onderwijslicenties
    monkeypatch.setattr(opvolger, "onderwijslicenties", lambda *a: (_ for _ in ()).throw(httpx.ConnectError("weg")))
    _avans()
    assert "opvolgers" not in _koppel()[0]
    monkeypatch.setattr(opvolger, "onderwijslicenties", echt)
    assert _koppel()[0]["opvolgers"][0]["reden"] == _REDEN


# --- Andere koppelingen raken RIO niet aan ----------------------------------------------------------------------------


def test_een_gewone_match_verandert_niet(rio):
    """HU (25DW) 30020 staat in SKDB en DUO: geen RIO, geen kolom, geen opvolgers."""
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"], "croho": [30020], "nse_oordeel": [3.5]}), _SKDB_META)
    store.put(
        _DUO,
        pd.DataFrame(
            {
                "STUDIEJAAR": 2025,
                "INSTELLINGSCODE_ACTUEEL": ["25DW"],
                "OPLEIDINGSCODE_ACTUEEL": [30020.0],
                "AANTAL": 512,
            }
        ),
        _DUO_META,
    )
    uit, _ = _koppel()
    assert uit["telling"] == {"beide": 1}
    assert "opvolgers" not in uit and "koppelreden" not in store.get(uit["data_key"]).columns
    assert rio == []


def test_een_koppeling_zonder_skdb_kant_vraagt_rio_niets(rio):
    _avans()
    tweede = pd.DataFrame(
        {"STUDIEJAAR": 2025, "INSTELLINGSCODE_ACTUEEL": ["07GR"], "OPLEIDINGSCODE_ACTUEEL": [30020], "AANTAL": 1}
    )
    store.put(_DUO2, tweede, KeyMeta(bron="duo", dataset="p02ho1ejrs", resource=0, periodekolom="STUDIEJAAR"))
    uit, _ = _koppel(_DUO2, _DUO)
    assert "opvolgers" not in uit
    assert rio == []


def test_een_koppeling_op_alleen_croho_vraagt_rio_niets(rio):
    _avans()
    store.put(_SKDB, pd.DataFrame({"croho": [30020, 99999]}), _SKDB_META)
    uit, _ = _koppel(sleutels=["croho"])
    assert "opvolgers" not in uit
    assert rio == []


def test_boven_het_maximum_aan_instellingen_vraagt_de_koppeling_rio_niets(rio):
    brins = [f"{i:02d}XX" for i in range(opvolger.MAX_INSTELLINGEN + 1)]
    store.put(_SKDB, pd.DataFrame({"brin": brins, "croho": 30020}), _SKDB_META)
    store.put(
        _DUO,
        pd.DataFrame(
            {"STUDIEJAAR": 2025, "INSTELLINGSCODE_ACTUEEL": ["25DW"], "OPLEIDINGSCODE_ACTUEEL": [30020], "AANTAL": 1}
        ),
        _DUO_META,
    )
    assert "opvolgers" not in _koppel()[0]
    assert rio == []
