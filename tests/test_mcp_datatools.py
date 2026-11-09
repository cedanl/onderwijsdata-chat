"""Sessieloze datatools van de MCP-server (#708): dezelfde uitkomst als dezelfde vraag in de chat.

De bronnen zijn de bevroren DUO-bestanden van de gouden tests (fixture `gouden`, #870, netwerk dicht) met het echte
instellingenregister. Per opleiding staat er een klein niveaubestand in de vorm van DUO p01hoinges bestand 5 naast.

De vergelijkingstest legt de uitkomst van de MCP-tool naast het toolpad van de chat voor dezelfde vraag, zonder
taalmodel: `get_maat` (of bij een opleiding `get_duo_data` en `query_data`, stap 1 tot 4 van de prompt) en daarna
`compute_kpi` via `tools.dispatch`, met een lege store ertussen zodat de chat zelf laadt en rekent.
"""

import json

import pandas as pd
import pytest

import mcp_server
import tools
from tools import kernvragen, store
from tools.schemas import TOOL_SCHEMAS

UU, ROC = "Universiteit Utrecht", "ROC Mondriaan"
MBO = ["Albeda", "Zadkine", ROC]
_KOLOMMEN = [
    "STUDIEJAAR", "PROVINCIENAAM", "GEMEENTENUMMER", "GEMEENTENAAM", "SOORT_INSTELLING", "TYPE_HOGER_ONDERWIJS",
    "INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL", "ONDERDEEL", "SUBONDERDEEL", "OPLEIDINGSCODE_ACTUEEL",
    "OPLEIDINGSNAAM_ACTUEEL", "AANTAL_INGESCHREVENEN",
]  # fmt: skip
_B_RECHT, _M_RECHT, _GENEESKUNDE = (
    ("50400", "B Rechtsgeleerdheid"),
    ("60400", "M Rechtsgeleerdheid"),
    ("56551", "B Geneeskunde"),
)


def _rij(jaar, opleiding, aantal, onderdeel="RECHT", instelling=("21PD", UU)):
    return (jaar, "Utrecht", "0344", "Utrecht", "reguliere inst.", "bachelor", *instelling, onderdeel, "n.v.t.",
            *opleiding, aantal)  # fmt: skip


# B Rechtsgeleerdheid van de UU: 2021 één rij; 2022 twee rijen (1250 + 30); 2023 een onderdrukte cel naast 1300.
# Dezelfde opleiding bij een andere instelling telt niet mee.
_NIVEAU_WO = pd.DataFrame(
    [
        _rij(2021, _B_RECHT, 1200),
        _rij(2021, _M_RECHT, 400),
        _rij(2021, _GENEESKUNDE, 1800, onderdeel="GEZONDHEIDSZORG"),
        _rij(2022, _B_RECHT, 1250),
        _rij(2022, _B_RECHT, 30, onderdeel="TAAL_EN_CULTUUR"),
        _rij(2023, _B_RECHT, 1300),
        _rij(2023, _B_RECHT, -1, onderdeel="TAAL_EN_CULTUUR"),
        _rij(2023, _B_RECHT, 999, instelling=("21PK", "Universiteit van Amsterdam")),
    ],
    columns=_KOLOMMEN,
)


@pytest.fixture(autouse=True)
def _niveaubestand(gouden, monkeypatch):
    """Het niveaubestand wo van p01hoinges naast de gouden bestanden; de rest laadt zoals de fixture `gouden`."""
    from onderwijsbronnen import duo

    gouden = duo.load

    def load(dataset_id: str, resource: int = 0, **kwargs) -> pd.DataFrame:
        if (dataset_id, resource) == ("p01hoinges", 5):
            df = _NIVEAU_WO.copy()
            # Zoals riodata: de herkomst van het bestand, waar de versie in het bewijs uit komt (#717).
            df.attrs["bron"] = {"dataset_id": dataset_id, "last_modified": "2026-04-08T12:55:00"}
            return df
        return gouden(dataset_id, resource, **kwargs)

    monkeypatch.setattr(duo, "load", load)
    store.clear()
    yield
    store.clear()


