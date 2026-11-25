"""Waarom wijkt dit af van ons eigen cijfer? Een eigen getal naast het hoofdgetal, met de bekende redenen en hun grootte
uit code (#1258).

Gebruikers leggen een cijfer naast hun eigen administratie (1CijferHO, jaarverslag) of de cijfers van een koepel en zien
een verschil. In het rapport noemt het definitieblok de mogelijke redenen (`report_vergelijken`, #736); in de chat staat
onder een antwoord met precies één hoofdgetal (uit een vaste maat of een enkele selectie) de knop "Wijkt af van je eigen
cijfer?". De gebruiker typt alleen een getal. Code zet het naast ons getal (verschil absoluut en in %) en loopt de
redenen af die de teldefinitie van de geladen key draagt; per reden de grootte als code die kan uitrekenen (extranei,
personen of inschrijvingen, opleidingsvorm uit de andere definities van #1256; onderdrukte cellen en afronding als
bovengrens), anders "kan meespelen, grootte niet te bepalen uit open data". De slotzin zegt of het verschil binnen de
bekende redenen valt, of hoeveel er overblijft.

Het eigen getal is invoer van de gebruiker, nooit bewijs: het staat in de stap en het bewijs als `eigen_getal`, met
`invoer: gebruiker` en zonder citatie; het rapport en de getalcontrole van een volgend antwoord tellen het niet
(`session_data.rekenbewijs`, `beurtbewijs.eerdere_antwoorden`). Het model schrijft hier niets; de uitkomst zegt nooit
dat een getal fout is.
"""

import json
import re
from dataclasses import dataclass

from tools import store
from tools.duo import OPLEIDINGSVORM_DATASETS, onderdrukt
from tools.schemas import TOOL_GET_MAAT, TOOL_QUERY_DATA

from . import controlestappen
from .meetwaarden import meetwaarden
from .onder_antwoord import KOP_VERSCHILVERKLARING
from .selectie import laadkey
from .session_data import INVOER_GEBRUIKER, voeg_controlebewijs_toe

KOP = KOP_VERSCHILVERKLARING
STAP = "verschilverklaring"
LABEL = "Verschil met je eigen cijfer uitgelegd"
MAX_CIJFERS = 12
GEEN_GETAL = "Geef alleen een heel getal, zonder tekst of decimalen: bijvoorbeeld 475.460."
TE_LANG = f"Dat getal is te lang: geef hoogstens {MAX_CIJFERS} cijfers."
GROEPERING = (
    "Een punt of spatie staat alleen tussen groepen van drie cijfers, zoals in 475.460. "
    "Geef een heel getal, zonder decimalen."
)
GEEN_HOOFDGETAL = (
    "Bij dit antwoord kan ik je getal niet (meer) naast het onze leggen: stel de vraag opnieuw en probeer het dan."
)
ONBEKEND = "kan meespelen, grootte niet te bepalen uit open data"
_MAX_HOOFDGETALLEN = 20
_SESSIE = "hoofdgetallen"
_INVOER_MAX_TEKENS = 40
# Scheiding van duizendtallen: een spatie, ook de harde spaties die een spreadsheet kopieert, of een punt.
_SPATIES = " \u00a0\u202f"
_TEKENS = re.compile(f"[0-9.{_SPATIES}]+")
_HEEL = re.compile(r"[0-9]+")
_GEGROEPEERD = re.compile(f"[0-9]{{1,3}}(?:\\.[0-9]{{3}})+|[0-9]{{1,3}}(?:[{_SPATIES}][0-9]{{3}})+")


