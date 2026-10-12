"""Een vage vraag krijgt een zichtbare interpretatie (#514, UX F07b).

"studentenwelzijn" leverde zonder navraag een grafiek over werkdruk bij gepromoveerden: het
model koos stilzwijgend een lezing. Of het model eerst vraagt (clarify_scope) blijft aan het
model (#348); hier staat de zichtbare kant in code. Rust het antwoord op een gekozen lezing
van een thema zonder maat, dan opent het met "Ik ga uit van …" en noemt het de datasets
waarop het rust, met hun titel uit de catalogus. Geen modeltekst, geen getallen: de zin komt
uit de toolstappen, net als de Bronnen eronder (#416).
"""

import re

from tools import store
from tools.catalog import catalogus_titel

from .selectie import laadkey, stapkeys

_MAX_WOORDEN = 4
# Een maat, een vraagvorm of een zoekopdracht: dan is de vraag niet vaag, hoe kort ook.
_MAAT = re.compile(
    r"\b(hoeveel|aantal(len)?|instroom|uitstroom|uitval|diploma\w*|gediplomeerd\w*|inschrijving\w*|"
    r"ingeschreven\w*|rendement|doorstroom|vacature\w*|prognose\w*|percentage|procent|gemiddeld\w*|"
    r"totaal|trend|groei|daling|vergelijk\w*|verschil|zoek\w*|welke|wat|waarom|hoe|toon|definitie|datasets?|bronnen?)\b",
    re.IGNORECASE,
)
# Het model benoemde zijn lezing al zelf, in de eerste regels.
_EIGEN_LEZING = re.compile(
    r"\b(ik ga uit van|ik ga er ?van uit|ik interpreteer|opgevat als|ik neem aan|aanname|ik lees)\b", re.IGNORECASE
)
_MAX_TITELS = 3


def is_vaag(vraag: str) -> bool:
    """Een kort thema zonder maat, getal of vraagwoord: 'studentenwelzijn', 'kwaliteit van het onderwijs'."""
    tekst = " ".join((vraag or "").split()).strip(" ?!.,:")
    if not tekst or any(ch.isdigit() for ch in tekst):
        return False
    return len(tekst.split()) <= _MAX_WOORDEN and not _MAAT.search(tekst)


def _titels(steps: list[tuple[str, str]]) -> list[str]:
    """De catalogustitels van de datasets waarop de beurt rust, in volgorde; zonder cijfers (de citaties tellen getallen)."""
    titels: list[str] = []
    for _tool, result in steps:
        for key in stapkeys(result):
            known = store.meta(laadkey(key))
            if known is None:
                continue
            titel = catalogus_titel(known.dataset)
            if titel and titel != known.dataset and not any(c.isdigit() for c in titel) and titel not in titels:
                titels.append(titel)
    return titels


def interpretatiezin(vraag: str, steps: list[tuple[str, str]]) -> str | None:
    """De zin die zegt op welke lezing het antwoord rust; None als de beurt geen bekende dataset las."""
    titels = _titels(steps)
    if not titels:
        return None
    lezing = "; ".join(titels[:_MAX_TITELS])
    return (
        f"Ik ga uit van de lezing «{lezing}» voor je vraag '{' '.join(vraag.split())}'. "
        "Bedoel je iets anders, noem dan de maat of de bron die je zoekt."
    )


def met_interpretatie(tekst: str, vraag: str, steps: list[tuple[str, str]], session: dict) -> str:
    """Het antwoord met de interpretatiezin ervoor, als de vraag vaag was en het antwoord op data rust.

    Niet na een verduidelijkingskaart (dan koos de gebruiker de lezing al), en niet als het
    model zijn lezing zelf al benoemde.
    """
    if session.get("clarify_rondes", 0) or not is_vaag(vraag) or _EIGEN_LEZING.search(tekst[:400]):
        return tekst
    zin = interpretatiezin(vraag, steps)
    return f"{zin}\n\n{tekst}" if zin else tekst
