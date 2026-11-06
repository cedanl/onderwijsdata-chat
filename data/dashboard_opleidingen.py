"""Het dashboard Opleidingen (#957): per opleiding van een hogeschool of universiteit de cijfers uit de
Studiekeuzedatabase van het Landelijk Centrum Studiekeuze (LCSK).

Eén eindpunt, `/api/dashboard/opleidingen`, voor dezelfde instelling als Mijn instelling (`?instelling=`):

- de opleidingentabel: per opleiding (CROHO-code op een vestiging) en vorm het NSE-oordeel met respondenten naast het landelijke
  oordeel, doorstroom naar jaar 2, diplomarendement naast het landelijke rendement en numerus fixus, met de NSE-thema's
  per vorm (aantallen studenten en eerstejaars niet: daarvoor is DUO leidend, afspraken #878);
- de arbeidsmarkt van de opleidingsrichting: per opleiding de landelijke cijfers van haar SOI-rubriek;
- de numerus-fixuslijst met capaciteit, studiejaar en voertaal.

Rekenen doet `onderwijsbronnen.skdb` (`opleidingen`, `studie`, `numerus_fixus`, `jaren`), dezelfde functies als de chat
en de snippet; de export is de lading van de chat (`tools.studiekeuze._export`), dus 18 MB één keer per TTL voor beide.
Hier staat alleen wat het dashboard ervan toont: welke velden, de onzekerheidsregel van de chat
(`studiekeuze.met_onzekerheid`), de vaste teksten en het bronblok. Geen rangorde: de rijen staan op naam (art. 5 van de
leveringsvoorwaarden, docs/dashboards.md). Het taalmodel komt er niet aan te pas.
"""

from __future__ import annotations

import difflib
import logging

from onderwijsbronnen import skdb

from core import brongebruik
from core.logging_util import foutkenmerk
from tools import studiekeuze

from . import bronblok, instellingen
from .dashboard import _GEEN_SUGGESTIES, _MAX_SUGGESTIONS, BronNietBeschikbaar

logger = logging.getLogger(__name__)

BRON = "LCSK"
DATASET = "studiekeuzedatabase"  # het `_skdb_id` van het catalogusrecord, voor titel en link in het bronblok

ALLEEN_HO = (
    "De Studiekeuzedatabase heeft alleen opleidingen van hogescholen en universiteiten (hbo en wo). Voor een "
    "mbo-instelling staan er geen cijfers in."
)
NIET_IN_SKDB = "{naam} ({brin}) staat niet in de Studiekeuzedatabase: er zijn geen cijfers per opleiding."
EXPORT_NIET_BESCHIKBAAR = (
    "De Studiekeuzedatabase van LCSK is nu niet beschikbaar. Probeer het over een paar minuten opnieuw."
)
GEEN_ARBEIDSMARKT_WO_BACHELOR = (
    "Voor een wo-bachelor heeft LCSK geen arbeidsmarktcijfers: die staan bij de master waar de meeste afgestudeerden "
    "naartoe gaan."
)

# De velden van een opleidingsrij, zoals `skdb.opleidingen` ze geeft; daarna de NSE-thema's (`skdb.NSE_THEMAS`).
KOLOMMEN = (
    "opleiding",
    "croho",
    "studiecode",
    "graad",
    "soort_ho",
    "vorm",
    "plaats",
    "nse_oordeel",
    "nse_respondenten",
    "nse_oordeel_landelijk",
    "doorstroom_jaar2_pct",
    "diploma_opleiding_pct",
    "numerus_fixus_capaciteit",
    "numerus_fixus_studiejaar",
)
# De namen van de NSE-thema's op het dashboard, op het veld van het pakket.
THEMANAMEN = {
    "nse_inhoud_opzet": "Inhoud en opzet",
    "nse_docenten": "Docenten",
    "nse_toetsing": "Toetsing en beoordeling",
    "nse_begeleiding": "Studiebegeleiding",
    "nse_betrokkenheid": "Betrokkenheid en contact",
    "nse_aansluiting_beroep": "Aansluiting op het beroep",
    "nse_faciliteiten": "Studiefaciliteiten",
    "nse_sfeer": "Sfeer",
    "nse_opnieuw_kiezen": "Opnieuw kiezen",
    "nse_studiedruk": "Studiedruk",
}
# De arbeidsmarkt per opleiding: de SOI-rubriek en drie cijfers (`skdb.ARBEIDSMARKT`), en het ROA-opleidingstype: de
# sleutel naar de ROA-cijfers. De aansluiting studie-baan zelf komt uit ROA-AIS, niet uit SKDB (#878).
ARBEIDSMARKTVELDEN = (
    "soi_rubriek",
    "salaris_mediaan_bruto_maand",
    "werkloos_pct",
    "baan_op_niveau_pct",
    "roa_opleidingstype",
)
# LCSK geeft de arbeidsmarktcijfers alleen voor voltijd (studiekeuze.ARBEIDSMARKT); de andere vormen zijn leeg.
_ARBEIDSMARKTVORM = "voltijd"
_NUMERUS_FIXUS_VELDEN = ("opleiding", "croho", "vorm", "voertaal", "studiejaar", "capaciteit", "aanmelden_uiterlijk")


