"""Draait search_catalog op de vragenset: zonder netwerk, zonder model en zonder instellingsregister (#359).

Gedeeld door pytest en scripts/meet_retrieval.py, zodat beide hetzelfde meten.
"""

import json
import logging
import socket
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from core.catalogusversie import catalogusversie
from tests.retrieval_baseline import meting
from tools import catalog, instelling, scopeprofiel

MAP = Path(__file__).resolve().parent
VRAGENSET = MAP / "vragenset.json"
BASELINE = MAP / "baseline.json"
ONBEKEND = "?"


class NetwerkGeblokkeerd(RuntimeError):
    """Een socketverbinding of DNS-opvraging tijdens de meting: de baseline draait offline."""


def _blokkade(naam: str, pogingen: list[str]):
    def blokkeer(*args, **kwargs):
        pogingen.append(f"{naam}{args!r:.120}")
        raise NetwerkGeblokkeerd(f"netwerk geblokkeerd tijdens de retrieval-baseline: {naam}")

    return blokkeer


@contextmanager
def zonder_netwerk() -> Iterator[list[str]]:
    """Laat elke socketverbinding en DNS-opvraging falen en houdt de pogingen bij.

    Code die de fout zelf afvangt (genoemde_namen doet dat bewust) verbergt een poging zo niet.
    """
    pogingen: list[str] = []
    with (
        patch.object(socket.socket, "connect", _blokkade("connect", pogingen)),
        patch.object(socket.socket, "connect_ex", _blokkade("connect_ex", pogingen)),
        patch.object(socket, "create_connection", _blokkade("create_connection", pogingen)),
        patch.object(socket, "getaddrinfo", _blokkade("getaddrinfo", pogingen)),
    ):
        yield pogingen


@contextmanager
def zonder_instellingsregister() -> Iterator[None]:
    """Het register bouwt uit DUO-downloads, ook in _drempel; instellingsroutering (#334) valt erbuiten."""
    with (
        patch.object(instelling, "noemt_instelling", lambda vraag: False),
        patch.object(instelling, "genoemde_namen", lambda vraag: set()),
    ):
        yield


@contextmanager
def _zonder_logregels() -> Iterator[None]:
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


def laad_vragen(pad: Path = VRAGENSET) -> list[dict]:
    return json.loads(pad.read_text(encoding="utf-8"))["vragen"]


def laad_baseline(pad: Path = BASELINE) -> dict | None:
    return json.loads(pad.read_text(encoding="utf-8")) if pad.exists() else None


def schrijf_baseline(inhoud: dict, pad: Path = BASELINE) -> None:
    pad.write_text(json.dumps(inhoud, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def doorzoekbaar() -> list[dict]:
    """De records waaruit search_catalog put: CBS en RIO/DUO binnen het profiel, van ondersteunde leveranciers."""
    ondersteund = [
        e for e in catalog._rio_duo() if str(e.get("leverancier", "")).upper() in catalog.SUPPORTED_LEVERANCIERS
    ]
    return [*catalog._cbs(), *ondersteund]


def doorzoekbare_ids() -> list[str]:
    return sorted({i for e in doorzoekbaar() if (i := scopeprofiel.dataset_id(e))})


def inventaris_ids() -> set[str]:
    """Alle dataset-ID's uit de volledige CBS- en riodata-inventaris, ook buiten het profiel."""
    return {i for e in [*catalog._cbs_alles(), *catalog._rio_duo_alles()] if (i := scopeprofiel.dataset_id(e))}


def unieke_titels(records: list[dict]) -> dict[str, str]:
    """`bron`-titel naar dataset-ID, alleen voor titels die één keer voorkomen."""
    aantal = Counter(e.get("bron") for e in records)
    return {
        titel: dataset_id
        for e in records
        if (titel := e.get("bron")) and aantal[titel] == 1 and (dataset_id := scopeprofiel.dataset_id(e))
    }


def treffer_id(treffer: dict, titels: dict[str, str]) -> str:
    """Het dataset-ID van een treffer; ROA-records verliezen `_roa_id` in de zoekuitvoer, dan beslist de titel."""
    return scopeprofiel.dataset_id(treffer) or titels.get(str(treffer.get("bron"))) or ONBEKEND


def ranking(resultaat: str, titels: dict[str, str]) -> list[str]:
    """De dataset-ID's in volgorde; een tekstresultaat (no_match, geo-melding) is een lege ranglijst."""
    try:
        treffers = json.loads(resultaat)
    except json.JSONDecodeError:
        return []
    if not isinstance(treffers, list):
        return []
    return [treffer_id(t, titels) for t in treffers if isinstance(t, dict) and set(t) != {"melding"}]


@dataclass(frozen=True)
class Uitkomst:
    """Wat search_catalog voor één vraag teruggaf, met de vaste zoekinput en met de vraag zelf."""

    vraag: dict
    ranking: list[str]
    ranking_vraag: list[str]
    latentie_ms: float

    @property
    def rangen(self) -> dict[str, meting.Rang]:
        return meting.rangen(self.ranking, self.vraag["geaccepteerd"])

    @property
    def eerste(self) -> meting.Rang:
        return meting.eerste_rang(self.rangen)

    @property
    def eerste_vraag(self) -> meting.Rang:
        return meting.eerste_rang(meting.rangen(self.ranking_vraag, self.vraag["geaccepteerd"]))

    @property
    def verboden_top(self) -> dict[str, int]:
        return meting.verboden_in_top(self.ranking, self.vraag["verboden"])

    @property
    def geen_kandidaat(self) -> bool:
        return not self.ranking


@dataclass(frozen=True)
class Meting:
    uitkomsten: list[Uitkomst]
    netwerkpogingen: list[str]

    def uitkomst(self, vraag_id: str) -> Uitkomst:
        return next(u for u in self.uitkomsten if u.vraag["id"] == vraag_id)


def zoek(invoer: str, vraag: dict, titels: dict[str, str]) -> tuple[list[str], float]:
    """De ranglijst van search_catalog voor `invoer` met de parameters van de vraag, en de duur in ms."""
    begin = time.perf_counter()
    resultaat = catalog.search_catalog(
        invoer, vraag.get("source", "both"), top_n=meting.TOP_N, geo_niveau=vraag.get("geo_niveau")
    )
    return ranking(resultaat, titels), (time.perf_counter() - begin) * 1000


def _uitkomst(vraag: dict, titels: dict[str, str]) -> Uitkomst:
    zoekinput, latentie_ms = zoek(vraag["zoekinput"], vraag, titels)
    natuurlijk, _ = zoek(vraag["vraag"], vraag, titels)
    return Uitkomst(vraag, zoekinput, natuurlijk, latentie_ms)


def meet(vragen: list[dict]) -> Meting:
    with zonder_netwerk() as pogingen, zonder_instellingsregister(), _zonder_logregels():
        titels = unieke_titels(doorzoekbaar())
        uitkomsten = [_uitkomst(v, titels) for v in vragen]
    return Meting(uitkomsten, list(pogingen))


def snapshot() -> dict:
    """De catalogus waartegen gemeten is (#344, #361)."""
    return {
        "catalogus_digest": catalog.catalogus_digest(),
        "catalogusversie": catalogusversie(),
        "dataset_counts": catalog.dataset_counts(),
        "doorzoekbaar": doorzoekbare_ids(),
    }
