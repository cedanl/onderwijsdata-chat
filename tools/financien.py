"""De financiële positie van een bestuur in het mbo, hbo of wo, uit DUO's verantwoording uit XBRL (#935, besluit #725).

De bron en het rekenen staan in `onderwijsbronnen.duo.financien`: de nieuwste editie ophalen, de variant `standaard`,
het gewogen sectorcijfer van de Inspectie en de toets aan haar signaleringswaarden. Hier staat het beleid: welke
instelling bij welk bestuur hoort, de scope (alleen besturen die DUO aan mbo, hbo of wo toerekent), de afronding, de
vaste voorbehouden en de meldingen bij een wissel van variant, een fusie of een reeks die eerder stopt. Het model
rekent niets: elk getal, verschil en signaal komt uit de code.

Bestuur 40833 heeft drie verantwoordingen, één per BRIN; die blijven aparte eenheden. Een vraag over ROC van
Amsterdam (25PZ) krijgt alleen die eenheid, een vraag over bestuur 40833 alle drie, nooit een som.

Licentie: de pagina van deze bron noemt er geen, maar op de open onderwijsdata van DUO rust een CC0-verklaring. Zonder
bevestigde licentie geeft de tool op playground en productie alleen een melding (`tools.beschikbaarheid.financien`).
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
from onderwijsbronnen import Bestuurssleutel
from onderwijsbronnen.duo import financien

from core import actualiteit, brongebruik
from data import instellingen

from . import beschikbaarheid, fouten, fusies, store
from .inspectie import bestuur_van
from .schemas import TOOL_GET_BESTUURSFINANCIEN

BRONNAAM = "DUO"
# Het ID in het bron:id-contract (#912); de tabel achter een uitkomst staat onder dit ID in de store (#956).
DATASET = "duo:financien"
BRONTITEL = "Financiële verantwoording uit XBRL (variant standaard)"
LICENTIE = "CC0 1.0 (DUO, hergebruik open onderwijsdata)"
_HEADERS = {"User-Agent": "openEDUdata+ (onderwijsdata-chat)"}
_SECTOREN = {"MBO": "mbo", "HBO": "hbo", "WO": "wo"}
# De velden van een jaar waarvan een lege waarde een noot krijgt: leeg is geen nul.
_GECONTROLEERD = (*(k.sleutel for k in financien.KENGETALLEN), "rijksbijdragen")
_TWEE = Decimal("0.01")
_EEN = Decimal("0.1")

DEFINITIES = {
    ("rentabiliteit_procent" if k.sleutel == "rentabiliteit" else k.sleutel): f"{k.naam}: {k.definitie} (definitie DUO)"
    + (", in procent." if k.sleutel == "rentabiliteit" else ".")
    for k in financien.KENGETALLEN
} | {
    "rijksbijdragen_eur": (
        "Totaal van de verantwoorde rijksbijdragen in het verslagjaar, in euro; bij een universiteit met umc zonder de "
        "rijksbijdrage voor de werkplaatsfunctie, die apart staat. Verantwoord, niet toegekend."
    ),
}
VOORBEHOUDEN = (
    "Het cijfer geldt voor het hele bestuur (bevoegd gezag), niet voor één instelling, vestiging of opleiding, en ook "
    "voor de andere sectoren van dat bestuur (vo bij 18 mbo-besturen): het is niet te splitsen naar een mbo-, hbo- of "
    "wo-deel.",
    "Een financiële positie zegt niets over de kwaliteit van het onderwijs; daarover oordelen de Inspectie (mbo) en de "
    "NVAO (hbo, wo).",
    "Het verslagjaar is het boekjaar, met de stand op 31 december. Het bestuur leverde de cijfers zelf aan uit de "
    "jaarrekening; DUO heeft ze niet door een accountant laten controleren en ze kunnen afwijken van de gedrukte "
    "jaarrekening.",
    "Eén variant: standaard, dus geconsolideerd waar het bestuur dat aanleverde en anders enkelvoudig, met de variant "
    "per jaar. Varianten zijn nooit opgeteld.",
    "Een signaleringswaarde van de Inspectie is een signaal, geen oordeel. Een negatieve rentabiliteit is op zichzelf "
    "geen signaal.",
)
_NOOT = (
    "Neem de voorbehouden op in het antwoord, met het verslagjaar en de variant. Reken niets zelf: gebruik alleen de "
    "getallen, verschillen en signaleringen hieronder. Het sectorcijfer is het gewogen cijfer van de Inspectie, geen "
    "mediaan."
)
NIET_BESCHIKBAAR = (
    "De financiële verantwoording van DUO is in deze omgeving nog niet beschikbaar: DUO moet de licentie nog "
    "bevestigen. Er zijn hier geen financiële cijfers per bestuur; noem er geen en schat er geen."
)


_haler = actualiteit.Voorwaardelijk(headers=_HEADERS)


# Het dataset-ID in het bronblok van een dashboard (#935): de CKAN-naam in de catalogus, zoals de andere DUO-regels.
CATALOGUS_ID = "financien"


@actualiteit.Lading
def _bron() -> financien.Financien:
    """De nieuwste editie, een dag bewaard; daarna met If-Modified-Since opnieuw gevraagd (DUO publiceert jaarlijks).
    De editie meldt zich voor het bronblok van een dashboard (core/brongebruik.py); in de chat gaat de melding nergens
    heen."""
    data = financien.laad(_haler)
    editie = data.editie
    brongebruik.meld(
        {
            "bron": BRONNAAM,
            "dataset": CATALOGUS_ID,
            "editie": f"verslagjaren {editie.jaren}",
            "peildatum": editie.peildatum,
            "versie": editie.publicatiedatum,
            "opgehaald_op": actualiteit.nu().isoformat(),
        }
    )
    return data


def _rond(waarde: float, stap: Decimal = _TWEE, factor: int = 1) -> Decimal:
    """Half naar boven, op de decimale waarde: 0,685 wordt 0,69 (een float-afronding gaf 0,68)."""
    return (Decimal(repr(waarde)) * factor).quantize(stap, rounding=ROUND_HALF_UP)


def _vergelijking(bestuur: float | None, sector: float | None, factor: int = 1) -> dict:
    """Bestuur en sectorcijfer afgerond op twee decimalen, en het verschil van die afgeronde waarden."""
    b = None if bestuur is None else _rond(bestuur, factor=factor)
    s = None if sector is None else _rond(sector, factor=factor)
    uit: dict = {"bestuur": None if b is None else float(b), "sector": None if s is None else float(s)}
    if b is not None and s is not None:
        uit["verschil"] = float(b - s)
    return uit


def _signaleringen(regel: dict) -> list[dict]:
    uit = []
    if regel["solvabiliteit_2_onder_signaleringswaarde"]:
        uit.append(
            {
                "kengetal": "solvabiliteit_2",
                "waarde": float(_rond(regel["solvabiliteit_2"])),
                "signaleringswaarde": regel["solvabiliteit_2_signaleringswaarde"],
            }
        )
    if regel["liquiditeit_onder_signaleringswaarde"]:
        uit.append(
            {
                "kengetal": "liquiditeit",
                "waarde": float(_rond(regel["liquiditeit"])),
                "signaleringswaarde": regel["liquiditeit_signaleringswaarde"],
                "trede": regel["liquiditeit_trede"],
            }
        )
    return uit


def _jaar(regel: dict) -> dict:
    uit: dict = {"verslagjaar": regel["verslagjaar"], "variant": regel["variant"]}
    for k in ("solvabiliteit_1", "solvabiliteit_2", "liquiditeit"):
        uit[k] = _vergelijking(regel[k], regel[f"{k}_sector"])
    uit["rentabiliteit_procent"] = _vergelijking(regel["rentabiliteit"], regel["rentabiliteit_sector"], factor=100)
    rijk = regel["rijksbijdragen"]
    uit["rijksbijdragen_eur"] = None if rijk is None else round(rijk)
    uit["rijksbijdragen_mln_eur"] = None if rijk is None else float(_rond(rijk / 1e6, _EEN))
    if regel["werkplaatsfunctie"] is not None:
        uit["werkplaatsfunctie_eur"] = round(regel["werkplaatsfunctie"])
    uit["liquiditeit_signaleringswaarde"] = regel["liquiditeit_signaleringswaarde"]
    uit["signaleringen"] = _signaleringen(regel)
    return uit


def _variantwissel(regels: list[dict]) -> str | None:
    """De melding bij een reeks die van variant wisselt: een verschil rond de wissel kan door de variant komen."""
    if len({r["variant"] for r in regels}) < 2:
        return None
    stukken: list[tuple[str, int, int]] = []
    for r in regels:
        if stukken and stukken[-1][0] == r["variant"]:
            stukken[-1] = (r["variant"], stukken[-1][1], r["verslagjaar"])
        else:
            stukken.append((r["variant"], r["verslagjaar"], r["verslagjaar"]))
    delen = [f"{v} {a}" if a == b else f"{v} {a}-{b}" for v, a, b in stukken]
    return (
        f"De variant wisselt binnen de reeks ({', '.join(delen)}): een verschil rond de wissel kan door de variant "
        "komen in plaats van door de financiële positie."
    )


def _reeksgrenzen(regels: list[dict], editie: financien.Editie) -> str | None:
    eerste, laatste = regels[0]["verslagjaar"], regels[-1]["verslagjaar"]
    delen = []
    if eerste > editie.eerste_jaar:
        delen.append(f"staat pas vanaf verslagjaar {eerste} in de verantwoording")
    if laatste < editie.laatste_jaar:
        delen.append(f"staat na verslagjaar {laatste} niet meer in de verantwoording (bijvoorbeeld door een fusie)")
    return f"{regels[0]['naam']} " + " en ".join(delen) + "." if delen else None


def _eenheid(regels: list[dict], editie: financien.Editie) -> dict:
    uit: dict = {"eenheid": regels[0]["eenheid"], "naam": regels[0]["naam"], "reeks": [_jaar(r) for r in regels]}
    meldingen = [m for m in (_variantwissel(regels), _reeksgrenzen(regels, editie)) if m]
    if meldingen:
        uit["melding"] = " ".join(meldingen)
    return uit


def _eenheden(regel: dict) -> int | dict[str, int]:
    """Hoeveel eenheden in het sectorcijfer zitten: één getal, of per kengetal als een lege post er een uithield."""
    per_kengetal = {k.sleutel: regel[f"{k.sleutel}_sector_eenheden"] for k in financien.KENGETALLEN}
    return next(iter(per_kengetal.values())) if len(set(per_kengetal.values())) == 1 else per_kengetal


def _sectorcijfer(regels: list[dict]) -> dict:
    eenheden = {str(r["verslagjaar"]): _eenheden(r) for r in regels}
    return {"sector": _SECTOREN[regels[0]["sector"]], "methode": financien.SECTORMETHODE, "eenheden_per_jaar": eenheden}


def _signaleringswaarden() -> dict:
    return {
        "solvabiliteit_2": f"onder {financien.SOLVABILITEIT_2_GRENS:.2f}".replace(".", ","),
        "liquiditeit": {trede: grens for grens, trede in financien.LIQUIDITEIT_TREDEN},
        "rentabiliteit": "geen signaleringswaarde",
        "bron": financien.SIGNALERINGSWAARDEN_BRON["naam"],
        "jaar": financien.SIGNALERINGSWAARDEN_BRON["jaar"],
    }


def _bronblok(editie: financien.Editie) -> dict:
    return {
        "naam": f"{BRONNAAM}, {BRONTITEL}",
        "url": financien.PAGINA,
        "editie": f"verslagjaren {editie.jaren}",
        "peildatum": editie.peildatum,
        "versie": editie.publicatiedatum,
        "licentie": LICENTIE,
    }


def _bestuurskop(sleutel: Bestuurssleutel, regels: list[dict]) -> dict:
    return {
        "nummer": sleutel.rio_code,
        "naam": regels[0]["naam"],
        "sector": _SECTOREN[regels[0]["sector"]],
        "groepering": regels[0]["groepering"],
    }


def _geen_bestuur(profiel: dict) -> str:
    return (
        f"Voor {profiel['naam']} ({profiel['instellingscode']}) staat geen bestuur in DUO's adressenbestand: er zijn "
        "geen financiële cijfers aan te koppelen."
    )


def _buiten_verantwoording(sleutel: Bestuurssleutel, editie: financien.Editie) -> str:
    return (
        f"Bestuur {sleutel} staat niet bij de besturen die DUO aan mbo, hbo of wo toerekent in de financiële "
        f"verantwoording (verslagjaren {editie.jaren})."
    )


def _sleutel_van(profiel: dict, data: financien.Financien) -> Bestuurssleutel | None:
    """Het bestuur van een instelling uit het register, of haar eigen eenheid als het bestuur er een per BRIN heeft
    (40833); None zonder bestuur in het adressenbestand."""
    nummer = bestuur_van(profiel["instellingscode"])
    if nummer is None:
        return None
    eenheid = Bestuurssleutel(nummer, profiel["instellingscode"])
    return eenheid if data.van(eenheid) else Bestuurssleutel(nummer)


def _doel(tekst: str, data: financien.Financien) -> tuple[Bestuurssleutel, dict | None] | str:
    """Het bestuur (of de eenheid van 40833) achter een bestuursnummer, instelling of bestuursnaam; anders een melding."""
    if (sleutel := Bestuurssleutel.parse(tekst)) is not None:
        return sleutel, None
    if (profiel := instellingen.instellingsprofiel(tekst)) is not None:
        sleutel = _sleutel_van(profiel, data)
        return (sleutel, profiel) if sleutel is not None else f"{_geen_bestuur(profiel)} Noem geen cijfers."
    naam = " ".join(tekst.split()).casefold()
    if naam and (treffer := next((r for r in data.rijen if r.naam.casefold() == naam), None)):
        return treffer.sleutel, None
    return (
        f"Onbekende instelling of bestuur {tekst!r}: het register kent deze naam of alias niet, en het is geen "
        "bestuursnummer. Geen gok; controleer de naam, bijvoorbeeld met get_rio_instelling."
    )


def _sectornoot(profiel: dict | None, sector: str) -> str | None:
    """Rekent DUO het bestuur aan een andere sector toe dan de instelling heeft (Aeres Hogeschool: bestuur onder mbo)?"""
    if profiel is None or profiel.get("sector") == _SECTOREN[sector]:
        return None
    return (
        f"{profiel['naam']} is een {profiel.get('sector')}-instelling, maar DUO rekent het bestuur toe aan het "
        f"{_SECTOREN[sector]}: de cijfers gaan over het hele bestuur en het sectorcijfer is dat van het "
        f"{_SECTOREN[sector]}."
    )


def _telregel(sectorcijfer: dict) -> str:
    """Wat het sectorcijfer telt, voor het Telling-blok (#956): over hoeveel eenheden van de sector, per verslagjaar."""
    delen = []
    for jaar, n in sorted(sectorcijfer["eenheden_per_jaar"].items(), reverse=True):
        aantal = n if isinstance(n, int) else f"{min(n.values())} tot {max(n.values())} (per kengetal)"
        delen.append(f"{aantal} in {jaar}")
    return (
        f"Sectorcijfer {sectorcijfer['sector']} (DUO-verantwoording uit XBRL): het gewogen cijfer van de Inspectie over "
        f"alle eenheden van de sector ({', '.join(delen)}); een eenheid is een bestuur, bij bestuur 40833 elk van de "
        "drie verantwoordingen."
    )


def _bewaar(
    sleutel: Bestuurssleutel, regels: list[dict], editie: financien.Editie, telregel: str, fusieregels: tuple[str, ...]
) -> str:
    """De tabel achter de uitkomst in de store (#956), zoals de snippet haar maakt: de platte rijen van
    `financien.overzicht`, onafgerond. Met de laadaanroep (herladen, snippet), de editie als peilmoment en de vaste
    regels voor het Telling-blok (sectorcijfer, fusies). De key begint niet met `duo:`: de rijen zijn geen DUO-telling
    met -1 als onderdrukte cel (store.put)."""
    key = f"financien:{str(sleutel).lower()}"
    meta = store.KeyMeta(
        bron="duo",
        dataset=DATASET,
        laad=(TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": str(sleutel)}),
        peilmoment=f"editie verslagjaren {editie.jaren}, peildatum {editie.peildatum}, versie van {editie.publicatiedatum}",
        fusies=fusieregels,
        telregels=(telregel,),
    )
    store.put(key, pd.DataFrame(regels), meta)
    return key


def _kern(sleutel: Bestuurssleutel, profiel: dict | None, regels: list[dict], editie: financien.Editie) -> dict:
    """Wat de chat en het dashboard delen: per eenheid de reeks, het sectorcijfer, de definities, de signaleringswaarden,
    de voorbehouden en de bron. Een melding bij een eenheid is een feit, zonder aanwijzing aan het model."""
    per_eenheid: dict[str, list[dict]] = {}
    for r in regels:
        per_eenheid.setdefault(r["eenheid"], []).append(r)
    uit: dict = {
        "sleutel": str(sleutel),
        "dataset": DATASET,
        "bestuur": _bestuurskop(sleutel, regels),
        "eenheden": [_eenheid(rs, editie) for rs in per_eenheid.values()],
        "sectorcijfer": _sectorcijfer(regels),
        "definities": DEFINITIES,
        "signaleringswaarden": _signaleringswaarden(),
        "voorbehouden": list(VOORBEHOUDEN),
        "databewerking": [
            "Kengetallen afgerond op twee decimalen, rentabiliteit in procent; het verschil is dat van de afgeronde "
            "waarden.",
            f"Sectorcijfer: {financien.SECTORMETHODE}",
        ],
        "bron": _bronblok(editie),
    }
    if profiel is not None:
        uit["instelling"] = {"naam": profiel["naam"], "instellingscode": profiel["instellingscode"]}
    return uit


def _uitkomst(sleutel: Bestuurssleutel, profiel: dict | None, data: financien.Financien) -> dict:
    regels = financien.overzicht(data, sleutel)
    editie = data.editie
    besturen = {}
    for r in data.rijen:
        besturen[r.sleutel.nummer] = (r.naam, max(r.verslagjaar, besturen.get(r.sleutel.nummer, ("", 0))[1]))
    uit = _kern(sleutel, profiel, regels, editie)
    for eenheid in uit["eenheden"]:
        if "melding" in eenheid:
            eenheid["melding"] += " Zeg dat."
    noten = [_NOOT]
    if len(uit["eenheden"]) > 1:
        noten.append(
            "Dit bestuur staat in de verantwoording als losse eenheden, één per BRIN: geef ze apart en tel of middel "
            "ze nooit."
        )
    if sectornoot := _sectornoot(profiel, regels[0]["sector"]):
        noten.append(f"{sectornoot} Zeg dat.")
    if any(r[k] is None for r in regels for k in _GECONTROLEERD):
        noten.append("Een waarde null ontbreekt in de bron: dat is geen 0. Noem geen getal en schat er geen.")
    fusieregels = fusies.bestuur_in_reeks(
        sleutel.nummer, uit["bestuur"]["naam"], (editie.eerste_jaar, editie.laatste_jaar), besturen
    )
    uit["noot"] = " ".join([*noten, *fusieregels])
    uit["data_key"] = _bewaar(sleutel, regels, editie, _telregel(uit["sectorcijfer"]), fusieregels)
    return uit


def get_bestuursfinancien(instelling_of_bestuur: str) -> str:
    """Kengetallen en rijksbijdragen van een bestuur, met sectorcijfer, signaleringen en voorbehouden (#935)."""
    if not beschikbaarheid.financien():
        return NIET_BESCHIKBAAR
    tekst = str(instelling_of_bestuur or "").strip()
    try:
        data = _bron()
    except financien.FinancienOnbereikbaar as e:
        oorzaak = e.__cause__ if isinstance(e.__cause__, Exception) else e
        return fouten.bronfout(BRONNAAM, oorzaak, f" {financien.TITEL}.")
    except financien.FinancienAfwijkend as e:
        return fouten.melding(
            fouten.Fout.BRON_FOUT,
            f"{BRONNAAM}: de financiële verantwoording wijkt af van de bekende opbouw ({e}). Geen cijfers; noem geen "
            "schatting.",
        )
    doel = _doel(tekst, data)
    if isinstance(doel, str):
        return doel
    sleutel, profiel = doel
    if not data.van(sleutel):
        return (
            f"{_buiten_verantwoording(sleutel, data.editie)} Deze app geeft geen financiën van besturen in po of vo. "
            "Noem geen cijfers en schat er geen."
        )
    return json.dumps(_uitkomst(sleutel, profiel, data), ensure_ascii=False, separators=(",", ":"))


def _gedeeld_bestuur(sleutel: Bestuurssleutel, profiel: dict) -> str | None:
    """Welke andere instellingen uit het register onder hetzelfde bestuur vallen (Aeres, Koning Willem I College en
    BBO de Schalm): hun cijfers zijn dezelfde. Niet bij een eigen eenheid per BRIN (40833)."""
    if sleutel.brin is not None:
        return None
    andere = sorted(
        i["naam"]
        for i in instellingen.get_all()
        if i["naam"] != profiel["naam"] and bestuur_van(i["instellingscode"]) == sleutel.nummer
    )
    if not andere:
        return None
    namen = andere[0] if len(andere) == 1 else f"{', '.join(andere[:-1])} en {andere[-1]}"
    werkwoord = "valt" if len(andere) == 1 else "vallen"
    return f"Ook {namen} {werkwoord} onder dit bestuur: de cijfers gelden voor het hele bestuur, voor elk van zijn instellingen gelijk."


def voor_instelling(profiel: dict) -> dict | str:
    """De financiën van het bestuur van een instelling uit het register, voor het dashboard Mijn instelling (#935).

    Dezelfde uitkomst als de tool, als dict: zonder de noot voor het model en zonder de tabel in de store (een dashboard
    bewaart niets). `meldingen` zijn feiten voor de lezer: een sector die DUO anders toerekent, andere instellingen
    onder hetzelfde bestuur. Zonder bestuur of buiten de verantwoording een melding. Een fout van de bron gaat door: het
    dashboard noemt het onderdeel dat niet laadde. Fusies (RIO) staan er niet in: dat is een aanroep naar een tweede bron.
    """
    data = _bron()
    sleutel = _sleutel_van(profiel, data)
    if sleutel is None:
        return _geen_bestuur(profiel)
    if not data.van(sleutel):
        return _buiten_verantwoording(sleutel, data.editie)
    regels = financien.overzicht(data, sleutel)
    uit = _kern(sleutel, profiel, regels, data.editie)
    # De grens als getal, voor de stippellijn; die van de liquiditeit staat per jaar in de reeks (hangt af van de baten).
    uit["solvabiliteit_2_signaleringswaarde"] = financien.SOLVABILITEIT_2_GRENS
    uit["meldingen"] = [
        m for m in (_sectornoot(profiel, regels[0]["sector"]), _gedeeld_bestuur(sleutel, profiel)) if m is not None
    ]
    return uit