class StudiekeuzeNietBeschikbaar(BronNietBeschikbaar):
    """De export van LCSK laadde niet: een storing (503), geen "niet gevonden". Nooit de fouttekst zelf, die kan de
    URL of de status noemen."""

    def __init__(self) -> None:
        Exception.__init__(self, EXPORT_NIET_BESCHIKBAAR)


def _collegejaar(jaar: int | None) -> str:
    """2025 → "2025/26", zoals de dashboards een schooljaar schrijven (#847)."""
    return f"{jaar}/{(jaar + 1) % 100:02d}" if jaar else "onbekend"


def peilmoment(versie: str | None, datum: str | None, jaren: dict) -> str:
    """ "versie 26.6, export van 2026-11-06, NSE 2026, 1cijferHO 2025/26": wat het bronblok en de kop noemen."""
    delen = [
        f"versie {versie}" if versie else None,
        f"export van {datum}" if datum else None,
        f"NSE {jaren['nse']}" if jaren.get("nse") else None,
        f"1cijferHO {_collegejaar(jaren['1cijferho'])}" if jaren.get("1cijferho") else None,
    ]
    return ", ".join(d for d in delen if d)


def _uitleg(jaren: dict) -> dict[str, str]:
    """De vaste teksten bij de tabellen; de definities zijn die van de chat (tools/studiekeuze.py)."""
    nse = jaren.get("nse") or "(jaar onbekend)"
    return {
        "nse": (
            f"Gewogen gemiddelde op een schaal van 1 (zeer ontevreden) tot 5 (zeer tevreden) uit de Nationale Studenten "
            f"Enquête {nse}, met het aantal respondenten. Een oordeel op minder dan {studiekeuze.MIN_RESPONDENTEN} "
            "respondenten is onzeker. Een verschil van een paar honderdsten is geen verschil."
        ),
        "landelijk": (
            "Landelijk is het cijfer van LCSK voor dezelfde studie in dezelfde vorm over alle instellingen samen, geen "
            "gemiddelde van de rijen in deze tabel. Is de instelling de enige aanbieder, dan is landelijk deze "
            "opleiding zelf."
        ),
        "themas": (
            "Bij de NSE-thema's is het aantal respondenten per thema onbekend; het aantal bij een opleiding is dat van "
            "het algemeen oordeel."
        ),
        "aantallen": (
            "Aantallen studenten en eerstejaars staan op Mijn instelling (DUO): de Studiekeuzedatabase telt anders, "
            "daarom staan ze hier niet."
        ),
        "doorstroom": f"Doorstroom jaar 2: {studiekeuze.DOORSTROOM_JAAR2}.",
        "diplomarendement": (
            f"Diplomarendement: {studiekeuze.DIPLOMARENDEMENT}. LCSK berekent het uit 1cijferHO (collegejaar "
            f"{_collegejaar(jaren.get('1cijferho'))}, niet openbaar); het cohortjaar en de omvang van het cohort staan "
            "niet in de bron."
        ),
        "leeg": "Een leeg vak is leeg in de bron: geen cijfer, ook geen 0.",
        "volgorde": (
            "De opleidingen staan op naam: het dashboard rangschikt geen opleidingen of instellingen en geeft geen "
            "oordeel boven of onder landelijk."
        ),
        "arbeidsmarkt": (
            f"{studiekeuze.ARBEIDSMARKT} Het zijn landelijke cijfers per rubriek van voltijdafgestudeerden, niet over de "
            "eigen afgestudeerden van deze instelling."
        ),
        "numerus_fixus": studiekeuze.NUMERUS_FIXUS,
    }


def _per_studie(export: skdb.Export, studiecodes: set[int]) -> dict[tuple[int, str], dict]:
    """(studiecode, vorm) → de landelijke rij van `skdb.studie`: rendement, aanbieders en de arbeidsmarkt."""
    return {(code, r["vorm"]): r for code in sorted(studiecodes) for r in skdb.studie(export, code)}


def _opleidingsrij(rij: dict, landelijk: dict) -> dict:
    uit = {veld: rij[veld] for veld in (*KOLOMMEN, *THEMANAMEN)}
    uit["diploma_opleiding_pct_landelijk"] = landelijk.get("diploma_opleiding_pct")
    uit["aanbieders_landelijk"] = landelijk.get("aantal_opleidingen")
    return studiekeuze.met_onzekerheid(uit)


