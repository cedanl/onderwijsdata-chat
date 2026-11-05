"""De onderwijsaanbieders van een instelling in RIO v3: de sleutel van het aanbod per locatie naar het BRIN (#744).

Het opleidingsaanbod per onderwijslocatie (RIO, en DUO's export ``mbo_opleidingsaanbod``) noemt de aanbieder
(``ONDERWIJSAANBIEDERID``, bijvoorbeeld ``100A932`` "Zone.college mbo"), niet het BRIN waaronder DUO de studenten telt.
``/erkenningen/{brin}/organisatorische-eenheden`` geeft per instelling haar aanbieders; zo komt een locatie bij de
instelling (``31JC``). Nagegaan op 05-11-2026: voor alle 55 BRIN's in DUO's mbo-studenten-per-instelling geeft deze
route een antwoord. De omgekeerde route (``/organisatorische-eenheden/{aanbieder}/erkenningen``) gaf voor 23 van de
407 aanbieders HTTP 500, waaronder Summa College en Koning Willem I College, en de locatiegebruiken dragen bij 459 van
de 570 mbo-locaties geen erkenning: die twee routes zijn niet bruikbaar.

Elke aanroep geeft ``datumGeldigOp`` mee. Een bronfout gaat naar de aanroeper.
"""

from __future__ import annotations

import datetime as dt

from .client import related

_AANBIEDER = "ONDERWIJSAANBIEDER"


def _iso(datum: dt.date | str | None) -> str:
    if datum is None:
        return dt.date.today().isoformat()
    return datum.isoformat() if isinstance(datum, dt.date) else str(datum)


def _in_bedrijf(eenheid: dict, peil: str) -> bool:
    begin, eind = eenheid.get("inbedrijfdatum"), eenheid.get("uitbedrijfdatum")
    return (not begin or begin <= peil) and (not eind or eind > peil)


def onderwijsaanbieders(brin: str, peildatum: dt.date | str | None = None) -> list[str]:
    """De codes van de onderwijsaanbieders van erkenning ``brin`` die op ``peildatum`` (standaard vandaag) in bedrijf
    zijn, gesorteerd. Leeg als RIO er geen kent; een bestuur of andere eenheid telt niet mee."""
    peil = _iso(peildatum)
    eenheden = related("erkenningen", brin, "organisatorische-eenheden", datumGeldigOp=peil)
    return sorted({str(e["code"]) for e in eenheden if e.get("type") == _AANBIEDER and _in_bedrijf(e, peil)})
