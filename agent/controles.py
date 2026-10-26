"""De antwoordcontrole van `run`: wat een geldig antwoord is, los van streamen en publiceren (#694).

Alles hier is invoer → bevindingen, zonder `emit` en zonder sessie: wat de controle van het gesprek moet weten
(`clarify_keuzes`, `data_keys`) komt als parameter binnen. Een nieuwe antwoordcontrole komt in de lijst in
`antwoordcontrole` (zie CONTRIBUTING.md, "Een antwoordcontrole toevoegen"); `agent/run.py` roept hem alleen aan.
"""

import logging
from collections.abc import Callable

from .aanspreekcontrole import overgebleven_u_vorm
from .antwoordtaal import Taal, taal, verkeerde_antwoordtaal
from .beweringen import onbeschikbaar_zonder_zoekpad, ongedekte_oorzaak
from .binding import verkeerd_gebonden
from .bronvermelding import zonder_bronnensectie
from .dimensielabels import verkeerde_dimensielabels
from .getalnotatie import engels_gelezen, nl_notatie
from .grafiekvraag import ontbrekende_grafiek
from .grounding import afgeleide_verschillen, unverified
from .kenmerken import verkeerde_kenmerken
from .keuze import genegeerde_keuze
from .kpi_periode import verkeerde_kpi_periodes
from .kpi_scope import kpi_naast_filter
from .labels import onbekende_datasets, ongebruikte_bronnen, verkeerde_opleidingsvormen
from .metatekst import metatekst, zonder_toolnamen
from .probleem import Probleem, hard, uitkomsten, veilig
from .selectie import ontbrekende_instellingen, ontbrekende_schooljaren, onvolledige_selecties
from .tekens import zonder_citaatkop
from .zelfcorrectie import zonder_zelfcorrectie

# De regel CONTROLES blijft onder de logger van `agent/run.py`: logfilters en tests kennen die bron, en de verhuizing
# van de code is geen reden om hem te veranderen (#694).
logger = logging.getLogger("agent.run")


def correctie(problems: list[str]) -> str:
    return (
        "Controle van je antwoord tegen de data van dit gesprek:\n"
        + "\n".join(f"- {p}" for p in problems)
        + "\nReken niet zelf en rond niet af: haal elk getal op met query_data (group_by/aggregate) "
        "of compute_kpi, selecteer het gevraagde schooljaar en de gevraagde instelling, of laat het weg. "
        "Dat geldt ook voor verschillen, percentages en aandelen: bereken die met compute_kpi of query_data, "
        "schrijf ze niet uit je hoofd op.\n"
        "Schrijf daarna een volledig nieuw antwoord voor de gebruiker, alsof het het eerste is: zonder kop of inleiding "
        "over de herziening, zonder te verwijzen naar een eerdere versie of naar deze controle, en zonder toolnamen."
    )


def leestekst(antwoord: str) -> str:
    """De tekst waarop de taal van het antwoord beslist wordt: wat de gebruiker leest, zonder zelfcorrectie,
    eigen Bronnen-sectie, toolnamen en citaatkop (#326).

    Controles en weergave beslissen de taal op deze tekst. Op de ruwe modeltekst maakte een Nederlandse
    Bronnen-lijst een Engels antwoord Nederlands voor de controle, terwijl de gebruiker het Engels las."""
    zonder_correctie, _ = zonder_zelfcorrectie(antwoord)
    return zonder_citaatkop(zonder_toolnamen(zonder_bronnensectie(zonder_correctie)))


def geschreven_taal(antwoord: str) -> Taal | None:
    return taal(leestekst(antwoord))


def lezingen(antwoord: str) -> list[str]:
    """Het antwoord met de getallen zoals de grondingscontrole ze moet lezen: zoals de gebruiker ze ziet.

    Een Nederlands antwoord krijgt na de controle de notatie (9.5% wordt 9,5%), dus toetst de controle die al.
    Een Engels antwoord houdt 12,345: dat is twaalfduizend, geen twaalf met decimalen. Bij een onduidelijke taal
    leest de gebruiker 12,345 misschien zo of zo: dan toetst de controle beide lezingen (#326)."""
    geschreven = geschreven_taal(antwoord)
    lezingen = []
    if geschreven != "en":
        lezingen.append(nl_notatie(antwoord))
    if geschreven != "nl":
        lezingen.append(engels_gelezen(antwoord))
    return lezingen


