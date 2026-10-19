"""Een rapport of dashboard op een afgekapte bron zegt dat, in één vaste regel uit code (#578)."""

import asyncio
import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import dashboard, report
from agent.afkapping import afkappingsregels
from agent.report import RapportGeweigerd
from agent.report_definities import definities_uit_bron
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

loop_module = importlib.import_module("agent.loop")

_TITELS = {
    "85425NED": "Hoger onderwijs; gediplomeerden",
    "85423NED": "Hoger onderwijs; ingeschrevenen",
    "p01hoinges": "Ingeschrevenen hoger onderwijs",
}
_KEY = "cbs:85425NED"
_REGEL = (
    "CBS · Hoger onderwijs; gediplomeerden: de app haalde één pagina van de bron op (5.000 rijen), "
    "niet de hele bron; rijen buiten die pagina ontbreken in dit rapport."
)


@pytest.fixture(autouse=True)
def catalogus():
    with (
        patch("agent.selectie.bron_titel", side_effect=lambda d: _TITELS.get(d, d)),
        patch("agent.selectie.tabelbestanden", return_value=[]),
    ):
        yield


def _pagina(key: str = _KEY, dataset: str = "85425NED", rijen: int = 5000, volledig: bool = False) -> None:
    """Een geladen CBS-key; afgekapt is één pagina van `rijen` rijen, niet de hele bron (#186)."""
    df = pd.DataFrame({"Perioden": ["2024SJ00"] * rijen, "Totaal": [7] * rijen})
    store.put(key, df, KeyMeta(bron="cbs", dataset=dataset, volledig=volledig))


def _datasets(*keys: str, volledig: bool = False) -> list[dict]:
    return [{"data_key": key, "volledig": volledig} for key in keys]


def _rapport(context_datasets: list[dict], **antwoord) -> report.ReportSpec:
    tekst = json.dumps({"beantwoordt": ["Gediplomeerden 2024"], "conclusie": "c", **antwoord})
    return report._parse_spec_from_response(tekst, [], {"topic": "Gediplomeerden", "datasets": context_datasets})


# ── De regel: bron uit de catalogus, het aantal van de laadkey, één per laadkey ─────────────


def test_de_regel_noemt_bron_titel_en_het_aantal_opgehaalde_rijen():
    _pagina()

    assert afkappingsregels(_datasets(_KEY), "rapport") == [_REGEL]


def test_de_tekst_komt_uit_de_store_niet_van_het_model():
    _pagina()

    [regel] = afkappingsregels(_datasets(_KEY), "rapport")

    tekst = store.AFGEKAPT.format(aantal=store.AFGEKAPT_AANTAL.format(rijen="5.000"), waar="rapport")
    assert regel == f"CBS · Hoger onderwijs; gediplomeerden: {tekst}"


def test_een_laadkey_en_een_selectie_erop_geven_een_regel_met_het_aantal_van_de_laadkey():
    _pagina()
    store.derive(_KEY, f"{_KEY}:abc", pd.DataFrame({"Totaal": [7]}))
    store.derive(_KEY, f"{_KEY}:def", pd.DataFrame({"Totaal": [7, 8]}))

    assert afkappingsregels(_datasets(_KEY, f"{_KEY}:abc", f"{_KEY}:def"), "rapport") == [_REGEL]
    assert afkappingsregels(_datasets(f"{_KEY}:abc"), "rapport") == [_REGEL]


def test_twee_afgekapte_laadkeys_geven_twee_regels():
    _pagina()
    _pagina("cbs:85423NED", "85423NED", rijen=1000)

    assert afkappingsregels(_datasets(_KEY, "cbs:85423NED"), "rapport") == [
        _REGEL,
        "CBS · Hoger onderwijs; ingeschrevenen: de app haalde één pagina van de bron op (1.000 rijen), "
        "niet de hele bron; rijen buiten die pagina ontbreken in dit rapport.",
    ]


def test_zonder_laadkey_in_de_store_geen_aantal():
    store.put(
        f"{_KEY}:abc",
        pd.DataFrame({"Totaal": [7]}),
        KeyMeta(bron="cbs", dataset="85425NED", volledig=False, afgeleid_van=_KEY),
    )

    assert afkappingsregels(_datasets(f"{_KEY}:abc"), "rapport") == [
        "CBS · Hoger onderwijs; gediplomeerden: de app haalde één pagina van de bron op, "
        "niet de hele bron; rijen buiten die pagina ontbreken in dit rapport."
    ]


