"""Opvolgers en voorgangers langs de overgangen in RIO v3 (#728), zonder netwerk.

De fixture bevriest wat RIO op 05-11-2026 gaf voor drie fusies uit het onderzoek van 04-11: Friesland College (25LG)
→ Firda (08PG) per 1-8-2023, volledig; Regio College (25RA) → Talland College (25PT) per 1-8-2024, volledig;
Helicon Opleidingen (26CC) en CITAVERDE (21CS) → Yuverta (01OE) per 1-8-2021, gedeeltelijk.
"""

import datetime as dt

import httpx
import pytest
import riodata
from riodata import overgangen
from riodata.overgangen import Stap, opvolgers, voorgangers

_BASIS = "https://lod.onderwijsregistratie.nl/api/rio/v3/erkenningen"


def _relatie(van, naar, soort, begin, eind=None):
    """Een instellingsrelatie zoals RIO v3 hem geeft: de codes als veld én als link."""
    return {
        "soort": soort,
        "begindatum": begin,
        "einddatum": eind,
        "vanErkenningId": van,
        "naarErkenningId": naar,
        "vanErkenningType": "ERKENDE_ONDERWIJSINSTELLING",
        "naarErkenningType": "ERKENDE_ONDERWIJSINSTELLING",
        "_links": {
            "van": {"href": f"{_BASIS}/{van}?datumGeldigOp={begin}"},
            "naar": {"href": f"{_BASIS}/{naar}?datumGeldigOp={begin}"},
        },
    }


def _volledig(van, naar, begin):
    return _relatie(van, naar, "OVERGANG_VOLLEDIG", begin)


def _gedeeltelijk(van, naar, begin):
    return _relatie(van, naar, "OVERGANG_GEDEELTELIJK", begin)


_NAMEN = {
    "25LG": "Regionaal Opleidingen Centrum Friesland College",
    "08PG": "Firda",
    "18XX": "ROC Friese Poort",
    "25RA": "Regio College voor Beroepsonderwijs en Educatie Zaanstreek-Waterland",
    "25PT": "Talland College",
    "26CC": "Helicon Opleidingen",
    "21CS": "CITAVERDE College",
    "01OE": "Yuverta",
    "14JV": "Helicon voorganger",
}

# Per erkenning de relaties uit RIO, ingekort tot de overgangen en één hiërarchische relatie.
_RELATIES = {
    "25LG": [
        _relatie("30932", "25LG", "HIERARCHISCH", "2023-01-01"),
        _volledig("25LG", "08PG", "2023-08-01"),
    ],
    "08PG": [
        _gedeeltelijk("18XX", "08PG", "2015-01-01"),
        _relatie("30932", "08PG", "HIERARCHISCH", "1989-06-02"),
        _volledig("25LG", "08PG", "2023-08-01"),
    ],
    "25RA": [_volledig("25RA", "25PT", "2024-08-01")],
    "25PT": [_volledig("25RA", "25PT", "2024-08-01")],
    "26CC": [
        _gedeeltelijk("14JV", "26CC", "1998-01-01"),
        _gedeeltelijk("26CC", "01OE", "2021-08-01"),
    ],
    "21CS": [_gedeeltelijk("21CS", "01OE", "2021-08-01")],
    "01OE": [
        _gedeeltelijk("21CS", "01OE", "2021-08-01"),
        _gedeeltelijk("26CC", "01OE", "2021-08-01"),
    ],
}


class _NepRio:
    """RIO als woordenboek; onthoudt elke aanroep met haar parameters."""

    def __init__(self, relaties=None, namen=None, wetten=None):
        self.relaties = _RELATIES if relaties is None else relaties
        self.namen = _NAMEN if namen is None else namen
        self.wetten = wetten or {}
        self.aanroepen: list[tuple[str, dict]] = []

    def related(self, resource, id, sub, **params):
        self.aanroepen.append((f"{resource}/{id}/{sub}", params))
        return list(self.relaties.get(id, []))

    def get(self, resource, id, **params):
        self.aanroepen.append((f"{resource}/{id}", params))
        if id not in self.namen:
            verzoek = httpx.Request("GET", f"{_BASIS}/{id}")
            raise httpx.HTTPStatusError("404", request=verzoek, response=httpx.Response(404, request=verzoek))
        return {
            "code": id,
            "volledigeNaam": f" {self.namen[id]} ",
            "wet": self.wetten.get((id, params.get("datumGeldigOp"))),
        }


