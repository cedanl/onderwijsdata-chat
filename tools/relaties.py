"""Relatielaag: wat hangt aan wat tussen CBS, DUO, RIO en de Studiekeuzedatabase, als tool in plaats van een gok (#63).

De sleutels zelf staan in het pakket (`onderwijsbronnen.sleutels`, #958): welke er zijn (brin, croho, crebo, gemeente,
provincie, schooljaar, …), onder welke kolomnamen ze in de bronnen staan en hoe hun waarden naar één vorm gaan
(GM0344 ↔ 344, 2021SJ00 ↔ 2021, 30020.0 ↔ 30020). Dezelfde lijst geeft de catalogus per dataset (`_sleutels`, in
search_catalog en dataset_details als `koppelbaar_via`), zodat het model een koppeling plant vóór het laadt. Hier staat
wat de chat eraan hangt: het instellingsregister (`data/instellingen.py`), de CBS-gebiedsindeling
(`data/arbeidsmarktregio.py`) en de tools die een sleutel verder brengen.

`relatie(data_key)` zegt per sleutelkolom van een geladen tabel wat eraan hangt en hoeveel waarden het register of de
indeling kent. `relatie(data_key, andere_key)` noemt de kolommen die beide tabellen als dezelfde sleutel dragen, met
kardinaliteit en overlap: kandidaten voor een koppeling. De tool koppelt zelf niets; dat blijft een expliciete stap
(query_data of run_analysis). Elke uitkomst draagt `basis` en `confidence`: handmatig vastgelegd is 1.0.
"""

import json
import logging
from dataclasses import dataclass

import pandas as pd
from onderwijsbronnen import sleutels as kern

from data import arbeidsmarktregio, instellingen

from . import fouten, store

logger = logging.getLogger(__name__)

HANDMATIG = "handmatig"
GEDETECTEERD = "gedetecteerd"
# Zoveel waarden hoogstens per kolom genormaliseerd voor dekking en overlap; genoeg voor elke bron in de chat.
_MAX_WAARDEN = 200_000

# Hoe een koppeling rijen bewaart (#962): review 08-C1/C4 verloor instellingen en opleidingen zonder match door een
# inner join en dropna. Bij elke uitkomst met koppelkandidaten, zodat het model de regel ziet op het moment dat hij koppelt.
KOPPELREGEL = (
    'Koppel met how="left" vanuit de tabel van de vraag (links) op de kolommen van één kandidaat, zodat elke rij blijft. '
    "Een rij zonder match houdt een leeg veld: noem welke rijen geen match hebben en waarom (andere bron, andere "
    "afbakening), vul nooit 0 in, en gooi geen rijen weg met dropna of een inner join op de koppelkolommen."
)

# Wat er in de chat aan een sleutel hangt: naslag en tools. De sleutels zelf staan in het pakket.
KOPPELT_AAN: dict[str, tuple[str, ...]] = {
    "brin": (
        "naam, sector, provincie en arbeidsmarktregio via het instellingsregister "
        "(DUO-adressen plus CBS-gebiedsindeling; aliassen handmatig)",
        "RIO: bestuur, instellingen en vestigingen op naam via get_rio_instelling",
    ),
    "vestiging": ("de instelling: de eerste vier tekens zijn de BRIN-code",),
    "bestuur": ("de financiële kengetallen per bestuur (get_bestuursfinancien); DUO-adressen (BEVOEGD GEZAG NUMMER)",),
    "croho": (
        "RIO opleidingserkenningen (erkendeopleidingscode in het ho)",
        "Studiekeuzedatabase (LCSK): de opleiding van een hogeschool of universiteit op BRIN plus CROHO",
    ),
    "crebo": ("RIO opleidingserkenningen (erkendeopleidingscode in het mbo); DUO mbo-bestanden",),
    "opleidingseenheid": ("RIO opleidingen, opleidingsfasen, -groepen en -onderdelen (opleidingseenheidcode)",),
    "aangeboden_opleiding": ("RIO aangeboden opleidingen en cohorten (aangebodenOpleidingcode)",),
    "gemeente": (
        "arbeidsmarktregio via de CBS-gebiedsindeling (data/arbeidsmarktregio.py)",
        "CBS RegioS als 'GM' plus vier cijfers (GM0344 is gemeente 344)",
    ),
    "provincie": ("CBS RegioS als 'PV' plus twee cijfers (PV26 is Utrecht), vaste lijst van twaalf",),
    "arbeidsmarktregio": (
        "de 35 arbeidsmarktregio's van UWV en ROA; een gemeente vertaalt via de CBS-gebiedsindeling",
    ),
    "schooljaar": ("CBS Perioden als '<startjaar>SJ00', DUO als startjaar of label 2021/2022 (tools/periode.py)",),
    "soi": ("Studiekeuzedatabase: de arbeidsmarkt van afgestudeerden per SOI-rubriek",),
    "roa_opleidingstype": ("ROA-AIS: de arbeidsmarktprognose per opleidingstype (get_roa_benchmark)",),
    "instellingsnaam": ("instellingscode via het instellingsregister (naam of alias, hoofdletterongevoelig)",),
    "gemeentenaam": (
        "gemeentenummer via dezelfde tabel, als die beide kolommen heeft; spelling kan per bron verschillen",
    ),
}


