"""Een zelfcorrectie hoort in de redeneerkaart, niet in het eindantwoord (#412).

CH-05: het juiste antwoord over ROC Mondriaan bevatte "Mijn tussenzin 'zes vestigingen'
was onjuist." Die tussenzin stond al in de redeneerkaart; de gebruiker leest het
eindantwoord als het antwoord, niet als een gesprek van het model met zichzelf. De
code haalt zulke zinnen eruit en geeft ze terug voor de kaart: geen extra modelronde,
en de uitkomst hangt niet af van of het model een promptregel volgt.

Alleen de eerste persoon telt: "de aanname ... was onjuist" is een bevinding, "mijn
tussenzin was onjuist" een herziening. Een vervolgzin "Dat was onjuist, want …" hoort bij
de herziening ervóór (#543); op zichzelf blijft zo'n zin staan.

Een zin die een eigen tabel als fout aanwijst, is ook een herziening (#982): "De eerste tabel hierboven is een
vergissing; gebruik de tweede tabel." (F3). Dan gaat ook de tabel die herzien is mee naar de kaart: elke tabel waarna
nog een tabel met dezelfde kolommen volgt. Zo staat in het antwoord alleen de laatste. Is zo'n tabel niet te vinden,
dan meldt `onvervangen_tabelcorrectie` dat aan de antwoordcontrole en schrijft het model het antwoord opnieuw.
"""

import re

from .mdtabel import Tabel, tabellen
from .probleem import Probleem

# Tussen "mijn vorige antwoord" en "was onjuist" mag een getal met duizendtallenpunt staan
# (36.206, #543), maar geen zinseinde.
_TUSSEN = r"(?:[^.\n]|(?<=\d)\.(?=\d)){0,120}?"
# Een tabel van het antwoord zelf: "de eerste tabel", "de tabel hierboven" (#982).
_EIGEN_TABEL = r"(?:(?:eerste|vorige|eerdere|bovenstaande|bovenste)\s+tabel|tabel\s+hierboven)"
_TABELCORRECTIE = (
    rf"\b{_EIGEN_TABEL}\b{_TUSSEN}\b(?:(?:is|was)\s+(?:een\s+)?(?:vergissing|fout(?:ief)?|on(?:juist|correct)"
    r"|niet\s+(?:juist|correct))|klopte?\s+niet)\b"
    rf"|\b(?:negeer|vergeet)\s+(?:de\s+)?{_EIGEN_TABEL}\b"
    r"|\bgebruik\s+(?:alleen\s+)?de\s+(?:tweede|laatste)\s+tabel\b"
)
_ZELFCORRECTIE = re.compile(
    r"\bmijn\s+(?:tussenzin|tussenstap|eerdere?|eerste|vorige|zin|opmerking|bewering|uitspraak|telling|antwoord|tabel)\b"
    + _TUSSEN
    + r"\b(?:was|is)\s+(?:on(?:juist|correct)|fout|niet\s+(?:juist|correct))\b"
    rf"|{_TABELCORRECTIE}"
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


# Een herziening die over een tabel gaat: dan is er ook een herziene tabel (#982).
_OVER_TABEL = re.compile(r"\btabel\b", re.IGNORECASE)


def _herzien(tekst: str) -> tuple[list[str | None], list[str]]:
    """De regels zonder zelfcorrigerende zinnen (None: de regel bestond er alleen uit), en die zinnen zelf."""
    weg: list[str] = []
    regels: list[str | None] = []
    for regel in tekst.split("\n"):
        zinnen = _ZINSGRENS.split(regel)
        hier = _zelfcorrecties(zinnen)
        if not hier:
            regels.append(regel)
            continue
        weg += hier
        regels.append(" ".join(z for z in zinnen if z not in hier).rstrip() or None)
    return regels, weg


def _kolommen(tabel: Tabel) -> tuple[str, ...]:
    return tuple(" ".join(cel.lower().split()) for cel in tabel.kop)


def _vervangen(regels: list[str]) -> list[Tabel]:
    """De tabellen waarna nog een tabel met dezelfde kolommen volgt: die zijn herzien."""
    gevonden = tabellen(regels)
    return [t for i, t in enumerate(gevonden) if any(_kolommen(t) == _kolommen(later) for later in gevonden[i + 1 :])]


def zonder_zelfcorrectie(tekst: str) -> tuple[str, list[str]]:
    """De tekst zonder zelfcorrigerende zinnen en zonder de tabellen die ze herzien, en wat eruit ging; opmaak per
    regel blijft staan. Een herziene tabel staat vóór de zinnen, zoals in de tekst."""
    regels, weg = _herzien(tekst)
    if not weg:
        return tekst, []
    herziene_tabellen: list[str] = []
    if any(_OVER_TABEL.search(zin) for zin in weg):
        for tabel in _vervangen([regel or "" for regel in regels]):
            herziene_tabellen.append("\n".join(str(r) for r in regels[tabel.begin : tabel.einde + 1]))
            regels[tabel.begin : tabel.einde + 1] = [None] * (tabel.einde + 1 - tabel.begin)
    return _zonder_lege_regels(regels), herziene_tabellen + [z.strip() for z in weg]


def onvervangen_tabelcorrectie(tekst: str) -> list[Probleem]:
    """Een zin die een eigen tabel als fout aanwijst, zonder dat er een vervangende tabel volgt (#982).

    Dan weet code niet welke tabel weg moet; de herkansing laat het model het antwoord opnieuw opbouwen."""
    regels, weg = _herzien(tekst)
    correcties = [zin.strip() for zin in weg if _OVER_TABEL.search(zin)]
    if not correcties or _vervangen([regel or "" for regel in regels]):
        return []
    return [
        Probleem(
            f"Het antwoord zegt zelf dat een tabel niet klopt ('{correcties[0]}'), maar geeft geen tabel in haar plaats.",
            "Schrijf het antwoord opnieuw op met alleen de juiste tabel: zonder de foute tabel en zonder de correctie.",
        )
    ]


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