def _mcp(naam: str, argumenten: dict) -> dict:
    tekst, fout = mcp_server.voer_uit(naam, argumenten)
    assert not fout, tekst
    return json.loads(tekst)


def _fout(naam: str, argumenten: dict) -> str:
    tekst, fout = mcp_server.voer_uit(naam, argumenten)
    assert fout, tekst
    return tekst


def _per_jaar(reeks: list[dict]) -> dict[str, int | None]:
    return {r["schooljaar"]: r["aantal"] for r in reeks}


# ── Het toolpad van de chat voor dezelfde vraag ─────────────────────────────────────────────────────────────────────


def _dispatch(naam: str, argumenten: dict) -> dict:
    tekst, _ = tools.dispatch(naam, argumenten)
    uit = json.loads(tekst)
    assert "data_key" in uit or "raw" in uit, tekst
    return uit


def _chat_verloop(key: str, kolom: str, periodekolom: str) -> dict:
    args = {"data_key": key, "value_column": kolom, "sort_column": periodekolom}
    delta = _dispatch("compute_kpi", {**args, "metric": "delta"})
    procent = _dispatch("compute_kpi", {**args, "metric": "pct_change"})
    return {**delta["periode"], "verschil": delta["raw"], "procentuele_verandering": procent["value"]}


def _chat_maat(**argumenten) -> tuple[dict[str, int | None], dict]:
    """get_maat en compute_kpi, zoals de chat een telvraag per instelling beantwoordt (prompt, stap 0)."""
    store.clear()
    uit = _dispatch("get_maat", argumenten)
    kolom, waarde = uit["periodekolom"], uit["waardekolom"]
    per_jaar = {f"{r[kolom]}/{(r[kolom] + 1) % 100:02d}": r[waarde] for r in uit["rijen"]}
    return per_jaar, _chat_verloop(uit["data_key"], waarde, kolom)


def _chat_opleiding(instellingscode: str, opleidingscode: str) -> tuple[dict[str, int | None], dict]:
    """Zonder vaste maat volgt de chat stap 1 tot 4: het niveaubestand laden en filteren en optellen met query_data."""
    store.clear()
    geladen = _dispatch("get_duo_data", {"dataset_id": "p01hoinges", "resource": 5})
    filters = {"INSTELLINGSCODE_ACTUEEL": instellingscode, "OPLEIDINGSCODE_ACTUEEL": opleidingscode}
    gekozen = _dispatch(
        "query_data",
        {
            "data_key": geladen["data_key"],
            "filters": filters,
            "group_by": ["STUDIEJAAR"],
            "aggregate": {"AANTAL_INGESCHREVENEN": "sum"},
        },
    )
    per_jaar = {
        f"{r['STUDIEJAAR']}/{(r['STUDIEJAAR'] + 1) % 100:02d}": r["AANTAL_INGESCHREVENEN"] for r in gekozen["rijen"]
    }
    return per_jaar, _chat_verloop(gekozen["data_key"], "AANTAL_INGESCHREVENEN", "STUDIEJAAR")


# ── Vergelijkingstest: dezelfde vraag in de chat (acceptatie #708) ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argumenten", "chat"),
    [
        ({"instelling": UU, "vorm": "voltijd"}, {"maat": "ingeschreven_personen_ho", "instelling": UU, "vorm": "voltijd"}),
        ({"instelling": UU}, {"maat": "ingeschreven_personen_ho", "instelling": UU}),
        ({"instelling": "uu", "telling": "eerstejaars", "vorm": "voltijd"}, {"maat": "eerstejaars_ho", "instelling": UU, "vorm": "voltijd"}),
        ({"instelling": "21PD", "telling": "inschrijvingen", "vorm": "voltijd"}, {"maat": "inschrijvingen_ho", "instelling": UU, "vorm": "voltijd"}),
        ({"instelling": ROC, "vorm": "bol"}, {"maat": "mbo_studenten_instelling", "instelling": ROC, "vorm": "bol"}),
        ({"instelling": ROC, "schooljaren": ["2022/23", "2025"]}, {"maat": "mbo_studenten_instelling", "instelling": ROC, "schooljaren": ["2022/23", "2025"]}),
    ],
    ids=["uu-voltijd", "uu-alle", "uu-eerstejaars-alias", "uu-inschrijvingen-brin", "roc-bol", "roc-twee-jaren"],
)  # fmt: skip
def test_aantallen_per_jaar_is_dezelfde_uitkomst_als_de_chat(argumenten, chat):
    uit = _mcp("aantallen_per_jaar", argumenten)
    per_jaar, verloop = _chat_maat(**chat)

    assert _per_jaar(uit["reeks"]) == per_jaar
    assert uit["verloop"] == verloop
    assert uit["teldefinitie"] == _dispatch("get_maat", chat)["teldefinitie"]


