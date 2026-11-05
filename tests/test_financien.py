"""get_bestuursfinancien: de financiële positie van een bestuur uit DUO's verantwoording uit XBRL (#935, besluit #725).

Zonder netwerk: de eenheden zijn synthetisch en gaan als `Financien` de tool in; het pakket rekent er zelf mee
(sectorcijfer, signaleringen). ROC Midden Nederland (40597) heeft in 2025 solvabiliteit I 0,69, zoals in de echte
editie 2021-2025; het sectorcijfer is het gewogen cijfer van de Inspectie over de acht mbo-eenheden (0,64), niet de
mediaan (0,59). De pakkettest bewijst hetzelfde met de mediaan 0,573 uit de verkenning.
"""

import json

import httpx
import pandas as pd
import pytest
from onderwijsbronnen import Bestuurssleutel
from onderwijsbronnen.duo import financien
from onderwijsbronnen.rio import Stap

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from core import actualiteit
from scripts import bronping
from tools import catalog, fouten, fusies, snippet
from tools import financien as tool
from tools.duo import get_duo_data
from tools.schemas import TOOL_GET_BESTUURSFINANCIEN

_M = 1_000_000
_EDITIE = financien.Editie(
    eerste_jaar=2021,
    laatste_jaar=2025,
    peildatum="31 december 2025",
    publicatiedatum="15 september 2026",
    urls={o: f"https://duo.nl/open_onderwijsdata/images/{o}.xlsx" for o in financien.ONDERDELEN},
)


def _jaar(sleutel, naam, sector, groep, jaar, variant, ev, vz, tp, va, ks, baten, fb, res, rijk, wp=None, leeg=()):
    """Eén bestuursjaar met kengetallen die bij de posten horen (posten in miljoen euro)."""
    waarden = {
        "eigen_vermogen": ev * _M,
        "voorzieningen": None if vz is None else vz * _M,
        "totaal_passiva": tp * _M,
        "vlottende_activa": va * _M,
        "kortlopende_schulden": ks * _M,
        "baten": baten * _M,
        "financiele_baten": None if fb is None else fb * _M,
        "resultaat": res * _M,
        "rijksbijdragen": rijk * _M,
        "werkplaatsfunctie": None if wp is None else wp * _M,
        "solvabiliteit_1": ev / tp,
        "solvabiliteit_2": (ev + (vz or 0)) / tp,
        "liquiditeit": va / ks,
        "rentabiliteit": res / (baten + (fb or 0)),
    }
    waarden.update(dict.fromkeys(leeg))
    bestuur = Bestuurssleutel.parse(sleutel)
    assert bestuur is not None
    return financien.Bestuursjaar(bestuur, naam, sector, groep, jaar, variant, waarden)


_RIJEN = (
    _jaar("40597", "Stichting ROC Midden Nederland", "MBO", "ROC", 2024, "geconsolideerd", 68, 6, 100, 35, 10, 200, 0.5, 6.5, 187),
    _jaar("40597", "Stichting ROC Midden Nederland", "MBO", "ROC", 2025, "geconsolideerd", 69, 6, 100, 32, 10, 213, 0.4, 4.3, 197.021),
    _jaar("40001", "Vakcollege Een", "MBO", "BER", 2025, "enkelvoudig", 57.3, 2, 100, 12, 8, 60, None, -0.6, 50),
    _jaar("40002", "ROC Krap", "MBO", "ROC", 2025, "enkelvoudig", 50, 1, 100, 6, 10, 20, 0, 0.2, 18),
    _jaar("40833-25PZ", "ROC van Amsterdam", "MBO", "ROC", 2024, "geconsolideerd", 290, 20, 500, 120, 100, 400, 1, 3, 350),
    _jaar("40833-25PZ", "ROC van Amsterdam", "MBO", "ROC", 2025, "enkelvoudig", 300, 20, 500, 130, 100, 410, 1, 4, 360),
    _jaar("40833-25LR", "ROC van Flevoland", "MBO", "ROC", 2025, "enkelvoudig", 10, None, 20, 5, 4, 30, None, 0.3, 25),
    _jaar("40833-30RM", "ROC TOP", "MBO", "ROC", 2025, "enkelvoudig", 0.05, None, 0.117, 0.1, 0.05, 2.5, None, 0, 2.4),
    _jaar("40687", "Stichting Aeres Groep", "MBO", "BER", 2025, "geconsolideerd", 70, 3, 90, 20, 15, 140, None, 1, 120),
    _jaar("30000", "Hogeschool Dun", "HBO", "HBO", 2025, "enkelvoudig", 2, 0.5, 10, 3, 5, 11, None, -0.5, 9, leeg=("rentabiliteit",)),
    _jaar("30932", "Stg. Firda", "MBO", "ROC", 2024, "geconsolideerd", 60, 5, 120, 30, 20, 150, None, 2, 140),
    _jaar("30932", "Stg. Firda", "MBO", "ROC", 2025, "geconsolideerd", 100, 5, 120, 30, 20, 155, None, 2, 145),
    _jaar("40295", "Stg Alg VO BO Volw Eduk", "MBO", "ROC", 2024, "enkelvoudig", 10, 1, 30, 8, 6, 50, None, 0.1, 45),
    _jaar("00009", "Universiteit Utrecht", "WO", "UNIV", 2025, "geconsolideerd", 600, 50, 1500, 500, 600, 1100, 2, -10, 700, wp=115),
)  # fmt: skip
_DATA = financien.Financien(_EDITIE, _RIJEN)