def _waarden(reeks: pd.Series, sleutel: kern.Sleutel) -> list[str]:
    """De genormaliseerde waarden van een kolom, zonder lege; begrensd."""
    uit = (sleutel.normaliseer(v) for v in reeks.head(_MAX_WAARDEN).tolist())
    return [w for w in uit if w is not None]


# Zoveel van de waarden moet minstens een regiocode van één soort zijn om de kolom als CBS-regiosleutel te lezen.
_MIN_AANDEEL_REGIOCODES = 0.5
_MET_WAARDEPATROON = tuple((s.waardepatroon, s) for s in kern.SLEUTELS.values() if s.waardepatroon is not None)


def sleutels_van(kolom: str, reeks: pd.Series) -> tuple[kern.Sleutel, ...]:
    """De sleutels van een kolom: op naam (`onderwijsbronnen.sleutels`), anders op de waarden (CBS-regiokolom).

    Een CBS-regiokolom mengt Nederland (NL), landsdelen (LD), provincies (PV), COROP-gebieden (CR) en gemeenten
    (GM). De soort met de meeste codes bepaalt de sleutel, mits dat minstens de helft van de waarden is; de
    andere regio's tellen dan niet mee in `_waarden`, dekking en overlap.
    """
    if op_naam := kern.van_kolom(kolom):
        return op_naam
    tekst = reeks.dropna().astype(str).str.strip().str.upper()
    if tekst.empty:
        return ()
    aantallen = [(int(tekst.str.fullmatch(patroon.pattern).sum()), s) for patroon, s in _MET_WAARDEPATROON]
    aantal, beste = max(aantallen, key=lambda paar: paar[0])
    return (beste,) if aantal and aantal >= _MIN_AANDEEL_REGIOCODES * len(tekst) else ()


def _dekking(sleutel: kern.Sleutel, waarden: list[str]) -> dict | None:
    """Hoeveel van de waarden het register of de indeling kent; None als er geen naslag is."""
    uniek = set(waarden)
    if not uniek:
        return None
    if sleutel.naam == "brin":
        try:
            bekend = {str(i.get("instellingscode") or "").upper() for i in instellingen.get_all()}
        except Exception as e:  # het register laadt over het netwerk; zonder register geen dekking, geen gok
            logger.warning("relatie: instellingsregister niet beschikbaar: %s", type(e).__name__)
            return None
        return {"naslag": "instellingsregister", "bekend": len(uniek & bekend), "van": len(uniek)}
    if sleutel.naam == "gemeente":
        bekend = set(arbeidsmarktregio.gemeenten())
        return {"naslag": "arbeidsmarktregio-indeling", "bekend": len(uniek & bekend), "van": len(uniek)}
    if sleutel.naam == "provincie":
        return {"naslag": "CBS-provinciecodes", "bekend": len(uniek & set(kern.PROVINCIES)), "van": len(uniek)}
    return None


@dataclass(frozen=True)
class Sleutelkolom:
    kolom: str
    sleutel: kern.Sleutel
    waarden: list[str]

    def als_dict(self) -> dict:
        uit = {
            "kolom": self.kolom,
            "sleutel": self.sleutel.naam,
            "bronnen": list(self.sleutel.bronnen),
            "koppelt_aan": list(KOPPELT_AAN[self.sleutel.naam]),
            "basis": HANDMATIG,
            "confidence": self.sleutel.confidence,
            "uniek": len(set(self.waarden)),
        }
        if (dekking := _dekking(self.sleutel, self.waarden)) is not None:
            uit["dekking"] = dekking
        return uit