def test_de_uitkomst_staat_vast_bij_de_bevroren_bron():
    """De getallen uit tests/test_gouden_maten.py (met pandas nagerekend), nu via MCP: UU voltijd, 2021/22 tot 2025/26."""
    uit = _mcp("aantallen_per_jaar", {"instelling": UU, "vorm": "voltijd"})

    assert [r["aantal"] for r in uit["reeks"]] == [36534, 37317, 37910, 37357, 36769]
    assert uit["verloop"] == {"van": "2021/22", "tot": "2025/26", "verschil": 235, "procentuele_verandering": "+0,6%"}


def test_per_opleiding_is_dezelfde_uitkomst_als_de_chat():
    uit = _mcp("aantallen_per_jaar", {"instelling": UU, "opleiding": "B Rechtsgeleerdheid"})
    per_jaar, verloop = _chat_opleiding("21PD", "50400")

    assert uit["opleiding"] == {"code": "50400", "naam": "B Rechtsgeleerdheid"}
    assert _per_jaar(uit["reeks"]) == per_jaar == {"2021/22": 1200, "2022/23": 1280, "2023/24": 1300}
    assert uit["verloop"] == verloop
    assert any("-1" in regel for regel in uit["databewerking"]), "de onderdrukte cel van 2023 staat erbij"


def test_vergelijk_instellingen_is_per_instelling_dezelfde_uitkomst_als_de_chat():
    uit = _mcp("vergelijk_instellingen", {"instellingen": MBO, "vorm": "bbl"})

    for naam, deel in zip(MBO, uit["instellingen"], strict=True):
        per_jaar, verloop = _chat_maat(maat="mbo_studenten_instelling", instelling=naam, vorm="bbl")
        assert deel["instelling"]["naam"] == naam
        assert _per_jaar(deel["reeks"]) == per_jaar
        assert deel["verloop"] == verloop


def test_de_volgorde_is_die_van_het_laatste_jaar_dat_elke_instelling_heeft():
    uit = _mcp("vergelijk_instellingen", {"instellingen": MBO, "vorm": "bbl"})
    laatste = {d["instelling"]["naam"]: d["reeks"][-1]["aantal"] for d in uit["instellingen"]}

    volgorde = uit["volgorde"]
    assert volgorde["schooljaar"] == "2025/26"
    assert [(r["plaats"], r["naam"], r["aantal"]) for r in volgorde["instellingen"]] == [
        (i, naam, laatste[naam]) for i, naam in enumerate(sorted(laatste, key=lambda n: -laatste[n]), start=1)
    ]


def test_vergelijken_per_opleiding():
    uit = _mcp("vergelijk_instellingen", {"instellingen": [UU, "Universiteit van Amsterdam"], "opleiding": "50400"})
    per_code = {d["instelling"]["instellingscode"]: _per_jaar(d["reeks"]) for d in uit["instellingen"]}

    assert per_code == {"21PD": {"2021/22": 1200, "2022/23": 1280, "2023/24": 1300}, "21PK": {"2023/24": 999}}
    assert uit["volgorde"]["schooljaar"] == "2023/24"


def test_dezelfde_vraag_geeft_dezelfde_uitkomst():
    argumenten = {"instellingen": MBO}
    eerste = mcp_server.voer_uit("vergelijk_instellingen", argumenten)
    store.clear()
    assert mcp_server.voer_uit("vergelijk_instellingen", argumenten) == eerste


# ── Envelope: bewijs, vervolg, geen data_key ────────────────────────────────────────────────────────────────────────


