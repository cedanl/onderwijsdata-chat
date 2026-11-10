"""Het bewijs per afgerond antwoord: lineage, rekenbewijs en kaarten, zodat een heropend gesprek hetzelfde rapport geeft
als het levende (ADR-009, #875).

De client blijft de bron van de gesprekstekst: zij PUT het gesprek en stuurt het als `history`-frame terug. De server
bewaart per afgerond antwoord wat zij zelf vastlegde, gesleuteld op de sha256 van de tekst die `message_end` als
`content` stuurde. Die tekst bewaart de frontend ongewijzigd, dus de hash koppelt een rij aan het bericht waar het
ook staat; een tekst die de client veranderde, vindt geen rij en herstelt niets (fail closed).

Zoals bij de recepten (`agent/recepten.py`, #472): bij `message_end` kent de server het gesprek-id nog niet, dat kiest
de frontend. De sessie zet de rij daarom klaar in het geheugen, per `(gebruiker, hash)` en begrensd; na een geslaagde
PUT schrijft `bewaar` een rij onder het gesprek-id voor elk antwoord in de body waarvan de hash klaarstaat. Bij
heropenen en herverbinden leest `rijen_voor` de rijen van het gesprek plus de klaarstaande, en `zet_terug` vult de
verse sessie. Opzoeken gaat altijd per gebruiker.

Een beurt is wat `_process_message` aan `turns` toevoegt. Een gestopt, afgebroken of mislukt antwoord en een
verduidelijkingskaart krijgen geen rij; wat die aan lineage of rekenbewijs opleverden, gaat mee in de rij van de volgende
afgeronde beurt (`session_data.neem_beurtbewijs`).
"""

import hashlib
import logging
from collections import OrderedDict
from datetime import UTC, datetime

from persistence import db

from .kaarten import kaarten_van_beurt
from .session_data import begrens_rekenbewijs, neem_beurtbewijs, voeg_rekenbewijs_toe

logger = logging.getLogger(__name__)

# Wacht tot het gesprek is opgeslagen. Begrensd: een gesprek dat nooit wordt opgeslagen blijft niet hangen. Kleiner dan
# de recepten (`_MAX_WACHTEND`), want een rij draagt het hele resultaat van haar rekentools.
_MAX_KLAAR = 500
_klaar: OrderedDict[tuple[str, str], dict] = OrderedDict()

# De hashes van de assistentberichten die een heropend gesprek zonder rij binnenbracht (#876). Alleen na heropenen of
# herverbinden; een levende sessie heeft de sleutel niet.
_ZONDER_RIJ = "antwoorden_zonder_rij"


def tekst_hash(tekst: str) -> str:
    """De sleutel van een antwoord: sha256 (hex) van zijn UTF-8-tekst. Een onbruikbaar teken breekt de hash niet."""
    return hashlib.sha256(tekst.encode("utf-8", errors="replace")).hexdigest()


