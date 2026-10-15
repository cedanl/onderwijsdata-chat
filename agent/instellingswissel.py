"""Een instellingswissel midden in een gesprek is geen fout in een eerder antwoord (#543).

BEV-01: na de wissel van Hogeschool Utrecht naar HAN in hetzelfde gesprek opende het
volgende antwoord met "Correctie op mijn vorige antwoord: ... Dat was onjuist, want jouw
instelling is de HAN." Het profiel zegt per beurt alleen de instelling van nú, en de history
draagt een antwoord over de vorige instelling zonder te zeggen bij welke instelling het
hoorde. Het model las dat als tegenspraak en "corrigeerde" een juist antwoord.

De code onthoudt per beantwoorde beurt de instelling van het profiel en zegt het model
bij een wissel in één vaste regel wat er is gebeurd. Geen modelronde en geen filter op
het antwoord: de oorzaak zit in de context, dus daar staat de fix.
"""

from collections.abc import Iterable

_GEEN_INSTELLING = "geen instelling"


def eerdere_instellingen(turns: Iterable[dict]) -> list[str]:
    """De instellingen waarop de beantwoorde beurten van dit gesprek rustten, elk één keer, in volgorde.

    Een beurt zonder profielinstelling telt niet mee: zo'n antwoord ging over niemands 'wij'."""
    gezien: dict[str, None] = {}
    for beurt in turns:
        naam = " ".join((beurt.get("instelling") or "").split())
        if naam:
            gezien.setdefault(naam, None)
    return list(gezien)


def wisselcontext(huidig: str | None, eerdere: Iterable[str]) -> str:
    """De vaste regel voor het model als het profiel nu een andere instelling noemt dan eerdere antwoorden.

    Leeg als er niets gewisseld is: geen eerdere beurt met een instelling, of dezelfde als nu."""
    nu = " ".join((huidig or "").split())
    vorige = [naam for naam in eerdere if naam != nu]
    if not vorige:
        return ""
    waarover = _opsomming([f"**{naam}**" for naam in vorige])
    regel = (
        "Instellingswissel: de gebruiker koos in dit gesprek een andere instelling. "
        f"Eerdere antwoorden gingen over {waarover} en waren daarvoor juist: corrigeer ze niet en noem ze niet onjuist. "
    )
    if nu:
        return regel + (
            f"Beantwoord deze en volgende vragen voor **{nu}**; 'wij', 'onze' en 'mijn instelling' betekenen nu {nu}."
        )
    return regel + (
        f"Het profiel noemt nu {_GEEN_INSTELLING}: vraag bij 'wij', 'onze' of 'mijn instelling' welke instelling bedoeld is."
    )


def _opsomming(delen: list[str]) -> str:
    if len(delen) == 1:
        return delen[0]
    return ", ".join(delen[:-1]) + " en " + delen[-1]
