"""Het bronblok van een dashboard: per bron wat het dashboard echt laadde, met editie, peildatum en voorlopig (#904).

Eerder stonden de bronnen als vaste lijst in de frontend: zonder editie, zonder peildatum, en niet per se wat de
pagina gebruikte.
"""

from datetime import UTC, datetime

import onderwijsbronnen
import pytest
from onderwijsbronnen import duo

import data.dashboard as dashboard
from core import actualiteit
from data import arbeidsmarkt, bronblok
from tools import scopeprofiel

pytestmark = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")

_HU = "Hogeschool Utrecht"
_MONDRIAAN = "ROC Mondriaan"
_NU = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def klok(monkeypatch):
    monkeypatch.setattr(actualiteit, "nu", lambda: _NU)


@pytest.fixture
def bronversie(monkeypatch):
    """De DUO-fixtures met de versie die riodata in df.attrs["bron"] zet (#717): resource-ID en last_modified."""
    fixtures = duo.load

    def load(dataset_id, resource=0, **kwargs):
        df = fixtures(dataset_id, resource, **kwargs)
        df.attrs["bron"] = {
            "dataset_id": dataset_id,
            "resource_id": f"{dataset_id}-r{resource}",
            "last_modified": "2026-04-08T03:04:43.123456",
            "md5": "0" * 32,
        }
        return df

    monkeypatch.setattr(duo, "load", load)


def _per_dataset(result: dict) -> dict[str, dict]:
    return {b["dataset"]: b for b in result["bronnen"]}


def test_de_arbeidsmarkt_noemt_de_duo_bestanden_uwv_en_roa_die_ze_laadde(bronversie):
    result = dashboard.load_dashboard_arbeidsmarktmatch(_HU)

    bronnen = _per_dataset(result)
    # p02ho1ejrs (eerstejaars) gebruikt de arbeidsmarkt niet: hij staat er niet in.
    assert list(bronnen) == ["p01hoinges", "p04hogdipl", "uwv-open-match-data", "ais2030"]
    assert [b["bron"] for b in result["bronnen"]] == ["DUO", "DUO", "UWV", "ROA"]

    dipl = bronnen["p04hogdipl"]
    assert dipl["url"] == "https://onderwijsdata.duo.nl/dataset/p04hogdipl"
    assert dipl["titel"]  # de titel uit de catalogus, zoals de chat hem noemt
    assert dipl["bestanden"] == [
        {"resource": 0, "resource_id": "p04hogdipl-r0", "last_modified": "2026-04-08T03:04:43.123456"},
        {"resource": 1, "resource_id": "p04hogdipl-r1", "last_modified": "2026-04-08T03:04:43.123456"},
    ]
    assert dipl["last_modified"] == "2026-04-08T03:04:43.123456"
    assert dipl["peilmoment"] == "versie van 08-04-2026"  # de woorden van de bronregel in de chat (#717)
    assert dipl["peildatum"] == "1 oktober"
    assert dipl["voorlopig"] is False
    assert dipl["opgehaald_op"] == _NU.isoformat()


def test_uwv_is_de_momentopname_met_de_peildatum_uit_de_data():
    uwv = _per_dataset(dashboard.load_dashboard_arbeidsmarktmatch(_HU))["uwv-open-match-data"]

    assert uwv["bron"] == "UWV"
    assert uwv["peildatum"] == "2023-05-16"
    assert uwv["peilmoment"] == "peildatum 2023-05-16"
    assert uwv["voorlopig"] is False
    assert uwv["url"] == "https://data.overheid.nl/dataset/uwv-open-match-data"


def test_roa_draagt_de_editie_uit_de_data(monkeypatch):
    roa = arbeidsmarkt._roa()  # de bevroren snapshot van arbeidsmarkt_fixtures
    arbeidsmarkt._roa.cache_clear()
    roa.attrs["schema"] = {"editie": "2025"}
    monkeypatch.setattr("onderwijsbronnen.roa.load", lambda *a, **k: roa)

    result = _per_dataset(dashboard.load_dashboard_arbeidsmarktmatch(_HU))["ais2030"]

    assert result["titel"] == "AIS tot 2030"
    assert result["editie"] == "2025"
    assert result["versie"] == "v20251218"  # de kolom versie van het bestand
    assert result["peilmoment"] == "editie 2025, versie v20251218"
    assert result["url"] == "https://doi.org/10.34894/DVQTOG"


