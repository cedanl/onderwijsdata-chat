"""Vaste koppeling van een DUO-onderdeel (hbo/wo) aan de opleidingsindeling van ROA (ONR2019), voor get_roa_benchmark (#745).

DUO deelt ho-opleidingen in naar CROHO-onderdeel (kolom ONDERDEEL: ECONOMIE, GEDRAG_EN_MAATSCHAPPIJ, ...); ROA deelt de
arbeidsmarkt in naar ONR2019: niveau (Bachelor, 'Master, doctor'), sector, subsector en opleidingstype. Sector en
subsector staan er per arbeidsmarktregio en provincie, het opleidingstype alleen landelijk. Deze tabel zegt welke
ROA-categorie bij een onderdeel hoort; de tool zoekt de cijfers erbij en het model koppelt niets zelf.

Bron en meting. Een CROHO-onderdeel en een ROA-categorie vallen niet samen: onder Natuur staan informatica-opleidingen,
die ROA bij 'techniek en ict' telt. De koppeling is daarom gemeten op DUO `overzicht-erkenningen-ho` (opgehaald
05-11-2026): de erkende opleidingen (unieke ERKENDEOPLEIDINGSCODE) met GRAAD BACHELOR of MASTER, hbo en wo samen
(ROA splitst daar niet naar), per onderdeel geteld naar ISCED-rubriek (RUBRIEKOMSCHRIJVING). Als uitloop telt een
rubriek die naar naam herkenbaar in een andere ROA-categorie van hetzelfde niveau valt: informatica, kunstmatige
intelligentie en informatiemanagement ('techniek en ict'), architectuur ('techniek en ict'), communicatie,
journalistiek en psychologie ('journalistiek, gedrag en maatschappij'), onderwijskunde en pedagogiek ('onderwijs'),
horeca, toerisme, vrije tijd en logistiek ('Bachelor - dienstverlening'), sociaal en pedagogisch werk ('Bachelor -
gezondheidszorg en welzijn'), medische techniek ('Bachelor - gezondheidszorg en welzijn'), farmacie ('Master -
gezondheidszorg') en fiscaal recht ('financieel management en fiscaal recht'). De uitloop is dus een ondergrens.

Regel. Een onderdeel hoort bij een ROA-subsector als ten hoogste 20% van zijn opleidingen aantoonbaar elders valt;
anders bij de sector erboven onder dezelfde voorwaarde; anders is het ongekoppeld en meldt de tool alleen het niveau.
Een opleidingstype krijgt een onderdeel alleen onder dezelfde voorwaarde (alleen Recht). De gemeten uitloop staat in de
toelichting en gaat mee in het toolresultaat. Opleidingsnamen koppelen we niet: daar is geen bron voor, en raden
doen we niet.

Waarom 20% (besluit 05-11, #745). De gemeten uitloop valt in twee groepen: gekoppeld 0-11% (het hoogst: Gedrag en
maatschappij-master, Landbouw-bachelor en Recht op type), niet gekoppeld vanaf 23% (Natuur, en Economie-bachelor op
subsector). Elke drempel tussen 12% en 22% geeft dus dezelfde tabel. Ruimer koppelt Natuur aan 'landbouw, wiskunde en
natuurwetenschappen', terwijl de uitloop informatica en AI is, een andere arbeidsmarkt; en de uitloop is een
ondergrens. Komt er bij een nieuwe meting een onderdeel tussen 12% en 22% uit, dan is dat een nieuw besluit.
"""

from __future__ import annotations

from dataclasses import dataclass

BACHELOR = "Bachelor"
MASTER = "Master, doctor"


@dataclass(frozen=True)
class Koppeling:
    """De ROA-categorie bij een onderdeel op één niveau; zonder categorie is het onderdeel daar niet te koppelen."""

    toelichting: str  # de gemeten uitloop, of waarom het niet koppelt
    laag: str | None = None  # 'subsector' of 'sector' (sleutel van data.arbeidsmarkt.ROA_AGGREGATIE)
    categorie: str | None = None  # de naam zoals ROA hem spelt
    opleidingstype: str | None = None  # alleen als het onderdeel ook op type eenduidig is

    def uitvoer(self) -> dict[str, str]:
        if self.categorie is None:
            return {"ongekoppeld": self.toelichting}
        type_ = {"opleidingstype": self.opleidingstype} if self.opleidingstype else {}
        return {str(self.laag): self.categorie, **type_, "kanttekening": self.toelichting}


def _sub(categorie: str, toelichting: str, opleidingstype: str | None = None) -> Koppeling:
    return Koppeling(toelichting, "subsector", categorie, opleidingstype)


_GEEN_VAKGEBIED = (
    "Niet te koppelen: Sectoroverstijgend is geen vakgebied (liberal arts and sciences, milieu, bestuur, toerisme) en "
    "heeft geen ROA-categorie."
)

