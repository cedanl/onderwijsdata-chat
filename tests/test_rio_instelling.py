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
from riodata import overgangen

from agent.telling import telling_blok
from tools import fouten, rio_instelling
from tools.rio import get_rio_data
from tools.rio_instelling import get_rio_instelling

_BASIS = "https://lod.onderwijsregistratie.nl/api/rio/v3/erkenningen"
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


def _relatie(van, naar, soort="HIERARCHISCH", eind=None, begin="2000-01-01"):
    """Een instellingsrelatie zoals RIO v3 hem geeft: de codes als veld én als link."""
    return {
        "soort": soort,
        "begindatum": begin,
        "einddatum": eind,
        "vanErkenningId": van,
        "naarErkenningId": naar,
        "vanErkenningType": "ERKENDE_ONDERWIJSINSTELLING",
        "naarErkenningType": "ERKENDE_VESTIGING",
        "_links": {
            "van": {"href": f"{_BASIS}/{van}?datumGeldigOp=2000-01-01"},
            "naar": {"href": f"{_BASIS}/{naar}?datumGeldigOp=2000-01-01"},
        },
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
            if naam in e["volledigeNaam"].lower() and e["type"] == params.get("type", e["type"])
        )

    def related(self, resource: str, id: str, sub: str, **params):
        assert set(params) <= {"datumGeldigOp"}, "instellingsrelaties weigert paging-parameters (HTTP 400)"
        self.aanroepen.append((f"{resource}/{id}/{sub}", params))
        # Zoals RIO: zonder datumGeldigOp alleen de relaties van vandaag (#728).
        peil = params.get("datumGeldigOp") or date.today().isoformat()
        return self._lijst(
            r
            for r in self.relaties.get(id, [])
            if r["begindatum"] <= peil and (not r["einddatum"] or r["einddatum"] > peil)
        )

    def get(self, resource: str, id: str, **params):
        self.aanroepen.append((f"{resource}/{id}", params))
        if id not in self.erkenningen:
            verzoek = httpx.Request("GET", f"{_BASIS}/{id}")
            raise httpx.HTTPStatusError("404", request=verzoek, response=httpx.Response(404, request=verzoek))
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
        # De overgangen (riodata.opvolgers) lezen hetzelfde nagebootste RIO.
        monkeypatch.setattr(overgangen, "get", nep.get)
        monkeypatch.setattr(overgangen, "related", nep.related)
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
    assert ("erkenningen", {"volledigeNaam": "ROC Mondriaan", "type": "ERKENDE_ONDERWIJSINSTELLING",
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


# --- CH-29: de relatie én het doelobject op de peildatum ---


def test_een_vestiging_uit_bedrijf_achter_een_geldige_relatie_telt_niet(rio):
    """CH-29: _onder() telde relaties zonder de vestiging zelf te lezen; 'in bedrijf' was niet afgedwongen."""
    erkenningen, relaties = _mondriaan()
    erkenningen[_VESTIGINGEN[0]]["uitBedrijfdatum"] = "2020-01-01"
    rio(erkenningen, relaties)

    uit = _overzicht("ROC Mondriaan")

    assert uit["aantallen"] == {"erkenningen": 33, "instellingen": 3, "vestigingen": 29}
    roc = next(i for i in uit["instellingen"] if i["code"] == "27GZ")
    assert _VESTIGINGEN[0] not in roc["vestigingscodes"]


def test_een_relatie_naar_een_ander_type_is_geen_vestiging(rio):
    erkenningen, relaties = _mondriaan()
    erkenningen[_VESTIGINGEN[1]]["type"] = "ERKENDE_SAMENWERKING"
    rio(erkenningen, relaties)

    assert _overzicht("ROC Mondriaan")["aantallen"]["vestigingen"] == 29


def test_een_ontbrekend_doelobject_wordt_genoemd_en_niet_geteld(rio):
    erkenningen, relaties = _mondriaan()
    del erkenningen[_VESTIGINGEN[2]]
    rio(erkenningen, relaties)

    uit = _overzicht("ROC Mondriaan")

    assert uit["aantallen"]["vestigingen"] == 29
    assert uit["niet_te_lezen"] == [_VESTIGINGEN[2]]


def test_andere_erkenningen_onder_het_bestuur_worden_genoemd(rio):
    """Fontys: 'RIO telt 23 erkenningen' verzweeg twee erkende onderwijsondersteuners."""
    erkenningen, relaties = _mondriaan()
    for code in ("OO1", "OO2"):
        erkenningen[code] = _erkenning(code, "Ondersteuner", "ERKENDE_ONDERWIJSONDERSTEUNER")
        relaties["41171"].append(_relatie("41171", code))
    rio(erkenningen, relaties)

    uit = _overzicht("ROC Mondriaan")

    assert uit["aantallen"]["erkenningen"] == 34
    assert uit["niet_meegeteld"] == {"ERKENDE_ONDERWIJSONDERSTEUNER": 2}


def test_een_relatie_met_alleen_links_werkt_ook(rio):
    """Terugval: zonder `vanErkenningId`/`naarErkenningId` komt de code uit `_links` (v2-vorm, en wat v3 ook meestuurt)."""
    erkenningen, relaties = _mondriaan()
    for lijst in relaties.values():
        for r in lijst:
            del r["vanErkenningId"], r["naarErkenningId"]
    rio(erkenningen, relaties)
    uit = _overzicht("ROC Mondriaan")
    assert uit["aantallen"]["vestigingen"] == 30


def test_de_route_zoekt_met_het_v3_typefilter(rio):
    nep = rio()
    _overzicht("ROC Mondriaan")
    for resource, params in nep.aanroepen:
        if resource == "erkenningen":
            assert "type" in params and "erkenningtype" not in params


# --- #728: een opgeheven instelling zegt waarin ze opging; een peildatum in het verleden leest de relaties van toen ---


def _uit(erkenning: dict, uit: str) -> dict:
    return {**erkenning, "uitBedrijfdatum": uit}


def _friesland() -> tuple[dict, dict]:
    """Friesland College (25LG) ging op 2023-08-01 volledig op in Firda (08PG); RIO op 05-11-2026, ingekort."""
    bestuur_oud = "Stg. Alg. Voortgez. Onderwijs, Beroepsonderwijs en Volw.educ"
    erkenningen = {
        "40295": _uit(_erkenning("40295", bestuur_oud, "BEVOEGD_GEZAG"), "2023-01-01"),
        "30932": _erkenning(
            "30932", "Stg. Beroepsonderw./ Volw.educ en AVO in Friesland en Flevoland", "BEVOEGD_GEZAG"
        ),
        "25LG": _uit(
            _erkenning("25LG", "Regionaal Opleidingen Centrum Friesland College", "ERKENDE_ONDERWIJSINSTELLING", "WEB"),
            "2023-08-01",
        ),
        "1000K0155": _erkenning("1000K0155", "Friesland College", "ERKENDE_ONDERWIJSINSTELLING"),
        "08PG": _erkenning("08PG", "Firda", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"),
        "25LG00": _uit(_erkenning("25LG00", "Friesland College", "ERKENDE_VESTIGING", wet="WEB"), "2023-08-01"),
        "08PG00": _erkenning("08PG00", "Firda", "ERKENDE_VESTIGING", wet="WEB"),
    }
    oud_naar_25lg = _relatie("40295", "25LG", begin="1996-01-01", eind="2023-01-01")
    nieuw_naar_25lg = _relatie("30932", "25LG", begin="2023-01-01")
    fusie = _relatie("25LG", "08PG", soort="OVERGANG_VOLLEDIG", begin="2023-08-01")
    naar_k0155 = _relatie("40295", "1000K0155", begin="2021-12-15")
    relaties = {
        "40295": [oud_naar_25lg, naar_k0155],
        "30932": [nieuw_naar_25lg, _relatie("30932", "08PG", begin="1989-06-02")],
        "25LG": [oud_naar_25lg, nieuw_naar_25lg, fusie, _relatie("25LG", "25LG00", begin="1996-01-01")],
        "1000K0155": [naar_k0155],
        "08PG": [_relatie("30932", "08PG", begin="1989-06-02"), fusie, _relatie("08PG", "08PG00")],
    }
    return erkenningen, relaties


_FIRDA_ZIN = (
    "Regionaal Opleidingen Centrum Friesland College (25LG) is per 1 augustus 2023 opgegaan in Firda (08PG) "
    "(volledige overgang)."
)


def _vandaag(naam: str) -> dict:
    return json.loads(get_rio_instelling(naam, peildatum=date(2026, 11, 5)))


def test_een_oude_naam_zegt_waarin_de_instelling_opging(rio):
    rio(*_friesland())
    uit = _vandaag("Friesland College")

    assert uit["status"] == "opgegaan"
    assert "aantallen" not in uit
    assert uit["fusiemelding"] == _FIRDA_ZIN
    assert uit["melding"].startswith(_FIRDA_ZIN)
    (opgegaan,) = uit["opgegaan"]
    assert opgegaan["code"] == "25LG"
    assert opgegaan["opgegaan_in"] == [
        {"code": "08PG", "naam": "Firda", "overgang": "volledig", "datum": "2023-08-01", "via": "25LG"}
    ]


def test_een_oude_brin_zegt_het_ook(rio):
    rio(*_friesland())
    uit = _vandaag("25lg")
    assert uit["status"] == "opgegaan"
    assert uit["fusiemelding"] == _FIRDA_ZIN


def test_de_fusiezin_staat_vast_onder_het_antwoord(rio):
    """Het model kiest niets: de zin komt uit de code in het Telling-blok."""
    rio(*_friesland())
    blok = telling_blok([get_rio_instelling("Friesland College", peildatum=date(2026, 11, 5))])
    assert f"- {_FIRDA_ZIN}" in blok


def test_een_brin_van_een_actieve_instelling_geeft_het_overzicht(rio):
    rio()
    uit = _overzicht("27gz")
    assert uit["bevoegd_gezag"]["code"] == "41171"
    assert "opgegaan" not in uit


def test_een_onbekende_brin_is_niet_gevonden(rio):
    rio()
    uit = _overzicht("99ZZ")
    assert uit["status"] == "niet_gevonden"
    assert "99ZZ" in uit["melding"]


def test_een_peildatum_in_het_verleden_leest_de_relaties_van_toen(rio):
    """Bijvangst #728: zonder datumGeldigOp kwam bestuur 40295 zonder mbo-instelling terug."""
    nep = rio(*_friesland())
    uit = json.loads(get_rio_instelling("Friesland College", peildatum=date(2022, 10, 1)))

    assert uit["bevoegd_gezag"]["code"] == "40295"
    assert "25LG" in [i["code"] for i in uit["instellingen"]]
    assert "opgegaan" not in uit  # op die dag bestond Friesland College nog
    relaties = [p for r, p in nep.aanroepen if r.endswith("/instellingsrelaties")]
    assert relaties and all(p == {"datumGeldigOp": "2022-10-01"} for p in relaties)


def test_helicon_is_gedeeltelijk_opgegaan_in_yuverta(rio):
    erkenningen = {
        "31142": _uit(_erkenning("31142", "Stichting Helicon Opleidingen", "BEVOEGD_GEZAG"), "2021-08-01"),
        "26CC": _uit(_erkenning("26CC", "Helicon Opleidingen", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"), "2021-08-01"),
        "01OE": _erkenning("01OE", "Yuverta", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"),
    }
    fusie = _relatie("26CC", "01OE", soort="OVERGANG_GEDEELTELIJK", begin="2021-08-01")
    rio(erkenningen, {"26CC": [fusie], "01OE": [fusie]})

    uit = _vandaag("Helicon Opleidingen")

    assert uit["status"] == "opgegaan"
    assert uit["fusiemelding"] == (
        "Helicon Opleidingen (26CC) is per 1 augustus 2021 opgegaan in Yuverta (01OE) (gedeeltelijke overgang)."
    )


def test_regio_college_geeft_talland_en_zegt_dat_het_roc_erin_opging(rio):
    """De naam vindt een actieve educatie-instelling onder Talland; het roc Regio College (25RA) ging in 2024 op in
    Talland College. Eerder kwam het overzicht van Talland zonder melding."""
    erkenningen = {
        "40864": _uit(_erkenning("40864", "Stichting Regio College", "BEVOEGD_GEZAG"), "2024-01-01"),
        "40877": _erkenning("40877", "Stichting Talland College", "BEVOEGD_GEZAG"),
        "25RA": _uit(
            _erkenning(
                "25RA",
                "Regio College voor Beroepsonderwijs en Educatie Zaanstreek-Waterland",
                "ERKENDE_ONDERWIJSINSTELLING",
                wet="WEB",
            ),
            "2024-08-01",
        ),
        "30TC": _erkenning("30TC", "Regio College", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"),
        "25PT": _erkenning("25PT", "Talland College", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"),
    }
    fusie = _relatie("25RA", "25PT", soort="OVERGANG_VOLLEDIG", begin="2024-08-01")
    relaties = {
        "40877": [_relatie("40877", c, begin="2024-01-01") for c in ("30TC", "25RA")] + [_relatie("40877", "25PT")],
        "30TC": [_relatie("40877", "30TC", begin="2024-01-01")],
        "25RA": [_relatie("40877", "25RA", begin="2024-01-01"), fusie],
        "25PT": [_relatie("40877", "25PT"), fusie],
    }
    rio(erkenningen, relaties)

    uit = _vandaag("Regio College")

    assert uit["bevoegd_gezag"]["code"] == "40877"
    assert [i["code"] for i in uit["instellingen"]] == ["25PT", "30TC"]
    assert uit["fusiemelding"] == (
        "Regio College voor Beroepsonderwijs en Educatie Zaanstreek-Waterland (25RA) is per 1 augustus 2024 "
        "opgegaan in Talland College (25PT) (volledige overgang)."
    )


def test_een_opgeheven_vo_school_krijgt_geen_fusiemelding(rio):
    """Scope (#355): een vo-instelling (WVO) noemt de chat niet, ook niet als voorganger."""
    erkenningen = {
        "02EX": _uit(_erkenning("02EX", "Morgen College", "ERKENDE_ONDERWIJSINSTELLING", wet="WVO"), "2025-08-01"),
        "01AA": _erkenning("01AA", "Stichting Landstede", "ERKENDE_ONDERWIJSINSTELLING", wet="WEB"),
    }
    fusie = _relatie("02EX", "01AA", soort="OVERGANG_VOLLEDIG", begin="2025-08-01")
    nep = rio(erkenningen, {"02EX": [fusie]})

    uit = _vandaag("Morgen College")

    assert uit["status"] == "niet_gevonden"
    assert "fusiemelding" not in uit
    assert not any(r.endswith("/instellingsrelaties") for r, _ in nep.aanroepen)