def _sleutels(waarde):
    if isinstance(waarde, dict):
        for k, w in waarde.items():
            yield k
            yield from _sleutels(w)
    elif isinstance(waarde, list):
        for w in waarde:
            yield from _sleutels(w)


@pytest.mark.parametrize(
    ("naam", "argumenten"),
    [
        ("aantallen_per_jaar", {"instelling": UU, "vorm": "voltijd"}),
        ("aantallen_per_jaar", {"instelling": UU, "opleiding": "50400"}),
        ("vergelijk_instellingen", {"instellingen": MBO}),
    ],
)
def test_elk_resultaat_heeft_bewijs_en_vervolg_en_geen_data_key(naam, argumenten):
    uit = _mcp(naam, argumenten)

    assert list(uit["bewijs"]) == list(mcp_server.BEWIJS_SLEUTELS)
    assert uit["bewijs"]["bron"] == "DUO"
    assert uit["bewijs"]["maat"] == uit["teldefinitie"]
    assert uit["bewijs"]["verwijzing"].startswith("https://onderwijsdata.duo.nl/dataset/")
    assert "versie van" in uit["bewijs"]["versie"]
    assert uit["vervolg"]["url"].startswith(f"{mcp_server.STANDAARD_APP_URL}/chat#vraag=")
    assert "data_key" not in set(_sleutels(uit)), "sessieloos: geen key naar buiten"


def test_het_bewijs_noemt_het_recept_van_de_chat():
    bewijs = _mcp("aantallen_per_jaar", {"instelling": UU, "opleiding": "50400"})["bewijs"]

    assert bewijs["dataset_id"] == "p01hoinges"
    assert bewijs["selectie"]["bestand"] == 5
    assert bewijs["selectie"]["filters"] == {"INSTELLINGSCODE_ACTUEEL": "21PD", "OPLEIDINGSCODE_ACTUEEL": "50400"}


def test_de_link_stelt_dezelfde_vraag_in_de_volledige_app():
    import urllib.parse

    uit = _mcp("vergelijk_instellingen", {"instellingen": MBO, "vorm": "bbl"})
    vraag = urllib.parse.parse_qs(urllib.parse.urlsplit(uit["vervolg"]["url"]).fragment)["vraag"][0]
    assert vraag == "Vergelijk het aantal studenten bbl van Albeda, Zadkine en ROC Mondriaan per studiejaar."


def test_de_datatools_staan_niet_in_de_chat():
    """Alleen de MCP-server biedt ze: de chat houdt zijn eigen toolset (#707, geen gedragswijziging van de chat)."""
    chat = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert not chat & set(kernvragen.TOOLS)
    assert not tools._HANDLERS.keys() & set(kernvragen.TOOLS)


# ── Grenzen ─────────────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("instelling", ["Amadeus Lyceum voor Vwo Havo Mavo", "00RO"], ids=["vo-naam", "vo-brin"])
def test_buiten_scope_vo_is_een_fout_zonder_gok(instelling):
    for naam, argumenten in (
        ("aantallen_per_jaar", {"instelling": instelling}),
        ("vergelijk_instellingen", {"instellingen": [instelling, ROC]}),
    ):
        tekst = _fout(naam, argumenten)
        assert "alleen mbo-, hbo- en wo-instellingen" in tekst
        assert "bewijs" not in tekst


def test_onbekende_instelling_is_een_fout_die_haar_noemt():
    tekst = _fout("vergelijk_instellingen", {"instellingen": [ROC, "Hogeschool Nergens"]})
    assert "'Hogeschool Nergens'" in tekst and "Geen gok" in tekst


