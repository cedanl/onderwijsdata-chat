"""De vergelijkingsgroep van het dashboard Mijn instelling, ook in de chat (#1267).

"Hoe doen wij het ten opzichte van vergelijkbare instellingen?" liet het model zelf peers kiezen: elke keer misschien
een andere groep, en een andere dan het dashboard. Deze tool geeft de groep van het dashboard, uit dezelfde functie
(`data.dashboard.vergelijkingsgroep`): instellingen van hetzelfde type, van ten minste 10% van de eigen omvang, in de
smalste regio met ten minste drie (arbeidsmarktregio, provincie, landelijk). Met het peergemiddelde van de
ingeschrevenen per jaar, zoals het kerncijfer; heeft het laatste jaar minder dan drie peers met cijfers, dan geen
gemiddelde, zoals het dashboard (#1007). Een eigen groep van de gebruiker kan met namen of codes: dan zegt de zin uit
code dat het niet de dashboardgroep is.

De zin over de groep (`zin`) komt uit code; de app zet hem zelf onder het antwoord (agent/controlestappen.py).
"""

import json
import logging

from core.logging_util import foutkenmerk
from data import dashboard

from . import periode

logger = logging.getLogger(__name__)

BRONREGEL = {
    "ho": "DUO · Ingeschreven studenten hoger onderwijs (p01hoinges), met de DUO-adressen van de instellingen: de "
    "vergelijkingsgroep van het dashboard Mijn instelling",
    "mbo": "DUO · Mbo-studenten per instelling (mbo-studenten-per-instelling), met de DUO-adressen van de instellingen: "
    "de vergelijkingsgroep van het dashboard Mijn instelling",
}
_SOORT = {"hbo": "hogescholen", "wo": "universiteiten", "mbo": "mbo-instellingen"}
NOOT = (
    "Noem de groep met de zin in `zin`; de app zet die zin zelf onder het antwoord. Vergelijk alleen met deze peers en "
    "dit peergemiddelde: voeg geen instelling toe en laat er geen weg. Wil de gebruiker een andere groep, roep de tool "
    "dan opnieuw aan met `eigen_groep`."
)


def _aantal(n: int, soort: str) -> str:
    enkel = {"hogescholen": "hogeschool", "universiteiten": "universiteit", "mbo-instellingen": "mbo-instelling"}
    return f"{n} {enkel[soort] if n == 1 else soort}"


def zin(groep: dict) -> str:
    """De vaste zin over de groep: aantal, regio-trede en terugvalregel, of dat het een eigen groep is."""
    soort = _SOORT[groep["soort"]]
    n = groep.get("n_instellingen", len(groep["peers"]))  # zoals het label van het dashboard: de peers met cijfers
    if groep["groep"] == dashboard.EIGEN_GROEP:
        tekst = f"Vergeleken met een eigen groep van {_aantal(n, soort)}, niet de dashboardgroep van Mijn instelling."
    else:
        plaats = "landelijk" if groep["regio_trede"] == "nationaal" else f"in {groep['regio_trede']} {groep['regio']}"
        tekst = (
            f"Vergeleken met de dashboardgroep van Mijn instelling: {_aantal(n, soort)} {plaats}, van hetzelfde type "
            f"en met ten minste {groep['min_peer_omvang']:.0%} van de eigen omvang"
        )
        tekst += f"; terugval: {groep['terugval']}." if groep.get("terugval") else "."
    if groep.get("geen_gegevens"):
        tekst += f" Zonder cijfers en dus niet in het gemiddelde: {', '.join(groep['geen_gegevens'])}."
    if groep.get("te_weinig_peers"):
        tekst += (
            f" In het laatste jaar hebben minder dan {groep['min_peers']} peers cijfers: het dashboard toont dan geen "
            "gemiddelde, en dit antwoord ook niet."
        )
    return tekst


def _rijen(groep: dict) -> list[dict]:
    """Per schooljaar het peergemiddelde, het aantal peers erachter en de eigen ingeschrevenen; zonder gemiddelde
    (te weinig peers met cijfers) alleen de eigen reeks en het aantal peers."""
    gemiddelde = {} if groep.get("te_weinig_peers") else groep.get("peergemiddelde") or {}
    n_per_jaar, eigen = groep.get("n_per_jaar") or {}, groep.get("eigen_ingeschrevenen") or {}
    rijen = []
    for jaar in sorted({*map(int, gemiddelde), *map(int, eigen)}):
        rij: dict = {"Schooljaar": periode.label(jaar), "Ingeschrevenen eigen instelling": eigen.get(jaar)}
        if jaar in gemiddelde:
            rij["Peergemiddelde ingeschrevenen"] = gemiddelde[jaar]
        rij["Peers met cijfers"] = n_per_jaar.get(jaar, 0)
        rijen.append(rij)
    return rijen


def vergelijkingsgroep(instelling: str, eigen_groep: list[str] | None = None) -> str:
    """De vergelijkingsgroep van een instelling zoals het dashboard Mijn instelling haar kiest, of een eigen groep."""
    naam = str(instelling or "").strip()
    if not naam:
        return "Geef de instelling (officiële naam of alias), bijvoorbeeld de profielinstelling."
    if eigen_groep is not None and not isinstance(eigen_groep, list):
        return "`eigen_groep` is een lijst met namen of codes van instellingen."
    try:
        groep = dashboard.vergelijkingsgroep(naam, eigen_groep or ())
    except Exception as e:
        logger.warning("vergelijkingsgroep niet beschikbaar: %s", foutkenmerk(e))
        return (
            "De DUO-data voor de vergelijkingsgroep is nu niet beschikbaar. Probeer het over een paar minuten opnieuw."
        )
    if groep is None:
        return (
            f"Onbekende instelling {naam!r}: het register en de DUO-bestanden kennen haar niet als hbo-, wo- of "
            "mbo-instelling. Geen gok; controleer de naam."
        )
    soort = "mbo" if groep["soort"] == "mbo" else "ho"
    uit = {
        "instelling": groep["instelling"],
        "groep": groep["groep"],
        "zin": zin(groep),
        "regio_trede": groep["regio_trede"],
        "regio": groep["regio"],
        "terugval": groep["terugval"],
        "regel": (
            f"hetzelfde type ({_SOORT[groep['soort']]}), ten minste {groep['min_peer_omvang']:.0%} van de eigen omvang "
            f"(ingeschrevenen in het laatste jaar), in de smalste regio met ten minste {groep['min_peers']} andere: "
            "arbeidsmarktregio, dan provincie, dan landelijk"
        ),
        "peers": groep["peers"],
        "rijen": _rijen(groep),
        "bron": {"regel": BRONREGEL[soort]},
        "noot": NOOT,
    }
    for veld in ("geen_gegevens", "te_weinig_peers", "onbekend", "ander_type"):
        if groep.get(veld):
            uit[veld] = groep[veld]
    return json.dumps(uit, ensure_ascii=False, default=str)