def test_bij_meer_duo_bestanden_staat_het_bestand_erbij():
    store.put(
        "duo:p01hoinges:3",
        pd.DataFrame({"AANTAL": [5] * 20}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=3, volledig=False),
    )
    with (
        patch("agent.selectie.tabelbestanden", return_value=[(1, "hbo"), (3, "wo")]),
        patch("agent.selectie.resource_titel", return_value="Ingeschrevenen wo"),
    ):
        [regel] = afkappingsregels(_datasets("duo:p01hoinges:3"), "rapport")

    assert regel.startswith("DUO · Ingeschrevenen hoger onderwijs, bestand Ingeschrevenen wo: de app haalde")
    assert "(20 rijen)" in regel


@pytest.mark.parametrize(
    ("dataset", "store_volledig"),
    [
        ({"data_key": _KEY, "volledig": True}, True),
        # De context zegt niets over volledigheid (oude tests, een gepatchte context): geen regel.
        ({"data_key": _KEY}, False),
        # Zonder KeyMeta is er geen bron om te noemen.
        ({"data_key": "cbs:zonder-meta", "volledig": False}, False),
        ({"volledig": False}, False),
    ],
)
def test_zonder_bekende_afkapping_geen_regel(dataset, store_volledig):
    _pagina(volledig=store_volledig)
    store.put("cbs:zonder-meta", pd.DataFrame({"Totaal": [7]}))

    assert afkappingsregels([dataset], "rapport") == []


# ── Rapport: vooraan in "Wat dit rapport niet beantwoordt" ──────────────────────────────


def test_het_rapport_zet_de_regel_voor_wat_het_model_als_niet_beantwoord_noemde():
    _pagina()

    spec = _rapport(
        _datasets(_KEY), beantwoordt_niet=["Uitval valt buiten dit rapport.", "Wat u niet in de data vindt"]
    )

    assert spec.beantwoordt_niet == [_REGEL, "Uitval valt buiten dit rapport.", "Wat je niet in de data vindt"]


def test_het_rapport_krijgt_de_regel_ook_als_het_model_niets_als_niet_beantwoord_noemde():
    _pagina()

    assert _rapport(_datasets(_KEY)).beantwoordt_niet == [_REGEL]


@pytest.mark.parametrize(
    ("beantwoordt_niet", "afgekapte", "verwacht"),
    [
        # Zonder regels lijst was al gedekt; de string en de situatie zonder regels liepen niet mee (#583).
        (["Uitval"], True, [_REGEL, "Uitval"]),
        ("Uitval", True, [_REGEL, "Uitval"]),
        (["Uitval"], False, ["Uitval"]),
        ("Uitval", False, ["Uitval"]),
    ],
)
def test_de_regel_komt_voor_een_lijst_en_voor_een_enkele_string(beantwoordt_niet, afgekapte, verwacht):
    """Het model mag `beantwoordt_niet` als één string geven: die telt als één item, achter de regel (#583)."""
    _pagina()
    spec = _rapport(
        _datasets(_KEY, volledig=not afgekapte),
        beantwoordt_niet=beantwoordt_niet,
    )

    assert spec.beantwoordt_niet == verwacht


@pytest.mark.parametrize("dataset", [{"data_key": _KEY, "volledig": True}, {"data_key": _KEY}])
def test_zonder_afkapping_staat_er_precies_wat_het_model_schreef(dataset):
    _pagina(volledig=dataset.get("volledig", False))

    assert _rapport([dataset], beantwoordt_niet=["Uitval"]).beantwoordt_niet == ["Uitval"]
    assert _rapport([dataset]).beantwoordt_niet == []


def test_de_controle_ziet_de_regel_niet():
    _pagina()
    tekst = json.dumps({"beantwoordt_niet": ["Uitval"], "conclusie": "c"})
    context = {"topic": "Gediplomeerden", "datasets": _datasets(_KEY)}

    spec = report._parse_spec_from_response(tekst, [], context, met_voorbehoud=False)

    assert spec.beantwoordt_niet == ["Uitval"]


