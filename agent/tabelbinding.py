"""Staat een decimaal in een tabelrij bij het schooljaar, de maat en de instelling van die rij? (#982)

F3 (ROC Midden Nederland) gaf een tabelrij "2022/23 | 70,6%". 70,6% staat in de bron, als diplomaresultaat van
2024/25 en als jaarresultaat van 2022/23, maar het antwoord ging over het diplomaresultaat: in 2022/23 was dat 71,2%.
De getalcontrole (agent/grounding.py) vraagt alleen of een percentage ergens in de tooluitvoer staat, en de
bindingscontrole (agent/binding.py) bindt alleen gehele getallen uit tabellen in de store.

Hier is elke cel met een decimale komma een bewering over één meetwaarde met een schooljaar
(`agent/meetwaarden.Meetwaarde` met `decimaal`). Kandidaten zijn de meetwaarden die de cel schrijft, afgerond op de
decimalen van de cel. De kolomkop en de labelcellen van de rij kiezen eruit, zoals een zin in agent/claimbinding.py:
de kandidaten die er de meeste kenmerken van noemen (de instelling of "roc's", de maat, "Verschil"). Noemen ze een
kenmerk van de bron dat geen kandidaat heeft, dan past geen enkele. Blijven er kandidaten van meer maten over, dan geldt
de maat die de tekst vóór de cel het laatst noemt ("Het diplomaresultaat ... was"). Het schooljaar van de cel komt uit
de cel zelf, de kolomkop of de labelcellen van de rij. Staat geen overgebleven kandidaat bij dat schooljaar, dan is
dat een probleem.

Zacht, geen inhouden: een decimaal botst vaker toevallig met een cel van een ander jaar dan een getal van vier cijfers
(het verschil -0,6 is in 2023/24 dat van het jaar- én van het diplomaresultaat), en de maat kan uit de tekst vóór de
tabel komen. De melding geeft een herkansing en staat onder het antwoord als het blijft.

Grens: alleen tabelrijen, alleen schooljaren (2022/23, 2025-2026; een kaal kalenderjaar niet) en alleen decimalen
van een bron met een eigen resultaatvorm die haar waarden met decimalen en een schooljaar meegeeft: de mbo-indicatoren
en het collegegeld (`_EIGEN_VORM` in agent/meetwaarden.py). De financiën en WOPI noemen een kalenderjaar of peildatum,
de Studiekeuzedatabase een kaal studiejaar (2026): die vallen erbuiten. Een zin bindt deze controle niet:
een vergelijking in de tijd noemt vaak één jaar bij twee waarden (#379). Gehele getallen uit de store bindt
agent/binding.py, in zinnen en tabelrijen.

Heroverwegen: als agent/binding.py ook decimalen en bronnen buiten de store bindt, of als deze controle een kwartaal
lang niet afgaat (logregel CONTROLES).
"""

import re
from collections.abc import Iterable

from tools import periode

from .claimbinding import kenmerken
from .grounding import decimalen_met_positie
from .mdtabel import Tabel, tabellen
from .meetwaarden import Meetwaarde, meetwaarden, schrijft
from .probleem import Probleem

_SCHEIDING = " · "


def _jaren(waarde: Meetwaarde) -> set[int]:
    """De startjaren van de schooljaren in de selectie van een meetwaarde."""
    return {jaar for cel in waarde.selectie for jaar in periode.gevraagde_schooljaren(cel)}


def _kenmerken(waarde: Meetwaarde) -> frozenset[str]:
    """Wat een kop of label over de meetwaarde kan noemen, zonder het schooljaar: dat toetst de controle apart."""
    return frozenset(k for k in kenmerken(waarde) if not periode.gevraagde_schooljaren(k))


def _posities(tekst: str, kenmerk: str) -> list[int]:
    """Waar de tekst het kenmerk als los woord noemt; een typografische apostrof (U+2019) telt als een rechte."""
    patroon = rf"(?<!\w){re.escape(kenmerk)}(?!\w)"
    return [m.start() for m in re.finditer(patroon, tekst.replace("\u2019", "'"), re.IGNORECASE)]


