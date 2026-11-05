"""Personeel van de universiteiten uit het WOPI-bestand van UNL (#936): fte, of personen per leeftijd, per instelling.

Besluit 05-11 op #731: standaard **zonder** het HOOP-gebied Gezondheid (GEZO) en in **fte**; GEZO alleen op
uitdrukkelijk verzoek en nooit gemengd. De bron staat achter de vlag `ENABLE_WO_PERSONEEL` (core/config.py), alleen
aan op test, tot UNL schriftelijk bevestigt dat hergebruik mag.

Wat hier in code staat en niet bij het model (ADR-001, epic #191):

- de instelling wordt een BRIN-code via het register (`data.instellingen`), niet via het model; een hbo- of
  mbo-instelling krijgt een vaste melding zonder cijfers, net als de vier wo-instellingen die niet in WOPI staan;
- elk getal is een som over de records van de draaitabellen (`onderwijsbronnen.unl`), nooit over getoonde cellen
  met een rij "Totaal"; wetenschappelijk personeel, OBP, vast en tijdelijk en het aandeel vrouwen rekent de code uit;
- één GEZO-variant per aanroep, en die variant staat in de bronregel;
- breuken in de reeks (GEZO vóór 2006, docent en onderzoeker vóór 2005, vast/tijdelijk vóór 2003) geven een weigering
  of een vaste zin, nooit een stil afwijkend getal;
- de vaste voorbehouden (peildatum, fte is geen personen, wat niet meetelt) komen altijd mee.

De rekenstappen staan in `reken` (pandas); de snippet (tools/snippet.py) herhaalt ze op `unl.load`, en een
equivalentietest bewaakt dat de twee hetzelfde geven.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import pandas as pd
from onderwijsbronnen import unl

from core import actualiteit
from data import instellingen

from . import fouten

BRONNAAM = "Universiteiten van Nederland"
BRONTITEL = "WOPI-personeelsbestand"

UITSPLITSINGEN = ("geen", "wp_obp", "functie", "vast_tijdelijk", "geslacht", "leeftijd")
EENHEDEN = ("fte", "personen")
# Welke uitsplitsing bij welke eenheid kan: fte komt uit Tabel 1 (functie × universiteit), personen uit Tabel 9
# (leeftijd × universiteit). Personen per functie per instelling bestaan niet in het bestand.
MOGELIJK = {
    "fte": ("geen", "wp_obp", "functie", "vast_tijdelijk", "geslacht"),
    "personen": ("geen", "leeftijd", "geslacht"),
}
_TABEL = {"fte": "functie", "personen": "personen"}
# De kolom waarop een uitsplitsing groepeert; wp_obp is een afgeleide kolom (zie `reken`).
KOLOM = {"functie": "functie", "vast_tijdelijk": "aanstelling", "leeftijd": "leeftijd"}

GEZO_VANAF = 2006  # vóór 2006 gingen de medische faculteiten over naar de umc's: "incl" is daar niet vergelijkbaar
AANSTELLING_VANAF = 2003  # vast/tijdelijk bestaat vanaf 2003; daarvoor staat er "n.b."
DOCENT_ONDERZOEKER_VANAF = 2005  # OWPOW (docent) en OWPOZ (onderzoeker) bestaan vanaf 2005 (UFO)

LANDELIJK = ("", "landelijk", "nederland", "alle universiteiten", "wo", "universiteiten")
_SECTOR_HO_MBO = ("hbo", "mbo", "hogeschool", "hogescholen", "roc", "roc's", "mbo-instellingen")
_BRIN = re.compile(r"^\d{2}[A-Z]{2}$")

# Wo-instellingen in DUO die geen lid zijn van UNL en dus niet in WOPI staan (onderzoek #731 §3).
NIET_IN_WOPI = {
    "21QO": "Theologische Universiteit Apeldoorn",
    "00DV": "Protestantse Theologische Universiteit",
    "23BF": "Universiteit voor Humanistiek",
    "25AV": "Theologische Universiteit Kampen",
}

FUNCTIES = {
    "HGL": "hoogleraar",
    "UHD": "universitair hoofddocent",
    "UD": "universitair docent",
    "OWPOW": "docent",
    "OWPOZ": "onderzoeker",
    "OVWP": "overig wetenschappelijk personeel",
    "PROM": "promovendus (in dienst)",
    "OBP": "ondersteunend en beheerspersoneel",
}

# --- vaste zinnen ----------------------------------------------------------------------------------------------

PEILDATUM = (
    "Peildatum 31 december van elk jaar: personeel in dienst op die dag. Een editie verschijnt tussen mei en november "
    "van het jaar erna."
)
FTE_GEEN_PERSONEN = (
    "fte is geen aantal personen: 1 fte is een volledige werkweek (38 uur). Schrijf 'fte', nooit 'medewerkers' of "
    "'mensen'."
)
PERSONEN = (
    "Personen: elke medewerker telt één keer per universiteit (de hoofdaanstelling). Landelijk is dat de som over de "
    "universiteiten; iemand met een aanstelling bij twee universiteiten telt twee keer."
)
UITGESLOTEN = (
    "Alleen personeel in dienst van de universiteit. Niet meegeteld: inhuur, uitzendkrachten, studentassistenten, "
    "gastmedewerkers en personeel van de umc's; promovendi alleen als ze in dienst zijn (geen beurs- of buiten-"
    "promovendi)."
)
JAARVERSLAG = (
    "Een jaarverslag van een universiteit noemt vaak een ander getal (eigen afbakening, met of zonder GEZO, personen in "
    "plaats van fte). Zeg dat bij een vergelijking."
)
GEZO_UITLEG = {
    "excl": (
        "Zonder het HOOP-gebied Gezondheid (GEZO): personeel van de geneeskunde, diergeneeskunde en tandheelkunde dat "
        "bij de universiteit in dienst is, telt niet mee. Zo blijft de reeks vergelijkbaar over de tijd. Het kopcijfer "
        "van UNL is mét GEZO; die variant alleen als de gebruiker er uitdrukkelijk om vraagt."
    ),
    "incl": (
        "Met het HOOP-gebied Gezondheid (GEZO), zoals het kopcijfer van UNL. Vóór 2006 is deze variant niet "
        "vergelijkbaar: toen ging het medische personeel over naar de umc's."
    ),
}
WP = (
    "Wetenschappelijk personeel (WP) = hoogleraren, universitair hoofddocenten, universitair docenten, docenten, "
    "onderzoekers, overig wetenschappelijk personeel en promovendi in dienst; OBP = ondersteunend en beheerspersoneel. "
    "De app telt ze op uit de records."
)
LANDELIJK_UITLEG = (
    "Landelijk = de 14 universiteiten van Universiteiten van Nederland, zonder de Theologische Universiteit Apeldoorn, "
    "de Protestantse Theologische Universiteit, de Universiteit voor Humanistiek en de Theologische Universiteit Kampen "
    "(die staan niet in WOPI)."
)
GEEN_OPEN_BRON_HO_MBO = (
    "Voor hogescholen (hbo) en mbo-instellingen is er geen open bron met personeel per instelling: de Vereniging "
    "Hogescholen publiceert alleen een dashboard, en voor het mbo bestaat niets vergelijkbaars. Noem geen cijfers, "
    "schat er geen en vul niet aan met cijfers van universiteiten."
)
OVERNEMEN = (
    "Neem in het antwoord over: de eenheid, de peildatum, de GEZO-variant en de voorbehouden. Reken niet zelf: elk "
    "getal staat in `cijfers`."
)

_NOG_NIET = (
    "Uitsplitsing naar HOOP-gebied, salarisgroep of fte per leeftijd zit (nog) niet in deze tool; noem er geen cijfers "
    "voor."
)


@dataclass(frozen=True)
class Keuze:
    """Wat een aanroep opvraagt, na controle: één tabel, één GEZO-variant, één instelling (of landelijk)."""

    brin: str | None  # None = landelijk
    naam: str
    eenheid: str
    uitsplitsing: str
    gezo: str
    jaren: tuple[int, ...]

    @property
    def tabel(self) -> str:
        return _TABEL[self.eenheid]

    @property
    def maat(self) -> str:
        return unl.TABELLEN[self.tabel].maat


@actualiteit.Lading
def _wopi() -> unl.Wopi:
    """De nieuwste editie, één keer per TTL opgehaald en gelezen (core/actualiteit.py)."""
    return unl.lees(*unl.haal_op())


# --- rekenen ---------------------------------------------------------------------------------------------------


def reken(totaal: pd.DataFrame, vrouwen: pd.DataFrame | None, keuze: Keuze) -> pd.DataFrame:
    """De cijfers per jaar: een som over de records van de instelling (of alle), per groep van de uitsplitsing.

    `totaal` en `vrouwen` zijn tidy records van `unl` (één tabel, één GEZO-variant). De kolom `totaal` is altijd de som
    over de records zelf, nooit over de groepen of over een rij "Totaal".
    """
    maat = keuze.maat
    df = totaal[totaal["jaar"].isin(keuze.jaren)]
    if keuze.brin:
        df = df[df["brin"] == keuze.brin]
    uit = df.groupby("jaar")[maat].sum().rename("totaal").to_frame()
    if keuze.uitsplitsing == "wp_obp":
        groep = df["functie"].eq("OBP").map({True: "obp", False: "wetenschappelijk_personeel"})
        uit = uit.join(df.groupby(["jaar", groep])[maat].sum().unstack(fill_value=0))
    elif keuze.uitsplitsing in KOLOM:
        uit = uit.join(df.groupby(["jaar", KOLOM[keuze.uitsplitsing]])[maat].sum().unstack(fill_value=0))
    elif keuze.uitsplitsing == "geslacht" and vrouwen is not None:
        dv = vrouwen[vrouwen["jaar"].isin(keuze.jaren)]
        if keuze.brin:
            dv = dv[dv["brin"] == keuze.brin]
        uit["vrouwen"] = dv.groupby("jaar")[maat].sum()
        uit["vrouwen"] = uit["vrouwen"].fillna(0)
        uit["aandeel_vrouwen_procent"] = (100 * uit["vrouwen"] / uit["totaal"]).round(1)
    uit = uit.fillna(0).reset_index()
    waarden = [k for k in uit.columns if k not in ("jaar", "aandeel_vrouwen_procent")]
    uit[waarden] = uit[waarden].round(2) if maat == "fte" else uit[waarden].astype(int)
    return uit


# --- de instelling ---------------------------------------------------------------------------------------------


def _wopi_namen(wopi: unl.Wopi) -> dict[str, str]:
    """BRIN → naam zoals WOPI hem noemt, uit het jongste jaar."""
    rijen = wopi.rijen("functie")
    jongste = max(r["jaar"] for r in rijen)
    return {r["brin"]: r["instelling"] for r in rijen if r["jaar"] == jongste}


def _instelling(tekst: str, wopi: unl.Wopi) -> tuple[str | None, str] | str:
    """(BRIN, naam), (None, "landelijk"), of een vaste melding zonder cijfers."""
    schoon = " ".join(str(tekst or "").split())
    sleutel = schoon.lower()
    if sleutel in LANDELIJK:
        return None, "landelijk"
    if sleutel in _SECTOR_HO_MBO:
        return GEEN_OPEN_BRON_HO_MBO
    namen = _wopi_namen(wopi)
    # Het register kent namen, afkortingen en BRIN-codes; zonder register (DUO niet geladen) een BRIN-code of een naam
    # zoals WOPI of de lijst hierboven hem schrijft.
    profiel = instellingen.instellingsprofiel(schoon)
    if profiel is not None:
        if profiel.get("sector") in ("hbo", "mbo"):
            return f"{profiel['naam']} is een {profiel['sector']}-instelling. {GEEN_OPEN_BRON_HO_MBO}"
        brin, naam = profiel.get("instellingscode"), profiel["naam"]
    elif _BRIN.match(schoon.upper()):
        brin, naam = schoon.upper(), None
    else:
        brin = next((b for b, n in {**namen, **NIET_IN_WOPI}.items() if n.lower() == sleutel), None)
        naam = None
    if brin in NIET_IN_WOPI:
        return (
            f"{naam or NIET_IN_WOPI[brin]} ({brin}) is een wo-instelling, maar geen lid van Universiteiten van Nederland "
            "en staat niet in het WOPI-bestand: er zijn geen personeelscijfers. Noem geen getal, ook geen 0."
        )
    if brin in namen:
        return brin, namen[brin]
    if brin is not None:
        return (
            f"{naam or brin} ({brin}) staat niet in het WOPI-bestand: dat heeft alleen de 14 universiteiten van "
            "Universiteiten van Nederland. Noem geen getal, ook geen 0."
        )
    return (
        f"Onbekende instelling {schoon!r}. Geef de naam of BRIN-code van een van de 14 universiteiten: "
        f"{', '.join(sorted(namen.values()))}; of 'landelijk'. Geen gok."
    )


# --- jaren -----------------------------------------------------------------------------------------------------


def _beschikbaar(wopi: unl.Wopi, tabel: str, gezo: str) -> list[int]:
    return sorted({r["jaar"] for r in wopi.rijen(tabel, gezo)})


def _jaren(jaar, reeks: bool, uitsplitsing: str, gezo: str, beschikbaar: list[int]) -> tuple[int, ...] | str:
    """De jaren van de aanroep, met de breuken in de reeks als weigering of als kortere reeks."""
    vanaf = beschikbaar[0]
    if gezo == "incl":
        vanaf = max(vanaf, GEZO_VANAF)
    if uitsplitsing == "vast_tijdelijk":
        vanaf = max(vanaf, AANSTELLING_VANAF)
    if reeks:
        return tuple(j for j in beschikbaar if j >= vanaf)
    if jaar in (None, ""):
        return (beschikbaar[-1],)
    try:
        gekozen = int(jaar)
    except (TypeError, ValueError):
        return f"'{jaar}' is geen jaar. Geef een jaar als 2025 (peildatum 31-12-2025), of reeks=true."
    if gekozen not in beschikbaar:
        return (
            f"Voor {gekozen} staan geen cijfers in deze editie (beschikbaar: {beschikbaar[0]} tot en met "
            f"{beschikbaar[-1]}). Noem geen getal."
        )
    if gekozen < vanaf:
        reden = (
            "met GEZO is vóór 2006 niet vergelijkbaar (overgang van het medische personeel naar de umc's); vraag het "
            "zonder GEZO"
            if gezo == "incl" and gekozen < GEZO_VANAF
            else "vast en tijdelijk staan pas vanaf 2003 in het bestand"
        )
        return f"Voor {gekozen} geen cijfer in deze uitsplitsing: {reden}. Noem geen getal."
    return (gekozen,)


# --- uitkomst --------------------------------------------------------------------------------------------------


def bronregel(editiejaar: int, gezo: str) -> str:
    """De vaste bronregel: 'WOPI {jaar}, Universiteiten van Nederland, peildatum 31-12-{jaar}, {excl./incl.} …'."""
    return f"WOPI {editiejaar}, {BRONNAAM}, peildatum 31-12-{editiejaar}, {gezo}. sector Gezondheid"


def _noten(keuze: Keuze) -> list[str]:
    noten = []
    eerste = keuze.jaren[0]
    if keuze.uitsplitsing == "functie" and eerste < DOCENT_ONDERZOEKER_VANAF:
        noten.append(
            "Docent (OWPOW) en onderzoeker (OWPOZ) bestaan pas vanaf 2005 (functieordening UFO); daarvoor vallen ze "
            "onder de andere categorieën. Vergelijk die categorieën niet over 2005 heen."
        )
    if keuze.uitsplitsing == "vast_tijdelijk":
        noten.append(
            "Vast en tijdelijk bestaan vanaf 2003. 'onbekend' is een kleine restpost zonder aard van de aanstelling in "
            "de bron; het aandeel tijdelijk is berekend over vast plus tijdelijk."
        )
    if keuze.uitsplitsing == "geslacht":
        noten.append(
            "De bron noemt alleen het totaal en de vrouwen. Leid geen aantal mannen af (totaal min vrouwen): of er "
            "andere of onbekende geslachtscategorieën zijn, is niet bekend."
        )
    if keuze.gezo == "incl" and len(keuze.jaren) > 1:
        noten.append(f"De reeks met GEZO begint in {GEZO_VANAF}: daarvoor is hij niet vergelijkbaar.")
    if keuze.eenheid == "personen":
        noten.append("Personen per universiteit staan pas vanaf 2005 in het bestand, alleen per leeftijdsklasse.")
    return noten


def _cijfers(df: pd.DataFrame, keuze: Keuze) -> list[dict]:
    """De rijen van `reken` als JSON-waarden, met de peildatum per jaar en het aandeel tijdelijk."""
    rijen = []
    for rij in df.to_dict(orient="records"):
        jaar = int(rij.pop("jaar"))
        if keuze.uitsplitsing == "vast_tijdelijk":
            bekend = rij.get("vast", 0) + rij.get("tijdelijk", 0)
            rij["aandeel_tijdelijk_procent"] = round(100 * rij.get("tijdelijk", 0) / bekend, 1) if bekend else None
        rijen.append({"jaar": jaar, "peildatum": f"31-12-{jaar}", **rij})
    return rijen


def _uitkomst(df: pd.DataFrame, keuze: Keuze, herkomst: unl.Herkomst) -> dict:
    voorbehouden = [PEILDATUM, FTE_GEEN_PERSONEN if keuze.eenheid == "fte" else PERSONEN, UITGESLOTEN]
    voorbehouden += [GEZO_UITLEG[keuze.gezo], JAARVERSLAG]
    uit: dict = {
        "instelling": {"naam": keuze.naam, "brin": keuze.brin} if keuze.brin else "landelijk",
        "eenheid": keuze.eenheid,
        "gezo": keuze.gezo,
        "uitsplitsing": keuze.uitsplitsing,
        "cijfers": _cijfers(df, keuze),
        "voorbehouden": voorbehouden,
        "instructie": OVERNEMEN,
        "bron": {
            "naam": f"{BRONNAAM}, {BRONTITEL}",
            "regel": bronregel(herkomst.editiejaar, keuze.gezo),
            "url": unl.PAGINA,
            "bestand": herkomst.url,
            "editie": str(herkomst.editiejaar),
            "peildatum": herkomst.peildatum,
        },
    }
    if keuze.uitsplitsing in ("wp_obp", "functie"):
        uit["definitie"] = WP
    if keuze.uitsplitsing == "functie":
        uit["functies"] = FUNCTIES
    if keuze.brin is None:
        uit["landelijk"] = LANDELIJK_UITLEG
    if noten := _noten(keuze):
        uit["noot"] = " ".join(noten)
    return uit


def _keuze(instelling, jaar, reeks, uitsplitsing, eenheid, gezo, wopi: unl.Wopi) -> Keuze | str:
    eenheid = str(eenheid or "fte").lower()
    uitsplitsing = str(uitsplitsing or "geen").lower()
    gezo = str(gezo or "excl").lower()
    if gezo not in unl.GEZO:
        return "gezo is 'excl' (standaard) of 'incl': één variant per aanroep, nooit beide of gemengd."
    if eenheid not in EENHEDEN:
        return f"Eenheid '{eenheid}' bestaat niet: kies 'fte' (standaard) of 'personen'."
    if uitsplitsing not in MOGELIJK[eenheid]:
        andere = [e for e in EENHEDEN if uitsplitsing in MOGELIJK[e]]
        extra = f" Met eenheid '{andere[0]}' kan het wel." if andere else f" {_NOG_NIET}"
        return (
            f"Uitsplitsing '{uitsplitsing}' kan niet met eenheid '{eenheid}': het bestand heeft {eenheid} per "
            f"instelling alleen naar {', '.join(MOGELIJK[eenheid])}.{extra}"
        )
    gevonden = _instelling(instelling, wopi)
    if isinstance(gevonden, str):
        return gevonden
    brin, naam = gevonden
    tabel = _TABEL[eenheid]
    jaren = _jaren(jaar, bool(reeks), uitsplitsing, gezo, _beschikbaar(wopi, tabel, gezo))
    if isinstance(jaren, str):
        return jaren
    return Keuze(brin, naam, eenheid, uitsplitsing, gezo, jaren)


def get_wo_personeel(
    instelling: str = "landelijk",
    jaar: int | None = None,
    reeks: bool = False,
    uitsplitsing: str = "geen",
    eenheid: str = "fte",
    gezo: str = "excl",
) -> str:
    """Personeel van een universiteit of landelijk, uit WOPI (#936); zie de moduledocstring voor de regels."""
    try:
        wopi = _wopi()
    except unl.WopiFout as e:
        return fouten.melding(
            fouten.Fout.BRON_FOUT,
            f"{BRONNAAM}: het WOPI-bestand wijkt af van de bekende opbouw ({e}). Geen cijfers; noem geen schatting.",
        )
    except Exception as e:  # netwerk, HTTP-status
        return fouten.bronfout(BRONNAAM, e, " WOPI-personeelsbestand.")
    keuze = _keuze(instelling, jaar, reeks, uitsplitsing, eenheid, gezo, wopi)
    if isinstance(keuze, str):
        return keuze
    vrouwen = wopi.frame(keuze.tabel, keuze.gezo, "vrouwen") if keuze.uitsplitsing == "geslacht" else None
    df = reken(wopi.frame(keuze.tabel, keuze.gezo, "totaal"), vrouwen, keuze)
    return json.dumps(_uitkomst(df, keuze, wopi.herkomst), ensure_ascii=False, separators=(",", ":"))