def invoer(waarde) -> int | str:
    """Het getal dat de gebruiker typte, of de melding waarom het geen getal is. Een punt of spatie mag alleen als
    scheiding van duizendtallen, tussen groepen van drie cijfers (475.460, 475 460, 1.234.567), zoals in het
    Nederlands; 1.5 of 475.46 is een decimaal getal en geen telling, en wordt geweigerd in plaats van 15 of 47546.
    Een komma, een teken, tekst of meer dan 12 cijfers ook. frontend/src/eigenGetal.js toetst hetzelfde."""
    if isinstance(waarde, bool) or not isinstance(waarde, str | int):
        return GEEN_GETAL
    tekst = str(waarde).strip()
    if not tekst or not _TEKENS.fullmatch(tekst):
        return GEEN_GETAL
    kaal = re.sub(f"[.{_SPATIES}]", "", tekst)
    if not kaal:
        return GEEN_GETAL
    if len(kaal) > MAX_CIJFERS or len(tekst) > _INVOER_MAX_TEKENS:
        return TE_LANG
    if not (_HEEL.fullmatch(tekst) or _GEGROEPEERD.fullmatch(tekst)):
        return GROEPERING
    return int(kaal)


def _json(tekst: str) -> dict:
    try:
        parsed = json.loads(tekst)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _getal(waarde) -> float | None:
    return float(waarde) if isinstance(waarde, int | float) and not isinstance(waarde, bool) else None


def _uit_maat(parsed: dict) -> dict | None:
    """Een get_maat-resultaat met precies één rij met een waarde: het hoofdgetal met zijn teldefinitie."""
    ruw = parsed.get("rijen")
    rijen = [r for r in ruw if isinstance(r, dict)] if isinstance(ruw, list) else []
    kolom = parsed.get("waardekolom")
    if len(rijen) != 1 or not isinstance(kolom, str) or (waarde := _getal(rijen[0].get(kolom))) is None:
        return None
    if not isinstance(key := parsed.get("data_key"), str):
        return None
    return {
        "waarde": waarde,
        "data_key": key,
        "teldefinitie": str(parsed.get("teldefinitie") or ""),
        "maat": parsed.get("maat"),
        "vorm": parsed.get("vorm"),
        "extranei": _getal(rijen[0].get("EX")),  # de examendeelnemers van een mbo-maat per instelling
    }


def _uit_selectie(result: str, tool: str) -> dict | None:
    """Een selectie met precies één meetwaarde (één rij, één telkolom): het hoofdgetal."""
    parsed = _json(result)
    rijen = parsed.get("rijen")
    if not isinstance(rijen, list) or len(rijen) != 1 or not isinstance(rij := rijen[0], dict):
        return None
    waarden = meetwaarden(result, tool)
    if len(waarden) != 1 or not isinstance(key := parsed.get("data_key"), str):
        return None
    return {
        "waarde": _getal(rij.get(waarden[0].maat)),
        "data_key": key,
        "teldefinitie": "",
        "extranei": _getal(rij.get("EX")) if waarden[0].maat != "EX" else None,
    }


def hoofdgetal(steps: list[tuple[str, str]]) -> dict | None:
    """Het ene hoofdgetal van een beurt: uit een vaste maat met één rij, of een enkele selectie met één waarde. None
    als de beurt geen of meer dan één getal geeft (hetzelfde getal uit maat en selectie telt één keer)."""
    kandidaten = []
    for tool, result in steps:
        if tool == TOOL_GET_MAAT:
            gevonden = _uit_maat(_json(result))
        elif tool == TOOL_QUERY_DATA:
            gevonden = _uit_selectie(result, tool)
        else:
            gevonden = None
        if gevonden and gevonden["waarde"] is not None:
            kandidaten.append(gevonden)
    if len({k["waarde"] for k in kandidaten}) != 1:
        return None
    return kandidaten[0]


def _alternatieven(controles: controlestappen.Controles, key: str) -> dict[str, float]:
    """De andere definities van het hoofdgetal die code al uitrekende (#1256), op naam."""
    return {u.naam: u.waarde for d in controles.definities if d.hoofd.data_key == key for u in d.uitkomsten}


