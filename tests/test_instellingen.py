import importlib

import pandas as pd
import pytest

# Register en dashboards draaien op bevroren DUO-bestanden, niet op live DUO (#766), en zonder live UWV en ROA (#915).
pytestmark = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")

# De waardetests (#824) rekenen elk getal met pandas na uit dezelfde fixtures, los van data/dashboard.py.
_HU = "Hogeschool Utrecht"
_INST = "INSTELLINGSNAAM_ACTUEEL"


def _duo_ho(dataset_id: str, waardekolom: str) -> pd.DataFrame:
    """Beide resources van een HO-bestand uit de fixtures; DUO's -1 (onderdrukt) telt als 0, zoals het dashboard."""
    from riodata import duo

    df = pd.concat([duo.load(dataset_id, 0), duo.load(dataset_id, 1)], ignore_index=True)
    df[waardekolom] = df[waardekolom].where(df[waardekolom] >= 0, 0)
    return df


def _som_per_jaar(df: pd.DataFrame, jaarkolom: str, waardekolom: str, instelling: str = _HU) -> dict[int, int]:
    rijen = df[df[_INST] == instelling]
    return {int(j): int(v) for j, v in rijen.groupby(jaarkolom)[waardekolom].sum().items()}


# ─── Registry ────────────────────────────────────────────────────────────────


def test_registry_returns_list():
    from data.instellingen import get_all

    result = get_all()
    assert isinstance(result, list)
    assert len(result) > 0


def test_registry_sorted_alphabetically():
    from data.instellingen import get_all

    result = get_all()
    names = [i["naam"] for i in result]
    assert names == sorted(names, key=str.lower)


def test_registry_has_required_fields():
    from data.instellingen import get_all

    for inst in get_all():
        assert "naam" in inst
        assert "type" in inst
        assert "aliassen" in inst
        assert "instellingscode" in inst
        assert "provincie" in inst
        assert "arbeidsmarktregio" in inst
        assert inst["type"] in ("wo", "hbo", "mbo")
        assert isinstance(inst["aliassen"], list)
        assert inst["instellingscodes"][0] == inst["instellingscode"]


def test_registry_most_have_provincie():
    from data.instellingen import get_all

    with_prov = [i for i in get_all() if i["provincie"]]
    assert len(with_prov) >= len(get_all()) - 2


def test_registry_most_have_arbeidsmarktregio():
    from data.instellingen import get_all

    with_amr = [i for i in get_all() if i["arbeidsmarktregio"]]
    assert len(with_amr) >= len(get_all()) - 2


def test_get_adres_lookup_returns_dict():
    from data.instellingen import get_adres_lookup

    lookup = get_adres_lookup()
    assert isinstance(lookup, dict)
    assert len(lookup) > 0
    first = next(iter(lookup.values()))
    assert "provincie" in first
    assert "arbeidsmarktregio" in first


def test_get_adres_lookup_cached():
    from data.instellingen import get_adres_lookup

    assert get_adres_lookup() is get_adres_lookup()


def test_registry_contains_all_types():
    from data.instellingen import get_all

    types = {i["type"] for i in get_all()}
    assert types == {"wo", "hbo", "mbo"}


def test_registry_no_duplicate_names():
    from data.instellingen import get_all

    names = [i["naam"] for i in get_all()]
    assert len(names) == len(set(names))


# ─── Alias resolve ───────────────────────────────────────────────────────────


def test_resolve_exact_name():
    from data.instellingen import resolve_alias

    assert resolve_alias("Hogeschool Utrecht") == "Hogeschool Utrecht"


def test_resolve_case_insensitive():
    from data.instellingen import resolve_alias

    assert resolve_alias("hogeschool utrecht") == "Hogeschool Utrecht"


def test_resolve_known_alias():
    from data.instellingen import resolve_alias

    assert resolve_alias("VU") == "Vrije Universiteit Amsterdam"
    assert resolve_alias("HvA") == "Hogeschool van Amsterdam"
    assert resolve_alias("TU Delft") == "Technische Universiteit Delft"


