"""Wat de chat zegt als het stappenbudget op is (#381, #332).

'Probeer een specifiekere vraag' was een dood spoor: de vraag was vaak al specifiek,
het model liep vast op een filter, en de opgehaalde data bleef onzichtbaar. Eerst
krijgt het model één afrondronde zonder tools (AFRONDEN); lukt ook dat niet, dan
zegt code wat er is opgehaald en waar het vastliep.
"""

import json

from tools import fouten, outcome, store
from tools.schemas import TOOL_QUERY_DATA

AFRONDEN = (
    "Het maximale aantal stappen is bereikt: je kunt geen tools meer aanroepen. "
    "Geef nu het beste antwoord dat de opgehaalde data toelaat. Zeg daarbij wat je niet kon ophalen "
    "of filteren en waarom. Noem alleen getallen die letterlijk in de toolresultaten staan."
)

DEELANTWOORD = "_Deelantwoord: het maximale aantal stappen was bereikt voordat de vraag helemaal beantwoord was._"

Stap = tuple[str, str]  # (toolnaam, resultaat)


def _bronnen(stappen: list[Stap]) -> list[str]:
    bronnen: list[str] = []
    for _, resultaat in stappen:
        try:
            parsed = json.loads(resultaat)
        except ValueError:
            continue
        key = parsed.get("data_key") if isinstance(parsed, dict) else None
        herkomst = store.herkomst(key) if isinstance(key, str) else []
        bron = herkomst[0].removeprefix("bron: ") if herkomst else None
        if bron and bron not in bronnen:
            bronnen.append(bron)
    return bronnen


def _oorzaak(stappen: list[Stap]) -> str:
    if any(fouten.code(r) == fouten.Fout.BRON_ONBEREIKBAAR for _, r in stappen):
        return "De bron was niet bereikbaar; probeer het over een paar minuten opnieuw."
    mislukt = sum(1 for naam, r in stappen if naam == TOOL_QUERY_DATA and outcome(naam, r).get("status"))
    if mislukt >= 2:
        return (
            f"Het filteren van de opgehaalde data lukte niet: {mislukt} filterstappen gaven een fout of 0 rijen. "
            "Vaak helpt het de vraag op te splitsen, bijvoorbeeld eerst één jaar of één indeling."
        )
    return "Het maximale aantal stappen was op voordat de vraag beantwoord was."


def zonder_antwoord(stappen: list[Stap]) -> str:
    """Het bericht als ook de afrondronde geen antwoord gaf: wat er is, en waar het vastliep."""
    bronnen = _bronnen(stappen)
    opgehaald = (
        "Wel opgehaald:\n" + "\n".join(f"- {b}" for b in bronnen) if bronnen else "Er is nog geen data opgehaald."
    )
    return f"Ik kwam niet tot een antwoord. {_oorzaak(stappen)}\n\n{opgehaald}"
