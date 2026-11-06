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

Eén uitzondering (#554, #877): de vo-bronnen in `VO_CONTEXT` geven een vraag over vervolgonderwijs context.
Ze vallen binnen het profiel, maar `catalog.search_catalog` toont ze alleen als de vraag van de gebruiker het ho
noemt of de doorstroom uit het vo (`ho_markers.vo_context_poort`, #597), en elke treffer, bronregel en
maatkaartoptie noemt ze "vo-context voor vervolgonderwijs".

Een RIO-register over alle sectoren is alleen toegelaten als een filter de sector
vastlegt (`SECTORFILTER`); die toets doet `sectorfilter_ontbreekt` vóór elke aanroep.
Een CBS-tabel die ook over andere onderwijssoorten gaat, krijgt de selectie op mbo, hbo of wo
van de code zelf (`CBS_SECTORFILTER`): in de aanroep en nog eens op de ontvangen rijen
(`cbs_sectorselectie`).

Bij een doorstroomvraag uit het vo (`ho_markers.vo_deel_poort`, #879, #880) laten beide ook hun vo-deel toe: de
vo-codes van een CBS-tabel (`CbsSectorfilter.vo_codes`) en de vo- en vavo-typen van een RIO-register
(`SECTORFILTER_VO_CONTEXT`). De aanroeper geeft de poort mee; de lading houdt haar vast (`KeyMeta.vo_context`), en
elke bronregel van die lading noemt het vo-deel als vo-context voor vervolgonderwijs (`bronetiket`).
"""

import re
from dataclasses import dataclass

from onderwijsbronnen import scope

from .canoniek import zonder_bronprefix
from .schemas import TOOL_GET_RIO_INSTELLING

SECTOREN = frozenset({"MBO", "HBO", "WO", "HO"})
# Het wettelijk kader van een RIO-erkenning (`wet`) voor po, vo en so (WPO, WVO, WEC, ook met een toevoeging): zo'n
# instelling noemt de chat niet, ook niet onder een bestuur (#355) of als voorganger in een fusie (#937).
_WETTEN_BUITEN_SCOPE = ("WPO", "WVO", "WEC")


def wet_buiten_scope(wet: str | None) -> bool:
    """Of een erkenning met dit wettelijk kader po, vo of so is; een onbekende wet valt er niet onder."""
    return str(wet or "").startswith(_WETTEN_BUITEN_SCOPE)


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
# Per register de vo- en vavo-typen op hetzelfde filter (#880): alleen toegelaten als de poort open is
# (`sectorfilter_ontbreekt(..., vo_context=True)`), en een pagina ervan draagt het etiket van de vo-context.
# Uit het riodata-contract (filter `type`, gemeten 03-11-2026); test_scopeprofiel toetst de namen. Po en (v)so blijven
# dicht, net als de registers zonder typefilter.
SECTORFILTER_VO_CONTEXT: dict[str, frozenset[str]] = {
    "aangeboden-opleidingen": frozenset({"AANGEBODENVOOPLEIDING", "AANGEBODENVAVOOPLEIDING"}),
    "opleidingen": frozenset(
        {
            "VOOPLEIDING",
            "VOOPLEIDINGSFASE",
            "VOGROEP",
            "VOVAK",
            "VOSTAGE",
            "VAVOOPLEIDING",
            "VAVOOPLEIDINGSFASE",
            "VAVOGROEP",
        }
    ),
    "opleidingserkenningen": frozenset(
        {
            "VOOPLEIDINGSERKENNING",
            "VOGROEPSERKENNING",
            "VOVAKERKENNING",
            "VAVOOPLEIDINGSERKENNING",
            "VAVOGROEPSERKENNING",
        }
    ),
    "onderwijslicenties": frozenset({"VOONDERWIJSLICENTIE", "VAVOONDERWIJSLICENTIE"}),
}


@dataclass(frozen=True)
class CbsSectorfilter:
    """De rijen van een CBS-tabel over meer onderwijssoorten die de chat laadt.

    `deel` zegt in woorden welk deel dat is ('mbo'; 'mbo, hbo en wo'): elke bronregel en
    melding noemt het, zodat een antwoord de tabel niet breder voorstelt dan wat geladen is.
    `vo_codes` zijn de vo- en vavo-rijen, alleen bij een doorstroomvraag uit het vo (#879); geen totaal over
    vo en mbo samen, en geen po of (v)so.
    """

    dimensie: str
    codes: frozenset[str]
    deel: str
    vo_codes: frozenset[str] = frozenset()

    def toegelaten(self, vo_context: bool) -> frozenset[str]:
        """De codes die de chat laadt: met de vo-codes alleen als de poort open is."""
        return self.codes | self.vo_codes if vo_context else self.codes

    def deel_voor(self, vo_context: bool) -> str:
        """Het deel in woorden: 'mbo', of met het vo erbij 'mbo en vo (vo-context voor vervolgonderwijs)'."""
        if not (vo_context and self.vo_codes):
            return self.deel
        return f"{self.deel.replace(' en ', ', ')} en vo ({VO_CONTEXT_DEEL})"

    def geen_rijen(self, dataset_id: str, vo_context: bool) -> str:
        """De melding als de selectie geen rijen in het profiel bevat."""
        deel = self.deel_voor(vo_context)
        return (
            f"Dataset '{dataset_id}' gaat ook over andere onderwijssoorten; de chat laadt alleen de rijen voor "
            f"{deel}, en deze selectie bevat er geen. Filter in $filter op {self.dimensie} met een code "
            f"voor {deel}: {sorted(self.toegelaten(vo_context))}."
        )


# CBS-tabellen die ook over andere onderwijssoorten gaan, met een dimensie die de sector
# vastlegt. get_cbs_data vraagt alleen de rijen in het profiel op en houdt na het ophalen
# ook alleen die over: geen filter van het model en geen herstelpoging kan de sector
# verbreden (CH-03). De CBS-feed gebruikt bij twee clausules op dezelfde dimensie alleen
# de eerste: op "(vo-code) and (mbo-codes)" kwamen de vo-rijen. De sectorselectie staat
# daarom vooraan. Het filter van het model komt erachter zonder haakjes: zie _als_term.
# Codes uit de dimensie zelf; de vo-codes opnieuw gecontroleerd op 03-11-2026 (#879), zonder de totalen over vo en mbo
# samen ('Totaal onderwijs') en zonder po en (v)so.
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
        frozenset(
            {
                "A042781",  # Totaal vmbo/havo/vwo
                "A028733",  # leerjaar 1 en 2
                "A042824",
                "A049228",  # vmbo 3-4 zonder, met diploma
                "A042798",  # havo 3-5/vwo 3-6
                "A025300",  # Totaal vavo
                "A043030",
                "A043031",  # vavo vmbo-t zonder, met diploma
                "A043038",  # vavo havo/vwo
            }
        ),
    ),
    # Dezelfde VSV, naar leeftijd; de dimensie kent alleen totalen: mbo is A025290, vo A042781 en vavo A025300.
    "85367NED": CbsSectorfilter("Onderwijssoort", frozenset({"A025290"}), "mbo", frozenset({"A042781", "A025300"})),
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
        frozenset(
            {
                "T001345",  # Totaal voortgezet onderwijs
                "A041919",  # vo algemene leerjaren 1-3
                "A041920",
                "A041921",  # vwo 3-6, havo 3-5
                "A041922",
                "A041923",  # vmbo-g/t, vmbo-b/k 3-4
                "A025289",  # praktijkonderwijs
                "A025300",  # Totaal vavo
                "A043035",
                "A043032",
                "A043029",  # vavo vwo, havo, vmbo-t
            }
        ),
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
        frozenset(
            {
                "T001345",  # Totaal voortgezet onderwijs
                "A025284",
                "A025285",  # vwo, havo
                "A025288",
                "A042836",
                "A042842",  # vmbo g/t, -k, -b
                "A025300",  # Totaal vavo
                "A043035",
                "A043032",
                "A043029",  # vavo vwo, havo, vmbo-t
            }
        ),
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
        + (", bij een doorstroomvraag uit het vo ook het vo" if filter_.vo_codes else "")
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

# Vo-bronnen die een vraag over vervolgonderwijs van context voorzien: wie er van het vo naar het mbo of het ho kan
# doorstromen (#554, besluit A van #877). Een aparte categorie naast TOEGELATEN: in_scope laat ze toe, maar de
# zoekpoort in catalog._verzamel toont ze alleen bij een vraag over het ho of over doorstroom uit het vo
# (ho_markers.opent_vo_context), en elke treffer en bronregel draagt het etiket hieronder. Alleen lopende tabellen
# en recente bestanden; gearchiveerde CBS-reeksen en de DUO-bestanden t/m 2019 pas bij een echte vraag (#877).
VO_CONTEXT: dict[str, str] = {
    "85566NED": "Doorstroom en uitstroom uit het vo en vso als context voor de instroom in mbo en ho; het gaat om "
    "vo- en vso-leerlingen, geen studenten",
    "85381NED": "Vo-gediplomeerden naar onderwijssoort als context voor de potentiële instroom in mbo en ho; "
    "het gaat om vo-leerlingen, geen studenten",
    "85382NED": "Vo-gediplomeerden naar woonregio als context voor de regionale instroom in mbo en ho; "
    "het gaat om vo-leerlingen, geen studenten",
    "85380NED": "Huidige vo-leerlingen naar onderwijssoort, leerjaar en woonregio als context voor de toekomstige "
    "instroom in mbo en ho; het gaat om vo-leerlingen, geen studenten",
    "85379NED": "Huidige vo-leerlingen naar onderwijssoort in detail (vmbo-leerweg, havo, vwo), leerjaar en herkomst "
    "als context voor de toekomstige instroom in mbo en ho; het gaat om vo-leerlingen, geen studenten",
    "85534NED": "Vo-cohorten met hun hoogst behaalde diploma en onderwijspositie op een later peilmoment: waar een "
    "vo-cohort uitkomt, ook in mbo en ho; het gaat om vo-leerlingen, geen studenten",
    "85328NED": "Vavo-gediplomeerden naar onderwijssoort: een vo-diploma via het vavo als opstap naar mbo of ho; "
    "het gaat om vavo-deelnemers, geen mbo- of ho-studenten",
    "85329NED": "Vavo-deelnemers naar onderwijssoort: de tweedekansroute naar een vo-diploma en daarmee naar "
    "vervolgonderwijs; CBS noemt ze studenten, maar het zijn geen mbo- of ho-studenten",
    "85948NED": "Terugkeer in het onderwijs van voortijdig schoolverlaters uit vo en mbo: de route terug naar "
    "vervolgonderwijs; het gaat om schoolverlaters, geen ingeschreven studenten",
    "voprognoses": "Prognoses van leerlingaantallen in het vo als context voor de toekomstige instroom in mbo en "
    "ho; het gaat om vo-leerlingen, geen studenten",
}
# Het veld `context` op elke zoektreffer uit VO_CONTEXT, en het deel achter de titel in een bronregel.
VO_CONTEXT_ETIKET = (
    "vo-context voor vervolgonderwijs: leerlingen in het voortgezet onderwijs (ook vavo en vsv), "
    "geen mbo- of ho-studenten"
)
VO_CONTEXT_DEEL = "vo-context voor vervolgonderwijs"
_VO_CONTEXT_SLEUTELS = frozenset(i.lower() for i in VO_CONTEXT)

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
    return (
        entry.get("_cbs_id")
        or entry.get("_ckan_id")
        or entry.get("_rio_resource")
        or entry.get("_roa_id")
        or entry.get("_unl_id")
        or entry.get("_skdb_id")
    )


def is_vo_context(entry_or_id: dict | str) -> bool:
    """Of een record of ID in VO_CONTEXT staat; hoofdletterongevoelig en zonder bron-voorvoegsel,
    zoals `catalog.bron_id` het ID terugvindt (`cbs:85566ned` is `85566NED`)."""
    ruw = dataset_id(entry_or_id) if isinstance(entry_or_id, dict) else entry_or_id
    return bool(ruw) and zonder_bronprefix(ruw).lower() in _VO_CONTEXT_SLEUTELS


def in_scope(entry: dict) -> bool:
    if scope.buiten_scope(entry):
        return False
    if dataset_id(entry) in TOEGELATEN or is_vo_context(entry):
        return True
    typen = set(entry.get("onderwijstype") or [])
    return bool(typen) and typen <= SECTOREN


def sectorfilter_ontbreekt(resource: str, filters: dict, *, vo_context: bool) -> str | None:
    """Waarom een RIO-aanroep de sector niet vastlegt; None als het filter goed staat.

    `vo_context` is de poort van de beurt (`ho_markers.vo_deel_poort`) of het recept van de lading: alleen dan mag het
    filter ook een vo- of vavo-type zijn (#880)."""
    if resource not in SECTORFILTER:
        return None
    naam, waarden = SECTORFILTER[resource]
    vo_waarden = SECTORFILTER_VO_CONTEXT[resource] if vo_context else frozenset()
    if filters.get(naam) in waarden | vo_waarden:
        return None
    vo = f", of als vo-context voor vervolgonderwijs op een vo-waarde: {sorted(vo_waarden)}" if vo_waarden else ""
    return (
        f"RIO-register '{resource}' bevat alle onderwijssectoren; de chat haalt het alleen op met "
        f"filter '{naam}' op een mbo/hbo/wo-waarde: {sorted(waarden)}{vo}."
    )


def rio_vo_context(resource: str, filters: dict) -> bool:
    """Haalt deze RIO-aanroep een vo- of vavo-type op (#880)? Dan draagt de lading het etiket van de vo-context."""
    return resource in SECTORFILTER and filters.get(SECTORFILTER[resource][0]) in SECTORFILTER_VO_CONTEXT[resource]


@dataclass(frozen=True)
class CbsSectorselectie:
    """De aanroep van een CBS-tabel uit CBS_SECTORFILTER, met de codes die de chat toelaat."""

    params: dict
    dimensie: str
    codes: frozenset[str]
    deel: str
    vo_context: bool  # de selectie bevat vo-codes: de lading is (deels) vo-context (#879)

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


def cbs_sectorselectie(dataset_id: str, params: dict, *, vo_context: bool) -> CbsSectorselectie | str | None:
    """De params met de sectorselectie vooraan in $filter; None voor een andere tabel.

    Noemt het filter van het model zelf codes van de sectordimensie, dan is de selectie de
    doorsnede met de toegelaten codes. Een lege doorsnede, of de dimensie in een andere vorm
    dan `eq`, geeft een melding in plaats van een aanroep (CH-03). `vo_context` is de poort (#879): alleen dan horen
    de vo-codes bij de toegelaten codes, ook in de meldingen, zodat een herstelpoging ze verder niet leert kennen.
    """
    if dataset_id not in CBS_SECTORFILTER:
        return None
    filter_ = CBS_SECTORFILTER[dataset_id]
    dimensie = filter_.dimensie
    toegelaten = filter_.toegelaten(vo_context)
    eigen = str(params.get("$filter") or "").strip()
    # `Dim eq 'code'` uit een bewaard recept, of `trim(Dim) eq 'code'` zoals de compiler schrijft (#531).
    genoemd = re.findall(rf"(?:\btrim\({dimensie}\)|\b{dimensie})\s+eq\s+'([^']*)'", eigen)
    if len(re.findall(rf"\b{dimensie}\b", eigen)) != len(genoemd):
        return (
            f"Filter in $filter op {dimensie} alleen met '{dimensie} eq <code>' en een code voor "
            f"{filter_.deel_voor(vo_context)}: {sorted(toegelaten)}."
        )
    codes = toegelaten & {c.strip() for c in genoemd} if genoemd else toegelaten
    if not codes:
        return filter_.geen_rijen(dataset_id, vo_context)
    sector = " or ".join(f"{dimensie} eq '{c}'" for c in sorted(codes))
    nieuw = {**params, "$filter": f"({sector}) and {_als_term(eigen)}" if eigen else sector}
    if "$select" in nieuw and dimensie not in (k.strip() for k in str(nieuw["$select"]).split(",")):
        nieuw["$select"] = f"{nieuw['$select']},{dimensie}"
    vo = bool(codes & filter_.vo_codes)
    return CbsSectorselectie(nieuw, dimensie, codes, filter_.deel_voor(vo), vo)


def cbs_sectordeel(dataset_id: str, vo_context: bool = False) -> str | None:
    """Welk deel van een CBS-tabel uit CBS_SECTORFILTER de chat laadt; None voor een andere tabel.

    `cbs_sectorselectie` en de snippet laden zo'n tabel altijd zonder de rijen buiten het
    profiel, dus de bron van die data is dat deel, niet de hele tabel (CH-45). `vo_context` komt van de lading
    (`KeyMeta.vo_context`, #879): zonder lading is het deel dat van een lading zonder vo-rijen."""
    filter_ = CBS_SECTORFILTER.get(dataset_id)
    return f"alleen {filter_.deel_voor(vo_context)}" if filter_ else None


def bronetiket(dataset_id: str, vo_context: bool = False) -> str | None:
    """Wat een bronregel achter de titel zet: het geladen deel (`alleen mbo`) of `vo-context voor vervolgonderwijs`;
    anders None. `vo_context` is die van de lading (#879, #880): een RIO-pagina met een vo-type draagt het etiket ook."""
    return cbs_sectordeel(dataset_id, vo_context) or (
        VO_CONTEXT_DEEL if vo_context or is_vo_context(dataset_id) else None
    )


def buiten_scope(bron: str, *, register: bool = False) -> dict:
    """Het toolresultaat voor een record buiten de grens; `opvraagbaar: false` zoals bij #200,
    zodat de afwezigheidscontrole (#396) 'niet via de chat' als eerlijk antwoord ziet."""
    melding = REGISTER_MELDING if register else MELDING
    return {"bron": bron, "opvraagbaar": False, "buiten_scope": True, "melding": melding}


def buiten_scope_voor(entry: dict) -> dict:
    """`buiten_scope` voor een bekend catalogusrecord."""
    return buiten_scope(entry.get("bron") or dataset_id(entry) or "?", register=entry.get("leverancier") == "RIO")
