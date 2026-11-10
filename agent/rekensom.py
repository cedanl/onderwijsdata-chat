"""Een uitgeschreven rekensom in het antwoord moet kloppen (#1001).

Foutklasse: "Dat zijn 3 x 3 x 3 x 4 x 15 = 540 combinaties." (reaudit 10-11, met het vermenigvuldigingsteken): de
som is 1.620. De getalcontrole ziet dat niet, want 540 heeft geen vier cijfers en een uitkomst van vier cijfers kan
toevallig in de data staan. Deze controle rekent elke som met `=` binnen één zin na, met `Decimal` en de gewone
voorrang (eerst keer en gedeeld door, dan plus en min), zonder `eval`. De uitkomst mag afgerond zijn op het aantal
decimalen dat het antwoord schrijft ("571 / 8.060 x 100 = 7,1"); met een procentteken telt ook de breuk zelf
("1 / 3 = 33%").

Streng en stil: alleen getallen in Nederlandse notatie (punt voor duizendtallen, komma voor decimalen) met de tekens
voor keer, gedeeld door, plus en min (_KEER, _DELING, _MIN), zonder haakjes en zonder minteken voor het eerste getal.
Een schooljaar of jaarreeks (2024/25, 2019-2023) is geen deling of aftrekking, en een zin met "ongeveer", "circa" of
het teken voor "bij benadering" is geen som om na te rekenen. Wat daarbuiten valt, slaat de controle over.

Eigenaar: `agent/`, naast de getalcontrole (`agent/grounding.py`). Heroverwegen als de controle een kwartaal lang
niet afgaat in de logregel CONTROLES.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .probleem import Probleem

# Een getal zoals de grondingscontrole het leest (378.490, 7,1), maar zonder spatie als duizendtalscheiding: in een
# som scheidt een spatie twee getallen. Niet aan een letter of cijfer vast (85423NED, 2024SJ00), behalve aan de x van
# een vermenigvuldiging (3x4), en niet halverwege een getal (1.62 of 3.14.8).
_GETAL = r"(?<![^\Wx])(?<![.,])(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?(?![^\Wx])(?![.,]\d)"
_TOKEN = re.compile(
    rf"(?P<getal>{_GETAL})|(?P<op>[×x*+−\-÷/])|(?P<is>=)|(?P<spatie>[ \t\u00a0\u202f]+)|(?P<ander>.)", re.DOTALL
)
_KEER = "×x*"
_DELING = "÷/"
_MIN = "−-"
_ZIN = re.compile(r"(?<=[.!?])\s+|\n+")
_BIJ_BENADERING = re.compile(r"\b(?:ongeveer|circa)\b|≈", re.IGNORECASE)
_JAREN = range(1900, 2101)
_MAX_GETALLEN = 20


@dataclass(frozen=True)
class _Token:
    soort: str
    tekst: str
    begin: int
    eind: int


@dataclass(frozen=True)
class _Som:
    links: str  # de som zoals ze er staat: "3 × 3 × 3 × 4 × 15"
    getallen: list[str]
    tekens: list[str]
    uitkomst: str  # zoals ze er staat, zonder procentteken
    procent: bool


def _tokens(zin: str) -> list[_Token]:
    return [
        _Token(soort, m.group(0), m.start(), m.end())
        for m in _TOKEN.finditer(zin)
        if (soort := m.lastgroup or "ander") != "spatie"
    ]


def _waarde(getal: str) -> Decimal:
    return Decimal(getal.replace(".", "").replace(",", "."))


def _jaarpaar(links: str, teken: str, rechts: str) -> bool:
    """2024/25, 2023/2024, 2019-2023 of 2023-24: een schooljaar of jaarreeks, geen deling of aftrekking.

    2024 - 2019 blijft een aftrekking: het tweede jaar ligt vóór het eerste."""
    if teken not in _DELING + _MIN or not links.isdigit() or int(links) not in _JAREN or not rechts.isdigit():
        return False
    if len(rechts) == 2:
        return True
    return len(rechts) == 4 and int(rechts) in _JAREN and (teken in _DELING or int(rechts) > int(links))


def _rechterkant(tokens: list[_Token], i: int) -> tuple[str, bool] | None:
    """Het getal na het `=` op plek `i`, en of er een procentteken bij staat; None als er geen enkel getal staat."""
    if i + 1 >= len(tokens) or tokens[i + 1].soort != "getal":
        return None
    j = i + 2
    procent = j < len(tokens) and tokens[j].tekst == "%"
    j += int(procent)
    if j + 1 < len(tokens) and tokens[j].soort == "op" and tokens[j + 1].soort == "getal":
        return None  # "= 10 + 2": rechts staat weer een som
    return tokens[i + 1].tekst, procent


def _linkerkant(tokens: list[_Token], i: int) -> list[_Token] | None:
    """De som vóór het `=` op plek `i`: getal, teken, getal, ...; None zonder teken of met een teken vooraan (-3)."""
    deel: list[_Token] = []
    k = i - 1
    while k >= 0 and tokens[k].soort == ("getal" if len(deel) % 2 == 0 else "op"):
        deel.append(tokens[k])
        k -= 1
    if len(deel) < 3 or len(deel) % 2 == 0 or len(deel) > 2 * _MAX_GETALLEN:
        return None
    return deel[::-1]


def _sommen(zin: str) -> list[_Som]:
    tokens = _tokens(zin)
    sommen = []
    for i, token in enumerate(tokens):
        if token.soort != "is" or (rechts := _rechterkant(tokens, i)) is None:
            continue
        if (links := _linkerkant(tokens, i)) is None:
            continue
        getallen, tekens = [t.tekst for t in links[::2]], [t.tekst for t in links[1::2]]
        if any(_jaarpaar(a, teken, b) for a, teken, b in zip(getallen, tekens, getallen[1:], strict=False)):
            continue
        uitkomst, procent = rechts
        sommen.append(_Som(zin[links[0].begin : links[-1].eind], getallen, tekens, uitkomst, procent))
    return sommen


def _uitrekenen(getallen: list[str], tekens: list[str]) -> Decimal | None:
    """De som met de gewone voorrang: eerst keer en gedeeld door, dan plus en min. None bij delen door nul."""
    termen = [_waarde(getallen[0])]
    plus_min: list[str] = []
    for teken, getal in zip(tekens, getallen[1:], strict=True):
        waarde = _waarde(getal)
        if teken in _KEER:
            termen[-1] *= waarde
        elif teken in _DELING:
            if waarde == 0:
                return None
            termen[-1] /= waarde
        else:
            plus_min.append(teken)
            termen.append(waarde)
    uitkomst = termen[0]
    for teken, term in zip(plus_min, termen[1:], strict=True):
        uitkomst = uitkomst - term if teken in _MIN else uitkomst + term
    return uitkomst


def _decimalen(getal: str) -> int:
    return len(getal.split(",")[1]) if "," in getal else 0


def _afgerond(waarde: Decimal, decimalen: int) -> Decimal | None:
    try:
        return waarde.quantize(Decimal(1).scaleb(-decimalen), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None  # te groot om op deze decimalen af te ronden


def _nl(waarde: Decimal, decimalen: int) -> str:
    """1620 → 1.620, 7.08 → 7,1 bij één decimaal."""
    return f"{waarde:,.{decimalen}f}".translate(str.maketrans(",.", ".,"))


def _fout(som: _Som) -> Probleem | None:
    if (berekend := _uitrekenen(som.getallen, som.tekens)) is None:
        return None
    decimalen = _decimalen(som.uitkomst)
    gegeven = _waarde(som.uitkomst)
    # Met een procentteken mag de som de breuk zijn (1 / 3 = 33%) of al het percentage (1 / 3 × 100 = 33,3%).
    kandidaten = [berekend, berekend * 100] if som.procent else [berekend]
    if any(_afgerond(k, decimalen) == gegeven for k in kandidaten):
        return None
    if (afgerond := _afgerond(berekend, decimalen)) is None:
        return None
    procent = "%" if som.procent else ""
    return Probleem(
        f"De som klopt niet: {som.links} is {_nl(afgerond, decimalen)}{procent}, niet {som.uitkomst}{procent}.",
        "Reken de som na met een tool, of laat de som en haar uitkomst weg.",
    )


def _fouten(tekst: str) -> list[Probleem]:
    return [
        probleem
        for zin in _ZIN.split(tekst)
        if "=" in zin and not _BIJ_BENADERING.search(zin)
        for som in _sommen(zin)
        if (probleem := _fout(som))
    ]


def onjuiste_rekensommen(tekst: str, *andere_lezingen: str) -> list[Probleem]:
    """Elke rekensom met `=` in één zin waarvan de uitkomst niet klopt, ook na afronden.

    `andere_lezingen`: dezelfde tekst met de getallen anders gelezen (controles.lezingen, bij een antwoord waarvan de
    taal en dus de notatie onduidelijk is). Een som is dan alleen fout als ze in elke lezing fout is: 1,620 is in de
    ene lezing 1,62 en in de andere 1.620.
    """
    problemen = _fouten(tekst)
    for lezing in andere_lezingen:
        ook = set(_fouten(lezing))
        problemen = [p for p in problemen if p in ook]
    return problemen