def zet_klaar(session: dict, turn: dict, tekst: str) -> None:
    """Zet de rij van een net afgeronde beurt klaar tot het gesprek wordt opgeslagen.

    `tekst` is de `content` van haar `message_end`. Dezelfde tekst twee keer geeft één rij: de tweede beurt voegt haar
    items toe (`voeg_samen`).
    """
    username = session.get("username")
    if not username:
        return
    lineage, rekenbewijs = neem_beurtbewijs(session)
    rij = {
        "lineage": lineage,
        "rekenbewijs": rekenbewijs,
        "kaarten": kaarten_van_beurt(turn),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    sleutel = (username, tekst_hash(tekst))
    _klaar[sleutel] = voeg_samen(_klaar[sleutel], rij) if sleutel in _klaar else rij
    _klaar.move_to_end(sleutel)
    while len(_klaar) > _MAX_KLAAR:
        _klaar.popitem(last=False)
    logger.info(
        "BEURTBEWIJS klaar  lineage=%d  rekenbewijs=%d  kaarten=%d",
        len(rij["lineage"]),
        len(rij["rekenbewijs"]),
        len(rij["kaarten"]),
    )


def voeg_samen(oud: dict, nieuw: dict) -> dict:
    """Twee rijen met dezelfde tekst als één, en zo vaak als je wilt: opnieuw samenvoegen verandert niets.

    Voor de lineage wint de eerste maker, zoals in `data_provenance`; een kaart die later kwam vervangt de oudere
    van dezelfde key, zoals in het levende gesprek; het rekenbewijs krijgt de items die er nog niet in staan, tot de
    grens van de sessie; het antwoord behoudt zijn eerste tijd.
    """
    rekenbewijs = oud["rekenbewijs"] + [r for r in nieuw["rekenbewijs"] if r not in oud["rekenbewijs"]]
    return {
        "lineage": {**nieuw["lineage"], **oud["lineage"]},
        "rekenbewijs": begrens_rekenbewijs(rekenbewijs),
        "kaarten": {**oud["kaarten"], **nieuw["kaarten"]},
        "created_at": oud["created_at"],
    }


def antwoord_hashes(messages: object) -> list[str]:
    """De hashes van de antwoorden in een gesprek zoals de client het stuurt, in volgorde, elk één keer.

    Over de tekst zoals de client haar brengt: vóór `_parse_history` inkort of markeert."""
    if not isinstance(messages, list):
        return []
    hashes = (
        tekst_hash(m["content"])
        for m in messages
        if isinstance(m, dict) and m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"]
    )
    return list(dict.fromkeys(hashes))


def bewaar(username: str, conv_id: str, messages: object) -> None:
    """Schrijf na een geslaagde PUT de klaarstaande rij van elk antwoord in de body.

    Een klaarstaande rij blijft staan na het schrijven, tot de grens haar verdringt: het gesprek wordt na elk antwoord
    opnieuw opgeslagen. Wat er al staat blijft; alleen een rij die verandert wordt geschreven.
    """
    klaar = {h: _klaar[username, h] for h in antwoord_hashes(messages) if (username, h) in _klaar}
    if not klaar:
        return
    bewaard = db.beurtbewijs_voor(username, conv_id)
    nieuw: dict[str, dict] = {}
    for h, rij in klaar.items():
        samen = voeg_samen(bewaard[h], rij) if h in bewaard else rij
        if samen != bewaard.get(h):
            nieuw[h] = samen
    db.save_beurtbewijs(username, conv_id, nieuw)
    logger.info("BEURTBEWIJS bewaard  antwoorden=%d  geschreven=%d", len(klaar), len(nieuw))


def rijen_voor(username: str, conv_id: object, messages: object) -> dict[str, dict]:
    """De rijen van de antwoorden in `messages` (het `history`-frame): die van het gesprek en de klaarstaande.

    Per tekst-hash één rij, in de volgorde van het gesprek; een antwoord waarvan de client de tekst veranderde, heeft
    er geen. Leest de database.
    """
    hashes = antwoord_hashes(messages)
    bewaard = db.beurtbewijs_voor(username, conv_id) if hashes and isinstance(conv_id, str) and conv_id else {}
    rijen = {}
    for h in hashes:
        if rij := _samen(bewaard.get(h), _klaar.get((username, h))):
            rijen[h] = rij
    logger.info("BEURTBEWIJS gelezen  antwoorden=%d  rijen=%d", len(hashes), len(rijen))
    return rijen


def zet_terug(session: dict, rijen: dict[str, dict]) -> None:
    """Vul een verse, net geopende sessie met het bewijs van haar antwoorden, in de volgorde van het gesprek.

    `session["messages"]` is al de (ingekorte) modelgeschiedenis. Lineage, rekenbewijs en kaarten komen van elk
    antwoord uit `rijen`, ook van beurten die buiten die geschiedenis vielen. Het vraagnummer per key (`data_vraag`,
    #733) volgt uit de plaats van het antwoord in de geschiedenis, zoals `gebruikersvragen`: een antwoord dat de
    geschiedenis niet meer haalt, heeft geen nummer.

    Een antwoord in die geschiedenis zonder rij is niet van de server: het telt niet als bewijs (`eerdere_antwoorden`,
    #876).
    """
    for rij in rijen.values():
        for key, call in rij["lineage"].items():
            session.setdefault("data_provenance", {}).setdefault(key, call)
        voeg_rekenbewijs_toe(session, rij["rekenbewijs"])
        session.setdefault("kaarten", {}).update(rij["kaarten"])
    vragen = 0
    zonder_rij: set[str] = set()
    for m in session.get("messages") or []:
        if m["role"] == "user":
            vragen += 1
        elif rij := rijen.get(h := tekst_hash(m["content"])):
            for key in rij["lineage"]:
                session.setdefault("data_vraag", {}).setdefault(key, vragen)
        else:
            zonder_rij.add(h)
    session[_ZONDER_RIJ] = zonder_rij


def eerdere_antwoorden(berichten: list[dict], session: dict) -> list[str]:
    """De teksten van de assistentberichten die als bewijs tellen: `earlier` van de getalcontrole en de weigering.

    In een levende sessie alle: de server zette ze zelf in het gesprek. Na heropenen of herverbinden niet die zonder
    rij, want die schreef de client (besluit 1 op ADR-009, 09-11): een gesprek van vóór de migratie, een tekst die de
    client veranderde of toevoegde, een gestopt antwoord, of een herstart vóór de PUT. Wat de server daarna in de
    heropende sessie schrijft, telt weer, tenzij het letterlijk dezelfde tekst is als zo'n bericht.
    """
    teksten = [str(m.get("content") or "") for m in berichten if m.get("role") == "assistant"]
    if not (zonder_rij := session.get(_ZONDER_RIJ)):
        return teksten
    return [t for t in teksten if tekst_hash(t) not in zonder_rij]


def vergeet(username: str, hashes) -> None:
    """Een verwijderd gesprek laat ook in het geheugen geen rij achter (zoals `recepten.vergeet`)."""
    for h in hashes:
        _klaar.pop((username, h), None)


def vergeet_gebruiker(username: str) -> None:
    """Na "verwijder al mijn gegevens" (#646) geen rij van deze gebruiker meer, ook niet van een nooit opgeslagen
    gesprek: die staan niet in de database, dus `vergeet` met de hashes daaruit mist ze."""
    for sleutel in [s for s in list(_klaar) if s[0] == username]:
        _klaar.pop(sleutel, None)


def wis() -> None:
    _klaar.clear()


def _samen(bewaard: dict | None, klaar: dict | None) -> dict | None:
    """De rij uit de database en de klaarstaande als één; ontbreekt een van beide, dan de andere."""
    if bewaard is not None and klaar is not None:
        return voeg_samen(bewaard, klaar)
    return bewaard if bewaard is not None else klaar