def _laatst_genoemde_maat(kandidaten: list[Meetwaarde], ervoor: str) -> list[Meetwaarde]:
    """Van kandidaten met verschillende maten die van de maat die de tekst ervoor het laatst noemt; anders allemaal."""
    maten = {w.maat for w in kandidaten}
    posities = {maat: treffers[-1] for maat in maten if (treffers := _posities(ervoor, maat))}
    if len(maten) == 1 or not posities:
        return kandidaten
    laatste = max(posities, key=lambda maat: posities[maat])
    return [w for w in kandidaten if w.maat == laatste]


def _passend(kandidaten: list[Meetwaarde], context: str, bekend: frozenset[str], ervoor: str) -> list[Meetwaarde]:
    """De kandidaten die de kop en labels van de cel aanwijzen; leeg als die een kenmerk noemen dat geen kandidaat
    heeft (70,6% van de instelling in de kolom "Alle roc's")."""
    genoemd = {k for k in bekend if _posities(context, k)}
    scores = [len(_kenmerken(w) & genoemd) for w in kandidaten]
    beste = max(scores)
    if genoemd and not beste:
        return []
    return _laatst_genoemde_maat([w for w, score in zip(kandidaten, scores, strict=True) if score == beste], ervoor)


def _beschrijving(waarde: Meetwaarde) -> str:
    return _SCHEIDING.join((waarde.maat, *waarde.selectie))


def _cel_jaren(cel: str, kop: str, labels: Iterable[str]) -> set[int]:
    """Het schooljaar van een cel: uit de cel zelf, anders uit de kolomkop, anders uit de labelcellen van de rij."""
    for bron in (cel, kop, " ".join(labels)):
        if jaren := periode.gevraagde_schooljaren(bron):
            return jaren
    return set()


def _probleem(geschreven: str, jaren: set[int], kop: str, rij: tuple[str, ...], hoort: list[Meetwaarde]) -> Probleem:
    jaar = ", ".join(periode.labels(sorted(jaren)))
    bij = "; ".join(dict.fromkeys(_beschrijving(w) for w in hoort))
    return Probleem(
        f"{geschreven} staat in de tabelrij van {jaar}, kolom '{kop}' ('{' | '.join(rij)}'), maar hoort in de data "
        f"bij {bij}.",
        f"Neem de waarde uit de bron voor {jaar} en deze kolom, of laat de rij weg. Herschrijf het antwoord met alleen "
        "de juiste tabel, niet met een correctie naast de oude.",
    )


def _in_tabel(tabel: Tabel, ervoor: str, waarden: list[Meetwaarde], bekend: frozenset[str]) -> list[Probleem]:
    problemen = []
    maattekst = f"{ervoor}\n{' | '.join(tabel.kop)}"
    for rij in tabel.rijen:
        labels = [cel for cel in rij if not decimalen_met_positie(cel)]
        for k, cel in enumerate(rij):
            kop = tabel.kop[k] if k < len(tabel.kop) else ""
            if not (jaren := _cel_jaren(cel, kop, labels)):
                continue
            for geschreven, waarde, _ in decimalen_met_positie(cel):
                # Zonder kandidaat komt het getal niet uit deze bronnen: daarover beslist de getalcontrole.
                if not (kandidaten := [w for w in waarden if schrijft(w, waarde)]):
                    continue
                passend = _passend(kandidaten, " ".join([kop, *labels]), bekend, maattekst)
                if not any(jaren & _jaren(w) for w in passend):
                    problemen.append(_probleem(geschreven, jaren, kop, rij, passend or kandidaten))
    return problemen


def verkeerde_tabeljaren(lezingen: Iterable[str], tool_results: list[str]) -> list[Probleem]:
    """Decimalen in een tabelrij die in de data bij een ander schooljaar, een andere maat of een andere instelling
    staan dan de rij en de kolom zeggen. `lezingen`: het antwoord zoals de gebruiker het leest, in elke notatie die
    de controle moet toetsen (agent/controles.lezingen)."""
    waarden = [w for result in tool_results for w in meetwaarden(result) if w.decimaal is not None and _jaren(w)]
    if not waarden:
        return []
    bekend = frozenset().union(*(_kenmerken(w) for w in waarden))
    problemen: list[Probleem] = []
    for tekst in lezingen:
        regels = tekst.split("\n")
        for tabel in tabellen(regels):
            problemen += _in_tabel(tabel, "\n".join(regels[: tabel.begin]), waarden, bekend)
    return list(dict.fromkeys(problemen))
