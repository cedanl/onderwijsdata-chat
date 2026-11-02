"""Een opgehaalde CBS-tabel geldt niet als actueel tot de pod herstart (#864).

De datastore verdrong alleen op grootte en de CBS-metadata zat in een lru_cache zonder verloop: een revisie bij CBS
bleef onzichtbaar. `get_cbs_data` meldde bovendien de catalogusdatum van het buildmoment van de package, terwijl CBS
de live `TableInfos.Modified` geeft. De klok staat stil in deze tests: `actualiteit.nu` wordt verzet, niet afgewacht.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agent.bronvermelding import bronnen_van
from agent.session_data import herstel_data_keys, record_data_key
from core import actualiteit
from tools import cbs, store
from tools.catalog import catalogus_laatste_update
from tools.cbs import get_cbs_data, get_cbs_dimension
from tools.store import KeyMeta

_START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
_DEFS = {
    "Onderwijssoort": {"type": "Dimension"},
    "Perioden": {"type": "TimeDimension"},
    "Ingeschrevenen_1": {"type": "Topic"},
}
_ROWS = [{"Onderwijssoort": "A025294", "Perioden": "2025SJ00", "Ingeschrevenen_1": 367960}]
_LIVE_MODIFIED = "2026-10-20T02:00:00"


class _Klok:
    """De klok van actualiteit, met de hand verzet."""

    def __init__(self, monkeypatch):
        self.moment = _START
        monkeypatch.setattr(actualiteit, "nu", lambda: self.moment)

    def verzet(self, **delta) -> None:
        self.moment += timedelta(**delta)


@pytest.fixture
def klok(monkeypatch):
    # De verversing van de CBS-metadata begint opnieuw, op de stilstaande klok.
    monkeypatch.setattr(cbs._metadata, "_sinds", None)
    return _Klok(monkeypatch)


def _meta(key: str) -> KeyMeta:
    known = store.meta(key)
    assert known is not None
    return known


def _get(modified: str | None = _LIVE_MODIFIED):
    """CBS' TableInfos met of zonder Modified; elk ander endpoint (dimensies) leeg."""

    def get(dataset_id, endpoint, **params):
        if endpoint == "TableInfos":
            return [{"Description": "", **({"Modified": modified} if modified else {})}]
        return []

    return get


# ── De datastore: een key ouder dan de TTL gaat eruit ────────────────────────


