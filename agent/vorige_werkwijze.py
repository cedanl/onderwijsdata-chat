"""De werkwijze van de vorige databeurt voor het model, bij een vervolgvraag (#992).

Na een koppeling van de Studiekeuzedatabase en DUO op `brin` vroeg de gebruiker welke sleutels de koppeling gebruikte.
De geschiedenis draagt alleen de tekst van het antwoord (`_parse_history`), dus het model antwoordde "dat kan ik niet
bevestigen". De sessie weet het wel: per key de aanroep die hem maakte (`data_provenance`) en wat de store erover weet.

Deze module zet dat om in een korte, vaste samenvatting: bronnen en stappen, met alleen de argumenten uit een vaste lijst
en nooit de code van een eigen analyse of een waarde uit de data. Het is werkwijze, geen bewijs voor getallen: de
getalcontrole leest deze tekst niet.
"""

import re

from tools import store
from tools.schemas import TOOL_RUN_ANALYSIS
from tools.store import KeyMeta

from .session_data import vorige_databeurt

KOP = "Werkwijze van de vorige databeurt (alleen werkwijze, geen waarden of bewijs voor getallen):"
MAX_TEKENS = 1500

EIGEN_ANALYSE = f"eigen analyse ({TOOL_RUN_ANALYSIS})"

# De argumenten die zeggen wat er gebeurde; de rest (code, titels, kleuren, max_rows) blijft weg.
_ARGUMENTEN = (
    "dataset_id",
    "resource",
    "weergave",
    "maat",
    "instelling",
    "opleiding",
    "schooljaren",
    "filters",
    "columns",
    "group_by",
    "aggregate",
    "sleutels",
    "kolommen_links",
    "kolommen_rechts",
)
# Waar een laadaanroep zijn dataset noemt, als de store de key niet meer kent (na heropenen).
_DATASETARGUMENTEN = ("dataset_id", "resource", "weergave", "maat")
# De argumenten die naar een eerdere key wijzen: de linker- en de rechterkant van een stap.
_OUDERS = ("data_key", "andere_key")

_MAX_WAARDE = 60  # tekens per argumentwaarde: de waarden komen van het model
_MAX_ITEMS = 8  # elementen per lijst of mapping
_MAX_KEYS = 40  # keys per boom: begrenst de wandeling, ook bij een lus in de provenance

_KORREL = re.compile(r"\bkorrel (\S+)\s*$")


def werkwijze_vorige_databeurt(session: dict) -> str:
    """Bronnen en stappen van de laatste eerdere vraag die data maakte, of "" als die er niet is."""
    bomen = [_Boom(session, key) for key in vorige_databeurt(session)]
    # Een key waar een latere key van dezelfde beurt op rust (de tabellen onder een koppeling), staat al in diens regel.
    bovenste = [b for i, b in enumerate(bomen) if not any(b.keys[0] in a.keys for a in bomen[i + 1 :])]
    bovenste = [b for b in bovenste if b.bronnen or b.stappen]
    if not bovenste:
        return ""
    return _binnen_de_grens([b.regel() for b in bovenste], [b.korte_regel() for b in bovenste])


class _Boom:
    """De keten onder één key: elke key waar hij op rust, oudste eerst, met de linkerkant vóór de rechterkant."""

    def __init__(self, session: dict, key: str):
        self._provenance: dict = session.get("data_provenance") or {}
        self.keys: list[str] = []
        self.bronnen: list[str] = []
        self.stappen: list[tuple[dict, KeyMeta | None]] = []
        self._volg(key)

    def _volg(self, key: object) -> None:
        if not isinstance(key, str) or key in self.keys or len(self.keys) >= _MAX_KEYS:
            return
        self.keys.append(key)
        call = self._provenance.get(key)
        call = call if isinstance(call, dict) else None
        meta = store.meta(key)
        ouders = [o for o in _ouders(call, meta) if o in self._provenance or store.meta(o) is not None]
        for ouder in ouders:
            self._volg(ouder)
        if not ouders and (bron := _bron(call, meta)):
            self.bronnen.append(bron)
        if call is not None:
            self.stappen.append((call, meta))

    def regel(self) -> str:
        return self._regel([_stap(call, meta) for call, meta in self.stappen])

    def korte_regel(self) -> str:
        return self._regel([_toolnaam(call) for call, _ in self.stappen])

    def _regel(self, stappen: list[str]) -> str:
        delen = []
        if bronnen := list(dict.fromkeys(self.bronnen)):
            delen.append(f"Bronnen: {'; '.join(bronnen)}.")
        if stappen:
            delen.append(f"Stappen: {' → '.join(stappen)}.")
        return f"- {' '.join(delen)}"


