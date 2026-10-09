"""Eén getalnotatie in tekst, tabel en grafiek (CH-11r, #445).

De grafiek, de KPI en de controlemeldingen schrijven 3.303 (tools/getal.py, #418); het
model schreef in de tekst en in markdowntabellen soms 3303. Een regel in de prompt
alleen is niet genoeg, dus zet de code elk geheel getal van vier of meer cijfers in
het antwoord om naar de Nederlandse notatie: punt voor duizendtallen, de decimale
komma blijft staan.

Wat geen hoeveelheid is, blijft zoals het staat: jaartallen (dezelfde grens als de
grondingscontrole), codes (85423NED, een voorloopnul, een getal na "CROHO" of "code",
een cel in een kolom met zo'n kop), al genoteerde getallen, een Engelse decimale punt,
code, links en HTML. De grondingscontrole leest 3303 en 3.303 als hetzelfde getal,
dus ze vindt na de omzetting hetzelfde.
"""

import re

from tools.getal import nl_getal

from .grounding import checked

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

# Woorden waarna een getal een code is, en de kop van een kolom met codes.
_CODEWOORD = r"\w*codes?|croho|crebo|isat|brin|id|nummers?|nr"
_CODEKOP = re.compile(rf"\b(?:{_CODEWOORD})\b", re.IGNORECASE)
# Het woord, eventueel gevolgd door eerdere codes in een opsomming: "codes 34479, 34480 en".
_NA_CODEWOORD = re.compile(
    rf"\b(?:{_CODEWOORD}|tabel(?:len)?|dataset)\b[\s:#=(]*(?:\d+(?:\s*,\s*|\s+(?:en|of)\s+))*$",
    re.IGNORECASE,
)
_VENSTER = 80

# Ongemoeid: inline code, links en hun doel, HTML-tags.
_BESCHERMD = re.compile(r"`[^`\n]*`|https?://[^\s<>()]+|\]\([^)\n]*\)|<[^<>\n]+>")
_CODEBLOK = re.compile(r"^\s*(```|~~~)")
_TABELSCHEIDING = re.compile(r"^[\s|:-]*-[\s|:-]*$")


def _hoeveelheid(m: re.Match) -> str:
    geschreven = m.group(0)
    cijfers = _SCHEIDING.sub("", m.group("geheel"))
    if cijfers.startswith("0") or not checked(cijfers):
        return geschreven
    if _NA_CODEWOORD.search(m.string[max(0, m.start() - _VENSTER) : m.start()]):
        return geschreven
    return nl_getal(int(cijfers)) + (m.group("decimalen") or "")


def _in_tekst(tekst: str) -> str:
    """De notatie in een stuk lopende tekst, buiten code, links en HTML."""
    stukken, vorige = [], 0
    for m in _BESCHERMD.finditer(tekst):
        stukken += [_GETAL.sub(_hoeveelheid, tekst[vorige : m.start()]), m.group(0)]
        vorige = m.end()
    return "".join([*stukken, _GETAL.sub(_hoeveelheid, tekst[vorige:])])


def _codekolommen(kop: str) -> set[int]:
    return {i for i, cel in enumerate(kop.split("|")) if _CODEKOP.search(cel)}


def _tabelrij(regel: str, codekolommen: set[int]) -> str:
    return "|".join(cel if i in codekolommen else _in_tekst(cel) for i, cel in enumerate(regel.split("|")))


def nl_notatie(tekst: str) -> str:
    """`tekst` met elk geheel getal van vier of meer cijfers, geen jaar of code, als 3.303."""
    regels = tekst.split("\n")
    uit: list[str] = []
    in_codeblok = False
    codekolommen: set[int] | None = None  # None: niet in een tabel
    for i, regel in enumerate(regels):
        if hek := bool(_CODEBLOK.match(regel)):
            in_codeblok = not in_codeblok
        if in_codeblok or hek:
            uit.append(regel)
            continue
        if "|" not in regel:
            codekolommen = None
        elif i + 1 < len(regels) and _TABELSCHEIDING.match(regels[i + 1]) and "|" in regels[i + 1]:
            codekolommen = _codekolommen(regel)
        uit.append(_tabelrij(regel, codekolommen) if codekolommen is not None else _in_tekst(regel))
    return "\n".join(uit)