_PROFIELEN = {
    "roc midden nederland": {"naam": "ROC Midden Nederland", "sector": "mbo", "instellingscode": "25LH"},
    "roc van amsterdam": {"naam": "ROC van Amsterdam", "sector": "mbo", "instellingscode": "25PZ"},
    "aeres hogeschool": {"naam": "Aeres Hogeschool", "sector": "hbo", "instellingscode": "30TX"},
    "firda": {"naam": "Firda", "sector": "mbo", "instellingscode": "08PG"},
    "transnationale universiteit limburg": {"naam": "tUL", "sector": "wo", "instellingscode": "27YA"},
}
_BESTUUR = {"25LH": 40597, "25PZ": 40833, "30TX": 40687, "08PG": 30932}


@pytest.fixture(autouse=True)
def bron(monkeypatch):
    monkeypatch.setattr(tool.instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(naam.strip().lower()))
    monkeypatch.setattr(tool, "bestuur_van", lambda code: _BESTUUR.get(code))
    monkeypatch.setattr(tool, "_bron", lambda: _DATA)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: ())
    monkeypatch.setattr(tool.Config, "APP_ENV", "test")


def _uit(vraag: str) -> dict:
    return json.loads(tools.dispatch(TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": vraag})[0])


def _jaar_van(uit: dict, jaar: int, eenheid: int = 0) -> dict:
    return next(j for j in uit["eenheden"][eenheid]["reeks"] if j["verslagjaar"] == jaar)


# --- de acceptatievraag ------------------------------------------------------------------------------------------


def test_acceptatie_hoe_staat_roc_midden_nederland_er_financieel_voor():
    """Kengetallen met verslagjaar, variant, het sectorcijfer van de Inspectie, signaleringswaarden en voorbehouden."""
    uit = _uit("ROC Midden Nederland")

    assert uit["bestuur"] == {"nummer": "40597", "naam": "Stichting ROC Midden Nederland", "sector": "mbo",
                              "groepering": "ROC"}  # fmt: skip
    assert uit["instelling"] == {"naam": "ROC Midden Nederland", "instellingscode": "25LH"}
    j = _jaar_van(uit, 2025)
    assert (j["verslagjaar"], j["variant"]) == (2025, "geconsolideerd")
    # Solvabiliteit I 0,69; het sectorcijfer is het gewogen cijfer (656,35 / 1030,117 = 0,64), niet de mediaan (0,59).
    assert j["solvabiliteit_1"] == {"bestuur": 0.69, "sector": 0.64, "verschil": 0.05}
    mbo = sorted(r.waarden["solvabiliteit_1"] for r in _RIJEN if r.sector == "MBO" and r.verslagjaar == 2025)
    assert round((mbo[3] + mbo[4]) / 2, 2) == 0.59 != j["solvabiliteit_1"]["sector"]
    assert "Gewogen" in uit["sectorcijfer"]["methode"] and "Geen mediaan" in uit["sectorcijfer"]["methode"]
    assert uit["sectorcijfer"]["sector"] == "mbo"
    assert uit["sectorcijfer"]["eenheden_per_jaar"]["2025"] == 8  # 40833 telt als drie eenheden
    assert j["rentabiliteit_procent"]["bestuur"] == 2.01  # 4,3 / 213,4
    assert (j["rijksbijdragen_eur"], j["rijksbijdragen_mln_eur"]) == (197_021_000, 197.0)
    assert j["liquiditeit_signaleringswaarde"] == 0.5 and j["signaleringen"] == []
    assert uit["signaleringswaarden"]["solvabiliteit_2"] == "onder 0,30"
    assert uit["signaleringswaarden"]["rentabiliteit"] == "geen signaleringswaarde"
    assert uit["signaleringswaarden"]["jaar"] == 2024 and "Inspectie" in uit["signaleringswaarden"]["bron"]
    voorbehouden = " ".join(uit["voorbehouden"])
    for tekst in ("hele bestuur", "vo", "niets over de kwaliteit", "boekjaar", "accountant", "standaard"):
        assert tekst in voorbehouden
    assert "Reken niets zelf" in uit["noot"]
    assert uit["bron"]["editie"] == "verslagjaren 2021-2025" and uit["bron"]["peildatum"] == "31 december 2025"


def test_het_verschil_is_dat_van_de_afgeronde_waarden():
    j = _jaar_van(_uit("40597"), 2025)
    for k in ("solvabiliteit_1", "solvabiliteit_2", "liquiditeit", "rentabiliteit_procent"):
        assert j[k]["verschil"] == round(j[k]["bestuur"] - j[k]["sector"], 2)


# --- eenheden, variant, leeg -------------------------------------------------------------------------------------


def test_roc_van_amsterdam_krijgt_alleen_haar_eigen_eenheid_van_40833():
    uit = _uit("ROC van Amsterdam")
    assert uit["sleutel"] == "40833-25PZ" and [e["eenheid"] for e in uit["eenheden"]] == ["40833-25PZ"]


def test_bestuur_40833_geeft_drie_eenheden_en_nooit_een_som():
    uit = _uit("40833")
    assert [e["eenheid"] for e in uit["eenheden"]] == ["40833-25LR", "40833-25PZ", "40833-30RM"]
    assert "tel of middel ze nooit" in uit["noot"]


def test_een_wissel_van_variant_krijgt_een_melding():
    [eenheid] = _uit("ROC van Amsterdam")["eenheden"]
    assert "geconsolideerd 2024, enkelvoudig 2025" in eenheid["melding"]
    assert "door de variant" in eenheid["melding"]


def test_leeg_is_geen_nul():
    uit = _uit("30000")
    assert _jaar_van(uit, 2025)["rentabiliteit_procent"]["bestuur"] is None
    assert "verschil" not in _jaar_van(uit, 2025)["rentabiliteit_procent"]
    assert "null ontbreekt in de bron: dat is geen 0" in uit["noot"]


def test_signalering_onder_de_waarden_van_de_inspectie():
    j = _jaar_van(_uit("30000"), 2025)
    assert {s["kengetal"]: s["signaleringswaarde"] for s in j["signaleringen"]} == {
        "solvabiliteit_2": 0.3,
        "liquiditeit": 1.0,
    }
    liq = next(s for s in j["signaleringen"] if s["kengetal"] == "liquiditeit")
    assert liq["waarde"] == 0.6 and liq["trede"] == "totale baten van € 3 tot en met € 12 miljoen"


def test_werkplaatsfunctie_apart_bij_een_universiteit_met_umc():
    j = _jaar_van(_uit("00009"), 2025)
    assert (j["rijksbijdragen_eur"], j["werkplaatsfunctie_eur"]) == (700_000_000, 115_000_000)
    assert "werkplaatsfunctie_eur" not in _jaar_van(_uit("40597"), 2025)


def test_een_reeks_die_eerder_stopt_krijgt_een_melding():
    [eenheid] = _uit("40295")["eenheden"]
    assert "staat pas vanaf verslagjaar 2024" in eenheid["melding"]
    assert "na verslagjaar 2024 niet meer" in eenheid["melding"]


def test_aeres_hogeschool_krijgt_het_bestuur_onder_mbo_met_een_noot():
    uit = _uit("Aeres Hogeschool")
    assert uit["bestuur"]["sector"] == "mbo" and uit["sectorcijfer"]["sector"] == "mbo"
    assert "hbo-instelling, maar DUO rekent het bestuur toe aan het mbo" in uit["noot"]


# --- fusies (#728) -----------------------------------------------------------------------------------------------


def test_een_bestuursfusie_in_de_reeks_krijgt_een_vaste_regel(monkeypatch):
    stap = Stap("40295", "Stg. Alg. Voortgez. Onderwijs", "volledig", "2025-01-01", via="30932", wet=None)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: (stap,) if code == "30932" else ())
    noot = _uit("Firda")["noot"]
    assert "Fusie bij Stg. Firda (30932): Stg Alg VO BO Volw Eduk (40295) is per 1 januari 2025" in noot
    assert "tot en met verslagjaar 2024 staat Stg Alg VO BO Volw Eduk apart" in noot
    assert "DUO-studentaantallen van vóór de fusie" in noot


def test_een_voorganger_die_geen_bestuur_in_de_verantwoording_is_telt_niet(monkeypatch):
    """`00009` is in RIO de A&O groep: een overgang daarvan hoort niet bij de Universiteit Utrecht (#725)."""
    stap = Stap("99999", "A&O groep", "volledig", "2023-01-01", via="00009", wet=None)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: (stap,))
    assert "Fusie" not in _uit("00009")["noot"]