def onthoud(session: dict, steps: list[tuple[str, str]], controles: controlestappen.Controles) -> dict | None:
    """Zet het hoofdgetal van deze beurt in de sessie, voor de knop eronder; {id, waarde} voor de client, of None."""
    gevonden = hoofdgetal(steps)
    if gevonden is None:
        return None
    key = gevonden["data_key"]
    known = store.meta(laadkey(key)) or store.meta(key)
    gevonden |= {
        "alternatieven": _alternatieven(controles, key),
        "teldefinitie_bron": (known.teldefinitie if known else None) or "",
        "dataset": known.dataset if known else None,
        "bron": known.bron if known else None,
        "afronding": known.afronding if known else None,
        "onderdrukt": sum(onderdrukt(key).values()),
    }
    bewaard = session.setdefault(_SESSIE, {})
    bewaard.pop(key, None)
    bewaard[key] = gevonden
    while len(bewaard) > _MAX_HOOFDGETALLEN:
        bewaard.pop(next(iter(bewaard)))
    return {"id": key, "waarde": gevonden["waarde"]}


@dataclass(frozen=True)
class Reden:
    tekst: str
    grootte: float | None  # wat de reden ongeveer verklaart, of ten hoogste (`bovengrens`); None: niet te bepalen
    bovengrens: bool = False

    def regel(self) -> str:
        if self.grootte is None:
            return f"{self.tekst}: {ONBEKEND}."
        woord = "verklaart ten hoogste" if self.bovengrens else "verklaart ongeveer"
        return f"{self.tekst}: {woord} {controlestappen.nl_getal(self.grootte)}."


def _verschil_met(alternatieven: dict[str, float], namen: tuple[str, ...], ons: float) -> float | None:
    for naam in namen:
        if naam in alternatieven:
            return abs(alternatieven[naam] - ons)
    return None


def redenen(info: dict) -> list[Reden]:
    """De bekende redenen die de teldefinitie van de geladen key draagt, met hun grootte waar code die kent."""
    recept, bron = str(info.get("teldefinitie") or "").lower(), str(info.get("teldefinitie_bron") or "").lower()
    tel = f"{recept} {bron}"
    alternatieven, ons = info.get("alternatieven") or {}, float(info["waarde"])
    uit: list[Reden] = []
    if "extranei" in tel or "examendeelnemers" in tel:
        zonder = "excl. extranei" in tel or "zonder examendeelnemers" in tel
        grootte = info.get("extranei")
        if grootte is None:
            grootte = _verschil_met(alternatieven, ("zonder extranei", "met extranei"), ons)
        mee = "niet mee" if zonder else "mee"
        uit.append(Reden(f"Extranei (examendeelnemers): ons getal telt ze {mee}", grootte))
    # De teldefinitie van het recept begint met wat ze telt; zonder recept die van DUO, zoals report_vergelijken (#736).
    if recept.startswith(("personen", "eerstejaars personen")) or (not recept and "natuurlijke personen" in bron):
        grootte = _verschil_met(alternatieven, ("inschrijvingen",), ons)
        uit.append(
            Reden("Personen of inschrijvingen: ons getal telt personen, wie inschrijvingen telt komt hoger", grootte)
        )
    elif recept.startswith("inschrijvingen") or (not recept and "neveninschrijvingen meegeteld" in bron):
        grootte = _verschil_met(alternatieven, ("personen",), ons)
        uit.append(
            Reden("Personen of inschrijvingen: ons getal telt inschrijvingen, wie personen telt komt lager", grootte)
        )
    alle_vormen = info.get("vorm") in (None, "alle")
    if "alleen voltijd" in alternatieven or (info.get("dataset") in OPLEIDINGSVORM_DATASETS and alle_vormen):
        grootte = _verschil_met(alternatieven, ("alleen voltijd",), ons)
        uit.append(Reden("Opleidingsvorm: ons getal telt voltijd, deeltijd en duaal samen", grootte))
    if info.get("bron") == "duo" and (cellen := int(info.get("onderdrukt") or 0)):
        uit.append(
            Reden(
                f"Onderdrukte cellen: {cellen} cellen met 1 tot en met 4 tellen in ons getal niet mee", 4 * cellen, True
            )
        )
    if afronding := info.get("afronding"):
        uit.append(Reden(f"Afronding: CBS rondt af op {afronding}-tallen", afronding / 2, True))
    if "1 oktober" in tel:
        uit.append(
            Reden("Peildatum: ons getal telt op 1 oktober, een telling op een andere datum komt anders uit", None)
        )
    return uit


