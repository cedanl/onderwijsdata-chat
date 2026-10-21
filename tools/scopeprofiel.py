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

Eén uitzondering (#554): de vo-bronnen in `HO_CONTEXT` geven een ho-vraag context. Ze vallen
binnen het profiel, maar `catalog.search_catalog` toont ze alleen als de vraag van de gebruiker ho
noemt (`ho_markers.ho_poort`, #597), en elke treffer, bronregel en maatkaartoptie noemt ze "vo-context voor ho".

Een RIO-register over alle sectoren is alleen toegelaten als een filter de sector
vastlegt (`SECTORFILTER`); die toets doet `sectorfilter_ontbreekt` vóór elke aanroep.
Een CBS-tabel die ook over andere onderwijssoorten gaat, krijgt de selectie op mbo, hbo of wo
van de code zelf (`CBS_SECTORFILTER`): in de aanroep en nog eens op de ontvangen rijen
(`cbs_sectorselectie`).
"""

import re
from dataclasses import dataclass

from riodata import scope

from .canoniek import zonder_bronprefix
from .schemas import TOOL_GET_RIO_INSTELLING

SECTOREN = frozenset({"MBO", "HBO", "WO", "HO"})

# Woorden waarmee een vraag po, so of vo noemt, buiten de scope van de chat (#355): voor de vervolgvragen
# (agent/vervolgvragen.py), de scope-uitleg vóór het model (agent/po_vraag.py, #647; daar beslist een losse
# "so" of "bo" niet) en de vaste scope-uitleg achteraf (agent/vaste_antwoorden.py). "groep 1" t/m "groep 8"
# zijn de jaargroepen van de basisschool (BEV-12).
PO_SO_VO = re.compile(
    r"\b(?:po|so|vo|vso|bo|sbo|vavo|vmbo|havo|vwo|basisonderwijs|basisschool|basisscholen|praktijkonderwijs"
    r"|primair\s+onderwijs|speciaal\s+onderwijs|voortgezet(?:\s+speciaal)?\s+onderwijs|groep\s+[1-8])\b",
    re.IGNORECASE,
)

# Per RIO-register het filter dat de sector vastlegt, met de waarden die mbo/hbo/wo
# betekenen. Zonder dat filter haalt de chat het register niet op: een pagina zonder
# sectorfilter bevat ook po/vo-records. Sinds RIO LOD API v3 heet het typefilter op elk
# register `type` (#627); test_scopeprofiel toetst de namen tegen het riodata-contract.
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
        "type",
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
        "type",
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
# daarom vooraan. Het filter van het model komt erachter zonder haakjes: zie _als_term.
# Codes uit de dimensie zelf.
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
    # Dezelfde VSV, naar leeftijd; de dimensie kent alleen totalen: mbo is A025290 (vo is A042781, vavo A025300).
    "85367NED": CbsSectorfilter("Onderwijssoort", frozenset({"A025290"}), "mbo"),
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

# Vo-bronnen die een ho-vraag van context voorzien: wie er van het vo naar het ho kan instromen (#554).
# Een aparte categorie naast TOEGELATEN: in_scope laat ze toe, maar de zoekpoort in catalog._verzamel
# toont ze alleen bij een vraag die ho noemt (#557), en elke treffer en bronregel draagt het etiket hieronder.
HO_CONTEXT: dict[str, str] = {
    "85566NED": "Doorstroom en uitstroom uit het vo en vso als context voor de instroom in het ho; het gaat om "
    "vo- en vso-leerlingen, geen studenten",
    "85381NED": "Vo-gediplomeerden naar onderwijssoort als context voor de potentiële instroom in het ho; "
    "het gaat om vo-leerlingen, geen studenten",
    "85382NED": "Vo-gediplomeerden naar woonregio als context voor de regionale instroom in het ho; "
    "het gaat om vo-leerlingen, geen studenten",
    "85380NED": "Huidige vo-leerlingen naar onderwijssoort, leerjaar en woonregio als context voor de toekomstige "
    "instroom in het ho; het gaat om vo-leerlingen, geen studenten",
    "voprognoses": "Prognoses van leerlingaantallen in het vo als context voor de toekomstige instroom in het ho; "
    "het gaat om vo-leerlingen, geen studenten",
}
# Het veld `context` op elke zoektreffer uit HO_CONTEXT, en het deel achter de titel in een bronregel.
HO_CONTEXT_ETIKET = "vo-context voor ho: leerlingen in het voortgezet onderwijs, geen studenten"
HO_CONTEXT_DEEL = "vo-context voor ho"
_HO_CONTEXT_SLEUTELS = frozenset(i.lower() for i in HO_CONTEXT)

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


def is_ho_context(entry_or_id: dict | str) -> bool:
    """Of een record of ID in HO_CONTEXT staat; hoofdletterongevoelig en zonder bron-voorvoegsel,
    zoals `catalog.bron_id` het ID terugvindt (`cbs:85566ned` is `85566NED`)."""
    ruw = dataset_id(entry_or_id) if isinstance(entry_or_id, dict) else entry_or_id
    return bool(ruw) and zonder_bronprefix(ruw).lower() in _HO_CONTEXT_SLEUTELS


def in_scope(entry: dict) -> bool:
    if scope.buiten_scope(entry):
        return False
    if dataset_id(entry) in TOEGELATEN or is_ho_context(entry):
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


def _als_term(eigen: str) -> str:
    """Het filter van het model als één term achter de sectorselectie.

    De CBS-feed geeft een serverfout (HTTP 500) op `(A or B) and (X and Y)`: een haakjesgroep met
    een `and` erin naast een andere groep. `(A or B) and X and Y` en `(A or B) and (X or Y)` werken
    (gemeten 15-10-2026 op 85701NED: regio én periode gaf altijd een 500). Haakjes dus alleen om
    een filter met een `or` op het hoogste niveau, want daar binden ze de voorrang.
    """
    diepte = 0
    for i, teken in enumerate(eigen):
        if teken == "(":
            diepte += 1
        elif teken == ")":
            diepte -= 1
        elif diepte == 0 and eigen[i : i + 4].lower() == " or ":
            return f"({eigen})"
    return eigen


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
    # `Dim eq 'code'` uit een bewaard recept, of `trim(Dim) eq 'code'` zoals de compiler schrijft (#531).
    genoemd = re.findall(rf"(?:\btrim\({dimensie}\)|\b{dimensie})\s+eq\s+'([^']*)'", eigen)
    if len(re.findall(rf"\b{dimensie}\b", eigen)) != len(genoemd):
        return (
            f"Filter in $filter op {dimensie} alleen met '{dimensie} eq <code>' en een code voor "
            f"{filter_.deel}: {sorted(filter_.codes)}."
        )
    codes = filter_.codes & {c.strip() for c in genoemd} if genoemd else filter_.codes
    if not codes:
        return filter_.geen_rijen(dataset_id)
    sector = " or ".join(f"{dimensie} eq '{c}'" for c in sorted(codes))
    nieuw = {**params, "$filter": f"({sector}) and {_als_term(eigen)}" if eigen else sector}
    if "$select" in nieuw and dimensie not in (k.strip() for k in str(nieuw["$select"]).split(",")):
        nieuw["$select"] = f"{nieuw['$select']},{dimensie}"
    return CbsSectorselectie(nieuw, dimensie, codes, filter_.deel)


def cbs_sectordeel(dataset_id: str) -> str | None:
    """Welk deel van een CBS-tabel uit CBS_SECTORFILTER de chat laadt; None voor een andere tabel.

    `cbs_sectorselectie` en de snippet laden zo'n tabel altijd zonder de rijen buiten het
    profiel, dus de bron van die data is dat deel, niet de hele tabel (CH-45)."""
    filter_ = CBS_SECTORFILTER.get(dataset_id)
    return f"alleen {filter_.deel}" if filter_ else None


def bronetiket(dataset_id: str) -> str | None:
    """Wat een bronregel achter de titel zet: het geladen deel (`alleen mbo`) of `vo-context voor ho`; anders None."""
    return cbs_sectordeel(dataset_id) or (HO_CONTEXT_DEEL if is_ho_context(dataset_id) else None)


def buiten_scope(bron: str, *, register: bool = False) -> dict:
    """Het toolresultaat voor een record buiten de grens; `opvraagbaar: false` zoals bij #200,
    zodat de afwezigheidscontrole (#396) 'niet via de chat' als eerlijk antwoord ziet."""
    melding = REGISTER_MELDING if register else MELDING
    return {"bron": bron, "opvraagbaar": False, "buiten_scope": True, "melding": melding}


def buiten_scope_voor(entry: dict) -> dict:
    """`buiten_scope` voor een bekend catalogusrecord."""
    return buiten_scope(entry.get("bron") or dataset_id(entry) or "?", register=entry.get("leverancier") == "RIO")