def test_een_fusie_voor_de_reeks_telt_niet_en_een_rio_storing_breekt_niets(monkeypatch):
    besturen = {40295: ("Friesland College", 2022)}
    stap = Stap("40295", None, "volledig", "2021-01-01", via="30932")
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: (stap,))
    assert fusies.bestuur_in_reeks(30932, "Firda", (2021, 2025), besturen) == ()

    def kapot(code, sinds):
        raise httpx.ConnectTimeout("te laat")

    monkeypatch.setattr(fusies, "_voorgangers", kapot)
    assert fusies.bestuur_in_reeks(30932, "Firda", (2021, 2025), besturen) == ()


# --- scope en meldingen ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vraag", "tekst"),
    [
        ("12345", "staat niet bij de besturen die DUO aan mbo, hbo of wo toerekent"),
        ("12345", "geen financiën van besturen in po of vo"),
        ("Hogeschool Nergens", "Onbekende instelling of bestuur"),
        ("Transnationale Universiteit Limburg", "geen bestuur in DUO's adressenbestand"),
    ],
)
def test_buiten_scope_of_onbekend_is_een_melding_zonder_cijfers(vraag, tekst):
    uit = tools.dispatch(TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": vraag})[0]
    assert tekst in uit and not uit.startswith("{")


def test_een_bestuursnaam_uit_de_verantwoording_werkt_ook():
    assert _uit("stichting roc midden nederland")["sleutel"] == "40597"


@pytest.mark.parametrize("omgeving", ["playground", "production"])
def test_zonder_bevestigde_licentie_geen_cijfers_op_playground_en_productie(monkeypatch, omgeving):
    monkeypatch.setattr(tool.Config, "APP_ENV", omgeving)
    assert tool.get_bestuursfinancien("ROC Midden Nederland") == tool.NIET_BESCHIKBAAR
    monkeypatch.setattr(tool, "LICENTIE_BEVESTIGD", True)
    assert tool.get_bestuursfinancien("ROC Midden Nederland").startswith("{")


def test_een_onbereikbare_bron_is_een_gecodeerde_fout(monkeypatch):
    def kapot():
        try:
            raise httpx.ConnectTimeout("te laat")
        except httpx.ConnectTimeout as e:
            raise financien.FinancienOnbereikbaar("DUO antwoordde niet") from e

    monkeypatch.setattr(tool, "_bron", kapot)
    uit = tool.get_bestuursfinancien("ROC Midden Nederland")
    assert fouten.code(uit) == "bron_onbereikbaar" and "DUO" in uit


def test_een_afwijkend_bestand_is_een_weigering(monkeypatch):
    def afwijkend():
        raise financien.FinancienAfwijkend("kolom ontbreekt")

    monkeypatch.setattr(tool, "_bron", afwijkend)
    uit = tool.get_bestuursfinancien("ROC Midden Nederland")
    assert fouten.code(uit) == "bron_fout" and "kolom ontbreekt" in uit


# --- de app eromheen ---------------------------------------------------------------------------------------------


def test_de_tool_staat_in_de_dispatch_en_de_bron_onder_het_antwoord():
    uit, _ = tools.dispatch(TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": "ROC Midden Nederland"})
    stap = (TOOL_GET_BESTUURSFINANCIEN, uit)
    regel = (
        "DUO · Financiële verantwoording uit XBRL (variant standaard), editie verslagjaren 2021-2025, peildatum "
        "31 december 2025, versie van 15 september 2026"
    )
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: financien.PAGINA}
    assert TOOL_GET_BESTUURSFINANCIEN in tools.LABELS


def test_de_catalogus_wijst_naar_de_tool_en_get_duo_data_laadt_hem_niet():
    record = next(r for r in catalog._rio_duo() if r.get("_ckan_id") == "financien")
    assert catalog.status(record) == catalog.STATUS_VIA_TOOL
    assert catalog.eigen_tool("financien") == TOOL_GET_BESTUURSFINANCIEN
    assert "get_bestuursfinancien" in get_duo_data("duo:financien")


def test_de_snippet_rekent_met_dezelfde_pakketfunctie_als_de_tool(monkeypatch):
    """Equivalentie (#945): de snippet draait tegen dezelfde data en geeft afgerond dezelfde getallen."""
    vraag = {"instelling_of_bestuur": "ROC van Amsterdam"}
    uit = tools.dispatch(TOOL_GET_BESTUURSFINANCIEN, vraag)[0]
    code = snippet.generate(TOOL_GET_BESTUURSFINANCIEN, vraag, uit)
    assert code is not None
    assert 'financien.overzicht(f, "40833-25PZ")' in code and "from onderwijsbronnen.duo import financien" in code
    assert "# Gemaakt met onderwijsbronnen" in code and "# Databewerking in de app:" in code

    monkeypatch.setattr(financien, "laad", lambda *a, **k: _DATA)
    ruimte: dict = {}
    exec(compile(code.replace("print(df)", ""), "<snippet>", "exec"), ruimte)
    df: pd.DataFrame = ruimte["df"]
    reeks = json.loads(uit)["eenheden"][0]["reeks"]
    assert list(df["verslagjaar"]) == [j["verslagjaar"] for j in reeks]
    for rij, j in zip(df.to_dict("records"), reeks, strict=True):
        assert rij["variant"] == j["variant"]
        for k in ("solvabiliteit_1", "solvabiliteit_2", "liquiditeit"):
            assert (round(rij[k], 2), round(rij[f"{k}_sector"], 2)) == (j[k]["bestuur"], j[k]["sector"])
        assert round(100 * rij["rentabiliteit"], 2) == j["rentabiliteit_procent"]["bestuur"]


def test_geen_snippet_bij_een_melding():
    vraag = {"instelling_of_bestuur": "12345"}
    uit = tools.dispatch(TOOL_GET_BESTUURSFINANCIEN, vraag)[0]
    assert snippet.generate(TOOL_GET_BESTUURSFINANCIEN, vraag, uit) is None


def test_de_bron_ping_telt_de_eenheden_per_sector():
    ping = next(p for p in bronping.PINGS if p.id == "duo-financien")
    assert ping.bron == "duo"
    assert ping.bewijs({"editie": "2021-2025", "eenheden": {"MBO": 53, "HBO": 35, "WO": 18}}) is None
    assert "MBO 3" in str(ping.bewijs({"editie": "2021-2025", "eenheden": {"MBO": 3, "HBO": 35, "WO": 18}}))


# --- If-Modified-Since (core/actualiteit) ------------------------------------------------------------------------


def test_een_ongewijzigd_bestand_komt_uit_de_cache_met_if_modified_since(monkeypatch):
    gezien = []

    def get(url, headers, timeout, follow_redirects):
        gezien.append(headers.get("If-Modified-Since"))
        verzoek = httpx.Request("GET", url)
        if headers.get("If-Modified-Since"):
            return httpx.Response(304, request=verzoek)
        kop = {"content-type": "application/xlsx", "last-modified": "Tue, 15 Sep 2026 14:01:22 GMT"}
        return httpx.Response(200, headers=kop, content=b"PK-inhoud", request=verzoek)

    monkeypatch.setattr(actualiteit.httpx, "get", get)
    haler = actualiteit.Voorwaardelijk()
    assert haler("https://duo.nl/x.xlsx") == (b"PK-inhoud", "application/xlsx")
    assert haler("https://duo.nl/x.xlsx") == (b"PK-inhoud", "application/xlsx")
    assert gezien == [None, "Tue, 15 Sep 2026 14:01:22 GMT"]


def test_zonder_last_modified_bewaart_de_haler_niets(monkeypatch):
    def get(url, headers, timeout, follow_redirects):
        assert "If-Modified-Since" not in headers
        return httpx.Response(200, content=b"<html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(actualiteit.httpx, "get", get)
    haler = actualiteit.Voorwaardelijk()
    haler("https://duo.nl/pagina.jsp")
    haler("https://duo.nl/pagina.jsp")