def test_resolve_alias_case_insensitive():
    from data.instellingen import resolve_alias

    assert resolve_alias("vu") == "Vrije Universiteit Amsterdam"
    assert resolve_alias("hva") == "Hogeschool van Amsterdam"


def test_resolve_mbo_alias():
    from data.instellingen import resolve_alias

    assert resolve_alias("Mondriaan") == "ROC Mondriaan"
    assert resolve_alias("ROC MN") == "ROC Midden Nederland"


def test_resolve_unknown_returns_input():
    from data.instellingen import resolve_alias

    assert resolve_alias("Onbekende Instelling") == "Onbekende Instelling"


def test_resolve_empty_string():
    from data.instellingen import resolve_alias

    assert resolve_alias("") == ""


# ─── Dashboard: de eigen instelling ──────────────────────────────────────────
# Het regiodashboard levert ook de cijfers van de eigen instelling; /api/dashboard/instroom deed dat dubbel en is weg
# (#930).


def test_regio_dashboard_ho_telt_zoals_de_fixture():
    from data.dashboard import load_dashboard_regio

    ins = _duo_ho("p01hoinges", "AANTAL_INGESCHREVENEN")
    result = load_dashboard_regio(_HU)
    assert result["gevonden"] is True
    assert result["type"] == "ho"

    verwacht = _som_per_jaar(ins, "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
    assert verwacht[2025] == 35058  # ijkpunt: HU 2025 in de bevroren fixture
    assert result["ingeschrevenen"] == verwacht
    assert result["laatste_jaar"] == max(verwacht) == 2025

    laatste = ins[(ins[_INST] == _HU) & (ins["STUDIEJAAR"] == 2025)]
    per_sector = laatste.groupby("ONDERDEEL")["AANTAL_INGESCHREVENEN"].sum()
    assert len(per_sector) > 1
    assert result["sectoren"] == {k: int(v) for k, v in per_sector.items()}
    per_geslacht = laatste.groupby("GESLACHT")["AANTAL_INGESCHREVENEN"].sum()
    assert result["geslacht"] == {k: int(v) for k, v in per_geslacht.items()}

    ej = _duo_ho("p02ho1ejrs", "AANTAL_EERSTEJAARS_INGESCHREVENEN")
    assert result["eerstejaars"] == _som_per_jaar(ej, "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN")
    dipl = _duo_ho("p04hogdipl", "AANTAL_GEDIPLOMEERDEN")
    assert result["gediplomeerden"] == _som_per_jaar(dipl, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN")


def test_regio_dashboard_vindt_een_wo_instelling():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Vrije Universiteit Amsterdam")
    assert result["gevonden"] is True
    assert result["ingeschrevenen"]


def test_regio_dashboard_mbo_heeft_leerwegen_en_gediplomeerden():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("ROC Mondriaan")
    assert result["gevonden"] is True
    assert result["type"] == "mbo"
    assert any(k in result["sectoren"] for k in ("BBL", "BOL voltijd", "BOL deeltijd"))
    assert result["gediplomeerden"]


# ─── Dashboard regio ─────────────────────────────────────────────────────────


def test_regio_dashboard_ho_has_arbeidsmarktregio():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Hogeschool Utrecht")
    assert result["gevonden"] is True
    assert "arbeidsmarktregio" in result


def test_regio_dashboard_ho_benchmark_uses_regio():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Hogeschool Utrecht")
    assert result["gevonden"] is True
    bm = result.get("benchmark", {})
    assert bm, "Benchmark verwacht voor Hogeschool Utrecht"
    assert "arbeidsmarktregio" in bm["label"].lower() or "provincie" in bm["label"].lower()


def test_regio_dashboard_mbo_has_arbeidsmarktregio():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("ROC Mondriaan")
    assert result["gevonden"] is True
    assert "arbeidsmarktregio" in result


def test_regio_dashboard_mbo_benchmark_uses_arbeidsmarktregio():
    # Albeda zit in Rijnmond met 7 MBO peers — arbeidsmarktregio verwacht
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Albeda")
    bm = result.get("benchmark", {})
    assert bm, "Benchmark verwacht voor Albeda"
    assert "arbeidsmarktregio" in bm["label"].lower()


def test_regio_dashboard_benchmark_has_regio_type():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Hogeschool Utrecht")
    bm = result.get("benchmark", {})
    assert "regio_type" in bm
    assert bm["regio_type"] in ("arbeidsmarktregio", "provincie")


def test_regio_dashboard_ho_provincie_still_present():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Hogeschool Utrecht")
    assert "provincie" in result
    assert result["provincie"] is not None


# ─── Dashboard composite ─────────────────────────────────────────────────────


def test_regio_dashboard_resolves_alias():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("VU")
    assert result["gevonden"] is True
    assert result["instelling"] == "Vrije Universiteit Amsterdam"


def test_regio_dashboard_mbo_via_alias():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Mondriaan")
    assert result["gevonden"] is True
    assert result["instelling"] == "ROC Mondriaan"


# ─── API endpoint ────────────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch, dashboards_aan):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    from fastapi.testclient import TestClient

    return TestClient(server.app)


def test_api_instellingen_returns_list(client):
    resp = client.get("/api/instellingen")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_instellingen_filter_by_type(client):
    resp = client.get("/api/instellingen?type=wo")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert all(i["type"] == "wo" for i in data)


def test_api_instellingen_filter_multiple_types(client):
    resp = client.get("/api/instellingen?type=wo,hbo")
    assert resp.status_code == 200
    data = resp.json()
    types = {i["type"] for i in data}
    assert types <= {"wo", "hbo"}
    assert len(types) == 2


def test_api_dashboard_ho(client):
    resp = client.get("/api/dashboard/regio?instelling=Hogeschool+Utrecht")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True


def test_api_dashboard_alias(client):
    resp = client.get("/api/dashboard/regio?instelling=VU")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert data["instelling"] == "Vrije Universiteit Amsterdam"


def test_api_dashboard_mbo(client):
    resp = client.get("/api/dashboard/regio?instelling=ROC+Mondriaan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True


# ─── Task 2: MBO regio improvements ─────────────────────────────────────────


def test_regio_mbo_has_eerstejaars():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("ROC Mondriaan")
    assert result["gevonden"] is True
    assert result["type"] == "mbo"
    assert "eerstejaars" in result
    ej = result["eerstejaars"]
    assert isinstance(ej, dict)
    assert len(ej) > 0
    # Values must be positive integers
    assert all(isinstance(v, int) and v > 0 for v in ej.values())
    # Benchmark should also carry eerstejaars
    if "benchmark" in result:
        bm = result["benchmark"]
        assert "eerstejaars" in bm
        assert isinstance(bm["eerstejaars"], dict)
        assert "peers" in bm
        assert "eerstejaars" in bm["peers"]


def test_regio_mbo_has_ingeschrevenen_per_hoofdgroep():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("ROC Mondriaan")
    assert result["gevonden"] is True
    assert result["type"] == "mbo"
    # Heette "sectorkamers"; TOTAAL MBO telt ingeschrevenen per DUO-hoofdgroep (#899).
    sk = result["ingeschrevenen_per_hoofdgroep"]
    assert isinstance(sk, dict)
    assert len(sk) > 0
    # Keys should be real sector names (not BBL/BOL)
    bbl_bol_keys = {"BBL", "BOL voltijd", "BOL deeltijd"}
    assert not set(sk.keys()).issubset(bbl_bol_keys), "hoofdgroepen should have real sector names"
    # Values should be positive integers
    assert all(isinstance(v, int) and v > 0 for v in sk.values())
    # Legacy sectoren (leerwegen) must still be present for backward compat
    assert "sectoren" in result


# ─── Task 3: HO regio improvements ───────────────────────────────────────────


def test_regio_ho_has_geslacht_trend():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Hogeschool Utrecht")
    assert result["gevonden"] is True
    assert result["type"] == "ho"
    assert "geslacht_trend" in result
    gt = result["geslacht_trend"]
    assert isinstance(gt, dict)
    assert len(gt) > 0
    # Each year should have VROUW and MAN
    for _jaar, val in gt.items():
        assert isinstance(val, dict)
        assert "VROUW" in val
        assert "MAN" in val
        assert isinstance(val["VROUW"], int)
        assert isinstance(val["MAN"], int)


# ─── Task 4: Nationaal Marktaandeel ──────────────────────────────────────────


def test_dashboard_nationaal_ho():
    from data.dashboard import load_dashboard_nationaal

    result = load_dashboard_nationaal("Hogeschool Utrecht")
    assert result["gevonden"] is True
    assert result["type"] == "ho"
    assert "instelling" in result
    assert "laatste_jaar" in result

    # sectoren_landelijk: {onderdeel: {jaar: int}}
    assert "sectoren_landelijk" in result
    sl = result["sectoren_landelijk"]
    assert isinstance(sl, dict)
    assert len(sl) > 0
    for _onderdeel, trend in sl.items():
        assert isinstance(trend, dict)
        assert trend
        assert all(isinstance(v, int) for v in trend.values())

    # eigen_sectoren: {onderdeel: {jaar: int}}
    assert "eigen_sectoren" in result
    es = result["eigen_sectoren"]
    assert isinstance(es, dict)
    assert len(es) > 0

    # alle_instellingen: [{naam, ingeschrevenen, type}] for laatste_jaar
    assert "alle_instellingen" in result
    ai = result["alle_instellingen"]
    assert isinstance(ai, list)
    assert len(ai) > 0
    for item in ai:
        assert "naam" in item
        assert "ingeschrevenen" in item
        assert "type" in item

    # eigen_positie: {onderdeel: int} (1-based rank)
    assert "eigen_positie" in result
    ep = result["eigen_positie"]
    assert isinstance(ep, dict)
    assert ep
    assert all(isinstance(v, int) and v >= 1 for v in ep.values())


def test_dashboard_nationaal_telt_en_rangschikt_zoals_de_fixture():
    from data.dashboard import load_dashboard_nationaal

    ins = _duo_ho("p01hoinges", "AANTAL_INGESCHREVENEN")
    result = load_dashboard_nationaal(_HU)

    landelijk = ins.groupby(["ONDERDEEL", "STUDIEJAAR"])["AANTAL_INGESCHREVENEN"].sum()
    verwacht_landelijk: dict[str, dict[int, int]] = {}
    for (onderdeel, jaar), waarde in landelijk.items():
        verwacht_landelijk.setdefault(onderdeel, {})[int(jaar)] = int(waarde)
    assert verwacht_landelijk
    assert result["sectoren_landelijk"] == verwacht_landelijk
    assert result["laatste_jaar"] == 2025

    laatste = ins[ins["STUDIEJAAR"] == 2025]
    per_inst = laatste.groupby(_INST)["AANTAL_INGESCHREVENEN"].sum()
    assert int(per_inst[_HU]) == 35058  # ijkpunt, gelijk aan het regiodashboard
    alle = result["alle_instellingen"]
    assert {i["naam"]: i["ingeschrevenen"] for i in alle} == {k: int(v) for k, v in per_inst.items()}
    aantallen = [i["ingeschrevenen"] for i in alle]
    assert aantallen == sorted(aantallen, reverse=True)

    # Positie per onderdeel: 1 + het aantal instellingen met meer ingeschrevenen in dat onderdeel. Bij een gelijke
    # stand met HU is de volgorde niet bepaald; die onderdelen slaat de test over.
    verwacht_positie = {}
    for onderdeel, groep in laatste.groupby("ONDERDEEL"):
        sommen = groep.groupby(_INST)["AANTAL_INGESCHREVENEN"].sum()
        if _HU not in sommen.index or (sommen == sommen[_HU]).sum() > 1:
            continue
        verwacht_positie[onderdeel] = 1 + int((sommen > sommen[_HU]).sum())
    assert verwacht_positie
    assert {o: p for o, p in result["eigen_positie"].items() if o in verwacht_positie} == verwacht_positie


def test_dashboard_nationaal_endpoint(client):
    resp = client.get("/api/dashboard/nationaal?instelling=Hogeschool+Utrecht")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert "sectoren_landelijk" in data


# ─── Task 5: Rendementsmonitor ────────────────────────────────────────────────


def test_dashboard_rendement_ho():
    from data.dashboard import load_dashboard_rendement

    result = load_dashboard_rendement("Hogeschool Utrecht")
    assert result["gevonden"] is True
    assert result["type"] == "ho"
    assert "instelling" in result
    assert "laatste_jaar" in result

    # pseudo_cohorten: [{instroom_jaar, instroom, gediplomeerden_t3, gediplomeerden_t4, gediplomeerden_t5}]
    assert "pseudo_cohorten" in result
    pc = result["pseudo_cohorten"]
    assert isinstance(pc, list)
    assert len(pc) > 0
    for cohort in pc:
        assert "instroom_jaar" in cohort
        assert "instroom" in cohort
        assert "gediplomeerden_t3" in cohort
        assert "gediplomeerden_t4" in cohort
        assert "gediplomeerden_t5" in cohort

    # rendement_per_jaar: {jaar: float}
    assert "rendement_per_jaar" in result
    ry = result["rendement_per_jaar"]
    assert isinstance(ry, dict)
    assert len(ry) > 0
    for v in ry.values():
        assert isinstance(v, float)
        assert 0.0 <= v <= 1.0

    # sector_rendement: {onderdeel: float} (HO only)
    assert "sector_rendement" in result
    sr = result["sector_rendement"]
    assert isinstance(sr, dict)

    # benchmark_rendement: {jaar: float}
    assert "benchmark_rendement" in result
    br = result["benchmark_rendement"]
    assert isinstance(br, dict)

    # peers_rendement: {naam: {jaar: float}}
    assert "peers_rendement" in result
    pr = result["peers_rendement"]
    assert isinstance(pr, dict)


def test_dashboard_rendement_ho_rekent_de_cohorten_zoals_de_fixture():
    from data.dashboard import load_dashboard_rendement

    ej = _som_per_jaar(
        _duo_ho("p02ho1ejrs", "AANTAL_EERSTEJAARS_INGESCHREVENEN"), "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"
    )
    dipl = _som_per_jaar(_duo_ho("p04hogdipl", "AANTAL_GEDIPLOMEERDEN"), "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN")
    result = load_dashboard_rendement(_HU)

    cohorten = {c["instroom_jaar"]: c for c in result["pseudo_cohorten"]}
    assert cohorten
    assert {j: c["instroom"] for j, c in cohorten.items()} == ej
    for jaar, cohort in cohorten.items():
        for t in (3, 4, 5):
            # Een diplomajaar dat er (nog) niet is, is None, geen 0 (#902).
            assert cohort[f"gediplomeerden_t{t}"] == dipl.get(jaar + t), (jaar, t)

    # Rendement na 3 jaar: gediplomeerden in jaar+3 gedeeld door de instroom, alleen als dat niet boven 1 komt.
    verwacht = {j: round(dipl[j + 3] / ej[j], 4) for j in ej if 0 < dipl.get(j + 3, 0) <= ej[j]}
    assert verwacht == {2021: round(6438 / 7108, 4)}  # ijkpunt: instroom 2021, diploma's 2024
    assert result["rendement_per_jaar"] == verwacht


def test_dashboard_rendement_endpoint(client):
    resp = client.get("/api/dashboard/rendement?instelling=Hogeschool+Utrecht")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert "pseudo_cohorten" in data


# ─── Task 6: Arbeidsmarktmatch ────────────────────────────────────────────────


def test_dashboard_arbeidsmarktmatch():
    from data.dashboard import load_dashboard_arbeidsmarktmatch

    result = load_dashboard_arbeidsmarktmatch("ROC Mondriaan")
    assert result["gevonden"] is True
    assert "instelling" in result
    assert "provincie" in result
    assert "laatste_jaar" in result
    assert "arbeidsmarktregio" in result

    # gediplomeerden_per_sector: {onderdeel: int}
    assert "gediplomeerden_per_sector" in result
    gps = result["gediplomeerden_per_sector"]
    assert isinstance(gps, dict)
    assert len(gps) > 0
    assert all(isinstance(v, int) for v in gps.values())

    # vacatures_per_cluster: {cluster: int}
    assert "vacatures_per_cluster" in result
    vpc = result["vacatures_per_cluster"]
    assert isinstance(vpc, dict)

    # vacatures_per_sector: {onderdeel: int}, gedeelde clusters naar rato (#455)
    vps = result["vacatures_per_sector"]
    assert vps
    assert set(vps) <= set(gps)
    assert all(isinstance(v, int) for v in vps.values())

    # roa_per_niveau: {niveau: {werkloosheid, vast_dienstverband, buiten_vakrichting}}
    assert "roa_per_niveau" in result

    # sector_cluster_mapping: {onderdeel: [cluster]}
    assert "sector_cluster_mapping" in result
    scm = result["sector_cluster_mapping"]
    assert isinstance(scm, dict)

    # match_score: {onderdeel: "schaarste"|"evenwicht"|"overaanbod"|null}
    assert "match_score" in result
    ms = result["match_score"]
    assert isinstance(ms, dict)
    valid_scores = {"schaarste", "evenwicht", "overaanbod", None}
    assert ms
    assert all(v in valid_scores for v in ms.values())


def test_dashboard_arbeidsmarktmatch_endpoint(client):
    resp = client.get("/api/dashboard/arbeidsmarktmatch?instelling=ROC+Mondriaan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert "gediplomeerden_per_sector" in data


@pytest.mark.parametrize(
    ("invoer", "naam"),
    [
        ("de VU", "Vrije Universiteit Amsterdam"),
        ("VU Amsterdam", "Vrije Universiteit Amsterdam"),
        ("het Deltion", "Deltion College"),
        ("Codarts", "Codarts, Hogeschool voor de Kunsten"),
        ("Graafschap College", "ROC Graafschap College"),
        ("De Haagse Hogeschool", "De Haagse Hogeschool"),  # het lidwoord is hier deel van de naam
        ("haagse", "De Haagse Hogeschool"),
    ],
)
def test_aliassen_en_lidwoorden_uit_de_audit(invoer, naam):
    """#631: 'de VU', 'VU Amsterdam', 'Codarts' en 'Graafschap College' waren onbekend in get_maat."""
    from data.instellingen import instellingsprofiel, resolve_alias

    assert resolve_alias(invoer) == naam
    profiel = instellingsprofiel(invoer)
    assert profiel is not None and profiel["naam"] == naam


def test_een_onbekende_naam_blijft_onbekend_ook_met_lidwoord():
    from data.instellingen import instellingsprofiel, resolve_alias

    assert resolve_alias("de Hogeschool van Narnia") == "de Hogeschool van Narnia"
    assert instellingsprofiel("de Hogeschool van Narnia") is None


# ─── Zoeken op instellingscode (#929) ────────────────────────────────────────


@pytest.mark.parametrize(("code", "naam"), [("25DW", _HU), ("25dw", _HU), ("27gz", "ROC Mondriaan")])
def test_regio_dashboard_vindt_de_instelling_op_haar_code(code, naam):
    from data.dashboard import load_dashboard_regio

    op_code = load_dashboard_regio(code)
    assert op_code["gevonden"] is True
    assert op_code == load_dashboard_regio(naam)


def test_regio_dashboard_zonder_suggesties_zegt_waarom():
    from data.dashboard import load_dashboard_regio

    result = load_dashboard_regio("Niet Bestaande Instelling XYZ")
    assert result["gevonden"] is False
    assert result["beschikbare_instellingen"] == []
    assert "instellingscode" in result["geen_suggesties"]


def test_regio_dashboard_met_suggesties_geeft_geen_reden():
    from data.dashboard import load_dashboard_regio

    # De dichtstbijzijnde namen, niet de eerste van het alfabet (#901).
    result = load_dashboard_regio("Hogeschool Utrect")
    assert result["gevonden"] is False
    assert result["beschikbare_instellingen"][0] == _HU
    assert "geen_suggesties" not in result


def test_api_dashboard_regio_op_code(client):
    resp = client.get("/api/dashboard/regio?instelling=25dw")
    assert resp.status_code == 200
    assert resp.json()["gevonden"] is True
    assert resp.json()["instelling"] == _HU
