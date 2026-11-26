"""Wat code onder een antwoord zet na de vaste maat: andere definities, de kruiscontrole en de vergelijkingsgroep.

Eén plek voor de regels onder het antwoord die op de recepten van `get_maat` rekenen (#1271):

- **Andere definities** (#1256): per vaste maat de gangbare andere keuzes (`tools/andere_definities.py`), elk een
  get_maat-aanroep op dezelfde afbakening die code zet, niet het model. Wijkt er een meer af dan de drempel (1%), dan
  noemt de regel de getallen; anders de vaste zin "andere definities geven hetzelfde beeld", zonder getallen.
- **Ter controle** (#1259): een maat uit de gecureerde koppeltabel (`data/bronparen.toml`) krijgt het getal van de
  andere bron op hetzelfde niveau, het verschil (absoluut en in %) en de bekende redenen uit de tabel. Boven de drempel
  van het paar zonder reden: "verschil, reden niet vastgesteld". Nooit "fout".
- **Vergelijkingsgroep** (#1267): de zin uit code bij de groep van het dashboard, of dat het een eigen groep is.

De stappen lopen na de modelronde, met dezelfde events en snippets als een modelstap (`loop.codestap`): ze staan in
de redeneerkaart, hun getallen krijgen een citatie, en de regel met haar getallen en keys staat in het bewijs van de
beurt (`bewijs`). Het zijn geen data van het gesprek: een rapport of heropend gesprek rust er niet op. Het model ziet ze
niet en schrijft er niets van: een getal uit de regel in de modeltekst zonder eigen toolstap valt in de getalcontrole
zoals altijd. Een regel die het model zelf overnam (uit een eerdere beurt) vervalt, en de historie naar het model
houdt ze niet (`zonder_regels`). Faalt er iets, dan gaat het antwoord zonder de regel (zoals de citaties).
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from core.errors import log_interne_fout
from tools import afbreken, andere_definities, bronparen, maten, outcome, periode
from tools.schemas import TOOL_GET_MAAT, TOOL_VERGELIJKINGSGROEP

from .loop import _EVENT_OUTPUT_CHARS, ToolCall, codestap
from .onder_antwoord import KOP_DEFINITIES, KOP_GROEP, KOP_KRUISCONTROLE, KOPPEN, zonder_regels
from .stream import Emit

logger = logging.getLogger(__name__)

HETZELFDE_BEELD = "andere definities geven hetzelfde beeld"
REDEN_NIET_VASTGESTELD = "verschil, reden niet vastgesteld"
# De stap van de kruiscontrole: geen tool van het model (dispatch kent haar niet), alleen code roept haar aan.
STAP_KRUISCONTROLE = "kruiscontrole"
LABEL_DEFINITIE = "Andere definitie berekend"
LABEL_KRUISCONTROLE = "Kruiscontrole met de andere bron"
# De soorten bewijs die deze regels in het rekenbewijs zetten (#1244): het rapport en de export lezen ze terug.
BEWIJS_DEFINITIES = "andere_definities"
BEWIJS_KRUISCONTROLE = "kruiscontrole"

Stap = tuple[str, str]
StapHook = Callable[[ToolCall, str, object], Awaitable[None]]


def _json(tekst: str) -> dict:
    try:
        parsed = json.loads(tekst)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def nl_getal(waarde: float) -> str:
    """Een aantal zoals de app het schrijft: 475.460."""
    return f"{round(waarde):,}".replace(",", ".")


def nl_pct(pct: float) -> str:
    """Een verschil in procenten met teken en decimale komma: +0,1%, -2,0%."""
    return f"{pct:+.1f}%".replace(".", ",")


@dataclass
class Alternatiefuitkomst:
    naam: str
    uitleg: str
    waarde: float
    verschil_pct: float
    data_key: str | None


@dataclass
class Definitiecontrole:
    """De andere definities bij één get_maat-resultaat van het model."""

    hoofd: andere_definities.Hoofdgetal
    onderwerp: str | None  # de instelling, als het resultaat er een heeft
    uitkomsten: list[Alternatiefuitkomst] = field(default_factory=list)

    def regel(self) -> str | None:
        if not self.uitkomsten:
            return None
        jaar = periode.label(self.hoofd.startjaar)
        waar = f"{self.onderwerp}, {jaar}" if self.onderwerp else jaar
        boven = [u for u in self.uitkomsten if abs(u.verschil_pct) > andere_definities.DREMPEL_PCT]
        if not boven:
            namen = ", ".join(u.naam for u in self.uitkomsten)
            return f"{KOP_DEFINITIES} {HETZELFDE_BEELD} ({namen})."
        delen = [f"{u.naam} {nl_getal(u.waarde)} ({nl_pct(u.verschil_pct)})" for u in self.uitkomsten]
        return f"{KOP_DEFINITIES} in {waar} telt dit antwoord {nl_getal(self.hoofd.waarde)}; " + "; ".join(delen) + "."

    def bewijs(self) -> dict:
        resultaat = {
            # Alleen de key van het hoofdgetal: daar rust het bewijs op (rapportselectie); de stappen van code zijn geen
            # data van het gesprek.
            "data_key": self.hoofd.data_key,
            "keys_van_code": [u.data_key for u in self.uitkomsten if u.data_key],
            "schooljaar": periode.label(self.hoofd.startjaar),
            "hoofdgetal": self.hoofd.waarde,
            "alternatieven": [
                {"naam": u.naam, "uitleg": u.uitleg, "waarde": u.waarde, "verschil_pct": u.verschil_pct}
                for u in self.uitkomsten
            ],
            "regel": self.regel(),
        }
        return {
            "tool": BEWIJS_DEFINITIES,
            "argumenten": {"data_key": self.hoofd.data_key},
            "resultaat": json.dumps(resultaat, ensure_ascii=False, default=str),
        }


@dataclass
class Kruiscontrole:
    """Het getal van de andere bron bij één get_maat-resultaat met een bronpaar."""

    paar: bronparen.Bronpaar
    hoofd: andere_definities.Hoofdgetal
    andere: float
    andere_key: str | None

    @property
    def verschil(self) -> float:
        return self.andere - self.hoofd.waarde

    @property
    def verschil_pct(self) -> float:
        return andere_definities.verschil_pct(self.andere, self.hoofd.waarde) or 0.0

    def regel(self) -> str:
        p, jaar = self.paar, periode.label(self.hoofd.startjaar)
        verschil = round(self.verschil)
        if verschil == 0:
            vergelijking = f"evenveel als {p.cbs.naam}"
        else:
            richting = "meer" if verschil > 0 else "minder"
            vergelijking = f"{nl_getal(abs(verschil))} {richting} dan {p.cbs.naam} ({nl_getal(self.hoofd.waarde)})"
        tekst = (
            f"{KOP_KRUISCONTROLE} {p.duo.naam} telt in {jaar} {nl_getal(self.andere)} ({p.duo.afbakening}): "
            f"{vergelijking}, {nl_pct(self.verschil_pct)}."
        )
        boven = abs(self.verschil_pct) > p.drempel_pct
        if boven and not p.redenen:
            return f"{tekst} {REDEN_NIET_VASTGESTELD[0].upper()}{REDEN_NIET_VASTGESTELD[1:]}."
        if p.redenen:
            tekst += " Bekende redenen voor een verschil: " + "; ".join(r.tekst for r in p.redenen) + "."
        if not boven:
            tekst += f" Het verschil valt binnen de drempel van dit bronpaar ({_drempel(p.drempel_pct)})."
        return tekst

    def bewijs(self) -> dict:
        resultaat = {
            "data_key": self.hoofd.data_key,
            "keys_van_code": [self.andere_key] if self.andere_key else [],
            "bronpaar": self.paar.id,
            "schooljaar": periode.label(self.hoofd.startjaar),
            "cbs": self.hoofd.waarde,
            "duo": self.andere,
            "verschil": self.verschil,
            "verschil_pct": self.verschil_pct,
            "redenen": [{"tekst": r.tekst, "bron": r.bron} for r in self.paar.redenen],
            "regel": self.regel(),
        }
        return {
            "tool": BEWIJS_KRUISCONTROLE,
            "argumenten": {"data_key": self.hoofd.data_key, "bronpaar": self.paar.id},
            "resultaat": json.dumps(resultaat, ensure_ascii=False, default=str),
        }


def _drempel(pct: float) -> str:
    return f"{pct:g}%".replace(".", ",")


@dataclass
class Controles:
    """Wat code na het antwoord rekende: per soort de uitkomsten, en de stappen die het deed (voor de citaties)."""

    definities: list[Definitiecontrole] = field(default_factory=list)
    kruiscontroles: list[Kruiscontrole] = field(default_factory=list)
    groepen: list[str] = field(default_factory=list)  # de zinnen bij de vergelijkingsgroep
    stappen: list[Stap] = field(default_factory=list)

    def regels(self) -> list[str]:
        regels = [r for d in self.definities if (r := d.regel())]
        regels += [k.regel() for k in self.kruiscontroles]
        regels += [f"{KOP_GROEP} {zin}" for zin in self.groepen]
        return list(dict.fromkeys(regels))

    def bewijs(self) -> list[dict]:
        return [d.bewijs() for d in self.definities if d.uitkomsten] + [k.bewijs() for k in self.kruiscontroles]


def _get_maat_resultaten(steps: list[Stap]) -> list[tuple[str, dict]]:
    """De geslaagde get_maat-stappen van het model, elk resultaat één keer (dezelfde key is dezelfde selectie)."""
    gezien: set[str] = set()
    uit = []
    for tool, result in steps:
        parsed = _json(result) if tool == TOOL_GET_MAAT else {}
        key = parsed.get("data_key")
        if isinstance(key, str) and key not in gezien:
            gezien.add(key)
            uit.append((result, parsed))
    return uit


def _met_vergelijking(result: str, **vergelijking) -> str:
    """Het toolresultaat met de vergelijking die code erop deed, zoals de regel haar noemt."""
    parsed = _json(result)
    return json.dumps({**parsed, "vergelijking": vergelijking}, ensure_ascii=False, default=str) if parsed else result


def groepzinnen(steps: list[Stap]) -> list[str]:
    """De zin uit code bij elke vergelijkingsgroep van deze beurt (#1267)."""
    zinnen = [_json(result).get("zin") for tool, result in steps if tool == TOOL_VERGELIJKINGSGROEP]
    return list(dict.fromkeys(z for z in zinnen if isinstance(z, str) and z))


async def _stap(name: str, args: dict, emit: Emit, label: str, on_result: StapHook | None) -> str:
    """Een get_maat-aanroep van code, met de interne vormen toegestaan (`maten.codestap`)."""
    with maten.codestap():
        result, figure = await codestap(name, args, emit, label)
    if on_result is not None:
        await on_result(ToolCall(id=f"code-{name}", name=name, arguments=json.dumps(args), args=args), result, figure)
    return result


async def _kruisstap(paar: bronparen.Bronpaar, startjaar: int, emit: Emit, on_result: StapHook | None) -> str:
    """De DUO-kant van een bronpaar, als eigen stap in de redeneerkaart. Geen tool van het model: dispatch kent haar
    niet, en haar enige argumenten komen uit de tabel en het hoofdresultaat."""
    args = {"bronpaar": paar.id, "schooljaar": periode.label(startjaar)}
    await emit({"type": "tool_start", "name": STAP_KRUISCONTROLE, "label": LABEL_KRUISCONTROLE, "input": args})
    result = str(await afbreken.in_thread(bronparen.duo_getal, paar, startjaar))
    event = {
        "type": "tool_end",
        "name": STAP_KRUISCONTROLE,
        "output": result[:_EVENT_OUTPUT_CHARS],
        **outcome(STAP_KRUISCONTROLE, result),
    }
    if isinstance(key := _json(result).get("data_key"), str):
        event["data_key"] = key
    await emit(event)
    if on_result is not None:
        call = ToolCall(id=f"code-{STAP_KRUISCONTROLE}", name=STAP_KRUISCONTROLE, arguments=json.dumps(args), args=args)
        await on_result(call, result, None)
    return result


async def _definities(result: str, parsed: dict, emit: Emit, on_result: StapHook | None, stappen: list[Stap]):
    aanroepen = andere_definities.aanroepen(result)
    hoofd = andere_definities.hoofdgetal(parsed)
    if not aanroepen or hoofd is None or not hoofd.waarde:
        return None
    instelling = parsed.get("instelling")
    onderwerp = instelling.get("naam") if isinstance(instelling, dict) else None
    controle = Definitiecontrole(hoofd, onderwerp)
    for alternatief, args in aanroepen:
        alt = await _stap(TOOL_GET_MAAT, args, emit, f"{LABEL_DEFINITIE}: {alternatief.naam}", on_result)
        waarde = andere_definities.waarde_in(alt, hoofd.startjaar)
        pct = andere_definities.verschil_pct(waarde, hoofd.waarde) if waarde is not None else None
        if waarde is None or pct is None:
            stappen.append((TOOL_GET_MAAT, alt))
            continue
        # Het verschil dat de regel noemt, staat in de stap: zo is ook het percentage gedekt in de getalcontrole.
        stappen.append((TOOL_GET_MAAT, _met_vergelijking(alt, hoofdgetal=hoofd.waarde, verschil_pct=pct)))
        key = _json(alt).get("data_key")
        controle.uitkomsten.append(Alternatiefuitkomst(alternatief.naam, alternatief.uitleg, waarde, pct, key))
    return controle


async def _kruiscontrole(parsed: dict, emit: Emit, on_result: StapHook | None, stappen: list[Stap]):
    paar = bronparen.paar_voor(parsed)
    hoofd = andere_definities.hoofdgetal(parsed)
    if paar is None or hoofd is None or not hoofd.waarde:
        return None
    result = await _kruisstap(paar, hoofd.startjaar, emit, on_result)
    andere = andere_definities.hoofdgetal(_json(result))
    if andere is None or andere.startjaar != hoofd.startjaar:
        stappen.append((STAP_KRUISCONTROLE, result))
        return None
    controle = Kruiscontrole(paar, hoofd, andere.waarde, andere.data_key)
    stap = _met_vergelijking(
        result, hoofdgetal=hoofd.waarde, verschil=controle.verschil, verschil_pct=controle.verschil_pct
    )
    stappen.append((STAP_KRUISCONTROLE, stap))
    return controle


async def voer_uit(steps: list[Stap], emit: Emit, on_result: StapHook | None = None) -> Controles:
    """De controles bij de stappen van het model: per get_maat-resultaat de andere definities en de kruiscontrole, en
    de zin bij een vergelijkingsgroep. Een fout laat alleen die controle weg, nooit het antwoord."""
    controles = Controles(groepen=groepzinnen(steps))
    for result, parsed in _get_maat_resultaten(steps):
        try:
            if (d := await _definities(result, parsed, emit, on_result, controles.stappen)) is not None:
                controles.definities.append(d)
            if (k := await _kruiscontrole(parsed, emit, on_result, controles.stappen)) is not None:
                controles.kruiscontroles.append(k)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_interne_fout(exc, "controlestappen")
    logger.info(
        "ONDER ANTWOORD  definities=%d  kruiscontroles=%d  groepen=%d  stappen=%d",
        len(controles.definities),
        len(controles.kruiscontroles),
        len(controles.groepen),
        len(controles.stappen),
    )
    return controles


def met_regels(tekst: str, controles: Controles) -> str:
    """Het antwoord met de regels eronder, elk één keer; een regel die het model zelf schreef, vervalt."""
    regels = controles.regels()
    if not tekst.strip() or (not regels and not any(k in tekst for k in KOPPEN)):
        return tekst
    kaal = zonder_regels(tekst)
    return "\n\n".join([kaal, *regels]) if regels else kaal


def rapportdefinities(berekeningen: list[dict]) -> list[dict]:
    """De regels uit het rekenbewijs van het gesprek, voor het definitieblok van het rapport ({begrip, definitie})."""
    begrippen = {
        BEWIJS_DEFINITIES: ("Andere definities", KOP_DEFINITIES),
        BEWIJS_KRUISCONTROLE: ("Ter controle", KOP_KRUISCONTROLE),
    }
    items: list[dict] = []
    for bewijs in berekeningen or []:
        soort = begrippen.get(bewijs.get("tool")) if isinstance(bewijs, dict) else None
        regel = _json(str(bewijs.get("resultaat") or "")).get("regel") if soort else None
        if soort and isinstance(regel, str) and regel.startswith(soort[1]):
            item = {"begrip": soort[0], "definitie": regel.removeprefix(soort[1]).strip()}
            if item not in items:
                items.append(item)
    return items
