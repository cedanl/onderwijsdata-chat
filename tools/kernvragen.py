"""Sessieloze datatools voor de kernvragen van SURF AI Chat (#708): één aanroep haalt op en rekent, zonder data_key.

Besluit 09-11 (#708): twee tools. `aantallen_per_jaar` geeft het aantal studenten, eerstejaars of inschrijvingen van
één instelling, of van één opleiding daar, per studiejaar met het verloop. `vergelijk_instellingen` legt die reeks
voor twee tot MAX_INSTELLINGEN instellingen naast elkaar, met hun volgorde in het laatste jaar dat ze allemaal hebben.

Dezelfde code als de chat (epic #191: het model kiest, de code rekent):
- de reeks is het vaste recept van `get_maat` (`maten.plan` en `maten.resultaat`): register, bestandskeuze, vorm,
  schooljaar, get_duo_data en query_data, dus ook de scopegrens, het maskeren van -1 en de fusieregels;
- per opleiding hetzelfde recept op het niveaubestand van de maat (`maten.per_opleiding`);
- het verloop is `compute_kpi` (delta en pct_change) op die reeks.
De vertaling van `telling` naar de maat volgt de sector uit het register: "studenten" is personen, zoals in de chat.

Sessieloos: de data_keys bestaan alleen binnen de aanroep en gaan niet mee naar buiten. De store is de gedeelde,
begrensde cache van read-only brondata die ook de chat gebruikt (tools/store.py); er is geen toestand per gebruiker.
Begrensd: hooguit MAX_INSTELLINGEN instellingen per vergelijking en één bestand per sector; de tijdslimiet en het
afkappen van een resultaat komen van /mcp (routes/mcp_http.py, #940).

Niet: landelijke maten (de CBS-standaardtelling hangt daar aan de vraag in het gesprek, #653), mbo per opleiding,
rapporten, exports en arbeidsmarkt.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from data import instellingen

from . import catalog, maten, periode, store
from .kpi import compute_kpi

TOOL_AANTALLEN = "aantallen_per_jaar"
TOOL_VERGELIJK = "vergelijk_instellingen"
TOOLS = (TOOL_AANTALLEN, TOOL_VERGELIJK)

STUDENTEN, EERSTEJAARS, INSCHRIJVINGEN = "studenten", "eerstejaars", "inschrijvingen"
TELLINGEN = (STUDENTEN, EERSTEJAARS, INSCHRIJVINGEN)
_HO = {STUDENTEN: maten.PERSONEN_HO, EERSTEJAARS: maten.EERSTEJAARS_HO, INSCHRIJVINGEN: maten.INSCHRIJVINGEN_HO}
# Per sector uit het register de maat van get_maat. Mbo kent per instelling alleen studenten (hoofdinschrijvingen).
_MATEN: dict[str, dict[str, str]] = {"hbo": _HO, "wo": _HO, "mbo": {STUDENTEN: maten.MBO_STUDENTEN}}
VORMEN = (maten.ALLE, "voltijd", "deeltijd", "duaal", "bol", "bbl")
# Genoeg voor een vergelijking in één antwoord; elke instelling is één selectie en hooguit één RIO-vraag naar fusies.
MAX_INSTELLINGEN = 8

# Wat get_maat naast de rijen zegt over de telling: het gaat mee, zodat het model van de client het ook ziet.
_NOTEN = ("noot", "ontbrekende_schooljaren", "databewerking", "publicatieregels", "waarschuwing")

_SCHOOLJAREN = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Schooljaren als 2024/25 (of het startjaar 2024); weglaten voor alle beschikbare.",
}
_TELLING = {
    "type": "string",
    "enum": list(TELLINGEN),
    "description": (
        "studenten (personen, standaard), eerstejaars of inschrijvingen (hoofd- én neveninschrijvingen). Eerstejaars "
        "en inschrijvingen alleen bij hbo en wo."
    ),
}
_VORM = {
    "type": "string",
    "enum": list(VORMEN),
    "description": "voltijd, deeltijd of duaal (hbo/wo) of de leerweg bol of bbl (mbo); standaard alle.",
}
_OPLEIDING = {
    "type": "string",
    "description": "Optioneel, alleen hbo/wo: naam of CROHO-code van één opleiding; dan zonder vorm.",
}
SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": TOOL_AANTALLEN,
            "description": (
                "Aantal studenten, eerstejaars of inschrijvingen van één mbo-, hbo- of wo-instelling per studiejaar "
                "(DUO, 1 oktober), of van één opleiding daar (hbo/wo), met het verloop tussen het eerste en het laatste "
                "jaar. De code kiest bestand, codes en rekenwijze, dezelfde als in de volledige app. Neem `reeks` en "
                "`verloop` letterlijk over en reken niet zelf; noem `teldefinitie` en de noten."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "instelling": {
                        "type": "string",
                        "description": "Officiële naam, gangbare afkorting of instellingscode (BRIN) van de instelling.",
                    },
                    "telling": _TELLING,
                    "opleiding": _OPLEIDING,
                    "vorm": _VORM,
                    "schooljaren": _SCHOOLJAREN,
                },
                "required": ["instelling"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_VERGELIJK,
            "description": (
                f"Vergelijk twee tot {MAX_INSTELLINGEN} instellingen: per instelling het aantal studenten, eerstejaars "
                "of inschrijvingen per studiejaar (DUO, 1 oktober) met het verloop, en de volgorde in het laatste "
                "jaar dat ze allemaal hebben. Mbo met mbo, of hbo en wo onderling; met `opleiding` dezelfde opleiding "
                "bij elke instelling. Neem de getallen letterlijk over en reken niet zelf."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "instellingen": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": MAX_INSTELLINGEN,
                        "description": "Officiële namen, afkortingen of instellingscodes (BRIN).",
                    },
                    "telling": _TELLING,
                    "opleiding": _OPLEIDING,
                    "vorm": _VORM,
                    "schooljaren": _SCHOOLJAREN,
                },
                "required": ["instellingen"],
            },
        },
    },
]


@dataclass(frozen=True)
class Uitkomst:
    """Een geslaagde aanroep: het resultaat, waar het vandaan komt en de vraag voor de link naar de volledige app."""

    resultaat: dict[str, Any]
    bewijs: dict[str, Any]
    vraag: str


@dataclass(frozen=True)
class _Reeks:
    """De reeks van één instelling, uit get_maat, met de key die alleen binnen deze aanroep bestaat."""

    instelling: dict[str, str]
    uit: dict[str, Any]
    verloop: dict[str, Any]
    fusies: tuple[str, ...] = ()

    def naar_buiten(self) -> dict[str, Any]:
        """De reeks zoals de client hem ziet: schooljaar en aantal, zonder data_key en zonder kolomnamen van DUO."""
        kolom, waarde = self.uit["periodekolom"], self.uit["waardekolom"]
        uit: dict[str, Any] = {"instelling": self.instelling}
        if opleiding := self.uit.get("opleiding"):
            uit["opleiding"] = opleiding
        uit["reeks"] = [
            {"schooljaar": periode.label(int(rij[kolom])), "aantal": rij.get(waarde)} for rij in self.uit["rijen"]
        ]
        uit["verloop"] = self.verloop
        uit |= {noot: self.uit[noot] for noot in _NOTEN if self.uit.get(noot)}
        if self.fusies:
            uit["fusies"] = list(self.fusies)
        return uit

    def recept(self) -> dict[str, Any]:
        """Het recept van get_maat, met de maat en de titel van het bestand."""
        return {"maat": self.uit["maat"], "bestandstitel": self.uit.get("bestand"), **self.uit["recept"]}


def _tekst(waarde: Any) -> str:
    return " ".join(str(waarde or "").split())


def _profiel(naam: Any) -> dict | str:
    """De instelling uit het register van de chat; onbekend is een melding, geen gok."""
    tekst = _tekst(naam)
    if not tekst:
        return "Geef de instelling: officiële naam, afkorting of instellingscode."
    profiel = instellingen.instellingsprofiel(tekst)
    if profiel is None or profiel["sector"] not in _MATEN:
        return (
            f"Onbekende instelling {tekst!r}: deze tools kennen alleen mbo-, hbo- en wo-instellingen uit het register, "
            "op officiële naam, afkorting of instellingscode. Geen gok; controleer de naam."
        )
    return profiel


def _telling(telling: Any) -> str:
    return _tekst(telling).lower() or STUDENTEN


def _maat(sector: str, telling: Any) -> tuple[str | None, str | None]:
    """(maat van get_maat, None) bij deze sector en telling, of (None, melding)."""
    telling = _telling(telling)
    if telling not in TELLINGEN:
        return None, f"Telling {telling!r} ken ik niet; kies uit {', '.join(TELLINGEN)}."
    if (maat := _MATEN[sector].get(telling)) is None:
        return None, f"Telling {telling!r}: DUO telt per {sector}-instelling alleen studenten."
    return maat, None


def _verloop(uit: dict[str, Any]) -> dict[str, Any]:
    """Verschil en procentuele verandering tussen het eerste en het laatste jaar, met compute_kpi zoals in de chat."""
    if sum(rij.get(uit["waardekolom"]) is not None for rij in uit["rijen"]) < 2:
        return {"melding": "Minder dan twee jaren met een aantal: geen verloop."}
    kpi = {
        metric: json.loads(compute_kpi(uit["data_key"], uit["waardekolom"], metric, sort_column=uit["periodekolom"]))
        for metric in ("delta", "pct_change")
    }
    if fout := next((k["fout"] for k in kpi.values() if "fout" in k), None):
        return {"melding": fout}
    delta, procent = kpi["delta"], kpi["pct_change"]
    # Een verschil tussen twee tellingen is een telling: 235, niet 235.0.
    verschil = int(delta["raw"]) if float(delta["raw"]).is_integer() else delta["raw"]
    return {**delta["periode"], "verschil": verschil, "procentuele_verandering": procent["value"]}


def _reeks(profiel: dict, telling: Any, opleiding: Any, vorm: Any, schooljaren: Any) -> _Reeks | str:
    """De reeks van één instelling, met hetzelfde plan en dezelfde uitvoering als get_maat."""
    maat, melding = _maat(profiel["sector"], telling)
    if maat is None:
        return str(melding)
    p = maten.plan(maat, profiel["naam"], vorm=_tekst(vorm).lower() or maten.ALLE, schooljaren=schooljaren)
    if isinstance(p, str):
        return p
    if gevraagd := _tekst(opleiding):
        p = maten.per_opleiding(p, gevraagd)
        if isinstance(p, str):
            return p
    tekst = maten.resultaat(p)
    try:
        uit = json.loads(tekst)
    except ValueError:
        return tekst
    if not isinstance(uit, dict) or "data_key" not in uit:
        return tekst
    known = store.meta(uit["data_key"])
    gekozen = {k: profiel[k] for k in ("naam", "instellingscode", "sector")}
    return _Reeks(gekozen, uit, _verloop(uit), known.fusies if known else ())


def _versie(keys: list[str]) -> str | None:
    """Welke versie van welk DUO-bestand: de dag waarop DUO het verving en, als riodata hem gaf, de md5."""
    versies = []
    for key in keys:
        known = store.meta(key)
        if known is None:
            continue
        delen = [f"bestand {known.resource}", known.peilmoment, f"md5 {known.bronhash}" if known.bronhash else None]
        versies.append(", ".join(d for d in delen if d))
    return "; ".join(dict.fromkeys(versies)) or None


def _verwijzing(dataset: str) -> str | None:
    details = json.loads(catalog.dataset_details(dataset))
    documentatie = details.get("documentatie") if isinstance(details, dict) else None
    return documentatie.get("url") if isinstance(documentatie, dict) else None


def _bewijs(reeksen: list[_Reeks], selectie: Any) -> dict[str, Any]:
    """Het bewijs bij #707: bron, dataset, selectie en teldefinitie; de getallen zelf staan in de reeksen."""
    dataset = reeksen[0].uit["recept"]["dataset"]
    return {
        "bron": "DUO",
        "dataset_id": dataset,
        "selectie": selectie,
        "maat": reeksen[0].uit["teldefinitie"],
        "waarde": None,
        "peildatum": None,
        "versie": _versie([str(r.uit["data_key"]) for r in reeksen]),
        "verwijzing": _verwijzing(dataset),
    }


