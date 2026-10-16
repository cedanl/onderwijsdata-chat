"""Algemene feedback via de Feedback-link (#600): een idee, probleem of compliment los van een antwoord of rapport.

Naast de feedback per antwoord (#248, core/answer_feedback.py) en op een rapport (#250, core/feedback.py). De tekst
is verplicht; de soort kiest de gebruiker optioneel; de pagina vult de app zelf in, zodat het team weet waar het
bericht vandaan kwam.
"""

from typing import Literal

Soort = Literal["idee", "probleem", "compliment"]

MAX_TEKST = 2000
# Een route van de app ("/", "/chat", "/rapporten"), geen URL: geen host, geen query, geen gesprek-ID.
PAGINA_PATROON = r"^/[a-z-]{0,30}$"


def als_markdown(rijen: list[dict]) -> str:
    """De berichten als één leesbaar overzicht voor het team, in de volgorde van `rijen`."""
    blokken = []
    for rij in rijen:
        soort = f" · {rij['soort']}" if rij["soort"] else ""
        blokken.append(f"## {rij['created_at']} · {rij['username']}{soort} · {rij['pagina']}\n\n{rij['tekst']}")
    return "\n\n---\n\n".join(blokken) + "\n" if blokken else "Nog geen algemene feedback.\n"
