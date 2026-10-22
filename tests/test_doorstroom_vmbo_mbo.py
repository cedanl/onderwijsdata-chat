"""Vmbo → mbo krijgt één vaste bron (#667): CBS 85569NED uit het recept, met de bron en het alternatief eronder.

Dezelfde vraag kreeg op 16/20-10 CBS 85569NED (83.020) en in de audit van 21-10 DUO "Instromende mbo-studenten"
(96.629). Beide klopten, met een andere definitie. Nu kiest de code (`get_maat`, maat `doorstroom_vmbo_mbo`) en
eindigt het antwoord met een regel uit code die de definitie en de andere bron noemt.

De bron is hier een fixture (`tools.cbs.data` filtert op de `$filter` zoals CBS); de catalogus is echt.
"""

import asyncio
import importlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agent.bronkeuze import KOP, bronregel, met_bronregel
from agent.grounding import checked_numbers
from agent.loop import LoopResult
from agent.uitgangspunt import uitgangspunt
from tools import cbs_standaard, herlaad, maten, snippet, store
from tools.maten import DOORSTROOM_VMBO_MBO, MATEN, get_maat, plan
from tools.query import query_data
from tools.schemas import TOOL_GET_MAAT, TOOL_SCHEMAS

_DS = "85569NED"
_POSITIE = "MaatschappelijkePositie1JaarEerder"
_BK, _GT = "A041923", "A041922"
_INCL, _EXCL = "A025290", "A041867"
_VRAAG = "Hoeveel leerlingen stromen door van het vmbo naar het mbo?"