def _arbeidsmarkt(rijen: list[dict], studies: dict[tuple[int, str], dict]) -> list[dict]:
    """Per opleiding (CROHO-code) één rij: de cijfers van haar SOI-rubriek bij voltijd, of de reden dat ze leeg zijn."""
    per_croho: dict[int, dict] = {}
    for rij in rijen:
        if rij["croho"] in per_croho:
            continue
        markt = studies.get((rij["studiecode"], _ARBEIDSMARKTVORM), {})
        wo_bachelor = str(rij["soort_ho"]).upper() == "WO" and rij["graad"] == "Bachelor"
        per_croho[rij["croho"]] = {
            "opleiding": rij["opleiding"],
            "croho": rij["croho"],
            "graad": rij["graad"],
            "soort_ho": rij["soort_ho"],
            **{veld: markt.get(veld) for veld in ARBEIDSMARKTVELDEN},
            "reden_leeg": GEEN_ARBEIDSMARKT_WO_BACHELOR if wo_bachelor else None,
        }
    return list(per_croho.values())


def _tabellen(export: skdb.Export, brin: str) -> dict:
    """De drie tabellen van één instelling uit de export, en wat de kop telt."""
    rijen = skdb.opleidingen(export, brin=brin)
    studies = _per_studie(export, {r["studiecode"] for r in rijen if r["studiecode"] is not None})
    opleidingen = [_opleidingsrij(r, studies.get((r["studiecode"], r["vorm"]), {})) for r in rijen]
    fixus = [{veld: r[veld] for veld in _NUMERUS_FIXUS_VELDEN} for r in skdb.numerus_fixus(export, brin=brin)]
    return {
        "opleidingen": opleidingen,
        "arbeidsmarkt": _arbeidsmarkt(rijen, studies),
        "numerus_fixus": fixus,
        "aantallen": {
            "opleidingen": len({(r["croho"], r["plaats"]) for r in rijen}),
            "vormen": len(rijen),
            "met_nse": sum(r["nse_oordeel"] is not None for r in rijen),
            "numerus_fixus": len({(r["croho"], r["vorm"]) for r in fixus}),
        },
    }


def _export() -> tuple[skdb.Export, dict]:
    """De export van de chat (één lading per TTL) met haar jaren, gemeld voor het bronblok; laadt ze niet, dan een
    storing."""
    try:
        export = studiekeuze._export()
    except Exception as e:  # SkdbFout (ook zonder sleutel), netwerk, onverwacht
        logger.warning("dashboard-opleidingen: export niet beschikbaar: %s", foutkenmerk(e))
        logger.debug("dashboard-opleidingen: export niet beschikbaar", exc_info=e)
        raise StudiekeuzeNietBeschikbaar from None
    herkomst, jaren = export.herkomst, skdb.jaren(export)
    brongebruik.meld(
        {
            "bron": BRON,
            "dataset": DATASET,
            "versie": herkomst.versie,
            "peilmoment": peilmoment(herkomst.versie, herkomst.datum, jaren),
            # Het dashboard toont studieverloop en arbeidsmarkt: de bronregel van de weergave studie noemt beide.
            "vermelding": studiekeuze.bronregel(herkomst, jaren, "studie"),
            "opgehaald_op": herkomst.opgehaald,
        }
    )
    return export, jaren


def _niet_gevonden(instelling: str) -> dict:
    """Een naam die het register niet kent: de namen die erop lijken, zoals bij Mijn instelling (#901, #929)."""
    namen = {i["naam"].lower(): i["naam"] for i in instellingen.get_all()}
    if not namen:  # het register (DUO) laadde niet: een storing, geen onbekende naam
        raise BronNietBeschikbaar
    dichtst = difflib.get_close_matches(instelling.lower(), list(namen), n=_MAX_SUGGESTIONS, cutoff=0.5)
    uit = {"instelling": instelling, "gevonden": False, "beschikbare_instellingen": [namen[n] for n in dichtst]}
    if not dichtst:
        uit["geen_suggesties"] = _GEEN_SUGGESTIES
    return uit


def _laad(instelling: str) -> dict:
    profiel = instellingen.instellingsprofiel(instelling)
    if profiel is None:
        return _niet_gevonden(instelling)
    naam, soort, brin = profiel["naam"], profiel["sector"], str(profiel.get("instellingscode") or "")
    result: dict = {"instelling": naam, "gevonden": True, "type": soort, "brin": brin}
    if soort == "mbo":
        return {**result, "melding": ALLEEN_HO}
    export, jaren = _export()
    result.update(
        {
            "jaren": jaren,
            "min_respondenten": studiekeuze.MIN_RESPONDENTEN,
            "themas": [{"veld": veld, "naam": THEMANAMEN[veld]} for veld in skdb.NSE_THEMAS.values()],
            "uitleg": _uitleg(jaren),
        }
    )
    if brin not in {i["brin"] for i in skdb.instellingen(export)}:
        return {
            **result,
            "melding": NIET_IN_SKDB.format(naam=naam, brin=brin),
            "opleidingen": [],
            "arbeidsmarkt": [],
            "numerus_fixus": [],
        }
    return {**result, **_tabellen(export, brin)}


def load_dashboard_opleidingen(instelling: str) -> dict:
    """De payload van `/api/dashboard/opleidingen`, met het bronblok van wat de lading gebruikte (#904)."""
    with brongebruik.verzamel() as gebruikt:
        result = _laad(instelling)
    if result.get("gevonden"):
        result["bronnen"] = bronblok.blok(gebruikt)
    return result
