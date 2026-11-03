"""Het wettelijk collegegeld per studiejaar, uit een vaste tabel met de wettekst als bron (#729).

De bedragen staan in artikel 9 van de Regeling financiën hoger onderwijs (BWBR0024005): per studiejaar het volledig
wettelijk collegegeld en het minimum- en maximumbedrag van het gedeeltelijk wettelijk collegegeld. Volgens artikel
7.45a, derde en vierde lid, WHW betaalt een student van een voltijdse opleiding het volledige bedrag en een student van
een deeltijdse of duale opleiding het gedeeltelijke, dat de instelling tussen minimum en maximum vaststelt (artikel
7.45, tweede lid).

De tabel staat hier en niet in de catalogus: het is één artikel dat eens per jaar verandert, en de wettekst is 735 KB
HTML. Het model onthoudt en berekent geen bedrag (#191): het kiest het studiejaar, de code geeft precies één
bedragenpaar met de wetsversie en de dag waarop die is nagelezen. De jaarlijkse controle rond 1 september staat in
docs/promoten.md; `bron:ping` wordt rood zodra het lopende studiejaar niet in de tabel staat.
"""

import json
from dataclasses import dataclass
from datetime import date

from . import periode

BWBR = "BWBR0024005"
REGELING = "Regeling financiën hoger onderwijs"
ARTIKEL = "artikel 9"
BRONNAAM = "wetten.nl"
BRONTITEL = f"{REGELING} ({BWBR}), {ARTIKEL}"


@dataclass(frozen=True)
class Bedragen:
    """Eén studiejaar uit artikel 9, zoals het in de wettekst staat, in hele euro's."""

    startjaar: int
    volledig: int  # voltijd
    gedeeltelijk_min: int  # deeltijd en duaal: de instelling kiest tussen min en max
    gedeeltelijk_max: int
    versie: date  # de versie van de regeling ("geldend van") waarin de bedragen zijn nagelezen
    opgehaald: date  # de dag waarop die versie is opgehaald en nagelezen


# Nagelezen op 03-11-2026 in de versies op wetten.overheid.nl/BWBR0024005/<versie>. Elke versie noemt twee studiejaren;
# per studiejaar staat hier de nieuwste versie die het noemt. 2027/2028 staat in een vastgestelde wijziging die per
# 01-09-2027 geldt. Een studiejaar dat niet in een wettekst terug te vinden is, staat er niet in.
TABEL: tuple[Bedragen, ...] = (
    Bedragen(2023, 2314, 1377, 2314, date(2024, 9, 1), date(2026, 11, 3)),
    Bedragen(2024, 2530, 1506, 2530, date(2025, 9, 1), date(2026, 11, 3)),
    Bedragen(2025, 2601, 1548, 2601, date(2026, 9, 18), date(2026, 11, 3)),
    Bedragen(2026, 2694, 1604, 2694, date(2026, 9, 18), date(2026, 11, 3)),
    Bedragen(2027, 2771, 1650, 2771, date(2027, 9, 1), date(2026, 11, 3)),
)
_PER_JAAR = {b.startjaar: b for b in TABEL}

VOLTIJD = (
    "Volledig wettelijk collegegeld: voor een student van een voltijdse opleiding die wettelijk collegegeld "
    "verschuldigd is (artikel 7.45a, derde lid, WHW)."
)
DEELTIJD = (
    "Gedeeltelijk wettelijk collegegeld: voor een student van een deeltijdse of duale opleiding (artikel 7.45a, vierde "
    "lid, WHW). De instelling stelt het bedrag vast tussen het minimum- en het maximumbedrag (artikel 7.45, tweede lid, "
    "WHW); welk bedrag een instelling kiest, staat niet in deze bron."
)
GEEN_OPEN_BRON = (
    "Het instellingscollegegeld, het bedrag dat een instelling voor deeltijd of duaal kiest en andere collegegelden "
    "die een instelling zelf vaststelt, zijn geen open data: daarvoor is geen open bron. Noem er geen bedrag voor."
)
# Tot en met 2023/2024 kon een eerstejaars verlaagd collegegeld betalen; die regeling verviel per 01-09-2024.
_VERLAAGD = (
    "In {studiejaar} kon een student in het eerste jaar verlaagd wettelijk collegegeld verschuldigd zijn (artikel 2.4b "
    "Uitvoeringsbesluit WHW 2008, vervallen per 01-09-2024). Dat bedrag staat niet in deze tabel: noem het niet."
)
_LAATSTE_VERLAAGD = 2023


