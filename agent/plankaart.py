"""De plankaart vóór een vraag over meer bronnen (#1268), alleen met "Geavanceerd".

Een koppelvraag (route 3: twee bronnen naast elkaar, `relatie`/`koppel_data`) laadt minuten lang; een verkeerd begrepen
vraag zag de gebruiker pas achteraf (#1218). Met Geavanceerd krijgt het model de halt-tool `plan_voorleggen`: vóór het
eerste laden legt het per bron de laadaanroep voor, met de koppelsleutel. De beurt stopt dan, zoals na `clarify_scope`, en
de kaart komt uit code: titel, dataset en versie uit de catalogus, de selectie in woorden uit de genormaliseerde
argumenten (ADR-006), de sleutel alleen als bekende sleutelnaam en een vaste grove duur. Tekst van het model (een
samenvatting vóór de aanroep, een extra argument) komt er niet op.

"Klopt, ga door" laat code precies die laadaanroepen uitvoeren (`aanroepen`, als stappen vóór de eerste modelronde), en
de guard (`weigering`) weigert elke andere laadaanroep in die beurt met een melding aan het model, zoals `halt_check` een
kapotte kaart weigert (#1067). De antwoordcontrole na het antwoord verandert niet.

Zonder Geavanceerd is de tool er niet en is de toolset gelijk aan die van vóór #1268.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass

from onderwijsbronnen import sleutels as _sleutels

from tools import arbeidsmarkt, financien, studiekeuze, vacatures, wo_personeel
from tools.canoniek import aanroep as canonieke_aanroep
from tools.catalog import bron_titel, catalogus_laatste_update, resource_titel
from tools.maten import MATEN
from tools.schemas import (
    TOOL_GET_ACCREDITATIE,
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_CBS_DATA,
    TOOL_GET_CBS_DIMENSION,
    TOOL_GET_COLLEGEGELD,
    TOOL_GET_DUO_DATA,
    TOOL_GET_INSPECTIEOORDEEL,
    TOOL_GET_INSPECTIEOORDEEL_VO,
    TOOL_GET_MAAT,
    TOOL_GET_MBO_INDICATOREN,
    TOOL_GET_ONTSTANE_VACATURES,
    TOOL_GET_RIO_DATA,
    TOOL_GET_RIO_INSTELLING,
    TOOL_GET_ROA_BENCHMARK,
    TOOL_GET_STUDIEKEUZE,
    TOOL_GET_UWV_VACATURES,
    TOOL_GET_VACATURES,
    TOOL_GET_WO_PERSONEEL,
)

from .loop import ToolCall
from .periodetekst import periodecode_als_label

logger = logging.getLogger(__name__)

TOOL_PLAN = "plan_voorleggen"

# De sessiesleutels: de stand van Geavanceerd voor dit verzoek (routes/chat.py), het plan dat op bevestiging wacht en het
# bevestigde plan, alleen tijdens de beurt die het uitvoert.
AAN = "plankaart"
OPEN = "plan_open"
BEVESTIGD = "plan_bevestigd"

# De tools die data uit een bron laden: alleen die staan op een plan, en alleen die weigert de guard.
LAADSTAPPEN = frozenset(
    {
        TOOL_GET_MAAT,
        TOOL_GET_CBS_DATA,
        TOOL_GET_DUO_DATA,
        TOOL_GET_RIO_DATA,
        TOOL_GET_RIO_INSTELLING,
        TOOL_GET_VACATURES,
        TOOL_GET_ONTSTANE_VACATURES,
        TOOL_GET_UWV_VACATURES,
        TOOL_GET_ROA_BENCHMARK,
        TOOL_GET_INSPECTIEOORDEEL,
        TOOL_GET_INSPECTIEOORDEEL_VO,
        TOOL_GET_MBO_INDICATOREN,
        TOOL_GET_ACCREDITATIE,
        TOOL_GET_COLLEGEGELD,
        TOOL_GET_BESTUURSFINANCIEN,
        TOOL_GET_WO_PERSONEEL,
        TOOL_GET_STUDIEKEUZE,
    }
)
# Hoogstens zoveel laadstappen op één kaart; meer is geen plan dat iemand in één oogopslag nakijkt.
MAX_STAPPEN = 4

# De sleutels waarop een plan mag koppelen: de codesleutels van de catalogus (`koppelbaar_via`), niet op naam (#958).
SLEUTELS = tuple(naam for naam, s in _sleutels.SLEUTELS.items() if not s.op_naam)

# De vaste dataset achter een tool die geen dataset-ID meekrijgt (zoals agent/datasetcontext.py).
_VASTE_DATASET = {
    **arbeidsmarkt.DATASET,
    **vacatures.DATASET,
    TOOL_GET_BESTUURSFINANCIEN: financien.DATASET,
    TOOL_GET_WO_PERSONEEL: wo_personeel.DATASET,
    TOOL_GET_STUDIEKEUZE: studiekeuze.DATASET,
}
# De bron achter een tool zonder dataset in de catalogus.
_BRONNAAM = {
    TOOL_GET_RIO_INSTELLING: "RIO: één instelling",
    TOOL_GET_INSPECTIEOORDEEL: "Onderwijsinspectie: oordelen",
    TOOL_GET_INSPECTIEOORDEEL_VO: "Onderwijsinspectie: oordelen vo",
    TOOL_GET_MBO_INDICATOREN: "Mbo-indicatoren",
    TOOL_GET_ACCREDITATIE: "NVAO: accreditaties",
    TOOL_GET_COLLEGEGELD: "Collegegeld",
}
# Argumentnamen in woorden; een naam die hier niet staat, komt er zoals hij is.
_WOORD = {
    "schooljaren": "jaren",
    "jaren": "jaren",
    "periode": "jaren",
    "perioden": "jaren",
    "instelling": "instelling",
    "sector": "sector",
    "vorm": "vorm",
    "resource": "bestand",
    "niveau": "niveau",
    "provincie": "provincie",
    "regio": "regio",
    "opleiding": "opleiding",
    "opleiding_naar_geslacht": "opleiding (naar geslacht)",
}
# Een waarde op de kaart is kort: een lange lijst of tekst krapt in tot deze lengte.
_MAX_WAARDE = 160

# Een grove duur per aantal bronnen, geen meting (#1268): wat de gebruiker ongeveer te wachten staat.
_DUUR = {2: "ongeveer een minuut"}
_DUUR_MEER = "een tot twee minuten"

OPEN_MELDING = "Plan voorgelegd aan de gebruiker; de beurt wacht op bevestiging."
AANGEPAST_MELDING = "De gebruiker wilde het plan aanpassen; er is niets geladen."


def bevestigd_melding(stappen: list[dict]) -> str:
    """Het toolresultaat van `plan_voorleggen` na "Klopt, ga door": wat code nu laadt, en dat de rest geweigerd wordt."""
    plan = json.dumps([{"tool": s["tool"], "argumenten": s["args"]} for s in stappen], ensure_ascii=False)
    return (
        "De gebruiker bevestigde het plan. De app laadt nu precies deze stappen; hun resultaten volgen hieronder. "
        f"Laad geen andere data: een laadaanroep buiten dit plan wordt geweigerd. Plan: {plan}"
    )


SCHEMA = {
    "type": "function",
    "function": {
        "name": TOOL_PLAN,
        "description": (
            "Alleen bij een vraag over twee of meer bronnen die je naast elkaar zet of koppelt (route 3: relatie, "
            "koppel_data): leg vóór je iets laadt het plan voor aan de gebruiker. Zoek en controleer eerst "
            "(search_catalog, dataset_details, get_cbs_dimension), en noem dan per bron de laadaanroep precies zoals "
            "je haar zou doen: de tool en haar argumenten. Na deze tool is de beurt klaar; de app toont het plan als "
            "kaart. Bevestigt de gebruiker, dan laadt de app precies deze stappen en ga je verder met relatie en "
            "koppel_data; een andere laadaanroep wordt dan geweigerd. Niet bij één bron of een vaste maat (get_maat "
            "alleen): laad die direct."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stappen": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": MAX_STAPPEN,
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "enum": sorted(LAADSTAPPEN)},
                            "argumenten": {
                                "type": "object",
                                "description": "De argumenten van die laadaanroep, zoals in het schema van de tool.",
                            },
                        },
                        "required": ["tool", "argumenten"],
                    },
                    "description": "Per bron één laadaanroep, in de volgorde waarin je laadt.",
                },
                "sleutel": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(SLEUTELS)},
                    "description": "De sleutel(s) waarop je koppelt, uit koppelbaar_via; leeg als je alleen naast elkaar zet.",
                },
            },
            "required": ["stappen"],
        },
    },
}


@dataclass
class Stand:
    """Wat één run van de plankaart weet: of er in deze run al een laadstap liep (dan is een plan te laat)."""

    geladen: bool = False


def _stap(ruw: object) -> dict | str:
    """Eén laadstap van het plan als {tool, args, key}, of de melding waarom het geen laadstap is."""
    if not isinstance(ruw, dict):
        return "elke stap is een object met `tool` en `argumenten`"
    tool, args = ruw.get("tool"), ruw.get("argumenten")
    if not isinstance(tool, str) or tool not in LAADSTAPPEN:
        return f"`{tool}` is geen laadtool; een plan noemt alleen laadstappen ({', '.join(sorted(LAADSTAPPEN))})"
    if not isinstance(args, dict):
        return f"de `argumenten` van `{tool}` zijn geen object"
    return {"tool": tool, "args": args, "key": canonieke_aanroep(tool, args)}


def _bron(stap: dict) -> str:
    """De bron achter een laadstap: de dataset, de maat of de tool zelf. Twee stappen op één bron zijn één bron."""
    args = stap["args"]
    if stap["tool"] == TOOL_GET_MAAT:
        recept = MATEN.get(str(args.get("maat")))
        return recept.dataset if recept else str(args.get("maat"))
    if stap["tool"] == TOOL_GET_RIO_DATA:
        return str(args.get("resource") or "")
    if isinstance(args.get("dataset_id"), str):
        return args["dataset_id"].strip()
    return _VASTE_DATASET.get(stap["tool"], stap["tool"])


def stappen(args: dict | None) -> list[dict] | str:
    """De laadstappen van een `plan_voorleggen`-aanroep, of de melding voor het model als het geen plan voor een kaart is.

    Een plan heeft twee tot vier laadstappen op minstens twee bronnen, en is niet alleen vaste maten: één bron of een
    vaste maat laadt direct (#1268, criterium 7)."""
    ruw = (args or {}).get("stappen")
    if not isinstance(ruw, list) or not ruw:
        return "`stappen` ontbreekt"
    uit: list[dict] = []
    for item in ruw:
        stap = _stap(item)
        if isinstance(stap, str):
            return stap
        if stap["key"] not in {s["key"] for s in uit}:
            uit.append(stap)
    if len(uit) > MAX_STAPPEN:
        return f"hoogstens {MAX_STAPPEN} laadstappen op één plan"
    if len({_bron(s).lower() for s in uit}) < 2:
        return "een plan is alleen voor een vraag over twee of meer bronnen; laad één bron direct, zonder plan"
    if all(s["tool"] == TOOL_GET_MAAT for s in uit):
        return "vaste maten laad je direct met get_maat, zonder plan"
    return uit


def sleutel(args: dict | None) -> list[str]:
    """De koppelsleutels van het plan: alleen bekende sleutelnamen, in de volgorde van de catalogus."""
    gevraagd = (args or {}).get("sleutel")
    if isinstance(gevraagd, str):
        gevraagd = [gevraagd]
    if not isinstance(gevraagd, list):
        return []
    namen = {str(n).strip().lower() for n in gevraagd}
    return [n for n in SLEUTELS if n in namen]


def afgekeurd(call: ToolCall, session: dict, stand: Stand) -> str | None:
    """De melding als deze `plan_voorleggen` geen kaart wordt; None als de beurt hier stopt voor de kaart.

    Geen kaart zonder Geavanceerd, na een bevestigd plan in deze beurt, na een laadstap in deze run (de kaart komt vóór
    het eerste laden) en voor een plan dat geen plan voor meer bronnen is. Het model gaat dan door, zonder kaart."""
    if not session.get(AAN):
        return "Fout: `plan_voorleggen` is er niet in deze sessie. Ga door zonder plan."
    if session.get(BEVESTIGD):
        return "Fout: de gebruiker heeft het plan al bevestigd; voer het uit en vraag het niet opnieuw."
    if stand.geladen:
        logger.info("PLANKAART te laat  na een laadstap, geen kaart")
        return "Fout: een plan komt vóór het eerste laden; er is al data geladen. Ga door zonder plan."
    uitkomst = stappen(call.args)
    if isinstance(uitkomst, str):
        return f"Fout: {uitkomst}."
    return None


def weigering(call: ToolCall, ronde: list[ToolCall], session: dict, stand: Stand) -> str | None:
    """De melding voor een laadaanroep die niet mag lopen; None als ze mag.

    Na een bevestigd plan mag alleen een laadstap van dat plan (dezelfde canonieke aanroep, ADR-006). En een laadstap in
    dezelfde modelronde als een plan voor de kaart loopt niet: de kaart komt vóór het eerste laden."""
    if call.name not in LAADSTAPPEN or call.args is None:
        return None
    if plan := session.get(BEVESTIGD):
        if call.key in {s["key"] for s in plan["stappen"]}:
            return None
        logger.warning("PLANKAART laadstap buiten het plan geweigerd  tool=%s", call.name)
        return (
            f"Geweigerd: deze `{call.name}`-aanroep staat niet in het plan dat de gebruiker bevestigde. Laad niets "
            "anders dan het plan; antwoord met wat geladen is, of zeg dat de gebruiker het plan kan aanpassen."
        )
    if any(c.name == TOOL_PLAN and afgekeurd(c, session, stand) is None for c in ronde):
        return "Geweigerd: eerst bevestigt de gebruiker het plan; laad nog niets."
    return None


def aanroepen(plan: dict) -> list[ToolCall]:
    """De laadstappen van een bevestigd plan als aanroepen die code doet, vóór de eerste modelronde."""
    return [
        ToolCall(f"plan-{i}", s["tool"], json.dumps(s["args"], ensure_ascii=False), s["args"])
        for i, s in enumerate(plan["stappen"])
    ]


# ── De kaart, uit code ────────────────────────────────────────────────────────


def _kort(tekst: str) -> str:
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= _MAX_WAARDE else tekst[: _MAX_WAARDE - 1].rstrip() + "…"


def _opsomming(delen: list[str]) -> str:
    return delen[0] if len(delen) == 1 else f"{', '.join(delen[:-1])} en {delen[-1]}"


def _waarde(waarde: object, labels: dict[str, str] | None = None) -> str:
    """Een argumentwaarde in woorden: een lijst als opsomming, een CBS-code met haar titel als die bekend is."""
    labels = labels or {}
    if isinstance(waarde, list):
        return _opsomming([_waarde(w, labels) for w in waarde]) if waarde else "geen"
    if isinstance(waarde, dict):
        if set(waarde) <= {"van", "tot"} and waarde:
            return f"{_waarde(waarde.get('van', '…'))} tot en met {_waarde(waarde.get('tot', '…'))}"
        return ", ".join(f"{k}: {_waarde(v, labels)}" for k, v in waarde.items())
    tekst = str(waarde).strip()
    if tekst == "*":
        return "alle waarden apart"
    return periodecode_als_label(labels.get(tekst, tekst))


def _regel(naam: str, waarde: object, labels: dict[str, str] | None = None) -> str:
    return _kort(f"{_WOORD.get(naam, naam)}: {_waarde(waarde, labels)}")


def _cbs_selectie(selectie: object, labels: dict[str, str]) -> list[str]:
    if not isinstance(selectie, dict):
        return ["de standaardselectie van de tabel"]
    regels: list[str] = []
    periode = selectie.get("periode")
    regels.append("jaren: alle jaren" if periode in (None, "*") else _regel("jaren", periode))
    if sector := selectie.get("sector"):
        regels.append(_regel("sector", sector))
    dimensies = selectie.get("dimensies")
    for dim, code in (dimensies or {}).items() if isinstance(dimensies, dict) else ():
        regels.append(_regel(str(dim), code, labels))
    if onderwerpen := selectie.get("onderwerpen"):
        regels.append(_regel("onderwerpen", onderwerpen))
    return regels


def _selectie(stap: dict, labels: dict[str, str]) -> list[str]:
    """De selectie van een laadstap in woorden: jaren, sector, instelling, vorm en wat de aanroep verder vastlegt."""
    tool, args = stap["tool"], stap["args"]
    if tool == TOOL_GET_CBS_DATA:
        return _cbs_selectie(args.get("selectie"), labels) + (
            [_regel("filters", args["filters"])] if args.get("filters") else []
        )
    regels: list[str] = []
    if tool == TOOL_GET_MAAT:
        args = {k: v for k, v in args.items() if k != "maat"}
        regels.append("jaren: alle beschikbare jaren" if not args.get("schooljaren") else "")
        regels.append("vorm: alle" if not args.get("vorm") else "")
    if tool == TOOL_GET_DUO_DATA:
        dataset = str(args.get("dataset_id") or "")
        bestand = args.get("resource")
        naam = resource_titel(dataset, bestand) if bestand is not None else None
        regels.append(_regel("bestand", naam or bestand) if bestand is not None else "bestand: het standaardbestand")
        args = {k: v for k, v in args.items() if k not in ("dataset_id", "resource")}
    if tool == TOOL_GET_RIO_DATA:
        args = {k: v for k, v in args.items() if k != "resource"}
        filters = args.pop("filters", None)
        if isinstance(filters, dict):
            regels.extend(_regel(str(k), v) for k, v in filters.items())
    args = {k: v for k, v in args.items() if k != "dataset_id"}
    regels.extend(_regel(k, v) for k, v in args.items() if v not in (None, "", [], {}))
    return [r for r in regels if r] or ["zonder verdere selectie"]


def _titel_en_dataset(stap: dict) -> tuple[str, str]:
    tool, args = stap["tool"], stap["args"]
    if tool == TOOL_GET_MAAT:
        recept = MATEN.get(str(args.get("maat")))
        if recept is None:
            return str(args.get("maat")), str(args.get("maat"))
        return bron_titel(recept.dataset), recept.dataset
    dataset = _bron(stap)
    if tool in _BRONNAAM:
        return _BRONNAAM[tool], tool
    return bron_titel(dataset), dataset


def _versie(dataset: str) -> str:
    try:
        laatste = catalogus_laatste_update(dataset)
    except Exception:
        laatste = None
    if isinstance(laatste, str) and len(laatste) >= 10:
        jaar, maand, dag = laatste[:10].split("-")
        return f"versie van {dag}-{maand}-{jaar}"
    return "de nieuwste versie bij het laden"


def _dimensielabels(steps: list[tuple[str, str]]) -> dict[str, str]:
    """Code → titel uit de get_cbs_dimension-stappen van deze beurt: zo staat er "Totaal mannen en vrouwen", geen code."""
    labels: dict[str, str] = {}
    for naam, resultaat in steps:
        if naam != TOOL_GET_CBS_DIMENSION:
            continue
        try:
            waarden = json.loads(resultaat)
        except (TypeError, ValueError):
            continue
        for code, titel in waarden.items() if isinstance(waarden, dict) else ():
            tekst = titel.get("titel") if isinstance(titel, dict) else titel
            if isinstance(tekst, str) and tekst.strip():
                labels[str(code)] = tekst.strip()
    return labels


def duur(aantal: int) -> str:
    return _DUUR.get(aantal, _DUUR_MEER)


def maak(call: ToolCall, vraag: str, steps: list[tuple[str, str]]) -> dict:
    """Het plan van deze `plan_voorleggen`-aanroep met zijn kaart, uit code; alleen na `afgekeurd(...) is None`."""
    uitkomst = stappen(call.args)
    if isinstance(uitkomst, str):
        raise ValueError(uitkomst)
    labels = _dimensielabels(steps)
    bronnen = []
    for stap in uitkomst:
        titel, dataset = _titel_en_dataset(stap)
        bronnen.append(
            {"titel": titel, "dataset": dataset, "versie": _versie(dataset), "selectie": _selectie(stap, labels)}
        )
    koppel = sleutel(call.args)
    kaart = {
        "id": uuid.uuid4().hex[:12],
        "vraag": vraag,
        "bronnen": bronnen,
        "sleutel": _opsomming(koppel) if koppel else None,
        "duur": duur(len(bronnen)),
    }
    return {"id": kaart["id"], "vraag": vraag, "stappen": uitkomst, "tool_call_id": call.id, "kaart": kaart}


def tekst(kaart: dict) -> str:
    """De kaart als één alinea: de tekst van deze beurt in het gesprek, voor het model en een heropend gesprek."""
    bronnen = _opsomming([f"{b['titel']} ({b['dataset']})" for b in kaart["bronnen"]])
    koppel = f", gekoppeld op {kaart['sleutel']}" if kaart.get("sleutel") else ", naast elkaar"
    return f"Plan voorgelegd: {bronnen}{koppel}. Duur: {kaart['duur']}."
