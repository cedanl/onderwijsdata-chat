"""Opleidingen in het hbo en wo uit de Studiekeuzedatabase van het Landelijk Centrum Studiekeuze (#957).

Eén tool, vijf weergaven: per opleiding van een instelling (NSE naast landelijk, studenten, doorstroom, rendement,
numerus fixus, collegegeld), per landelijke studie (met de arbeidsmarkt van de SOI-rubriek), de numerus-fixuslijst en
de doorstroom mbo-4 → hbo en bachelor → master. De bron staat aan waar `STUDIEKEUZEDATABASE_API_KEY` gezet is
(tools/beschikbaarheid.py): test en playground.

Wat hier in code staat en niet bij het model (ADR-001, epic #191):

- de instelling wordt een BRIN-code via de export zelf of via het register (`data.instellingen`); een mbo-instelling
  krijgt een vaste melding, want de bron heeft alleen hbo en wo;
- een opleiding wordt een CROHO-code, een studiecode of een naamfilter; bij meer studies met dezelfde naam kiest de
  gebruiker, de tool gokt niet;
- elke rij komt uit `onderwijsbronnen.skdb` (dezelfde functie als de snippet); afronden, sorteren en het landelijke
  oordeel ernaast doet het pakket, niet het model;
- de verplichte bronvermelding van LCSK (met het versienummer van de export) staat in de bronregel van elke uitkomst.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

import pandas as pd
from onderwijsbronnen import skdb

from core import actualiteit, config
from data import instellingen

from . import fouten, store
from .schemas import TOOL_GET_STUDIEKEUZE

BRONNAAM = skdb.LEVERANCIER
BRONTITEL = "Studiekeuzedatabase"
# Het ID in het bron:id-contract; de tabel achter een uitkomst staat onder dit ID in de store.
DATASET = "skdb:studiekeuzedatabase"

WEERGAVEN = ("opleidingen", "studie", "numerus_fixus", "doorstroom_mbo_hbo", "doorstroom_bachelor_master")
MAX_RIJEN = 15  # rijen in het toolresultaat; de hele tabel staat in de store (data_key)
MAX_THEMARIJEN = 3  # de NSE-thema's alleen bij zo weinig rijen, anders wordt het resultaat te lang
MAX_OPTIES = 15
# Onder dit aantal respondenten markeert de tool een NSE-oordeel als onzeker (zie NSE en docs/databronnen.md).
MIN_RESPONDENTEN = 30
_BRIN = re.compile(r"^\d{2}[A-Z]{2}$")
_CODE = re.compile(r"^\d{5}$")
_MBO = ("mbo", "roc", "mbo-instelling", "mbo-instellingen")

# --- vaste zinnen ----------------------------------------------------------------------------------------------

ALLEEN_HO = (
    "De Studiekeuzedatabase heeft alleen opleidingen van hogescholen en universiteiten (hbo en wo). Voor mbo-"
    "opleidingen staat er alleen in waar mbo-4-gediplomeerden in het hbo naartoe gaan (weergave doorstroom_mbo_hbo)."
)
NSE = (
    "NSE-oordelen zijn gewogen gemiddelden op een schaal van 1 (zeer ontevreden) tot 5 (zeer tevreden) uit de "
    "Nationale Studenten Enquête {nse}; nse_respondenten is het aantal antwoorden. Een verschil van een paar "
    "honderdsten is geen verschil. Een rij met nse_onzeker: true heeft minder dan 30 respondenten: noem dat oordeel "
    "onzeker."
)
LANDELIJK = (
    "nse_oordeel_landelijk is het oordeel over dezelfde studie in dezelfde vorm over alle instellingen samen, zoals LCSK "
    "het berekent; geen gemiddelde van de rijen hierboven."
)
AANTALLEN = (
    "studenten en eerstejaars komen uit 1cijferHO (collegejaar {jaar}) en kunnen afwijken van de DUO-tellingen. "
    "doorstroom_jaar2_pct: aandeel eerstejaars dat een jaar later nog aan dezelfde opleiding staat ingeschreven; "
    "diploma_opleiding_pct: aandeel eerstejaars dat het diploma van de opleiding haalt binnen de nominale duur plus 1 "
    "jaar (voltijd en duaal) of plus 2 jaar (deeltijd). Een leeg veld is leeg in de bron: noem geen getal, ook geen 0."
)
ARBEIDSMARKT = (
    "De arbeidsmarktcijfers (salaris, werkloosheid, baan op niveau) gaan over een SOI-rubriek: een bundel verwante "
    "studies, niet deze ene studie. Ze bestaan alleen voor voltijd hbo-bachelor, associate degree en wo-master; voor "
    "een wo-bachelor staan ze bij de master waar de meeste afgestudeerden naartoe gaan."
)
RANGORDE = (
    "Dit is een rangorde op één cijfer uit de Studiekeuzedatabase. Zeg dat erbij, noem het aantal respondenten, en "
    "presenteer het niet als oordeel over de kwaliteit van een opleiding."
)
NUMERUS_FIXUS = (
    "Numerus fixus: het aantal plaatsen (capaciteit) per taaltraject en studiejaar, met loting of decentrale "
    "selectie. Bij opleidingen staat het nieuwste studiejaar, opgeteld over de taaltrajecten."
)
DOORSTROOM_MBO = (
    "Doorstroom mbo-hbo: per mbo-4-kwalificatie (beroep_id van het doorstroombestand) het aantal en aandeel "
    "gediplomeerden dat naar een hbo-studie gaat, met rang 1 voor de grootste stroom. Het aandeel is van alle "
    "gediplomeerden van die mbo-opleiding, niet van wie doorstroomt."
)
DOORSTROOM_MASTER = (
    "Doorstroom bachelor-master: het aantal en aandeel afgestudeerden van de bachelor dat naar een master gaat, met "
    "rang 1 voor de grootste stroom."
)
KOPPELEN = (
    "brin en croho zijn de codes van RIO en DUO: met BRIN-code en opleidingscode vind je dezelfde opleiding in de "
    "DUO-bestanden (inschrijvingen, diploma's) en in RIO; relatie(data_key, andere_key) toont de koppelkandidaten. "
    "studiecode is een code van LCSK en niet altijd een CROHO-code."
)
OVERNEMEN = (
    "Neem de getallen letterlijk over en reken niet zelf; elk getal staat in `rijen`. Noem de bron met de bronregel: "
    "de vermelding van LCSK is verplicht."
)
_AFGEKAPT = "Er zijn {n} rijen; hier de eerste {m}. De hele tabel staat onder data_key (query_data, create_plot)."


@dataclass(frozen=True)
class Keuze:
    """Een aanroep na controle: de weergave met de opgeloste BRIN-code en opleiding (of studie)."""

    weergave: str
    brin: str | None = None
    instelling: str | None = None  # naam, voor de uitkomst
    croho: int | None = None
    naam: str | None = None
    soort_ho: str | None = None
    graad: str | None = None
    vorm: str | None = None
    plaats: str | None = None
    mbo: str | None = None
    alleen_numerus_fixus: bool = False
    sorteer: str = "naam"

    @property
    def laadargumenten(self) -> dict:
        """De aanroep die deze keuze opnieuw maakt (herladen, snippet): de BRIN in plaats van de naam en de code in
        plaats van een zoekterm, zodat dezelfde aanroep later dezelfde selectie geeft."""
        args = {
            "weergave": self.weergave,
            "instelling": self.brin,
            "opleiding": str(self.croho) if self.croho is not None else self.naam,
            "soort_ho": self.soort_ho,
            "graad": self.graad,
            "vorm": self.vorm,
            "plaats": self.plaats,
            "mbo_opleiding": self.mbo,
            "alleen_numerus_fixus": self.alleen_numerus_fixus or None,
            "sorteer": None if self.sorteer == "naam" else self.sorteer,
        }
        return {k: v for k, v in args.items() if v is not None}


def pakketaanroep(args: dict) -> tuple[str, dict]:
    """De functie van `onderwijsbronnen.skdb` en haar argumenten bij opgeloste laadargumenten: dezelfde voor de tool en
    de snippet (tools/snippet.py), zodat die twee per constructie dezelfde rijen geven."""
    weergave = args.get("weergave", "opleidingen")
    opleiding = args.get("opleiding")
    code = int(opleiding) if opleiding and _CODE.match(str(opleiding)) else None
    naam = None if code is not None else opleiding
    if weergave == "studie":
        return "studie", {"studiecode": code}
    if weergave == "doorstroom_bachelor_master":
        return "doorstroom_bachelor_master", {"studiecode": code}
    if weergave == "doorstroom_mbo_hbo":
        return "doorstroom_mbo_hbo", {
            k: v for k, v in {"mbo": args.get("mbo_opleiding"), "studiecode": code}.items() if v
        }
    if weergave == "numerus_fixus":
        kwargs = {"brin": args.get("instelling"), "croho": code, "naam": naam}
        return "numerus_fixus", {k: v for k, v in kwargs.items() if v is not None}
    kwargs = {
        "brin": args.get("instelling"),
        "croho": code,
        "naam": naam,
        "soort_ho": args.get("soort_ho"),
        "graad": args.get("graad"),
        "vorm": args.get("vorm"),
        "plaats": args.get("plaats"),
        "alleen_numerus_fixus": args.get("alleen_numerus_fixus"),
        "sorteer": args.get("sorteer"),
    }
    return "opleidingen", {k: v for k, v in kwargs.items() if v is not None}


@actualiteit.Lading
def _export() -> skdb.Export:
    """De export van vandaag, één keer per TTL opgehaald (core/actualiteit.py); de sleutel uit core.config."""
    return skdb.lees(*skdb.haal_op(config.STUDIEKEUZEDATABASE_API_KEY))


# --- oplossen ----------------------------------------------------------------------------------------------------


def _instelling(tekst, export: skdb.Export) -> tuple[str, str] | str | None:
    """(BRIN, naam) van een hogeschool of universiteit in de export, None zonder instelling, of een vaste melding."""
    schoon = " ".join(str(tekst or "").split())
    if not schoon:
        return None
    if schoon.lower() in _MBO:
        return ALLEEN_HO
    namen = {r["brin"]: r["naam"] for r in skdb.instellingen(export)}
    if schoon.upper() in namen:
        return schoon.upper(), namen[schoon.upper()]
    profiel = instellingen.instellingsprofiel(schoon)
    if profiel is not None:
        if profiel.get("sector") == "mbo":
            return f"{profiel['naam']} is een mbo-instelling. {ALLEEN_HO}"
        brin = str(profiel.get("instellingscode") or "")
        if brin in namen:
            return brin, namen[brin]
        return f"{profiel['naam']} ({brin}) staat niet in de Studiekeuzedatabase. Noem geen cijfers."
    if _BRIN.match(schoon.upper()):
        return (
            f"BRIN-code {schoon.upper()} staat niet in de Studiekeuzedatabase (alleen hogescholen en universiteiten)."
        )
    treffers = sorted((b, n) for b, n in namen.items() if schoon.lower() in str(n).lower())
    if len(treffers) == 1:
        return treffers[0]
    if treffers:
        opties = "; ".join(f"{n} ({b})" for b, n in treffers[:MAX_OPTIES])
        return f"Meer instellingen passen bij {schoon!r}: {opties}. Vraag welke, of geef de BRIN-code. Geen gok."
    return (
        f"Onbekende instelling {schoon!r} in de Studiekeuzedatabase (109 hogescholen en universiteiten, ook "
        "niet-bekostigde). Geef de naam of BRIN-code. Geen gok."
    )


def _studie(tekst, export: skdb.Export, soort_ho, graad) -> int | str:
    """De studiecode van één landelijke studie, of een melding met de opties."""
    treffers = skdb.zoek_studies(export, str(tekst), soort_ho=soort_ho, graad=graad)
    exact = [t for t in treffers if str(t["studie"]).lower() == str(tekst).lower().strip()]
    if len(exact) == 1:
        return exact[0]["studiecode"]
    if len(treffers) == 1:
        return treffers[0]["studiecode"]
    if not treffers:
        return f"Geen studie {tekst!r} in de Studiekeuzedatabase{' met deze filters' if soort_ho or graad else ''}."
    opties = "; ".join(
        f"{t['studie']} ({t['soort_ho']} {t['graad']}, studiecode {t['studiecode']})" for t in treffers[:MAX_OPTIES]
    )
    meer = f" (en {len(treffers) - MAX_OPTIES} meer)" if len(treffers) > MAX_OPTIES else ""
    return (
        f"Meer studies passen bij {tekst!r}: {opties}{meer}. Kies er een (studiecode als opleiding) of geef soort_ho en "
        "graad mee. Geen gok."
    )


def _tekst(waarde) -> str | None:
    schoon = " ".join(str(waarde or "").split())
    return schoon or None


def _keuze(
    export: skdb.Export,
    weergave,
    instelling,
    opleiding,
    soort_ho,
    graad,
    vorm,
    plaats,
    mbo_opleiding,
    alleen_numerus_fixus,
    sorteer,
) -> Keuze | str:
    weergave = str(weergave or "opleidingen").lower()
    if weergave not in WEERGAVEN:
        return f"Weergave '{weergave}' bestaat niet: kies uit {', '.join(WEERGAVEN)}."
    sorteer = str(sorteer or "naam").lower()
    if sorteer not in skdb.SORTERINGEN:
        return f"Sorteren op '{sorteer}' kan niet: kies uit {', '.join(skdb.SORTERINGEN)}."
    soort_ho = _tekst(soort_ho)
    if soort_ho and soort_ho.lower() not in ("hbo", "wo"):
        return ALLEEN_HO if soort_ho.lower() == "mbo" else "soort_ho is 'hbo' of 'wo'."
    soort_ho = soort_ho.upper() if soort_ho else None
    graad = _tekst(graad)
    if graad and graad.lower() not in skdb.overzicht.GRADEN:
        return "graad is 'bachelor', 'master' of 'associate degree'."
    vorm = _tekst(vorm)
    if vorm and vorm.lower() not in skdb.VORMEN.values():
        return "vorm is 'voltijd', 'deeltijd' of 'duaal'."
    gevonden = _instelling(instelling, export)
    if isinstance(gevonden, str):
        return gevonden
    brin, naam_instelling = gevonden or (None, None)
    opleiding = _tekst(opleiding)
    code = int(opleiding) if opleiding and _CODE.match(opleiding) else None
    graad = graad.lower() if graad else None
    vorm = vorm.lower() if vorm else None
    if weergave in ("studie", "doorstroom_bachelor_master"):
        if not opleiding:
            return f"Weergave {weergave} vraagt een opleiding: naam of studiecode van een landelijke studie."
        graad_studie = "bachelor" if weergave == "doorstroom_bachelor_master" else graad
        studiecode = code if code is not None else _studie(opleiding, export, soort_ho, graad_studie)
        if isinstance(studiecode, str):
            return studiecode
        return Keuze(weergave=weergave, croho=studiecode, soort_ho=soort_ho, graad=graad, vorm=vorm)
    if weergave == "doorstroom_mbo_hbo":
        mbo = _tekst(mbo_opleiding)
        if not mbo and not opleiding:
            return "Weergave doorstroom_mbo_hbo vraagt een mbo_opleiding (naam of beroep_id) of een hbo-opleiding."
        studiecode = None
        if opleiding:
            studiecode = code if code is not None else _studie(opleiding, export, "HBO", None)
            if isinstance(studiecode, str):
                return studiecode
        return Keuze(weergave=weergave, croho=studiecode, mbo=mbo)
    if weergave == "opleidingen" and not (brin or opleiding or _tekst(plaats) or alleen_numerus_fixus):
        return "Geef een instelling, een opleiding of een plaats: alle 4.400 opleidingsvormen tegelijk is te veel."
    return Keuze(
        weergave=weergave,
        brin=brin,
        instelling=naam_instelling,
        soort_ho=soort_ho,
        graad=graad,
        vorm=vorm,
        croho=code,
        naam=None if code is not None else opleiding,
        plaats=_tekst(plaats),
        alleen_numerus_fixus=bool(alleen_numerus_fixus) and weergave == "opleidingen",
        sorteer=sorteer if weergave == "opleidingen" else "naam",
    )


# --- uitkomst ----------------------------------------------------------------------------------------------------


def rijen(export: skdb.Export, args: dict) -> list[dict]:
    """De rijen van een aanroep met opgeloste laadargumenten; de snippet roept dezelfde pakketfunctie aan."""
    functie, kwargs = pakketaanroep(args)
    return getattr(skdb, functie)(export, **kwargs)


def bronregel(herkomst: skdb.Herkomst) -> str:
    """'Studiekeuzedatabase 26.6, Landelijk Centrum Studiekeuze, export van 2026-11-06. Er is gebruik gemaakt …'."""
    versie = f" {herkomst.versie}" if herkomst.versie else ""
    datum = f", export van {herkomst.datum}" if herkomst.datum else ""
    return f"{BRONTITEL}{versie}, {BRONNAAM}{datum}. {skdb.VERPLICHTE_ZIN}"


def _bewaar(df: pd.DataFrame, keuze: Keuze, herkomst: skdb.Herkomst) -> str:
    args = keuze.laadargumenten
    vingerafdruk = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:8]
    key = f"skdb:{keuze.weergave}:{vingerafdruk}"
    meta = store.KeyMeta(
        bron="skdb",
        dataset=DATASET,
        laad=(TOOL_GET_STUDIEKEUZE, args),
        # De vermelding van LCSK is verplicht bij elke uiting (art. 4.1): zo staat ze ook in de kop van een CSV-export
        # en in de bronregel van een selectie op deze tabel.
        peilmoment=f"versie {herkomst.versie or 'onbekend'}; {skdb.VERPLICHTE_ZIN} ({skdb.DOCUMENTATIE})",
        instellingskolom="brin" if "brin" in df.columns else None,
        instellingen=tuple(sorted(df["brin"].dropna().unique())) if "brin" in df.columns else None,
    )
    store.put(key, df, meta)
    return key


def _voorbehouden(keuze: Keuze, export: skdb.Export) -> list[str]:
    jaren = skdb.jaren(export)
    nse = NSE.format(nse=jaren["nse"] or "(jaar onbekend)")
    collegejaar = f"{jaren['1cijferho']}-{jaren['1cijferho'] + 1}" if jaren["1cijferho"] else "onbekend"
    aantallen = AANTALLEN.format(jaar=collegejaar)
    per_weergave = {
        "opleidingen": [nse, LANDELIJK, aantallen, NUMERUS_FIXUS],
        "studie": [nse, aantallen, ARBEIDSMARKT],
        "numerus_fixus": [NUMERUS_FIXUS],
        "doorstroom_mbo_hbo": [DOORSTROOM_MBO],
        "doorstroom_bachelor_master": [DOORSTROOM_MASTER],
    }[keuze.weergave]
    if keuze.sorteer != "naam":
        per_weergave.append(RANGORDE)
    return per_weergave


def _met_onzekerheid(rij: dict) -> dict:
    """Een NSE-oordeel op minder dan MIN_RESPONDENTEN antwoorden krijgt `nse_onzeker: true`: de code markeert het, het
    model hoeft niet zelf te tellen. Alleen in het toolresultaat, niet in de tabel in de store (die is gelijk aan de
    snippet)."""
    n = rij.get("nse_respondenten")
    if rij.get("nse_oordeel") is not None and isinstance(n, int) and n < MIN_RESPONDENTEN:
        return {**rij, "nse_onzeker": True}
    return rij


def _uitkomst(alle: list[dict], keuze: Keuze, export: skdb.Export) -> dict:
    herkomst = export.herkomst
    df = pd.DataFrame(alle)
    getoond = alle[:MAX_RIJEN]
    if len(alle) > min(MAX_THEMARIJEN, MAX_RIJEN):  # thema's alleen als alles getoond wordt en het weinig is
        getoond = [{k: v for k, v in r.items() if not k.startswith("nse_") or k in _NSE_KERN} for r in getoond]
    getoond = [_met_onzekerheid(r) for r in getoond]
    uit: dict = {
        "dataset": DATASET,
        "data_key": _bewaar(df, keuze, herkomst) if alle else None,
        "weergave": keuze.weergave,
        "selectie": keuze.laadargumenten,
        "aantal_rijen": len(alle),
        "rijen": getoond,
        "voorbehouden": _voorbehouden(keuze, export),
        "koppelen": KOPPELEN,
        "instructie": OVERNEMEN,
        "bron": {
            "naam": f"{BRONNAAM}, {BRONTITEL}",
            "regel": bronregel(herkomst),
            "url": skdb.DOCUMENTATIE,
            "versie": herkomst.versie,
            "exportdatum": herkomst.datum,
        },
    }
    if keuze.instelling:
        uit["instelling"] = {"naam": keuze.instelling, "brin": keuze.brin}
    if len(alle) > MAX_RIJEN:
        uit["afgekapt"] = _AFGEKAPT.format(n=len(alle), m=MAX_RIJEN)
    if not alle:
        uit["melding"] = "Geen rijen voor deze selectie in de Studiekeuzedatabase. Noem geen getal, ook geen 0."
        uit.pop("data_key")
    return uit


_NSE_KERN = {"nse_oordeel", "nse_respondenten", "nse_oordeel_landelijk"}


def get_studiekeuze(
    weergave: str = "opleidingen",
    instelling: str | None = None,
    opleiding: str | None = None,
    soort_ho: str | None = None,
    graad: str | None = None,
    vorm: str | None = None,
    plaats: str | None = None,
    mbo_opleiding: str | None = None,
    alleen_numerus_fixus: bool = False,
    sorteer: str = "naam",
) -> str:
    """Opleidingen, studies, numerus fixus en doorstroom uit de Studiekeuzedatabase; zie de moduledocstring."""
    try:
        export = _export()
    except skdb.GeenSleutel:
        return fouten.melding(
            fouten.Fout.BRON_FOUT,
            f"{BRONNAAM}: de Studiekeuzedatabase is in deze omgeving niet beschikbaar (geen sleutel). Noem geen cijfers.",
        )
    except skdb.SkdbFout as e:
        return fouten.melding(fouten.Fout.BRON_FOUT, f"{BRONNAAM}: {e} Geen cijfers; noem geen schatting.")
    except Exception as e:  # netwerk, onverwacht
        return fouten.bronfout(BRONNAAM, e, " Studiekeuzedatabase.")
    keuze = _keuze(
        export,
        weergave,
        instelling,
        opleiding,
        soort_ho,
        graad,
        vorm,
        plaats,
        mbo_opleiding,
        alleen_numerus_fixus,
        sorteer,
    )
    if isinstance(keuze, str):
        return keuze
    alle = rijen(export, keuze.laadargumenten)
    return json.dumps(_uitkomst(alle, keuze, export), ensure_ascii=False, separators=(",", ":"), default=str)
