"""Een zelfcorrectie hoort in de redeneerkaart, niet in het eindantwoord (#412).

CH-05: het juiste antwoord over ROC Mondriaan bevatte "Mijn tussenzin 'zes vestigingen'
was onjuist." Die tussenzin stond al in de redeneerkaart; de gebruiker leest het
eindantwoord als het antwoord, niet als een gesprek van het model met zichzelf. De
code haalt zulke zinnen eruit en geeft ze terug voor de kaart: geen extra modelronde,
en de uitkomst hangt niet af van of het model een promptregel volgt.

Alleen de eerste persoon telt: "de aanname ... was onjuist" is een bevinding, "mijn
tussenzin was onjuist" een herziening. Een vervolgzin "Dat was onjuist, want …" hoort bij
de herziening ervóór (#543); op zichzelf blijft zo'n zin staan.
"""

import re

# Tussen "mijn vorige antwoord" en "was onjuist" mag een getal met duizendtallenpunt staan
# (36.206, #543), maar geen zinseinde.
_TUSSEN = r"(?:[^.\n]|(?<=\d)\.(?=\d)){0,120}?"
_ZELFCORRECTIE = re.compile(
    r"\bmijn\s+(?:tussenzin|tussenstap|eerdere?|vorige|zin|opmerking|bewering|uitspraak|telling|antwoord)\b"
    + _TUSSEN
    + r"\b(?:was|is)\s+(?:on(?:juist|correct)|fout|niet\s+(?:juist|correct))\b"
    r"|\bik\s+(?:heb|had)\s+me\s+vergist\b|\bik\s+vergiste\s+me\b"
    r"|\bik\s+corrigeer\b|^\W*correctie\s*(?::|op\s+mijn\b)"
    r"|\bbij\s+nader\s+inzien\b"
    r"|\b(?:eerder|hierboven|zojuist)\s+(?:noemde|schreef|zei|meldde)\s+ik\b"
    r"|\bik\s+(?:noemde|schreef|zei|meldde)\s+(?:eerder|hierboven|zojuist)\b"
    r"|\bmijn\s+excuses\b|\bexcuses\s+voor\b",
    re.IGNORECASE,
)
# "Dat was onjuist, want …" direct na een herziening: de verklaring bij die herziening.
_VERVOLG = re.compile(
    r"^\W*(?:dat|dit)\s+(?:was|is)\s+(?:on(?:juist|correct)|fout|niet\s+(?:juist|correct))\b", re.IGNORECASE
)
# Een zin eindigt bij een leesteken gevolgd door witruimte, niet bij de punt in 475.460.
_ZINSGRENS = re.compile(r"(?<=[.!?])\s+")


def _zelfcorrecties(zinnen: list[str]) -> list[str]:
    """De zelfcorrigerende zinnen van een regel, elk met de vervolgzin die erbij hoort."""
    weg: list[str] = []
    for i, zin in enumerate(zinnen):
        if _ZELFCORRECTIE.search(zin) or (i and zinnen[i - 1] in weg and _VERVOLG.match(zin)):
            weg.append(zin)
    return weg


def zonder_zelfcorrectie(tekst: str) -> tuple[str, list[str]]:
    """De tekst zonder zelfcorrigerende zinnen, en die zinnen zelf; opmaak per regel blijft staan."""
    weg: list[str] = []
    regels: list[str | None] = []  # None: de regel bestond alleen uit zelfcorrectie
    for regel in tekst.split("\n"):
        zinnen = _ZINSGRENS.split(regel)
        hier = _zelfcorrecties(zinnen)
        if not hier:
            regels.append(regel)
            continue
        weg += hier
        regels.append(" ".join(z for z in zinnen if z not in hier).rstrip() or None)
    if not weg:
        return tekst, []
    return _zonder_lege_regels(regels), [z.strip() for z in weg]


def _zonder_lege_regels(regels: list[str | None]) -> str:
    """Een weggehaalde regel neemt een witregel mee, zodat er geen gat van twee ontstaat."""
    uit: list[str] = []
    for i, regel in enumerate(regels):
        if regel is None:
            if uit and not uit[-1].strip() and (i + 1 == len(regels) or not (regels[i + 1] or "").strip()):
                uit.pop()
            continue
        uit.append(regel)
    return "\n".join(uit).strip("\n")