_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Niveau": {"type": "Dimension", "title": "Niveau"},
    "Leerweg": {"type": "Dimension", "title": "Leerweg"},
    "Sectorkamer": {"type": "Dimension", "title": "Sectorkamer"},
    "Persoonskenmerken": {"type": "Dimension", "title": "Persoonskenmerken"},
    _POSITIE: {"type": "Dimension", "title": "Maatschappelijke positie 1 jaar eerder"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "InstromersTotaal_1": {"type": "Topic", "title": "Instromers totaal", "unit": "aantal"},
}
_LABELS = {
    "Leerweg": [
        {"Key": _INCL, "Title": "Totaal mbo (incl. extranei)"},
        {"Key": _EXCL, "Title": "Totaal mbo (excl. extranei)"},
    ],
    _POSITIE: [
        {"Key": "T001357", "Title": "Totaal instromers"},
        {"Key": _BK, "Title": "Vmbo-b/k 3-4 totaal"},
        {"Key": _GT, "Title": "Vmbo-g/t  3-4"},
    ],
    "Perioden": [
        {"Key": "2024SJ00", "Title": "2024/'25", "Status": "Definitief"},
        {"Key": "2025SJ00", "Title": "2025/'26", "Status": "Voorlopig"},
    ],
}
# De live waarden van 22-10-2026 (spec #667, stap 1): 39.940 + 43.080 = 83.020 incl. extranei, 82.780 excl.
_WAARDEN = {
    (_INCL, _BK, "2025SJ00"): 39940,
    (_INCL, _GT, "2025SJ00"): 43080,
    (_EXCL, _BK, "2025SJ00"): 39740,
    (_EXCL, _GT, "2025SJ00"): 43040,
    (_INCL, _BK, "2024SJ00"): 41660,
    (_INCL, _GT, "2024SJ00"): 42770,
    (_INCL, "T001357", "2025SJ00"): 157450,  # het totaal: mag nooit in de som komen
}
_VAST = {"Geslacht": "T001038", "Niveau": "T001336", "Sectorkamer": "T001637", "Persoonskenmerken": "T001638"}
_RIJEN = [
    {**_VAST, "Leerweg": leerweg, _POSITIE: positie, "Perioden": periode, "InstromersTotaal_1": waarde}
    for (leerweg, positie, periode), waarde in _WAARDEN.items()
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


# --- de maat (criterium 1) -------------------------------------------------------------------------


def test_een_rij_per_schooljaar_met_de_som_van_de_twee_vmbo_codes(bron):
    uit = _uit(get_maat(DOORSTROOM_VMBO_MBO))

    assert _per_jaar(uit) == {"2024SJ00": 41660 + 42770, "2025SJ00": 83020}
    assert uit["maat"] == DOORSTROOM_VMBO_MBO and uit["sector"] == "mbo" and uit["vorm"] == "alle"
    assert (uit["periodekolom"], uit["waardekolom"]) == ("Perioden", "InstromersTotaal_1")
    assert "vmbo-leerjaar 3-4 een jaar eerder" in uit["teldefinitie"]
    assert "Totaal mbo (incl. extranei)" in uit["teldefinitie"]
    assert "157450" not in json.dumps(uit)  # het totaal instromers telt niet mee


def test_het_recept_toont_de_dataset_en_de_gepinde_codes(bron):
    uit = _uit(get_maat(DOORSTROOM_VMBO_MBO, schooljaren=["2025/26"]))
    recept = uit["recept"]

    assert (recept["bron"], recept["dataset"]) == ("cbs", _DS)
    assert recept["som"] == {_POSITIE: [_BK, _GT]}
    assert recept["selectie"]["dimensies"] == {**_VAST, "Leerweg": _INCL, _POSITIE: [_BK, _GT]}
    assert recept["selectie"]["onderwerpen"] == ["InstromersTotaal_1"] and recept["selectie"]["sector"] == "mbo"
    # Eén aanroep: beide codes in één groep, geen haakjes om een `and`-groep (CBS geeft daar 500 op).
    (call,) = bron.call_args_list
    filter_ = call.kwargs["$filter"]
    assert f"(trim({_POSITIE}) eq '{_GT}' or trim({_POSITIE}) eq '{_BK}')" in filter_
    assert f"trim(Leerweg) eq '{_INCL}'" in filter_ and "2025SJ00" in filter_


def test_de_som_is_een_eigen_key_met_de_opgetelde_codes_in_het_label(bron):
    uit = _uit(get_maat(DOORSTROOM_VMBO_MBO))
    known = store.meta(uit["data_key"])
    df = store.get(uit["data_key"])

    assert known is not None and known.afgeleid_van is not None and known.dataset == _DS
    assert known.stap is not None and f"{_BK} + {_GT}" in known.stap
    assert set(df[f"{_POSITIE}_label"]) == {"Vmbo-b/k 3-4 totaal + Vmbo-g/t  3-4"}
    assert set(df["Leerweg_label"]) == {"Totaal mbo (incl. extranei)"}


def test_de_selectie_achter_de_som_is_verder_te_gebruiken(bron):
    """De som legt elke dimensie vast: query_data telt er niets dubbel mee en weigert hem niet (#162)."""
    uit = _uit(get_maat(DOORSTROOM_VMBO_MBO))
    verder = json.loads(query_data(uit["data_key"], group_by=["Perioden"], aggregate={"InstromersTotaal_1": "sum"}))

    assert {r["Perioden"]: r["InstromersTotaal_1"] for r in verder["rijen"]}["2025SJ00"] == 83020


def test_ontbreekt_een_code_in_een_jaar_dan_geen_som_van_een_deel(bron):
    def zonder_gt_2024(dataset_id, **params):
        return [r for r in _feed(dataset_id, **params) if (r[_POSITIE], r["Perioden"]) != (_GT, "2024SJ00")]

    bron.side_effect = zonder_gt_2024
    uit = _uit(get_maat(DOORSTROOM_VMBO_MBO))

    assert _per_jaar(uit) == {"2024SJ00": None, "2025SJ00": 83020}
    assert "geen som" in get_maat(DOORSTROOM_VMBO_MBO, schooljaren=["2024/25"])


@pytest.mark.parametrize(
    ("args", "tekst"),
    [
        ({"instelling": "ROC Mondriaan"}, "is landelijk"),
        ({"sector": "hbo"}, "geldt voor mbo"),
        ({"vorm": "bol"}, "past niet bij"),
    ],
)
def test_een_afbakening_die_niet_past_is_een_melding_geen_gok(args, tekst):
    uitkomst = plan(DOORSTROOM_VMBO_MBO, **args)
    assert isinstance(uitkomst, str) and tekst in uitkomst


def test_de_scopegrens_laat_de_maat_door(bron):
    """Vmbo is vo, maar dit is een mbo-tabel (instromers in het mbo): de scopegrens weigert haar niet."""
    assert "data_key" in json.loads(get_maat(DOORSTROOM_VMBO_MBO))


# --- de extranei-standaard (#653) volgt het gesprek (criterium 2, met de bron als fixture) ---------


def test_in_een_gesprek_zonder_uitsluiting_telt_de_maat_inclusief_extranei(bron):
    with cbs_standaard.gesprek([_VRAAG]):
        uit = _uit(get_maat(DOORSTROOM_VMBO_MBO, schooljaren=["2025/26"]))
    assert _per_jaar(uit) == {"2025SJ00": 83020}


def test_een_gesprek_dat_extranei_uitsluit_krijgt_de_telling_zonder_extranei(bron):
    with cbs_standaard.gesprek([_VRAAG, "En zonder extranei?"]):
        uit = _uit(get_maat(DOORSTROOM_VMBO_MBO, schooljaren=["2025/26"]))

    assert _per_jaar(uit) == {"2025SJ00": 82780}
    assert uit["recept"]["selectie"]["dimensies"]["Leerweg"] == _EXCL
    assert "Totaal mbo (excl. extranei)" in uit["teldefinitie"]
    assert "alternatieve_telling" not in uit  # het recept koos zelf: niets vervangen


def test_de_keuze_van_de_standaard_buiten_de_chat_is_de_ruimste_telling():
    assert cbs_standaard.keuze(_DS) == ("Leerweg", _INCL, "Totaal mbo (incl. extranei)")
    with cbs_standaard.gesprek(["Hoeveel mbo-instromers exclusief extranei?"]):
        assert cbs_standaard.keuze("cbs:85569ned") == ("Leerweg", _EXCL, "Totaal mbo (excl. extranei)")
    assert cbs_standaard.keuze("85701NED") is None


# --- vijf keer dezelfde vraag (criterium 3) -------------------------------------------------------


def test_vijf_keer_dezelfde_maat_geeft_dezelfde_bron_key_inhoud_en_getal(bron):
    uitkomsten = []
    for ronde in range(5):
        if ronde in (0, 2):
            store.clear()  # vers geladen; de andere rondes vinden de keys al in de store
        uit = _uit(get_maat(DOORSTROOM_VMBO_MBO, schooljaren=["2025/26"]))
        df = store.get(uit["data_key"])
        uitkomsten.append(
            (uit["recept"]["dataset"], uit["data_key"], df.to_dict(orient="records"), _per_jaar(uit)["2025SJ00"])
        )

    assert all(u == uitkomsten[0] for u in uitkomsten)
    assert uitkomsten[0][0] == _DS and uitkomsten[0][3] == 83020


# --- herladen, snippet, schema en prompt ----------------------------------------------------------


def test_de_key_komt_na_een_herstart_terug_door_het_recept(bron):
    args: dict[str, Any] = {"maat": DOORSTROOM_VMBO_MBO, "schooljaren": ["2025/26"]}
    key = _uit(get_maat(**args))["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_MAAT, "arguments": args})
    assert recept is not None and recept["tool"] == TOOL_GET_MAAT
    store.clear()

    assert herlaad.herlaad(key, recept).gelukt
    assert store.get(key)["InstromersTotaal_1"].tolist() == [83020]


def test_de_snippet_laadt_beide_codes_en_telt_ze_per_periode_op():
    script = snippet.generate(TOOL_GET_MAAT, {"maat": DOORSTROOM_VMBO_MBO})

    assert script is not None and _DS in script and _BK in script and _GT in script and _INCL in script
    assert 'groupby("Perioden"' in script and "sum(min_count=2)" in script


def test_schema_prompt_en_recept_noemen_de_maat():
    functie = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_MAAT)["function"]
    prompt = (Path(__file__).resolve().parents[1] / "prompts" / "system.md").read_text(encoding="utf-8")
    stap0 = next(regel for regel in prompt.splitlines() if regel.startswith("0. **Vaste maat eerst**"))

    assert DOORSTROOM_VMBO_MBO in MATEN and DOORSTROOM_VMBO_MBO in functie["parameters"]["properties"]["maat"]["enum"]
    for tekst in (functie["description"], stap0):
        assert DOORSTROOM_VMBO_MBO in tekst and "vmbo → mbo" in tekst.lower()
        assert "get_duo_data" in tekst and "Instromende mbo-studenten" in tekst
    assert "alleen als de gebruiker daarom vraagt" in stap0


def test_de_domeinregels_leggen_de_keuze_en_het_alternatief_vast():
    regels = (Path(__file__).resolve().parents[1] / "docs" / "domeinregels.md").read_text(encoding="utf-8")
    sectie = regels.split("## CBS: vmbo → mbo", 1)[1].split("\n## ", 1)[0]

    for tekst in (_DS, _BK, _GT, "instromende-mbo-studenten", "INSTROOM MBO", "ondergrens", "#667", "open"):
        assert tekst in sectie, tekst
    assert maten.MATEN[DOORSTROOM_VMBO_MBO].dataset == _DS


# --- de regel onder het antwoord (criterium 4) ----------------------------------------------------


def _stap(bron) -> tuple[str, str]:
    return TOOL_GET_MAAT, get_maat(DOORSTROOM_VMBO_MBO, schooljaren=["2025/26"])


def test_de_regel_noemt_beide_bronnen_met_hun_definitie_en_geen_getal(bron):
    regel = bronregel([_stap(bron)])

    assert regel is not None and regel.startswith(KOP)
    assert "CBS 85569NED" in regel and "vmbo-leerjaar 3-4 een jaar eerder" in regel
    assert "DUO 'Instromende mbo-studenten'" in regel and "soorten instroom" in regel
    assert "vmbo-diploma" in regel and "direct en indirect" in regel
    assert "verschillen de cijfers" in regel
    assert checked_numbers(regel) == []


def test_het_antwoord_eindigt_met_de_regel_een_keer(bron):
    stap = _stap(bron)
    tekst = met_bronregel("In 2025/26 kwamen 83.020 mbo-instromers uit vmbo-leerjaar 3-4.", [stap, stap])

    assert tekst.count(KOP) == 1
    assert tekst.endswith(bronregel([stap]) or "?")


def test_een_vervolgbeurt_met_de_maat_krijgt_de_regel_ook_een_keer(bron):
    stap = _stap(bron)
    eerste = met_bronregel("Er kwamen 83.020 mbo-instromers uit het vmbo.", [stap])
    # Het model neemt de regel uit de vorige beurt over: die van de app staat er dan toch maar één keer.
    vervolg = met_bronregel(f"En in 2025/26 opnieuw 83.020.\n\n{bronregel([stap])}", [stap])

    assert eerste.count(KOP) == 1 and vervolg.count(KOP) == 1
    assert vervolg.endswith(bronregel([stap]) or "?")


def test_geen_regel_zonder_de_vmbo_maat():
    andere = (TOOL_GET_MAAT, json.dumps({"data_key": "duo:p01hoinges:3:ab", "recept": {"bron": "duo"}}))
    tekst = "De HU had 38.288 studenten."

    assert met_bronregel(tekst, [andere]) == tekst
    assert met_bronregel(tekst, []) == tekst
    # Een regel die het model zelf schreef, zonder de maat in deze beurt, vervalt: hij komt alleen uit code.
    assert met_bronregel(f"{tekst}\n\n{KOP} eigen tekst.", [andere]) == tekst


def test_de_uitgangspunt_regel_noemt_de_opgetelde_vmbo_posities(bron):
    stap = _stap(bron)
    regel = uitgangspunt(_VRAAG, "Er kwamen 83.020 mbo-instromers.", [stap])

    assert regel is not None and "Vmbo-b/k 3-4 totaal + Vmbo-g/t  3-4" in regel


def test_het_antwoord_van_de_beurt_eindigt_met_de_regel_onder_het_telling_blok(bron):
    run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie
    stap = _stap(bron)
    result = LoopResult(text="In 2025/26 kwamen 83.020 mbo-instromers uit vmbo-leerjaar 3-4.", steps=[stap])

    tekst = run_module._antwoordtekst(result, result.text, [], [])

    assert "**Telling**" in tekst and tekst.endswith(bronregel([stap]) or "?")
    assert tekst.index("**Telling**") < tekst.index(KOP) and tekst.count(KOP) == 1


def test_run_zet_de_regel_onder_het_antwoord_en_niet_onder_een_beurt_zonder_maat(bron, zonder_scopekaart):
    run_module = importlib.import_module("agent.run")
    stap = _stap(bron)
    antwoorden = iter(
        [
            LoopResult(
                text="In 2025/26 kwamen 83.020 mbo-instromers uit vmbo-leerjaar 3-4.",
                steps=[stap],
                tool_calls=[{"name": TOOL_GET_MAAT, "arguments": {"maat": DOORSTROOM_VMBO_MBO}}],
            ),
            LoopResult(text="Dat is het cijfer van CBS.", steps=[]),
        ]
    )

    async def nep_loop(history, **kwargs):
        return next(antwoorden)

    async def emit(ev):
        pass

    messages = [{"role": "user", "content": _VRAAG}]
    with (
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "vo_schoolvraag", lambda *a, **k: None),
        patch.object(run_module, "po_vraag", lambda *a, **k: None),
        patch.object(run_module, "_vervolgvragen", lambda *a, **k: asyncio.sleep(0, [])),
    ):
        eerste = asyncio.run(run_module.run(messages, session={}, emit=emit))
        messages += [{"role": "assistant", "content": eerste}, {"role": "user", "content": "Welke bron is dat?"}]
        tweede = asyncio.run(run_module.run(messages, session={}, emit=emit))

    assert eerste.count(KOP) == 1 and eerste.rstrip().endswith("verschillen de cijfers van beide bronnen.")
    assert KOP not in tweede