@pytest.mark.parametrize(
    ("naam", "argumenten", "melding"),
    [
        ("aantallen_per_jaar", {"instelling": ROC, "telling": "eerstejaars"}, "alleen studenten"),
        ("aantallen_per_jaar", {"instelling": ROC, "telling": "leerlingen"}, "ken ik niet"),
        ("aantallen_per_jaar", {"instelling": ROC, "opleiding": "Verpleegkunde"}, "alleen bij een hbo- of wo-instelling"),
        ("aantallen_per_jaar", {"instelling": UU, "opleiding": "50400", "vorm": "voltijd"}, "geen opleidingsvorm"),
        ("aantallen_per_jaar", {"instelling": UU, "vorm": "bol"}, "past niet bij"),
        ("aantallen_per_jaar", {"instelling": UU, "schooljaren": ["2010"]}, "Geen van de gevraagde schooljaren"),
        ("aantallen_per_jaar", {"instelling": UU, "opleiding": "Rechtsgeleerdheid"}, "B Rechtsgeleerdheid (50400)"),
        ("vergelijk_instellingen", {"instellingen": [ROC, UU]}, "Mbo en hbo/wo vergelijk ik niet"),
        ("vergelijk_instellingen", {"instellingen": [ROC, "roc mondriaan", "27GZ"]}, "dit zijn er 1"),
        ("vergelijk_instellingen", {"instellingen": "ROC Mondriaan"}, "als een lijst"),
    ],
    ids=["mbo-eerstejaars", "telling", "mbo-opleiding", "opleiding-met-vorm", "vorm", "schooljaar", "twee-opleidingen",
         "mbo-met-ho", "dubbel", "geen-lijst"],
)  # fmt: skip
def test_een_vraag_buiten_wat_de_tool_kan_is_een_melding(naam, argumenten, melding):
    assert melding in _fout(naam, argumenten)


def test_te_veel_instellingen_wordt_geweigerd_voor_er_iets_geladen_is(monkeypatch):
    from onderwijsbronnen import duo

    geladen = []
    monkeypatch.setattr(duo, "load", lambda *a, **k: geladen.append(a))
    namen = [f"instelling {i}" for i in range(kernvragen.MAX_INSTELLINGEN + 1)]

    tekst = _fout("vergelijk_instellingen", {"instellingen": namen})

    assert f"hooguit {kernvragen.MAX_INSTELLINGEN}" in tekst
    assert geladen == []


def test_een_toolfout_noemt_de_uitzondering_niet(monkeypatch):
    def kapot(**_):
        raise RuntimeError("geheim argument")

    monkeypatch.setitem(kernvragen._UITVOERING, "aantallen_per_jaar", kapot)
    tekst = _fout("aantallen_per_jaar", {"instelling": UU})
    assert "toolfout" in tekst and "geheim" not in tekst


def test_een_parameter_buiten_het_schema_is_een_fout():
    assert "onbekende parameter: data_key" in _fout("aantallen_per_jaar", {"instelling": UU, "data_key": "x"})


def test_een_vergelijking_van_zeven_instellingen_past_binnen_de_grens_van_mcp():
    """Het gedeelde recept staat één keer in het bewijs, een noot die elke instelling heeft één keer bovenaan; een
    instelling met eigen noten (Grafisch Lyceum: onderdrukte cellen in de selectie, een ondergrens) houdt die zelf."""
    from routes.mcp_http import MCP_MAX_TEKENS

    zeven = ["Albeda", "Deltion College", "Grafisch Lyceum R'dam", "ROC Graafschap College", "ROC Midden Nederland"]
    tekst, fout = mcp_server.voer_uit("vergelijk_instellingen", {"instellingen": [*zeven, "ROC Mondriaan", "Zadkine"]})

    assert not fout, tekst
    assert len(tekst) < MCP_MAX_TEKENS
    uit = json.loads(tekst)
    per_naam = {d["instelling"]["naam"]: d for d in uit["instellingen"]}
    assert any("ondergrens" in regel for regel in per_naam["Grafisch Lyceum R'dam"]["databewerking"])
    selectie = uit["bewijs"]["selectie"]
    assert selectie["dataset"] == "mbo-studenten-per-instelling" and selectie["bestand"] == 0
    assert selectie["per_instelling"]["27GZ"] == {"filters": {"INSTELLINGSCODE": "27GZ"}}


def test_een_noot_van_elke_instelling_staat_een_keer_bovenaan():
    uit = _mcp("vergelijk_instellingen", {"instellingen": MBO})

    assert len(uit["databewerking"]) == 1 and "in de hele resource" in uit["databewerking"][0]
    assert all("databewerking" not in d for d in uit["instellingen"])
