"""DUO-metadata uit de CKAN-beschrijving die niet in de catalogus zit (#172).

De catalogus bewaart van de DUO-beschrijving alleen de eerste alinea. De sectie
'## Selectie' zegt wat er geteld wordt (bijv. p01: hoofdinschrijvingen als
natuurlijke personen; p03: hoofd- én neveninschrijvingen). Zonder die definitie
verwisselt het model datasets met verschillende telling zonder het te merken.
"""

import logging
import re

import httpx
from riodata import duo as _duo

logger = logging.getLogger(__name__)

# De langste selectiesectie over alle DUO-datasets is ~1.100 tekens (gemeten 2026-09-24).
_MAX_TEKENS = 1500
# DUO gebruikt 'Selectie', 'Selecties' en 'Selectiecriteria' als kop.
_SELECTIE_SECTIE = re.compile(r"^##\s*Selectie\w*\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)

# Alleen successen: een tijdelijke CKAN-storing mag niet blijvend 'geen definitie' geven.
_cache: dict[str, str | None] = {}


def selectie_sectie(notes: str) -> str | None:
    """De tekst onder de selectiekop, op één regel; None als die ontbreekt of leeg is."""
    match = _SELECTIE_SECTIE.search(notes or "")
    if not match:
        return None
    tekst = " ".join(match.group(1).split())
    if len(tekst) > _MAX_TEKENS:
        tekst = tekst[:_MAX_TEKENS].rsplit(" ", 1)[0] + " …"
    return tekst or None


def _fetch_notes(dataset_id: str) -> str:
    r = httpx.get(f"{_duo.CKAN_BASE}/package_show", params={"id": dataset_id}, timeout=30)
    r.raise_for_status()
    return r.json()["result"].get("notes") or ""


def teldefinitie(dataset_id: str) -> str | None:
    """Wat een DUO-dataset telt, letterlijk uit de DUO-beschrijving."""
    if dataset_id in _cache:
        return _cache[dataset_id]
    try:
        tekst = selectie_sectie(_fetch_notes(dataset_id))
    except Exception as e:
        logger.warning("DUO-beschrijving ophalen mislukt voor %s: %s", dataset_id, e)
        return None
    _cache[dataset_id] = tekst
    return tekst


def clear_cache() -> None:
    _cache.clear()