# Per onderdeel en niveau: de ROA-categorie en wat de meting zei, in aantallen erkende opleidingen ("x van n").
KOPPELING: dict[str, dict[str, Koppeling]] = {
    "ECONOMIE": {
        BACHELOR: Koppeling(
            "Alleen op sector: 54 van de 220 bachelors (25%) vallen buiten 'Bachelor - economie en recht', vooral "
            "logistiek, horeca, vrije tijd en toerisme (41, ROA: 'Bachelor - dienstverlening'). Buiten de sector vallen "
            "8 (4%): informatica en architectuur ('techniek en ict').",
            "sector",
            "Bachelor - economie en maatschappij",
        ),
        MASTER: _sub(
            "Master - economie en recht",
            "Uitloop 20 van de 276 masters (7%): informatica (13, 'techniek en ict') en communicatie en journalistiek "
            "(7, 'journalistiek, gedrag en maatschappij'). Logistiek, horeca, toerisme en vrije tijd (29) hebben op "
            "masterniveau geen eigen ROA-categorie.",
        ),
    },
    "GEDRAG_EN_MAATSCHAPPIJ": {
        BACHELOR: Koppeling(
            "Niet te koppelen: de bachelors vallen uiteen over twee ROA-sectoren. Van de 65 horen sociaal en "
            "pedagogisch werk (11) bij 'Bachelor - gezondheidszorg en welzijn' en onderwijskunde en pedagogiek (4) bij "
            "'Bachelor - onderwijs' (zorg en onderwijs), de rest grotendeels bij 'journalistiek, gedrag en "
            "maatschappij' (economie en maatschappij)."
        ),
        MASTER: _sub(
            "Master - journalistiek, gedrag en maatschappij",
            "Uitloop 21 van de 193 masters (11%): onderwijskunde en pedagogiek (16, 'Master - onderwijs'), informatica "
            "en architectuur (5, 'techniek en ict'). Masters sociaal werk (19) hebben op masterniveau geen eigen "
            "ROA-categorie.",
        ),
    },
    "GEZONDHEIDSZORG": {
        BACHELOR: _sub(
            "Bachelor - gezondheidszorg en welzijn",
            "Uitloop 6 van de 69 bachelors (9%): psychologie (5, 'journalistiek, gedrag en maatschappij') en "
            "informatica (1).",
        ),
        MASTER: _sub(
            "Master - gezondheidszorg",
            "Uitloop 11 van de 146 masters (8%): psychologie (6, 'journalistiek, gedrag en maatschappij') en "
            "informatica (5, 'techniek en ict').",
        ),
    },
    "LANDBOUW_EN_NATUURLIJKE_OMGEVING": {
        BACHELOR: _sub(
            "Bachelor - landbouw, wiskunde en natuurwetenschappen",
            "Uitloop 7 van de 65 bachelors (11%): landschapsarchitectuur (4, 'techniek en ict'), communicatie en "
            "journalistiek (2) en informatica (1).",
        ),
        MASTER: _sub(
            "Master - landbouw, wiskunde en natuurwetenschappen",
            "Uitloop 3 van de 40 masters (8%): onderwijskunde, communicatie en landschapsarchitectuur.",
        ),
    },
    "NATUUR": {
        BACHELOR: Koppeling(
            "Niet te koppelen: 10 van de 44 bachelors (23%) vallen buiten 'Bachelor - landbouw, wiskunde en "
            "natuurwetenschappen', in een andere ROA-sector: informatica en kunstmatige intelligentie (9, 'techniek en "
            "ict') en psychologie (1)."
        ),
        MASTER: Koppeling(
            "Niet te koppelen: 33 van de 107 masters (31%) vallen buiten 'Master - landbouw, wiskunde en "
            "natuurwetenschappen': informatica en kunstmatige intelligentie (23, 'techniek en ict'), farmacie en "
            "medische techniek (7, 'Master - gezondheidszorg') en psychologie (3)."
        ),
    },
    "ONDERWIJS": {
        BACHELOR: _sub("Bachelor - onderwijs", "Uitloop 1 van de 80 bachelors (sociaal werk)."),
        MASTER: _sub(
            "Master - onderwijs",
            "Geen uitloop gemeten (178 masters); lerarenopleidingen en onderwijskunde vallen in dezelfde subsector, "
            "maar in verschillende opleidingstypen.",
        ),
    },
    "RECHT": {
        BACHELOR: _sub(
            "Bachelor - economie en recht",
            "Geen uitloop uit de subsector (19 bachelors). Op type vallen fiscaal recht en belastingen (2, 11%) onder "
            "'Bachelor - financieel management en fiscaal recht'.",
            "Bachelor - recht",
        ),
        MASTER: _sub(
            "Master - economie en recht",
            "Uitloop 1 van de 110 masters (informatica). Op type vallen fiscaal recht, belastingen en financieel "
            "management (12, 11%) onder 'Master - financieel management en fiscaal recht'.",
            "Master - recht",
        ),
    },
    "SECTOROVERSTIJGEND": {BACHELOR: Koppeling(_GEEN_VAKGEBIED), MASTER: Koppeling(_GEEN_VAKGEBIED)},
    "TAAL_EN_CULTUUR": {
        BACHELOR: _sub(
            "Bachelor - kunst, taal en cultuur",
            "Uitloop 2 van de 123 bachelors: communicatie en binnenhuisarchitectuur.",
        ),
        MASTER: _sub(
            "Master - kunst, taal en cultuur",
            "Uitloop 17 van de 336 masters (5%): communicatie en journalistiek (9, 'journalistiek, gedrag en "
            "maatschappij') en architectuur (8, 'techniek en ict').",
        ),
    },
    "TECHNIEK": {
        BACHELOR: _sub(
            "Bachelor - techniek en ict",
            "Uitloop 7 van de 157 bachelors (4%): medische techniek (5, 'gezondheidszorg en welzijn') en logistiek "
            "(2, 'dienstverlening').",
        ),
        MASTER: _sub("Master - techniek en ict", "Uitloop 1 van de 155 masters (medische techniek)."),
    },
}

ONDERDELEN = sorted(KOPPELING)


def onderdeel(naam: str) -> str | None:
    """Het onderdeel in de spelling van de DUO-bestanden ('Gedrag en maatschappij' → 'GEDRAG_EN_MAATSCHAPPIJ'); None
    als het geen ho-onderdeel is."""
    sleutel = "_".join(naam.replace("_", " ").split()).upper()
    return sleutel if sleutel in KOPPELING else None