def _ouders(call: dict | None, meta: KeyMeta | None) -> list[str]:
    """De keys waar een key op rust: uit zijn aanroep, en uit de store als die hem nog kent."""
    args = _argumenten(call)
    ouders = [args.get(naam) for naam in _OUDERS]
    if meta is not None:
        ouders += [meta.afgeleid_van, *(meta.gelezen or ())]
    return [o for o in dict.fromkeys(ouders) if isinstance(o, str)]


def _bron(call: dict | None, meta: KeyMeta | None) -> str:
    """Bron en dataset van een geladen tabel: uit de store, anders uit de laadaanroep."""
    if meta is not None:
        return _kort(f"{meta.bron} {meta.dataset}")
    args = _argumenten(call)
    if call is None or any(args.get(naam) for naam in _OUDERS):
        return ""  # een afgeleide stap waarvan de ouder onbekend is: geen bron om te noemen
    dataset = next((args[a] for a in _DATASETARGUMENTEN if args.get(a) not in (None, "")), None)
    naam = _toolnaam(call)
    return f"{_waarde(dataset)} (via {naam})" if dataset is not None else naam


def _stap(call: dict, meta: KeyMeta | None) -> str:
    if call.get("name") == TOOL_RUN_ANALYSIS:
        return EIGEN_ANALYSE  # de code blijft weg: ze kan waarden uit de data bevatten
    args = _argumenten(call)
    delen = [f"{naam}={_waarde(args[naam])}" for naam in _ARGUMENTEN if args.get(naam) not in (None, "", [], {})]
    if meta is not None and (gevonden := _KORREL.search(meta.stap or "")):
        delen.append(f"korrel={_kort(gevonden.group(1))}")
    return f"{_toolnaam(call)}({', '.join(delen)})"


def _toolnaam(call: dict) -> str:
    return _kort(str(call.get("name") or "onbekende stap"))


def _argumenten(call: dict | None) -> dict:
    args = (call or {}).get("arguments")
    return args if isinstance(args, dict) else {}


def _waarde(waarde: object) -> str:
    """Een argumentwaarde op één regel en ingekort: een lijst of mapping met hoogstens een paar elementen."""
    if isinstance(waarde, dict):
        paren = list(waarde.items())
        tekst = ", ".join(f"{_kort(str(k))}: {_waarde(v)}" for k, v in paren[:_MAX_ITEMS])
        return _kort(f"{{{tekst}{', …' if len(paren) > _MAX_ITEMS else ''}}}")
    if isinstance(waarde, list | tuple):
        tekst = ", ".join(_waarde(v) for v in waarde[:_MAX_ITEMS])
        return _kort(f"[{tekst}{', …' if len(waarde) > _MAX_ITEMS else ''}]")
    return _kort(str(waarde))


def _kort(tekst: str, grens: int = _MAX_WAARDE) -> str:
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= grens else tekst[: grens - 1] + "…"


def _binnen_de_grens(regels: list[str], korte_regels: list[str]) -> str:
    """Het blok met kop, hoogstens MAX_TEKENS: eerst de volledige regels, dan alleen toolnamen, dan de laatste keys."""
    for kandidaat in (regels, korte_regels):
        tekst = "\n".join([KOP, *kandidaat])
        if len(tekst) <= MAX_TEKENS:
            return tekst
    # Nog te lang: de laatste keys van de beurt wegen het zwaarst, de eerste vallen weg met een telling.
    for weg in range(1, len(korte_regels)):
        tekst = "\n".join([KOP, f"- (nog {weg} eerdere tabellen van die beurt weggelaten)", *korte_regels[weg:]])
        if len(tekst) <= MAX_TEKENS:
            return tekst
    tekst = "\n".join([KOP, korte_regels[-1]])
    return tekst if len(tekst) <= MAX_TEKENS else tekst[: MAX_TEKENS - 1] + "…"
