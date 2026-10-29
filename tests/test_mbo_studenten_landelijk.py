"""Mbo-studenten landelijk krijgt één vaste bron (#805): CBS 85354NED uit het recept, met de bron en DUO eronder.

In de functionele test van 29-10 gaf "Hoeveel mbo-studenten waren er in 2024/25?" DUO 474.963 (het bestand per
sectorkamer, met onderdrukte cellen) en CBS 475.460 (85354NED; ook 85353NED). Beide klopten, met een andere
definitie. Nu kiest de code (`get_maat`, maat `mbo_studenten_landelijk`) en eindigt het antwoord met een regel uit
code die de definitie en de andere bron noemt, zoals bij vmbo → mbo (#667).

De bron is hier een fixture (`tools.cbs.data` filtert op de `$filter` zoals CBS); de catalogus is echt.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agent.bronkeuze import KOP, bronregel, met_bronregel
from agent.grounding import checked_numbers
from tools import cbs_standaard, herlaad, maten, snippet, store
from tools.maten import MATEN, MBO_STUDENTEN, MBO_STUDENTEN_LANDELIJK, PERSONEN_HO, get_maat, plan
from tools.schemas import TOOL_GET_MAAT, TOOL_SCHEMAS

_DS = "85354NED"
_INCL, _EXCL, _BOL, _BBL = "A025290", "A041867", "A041868", "A025293"
_VAST = {"Geslacht": "T001038", "Niveau": "T001336", "Herkomstland": "T001040", "GeboortelandOuders": "T001638"}
_VRAAG = "Hoeveel mbo-studenten waren er in 2024/25?"

_DEFS = {
    **{dimensie: {"type": "Dimension", "title": dimensie} for dimensie in (*_VAST, "Leerweg")},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "MboStudenten_1": {"type": "Topic", "title": "Mbo-studenten", "unit": "aantal"},
}
_LABELS = {
    "Leerweg": [
        {"Key": _INCL, "Title": "Totaal mbo (incl. extranei)"},
        {"Key": _EXCL, "Title": "Totaal mbo (excl. extranei)"},
        {"Key": _BOL, "Title": "Bol totaal"},
        {"Key": _BBL, "Title": "Bbl totaal"},
    ],
    "Perioden": [
        {"Key": "2024SJ00", "Title": "2024/'25", "Status": "Definitief"},
        {"Key": "2025SJ00", "Title": "2025/'26", "Status": "Voorlopig"},
    ],
}
# De live waarden van 29-10-2026 (CBS 85354NED, elke andere dimensie op haar totaal).
_WAARDEN = {
    (_INCL, "2024SJ00"): 475460,
    (_EXCL, "2024SJ00"): 465820,
    (_BOL, "2024SJ00"): 328610,
    (_BBL, "2024SJ00"): 137220,
    (_INCL, "2025SJ00"): 475550,
    (_EXCL, "2025SJ00"): 466800,
}
_RIJEN = [
    {**_VAST, "Leerweg": leerweg, "Perioden": periode, "MboStudenten_1": waarde}
    for (leerweg, periode), waarde in _WAARDEN.items()
]


def _feed(dataset_id, **params):
    """De CBS-feed in het klein: elke `and`-clausule moet kloppen, een `(… or …)`-groep op één van haar delen."""
    clausules = [c for c in str(params.get("$filter") or "").split(" and ") if c]

    def klopt_een(rij, clausule):
        kolom, _, waarde = clausule.strip("() ").partition(" eq ")
        return str(rij[kolom.removeprefix("trim(").removesuffix(")")]) == waarde.strip("'")

    def klopt(rij, clausule):
        return any(klopt_een(rij, deel) for deel in clausule.split(" or "))

    return [dict(r) for r in _RIJEN if all(klopt(r, c) for c in clausules)]


@pytest.fixture
def bron():
    with (
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=lambda dataset_id, endpoint, **_: _LABELS.get(endpoint, [])),
        patch("tools.cbs.data", side_effect=_feed) as datacall,
    ):
        yield datacall


def _uit(tekst: str) -> dict:
    uit = json.loads(tekst)
    assert "data_key" in uit, uit
    return uit


def _per_jaar(uit: dict) -> dict[str, int]:
    return {r["Perioden"]: r[uit["waardekolom"]] for r in uit["rijen"]}


# --- de maat ---------------------------------------------------------------------------------------


def test_een_rij_per_schooljaar_uit_een_tabel_met_de_standaardleerweg(bron):
    uit = _uit(get_maat(MBO_STUDENTEN_LANDELIJK))

    assert _per_jaar(uit) == {"2024SJ00": 475460, "2025SJ00": 475550}
    assert uit["maat"] == MBO_STUDENTEN_LANDELIJK and uit["sector"] == "mbo" and uit["vorm"] == "alle"
    assert (uit["periodekolom"], uit["waardekolom"]) == ("Perioden", "MboStudenten_1")
    assert uit["teldefinitie"].endswith("; Leerweg: Totaal mbo (incl. extranei)")
    assert (uit["recept"]["bron"], uit["recept"]["dataset"]) == ("cbs", _DS)


def test_het_recept_pint_elke_dimensie_in_een_aanroep(bron):
    uit = _uit(get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"]))

    assert uit["recept"]["selectie"]["dimensies"] == {"Leerweg": _INCL, **_VAST}
    assert uit["recept"]["selectie"]["onderwerpen"] == ["MboStudenten_1"]
    (call,) = bron.call_args_list
    filter_ = call.kwargs["$filter"]
    assert f"trim(Leerweg) eq '{_INCL}'" in filter_ and "2024SJ00" in filter_
    assert all(f"trim({dimensie}) eq '{code}'" in filter_ for dimensie, code in _VAST.items())
    assert _per_jaar(uit) == {"2024SJ00": 475460}


@pytest.mark.parametrize(("vorm", "code", "waarde"), [("bol", _BOL, 328610), ("bbl", _BBL, 137220)])
def test_een_leerweg_pint_haar_eigen_code_en_staat_in_de_teldefinitie(bron, vorm, code, waarde):
    with cbs_standaard.gesprek([_VRAAG]):
        uit = _uit(get_maat(MBO_STUDENTEN_LANDELIJK, vorm=vorm, schooljaren=["2024/25"]))

    assert uit["recept"]["selectie"]["dimensies"]["Leerweg"] == code
    assert _per_jaar(uit) == {"2024SJ00": waarde}
    assert uit["teldefinitie"].endswith(f"; Leerweg: {vorm}") and "extranei" not in uit["teldefinitie"]


def test_een_gesprek_dat_extranei_uitsluit_krijgt_de_smallere_telling(bron):
    with cbs_standaard.gesprek([_VRAAG, "En zonder extranei?"]):
        uit = _uit(get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"]))

    assert _per_jaar(uit) == {"2024SJ00": 465820}
    assert uit["recept"]["selectie"]["dimensies"]["Leerweg"] == _EXCL
    assert uit["teldefinitie"].endswith("; Leerweg: Totaal mbo (excl. extranei)")
    assert "alternatieve_telling" not in uit  # het recept koos zelf: niets vervangen


@pytest.mark.parametrize(
    ("maat", "args", "tekst"),
    [
        (MBO_STUDENTEN_LANDELIJK, {"instelling": "ROC Mondriaan"}, f"per instelling is dat {MBO_STUDENTEN}"),
        (MBO_STUDENTEN_LANDELIJK, {"sector": "hbo"}, "geldt voor mbo, niet voor hbo"),
        (MBO_STUDENTEN_LANDELIJK, {"vorm": "voltijd"}, "kies uit alle, bol, bbl"),
        # Dezelfde regel geldt nu voor elke landelijke maat: een instelling werd bij ho stil genegeerd.
        ("deelnemers_ho_landelijk", {"instelling": "HU", "sector": "hbo"}, f"per instelling is dat {PERSONEN_HO}"),
        ("deelnemers_ho_landelijk", {}, "Geef voor deelnemers_ho_landelijk de sector: hbo of wo"),
    ],
)
def test_een_afbakening_die_niet_past_is_een_melding_geen_gok(maat, args: dict[str, Any], tekst):
    uitkomst = plan(maat, **args)
    assert isinstance(uitkomst, str) and tekst in uitkomst


def test_vijf_keer_dezelfde_vraag_geeft_dezelfde_tabel_key_en_getal(bron):
    uitkomsten = []
    for ronde in range(5):
        if ronde in (0, 2):
            store.clear()  # vers geladen; de andere rondes vinden de key al in de store
        with cbs_standaard.gesprek([_VRAAG]):
            uit = _uit(get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"]))
        uitkomsten.append((uit["recept"]["dataset"], uit["data_key"], _per_jaar(uit)["2024SJ00"]))

    assert all(u == uitkomsten[0] for u in uitkomsten)
    assert uitkomsten[0][0] == _DS and uitkomsten[0][2] == 475460


# --- herladen, snippet, schema en prompt ----------------------------------------------------------


def test_de_key_komt_na_een_herstart_terug_door_het_recept(bron):
    args: dict[str, Any] = {"maat": MBO_STUDENTEN_LANDELIJK, "schooljaren": ["2024/25"]}
    key = _uit(get_maat(**args))["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_MAAT, "arguments": args})
    assert recept is not None  # zonder som is de key de CBS-selectie zelf: get_cbs_data laadt haar opnieuw
    store.clear()

    assert herlaad.herlaad(key, recept).gelukt
    assert store.get(key)["MboStudenten_1"].tolist() == [475460]


def test_de_snippet_laadt_de_tabel_met_de_gepinde_codes():
    script = snippet.generate(TOOL_GET_MAAT, {"maat": MBO_STUDENTEN_LANDELIJK, "vorm": "bbl"})

    assert script is not None and _DS in script and _BBL in script
    assert all(code in script for code in _VAST.values())


def test_schema_prompt_en_recept_noemen_de_maat():
    functie = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_MAAT)["function"]
    prompt = (Path(__file__).resolve().parents[1] / "prompts" / "system.md").read_text(encoding="utf-8")
    stap0 = next(regel for regel in prompt.splitlines() if regel.startswith("0. **Vaste maat eerst**"))

    assert MBO_STUDENTEN_LANDELIJK in MATEN
    assert MBO_STUDENTEN_LANDELIJK in functie["parameters"]["properties"]["maat"]["enum"]
    for tekst in (functie["description"], stap0):
        assert MBO_STUDENTEN_LANDELIJK in tekst and _DS in tekst
        assert "get_cbs_data" in tekst  # een uitsplitsing naar geslacht, niveau of herkomst is geen maat
        assert "Mbo-studenten per instelling" in tekst


def test_de_domeinregels_leggen_de_keuze_en_het_alternatief_vast():
    regels = (Path(__file__).resolve().parents[1] / "docs" / "domeinregels.md").read_text(encoding="utf-8")
    sectie = regels.split("## CBS: mbo-studenten landelijk", 1)[1].split("\n## ", 1)[0]

    for tekst in (_DS, _BOL, _BBL, *_VAST.values(), "mbo-studenten-per-instelling", "ondergrens", "#805"):
        assert tekst in sectie, tekst
    assert maten.MATEN[MBO_STUDENTEN_LANDELIJK].dataset == _DS


# --- de regel onder het antwoord -------------------------------------------------------------------


def _stap() -> tuple[str, str]:
    return TOOL_GET_MAAT, get_maat(MBO_STUDENTEN_LANDELIJK, schooljaren=["2024/25"])


def test_de_regel_noemt_een_tabel_en_duo_met_zijn_definitie_zonder_getal(bron):
    regel = bronregel([_stap()])

    assert regel is not None and regel.startswith(KOP)
    assert f"CBS {_DS}" in regel and "85353NED" not in regel
    assert "Totaal mbo (incl. extranei)" in regel
    assert "DUO 'Mbo-studenten per instelling'" in regel and "mbo-studenten-per-instelling" in regel
    assert "1 oktober" in regel and "ondergrens" in regel
    assert checked_numbers(regel) == []


def test_het_antwoord_eindigt_met_de_regel_een_keer(bron):
    stap = _stap()
    tekst = met_bronregel("In 2024/25 waren er 475.460 mbo-studenten.", [stap, stap])

    assert tekst.count(KOP) == 1
    assert tekst.endswith(bronregel([stap]) or "?")