def _waarover(telling: Any, vorm: str, opleiding: str | None) -> str:
    """ "studenten", "eerstejaars voltijd", "studenten van de opleiding B Rechtsgeleerdheid": voor de vraag in de link."""
    tekst = _telling(telling)
    if vorm != maten.ALLE:
        tekst += f" {vorm}"
    if opleiding:
        tekst += f" van de opleiding {opleiding}"
    return tekst


def aantallen_per_jaar(
    instelling: str,
    telling: str = STUDENTEN,
    opleiding: str | None = None,
    vorm: str = maten.ALLE,
    schooljaren: list | None = None,
) -> Uitkomst | str:
    """De reeks van één instelling of opleiding per studiejaar, met het verloop; een melding als tekst."""
    profiel = _profiel(instelling)
    if isinstance(profiel, str):
        return profiel
    reeks = _reeks(profiel, telling, opleiding, vorm, schooljaren)
    if isinstance(reeks, str):
        return reeks
    resultaat = {
        "telling": _telling(telling),
        "teldefinitie": reeks.uit["teldefinitie"],
        "vorm": reeks.uit["vorm"],
        **reeks.naar_buiten(),
    }
    opl = reeks.uit.get("opleiding")
    waarover = _waarover(telling, reeks.uit["vorm"], opl["naam"] if opl else None)
    vraag = f"Hoeveel {waarover} had {profiel['naam']} per studiejaar?"
    return Uitkomst(resultaat, _bewijs([reeks], reeks.recept()), vraag)


