"""Productscope mbo/hbo/wo: welke CBS-, DUO- en RIO-records de chat toelaat (#355).

riodata kent per record alleen het besluit `buiten_scope`; alles zonder besluit is daar
`onbekend` (#375). Dat is geen grens: `voprognoses` kwam zo bij een mbo-vraag terecht,
en een CBS-tabel over alle onderwijssoorten gaf po/vo-cijfers (CH-03). De chat laat een
record daarom alleen toe als het aantoonbaar over mbo, hbo of wo gaat:

- `onderwijstype` noemt alleen MBO, HBO, WO of HO; of
- het ID staat in `TOEGELATEN`, met de reden waarom.

Al het andere valt erbuiten: po/so/vo, gemengde tabellen en bestanden zonder veilige
sectorselectie, en een record zonder besluit. Voor CBS en DUO geldt dezelfde regel.
De bronpackages mogen een bredere inventaris houden.

Een RIO-register over alle sectoren is alleen toegelaten als een filter de sector
vastlegt (`SECTORFILTER`); die toets doet `sectorfilter_ontbreekt` vóór elke aanroep.
Een CBS-tabel die ook over andere onderwijssoorten gaat, krijgt de selectie op mbo, hbo of wo
van de code zelf (`CBS_SECTORFILTER`): in de aanroep en nog eens op de ontvangen rijen
(`cbs_sectorselectie`).
"""

import re
from dataclasses import dataclass

from riodata import scope

from .schemas import TOOL_GET_RIO_INSTELLING

SECTOREN = frozenset({"MBO", "HBO", "WO", "HO"})

# Per RIO-register het filter dat de sector vastlegt, met de waarden die mbo/hbo/wo
# betekenen. Zonder dat filter haalt de chat het register niet op: een pagina zonder
# sectorfilter bevat ook po/vo-records.
SECTORFILTER: dict[str, tuple[str, frozenset[str]]] = {
    "aangeboden-opleidingen": (
        "type",
        frozenset(
            {
                "AANGEBODENHOOPLEIDING",
                "AANGEBODENHOOPLEIDINGSONDERDEEL",
                "AANGEBODENMBOOPLEIDING",
                "AANGEBODENMBOOPLEIDINGSONDERDEEL",
            }
        ),
    ),
    "opleidingen": (
        "opleidingseenheidtype",
        frozenset(
            {
                "HOONDERWIJSEENHEDENCLUSTER",
                "HOONDERWIJSEENHEID",
                "HOOPLEIDING",
                "MBOCERTIFICEERBAREEENHEID",
                "MBOCROSS_OVERKWALIFICATIE",
                "MBODEELKWALIFICATIE",
                "MBODOMEIN",
                "MBOGENERIEKEXAMENONDERDEEL",
                "MBOKEUZEDEEL",
                "MBOKWALIFICATIE",
                "MBOKWALIFICATIEDOSSIER",
                "MBOREGIONAALKEUZEDEEL",
                "MBOREGIONALEKWALIFICATIE",
            }
        ),
    ),
    "opleidingserkenningen": (
        "opleidingserkenningtype",
        frozenset({"HOOPLEIDINGSERKENNING", "MBOOPLEIDINGSERKENNING", "MBOGENERIEKEXAMENONDERDEELERKENNING"}),
    ),
    "onderwijslicenties": (
        "type",
        frozenset({"HOONDERWIJSLICENTIE", "MBOONDERWIJSLICENTIE", "EXAMENLICENTIE"}),
    ),
}


@dataclass(frozen=True)
class CbsSectorfilter:
    """De rijen van een CBS-tabel over meer onderwijssoorten die de chat laadt.

    `deel` zegt in woorden welk deel dat is ('mbo'; 'mbo, hbo en wo'): elke bronregel en
    melding noemt het, zodat een antwoord de tabel niet breder voorstelt dan wat geladen is.
    """

    dimensie: str
    codes: frozenset[str]
    deel: str

    def geen_rijen(self, dataset_id: str) -> str:
        """De melding als de selectie geen rijen in het profiel bevat."""
        return (
            f"Dataset '{dataset_id}' gaat ook over andere onderwijssoorten; de chat laadt alleen de rijen voor "
            f"{self.deel}, en deze selectie bevat er geen. Filter in $filter op {self.dimensie} met een code "
            f"voor {self.deel}: {sorted(self.codes)}."
        )