@pytest.fixture
def rio(monkeypatch):
    def installeer(**kwargs) -> _NepRio:
        nep = _NepRio(**kwargs)
        monkeypatch.setattr(overgangen, "related", nep.related)
        monkeypatch.setattr(overgangen, "get", nep.get)
        return nep

    return installeer


def test_friesland_college_is_opgegaan_in_firda(rio):
    rio()
    assert opvolgers("25LG", "2026-11-05") == [
        Stap(code="08PG", naam="Firda", overgang="volledig", datum="2023-08-01", via="25LG")
    ]


def test_een_gedeeltelijke_overgang_heet_gedeeltelijk(rio):
    rio()
    assert opvolgers("26CC", dt.date(2026, 11, 5)) == [
        Stap(code="01OE", naam="Yuverta", overgang="gedeeltelijk", datum="2021-08-01", via="26CC")
    ]


def test_voor_de_overgang_is_er_nog_geen_opvolger(rio):
    rio()
    assert opvolgers("25LG", "2022-10-01") == []


def test_een_huidige_instelling_heeft_geen_opvolger(rio):
    rio()
    assert opvolgers("08PG", "2026-11-05") == []


def test_elke_aanroep_geeft_datum_geldig_op_mee(rio):
    nep = rio()
    opvolgers("25LG", "2026-11-05")
    voorgangers("08PG", "2020-01-01", peildatum="2026-11-05")

    assert nep.aanroepen
    assert all("datumGeldigOp" in params for _, params in nep.aanroepen)
    assert ("erkenningen/25LG/instellingsrelaties", {"datumGeldigOp": "2026-11-05"}) in nep.aanroepen


def test_zonder_peildatum_geldt_vandaag(rio):
    nep = rio()
    opvolgers("25LG")
    assert nep.aanroepen[0][1] == {"datumGeldigOp": dt.date.today().isoformat()}


def test_voorgangers_van_firda_sinds_2021(rio):
    rio()
    assert voorgangers("08PG", "2021-10-01", peildatum="2026-11-05") == [
        Stap(
            code="25LG",
            naam="Regionaal Opleidingen Centrum Friesland College",
            overgang="volledig",
            datum="2023-08-01",
            via="08PG",
        )
    ]


def test_de_naam_van_een_voorganger_komt_van_de_dag_voor_de_overgang(rio):
    nep = rio()
    voorgangers("08PG", "2021-10-01", peildatum="2026-11-05")
    assert ("erkenningen/25LG", {"datumGeldigOp": "2023-07-31"}) in nep.aanroepen


def test_de_wet_van_een_voorganger_komt_uit_dezelfde_aanroep_als_de_naam(rio):
    """Een vo-school (WVO) kan opgaan in een mbo-instelling; de aanroeper ziet dat aan `wet` (#937)."""
    nep = rio(wetten={("25LG", "2023-07-31"): "WEB"})
    (stap,) = voorgangers("08PG", "2021-10-01", peildatum="2026-11-05")
    assert stap.wet == "WEB"
    assert [a for a, _ in nep.aanroepen].count("erkenningen/25LG") == 1


def test_zonder_wet_in_rio_is_de_wet_none(rio):
    rio()
    assert voorgangers("08PG", "2021-10-01", peildatum="2026-11-05")[0].wet is None
    assert opvolgers("25LG", "2026-11-05")[0].wet is None


def test_sinds_laat_oudere_overgangen_weg(rio):
    rio()
    assert [s.code for s in voorgangers("08PG", "2010-01-01", peildatum="2026-11-05")] == ["18XX", "25LG"]
    assert [s.code for s in voorgangers("08PG", "2023-08-02", peildatum="2026-11-05")] == []


def test_voorgangers_van_yuverta_zijn_beide_gedeeltelijk(rio):
    rio()
    stappen = voorgangers("01OE", "2021-01-01", peildatum="2026-11-05")
    assert [(s.code, s.overgang) for s in stappen] == [("21CS", "gedeeltelijk"), ("26CC", "gedeeltelijk")]


