"""Een vaste standaardselectie per CBS-tabel, uit code (#653).

"vmbo → mbo" telde op 19-10 inclusief extranei (83.020 van 157.450) en op 20-10 exclusief (82.780 van 155.270):
het model koos de code. Bij de mbo-tabellen met beide totalen in Leerweg kiest nu de code de ruimste telling; alleen
een gebruiker die extranei uitsluit, houdt de smallere.
"""

import json
from unittest.mock import patch

from agent.uitgangspunt import uitgangspunt
from tools import cbs_standaard, store
from tools.cbs import get_cbs_data
from tools.snippet import generate

INCL = "A025290"
EXCL = "A041867"
_VRAAG = "Hoeveel mbo-instromers kwamen een jaar eerder uit het vmbo?"


def _selectie(leerweg) -> dict:
    return {
        "dimensies": {"Geslacht": "T001038", "Niveau": "T001336", "Leerweg": leerweg},
        "periode": ["2023/24"],
    }


def _leerweg(uitkomst) -> object:
    selectie, _ = uitkomst
    return selectie["dimensies"]["Leerweg"]


# --- de regel ---------------------------------------------------------------------


def test_de_smallere_telling_wordt_de_standaard_in_een_gesprek():
    model = _selectie(EXCL)
    with cbs_standaard.gesprek([_VRAAG]):
        selectie, standaard = cbs_standaard.toegepast("85569NED", model)

    assert selectie["dimensies"]["Leerweg"] == INCL
    assert standaard is not None and standaard.dimensie == "Leerweg"
    # De aanroep van het model blijft zoals hij was: de cache en de toolstap tonen wat het model vroeg.
    assert model["dimensies"]["Leerweg"] == EXCL


def test_de_standaard_zelf_blijft_ongemoeid():
    with cbs_standaard.gesprek([_VRAAG]):
        assert cbs_standaard.toegepast("85569NED", _selectie(INCL)) == (_selectie(INCL), None)


def test_een_lijst_van_een_code_telt_als_die_code():
    with cbs_standaard.gesprek([_VRAAG]):
        assert _leerweg(cbs_standaard.toegepast("85354NED", _selectie([EXCL]))) == INCL


def test_uitsplitsen_en_meer_codes_blijven_zoals_het_model_ze_koos():
    with cbs_standaard.gesprek([_VRAAG]):
        for leerweg in ("*", [EXCL, "A041773"], "A041868"):
            assert cbs_standaard.toegepast("85353NED", _selectie(leerweg)) == (_selectie(leerweg), None)


def test_een_gebruiker_die_extranei_uitsluit_houdt_de_smallere_telling():
    for vraag in (
        "Hoeveel mbo-studenten zonder extranei?",
        "Hoeveel mbo-studenten, exclusief extranei?",
        "Aantal mbo-studenten excl. extranei in 2023",
        "Hoeveel studenten zitten er in bol en bbl samen?",
        "Tel de extranei niet mee.",
    ):
        with cbs_standaard.gesprek([vraag]):
            assert _leerweg(cbs_standaard.toegepast("85569NED", _selectie(EXCL))) == EXCL, vraag


def test_een_uitsluiting_eerder_in_het_gesprek_geldt_ook_voor_een_vervolgvraag():
    with cbs_standaard.gesprek(["Hoeveel mbo-studenten zonder extranei?", "En in 2022?"]):
        assert _leerweg(cbs_standaard.toegepast("85354NED", _selectie(EXCL))) == EXCL


def test_extranei_noemen_is_geen_uitsluiting():
    for vraag in ("Hoeveel extranei zijn er?", "Hoeveel mbo-studenten inclusief extranei?"):
        with cbs_standaard.gesprek([vraag]):
            assert _leerweg(cbs_standaard.toegepast("85569NED", _selectie(EXCL))) == INCL, vraag


def test_buiten_de_chat_geldt_de_code_van_de_aanroeper():
    """MCP en evals hebben geen gesprek: een expliciet gekozen code is daar de vraag zelf."""
    assert cbs_standaard.toegepast("85569NED", _selectie(EXCL)) == (_selectie(EXCL), None)


def test_een_tabel_zonder_beide_totalen_heeft_geen_standaard():
    # 85701NED kent alleen "Totaal mbo (excl. extranei)", in de dimensie Onderwijssoort.
    selectie = {"dimensies": {"Onderwijssoort": EXCL}, "periode": ["2023/24"]}
    with cbs_standaard.gesprek([_VRAAG]):
        assert cbs_standaard.toegepast("85701NED", selectie) == (selectie, None)


def test_de_spelling_van_het_id_maakt_niet_uit():
    with cbs_standaard.gesprek([_VRAAG]):
        for dataset_id in ("85569ned", "cbs:85569NED", "cbs_85569NED"):
            assert _leerweg(cbs_standaard.toegepast(dataset_id, _selectie(EXCL))) == INCL, dataset_id


def test_elke_tabel_met_de_standaard_noemt_hem_in_de_domeinregels():
    from pathlib import Path

    regels = Path(__file__).resolve().parents[1].joinpath("docs", "domeinregels.md").read_text(encoding="utf-8")
    assert all(tabel in regels for tabel in cbs_standaard.TABELLEN)


# --- door get_cbs_data heen --------------------------------------------------------