def _dag(d: date) -> str:
    return f"{d:%d-%m-%Y}"


def huidig_studiejaar(vandaag: date) -> int:
    """Het startjaar van het studiejaar waarin `vandaag` valt; een studiejaar begint op 1 september."""
    return vandaag.year if vandaag.month >= 9 else vandaag.year - 1


def _startjaar(studiejaar) -> int | None:
    """2026, "2026", "2026/27" of "2026-2027" als startjaar; None als het geen studiejaar is."""
    if isinstance(studiejaar, int) and not isinstance(studiejaar, bool):
        return studiejaar
    tekst = str(studiejaar).strip()
    if tekst.isdigit() and len(tekst) == 4:
        return int(tekst)
    return periode.startjaar_van_spelling(tekst)


def _bron(b: Bedragen) -> dict:
    return {
        "naam": f"{BRONNAAM}, {BRONTITEL}",
        "url": f"https://wetten.overheid.nl/{BWBR}/{b.versie:%Y-%m-%d}#Paragraaf5_Artikel9",
        "versie": _dag(b.versie),
        "opgehaald": _dag(b.opgehaald),
    }


def _noten(b: Bedragen, label: str, vandaag: date) -> list[str]:
    noten = []
    if b.versie > vandaag:
        noten.append(
            f"De bedragen voor {label} staan in een vastgestelde wijziging van de regeling die per {_dag(b.versie)} "
            "geldt: zeg dat erbij."
        )
    if b.startjaar <= _LAATSTE_VERLAAGD:
        noten.append(_VERLAAGD.format(studiejaar=label))
    return noten


def uitkomst(b: Bedragen, vandaag: date) -> dict:
    """Het ene bedragenpaar van een studiejaar, met betekenis, noten en bron."""
    label = periode.studiejaar_label(b.startjaar)
    uit: dict = {
        "studiejaar": label,
        "voltijd": {"bedrag_euro": b.volledig, "betekenis": VOLTIJD},
        "deeltijd_en_duaal": {
            "minimum_euro": b.gedeeltelijk_min,
            "maximum_euro": b.gedeeltelijk_max,
            "betekenis": DEELTIJD,
        },
        "geen_open_bron": GEEN_OPEN_BRON,
        "bron": _bron(b),
    }
    if noten := _noten(b, label, vandaag):
        uit["noot"] = noten
    return uit


def get_collegegeld(studiejaar: int | str | None = None, vandaag: date | None = None) -> str:
    """Het wettelijk collegegeld van één studiejaar (voltijd, en deeltijd en duaal), uit de tabel (#729).

    Zonder studiejaar het lopende studiejaar; `vandaag` alleen voor tests en de bron-ping.
    """
    vandaag = vandaag or date.today()
    lopend = huidig_studiejaar(vandaag)
    startjaar = lopend if studiejaar in (None, "") else _startjaar(studiejaar)
    bekend = (
        f"{periode.studiejaar_label(TABEL[0].startjaar)} tot en met {periode.studiejaar_label(TABEL[-1].startjaar)}"
    )
    if startjaar is None:
        return (
            f"'{studiejaar}' is geen studiejaar. Geef het startjaar, bijv. {lopend} voor "
            f"{periode.studiejaar_label(lopend)}. Noem geen bedrag."
        )
    if (b := _PER_JAAR.get(startjaar)) is None:
        return (
            f"Voor studiejaar {periode.studiejaar_label(startjaar)} staat geen wettelijk collegegeld in de tabel van de "
            f"app (die dekt {bekend}, uit {REGELING}, {BWBR}). Noem geen bedrag en reken er geen uit. "
            f"{GEEN_OPEN_BRON}"
        )
    return json.dumps(uitkomst(b, vandaag), ensure_ascii=False)
