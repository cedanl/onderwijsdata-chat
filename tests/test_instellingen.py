import importlib

import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    import data.instellingen as inst
    inst._cache = None
    inst._alias_lookup = None
    inst._ADRES_CACHE = None
    yield
    inst._cache = None
    inst._alias_lookup = None
    inst._ADRES_CACHE = None


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


# ─── Dashboard HO ────────────────────────────────────────────────────────────

def test_dashboard_ho_found():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Hogeschool Utrecht")
    assert result is not None
    assert "ingeschrevenen" in result
    assert "laatste_jaar" in result
    assert "sectoren" in result
    assert isinstance(result["ingeschrevenen"], dict)
    assert all(isinstance(k, (int, str)) for k in result["ingeschrevenen"])


def test_dashboard_ho_wo_found():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Vrije Universiteit Amsterdam")
    assert result is not None
    assert "ingeschrevenen" in result


def test_dashboard_ho_not_found():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Niet Bestaande Instelling")
    assert result is None


def test_dashboard_ho_has_geslacht():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Hogeschool Utrecht")
    assert "geslacht" in result


# ─── Dashboard MBO ───────────────────────────────────────────────────────────

def test_dashboard_mbo_found():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("ROC Mondriaan")
    assert result is not None
    assert "ingeschrevenen" in result
    assert "laatste_jaar" in result
    assert "sectoren" in result


def test_dashboard_mbo_has_leerwegen():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("ROC Mondriaan")
    assert any(k in result["sectoren"] for k in ("BBL", "BOL voltijd", "BOL deeltijd"))


def test_dashboard_mbo_not_found():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("Niet Bestaande Instelling")
    assert result is None


def test_dashboard_mbo_has_gediplomeerden():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("ROC Mondriaan")
    assert "gediplomeerden" in result


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

def test_load_dashboard_resolves_alias():
    from data.dashboard import load_dashboard
    result = load_dashboard("VU")
    assert result["gevonden"] is True
    assert result["instelling"] == "Vrije Universiteit Amsterdam"


def test_load_dashboard_mbo_via_alias():
    from data.dashboard import load_dashboard
    result = load_dashboard("Mondriaan")
    assert result["gevonden"] is True
    assert result["instelling"] == "ROC Mondriaan"


def test_load_dashboard_not_found_has_suggestions():
    from data.dashboard import load_dashboard
    result = load_dashboard("Niet Bestaande Instelling XYZ")
    assert result["gevonden"] is False
    assert "beschikbare_instellingen" in result
    assert len(result["beschikbare_instellingen"]) > 0


# ─── API endpoint ────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    import core.auth as auth
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
    assert all(i["type"] == "wo" for i in data)
    assert len(data) > 0


def test_api_instellingen_filter_multiple_types(client):
    resp = client.get("/api/instellingen?type=wo,hbo")
    assert resp.status_code == 200
    data = resp.json()
    types = {i["type"] for i in data}
    assert types <= {"wo", "hbo"}
    assert len(types) == 2


def test_api_dashboard_ho(client):
    resp = client.get("/api/dashboard/instroom?instelling=Hogeschool+Utrecht")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True


def test_api_dashboard_alias(client):
    resp = client.get("/api/dashboard/instroom?instelling=VU")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert data["instelling"] == "Vrije Universiteit Amsterdam"


def test_api_dashboard_mbo(client):
    resp = client.get("/api/dashboard/instroom?instelling=ROC+Mondriaan")
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


def test_regio_mbo_has_sectorkamers():
    from data.dashboard import load_dashboard_regio
    result = load_dashboard_regio("ROC Mondriaan")
    assert result["gevonden"] is True
    assert result["type"] == "mbo"
    assert "sectorkamers" in result
    sk = result["sectorkamers"]
    assert isinstance(sk, dict)
    assert len(sk) > 0
    # Keys should be real sector names (not BBL/BOL)
    bbl_bol_keys = {"BBL", "BOL voltijd", "BOL deeltijd"}
    assert not set(sk.keys()).issubset(bbl_bol_keys), "sectorkamers should have real sector names"
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
    for jaar, val in gt.items():
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
    for onderdeel, trend in sl.items():
        assert isinstance(trend, dict)
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
    assert all(isinstance(v, int) and v >= 1 for v in ep.values())


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
    assert all(v in valid_scores for v in ms.values())


def test_dashboard_arbeidsmarktmatch_endpoint(client):
    resp = client.get("/api/dashboard/arbeidsmarktmatch?instelling=ROC+Mondriaan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert "gediplomeerden_per_sector" in data
