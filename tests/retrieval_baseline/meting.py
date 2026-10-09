"""Retrievalmaten zonder catalogus en zonder netwerk: rang, recall@5, MRR en hun 95%-interval (#359).

Pure functies op ranglijsten van dataset-ID's; de definities staan in README.md.
"""

import math
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

TOP_N = 15
K = 5
Z95 = 1.959963984540054
BOOTSTRAP_TREKKINGEN = 2000
BOOTSTRAP_SEED = 359
VOLLEDIG = (0.0, 1.0)

Rang = int | None


def rangen(ranking: Sequence[str], ids: Iterable[str], top_n: int = TOP_N) -> dict[str, Rang]:
    """De plaats (1 is de eerste) van elk ID in de eerste `top_n` treffers; None als het er niet in staat."""
    eerste = list(ranking[:top_n])
    return {i: eerste.index(i) + 1 if i in eerste else None for i in ids}


def eerste_rang(per_id: dict[str, Rang]) -> Rang:
    gevonden = [r for r in per_id.values() if r is not None]
    return min(gevonden) if gevonden else None


def reciproke_rang(rang: Rang) -> float:
    return 1 / rang if rang else 0.0


def _treffers(eerste: Sequence[Rang], k: int) -> int:
    return sum(1 for r in eerste if r is not None and r <= k)


def recall_bij(eerste: Sequence[Rang], k: int = K) -> float | None:
    """Het aandeel vragen met een geaccepteerde dataset in de top k; None zonder vragen."""
    return _treffers(eerste, k) / len(eerste) if eerste else None


def mrr(eerste: Sequence[Rang]) -> float | None:
    return sum(reciproke_rang(r) for r in eerste) / len(eerste) if eerste else None


def wilson(treffers: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson-scoreinterval voor een aandeel; zonder waarnemingen het hele bereik."""
    if n == 0:
        return VOLLEDIG
    p = treffers / n
    noemer = 1 + z * z / n
    midden = (p + z * z / (2 * n)) / noemer
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / noemer
    laag = 0.0 if treffers == 0 else midden - marge
    hoog = 1.0 if treffers == n else midden + marge
    return laag, hoog


def kwantiel(gesorteerd: Sequence[float], q: float) -> float:
    """Kwantiel van een oplopend gesorteerde reeks, met lineaire interpolatie."""
    positie = q * (len(gesorteerd) - 1)
    onder, boven = math.floor(positie), math.ceil(positie)
    return gesorteerd[onder] + (gesorteerd[boven] - gesorteerd[onder]) * (positie - onder)


def bootstrap_mrr(
    eerste: Sequence[Rang], trekkingen: int = BOOTSTRAP_TREKKINGEN, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """95%-percentielinterval van de MRR over trekkingen met teruglegging, met vaste seed."""
    if not eerste:
        return VOLLEDIG
    waarden = [reciproke_rang(r) for r in eerste]
    trekker = random.Random(seed)
    n = len(waarden)
    gemiddelden = sorted(sum(trekker.choices(waarden, k=n)) / n for _ in range(trekkingen))
    return kwantiel(gemiddelden, 0.025), kwantiel(gemiddelden, 0.975)


def verboden_in_top(ranking: Sequence[str], verboden: Iterable[str], k: int = K) -> dict[str, int]:
    """De verboden ID's in de top k, met hun rang."""
    return {i: r for i, r in rangen(ranking, verboden, top_n=k).items() if r is not None}


def aandeel(geslaagd: Sequence[bool]) -> float | None:
    return sum(geslaagd) / len(geslaagd) if geslaagd else None


@dataclass(frozen=True)
class Samenvatting:
    """recall@k en MRR van een cel beantwoordbare vragen, met hun 95%-interval."""

    n: int
    recall: float | None
    recall_interval: tuple[float, float]
    mrr: float | None
    mrr_interval: tuple[float, float]


def samenvatten(eerste: Sequence[Rang], k: int = K) -> Samenvatting:
    return Samenvatting(
        n=len(eerste),
        recall=recall_bij(eerste, k),
        recall_interval=wilson(_treffers(eerste, k), len(eerste)),
        mrr=mrr(eerste),
        mrr_interval=bootstrap_mrr(eerste),
    )