def _volgorde(reeksen: list[_Reeks]) -> dict[str, Any]:
    """De instellingen van groot naar klein in het laatste schooljaar waarin elk een aantal heeft."""
    per_jaar = [
        {r["schooljaar"]: r["aantal"] for r in reeks.naar_buiten()["reeks"] if r["aantal"] is not None}
        for reeks in reeksen
    ]
    gedeeld = set.intersection(*(set(jaren) for jaren in per_jaar))
    if not gedeeld:
        return {"melding": "Er is geen schooljaar waarin elke instelling een aantal heeft: geen volgorde."}
    jaar = max(gedeeld)  # "2025/26": het label sorteert als het startjaar
    aantallen = [jaren[jaar] for jaren in per_jaar]
    volgorde = sorted(range(len(reeksen)), key=lambda i: aantallen[i], reverse=True)
    return {
        "schooljaar": jaar,
        "instellingen": [
            {"plaats": plaats, **reeksen[i].instelling, "aantal": aantallen[i]}
            for plaats, i in enumerate(volgorde, start=1)
        ],
    }


def _gedeeld(delen: list[dict[str, Any]], sleutels: tuple[str, ...]) -> dict[str, Any]:
    """Wat in elk deel staat: in een vergelijking één keer, niet per instelling. Bij een lijst (de noten) per regel."""
    uit: dict[str, Any] = {}
    for k in sleutels:
        eerste = delen[0].get(k)
        if isinstance(eerste, list):
            if regels := [regel for regel in eerste if all(regel in (d.get(k) or ()) for d in delen)]:
                uit[k] = regels
        elif k in delen[0] and all(d.get(k) == eerste for d in delen):
            uit[k] = eerste
    return uit