def test_de_regel_bepaalt_niet_welke_definities_erbij_komen():
    # Een titel met "opleidingsvorm": in de rapporttekst zou de regel de codelijst erbij halen (#422).
    key = "duo:p01hoinges:3"
    store.put(key, pd.DataFrame({"AANTAL": [5] * 20}), KeyMeta(bron="duo", dataset="p01hoinges", volledig=False))
    datasets = _datasets(key)
    with patch("agent.selectie.bron_titel", return_value="Ingeschrevenen per opleidingsvorm"):
        [regel] = afkappingsregels(datasets, "rapport")
        spec = _rapport(datasets)

    assert spec.beantwoordt_niet == [regel]
    assert any(d["begrip"] == "Opleidingsvorm" for d in definities_uit_bron(datasets, regel))
    assert spec.definities == definities_uit_bron(datasets, "")


# ── Dashboard: na de bronnen ────────────────────────────────────────────────────────────


def _dashboard(context_datasets: list[dict]) -> dashboard.DashboardSpec:
    context = {"topic": "Gediplomeerden", "datasets": context_datasets}
    return dashboard._parse_spec_from_response('{"title": "D"}', [], [], context, {})


def test_het_dashboard_zet_de_regel_na_de_bronnen_uit_code():
    _pagina()

    spec = _dashboard(_datasets(_KEY, f"{_KEY}:abc"))

    [bron, regel] = spec.sources
    assert bron.startswith("CBS — ") and "85425NED" in bron
    assert regel == _REGEL.replace("dit rapport", "dit dashboard")


def test_een_volledig_dashboard_krijgt_geen_regel():
    _pagina(volledig=True)

    [bron] = _dashboard(_datasets(_KEY, volledig=True)).sources

    assert bron.startswith("CBS — ")


# ── De rapportrun: de regel gaat niet langs de controles (#207) ────────────────────────────

_RESULT = json.dumps({"rijen": [{"STUDIEJAAR": 2021 + i, "AANTAL": n} for i, n in enumerate([28355, 27904, 27441])]})
_GOED = json.dumps(
    {
        "onderzoeksvraag": "Hoeveel gediplomeerden?",
        "beantwoordt": ["Gediplomeerden per studiejaar"],
        "beantwoordt_niet": ["Uitval valt buiten dit rapport."],
        "conclusie": "Het aantal daalde van 28.355 in 2021 naar 27.441 in 2023.",
    }
)
_ZONDER_REIKWIJDTE = json.dumps({"conclusie": "Het aantal daalde van 28.355 in 2021 naar 27.441 in 2023."})


def _rapportrun(monkeypatch, antwoord: str) -> tuple[report.ReportSpec, list[dict]]:
    """De rapportrun van test_report_checks op een afgekapte pagina van 5000 rijen: dat getal staat nergens in de
    toolresultaten of de datasetcontext van de run, dus de getalcontrole zou het afkeuren."""
    _pagina()
    stappen = [
        StreamResult(
            text="", tool_calls=[{"id": "q1", "name": "query_data", "arguments": json.dumps({"data_key": _KEY})}]
        ),
        StreamResult(text=antwoord, tool_calls=[]),
        StreamResult(text=antwoord, tool_calls=[]),
    ]
    events: list[dict] = []

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def emit(event: dict) -> None:
        events.append(event)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (_RESULT, None))
    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": _datasets(_KEY)})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")

    spec = asyncio.run(report.generate({}, emit, model="openai/gpt-4o", stop_event=asyncio.Event()))
    return spec, events


def test_een_rapport_op_een_afgekapte_bron_wordt_niet_geweigerd_om_de_regel(monkeypatch):
    spec, events = _rapportrun(monkeypatch, _GOED)

    assert spec.beantwoordt_niet == [_REGEL, "Uitval valt buiten dit rapport."]
    assert [e for e in events if e.get("type") == "toast"] == []


def test_zonder_reikwijdte_van_het_model_blijft_het_rapport_zonder_reikwijdte(monkeypatch):
    """De regel telt niet als reikwijdte: een rapport dat er zelf geen geeft, wordt nog steeds afgekeurd."""
    gevonden: list[str] = []
    origineel = report.report_problems

    def report_problems(*args):
        problemen = origineel(*args)
        gevonden.extend(map(str, problemen))
        return problemen

    monkeypatch.setattr(report, "report_problems", report_problems)

    with pytest.raises(RapportGeweigerd):
        _rapportrun(monkeypatch, _ZONDER_REIKWIJDTE)

    assert "Het rapport heeft geen reikwijdte (beantwoordt / beantwoordt_niet)." in gevonden
