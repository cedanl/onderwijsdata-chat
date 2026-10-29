"""Eén logregel per gepubliceerd resultaat: herkomst, geen inhoud (#169).

/health en /ready zeggen dat de server draait, niet dat een antwoord klopt. Wat een audit nodig heeft
om een gepubliceerd cijfer aan zijn bron te koppelen, staat sinds #345 in het manifest van het
antwoord en het rapport, maar alleen bij de client. Hier gaat bij elk gepubliceerd resultaat
(antwoord, figuur, CSV-export, rapport) één regel naar het log op INFO: de soort, per data-key de
bron, de dataset, de resource, de key zelf (de digest van haar selectie, #342), of de data
volledig is, de afronding, een herlaaddatum, en de versies uit het manifest (model, prompt,
catalogus, app). Het tijdstip is dat van de logregel. Geen vraag, geen antwoord, geen filtertekst:
een selectie kan een door de gebruiker getypte naam bevatten, en die hoort op INFO niet in het log
(#475). De selectiestappen in woorden (store.herkomst) staan op DEBUG.
"""

import logging

from tools import herlaad, store
from tools.inhoudshash import hash_van

logger = logging.getLogger(__name__)

ANTWOORD, FIGUUR, CSV, RAPPORT = "antwoord", "figuur", "csv", "rapport"
_MANIFESTVELDEN = ("model", "prompt_hash", "catalogus", "app")


def _keyregel(key: str, username: str | None = None) -> str:
    """Eén data-key als veld: bron, dataset, resource, de key, en wat de meta over de data zegt."""
    known = store.meta(key)
    if known is None:
        return f"{key}(onbekend)"
    delen = [f"bron={known.bron}", f"dataset={known.dataset}"]
    if known.resource is not None:
        delen.append(f"resource={known.resource}")
    delen.append(f"key={key}")
    if known.afgeleid_van:
        delen.append(f"afgeleid_van={known.afgeleid_van}")
    delen.append(f"volledig={'ja' if known.volledig else 'nee'}")
    if known.afronding:
        delen.append(f"afronding={known.afronding}")
    if herladen := herlaad.herladen_op(username, key):
        delen.append(f"herladen_op={herladen}")
    if not known.afgeleid_van and (inhoud := hash_van(key)):
        delen.append(f"inhoudshash={inhoud}")
    if not known.afgeleid_van and known.bronhash:
        delen.append(f"bronhash={known.bronhash}")
    df = store.get(key)
    if df is not None and hasattr(df, "shape"):
        delen.append(f"rijen={df.shape[0]}")
    return "[" + " ".join(delen) + "]"


def log_publicatie(soort: str, keys, manifest: dict | None = None, username: str | None = None) -> None:
    """Log dat een resultaat van `soort` naar de gebruiker ging, met de herkomst van zijn data.

    `keys` zijn de data-keys waarop het rust, in volgorde en zonder dubbelen; `manifest` het
    manifest van het antwoord of rapport (#345), waarvan alleen de versievelden meegaan. Of data herladen is,
    geldt voor `username` (#788).
    """
    uniek = list(dict.fromkeys(k for k in keys if isinstance(k, str)))
    versies = " ".join(f"{veld}={manifest[veld]}" for veld in _MANIFESTVELDEN if manifest and manifest.get(veld))
    logger.info(
        "GEPUBLICEERD soort=%s keys=%d %s %s",
        soort,
        len(uniek),
        " ".join(_keyregel(k, username) for k in uniek),
        versies,
    )
    for key in uniek:
        if stappen := store.herkomst(key):
            logger.debug("GEPUBLICEERD herkomst key=%s %s", key, " | ".join(stappen))