def test_roa_zonder_editie_in_het_schema_noemt_de_versie_uit_de_data():
    roa = _per_dataset(dashboard.load_dashboard_arbeidsmarktmatch(_HU))["ais2030"]

    assert roa["editie"] is None
    assert roa["peilmoment"] == "versie v20251218"


def test_een_mbo_dashboard_noemt_geen_ho_bestanden_en_meldt_voorlopige_cijfers():
    # De ho-poging laadt p01hoinges om de naam te zoeken; daar komen de cijfers van een mbo-instelling niet uit.
    result = dashboard.load_dashboard_regio(_MONDRIAAN)

    bronnen = _per_dataset(result)
    assert not {"p01hoinges", "p02ho1ejrs", "p04hogdipl"} & set(bronnen)
    instroom = bronnen["instromende-mbo-studenten"]
    # De eerstejaars uit de bestanden "met soorten instroom", de hoofdgroepen uit dat van het laatste jaar (#934).
    assert sorted(b["resource"] for b in instroom["bestanden"]) == sorted(
        [*dashboard._INSTROMENDE_MBO_HISTORISCH, dashboard._INSTROMENDE_MBO_HOOFDGROEP]
    )
    assert instroom["voorlopig"] is True
    assert instroom["voorlopig_jaren"] == ["2025"]
    assert instroom["peildatum"] == "1 oktober van het studiejaar"
    # Zonder versie van riodata (een oudere riodata, een datastore-dump): geen peilmoment, geen fout.
    assert instroom["last_modified"] is None
    assert instroom["peilmoment"] is None


def test_een_cachetreffer_geeft_hetzelfde_bronblok(bronversie):
    eerste = dashboard.load_dashboard_regio(_MONDRIAAN)["bronnen"]

    assert dashboard.load_dashboard_regio(_MONDRIAAN)["bronnen"] == eerste


def test_een_bron_die_niet_laadde_staat_niet_als_gebruikt(monkeypatch):
    monkeypatch.setattr(arbeidsmarkt, "uwv_stand", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("UWV")))
    monkeypatch.setattr(arbeidsmarkt, "_uwv", lambda: (_ for _ in ()).throw(ConnectionError("UWV")))

    result = dashboard.load_dashboard_arbeidsmarktmatch(_HU)

    assert "uwv-open-match-data" not in _per_dataset(result)
    assert {g["bron"] for g in result["niet_beschikbaar"]} == {"UWV"}


@pytest.mark.parametrize(
    ("lader", "verwacht"),
    [
        (dashboard.load_dashboard_nationaal, ["p01hoinges"]),
        # Hbo en wo krijgen geen rendement, alleen de reden: geen getal, dus geen bron (#898).
        (dashboard.load_dashboard_rendement, []),
        # In de volgorde van laden: de regio laadt ROA vóór de vacatures van UWV.
        (dashboard.load_dashboard_regio, ["p01hoinges", "p02ho1ejrs", "p04hogdipl", "ais2030", "uwv-open-match-data"]),
    ],
)
def test_elk_dashboard_noemt_de_bestanden_die_het_gebruikt(lader, verwacht):
    assert list(_per_dataset(lader(_HU))) == verwacht


def test_een_onbekende_instelling_heeft_geen_bronblok():
    result = dashboard.load_dashboard_regio("Hogeschool Nergenshuizen")

    assert result["gevonden"] is False
    assert "bronnen" not in result


def test_het_bronblok_leest_het_dataset_id_zoals_de_rest_van_de_chat():
    """#971: het bronblok had een derde lijst ID-velden (`_ckan_id`, `_roa_id`, `_skdb_id`), zonder SBB, RIO en de
    Inspectie; die kregen geen titel en geen link. Nu leest het `scopeprofiel.dataset_id`, de ene lijst van #967."""
    records = [*onderwijsbronnen.catalog(source="all"), *onderwijsbronnen.catalog(source="skdb")]

    assert set(bronblok._catalogus()) == {scopeprofiel.dataset_id(r) for r in records} - {None}
    assert bronblok._catalogus()["crebolijst"]["_sbb_id"] == "crebolijst"
