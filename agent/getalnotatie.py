"""Eén getalnotatie in tekst, tabel en grafiek (CH-11r, #445).

De grafiek, de KPI en de controlemeldingen schrijven 3.303 (tools/getal.py, #418); het
model schreef in de tekst en in markdowntabellen soms 3303. Een regel in de prompt
alleen is niet genoeg, dus zet de code elk geheel getal van vier of meer cijfers in
het antwoord om naar de Nederlandse notatie: punt voor duizendtallen, de decimale
komma blijft staan.

Wat geen hoeveelheid is, blijft zoals het staat: jaartallen (dezelfde grens als de
grondingscontrole), codes (85423NED, een voorloopnul, een getal na "CROHO" of "code",
een cel in een kolom met zo'n kop, een getal dat de tooluitvoer van de beurt alleen als
code geeft of dat een eerder antwoord zonder punt schreef), een postcode, al genoteerde
getallen, een Engelse decimale punt, code, links en HTML. De grondingscontrole leest 3303
en 3.303 als hetzelfde getal, dus ze vindt na de omzetting hetzelfde.

Alles loopt in lineaire tijd: de functie draait synchroon op het eindantwoord, en een
patroon dat terugzoekt over modeluitvoer bevriest elke sessie op de worker.
"""

import re
from collections.abc import Iterable

from .grounding import checked
from .meetwaarden import identificaties, meetwaarden

# Een geheel getal, zonder of met spatie als duizendtalscheiding (gpt-oss, #236), en een
# eventuele decimale komma. Niet aan een letter, cijfer, punt, komma of schuine streep vast:
# dan is het een code (85423NED, T001228), al genoteerd (3.303) of een jaar (2023/24).
# Ook niet na "letter-" of "letter:" (CROHO-12345, een data_key) of voor "-letter".
_GETAL = re.compile(
    r"(?<![\w.,/#])(?<![^\W\d_]-)(?<!\w:)"
    r"(?P<geheel>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?P<decimalen>,\d+)?"
    r"(?!\w)(?![.,/:]\d)(?!-[^\W\d_])"
)
_SCHEIDING = re.compile(r"[ \u00a0\u202f]")
# Na het getal, als losse toets op de plek erna: in _GETAL zelf zou zo'n lookahead terugzoeken
# over elke groep van "1 234 234 …". Een los groepje (3303 456: met een punt leest de controle
# één getal), een percentage (12.345% herkent ze niet) en de letters van een postcode.
_LOS_GROEPJE = re.compile(r"[ \u00a0\u202f]\d{3}(?!\d)")
_PROCENT = re.compile(r"\s?(?:%|procent\b)")
_POSTCODE = re.compile(r"[ \u00a0]?[A-Z]{2}(?![\w-])")
# Daarboven is het geen aantal; float zou de cijfers ook veranderen.
_MAX_CIJFERS = 15

# Woorden waarna een getal een code is, en de kop van een kolom met codes.
_CODEWOORD = r"\w*codes?|croho|crebo|isat|brin|id|nummers?|nr"
_CODEKOP = re.compile(rf"\b(?:{_CODEWOORD})\b", re.IGNORECASE)
# Het woord, eventueel gevolgd door eerdere codes in een opsomming: "codes 34479, 34480 en".
_NA_CODEWOORD = re.compile(
    rf"\b(?:{_CODEWOORD}|tabel(?:len)?|dataset)\b[\s:#=(]*(?:\d+(?:\s*,\s*|\s+(?:en|of)\s+))*$",
    re.IGNORECASE,
)
_VENSTER = 80

# Ongemoeid: inline code (ook tussen dubbele backticks), links en hun doel, HTML-tags.
# Lineair: geen alternatief zoekt vanaf elk volgend begin opnieuw tot het einde van de regel.
# Een linkdoel mag één paar haakjes bevatten (wiki/Lijst_(12345)); elk teken past op één
# manier, dus terugzoeken blijft binnen dat ene doel.
_BESCHERMD = re.compile(
    r"``[^\n]*?``|`[^`\n]*`|https?://[^\s<>()]+|www\.[^\s<>()]+|\]\((?:[^()\n]|\([^()\n]*\))*\)|<[^<>\n]+>"
)
_CODEBLOK = re.compile(r"^\s*(```|~~~)")
_REFERENTIE = re.compile(r" {0,3}\[[^\]\n]*\]:")  # [1]: /pad?n=12345
_TABELTEKENS = " \t\r|:-"


