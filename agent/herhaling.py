"""Herhaal deze analyse (#1240): de tabellen achter een eigen antwoord opnieuw bij de bron, naast de stand van toen.

Per antwoord (zijn tekst-hash, zoals het beurtbewijs, ADR-009) de keys die de beurt maakte; per key het recept van
deze gebruiker (`recepten.voor`), langs de selecties terug naar de geladen tabel. Die laadt `herlaad.apart` opnieuw,
met dezelfde tool, scopegrens en meldingen als het herladen na een herstart, maar buiten de store: het eerdere antwoord
en ieder ander die op die data rust, houdt de data van toen. Er wordt geen model aangeroepen en geen modeltekst
vergeleken; alleen getallen en bronversie (`tools/brondiff.py`). De herhaling wordt niet bewaard.

"Toen" is de tabel zoals de store haar nog heeft, als die niet later is opgehaald dan het antwoord af was. Na een
herstart, de bovengrens of de termijn van de store (actualiteit.TTL) is die stand weg: dan alleen de stand van nu.

Een prototype voor CBS: `_BRONNEN` heeft per bron de laadtools die hier herhaalbaar zijn; DUO en RIO sluiten later aan.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from tools import brondiff, cbs, herlaad, inhoudshash, store
from tools.bron_ids import cbs_tabel_id
from tools.catalog import bron_titel
from tools.schemas import TOOL_GET_CBS_DATA, TOOL_GET_MAAT, TOOL_QUERY_DATA

from . import beurtbewijs, recepten

logger = logging.getLogger(__name__)

BRON_CBS = "cbs"
# Per bron de laadtools waarvan het recept hier opnieuw kan. Alleen CBS in dit prototype.
_BRONNEN: dict[str, frozenset[str]] = {BRON_CBS: frozenset({TOOL_GET_CBS_DATA})}
_MAX_TABELLEN = 5  # elke tabel is een aanroep naar de bron
_MAX_STAPPEN = 10  # een keten van selecties; meer is een kapot of rondlopend recept
# Het beurtbewijs noemt de tijd van het antwoord op de seconde; de lading kwam in diezelfde seconde.
_SPELING = timedelta(seconds=1)

MISLUKT = "mislukt"
GEEN_TABEL = "In dit antwoord staat geen CBS-tabel die de app opnieuw kan ophalen."
ANDERE_BRONNEN = "Alleen tabellen van CBS worden nu opnieuw opgehaald; DUO en RIO volgen later."


@dataclass
class _Tabellen:
    laad: dict[str, list] = field(default_factory=dict)  # de geladen tabel (key) en haar laadstap
    overgeslagen: list[str] = field(default_factory=list)  # stappen die niet opnieuw gaan, in woorden


def _wortel(username: str, key: str) -> tuple[str, dict | None]:
    """De geladen tabel waar `key` via selecties op rust, met het recept waar de keten stopt; None zonder recept."""
    recept = recepten.voor(username, key)
    for _ in range(_MAX_STAPPEN):
        if not isinstance(recept, dict) or "laad" in recept:
            return key, recept
        ouder = recept.get("afgeleid_van")
        if recept.get("tool") not in (TOOL_QUERY_DATA, TOOL_GET_MAAT) or not recept.get("herlaadbaar", True):
            return key, recept
        if not isinstance(ouder, str) or (ouder_recept := recepten.voor(username, ouder)) is None:
            return key, recept
        key, recept = ouder, ouder_recept
    return key, None


def _tabellen(username: str, rij: dict, bron: str) -> _Tabellen:
    """De te herhalen tabellen van een antwoord, elk één keer, en wat er niet opnieuw gaat."""
    uit = _Tabellen()
    andere_bron = False
    for key in rij.get("lineage") or {}:
        wortel, recept = _wortel(username, key)
        if recept is None:
            continue
        laad = recept.get("laad")
        if isinstance(laad, list | tuple) and len(laad) == 2:
            if laad[0] in _BRONNEN[bron] and herlaad.apart_herhaalbaar(laad[0]):
                uit.laad.setdefault(wortel, list(laad))
            else:
                andere_bron = True
        elif "tool" not in recept or not recept.get("herlaadbaar", True):
            # Een eigen berekening of koppeling: geen script of twee tabellen; de stap zegt het zelf (#472, #1063).
            uit.overgeslagen.append(herlaad.onherhaalbaar(wortel, recept))
    if andere_bron:
        uit.overgeslagen.append(ANDERE_BRONNEN)
    uit.overgeslagen = list(dict.fromkeys(uit.overgeslagen))
    return uit


def _tijd(iso: object) -> datetime | None:
    try:
        return datetime.fromisoformat(iso) if isinstance(iso, str) else None
    except ValueError:
        return None


def _toen(key: str, sinds: datetime | None) -> tuple[pd.DataFrame, store.KeyMeta] | None:
    """De tabel van het antwoord, als de store haar nog heeft: niet later opgehaald dan het antwoord af was."""
    known, df = store.meta(key), store.gezien(key)
    if known is None or not isinstance(df, pd.DataFrame) or sinds is None:
        return None
    if known.opgehaald_op > sinds + _SPELING:
        return None
    return df, known


def _titel(laad: list) -> tuple[str, str]:
    args = laad[1] if isinstance(laad[1], dict) else {}
    dataset = cbs_tabel_id(str(args.get("dataset_id") or ""))
    return dataset, bron_titel(dataset, vo_context=bool(args.get("vo_context")))


def _herhaal_tabel(key: str, laad: list, sinds: datetime | None) -> dict:
    """Eén tabel opnieuw, naast de stand van toen."""
    toen = _toen(key, sinds)  # vóór het ophalen: wat de store nu van het antwoord heeft
    dataset, titel = _titel(laad)
    basis = {"dataset": dataset, "titel": titel}
    nieuw = herlaad.apart(key, laad)
    if isinstance(nieuw, herlaad.Herlaadresultaat):
        return {**basis, "status": MISLUKT, "melding": nieuw.melding, "toen": None, "nu": None, "verschil": None}
    nu = brondiff.Stand(nieuw.meta.bijgewerkt_op, inhoudshash.inhoudshash(nieuw.data))
    if toen is None:
        stand_toen, verschil, status = None, None, brondiff.ZONDER_TOEN
    else:
        df, known = toen
        stand_toen = brondiff.Stand(known.bijgewerkt_op, inhoudshash.inhoudshash(df))
        titels = dict(nieuw.meta.kolomtitels or {})
        verschil = brondiff.vergelijk(df, nieuw.data, cbs.dimension_columns(nieuw.key), titels)
        status = brondiff.status(stand_toen, nu, verschil)
    return {
        **basis,
        "status": status,
        "samenvatting": brondiff.samenvatting(stand_toen, nu, verschil),
        "toen": stand_toen.als_dict() if stand_toen else None,
        "nu": nu.als_dict(),
        "verschil": verschil.als_dict() if verschil else None,
    }


def herhaal(username: str, conv_id: str, antwoord: str, bron: str = BRON_CBS) -> dict | None:
    """De herhaling van een eigen antwoord (`antwoord`: de sha256 van zijn tekst); None als het niet van deze gebruiker
    is of onbekend: dan hetzelfde 404 (#1240, zoals bij gesprekken en /api/data/csv). Gaat naar de bron: in een thread.
    """
    rij = beurtbewijs.rij_van(username, conv_id, antwoord)
    if rij is None:
        return None
    gevonden = _tabellen(username, rij, bron)
    sinds = _tijd(rij.get("created_at"))
    tabellen = [_herhaal_tabel(key, laad, sinds) for key, laad in list(gevonden.laad.items())[:_MAX_TABELLEN]]
    logger.info(
        "HERHAAL  bron=%s  tabellen=%d  status=%s  overgeslagen=%d",
        bron,
        len(tabellen),
        ",".join(t["status"] for t in tabellen) or "-",
        len(gevonden.overgeslagen),
    )
    return {
        "bron": bron,
        "tabellen": tabellen,
        "overgeslagen": gevonden.overgeslagen,
        **({"melding": GEEN_TABEL} if not tabellen else {}),
    }
