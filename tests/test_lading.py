"""`actualiteit.Lading`: een cache voor de dashboardladers die verloopt, geen fout bewaart en één keer laadt (#901).

De klok staat stil: `actualiteit.nu` wordt verzet, niet afgewacht.
"""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from core import actualiteit

_START = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


@pytest.fixture
def klok(monkeypatch):
    moment = [_START]
    monkeypatch.setattr(actualiteit, "nu", lambda: moment[0])

    def verzet(**delta):
        moment[0] += timedelta(**delta)

    return verzet


class _Bron:
    def __init__(self):
        self.aanroepen = 0
        self.storing = False

    def laad(self, *args):
        self.aanroepen += 1
        if self.storing:
            raise ConnectionError("DUO onbereikbaar")
        return {"args": args, "versie": self.aanroepen}


def test_binnen_de_ttl_blijft_de_lading(klok):
    bron = _Bron()
    lading = actualiteit.Lading(bron.laad)

    assert lading() == lading()
    klok(hours=23)
    lading()

    assert bron.aanroepen == 1


def test_na_de_ttl_laadt_de_eerste_aanroep_opnieuw(klok):
    bron = _Bron()
    lading = actualiteit.Lading(bron.laad)

    lading()
    klok(hours=24)

    assert lading()["versie"] == 2


def test_een_fout_komt_niet_in_de_cache(klok):
    bron = _Bron()
    lading = actualiteit.Lading(bron.laad)
    bron.storing = True

    with pytest.raises(ConnectionError):
        lading()
    bron.storing = False

    assert lading()["versie"] == 2


def test_per_argumenten_een_eigen_lading(klok):
    bron = _Bron()
    lading = actualiteit.Lading(bron.laad)

    assert lading("mbo")["args"] == ("mbo",)
    assert lading("ho")["args"] == ("ho",)
    lading("mbo")

    assert bron.aanroepen == 2


def test_gelijktijdige_koude_aanroepen_laden_een_keer(klok):
    # Vijf dashboardeindpunten tegelijk laadden _load_ho_full (zes DUO-bestanden) elk zelf.
    begonnen, door = threading.Event(), threading.Event()
    aanroepen = []

    def traag():
        aanroepen.append(1)
        begonnen.set()
        door.wait(timeout=5)
        return "data"

    lading = actualiteit.Lading(traag)
    uitkomsten = []
    draden = [threading.Thread(target=lambda: uitkomsten.append(lading())) for _ in range(5)]
    for draad in draden:
        draad.start()
    assert begonnen.wait(timeout=5)
    door.set()
    for draad in draden:
        draad.join(timeout=5)

    assert aanroepen == [1]
    assert uitkomsten == ["data"] * 5


def test_cache_clear_leegt_zoals_bij_lru_cache(klok):
    bron = _Bron()
    lading = actualiteit.Lading(bron.laad)

    lading()
    lading.cache_clear()
    lading()

    assert bron.aanroepen == 2