def test_een_key_binnen_de_ttl_blijft(klok):
    store.put("cbs:85423NED", pd.DataFrame({"A": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    klok.verzet(hours=23, minutes=59)
    assert store.get("cbs:85423NED") is not None


def test_een_key_ouder_dan_de_ttl_gaat_eruit_met_zijn_afleidingen_en_alias(klok):
    store.put("cbs:85423NED", pd.DataFrame({"A": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    store.alias("cbs_85423NED", "cbs:85423NED")
    klok.verzet(hours=12)
    store.derive("cbs:85423NED", "cbs:85423NED:sel", pd.DataFrame({"A": [1]}))
    assert _meta("cbs:85423NED:sel").opgehaald_op == _START  # de selectie is zo oud als haar bron

    klok.verzet(hours=12)
    assert store.get("cbs:85423NED:sel") is None
    assert store.get("cbs:85423NED") is None
    assert "cbs_85423NED" not in store.list_keys()


def test_een_key_zonder_meta_heeft_geen_ophaalmoment_en_blijft(klok):
    store.put("tmp:x", pd.DataFrame({"A": [1]}))
    klok.verzet(days=3)
    assert store.get("tmp:x") is not None


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()


@pytest.mark.usefixtures("zonder_scopegrens", "database")
@pytest.mark.parametrize(("uren", "aanroepen"), [(23, 1), (25, 2)])
def test_een_key_ouder_dan_de_ttl_wordt_uit_zijn_recept_opnieuw_opgehaald(klok, uren, aanroepen):
    data = MagicMock(return_value=_ROWS)
    with (
        patch("tools.cbs.data", data),
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=_get()),
    ):
        session = {"username": "alice"}
        args = {"dataset_id": "85423NED"}
        key = json.loads(resultaat := get_cbs_data("85423NED"))["data_key"]
        record_data_key(session, resultaat, {"name": "get_cbs_data", "arguments": args})

        klok.verzet(hours=uren)
        herstel = herstel_data_keys(session, "alice")

    assert not herstel.onherstelbaar
    assert data.call_count == aanroepen
    assert store.get(key) is not None
    assert _meta(key).opgehaald_op == (_START if aanroepen == 1 else klok.moment)


# ── De CBS-metadata: na de TTL weer van de bron ─────────────────────────────


@pytest.mark.usefixtures("zonder_scopegrens")
@pytest.mark.parametrize(("uren", "aanroepen"), [(23, 1), (25, 2)])
def test_dimensierijen_komen_na_de_ttl_opnieuw_van_cbs(klok, uren, aanroepen):
    get = MagicMock(return_value=[{"Key": "2025SJ00", "Title": "2025/'26", "Status": "Voorlopig"}])
    with patch("tools.cbs.get", get):
        get_cbs_dimension("85423NED", "Perioden")
        klok.verzet(hours=uren)
        get_cbs_dimension("85423NED", "Perioden")
    assert get.call_count == aanroepen


def test_de_verversing_leegt_ook_de_kolomdefinities_van_de_package(klok):
    definities = MagicMock()
    with patch("tools.cbs.definitions", definities):
        cbs._metadata.actueel()
        definities.cache_clear.reset_mock()
        klok.verzet(hours=25)
        cbs._metadata.actueel()
    definities.cache_clear.assert_called_once_with()


# ── get_cbs_data: de live Modified, met de catalogus als terugval ───────────


def _laad(get, dataset_id: str = "85423NED") -> dict:
    with (
        patch("tools.cbs.data", return_value=_ROWS),
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=get),
    ):
        return json.loads(get_cbs_data(dataset_id))


@pytest.mark.usefixtures("zonder_scopegrens")
def test_get_cbs_data_meldt_de_live_modified_en_de_ophaaldatum(klok):
    resultaat = _laad(_get())
    assert resultaat["laatste_update"] == "2026-10-20" != catalogus_laatste_update("85423NED")
    assert resultaat["opgehaald_op"] == f"{_START.astimezone():%Y-%m-%d}"
    assert _meta(resultaat["data_key"]).bijgewerkt_op == "2026-10-20"


@pytest.mark.usefixtures("zonder_scopegrens")
def test_antwoordt_cbs_niet_dan_geldt_de_catalogusdatum(klok):
    """Zonder Modified in het antwoord: tests/test_cbs_laatste_update_tekst.py."""

    def fout(dataset_id, endpoint, **params):
        if endpoint == "TableInfos":
            raise RuntimeError("CBS onbereikbaar")
        return []

    resultaat = _laad(fout)
    assert resultaat["laatste_update"] == catalogus_laatste_update("85423NED")
    assert _meta(resultaat["data_key"]).bijgewerkt_op == catalogus_laatste_update("85423NED")


# ── De bronvermelding: bijgewerkt door CBS en opgehaald ─────────────────────


@pytest.mark.usefixtures("zonder_scopegrens")
def test_de_bronvermelding_noemt_bijwerking_en_ophaaldatum(klok):
    key = _laad(_get())["data_key"]
    [bron] = bronnen_van([("get_cbs_data", json.dumps({"data_key": key}))])
    assert bron.endswith(f", bijgewerkt door CBS op 20-10-2026, opgehaald op {_START.astimezone():%d-%m-%Y}")


def test_zonder_bijwerkdatum_noemt_de_bronvermelding_alleen_het_ophalen(klok):
    store.put("cbs:85423NED", pd.DataFrame({"A": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    [bron] = bronnen_van([("get_cbs_data", json.dumps({"data_key": "cbs:85423NED"}))])
    assert "bijgewerkt door CBS" not in bron
    assert bron.endswith(f"(85423NED), opgehaald op {_START.astimezone():%d-%m-%Y}")


def test_een_andere_bron_krijgt_geen_ophaaldatum(klok):
    store.put("duo:p01hoinges:0", pd.DataFrame({"A": [1]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    [bron] = bronnen_van([("get_duo_data", json.dumps({"data_key": "duo:p01hoinges:0"}))])
    assert "opgehaald op" not in bron
