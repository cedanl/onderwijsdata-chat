"""Het schema van de Studiekeuzedatabase, uit de export zelf (#978).

Elke export van LCSK heeft twee beschrijvende tabellen: `exporttabellen` (per tabel het endpoint en een omschrijving)
en `exportkolommen` (per kolom het type en een omschrijving). Daaruit bouwt `schema()` de schemacatalogus: per tabel
de omschrijving, de kolommen met hun type, de korrel (de parameters van het endpoint), de relaties met andere tabellen,
de jaarkolommen en wat er met de tabel kan; voor de hele export de editie en wat een leeg veld betekent.

Die omschrijvingen zijn het gegevenswoordenboek van LCSK. Het valt onder de leveringsvoorwaarden (art. 11.1,
databankrechten; geen doorlevering) en staat daarom niet in deze repo: het komt alleen uit een opgehaalde export. Wat
hier wel staat, is van ons: per tabelnaam wat er met de tabel kan (`MOGELIJKHEDEN`) en welke kolommen een andere bron
leidend heeft (`ANDERE_BRON_KOLOMMEN`, afspraken #878).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .export import Export, SkdbFout
from .overzicht import jaren

# Wat er met een tabel kan.
OVERZICHT = "overzicht"  # een van de zes vaste overzichten leest haar (in de chat: een weergave van get_studiekeuze)
ANDERE_BRON = "andere_bron"  # bewust niet ondersteund: een andere bron is leidend
PAKKET = "pakket"  # alleen met `load` of `Export.frame` te lezen, zonder vast overzicht

# De zes overzichten (overzicht.py), in de volgorde van de chat.
OVERZICHTEN = ("opleidingen", "studie", "toelating", "numerus_fixus", "doorstroom_mbo_hbo", "doorstroom_bachelor_master")

GEEN_WAARDE = (
    "Een leeg veld (null) is in de export niet gevuld: de oorspronkelijke bron heeft de waarde niet (zoals de "
    "1cijferHO-velden bij een niet-bekostigde opleiding), of LCSK toont haar niet onder een drempel (te weinig "
    "respondenten of gediplomeerden). Een tekst als '(missing, data wordt op dit niveau niet getoond)' betekent "
    "hetzelfde. Het is geen 0: noem dan geen getal."
)


@dataclass(frozen=True)
class Mogelijkheid:
    """Wat er met een tabel kan: de overzichten die haar lezen, of de bron die leidend is; anders alleen het pakket."""

    overzichten: tuple[str, ...] = ()
    andere_bron: str | None = None

    @property
    def soort(self) -> str:
        if self.overzichten:
            return OVERZICHT
        return ANDERE_BRON if self.andere_bron else PAKKET

    def als_dict(self) -> dict:
        uit: dict = {"soort": self.soort}
        if self.overzichten:
            uit["overzichten"] = [o for o in OVERZICHTEN if o in self.overzichten]
        if self.andere_bron:
            uit["andere_bron"] = self.andere_bron
        return uit


_PAKKET = Mogelijkheid()

# De 45 tabellen van export 26.6 (alleen de namen). Een tabel die hier niet staat, is alleen in het pakket leesbaar. De
# overzichten per tabel toetst tests/test_skdb_schema.py tegen wat elk overzicht echt leest.
MOGELIJKHEDEN: dict[str, Mogelijkheid] = {
    "beroepenisced": _PAKKET,
    "brcberoepen": _PAKKET,
    "cijfersopleidingniveauland": Mogelijkheid(
        andere_bron=(
            "loon en uren na het ho: CBS StatLine is leidend (83815NED, 85776NED); deze cijfers zijn CBS-microdata, "
            "bewerkt door LCSK, en vormen geen reeks met StatLine"
        )
    ),
    "collegegelden": Mogelijkheid(andere_bron="het wettelijk collegegeld komt uit de wettekst, niet uit deze tabel"),
    "doorstroombachelormaster": Mogelijkheid(overzichten=("doorstroom_bachelor_master",)),
    "doorstroommbohbo": Mogelijkheid(overzichten=("doorstroom_mbo_hbo",)),
    "gemeenten": _PAKKET,
    "instellingen": Mogelijkheid(overzichten=("opleidingen", "toelating", "numerus_fixus")),
    "instellinglocaties": _PAKKET,
    "instellingopleidingen": _PAKKET,
    "instellingopleidingvormen": _PAKKET,
    "instroommomenten": _PAKKET,
    "iscedonderwijsindeling": _PAKKET,
    "iscedonderwijsindelingstudies": _PAKKET,
    "iscoberoepen": _PAKKET,
    "lotingopleidingendecentraleselecties": Mogelijkheid(overzichten=("opleidingen", "numerus_fixus")),
    "mogelijkeberoepen": _PAKKET,
    "nietwettelijkecollegegelden": _PAKKET,
    "onderwijstypen": _PAKKET,
    "opendagdoelregios": _PAKKET,
    "opendagen": _PAKKET,
    "opendaglocaties": _PAKKET,
    "opendagopleidingen": _PAKKET,
    "opendagopleidingvormen": _PAKKET,
    "opleidingen": Mogelijkheid(overzichten=("opleidingen", "toelating")),
    "opleidingvormen": Mogelijkheid(overzichten=("opleidingen", "studie")),
    "programmas": _PAKKET,
    "programmavormen": _PAKKET,
    "relatietrackvormen": _PAKKET,
    "samenwerkingen": _PAKKET,
    "soiberoepen": _PAKKET,
    "soistudievormen": _PAKKET,
    "standaardonderwijsindeling": _PAKKET,
    "standaardonderwijsindelingvorm": Mogelijkheid(overzichten=("studie",)),
    "studieadvies": _PAKKET,
    "studiekeuzechecks": _PAKKET,
    "studieopleidingen": _PAKKET,
    "studieroutes": _PAKKET,
    "studies": Mogelijkheid(overzichten=("studie", "doorstroom_bachelor_master")),
    "studievormen": Mogelijkheid(overzichten=("opleidingen", "studie")),
    "taaltoelatingseisen": _PAKKET,
    "talen": _PAKKET,
    "tracks": _PAKKET,
    "trackvormen": _PAKKET,
    "vestigingen": _PAKKET,
}

# Kolommen die SKDB overneemt van een bron die leidend is (afspraken #878, §1 "niet tonen"): ze staan in het schema met
# die bron, zonder de omschrijving van LCSK, zodat "niet beschikbaar" over de tool gaat en niet over de bron.
_DUO_TELLING = "DUO (ingeschreven studenten en eerstejaars; SKDB telt een andere populatie uit 1cijferHO)"
_DUO_ACCREDITATIE = "DUO (accreditatie per opleiding, overzicht-erkenningen-ho)"
_WETTEKST = "het wettelijk collegegeld uit de wettekst"
_CBS_LOON = "CBS StatLine (83815NED, 85776NED); dit is CBS-microdata, bewerkt door LCSK"
ANDERE_BRON_KOLOMMEN: dict[str, str] = {
    "studentenAantal": _DUO_TELLING,
    "eersteJaarAantal": _DUO_TELLING,
    "eersteJaarGemiddelde": _DUO_TELLING,
    "eersteJaarPerVestigingGemiddelde": _DUO_TELLING,
    "eersteJaarVrouwPerc": "DUO (eerstejaars naar geslacht, met aantallen)",
    "accreditatieBesluitDatum": _DUO_ACCREDITATIE,
    "uitstelAccreditatieTotDatum": _DUO_ACCREDITATIE,
    "vervallenAccreditatieDatum": _DUO_ACCREDITATIE,
    "redelijkeTermijnDatum": _DUO_ACCREDITATIE,
    "collegeGeldBedrag": _WETTEKST,
    "collegeGeldBedragMax": _WETTEKST,
    "collegeGeldBedragMin": _WETTEKST,
    "denominatie": "DUO (adressen van instellingen)",
    "inwonerAantal": "CBS StatLine (bevolking per gemeente)",
    "aansluitingStudieBaan": "ROA-AIS (de chat heeft een nieuwere editie)",
    "basisLoonMediaan": _CBS_LOON,
    "urenPerWeekGemiddelde": _CBS_LOON,
}

_PARAMETER = re.compile(r"\{(\w+)\}")
_BESCHRIJVING = ("exporttabellen", "exportkolommen")


def mogelijkheid(tabel: str) -> Mogelijkheid:
    """Wat er met deze tabel kan; een tabel die de code niet kent, is alleen in het pakket leesbaar."""
    return MOGELIJKHEDEN.get(tabel, _PAKKET)


def _beschrijving(export: Export, tabel: str) -> list[dict]:
    try:
        return export.rijen(tabel)
    except SkdbFout:
        raise SkdbFout(f"De export heeft geen {tabel}: het schema is niet te lezen.") from None


def _kolom(rij: dict) -> dict:
    kolom = {"kolom": rij.get("Kolom"), "type": rij.get("Type")}
    if (bron := ANDERE_BRON_KOLOMMEN.get(str(rij.get("Kolom")))) is not None:
        return {**kolom, "andere_bron": bron}
    return {**kolom, "omschrijving": rij.get("Omschrijving")}


def _relaties(naam: str, kolommen: set[str], korrels: dict[str, list[str]]) -> list[dict]:
    """De tabellen waarvan de hele korrel in deze tabel staat: daarop is ze te koppelen, de fijnste eerst."""
    gevonden = [(t, k) for t, k in korrels.items() if t != naam and k and set(k) <= kolommen]
    return [{"tabel": t, "via": k} for t, k in sorted(gevonden, key=lambda tk: (-len(tk[1]), tk[0]))]


def schema(export: Export) -> dict:
    """De schemacatalogus van deze export: de editie, wat een leeg veld betekent, en per tabel (op naam) de omschrijving,
    de kolommen met type, de korrel, de relaties, de jaarkolommen en wat er met de tabel kan. Een databestand zonder
    beschrijving staat er ook in (zonder omschrijving en kolommen), net als een beschreven tabel zonder databestand
    (`in_export: false`). Zonder `exporttabellen` of `exportkolommen` in de export een `SkdbFout`."""
    tabellen = {str(r.get("Tabel")): r for r in _beschrijving(export, "exporttabellen")}
    kolommen: dict[str, list[dict]] = {}
    for rij in _beschrijving(export, "exportkolommen"):
        kolommen.setdefault(str(rij.get("Tabel")), []).append(rij)
    in_export = set(export.tabellen)
    namen = sorted(set(tabellen) | set(kolommen) | in_export)
    korrels = {n: _PARAMETER.findall(str(tabellen.get(n, {}).get("Endpoint") or "")) for n in namen}
    herkomst = export.herkomst
    return {
        "editie": {"versie": herkomst.versie, "exportdatum": herkomst.datum, **jaren(export)},
        "null": GEEN_WAARDE,
        "tabellen": [
            {
                "tabel": naam,
                "omschrijving": tabellen.get(naam, {}).get("Omschrijving"),
                "endpoint": tabellen.get(naam, {}).get("Endpoint"),
                "korrel": korrels[naam],
                "kolommen": [_kolom(r) for r in kolommen.get(naam, [])],
                "jaarkolommen": [str(r["Kolom"]) for r in kolommen.get(naam, []) if str(r.get("Kolom")).endswith("Jaar")],
                "relaties": _relaties(naam, {str(r.get("Kolom")) for r in kolommen.get(naam, [])}, korrels),
                "mogelijkheid": mogelijkheid(naam).als_dict(),
                "in_export": naam in in_export,
            }
            for naam in namen
        ],
    }
