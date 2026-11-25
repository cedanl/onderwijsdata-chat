"""Klopt de richting die de vraag aanneemt? (#1255)

"Waarom is het aantal studenten gedaald?" neemt een daling aan. Steeg de reeks in werkelijkheid, dan zocht het model
eerder een oorzaak voor een daling die er niet was. Code toetst de aangenomen richting tegen de reeks die de beurt
ophaalde: `premisse(vraag, reeks)` geeft `tegengesproken`, `bevestigd` of `niet_te_toetsen`. Bij `tegengesproken` opent
het antwoord met een vaste zin uit code ("De vraag gaat uit van een daling, maar <maat> steeg van <a> naar <b> (<jaar>
→ <jaar>)."); beide getallen komen uit de reeks, dus de getalcontrole en de binding dekken ze. Het model hoort vooraf
in een beurtinstructie dat de app de richting toetst (zoals bij `verklaringsverzoek`). Geen extra modelstap.

Bij twijfel geen zin: een vraag zonder richting, met beide richtingen, een ja/nee-vraag ("Is het gedaald?"), een
ontkenning, een relatieve maat (aandeel, percentage, verhouding), een periode die de reeks niet heeft, een verschil 0
of meer dan één reeks in de beurt. Een subgroep die de vraag noemt maar de reeks niet, ziet de toets niet: de reeks
is wat de tools ophaalden.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from tools import periode, store
from tools.getal import nl_getal

from .beweringtelling import _OMHOOG, _OMLAAG

TEGENGESPROKEN = "tegengesproken"
BEVESTIGD = "bevestigd"
NIET_TE_TOETSEN = "niet_te_toetsen"
Uitkomst = Literal["tegengesproken", "bevestigd", "niet_te_toetsen"]

Richting = Literal["daling", "stijging"]

# De werkwoorden van de tellingcontrole (_OMLAAG, _OMHOOG) plus de vormen en zelfstandige naamwoorden van een vraag.
_DALEN = (
    *_OMLAAG,
    "dalen",
    "daalt",
    "daling",
    "dalende",
    "afname",
    "afnemen",
    "afnemende",
    "neemt af",
    "nemen af",
    "krimp",
    "krimpt",
    "krimpen",
    "teruggelopen",
    "terugloop",
    "loopt terug",
    "liep terug",
    "lopen terug",
    "achteruitgang",
    "achteruitgegaan",
    "minder geworden",
)
_STIJGEN = (
    *_OMHOOG,
    "stijgen",
    "stijgt",
    "stijging",
    "stijgende",
    "toename",
    "toenemen",
    "toenemende",
    "neemt toe",
    "nemen toe",
    "groei",
    "groeit",
    "groeien",
    "opgelopen",
    "loopt op",
    "liep op",
    "meer geworden",
)


def _woorden(woorden: Iterable[str]) -> re.Pattern[str]:
    vormen = "|".join(sorted((w.replace(" ", r"\s+") for w in woorden), key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?P<ontkend>(?:niet|geen)\s+)?(?:{vormen})(?![\w-])", re.IGNORECASE)


_DALING = _woorden(_DALEN)
_STIJGING = _woorden(_STIJGEN)
# Een relatieve maat: een daling van een aandeel zegt niets over het aantal, en omgekeerd.
_RELATIEF = re.compile(
    r"\b(?:aandeel|aandelen|percentage|procent|verhouding|ratio|relatief|per\s+\d+)\b|%", re.IGNORECASE
)
# Een ja/nee-vraag begint met een werkwoord: "Is het aantal gedaald?" neemt niets aan.
_JA_NEE = re.compile(
    r"^\s*(?:is|zijn|was|waren|wordt|worden|heeft|hebben|had|hadden|daalt|dalen|daalde|stijgt|stijgen|steeg|"
    r"groeit|groeide|krimpt|kromp|neemt|nam|loopt|liep|klopt|kloppen)\b",
    re.IGNORECASE,
)
_KAAL_JAAR = re.compile(r"(?<![\d/'’])((?:19|20)\d{2})(?![\d/])")
_SINDS = re.compile(
    r"\b(?:sinds|vanaf|na)\s+(?:het\s+)?(?:studiejaar\s+|schooljaar\s+|jaar\s+)?((?:19|20)\d{2})", re.IGNORECASE
)
_LAATSTE = re.compile(r"\b(?:de\s+)?(?:laatste|afgelopen)\s+(\d{1,2})\s+jaar\b", re.IGNORECASE)


@dataclass(frozen=True)
class Punt:
    jaar: int  # startjaar van de periode
    label: str  # hoe de zin de periode noemt
    waarde: float


@dataclass(frozen=True)
class Reeks:
    maat: str  # hoe de zin de maat noemt: "het aantal ingeschrevenen"
    punten: tuple[Punt, ...]


def aangenomen_richting(vraag: str) -> Richting | None:
    """De richting die de vraag aanneemt, of None als ze geen (eenduidige) richting aanneemt."""
    if not vraag or _JA_NEE.match(vraag) or _RELATIEF.search(vraag):
        return None
    dalen = list(_DALING.finditer(vraag))
    stijgen = list(_STIJGING.finditer(vraag))
    if any(m["ontkend"] for m in (*dalen, *stijgen)) or bool(dalen) == bool(stijgen):
        return None
    return "daling" if dalen else "stijging"


def _jaar(periode_: Any) -> int | None:
    if isinstance(periode_, bool):
        return None
    if isinstance(periode_, int):
        return periode_
    if isinstance(periode_, float) and periode_.is_integer():
        return int(periode_)
    tekst = str(periode_).strip()
    if (start := periode.startjaar_van_spelling(tekst)) is not None:
        return start
    match = re.match(r"((?:19|20)\d{2})(?:JJ\d{2})?$", tekst)
    return int(match.group(1)) if match else None


def _label(periode_: Any, jaar: int) -> str:
    """2021 en 2021SJ00 worden 2021/22; een kalenderjaar (2021JJ00) blijft 2021."""
    tekst = str(periode_).strip()
    return str(jaar) if re.fullmatch(r"\d{4}JJ\d{2}", tekst) else periode.label(jaar)


def _getal(waarde: Any) -> float | None:
    if isinstance(waarde, bool):
        return None
    try:
        getal = float(waarde)
    except (TypeError, ValueError):
        return None
    return getal if math.isfinite(getal) else None


def _punten(reeks: Reeks | Mapping | Iterable) -> list[Punt]:
    """De punten van een reeks, op jaar: een Reeks, een mapping periode → waarde of paren (periode, waarde)."""
    if isinstance(reeks, Reeks):
        return sorted(reeks.punten, key=lambda p: p.jaar)
    paren = reeks.items() if isinstance(reeks, Mapping) else reeks
    punten: dict[int, Punt] = {}
    for periode_, waarde in paren:
        if (jaar := _jaar(periode_)) is None or (getal := _getal(waarde)) is None:
            continue
        if jaar in punten and punten[jaar].waarde != getal:
            return []  # twee waarden voor één jaar: geen reeks
        punten[jaar] = Punt(jaar, _label(periode_, jaar), getal)
    return sorted(punten.values(), key=lambda p: p.jaar)


def _vergeleken(vraag: str, punten: list[Punt]) -> tuple[Punt, Punt] | None:
    """Het begin- en eindpunt dat de vraag bedoelt; None als de reeks die periode niet heeft."""
    if len(punten) < 2:
        return None
    per_jaar = {p.jaar: p for p in punten}
    genoemd = periode.gevraagde_schooljaren(vraag) | periode.jaarbereiken(vraag)
    zonder_schooljaren = re.sub(r"(?<!\d)(?:19|20)\d{2}\s*[/\-–]\s*['’]?\d{2,4}(?!\d)", " ", vraag)
    genoemd |= {int(j) for j in _KAAL_JAAR.findall(zonder_schooljaren)}
    if len(genoemd) >= 2:
        van, tot = per_jaar.get(min(genoemd)), per_jaar.get(max(genoemd))
    elif len(genoemd) == 1:
        sinds = _SINDS.search(vraag)
        if not sinds or int(sinds.group(1)) not in genoemd:
            return None  # één jaar zonder "sinds": vergeleken met welk jaar?
        van, tot = per_jaar.get(int(sinds.group(1))), punten[-1]
    elif laatste := _LAATSTE.search(vraag):
        n = int(laatste.group(1))
        if n < 1:
            return None
        van, tot = punten[max(0, len(punten) - 1 - n)], punten[-1]
    else:
        van, tot = punten[0], punten[-1]
    if van is None or tot is None or van.jaar >= tot.jaar:
        return None
    return van, tot


def premisse(vraag: str, reeks: Reeks | Mapping | Iterable) -> Uitkomst:
    """Spreekt de reeks de richting tegen die de vraag aanneemt? Verschil 0 is noch dalen noch stijgen."""
    if (richting := aangenomen_richting(vraag)) is None:
        return NIET_TE_TOETSEN
    if (paar := _vergeleken(vraag, _punten(reeks))) is None:
        return NIET_TE_TOETSEN
    van, tot = paar
    if tot.waarde == van.waarde:
        return NIET_TE_TOETSEN
    gedaald = tot.waarde < van.waarde
    return BEVESTIGD if gedaald == (richting == "daling") else TEGENGESPROKEN


def _opmaak(waarde: float) -> str:
    """Zoals de bron het getal geeft, in Nederlandse notatie: 27135 → 27.135, 70.55 → 70,55."""
    getal = float(waarde)
    if getal.is_integer():
        return nl_getal(getal, 0)
    return nl_getal(getal, min(3, len(repr(getal).split(".")[1])))


def premissezin(vraag: str, reeks: Reeks) -> str | None:
    """De vaste zin boven het antwoord als de reeks de aangenomen richting tegenspreekt; anders None."""
    if premisse(vraag, reeks) != TEGENGESPROKEN:
        return None
    van, tot = _vergeleken(vraag, _punten(reeks)) or (None, None)
    if van is None or tot is None:
        return None
    aangenomen = aangenomen_richting(vraag)
    werkwoord = "steeg" if tot.waarde > van.waarde else "daalde"
    return (
        f"De vraag gaat uit van een {aangenomen}, maar {reeks.maat} {werkwoord} van {_opmaak(van.waarde)} naar "
        f"{_opmaak(tot.waarde)} ({van.label} → {tot.label})."
    )


_INSTRUCTIE = (
    "**Richting in de vraag.** De vraag gaat uit van een {richting}. De app toetst die richting in code aan de reeks "
    "die je ophaalt, en spreekt de data haar tegen, dan opent het antwoord met een vaste zin van de app daarover. Neem "
    "de richting dus niet over: beschrijf de richting die de data laat zien, en geef geen oorzaak van een {richting} "
    "die de data niet laat zien."
)


def premisse_instructie(vraag: str) -> str:
    """De beurtinstructie als de vraag een richting aanneemt; anders leeg."""
    richting = aangenomen_richting(vraag)
    return _INSTRUCTIE.format(richting=richting) if richting else ""


# --- de reeks van de beurt, uit de toolstappen ---


def _maatnaam(kolom: str, titels: Mapping[str, str] | None = None) -> str:
    """AANTAL_INGESCHREVENEN → het aantal ingeschrevenen; anders de titel van de bron of de kolom tussen aanhalingstekens."""
    naam = (titels or {}).get(kolom) or kolom
    woorden = re.sub(r"[_\s]+", " ", str(naam)).strip()
    if woorden.lower().startswith("aantal "):
        return f"het aantal {woorden[7:].lower()}"
    return f"de waarde '{woorden}'"


def _uit_maat(uit: dict) -> Reeks | None:
    """De reeks van get_maat: één rij per periode, met periodekolom en waardekolom."""
    periodekolom, waardekolom, rijen = uit.get("periodekolom"), uit.get("waardekolom"), uit.get("rijen")
    if not (isinstance(periodekolom, str) and isinstance(waardekolom, str) and isinstance(rijen, list)):
        return None
    paren = [(r.get(periodekolom), r.get(waardekolom)) for r in rijen if isinstance(r, dict)]
    if len({p for p, _ in paren}) != len(paren):
        return None
    punten = _punten(paren)
    return Reeks(_maatnaam(waardekolom), tuple(punten)) if len(punten) >= 2 else None


def _uit_rijen(uit: dict) -> Reeks | None:
    """Een tabel van query_data of run_analysis met één rij per periode en precies één meetkolom die verandert."""
    key, rijen = uit.get("data_key"), uit.get("rijen")
    known = store.meta(key) if isinstance(key, str) else None
    if known is None or not known.periodekolom or not isinstance(rijen, list) or len(rijen) < 2:
        return None
    if not all(isinstance(r, dict) and known.periodekolom in r for r in rijen):
        return None
    periodes = [r[known.periodekolom] for r in rijen]
    if len(set(map(str, periodes))) != len(periodes):
        return None
    kolommen = [
        k
        for k in rijen[0]
        if k != known.periodekolom and k not in periode.JAARKOLOMMEN and not str(k).lower().endswith("label")
    ]
    getallen = [k for k in kolommen if all(_getal(r.get(k)) is not None for r in rijen)]
    varieert = [k for k in getallen if len({_getal(r.get(k)) for r in rijen}) > 1]
    meet = varieert if len(varieert) == 1 else getallen if len(getallen) == 1 else []
    # Een tekstkolom die per rij verschilt (een instelling, een geslacht): dan zijn het meer reeksen door elkaar.
    if len(meet) != 1 or any(len({str(r.get(k)) for r in rijen}) > 1 for k in kolommen if k not in getallen):
        return None
    punten = _punten((r[known.periodekolom], r[meet[0]]) for r in rijen)
    return Reeks(_maatnaam(meet[0], known.kolomtitels), tuple(punten)) if len(punten) >= 2 else None


def reeks_uit_stappen(steps: list[tuple[str, str]]) -> Reeks | None:
    """De ene reeks waarop de beurt rust; None zonder reeks, of bij twee reeksen die elkaar in een jaar tegenspreken."""
    gevonden: list[Reeks] = []
    for tool, result in steps:
        try:
            uit = json.loads(result)
        except (TypeError, ValueError):
            continue
        if not isinstance(uit, dict):
            continue
        reeks = _uit_maat(uit) if tool == "get_maat" else _uit_rijen(uit)
        if reeks is not None:
            gevonden.append(reeks)
    if not gevonden:
        return None
    samen: dict[int, Punt] = {}
    for reeks in gevonden:
        for punt in reeks.punten:
            if punt.jaar in samen and samen[punt.jaar].waarde != punt.waarde:
                return None
            samen.setdefault(punt.jaar, punt)
    if len({r.maat for r in gevonden}) != 1:
        return None
    return Reeks(gevonden[0].maat, tuple(sorted(samen.values(), key=lambda p: p.jaar)))


def met_premissezin(tekst: str, vraag: str, steps: list[tuple[str, str]]) -> str:
    """Het antwoord met de vaste zin bovenaan als de reeks van de beurt de aangenomen richting tegenspreekt."""
    if aangenomen_richting(vraag) is None or (reeks := reeks_uit_stappen(steps)) is None:
        return tekst
    zin = premissezin(vraag, reeks)
    return f"{zin}\n\n{tekst}" if zin else tekst
