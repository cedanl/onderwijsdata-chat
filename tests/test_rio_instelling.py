"""Eén instelling in RIO: naam → bevoegd gezag → instellingen → vestigingen, in code (#412).

CH-05: drie keer dezelfde vraag over ROC Mondriaan gaf drie antwoorden ("kan ik niet
vaststellen"; 22 vestigingen en 1 instelling; 34 erkenningen, 3 instellingen, 30
vestigingen). De route ligt nu vast; deze tests draaien op een nagebootst RIO, zonder netwerk.
"""

import json
import random
from datetime import date

import httpx
import pytest

from tools import fouten, rio_instelling
from tools.rio import get_rio_data
from tools.rio_instelling import get_rio_instelling

_BASIS = "https://lod.onderwijsregistratie.nl/api/rio/v2/erkenningen"
_PEIL = date(2026, 10, 7)


def _erkenning(code, naam, soort, wet=None, erkenner="OCW", eind=None):
    return {
        "code": code,
        "id": code,
        "volledigeNaam": naam,
        "type": soort,
        "wet": wet,
        "erkenner": erkenner,
        "begindatum": "2000-01-01",
        "einddatum": eind,
    }


def _relatie(van, naar, soort="HIERARCHISCH", eind=None):
    return {
        "soort": soort,
        "begindatum": "2000-01-01",
        "einddatum": eind,
        "vanErkenning": f"{_BASIS}/{van}?datumGeldigOp=2000-01-01",
        "naarErkenning": f"{_BASIS}/{naar}?datumGeldigOp=2000-01-01",
    }


_VESTIGINGEN = [f"27GZ{i:02d}" for i in range(30)]