# CBS-tabellen die ook over andere onderwijssoorten gaan, met een dimensie die de sector
# vastlegt. get_cbs_data vraagt alleen de rijen in het profiel op en houdt na het ophalen
# ook alleen die over: geen filter van het model en geen herstelpoging kan de sector
# verbreden (CH-03). De CBS-feed gebruikt bij twee clausules op dezelfde dimensie alleen
# de eerste: op "(vo-code) and (mbo-codes)" kwamen de vo-rijen. De sectorselectie staat
# daarom vooraan. Codes uit de dimensie zelf.
_VSV_MBO = frozenset({"T001336", "A041868", "A025293", "A041773"})  # mbo totaal, bol, bbl, extranei
CBS_SECTORFILTER: dict[str, CbsSectorfilter] = {
    # Voortijdig schoolverlaten (VSV): mbo en vo.
    "85368NED": CbsSectorfilter(
        "Onderwijssoort",
        frozenset(
            {
                "A025290",  # Totaal mbo (incl. extranei)
                "A042649",
                "A042652",
                "A042651",  # entreeopleiding
                "A042655",
                "A042661",
                "A042667",  # niveau 2-4
                "A041868",
                "A025293",
                "A041773",  # bol, bbl, extranei
                "A042676",
                "A042675",
                "A042716",
                "A042715",
                "A042732",
                "A042731",
                "A041756",
                "A041757",
                "A041758",
                "A041760",
                "A041761",
                "A041762",
                "A041764",
                "A041765",
                "A041766",
            }
        ),
        "mbo",
    ),
    "85859NED": CbsSectorfilter("Onderwijssoort", _VSV_MBO, "mbo"),
    "85860NED": CbsSectorfilter("Onderwijssoort", _VSV_MBO, "mbo"),
    "85861NED": CbsSectorfilter("Onderwijssoort", _VSV_MBO, "mbo"),
    "85862NED": CbsSectorfilter("Onderwijssoort", _VSV_MBO, "mbo"),
    "84534NED": CbsSectorfilter("Onderwijssoort", _VSV_MBO, "mbo"),
    # Leerlingen en studenten, en gediplomeerden, naar woonregio: alle onderwijssoorten (#473).
    # De enige open bron voor hbo/wo naar woonregio (#452); de regio is waar de student woont,
    # niet de vestiging, en er is geen instelling. Codes gecontroleerd op 09-10-2026.
    "85701NED": CbsSectorfilter(
        "Onderwijssoort",
        frozenset(
            {
                "A041867",  # Totaal mbo (excl. extranei)
                "A042650",  # entreeopleiding
                "A042656",
                "A042662",
                "A042668",  # niveau 2-4
                "A025294",  # hbo
                "A025297",  # wo
            }
        ),
        "mbo, hbo en wo",
    ),
    "85702NED": CbsSectorfilter(
        "Onderwijssoort",
        frozenset(
            {
                "A025290",  # Totaal mbo (incl. extranei)
                "A042649",  # entreeopleiding
                "A042655",
                "A042661",
                "A042667",  # niveau 2-4
                "A028669",
                "A043049",
                "A043051",  # hbo-associate degree, -bachelor, -master/vervolgopleiding
                "A043054",
                "A043055",  # wo-bachelor, -master
            }
        ),
        "mbo, hbo en wo",
    ),
}

# Records waarvan `onderwijstype` de sector niet noemt ('Allen', 'Arbeidsmarkt') of
# meer sectoren omvat. Een nieuw record zonder besluit hier valt erbuiten.
TOEGELATEN: dict[str, str] = {
    # DUO labelt deze mbo-bestanden als 'Allen'.
    "mbo-studenten-per-instelling": "mbo-bestand; DUO labelt het als 'Allen'",
    "mbo-studenten-per-sectorkamer-en-leerweg": "mbo-bestand; DUO labelt het als 'Allen'",
    "instromende-mbo-studenten": "mbo-bestand; DUO labelt het als 'Allen'",
    "gediplomeerde-mbo-studenten": "mbo-bestand; DUO labelt het als 'Allen'",
    # CBS labelt deze ho-tabel als 'Allen'.
    "71229ned": "CBS-tabel over afgestudeerden uit het ho; CBS labelt hem als 'Allen'",
    # CBS-tabellen over meer onderwijssoorten: alleen met de codes uit CBS_SECTORFILTER.
    **{
        tabel: f"CBS-tabel over meer onderwijssoorten; get_cbs_data selecteert alleen {filter_.deel}"
        for tabel, filter_ in CBS_SECTORFILTER.items()
    },
    # RIO-registers over alle sectoren: alleen met een sectorfilter (SECTORFILTER).
    **dict.fromkeys(SECTORFILTER, "RIO-register; alleen met een mbo/hbo/wo-sectorfilter"),
    # Examenlicenties bestaan alleen in het mbo (WEB).
    "examenlicenties": "RIO-register; examenlicenties bestaan alleen in het mbo",
    # Arbeidsmarkt na mbo/hbo/wo: de arbeidsmarktkant van het chatprofiel, via get_uwv_vacatures
    # en get_roa_benchmark (besluit 08-10, #441).
    "ais2030": "ROA-prognoses per mbo/hbo/wo-opleiding",
    "ais2028": "ROA-prognoses per mbo/hbo/wo-opleiding",
    "uwv-open-match-data": "UWV-vacatures; arbeidsmarktkant van het chatprofiel",
}

MELDING = (
    "Deze dataset valt buiten het profiel van de chat: die werkt alleen voor mbo, hbo en wo. "
    "Geef er geen cijfers voor en zeg niet dat de bron niet bestaat; noem dat de chat deze "
    "sector niet behandelt."
)