def maak_getalcontrole(earlier: list[str], said_by_user: list[str]) -> Callable[[str, list[str]], list[Probleem]]:
    """De getalcontrole van een antwoord: per getal dat niet in de data staat één probleem.

    Wat de assistent al zei telt als bron: een vervolgvraag mag een getal uit een eerdere
    beurt herhalen. Wat de gebruiker zei niet (#211): dat is een bewering om te toetsen.
    """

    def ongedekt(n: str) -> Probleem:
        # In de notatie van het antwoord dat de gebruiker ziet (CH-11r).
        getal = nl_notatie(n)
        if unverified(n, [], said_by_user):
            (verzonnen,) = hard([Probleem(f"{getal} staat niet in de opgehaalde data.")])
            verzonnen.getal = n
            return verzonnen
        # Zacht: een correcte weerlegging citeert het getal van de gebruiker ook (#207, #214).
        return Probleem(
            f"{getal} staat alleen in een eerder bericht van de gebruiker, niet in de opgehaalde data.",
            "Dat is een bewering om te toetsen: haal het getal uit de data of laat het weg.",
        )

    def ongedekt_gelezen(gelezen: str, tool_results: list[str]) -> list[str]:
        # Het verschil van twee genoemde getallen uit de data is na te rekenen, niet verzonnen (CH-01).
        afgeleid = afgeleide_verschillen(gelezen, tool_results)
        return [n for n in unverified(gelezen, tool_results, earlier) if n not in afgeleid]

    def ongedekte_getallen(text: str, tool_results: list[str]) -> list[Probleem]:
        # Een getal dat in één lezing ongedekt is, telt: ook 3303 en 3.303 uit twee lezingen geven één melding.
        gevonden = [n for gelezen in lezingen(text) for n in ongedekt_gelezen(gelezen, tool_results)]
        return list(dict.fromkeys(ongedekt(n) for n in gevonden))

    return ongedekte_getallen


def antwoordcontrole(
    vraag: str,
    earlier: list[str],
    said_by_user: list[str],
    clarify_keuzes: list,
    data_keys: list[str],
    getalcontrole: Callable[[str, list[str]], list[Probleem]] | None = None,
) -> Callable[[str, list[str]], list[str]]:
    """De controle van een antwoord tegen de data van dit gesprek, voor tool_loop."""
    getalcontrole = getalcontrole or maak_getalcontrole(earlier, said_by_user)

    def ongedekte_getallen(text: str, tool_results: list[str]) -> list[str]:
        return list(getalcontrole(text, tool_results))

    def check(text: str, tool_results: list[str]) -> list[str]:
        gelezen = leestekst(text)
        # (controle, argumenten, hard): blijft een hard probleem na de herkansing, dan wordt het antwoord
        # ingehouden (#207).
        controles = [
            (ongedekte_getallen, (text, tool_results), False),
            (ontbrekende_schooljaren, (vraag, tool_results), True),
            (ontbrekende_instellingen, (vraag, tool_results), True),
            (onvolledige_selecties, (text, tool_results), True),
            (verkeerde_opleidingsvormen, (text, tool_results), False),
            (verkeerde_dimensielabels, (text, tool_results), False),
            (onbekende_datasets, (text,), False),
            (ongebruikte_bronnen, (text, tool_results), False),
            (verkeerd_gebonden, (text, tool_results), False),
            (verkeerde_kenmerken, (text, tool_results), True),
            (verkeerde_kpi_periodes, (text, tool_results), True),
            (kpi_naast_filter, (text, tool_results), False),
            (genegeerde_keuze, (clarify_keuzes, text), False),
            (onbeschikbaar_zonder_zoekpad, (vraag, text, tool_results), False),
            (ongedekte_oorzaak, (text, tool_results), False),
            (ontbrekende_grafiek, (vraag, text, tool_results, data_keys), False),
            (metatekst, (text,), False),
            (verkeerde_antwoordtaal, (vraag, gelezen), False),
            # Op de tekst na de omzetting naar de je-vorm, zoals in _antwoordtekst (#536).
            (overgebleven_u_vorm, (gelezen, taal(gelezen)), False),
        ]
        problemen: list[str] = [
            p
            for controle, args, streng in controles
            for p in (hard(veilig(controle, *args)) if streng else veilig(controle, *args))
        ]
        # Per antwoord welke controle wat gaf: regressietestbaar en de afvuurfrequentie per controle (CH-01).
        per_controle = uitkomsten((c.__name__ for c, _, _ in controles), problemen)
        logger.info("CONTROLES  %s", "  ".join(f"{naam}={uitkomst}" for naam, uitkomst in per_controle.items()))
        return problemen

    return check