def test_een_keten_wordt_tot_het_eind_gevolgd(rio):
    """A → B → C: de opvolgers van A zijn B en C, de voorgangers van C zijn B en A, elk met de stap ertussen."""
    relaties = {
        "11AA": [_volledig("11AA", "22BB", "2019-08-01")],
        "22BB": [_volledig("11AA", "22BB", "2019-08-01"), _gedeeltelijk("22BB", "33CC", "2023-08-01")],
        "33CC": [_gedeeltelijk("22BB", "33CC", "2023-08-01")],
    }
    rio(relaties=relaties, namen={"11AA": "A", "22BB": "B", "33CC": "C"})

    assert opvolgers("11AA", "2026-01-01") == [
        Stap("22BB", "B", "volledig", "2019-08-01", via="11AA"),
        Stap("33CC", "C", "gedeeltelijk", "2023-08-01", via="22BB"),
    ]
    assert voorgangers("33CC", "2010-01-01", peildatum="2026-01-01") == [
        Stap("11AA", "A", "volledig", "2019-08-01", via="22BB"),
        Stap("22BB", "B", "gedeeltelijk", "2023-08-01", via="33CC"),
    ]
    # Een peildatum tussen de twee stappen kent alleen de eerste.
    assert [s.code for s in opvolgers("11AA", "2020-01-01")] == ["22BB"]


def test_een_cyclus_stopt_en_noemt_de_start_niet_als_opvolger(rio):
    relaties = {
        "11AA": [_volledig("11AA", "22BB", "2019-08-01"), _volledig("22BB", "11AA", "2021-08-01")],
        "22BB": [_volledig("11AA", "22BB", "2019-08-01"), _volledig("22BB", "11AA", "2021-08-01")],
    }
    nep = rio(relaties=relaties, namen={"11AA": "A", "22BB": "B"})

    assert [s.code for s in opvolgers("11AA", "2026-01-01")] == ["22BB"]
    assert [s.code for s in voorgangers("11AA", "2000-01-01", peildatum="2026-01-01")] == ["22BB"]
    assert len(nep.aanroepen) < 10


def test_een_ontbrekende_naam_is_none_en_geen_fout(rio):
    rio(namen={})
    assert opvolgers("25LG", "2026-11-05")[0].naam is None


def test_hierarchische_relaties_tellen_niet(rio):
    rio(relaties={"25LG": [_relatie("30932", "25LG", "HIERARCHISCH", "2023-01-01")]})
    assert opvolgers("25LG", "2026-11-05") == []
    assert voorgangers("25LG", peildatum="2026-11-05") == []


def test_een_relatie_met_alleen_links_werkt_ook(rio):
    zonder_velden = {k: v for k, v in _volledig("25LG", "08PG", "2023-08-01").items() if not k.endswith("ErkenningId")}
    rio(relaties={"25LG": [zonder_velden]})
    assert [s.code for s in opvolgers("25LG", "2026-11-05")] == ["08PG"]


def test_een_bronfout_gaat_naar_de_aanroeper(monkeypatch):
    def kapot(*args, **kwargs):
        raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(overgangen, "related", kapot)
    with pytest.raises(httpx.ConnectError):
        voorgangers("08PG", "2021-10-01")


def test_een_bestuursnummer_volgt_dezelfde_overgangen(rio):
    """Besturen fuseren ook (#725): RIO geeft hun overgangen in dezelfde instellingsrelaties, met het bestuursnummer.

    Op 05-11-2026: Stichting Regio College (40864) volledig in Stichting Talland College (40877) per 2024-01-01, en het
    bestuur van Friesland College (40295) in dat van Firda (30932) per 2023-01-01.
    """
    bestuur = {"vanErkenningType": "BEVOEGD_GEZAG", "naarErkenningType": "BEVOEGD_GEZAG"}
    regio = {**_volledig("40864", "40877", "2024-01-01"), **bestuur}
    friesland = {**_volledig("40295", "30932", "2023-01-01"), **bestuur}
    rio(
        relaties={"40864": [regio], "40877": [regio], "40295": [friesland], "30932": [friesland]},
        namen={
            "40864": "Stichting Regio College voor Beroepsonderwijs en Educatie Zaanstreek Waterland",
            "40877": "Stichting Talland College",
            "40295": "Stg. Alg. Voortgez. Onderwijs, Beroepsonderwijs en Volw.educ",
            "30932": "Stg. Beroepsonderw./ Volw.educ en AVO in Friesland en Flevoland",
        },
    )

    assert opvolgers("40864", "2026-11-05") == [
        Stap("40877", "Stichting Talland College", "volledig", "2024-01-01", via="40864")
    ]
    assert [s.code for s in voorgangers("40877", "2020-01-01", peildatum="2026-11-05")] == ["40864"]
    assert [s.code for s in opvolgers("40295", "2026-11-05")] == ["30932"]


def test_publieke_api():
    assert riodata.opvolgers is opvolgers
    assert riodata.voorgangers is voorgangers
    assert riodata.Stap is Stap