def _zonder(deel: dict[str, Any], gedeeld: dict[str, Any]) -> dict[str, Any]:
    """Een deel zonder wat al gedeeld is; een lijst houdt alleen haar eigen regels."""
    uit = {}
    for k, v in deel.items():
        if isinstance(gedeeld.get(k), list) and isinstance(v, list):
            if eigen := [regel for regel in v if regel not in gedeeld[k]]:
                uit[k] = eigen
        elif k not in gedeeld:
            uit[k] = v
    return uit


def _profielen(namen: Any) -> list[dict] | str:
    """De instellingen van een vergelijking, elk één keer; een onbekende of een mix van mbo en ho is een melding."""
    if not isinstance(namen, list) or not all(isinstance(n, str) for n in namen):
        return "Geef `instellingen` als een lijst namen."
    profielen: dict[str, dict] = {}
    onbekend = []
    for naam in namen:
        profiel = _profiel(naam)
        if isinstance(profiel, str):
            onbekend.append(_tekst(naam))
        else:
            profielen.setdefault(profiel["instellingscode"], profiel)
    if onbekend:
        return (
            f"Onbekende instelling(en): {', '.join(map(repr, onbekend))}. Deze tools kennen alleen mbo-, hbo- en "
            "wo-instellingen uit het register, op officiële naam, afkorting of instellingscode. Geen gok."
        )
    if not 2 <= len(profielen) <= MAX_INSTELLINGEN:
        return f"Vergelijk twee tot {MAX_INSTELLINGEN} verschillende instellingen; dit zijn er {len(profielen)}."
    if len({p["sector"] == "mbo" for p in profielen.values()}) > 1:
        return (
            "Mbo en hbo/wo vergelijk ik niet naast elkaar: DUO telt ze in andere bestanden met een andere definitie. "
            "Vergelijk mbo met mbo, of hbo en wo onderling."
        )
    return list(profielen.values())