def verklaar(eigen: int, info: dict) -> dict:
    """De uitkomst bij een eigen getal: het verschil, de redenen met hun grootte en de slotzin, als tekst en als stap."""
    ons = float(info["waarde"])
    verschil = eigen - ons
    pct = round(verschil / ons * 100, 1) if ons else None
    gevonden = redenen(info)
    verklaard = sum(r.grootte for r in gevonden if r.grootte is not None)
    rest = max(abs(verschil) - verklaard, 0)
    nl = controlestappen.nl_getal
    if verschil == 0:
        vergelijking = f"is gelijk aan ons getal {nl(ons)}"
        slot = "Er is geen verschil om te verklaren."
    else:
        richting = "hoger" if verschil > 0 else "lager"
        procent = f" ({controlestappen.nl_pct(pct)})" if pct is not None else ""
        vergelijking = f"ligt {nl(abs(verschil))} {richting} dan ons getal {nl(ons)}{procent}"
        slot = (
            "Het verschil valt binnen de bekende redenen."
            if rest == 0 and gevonden
            else f"Na deze redenen blijft een verschil van {nl(rest)} over."
        )
    kop = f"{KOP} je eigen getal {nl(eigen)} (jouw invoer, geen bron) {vergelijking}."
    if gevonden:
        midden = "Wat zo'n verschil kan verklaren, volgens de teldefinitie van ons getal:\n" + "\n".join(
            f"- {r.regel()}" for r in gevonden
        )
    else:
        midden = "De teldefinitie van ons getal noemt geen bekende reden voor een verschil."
    tekst = f"{kop}\n\n{midden}\n\n{slot}" if verschil else f"{kop}\n\n{slot}"
    return {
        "eigen_getal": {"waarde": eigen, "invoer": INVOER_GEBRUIKER, "citatie": None},
        "ons_getal": {"waarde": ons, "data_key": info["data_key"]},
        "verschil": verschil,
        "verschil_pct": pct,
        "redenen": [{"tekst": r.tekst, "grootte": r.grootte, "bovengrens": r.bovengrens} for r in gevonden],
        "rest": rest,
        "slot": slot,
        "tekst": tekst,
    }


def behandel(session: dict, id_, getal) -> dict | str:
    """De verschilverklaring bij het hoofdgetal `id_` van deze sessie, of de melding voor de gebruiker. Legt de stap
    vast in het bewijs, met het eigen getal als invoer van de gebruiker."""
    eigen = invoer(getal)
    if isinstance(eigen, str):
        return eigen
    info = (session.get(_SESSIE) or {}).get(id_) if isinstance(id_, str) else None
    if info is None:
        return GEEN_HOOFDGETAL
    uitkomst = verklaar(eigen, info)
    resultaat = {k: v for k, v in uitkomst.items() if k != "tekst"} | {"data_key": info["data_key"]}
    stap = json.dumps(resultaat, ensure_ascii=False, default=str)
    voeg_controlebewijs_toe(
        session,
        [
            {
                "tool": STAP,
                "argumenten": {"data_key": info["data_key"], "eigen_getal": uitkomst["eigen_getal"]},
                "resultaat": stap,
            }
        ],
    )
    return {**uitkomst, "stap": {"name": STAP, "label": LABEL, "input": {"eigen_getal": eigen}, "output": stap}}