def _mondriaan() -> tuple[dict, dict]:
    """De registertoestand uit de audit: 1 bevoegd gezag, 3 instellingen, 30 vestigingen."""
    erkenningen = {
        "41171": _erkenning("41171", "Stichting ROC Mondriaan", "BEVOEGD_GEZAG", erkenner="HANDELSREGISTER"),
        "27GZ": _erkenning("27GZ", "ROC Mondriaan", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"),
        "NLQF0262": _erkenning(
            "NLQF0262", "ROC Mondriaan", "ERKENDE_ONDERWIJSINSTELLING", wet="WNLQF", erkenner="NLQF"
        ),
        "1000K0772": _erkenning(
            "1000K0772", " Stichting ROC Mondriaan ", "ERKENDE_ONDERWIJSINSTELLING", erkenner="BRANCHE"
        ),
        **{v: _erkenning(v, "ROC Mondriaan", "ERKENDE_VESTIGING", wet="WEB") for v in _VESTIGINGEN},
    }
    relaties = {
        "41171": [_relatie("41171", c) for c in ("27GZ", "NLQF0262", "1000K0772")],
        "27GZ": [
            _relatie("41171", "27GZ"),
            # Een fusierelatie is geen vestiging.
            _relatie("25PR", "27GZ", soort="OVERGANG_GEDEELTELIJK"),
            *(_relatie("27GZ", v) for v in _VESTIGINGEN),
            # Een opgeheven vestiging telt niet mee.
            _relatie("27GZ", "27GZ99", eind="2015-07-31"),
        ],
        "NLQF0262": [_relatie("41171", "NLQF0262")],
        "1000K0772": [_relatie("41171", "1000K0772")],
    }
    return erkenningen, relaties


class _NepRio:
    """RIO als woordenboek; `schud` levert de lijsten in willekeurige volgorde, zoals een API mag."""

    def __init__(self, erkenningen: dict, relaties: dict, schud: random.Random | None = None):
        self.erkenningen = erkenningen
        self.relaties = relaties
        self.schud = schud
        self.aanroepen: list[tuple] = []

    def _lijst(self, items) -> list:
        items = list(items)
        if self.schud:
            self.schud.shuffle(items)
        return items

    def fetch(self, resource: str, **params):
        self.aanroepen.append((resource, params))
        naam = params["volledigeNaam"].lower()
        return self._lijst(
            e
            for e in self.erkenningen.values()
            if naam in e["volledigeNaam"].lower() and e["type"] == params.get("erkenningtype", e["type"])
        )

    def related(self, resource: str, id: str, sub: str, **params):
        assert not params, "instellingsrelaties weigert paging-parameters (HTTP 400)"
        self.aanroepen.append((f"{resource}/{id}/{sub}", params))
        return self._lijst(self.relaties.get(id, []))

    def get(self, resource: str, id: str, **params):
        self.aanroepen.append((f"{resource}/{id}", params))
        return self.erkenningen[id]


@pytest.fixture
def rio(monkeypatch):
    def installeer(erkenningen=None, relaties=None, schud=None) -> _NepRio:
        if erkenningen is None:
            erkenningen, relaties = _mondriaan()
        nep = _NepRio(erkenningen, relaties or {}, schud)
        monkeypatch.setattr(rio_instelling, "fetch", nep.fetch)
        monkeypatch.setattr(rio_instelling, "get", nep.get)
        monkeypatch.setattr(rio_instelling, "related", nep.related)
        return nep

    return installeer


def _overzicht(naam: str) -> dict:
    return json.loads(get_rio_instelling(naam, peildatum=_PEIL))


def test_de_route_telt_erkenningen_instellingen_en_vestigingen_in_code(rio):
    rio()
    uit = _overzicht("ROC Mondriaan")

    assert uit["bevoegd_gezag"] == {"code": "41171", "naam": "Stichting ROC Mondriaan"}
    assert uit["aantallen"] == {"erkenningen": 34, "instellingen": 3, "vestigingen": 30}
    assert [i["code"] for i in uit["instellingen"]] == ["1000K0772", "27GZ", "NLQF0262"]
    roc = next(i for i in uit["instellingen"] if i["code"] == "27GZ")
    assert roc["vestigingen"] == 30
    assert roc["vestigingscodes"] == sorted(_VESTIGINGEN)
    # Namen zoals de gebruiker ze leest, zonder de spaties uit het register.
    assert next(i for i in uit["instellingen"] if i["code"] == "1000K0772")["naam"] == "Stichting ROC Mondriaan"
    assert uit["peildatum"] == "2026-10-07"


def test_vijf_runs_geven_vijf_identieke_uitkomsten_ook_als_rio_de_volgorde_husselt(rio):
    """Klaar-als van #412: dezelfde vraag geeft hetzelfde antwoord, tot op de byte."""
    uitkomsten = set()
    for seed in range(5):
        rio(schud=random.Random(seed))
        uitkomsten.add(get_rio_instelling("ROC Mondriaan", peildatum=_PEIL))

    assert len(uitkomsten) == 1
    assert json.loads(uitkomsten.pop())["aantallen"] == {"erkenningen": 34, "instellingen": 3, "vestigingen": 30}


def test_een_instellingsnaam_zonder_bestuursnaam_vindt_het_bestuur_via_de_instelling(rio):
    erkenningen, relaties = _mondriaan()
    erkenningen["41171"]["volledigeNaam"] = "Stichting Middelbaar Beroepsonderwijs Haaglanden"
    nep = rio(erkenningen, relaties)

    uit = _overzicht("ROC Mondriaan")

    assert uit["bevoegd_gezag"]["code"] == "41171"
    assert uit["aantallen"]["instellingen"] == 3
    assert ("erkenningen", {"volledigeNaam": "ROC Mondriaan", "erkenningtype": "ERKENDE_ONDERWIJSINSTELLING",
                            "datumGeldigOp": "2026-10-07"}) in nep.aanroepen  # fmt: skip


def test_meerdere_besturen_geven_kandidaten_en_geen_telling(rio):
    erkenningen, relaties = _mondriaan()
    erkenningen["41843"] = _erkenning("41843", "Stg. Primair onderw. Mondriaan Abcoude", "BEVOEGD_GEZAG")
    rio(erkenningen, relaties)

    uit = _overzicht("Mondriaan")

    assert uit["status"] == "meerdere"
    assert "aantallen" not in uit
    assert uit["kandidaten"] == [
        {"code": "41171", "naam": "Stichting ROC Mondriaan"},
        {"code": "41843", "naam": "Stg. Primair onderw. Mondriaan Abcoude"},
    ]


def test_een_exacte_bestuursnaam_kiest_uit_meerdere(rio):
    erkenningen, relaties = _mondriaan()
    erkenningen["41843"] = _erkenning("41843", "Stichting ROC Mondriaan Oost", "BEVOEGD_GEZAG")
    rio(erkenningen, relaties)

    assert _overzicht("stichting roc  mondriaan")["bevoegd_gezag"]["code"] == "41171"


def test_onbekende_naam_zegt_dat_rio_hem_niet_kent(rio):
    rio()
    uit = _overzicht("Hogeschool Nergenshuizen")

    assert uit["status"] == "niet_gevonden"
    assert "aantallen" not in uit


def test_een_bestuur_zonder_mbo_of_ho_valt_buiten_scope(rio):
    erkenningen = {
        "41843": _erkenning("41843", "Stg. Primair onderw. Abcoude", "BEVOEGD_GEZAG"),
        "05AB": _erkenning("05AB", "Basisschool Abcoude", "ERKENDE_ONDERWIJSINSTELLING", wet="WPO"),
    }
    rio(erkenningen, {"41843": [_relatie("41843", "05AB")], "05AB": []})

    uit = _overzicht("Abcoude")

    assert uit["buiten_scope"] is True and uit["opvraagbaar"] is False
    assert "aantallen" not in uit


def test_po_vo_instellingen_onder_een_mbo_bestuur_tellen_niet_mee(rio):
    erkenningen, relaties = _mondriaan()
    erkenningen["20VO"] = _erkenning("20VO", "Mondriaan College", "ERKENDE_ONDERWIJSINSTELLING", wet="WVO")
    relaties["41171"].append(_relatie("41171", "20VO"))
    relaties["20VO"] = [_relatie("20VO", "20VO00")]
    rio(erkenningen, relaties)

    uit = _overzicht("ROC Mondriaan")

    assert uit["aantallen"] == {"erkenningen": 34, "instellingen": 3, "vestigingen": 30}
    assert uit["buiten_scope_weggelaten"] == ["20VO"]


def test_een_instelling_uit_bedrijf_telt_niet_mee(rio):
    erkenningen, relaties = _mondriaan()
    erkenningen["NLQF0262"]["uitBedrijfdatum"] = "2026-01-01"
    rio(erkenningen, relaties)

    uit = _overzicht("ROC Mondriaan")

    assert uit["aantallen"] == {"erkenningen": 33, "instellingen": 2, "vestigingen": 30}
    assert "NLQF0262" not in [i["code"] for i in uit["instellingen"]]


def test_een_bronfout_wordt_een_gecodeerde_fout(monkeypatch):
    def kapot(resource, **params):
        raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(rio_instelling, "fetch", kapot)
    uit = get_rio_instelling("ROC Mondriaan", peildatum=_PEIL)

    assert fouten.code(uit) == "bron_onbereikbaar"
    assert "geen netwerk" not in uit


def test_get_rio_data_op_erkenningen_verwijst_naar_de_vaste_route(monkeypatch):
    """De vrije route (erkenningen zoeken en zelf tellen) gaf per run een ander getal (#412), en
    het register is niet per sector te selecteren (CH-03): de chat haalt het niet op."""
    opgehaald = []
    monkeypatch.setattr("tools.rio.fetch", lambda resource, **params: opgehaald.append(resource) or [])

    uit = json.loads(get_rio_data("erkenningen", {"volledigeNaam": "ROC Mondriaan"}))

    assert not opgehaald
    assert uit["buiten_scope"] is True
    assert "get_rio_instelling" in uit["melding"]