def vergelijk_instellingen(
    instellingen: list,
    telling: str = STUDENTEN,
    opleiding: str | None = None,
    vorm: str = maten.ALLE,
    schooljaren: list | None = None,
) -> Uitkomst | str:
    """Dezelfde reeks voor elke instelling, naast elkaar, met de volgorde in het laatste gedeelde jaar."""
    if isinstance(instellingen, list) and len(instellingen) > MAX_INSTELLINGEN:
        return f"Vergelijk hooguit {MAX_INSTELLINGEN} instellingen per aanroep; dit zijn er {len(instellingen)}."
    profielen = _profielen(instellingen)
    if isinstance(profielen, str):
        return profielen
    reeksen = []
    for profiel in profielen:
        reeks = _reeks(profiel, telling, opleiding, vorm, schooljaren)
        if isinstance(reeks, str):
            return f"{profiel['naam']}: {reeks}"
        reeksen.append(reeks)
    delen = [reeks.naar_buiten() for reeks in reeksen]
    gedeeld = _gedeeld(delen, _NOTEN)
    resultaat = {
        "telling": _telling(telling),
        "teldefinitie": reeksen[0].uit["teldefinitie"],
        "vorm": reeksen[0].uit["vorm"],
        **gedeeld,
        "instellingen": [_zonder(deel, gedeeld) for deel in delen],
        "volgorde": _volgorde(reeksen),
    }
    namen = [p["naam"] for p in profielen]
    waarover = _waarover(telling, reeksen[0].uit["vorm"], _tekst(opleiding) or None)
    vraag = f"Vergelijk het aantal {waarover} van {', '.join(namen[:-1])} en {namen[-1]} per studiejaar."
    recepten = {reeks.instelling["instellingscode"]: reeks.recept() for reeks in reeksen}
    vast = _gedeeld(list(recepten.values()), tuple(next(iter(recepten.values()))))
    selectie = {
        **vast,
        "per_instelling": {code: {k: v for k, v in r.items() if k not in vast} for code, r in recepten.items()},
    }
    return Uitkomst(resultaat, _bewijs(reeksen, selectie), vraag)


_UITVOERING: dict[str, Callable[..., Uitkomst | str]] = {
    TOOL_AANTALLEN: aantallen_per_jaar,
    TOOL_VERGELIJK: vergelijk_instellingen,
}


def voer_uit(naam: str, argumenten: dict[str, Any]) -> Uitkomst | str:
    """Een datatool met argumenten die al tegen het schema zijn getoetst (mcp_server._controleer)."""
    return _UITVOERING[naam](**argumenten)