_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Niveau": {"type": "Dimension", "title": "Niveau"},
    "Leerweg": {"type": "Dimension", "title": "Leerweg"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "Instromers_1": {"type": "Topic", "title": "Instromers"},
}
_LABELS = {
    "Geslacht": [{"Key": "T001038", "Title": "Totaal mannen en vrouwen"}],
    "Niveau": [{"Key": "T001336", "Title": "Totaal middelbaar beroepsonderwijs"}],
    "Leerweg": [
        {"Key": INCL, "Title": "Totaal mbo (incl. extranei)"},
        {"Key": EXCL, "Title": "Totaal mbo (excl. extranei)"},
    ],
    "Perioden": [{"Key": "2023SJ00", "Title": "2023/'24"}],
}
_RIJEN = [
    {"Geslacht": "T001038", "Niveau": "T001336", "Leerweg": INCL, "Perioden": "2023SJ00", "Instromers_1": 157450},
    {"Geslacht": "T001038", "Niveau": "T001336", "Leerweg": EXCL, "Perioden": "2023SJ00", "Instromers_1": 155270},
]


def _feed(dataset_id, **params):
    """De CBS-feed in het klein: elke `trim(Dim) eq 'x'`-clausule moet kloppen."""
    clausules = [c for c in str(params.get("$filter") or "").split(" and ") if c]

    def klopt(rij, clausule):
        kolom, _, waarde = clausule.partition(" eq ")
        return str(rij[kolom.removeprefix("trim(").removesuffix(")")]) == waarde.strip("'")

    return [dict(r) for r in _RIJEN if all(klopt(r, c) for c in clausules)]


def _run(leerweg) -> tuple[str, dict, list]:
    """Eén beurt met een model-dubbel dat voor Leerweg `leerweg` kiest: (toolresultaat, selectie, datacalls)."""
    with (
        cbs_standaard.gesprek([_VRAAG]),
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=lambda dataset_id, endpoint, **_: _LABELS.get(endpoint, [])),
        patch("tools.cbs.data", side_effect=_feed) as datacall,
    ):
        resultaat = get_cbs_data("85569NED", selectie=_selectie(leerweg))
    return resultaat, json.loads(resultaat), [c.kwargs for c in datacall.call_args_list]


def test_twee_runs_met_een_andere_modelkeuze_geven_dezelfde_telling_en_uitgangspunt():
    tekst = "Er kwamen 157.450 mbo-instromers."
    regels, aantallen = [], []
    for leerweg in (INCL, EXCL):
        store.clear()
        ruw, resultaat, calls = _run(leerweg)
        assert all(f"trim(Leerweg) eq '{INCL}'" in c["$filter"] for c in calls)
        aantallen.append(store.get(resultaat["data_key"])["Instromers_1"].tolist())
        regels.append(uitgangspunt(_VRAAG, tekst, [("get_cbs_data", ruw)]))

    assert aantallen == [[157450], [157450]]
    assert regels[0] == regels[1]
    assert regels[0] is not None and "Totaal mbo (incl. extranei)" in regels[0]


def test_het_model_hoort_waarom_de_telling_anders_is_dan_gevraagd():
    _, gevraagd, _ = _run(INCL)
    store.clear()
    _, vervangen, _ = _run(EXCL)

    assert "standaardselectie" not in gevraagd
    assert "Totaal mbo (incl. extranei)" in vervangen["standaardselectie"]
    assert "zonder extranei" in vervangen["standaardselectie"]


def test_het_recept_en_de_snippet_tonen_de_telling_die_geladen_is():
    _, resultaat, _ = _run(EXCL)
    known = store.meta(resultaat["data_key"])
    assert known is not None and known.laad is not None
    assert f"trim(Leerweg) eq '{INCL}'" in known.laad[1]["filters"]["$filter"]

    with cbs_standaard.gesprek([_VRAAG]):
        snippet = generate("get_cbs_data", {"dataset_id": "85569NED", "selectie": _selectie(EXCL)})
    assert snippet is not None and INCL in snippet and EXCL not in snippet


# --- run() zet het gesprek ---------------------------------------------------------


def test_run_geeft_de_tools_de_vragen_van_het_hele_gesprek():
    """Een tool draait in een thread (asyncio.to_thread) en erft de vragen; na de beurt zijn ze weg."""
    import asyncio
    import importlib

    from agent.loop import LoopResult

    run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie
    gezien: dict = {}

    async def nep_loop(history, **kwargs):
        selectie, _ = await asyncio.to_thread(cbs_standaard.toegepast, "85354NED", _selectie(EXCL))
        gezien["leerweg"] = selectie["dimensies"]["Leerweg"]
        return LoopResult(aborted="stream", text="Klaar.")

    async def emit(ev):
        pass

    messages = [
        {"role": "user", "content": "Hoeveel mbo-studenten zonder extranei?"},
        {"role": "assistant", "content": "Er waren 450.000 mbo-studenten."},
        {"role": "user", "content": "En in 2022?"},
    ]
    with (
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "scopevraag", lambda *a, **k: None),
        patch.object(run_module, "vo_schoolvraag", lambda *a, **k: None),
        patch.object(run_module, "po_vraag", lambda *a, **k: None),
    ):
        asyncio.run(run_module.run(messages, session={}, emit=emit))

    assert gezien == {"leerweg": EXCL}
    assert cbs_standaard._gespreksvragen.get() is None