def sleutelkolommen(df: pd.DataFrame) -> list[Sleutelkolom]:
    """De sleutelkolommen van een tabel, in kolomvolgorde; een kolom met meer sleutels (ERKENDEOPLEIDINGSCODE: croho
    of crebo) staat er per sleutel."""
    return [
        Sleutelkolom(str(kolom), s, _waarden(df[kolom], s))
        for kolom in df.columns
        for s in sleutels_van(str(kolom), df[kolom])
    ]


def _kardinaliteit(links: list[str], rechts: list[str]) -> str:
    een_links = len(links) == len(set(links))
    een_rechts = len(rechts) == len(set(rechts))
    return {
        (True, True): "one_to_one",
        (True, False): "one_to_many",
        (False, True): "many_to_one",
        (False, False): "many_to_many",
    }[(een_links, een_rechts)]


def _pct(deel: int, geheel: int) -> float:
    return round(100 * deel / geheel, 1) if geheel else 0.0


def koppelingen(links_key: str, links: list[Sleutelkolom], rechts_key: str, rechts: list[Sleutelkolom]) -> list[dict]:
    """Kolomparen die dezelfde sleutel dragen, met kardinaliteit en overlap van de genormaliseerde waarden."""
    uit = []
    for a in links:
        for b in rechts:
            if a.sleutel is not b.sleutel:
                continue
            la, lb = set(a.waarden), set(b.waarden)
            gedeeld = len(la & lb)
            uit.append(
                {
                    "links": {"data_key": links_key, "kolom": a.kolom},
                    "rechts": {"data_key": rechts_key, "kolom": b.kolom},
                    "sleutel": a.sleutel.naam,
                    "type": _kardinaliteit(a.waarden, b.waarden),
                    "overlap": {
                        "gedeeld": gedeeld,
                        "links_in_rechts_pct": _pct(gedeeld, len(la)),
                        "rechts_in_links_pct": _pct(gedeeld, len(lb)),
                    },
                    "basis": GEDETECTEERD if a.kolom.upper() != b.kolom.upper() else HANDMATIG,
                    "confidence": a.sleutel.confidence,
                }
            )
    return sorted(uit, key=lambda k: (-k["overlap"]["gedeeld"], k["sleutel"]))


def _tabel(data_key: str) -> pd.DataFrame | str:
    df = store.get(data_key)
    return df if isinstance(df, pd.DataFrame) else fouten.onbekende_key(data_key)


def relatie(data_key: str, andere_key: str | None = None) -> str:
    """Wat aan de sleutelkolommen van een tabel hangt, en met `andere_key` de koppelkandidaten tussen twee.

    Koppelt niets: de kandidaten gaan naar het log en naar het model, de koppeling zelf is een eigen stap.
    """
    df = _tabel(data_key)
    if isinstance(df, str):
        return df
    eigen = sleutelkolommen(df)
    met_sleutel = {s.kolom for s in eigen}
    uit: dict = {
        "data_key": data_key,
        "sleutels": [s.als_dict() for s in eigen],
        "zonder_sleutel": [str(k) for k in df.columns if str(k) not in met_sleutel],
    }
    if not eigen:
        uit["melding"] = f"Geen bekende sleutelkolom ({', '.join(kern.SLEUTELS)})."
    if andere_key is not None:
        ander = _tabel(andere_key)
        if isinstance(ander, str):
            return ander
        kandidaten = koppelingen(data_key, eigen, andere_key, sleutelkolommen(ander))
        uit["koppelingen"] = kandidaten
        if kandidaten:
            uit["koppelregel"] = KOPPELREGEL
        else:
            uit["melding_koppeling"] = (
                "Geen gedeelde sleutel tussen de twee tabellen. Koppel niet op een kolom die alleen op naam lijkt; "
                "zoek een tabel met een gedeelde sleutel of vraag per bron apart."
            )
        # Kandidaten in het log, geen waarden (#475): alleen welke sleutels en hoeveel overlap.
        logger.info(
            "RELATIE kandidaten=%d %s",
            len(kandidaten),
            " ".join(f"{k['sleutel']}:{k['type']}:{k['overlap']['gedeeld']}" for k in kandidaten),
        )
    return json.dumps(uit, ensure_ascii=False, separators=(",", ":"), default=str)
