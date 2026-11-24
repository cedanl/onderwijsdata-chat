"""Waarop een rapport rust (#738): daaruit komen de bronnen, de teldefinities en de dataversie.

Het rapport nam die drie over van alles wat het gesprek had opgehaald. Bij twee grafieken uit CBS
83285NED noemde het ook CBS 83282NED en twee DUO-tabellen, die eerder in het gesprek waren opgevraagd
maar nergens in het rapport voorkwamen; een gebruiker meldde dat. De bronregel is het controlemiddel
van de lezer, dus een dataset staat erin als het rapport hem gebruikte:
- wat de rapportrun zelf las: haar bevragingen en de grafieken die in het rapport staan;
- een berekening uit het gesprek (#397) waarvan het rapport een getal citeert dat ze levert.
Een bron zonder tabel in de store (de mbo-indicatoren, #1077) heeft geen key en dus geen dataset: haar bronregel komt erbij
als het rapport een getal uit haar uitvoer citeert (`bewijsbronnen`).
Een selectie uit het gesprek telt mee als het rapport erop voortbouwde, en de laadkey altijd. Rust het
rapport op geen enkele herleidbare key, dan blijven de datasets van het gesprek staan: een rapport over
data zonder één bron zegt de lezer nog minder.
"""

from agent.bronvermelding import bronnen_van
from agent.grounding import unverified
from agent.selectie import keten, stapkeys
from agent.session_data import is_bewijs_zonder_tabel


def _citeert(tekst: str, berekening: dict) -> bool:
    """Of de tekst een getal citeert dat de berekening levert: een getal dat zonder haar resultaat ongedekt is."""
    return bool(set(unverified(tekst, [])) - set(unverified(tekst, [berekening["resultaat"]])))


def _geciteerd(tekst: str, berekening: dict) -> list[str]:
    """De keys van een berekening uit het gesprek, als de tekst een getal citeert dat zij levert."""
    if not _citeert(tekst, berekening):
        return []
    keys = [*stapkeys(berekening["resultaat"]), (berekening.get("argumenten") or {}).get("data_key")]
    return [key for key in keys if isinstance(key, str)]


def gebruikte_datasets(datasets: list[dict], gelezen: list, berekeningen: list[dict], tekst: str) -> list[dict]:
    """De datasets uit de context van het gesprek waarop het rapport rust, in hun volgorde.

    `gelezen` zijn de keys die de rapportrun las, `berekeningen` het rekenbewijs van het gesprek
    (session_data.rekenbewijs) en `tekst` wat het model schreef.
    """
    keys = [*gelezen, *(key for b in berekeningen for key in _geciteerd(tekst, b))]
    ketens = {k for key in keys if isinstance(key, str) for k in keten(key)}
    return [ds for ds in datasets if ds.get("data_key") in ketens] or datasets


def bewijsbronnen(berekeningen: list[dict], tekst: str) -> list[str]:
    """De bronregels van de bronnen zonder tabel (`session_data.BEWIJSTOOLS`) waaruit `tekst` een getal citeert (#1077).

    Zoals bij de datasets telt alleen een bron waaraan het rapport iets ontleent; de regel komt uit code, zoals onder een
    chatantwoord (`bronvermelding.bronnen_van`).
    """
    citeerbaar = [b for b in berekeningen if is_bewijs_zonder_tabel(b) and _citeert(tekst, b)]
    return bronnen_van([(b["tool"], b["resultaat"]) for b in citeerbaar])