def _tabelscheiding(regel: str) -> bool:
    """|---|---:|: alleen pijpen, streepjes, dubbelepunten en witruimte, met een pijp en een streepje."""
    return "|" in regel and "-" in regel and not regel.strip(_TABELTEKENS)


def _geen_hoeveelheid(m: re.Match, cijfers: str, codes: frozenset[str]) -> bool:
    if len(cijfers) > _MAX_CIJFERS or cijfers.startswith("0") or not checked(cijfers) or cijfers in codes:
        return True
    na = m.end()
    if _LOS_GROEPJE.match(m.string, na) or _PROCENT.match(m.string, na):
        return True
    if len(cijfers) == 4 and not m.group("decimalen") and _POSTCODE.match(m.string, na):
        return True
    return bool(_NA_CODEWOORD.search(m.string[max(0, m.start() - _VENSTER) : m.start()]))


def _hoeveelheid(m: re.Match, codes: frozenset[str]) -> str:
    cijfers = _SCHEIDING.sub("", m.group("geheel"))
    if _geen_hoeveelheid(m, cijfers, codes):
        return m.group(0)
    # Rechtstreeks uit de int, niet via float: die verandert vanaf 2^53 de cijfers.
    return f"{int(cijfers):,}".replace(",", ".") + (m.group("decimalen") or "")


def _in_tekst(tekst: str, codes: frozenset[str]) -> str:
    """De notatie in een stuk lopende tekst, buiten code, links en HTML."""

    def omzetten(stuk: str) -> str:
        return _GETAL.sub(lambda m: _hoeveelheid(m, codes), stuk)

    stukken, vorige = [], 0
    for m in _BESCHERMD.finditer(tekst):
        stukken += [omzetten(tekst[vorige : m.start()]), m.group(0)]
        vorige = m.end()
    return "".join([*stukken, omzetten(tekst[vorige:])])


def _codekolommen(kop: str) -> set[int]:
    return {i for i, cel in enumerate(kop.split("|")) if _CODEKOP.search(cel)}


def _tabelrij(regel: str, codekolommen: set[int], codes: frozenset[str]) -> str:
    return "|".join(cel if i in codekolommen else _in_tekst(cel, codes) for i, cel in enumerate(regel.split("|")))


def _ongepunt(eerder: Iterable[str]) -> set[str]:
    """Getallen van vier of meer cijfers die een eerder antwoord zonder punt schreef: daar bleven ze als code staan."""
    return {
        cijfers
        for tekst in eerder
        for m in _GETAL.finditer(tekst)
        if len(cijfers := m.group("geheel")) >= 4 and cijfers.isascii() and cijfers.isdigit()
    }


def _codes(stappen: Iterable[tuple[str, str]], eerder: Iterable[str]) -> frozenset[str]:
    """De cijfers die de tooluitvoer van de beurt of een eerder antwoord alleen als code geeft, nooit als meetwaarde.

    "Rechten (50800)" las met een punt als een aantal, naast "3.303 studenten" (#445). Een
    vervolgvraag die de code herhaalt zonder haar opnieuw te laden, vindt haar in het eerdere antwoord."""
    stappen = list(stappen)
    gemeten = {c for tool, result in stappen for w in meetwaarden(result, tool) for c in w.cijfers}
    codes = {c for _, result in stappen for c in identificaties(result)} | _ongepunt(eerder)
    return frozenset(codes - gemeten)


def nl_notatie(tekst: str, stappen: Iterable[tuple[str, str]] = (), eerder: Iterable[str] = ()) -> str:
    """`tekst` met elk geheel getal van vier of meer cijfers, geen jaar of code, als 3.303.

    `stappen`: (tool, resultaat) van de beurt; een getal dat daar alleen als code staat, blijft staan.
    `eerder`: de eerdere antwoorden; een getal dat daar zonder punt staat, blijft ook staan."""
    codes = _codes(stappen, eerder)
    regels = tekst.split("\n")
    uit: list[str] = []
    in_codeblok = False
    codekolommen: set[int] | None = None  # None: niet in een tabel
    for i, regel in enumerate(regels):
        if hek := bool(_CODEBLOK.match(regel)):
            in_codeblok = not in_codeblok
        if in_codeblok or hek or _REFERENTIE.match(regel):
            uit.append(regel)
            continue
        if "|" not in regel:
            codekolommen = None
        elif i + 1 < len(regels) and _tabelscheiding(regels[i + 1]):
            codekolommen = _codekolommen(regel)
        uit.append(_tabelrij(regel, codekolommen, codes) if codekolommen is not None else _in_tekst(regel, codes))
    return "\n".join(uit)