# Een RIO-register zonder sectorfilter (contactadressen, onderwijslocaties, erkenningen, ...)
# is geen po/vo-bron, maar een pagina ervan bevat wel po/vo-records.
REGISTER_MELDING = (
    "Dit RIO-register is niet per onderwijssector te selecteren; de chat haalt het daarom niet op. "
    f"Bestuur, instellingen en vestigingen van een mbo/hbo/wo-instelling: {TOOL_GET_RIO_INSTELLING}."
)


def dataset_id(entry: dict) -> str | None:
    return entry.get("_cbs_id") or entry.get("_ckan_id") or entry.get("_rio_resource") or entry.get("_roa_id")


def in_scope(entry: dict) -> bool:
    if scope.buiten_scope(entry):
        return False
    if dataset_id(entry) in TOEGELATEN:
        return True
    typen = set(entry.get("onderwijstype") or [])
    return bool(typen) and typen <= SECTOREN


def sectorfilter_ontbreekt(resource: str, filters: dict) -> str | None:
    """Waarom een RIO-aanroep de sector niet vastlegt; None als het filter goed staat."""
    if resource not in SECTORFILTER:
        return None
    naam, waarden = SECTORFILTER[resource]
    if filters.get(naam) in waarden:
        return None
    return (
        f"RIO-register '{resource}' bevat alle onderwijssectoren; de chat haalt het alleen op met "
        f"filter '{naam}' op een mbo/hbo/wo-waarde: {sorted(waarden)}."
    )


@dataclass(frozen=True)
class CbsSectorselectie:
    """De aanroep van een CBS-tabel uit CBS_SECTORFILTER, met de codes die de chat toelaat."""

    params: dict
    dimensie: str
    codes: frozenset[str]
    deel: str

    def rijen(self, rows: list[dict]) -> list[dict]:
        """Alleen de rijen met een toegelaten code: de feed is geen grens op zichzelf."""
        return [r for r in rows if str(r.get(self.dimensie, "")).strip() in self.codes]


def cbs_sectorselectie(dataset_id: str, params: dict) -> CbsSectorselectie | str | None:
    """De params met de sectorselectie vooraan in $filter; None voor een andere tabel.

    Noemt het filter van het model zelf codes van de sectordimensie, dan is de selectie de
    doorsnede met de toegelaten codes. Een lege doorsnede, of de dimensie in een andere vorm
    dan `eq`, geeft een melding in plaats van een aanroep (CH-03).
    """
    if dataset_id not in CBS_SECTORFILTER:
        return None
    filter_ = CBS_SECTORFILTER[dataset_id]
    dimensie = filter_.dimensie
    eigen = str(params.get("$filter") or "").strip()
    genoemd = re.findall(rf"\b{dimensie}\s+eq\s+'([^']*)'", eigen)
    if len(re.findall(rf"\b{dimensie}\b", eigen)) != len(genoemd):
        return (
            f"Filter in $filter op {dimensie} alleen met '{dimensie} eq <code>' en een code voor "
            f"{filter_.deel}: {sorted(filter_.codes)}."
        )
    codes = filter_.codes & {c.strip() for c in genoemd} if genoemd else filter_.codes
    if not codes:
        return filter_.geen_rijen(dataset_id)
    sector = " or ".join(f"{dimensie} eq '{c}'" for c in sorted(codes))
    nieuw = {**params, "$filter": f"({sector}) and ({eigen})" if eigen else sector}
    if "$select" in nieuw and dimensie not in (k.strip() for k in str(nieuw["$select"]).split(",")):
        nieuw["$select"] = f"{nieuw['$select']},{dimensie}"
    return CbsSectorselectie(nieuw, dimensie, codes, filter_.deel)


def cbs_sectordeel(dataset_id: str) -> str | None:
    """Welk deel van een CBS-tabel uit CBS_SECTORFILTER de chat laadt; None voor een andere tabel.

    `cbs_sectorselectie` en de snippet laden zo'n tabel altijd zonder de rijen buiten het
    profiel, dus de bron van die data is dat deel, niet de hele tabel (CH-45)."""
    filter_ = CBS_SECTORFILTER.get(dataset_id)
    return f"alleen {filter_.deel}" if filter_ else None


def buiten_scope(bron: str, *, register: bool = False) -> dict:
    """Het toolresultaat voor een record buiten de grens; `opvraagbaar: false` zoals bij #200,
    zodat de afwezigheidscontrole (#396) 'niet via de chat' als eerlijk antwoord ziet."""
    melding = REGISTER_MELDING if register else MELDING
    return {"bron": bron, "opvraagbaar": False, "buiten_scope": True, "melding": melding}


def buiten_scope_voor(entry: dict) -> dict:
    """`buiten_scope` voor een bekend catalogusrecord."""
    return buiten_scope(entry.get("bron") or dataset_id(entry) or "?", register=entry.get("leverancier") == "RIO")
