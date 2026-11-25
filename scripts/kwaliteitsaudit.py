#!/usr/bin/env python
"""
De wekelijkse kwaliteitsaudit (#1250): een weekrapport in Markdown uit de kwaliteitstellers of een logexport, zonder
vraag- of antwoordtekst.

Gebruik:
    uv run python scripts/kwaliteitsaudit.py --log export.jsonl [--tot JJJJ-MM-DD] [--uit rapport.md]
    uv run python scripts/kwaliteitsaudit.py --prometheus deze-week.json --prometheus-vorige vorige-week.json

Sinds #983 zijn de duimpjes weg; wat de app wel per antwoord vastlegt, leest dit script structureel. Het rapport geeft
de aantallen per controle en per tool, de trend tegen de vorige week, de top 10 van wat het vaakst misgaat en, bij een
duidelijk patroon, een kandidaat-wijziging (domeinregel, catalogusvermelding, voorbeeldvraag).

Twee bronnen, één per run:
- `--log`: een export van het JSON-log (logging_config.py), één regel per object. Het script leest alleen de vaste
  regelsoorten in REGELSOORTEN en daaruit alleen namen uit de vaste lijsten (de controles van agent/controles.py, de
  tools van de app) en vaste woorden; een andere naam telt als `overig`. Regels op DEBUG, zoals TOOL CALL met de vraag
  erin, en elke andere regelsoort slaat het over. De week loopt tot `--tot` (standaard vandaag, niet meegeteld); de
  vorige week is de zeven dagen daarvoor.
- `--prometheus` en `--prometheus-vorige`: per teller het antwoord van de Prometheus-API op een `increase(...[7d])`,
  zonder en met `offset 7d` (de query's staan in docs/operatie.md). Het script vraagt zelf niets op.

Het script leest alleen bestanden en schrijft één rapport: geen netwerk, geen model en geen git. Een voorstel uit het
rapport wordt een MR door een beheerder of een factory-job, altijd met review en nooit automatisch gemerged.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROLES_PY = ROOT / "agent" / "controles.py"
SCHEMAS_PY = ROOT / "tools" / "schemas.py"

# Zoals core/metrics.py: dezelfde woorden als de labels van de tellers (tests/test_kwaliteitsaudit.py houdt ze gelijk).
CONTROLE_UITKOMSTEN = ("hard", "zacht", "niet_gecontroleerd", "ok")
TOOL_WEIGERREDENEN = ("op_slot", "limiet", "afgekapt")
OVERIG = "overig"
# Wanneer iets een kandidaat-wijziging is: minstens zo vaak deze week, en vaker dan de vorige week.
KANDIDAAT_MIN = 5
TOP = 10
# Alleen deze niveaus: wat op DEBUG staat, mag gebruikerstekst bevatten (#475).
NIVEAUS = frozenset({"INFO", "WARNING", "ERROR"})


def _tuple_uit(pad: Path, naam: str) -> tuple[str, ...]:
    """Een vaste tuple uit een modulebestand, gelezen zonder de module te laden (geen app, geen model)."""
    for knoop in ast.parse(pad.read_text(encoding="utf-8")).body:
        if isinstance(knoop, ast.Assign) and any(isinstance(d, ast.Name) and d.id == naam for d in knoop.targets):
            return tuple(ast.literal_eval(knoop.value))
    raise SystemExit(f"{pad}: {naam} niet gevonden")


def controlenamen() -> frozenset[str]:
    return frozenset(_tuple_uit(CONTROLES_PY, "CONTROLENAMEN"))


def toolnamen() -> frozenset[str]:
    """De namen van alle tools: elke `TOOL_… = "…"` in tools/schemas.py, zoals tools.LABELS ze kent."""
    namen = set()
    for knoop in ast.parse(SCHEMAS_PY.read_text(encoding="utf-8")).body:
        if (
            isinstance(knoop, ast.Assign)
            and isinstance(knoop.value, ast.Constant)
            and isinstance(knoop.value.value, str)
            and any(isinstance(d, ast.Name) and d.id.startswith("TOOL_") for d in knoop.targets)
        ):
            namen.add(knoop.value.value)
    return frozenset(namen)


@dataclass
class Telling:
    """Wat er in één week gebeurde; alle sleutels komen uit de vaste lijsten of zijn OVERIG."""

    antwoorden: int = 0
    controles: Counter = field(default_factory=Counter)  # (controle, uitkomst) → aantal
    herkansingen: int = 0
    ingehouden: int = 0
    stappenbudget_op: int = 0
    tools: Counter = field(default_factory=Counter)  # (tool, reden) → aantal


class _Namen:
    def __init__(self) -> None:
        self.controles = controlenamen()
        self.tools = toolnamen()

    def controle(self, naam: str) -> str:
        return naam if naam in self.controles else OVERIG

    def tool(self, naam: str) -> str:
        return naam if naam in self.tools else OVERIG


def _uitkomst(woord: str) -> str:
    woord = woord.strip().replace(" ", "_")
    return woord if woord in CONTROLE_UITKOMSTEN else OVERIG


def _reden(woord: str) -> str:
    return woord if woord in TOOL_WEIGERREDENEN else OVERIG


# ── Logexport ────────────────────────────────────────────────────────────────

_CONTROLE = re.compile(r"(\w+)=(hard|zacht|niet gecontroleerd|ok|\S+)")
_OP_SLOT = re.compile(r"^TOOL OP SLOT  (\S+?):")
_LIMIET = re.compile(r"^TOOL LIMIET  (\S+) ")
_AFGEKAPT = re.compile(r"^TOOL_AFGEKAPT tool=(\S+)")


def _controles(t: Telling, bericht: str, namen: _Namen) -> None:
    t.antwoorden += 1
    for naam, uitkomst in _CONTROLE.findall(bericht.removeprefix("CONTROLES")):
        t.controles[namen.controle(naam), _uitkomst(uitkomst)] += 1


def _herkansing(t: Telling, bericht: str, namen: _Namen) -> None:
    t.herkansingen += 1


def _ingehouden(t: Telling, bericht: str, namen: _Namen) -> None:
    t.ingehouden += 1


def _stappenbudget(t: Telling, bericht: str, namen: _Namen) -> None:
    t.stappenbudget_op += 1


def _toolregel(patroon: re.Pattern, reden: str):
    def tel(t: Telling, bericht: str, namen: _Namen) -> None:
        m = patroon.match(bericht)
        t.tools[namen.tool(m.group(1) if m else ""), reden] += 1

    return tel


# De regelsoorten die het script leest (agent/controles.py, agent/run.py, agent/loop.py), met hun begin. Een andere
# regel, ook een die met een van deze woorden lijkt te beginnen, telt niet.
REGELSOORTEN = {
    "CONTROLES": ("CONTROLES  ", _controles),
    "HERKANSING": ("HERKANSING  ", _herkansing),
    "ANTWOORD INGEHOUDEN": ("ANTWOORD INGEHOUDEN  ", _ingehouden),
    "STAPPENBUDGET OP": ("STAPPENBUDGET OP ", _stappenbudget),
    "TOOL OP SLOT": ("TOOL OP SLOT  ", _toolregel(_OP_SLOT, "op_slot")),
    "TOOL LIMIET": ("TOOL LIMIET  ", _toolregel(_LIMIET, "limiet")),
    "TOOL_AFGEKAPT": ("TOOL_AFGEKAPT ", _toolregel(_AFGEKAPT, "afgekapt")),
}


def _week(tot: date) -> tuple[date, date, date]:
    """(begin vorige week, begin deze week, tot): deze week is [tot - 7, tot), de vorige de zeven dagen ervoor."""
    return tot - timedelta(days=14), tot - timedelta(days=7), tot


def _moment(tekst: object) -> date | None:
    try:
        moment = datetime.fromisoformat(str(tekst))
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC).date()


def lees_log(pad: Path, tot: date) -> tuple[Telling, Telling, tuple[int, int]]:
    """(deze week, vorige week, (regels gelezen, regels meegeteld)) uit een export van het JSON-log."""
    vorige_begin, deze_begin, einde = _week(tot)
    deze, vorige, namen = Telling(), Telling(), _Namen()
    gelezen = meegeteld = 0
    with pad.open(encoding="utf-8") as f:
        for regel in f:
            if not regel.strip():
                continue
            gelezen += 1
            try:
                obj = json.loads(regel)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or obj.get("level") not in NIVEAUS:
                continue
            bericht = obj.get("message")
            dag = _moment(obj.get("timestamp"))
            if not isinstance(bericht, str) or dag is None or not (vorige_begin <= dag < einde):
                continue
            soort = next((tel for begin, tel in REGELSOORTEN.values() if bericht.startswith(begin)), None)
            if soort is None:
                continue
            soort(deze if dag >= deze_begin else vorige, bericht, namen)
            meegeteld += 1
    return deze, vorige, (gelezen, meegeteld)


# ── Prometheus ───────────────────────────────────────────────────────────────


def _reeksen(antwoord: object) -> list[tuple[dict, int]]:
    """(labels, aantal) uit één antwoord van /api/v1/query (vector); een increase() wordt een heel aantal."""
    if not isinstance(antwoord, dict) or antwoord.get("status") != "success":
        raise SystemExit("Prometheus: verwacht een antwoord met status success (vector)")
    uit = []
    for reeks in antwoord.get("data", {}).get("result", []):
        labels = reeks.get("metric") or {}
        waarde = float(reeks.get("value", [0, "0"])[1])
        uit.append((labels, round(waarde)))
    return uit


def lees_prometheus(pad: Path) -> Telling:
    """Een week uit `{teller: antwoord}`; een teller die ontbreekt telt als 0."""
    try:
        data = json.loads(pad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as fout:
        raise SystemExit(f"{pad}: niet te lezen ({fout})") from fout
    t, namen = Telling(), _Namen()
    per_controle: Counter = Counter()
    for labels, n in _reeksen(data.get("edudata_controle_uitkomsten_total", _LEEG)):
        controle = namen.controle(str(labels.get("controle", "")))
        t.controles[controle, _uitkomst(str(labels.get("uitkomst", "")))] += n
        per_controle[controle] += n
    # Elk antwoord telt bij elke controle één uitkomst: het aantal antwoorden is dat van de controle met de meeste.
    t.antwoorden = max((n for c, n in per_controle.items() if c != OVERIG), default=0)
    t.herkansingen = sum(n for _, n in _reeksen(data.get("edudata_herkansingen_total", _LEEG)))
    t.ingehouden = sum(n for _, n in _reeksen(data.get("edudata_ingehouden_antwoorden_total", _LEEG)))
    t.stappenbudget_op = sum(n for _, n in _reeksen(data.get("edudata_stappenbudget_op_total", _LEEG)))
    for labels, n in _reeksen(data.get("edudata_tool_weigeringen_total", _LEEG)):
        t.tools[namen.tool(str(labels.get("tool", ""))), _reden(str(labels.get("reden", "")))] += n
    return t


_LEEG = {"status": "success", "data": {"resultType": "vector", "result": []}}


# ── Rapport ──────────────────────────────────────────────────────────────────


def _trend(nu: int, voor: int) -> str:
    if voor == 0 and nu > 0:
        return "nieuw"
    verschil = nu - voor
    return f"+{verschil}" if verschil > 0 else str(verschil)


def _misgegaan(t: Telling, controle: str) -> int:
    return sum(n for (c, u), n in t.controles.items() if c == controle and u != "ok")


def _fouten(t: Telling) -> Counter:
    """Wat misging, als regel voor de top 10: controles die niet ok gaven, toolweigeringen, ingehouden, budget op."""
    uit: Counter = Counter()
    for (controle, uitkomst), n in t.controles.items():
        if uitkomst != "ok" and n:
            uit[f"controle {controle}: {uitkomst.replace('_', ' ')}"] += n
    for (tool, reden), n in t.tools.items():
        if n:
            uit[f"tool {tool}: {reden.replace('_', ' ')}"] += n
    if t.ingehouden:
        uit["ingehouden antwoorden"] = t.ingehouden
    if t.stappenbudget_op:
        uit["stappenbudget op"] = t.stappenbudget_op
    return uit


def _kandidaat(wat: str) -> str:
    if wat.startswith("controle "):
        return "kandidaat-wijziging in een domeinregel (docs/domeinregels.md) of de prompt die deze controle voorkomt"
    if wat.endswith(": op slot"):
        return (
            "kandidaat-wijziging in de catalogusvermelding of de toolbeschrijving: de bron of de aanroep faalt herhaald"
        )
    if wat.endswith(": limiet"):
        return "kandidaat-wijziging in de toolbeschrijving of een voorbeeldvraag: het model roept de tool te vaak aan"
    if wat.endswith(": afgekapt"):
        return "kandidaat-wijziging in een voorbeeldvraag of de toolbeschrijving: filter of selecteer kolommen eerder"
    return "kandidaat-wijziging in een voorbeeldvraag of de catalogusvermelding: het model komt er niet uit binnen het budget"


def _tabel(kop: list[str], rijen: list[list[object]]) -> list[str]:
    return [
        "| " + " | ".join(kop) + " |",
        "|" + "---|" * len(kop),
        *("| " + " | ".join(str(c) for c in rij) + " |" for rij in rijen),
    ]


def rapport(deze: Telling, vorige: Telling, tot: date, *, bron: str, gelezen: tuple[int, int] | None = None) -> str:
    vorige_begin, deze_begin, einde = _week(tot)
    laatste = einde - timedelta(days=1)
    bronregel = f"Bron: {bron}"
    if gelezen:
        bronregel += f" ({gelezen[0]} regels gelezen, {gelezen[1]} meegeteld)"
    regels = [
        f"# Kwaliteitsaudit {deze_begin.isoformat()} t/m {laatste.isoformat()}",
        "",
        f"{bronregel}; vorige week: {vorige_begin.isoformat()} t/m {(deze_begin - timedelta(days=1)).isoformat()}.",
        "Alleen tellingen per controle en per tool: geen vraag- of antwoordtekst, gebruikersnaam of pseudoniem.",
        "",
        "## Samenvatting",
        "",
    ]
    weigeringen = sum(deze.tools.values()), sum(vorige.tools.values())
    signalen = [
        ("Antwoorden gecontroleerd", deze.antwoorden, vorige.antwoorden),
        ("Herkansingen", deze.herkansingen, vorige.herkansingen),
        ("Ingehouden antwoorden", deze.ingehouden, vorige.ingehouden),
        ("Stappenbudget op", deze.stappenbudget_op, vorige.stappenbudget_op),
        ("Toolweigeringen", *weigeringen),
    ]
    regels += _tabel(
        ["Signaal", "Deze week", "Vorige week", "Trend"], [[s, n, v, _trend(n, v)] for s, n, v in signalen]
    )

    # Het meest misgegaan eerst; overig achteraan bij een gelijk aantal.
    controles = {c for c, _ in deze.controles} | {c for c, _ in vorige.controles}
    volgorde = sorted(controles, key=lambda c: (-_misgegaan(deze, c), c == OVERIG, c))
    rijen: list[list[object]] = []
    for c in volgorde:
        uit = [deze.controles[c, u] for u in CONTROLE_UITKOMSTEN]
        nu, voor = _misgegaan(deze, c), _misgegaan(vorige, c)
        rijen.append([c, *uit, nu, voor, _trend(nu, voor)])
    regels += ["", "## Per controle", "", "Misgegaan is hard, zacht of niet gecontroleerd.", ""]
    kop = ["Controle", "Hard", "Zacht", "Niet gecontroleerd", "Ok", "Misgegaan", "Vorige week", "Trend"]
    regels += _tabel(kop, rijen) if rijen else ["Geen regel CONTROLES in deze periode."]

    def weigeringen_van(telling: Telling, tool: str) -> int:
        return sum(telling.tools[tool, r] for r in TOOL_WEIGERREDENEN)

    tools = {t for t, _ in deze.tools} | {t for t, _ in vorige.tools}
    rijen = []
    for t in sorted(tools, key=lambda t: (-weigeringen_van(deze, t), t == OVERIG, t)):
        uit = [deze.tools[t, r] for r in TOOL_WEIGERREDENEN]
        nu, voor = weigeringen_van(deze, t), weigeringen_van(vorige, t)
        rijen.append([t, *uit, nu, voor, _trend(nu, voor)])
    regels += ["", "## Per tool", ""]
    kop = ["Tool", "Op slot", "Limiet", "Afgekapt", "Totaal", "Vorige week", "Trend"]
    regels += _tabel(kop, rijen) if rijen else ["Geen toolweigering in deze periode."]

    nu, voor = _fouten(deze), _fouten(vorige)
    top = sorted(nu.items(), key=lambda item: (-item[1], item[0].casefold()))[:TOP]
    regels += ["", "## Top 10: wat het vaakst misgaat", ""]
    rijen = [[i, wat, n, voor[wat], _trend(n, voor[wat])] for i, (wat, n) in enumerate(top, 1)]
    regels += _tabel(["#", "Wat", "Deze week", "Vorige week", "Trend"], rijen) if rijen else ["Niets misgegaan."]

    regels += ["", "## Kandidaat-wijzigingen", ""]
    kandidaten = [(wat, n) for wat, n in top if n >= KANDIDAAT_MIN and n > voor[wat]]
    regels += [f"- {wat} ({n}, vorige week {voor[wat]}): {_kandidaat(wat)}." for wat, n in kandidaten]
    if not kandidaten:
        regels.append(
            f"Geen duidelijk patroon: niets kwam {KANDIDAAT_MIN} keer of vaker voor en vaker dan de vorige week."
        )
    regels += [
        "",
        "Een kandidaat is een voorstel, geen wijziging. Een beheerder of een factory-job maakt er een MR van, altijd met "
        "review en nooit automatisch gemerged; dit script wijzigt zelf niets.",
        "",
    ]
    return "\n".join(regels)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1], formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--log", type=Path, help="export van het JSON-log, één object per regel")
    parser.add_argument("--prometheus", type=Path, help="per teller het antwoord op increase(...[7d])")
    parser.add_argument("--prometheus-vorige", type=Path, help="dezelfde query's met offset 7d")
    parser.add_argument("--tot", type=date.fromisoformat, default=datetime.now(UTC).date(), help="einde van de week")
    parser.add_argument("--uit", type=Path, help="schrijf het rapport hierheen; standaard naar stdout")
    args = parser.parse_args(argv)
    if bool(args.log) == bool(args.prometheus):
        parser.error("kies één bron: --log, of --prometheus met --prometheus-vorige")
    if args.prometheus and not args.prometheus_vorige:
        parser.error("--prometheus vraagt ook --prometheus-vorige (dezelfde query's met offset 7d)")
    if args.log:
        deze, vorige, gelezen = lees_log(args.log, args.tot)
        tekst = rapport(deze, vorige, args.tot, bron=f"logexport `{args.log.name}`", gelezen=gelezen)
    else:
        deze, vorige = lees_prometheus(args.prometheus), lees_prometheus(args.prometheus_vorige)
        tekst = rapport(deze, vorige, args.tot, bron="Prometheus")
    if args.uit:
        args.uit.write_text(tekst, encoding="utf-8")
    else:
        sys.stdout.write(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
