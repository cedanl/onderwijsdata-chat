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
Een CBS-tabel over mbo én vo krijgt de mbo-selectie van de code zelf (`CBS_SECTORFILTER`):
in de aanroep en nog eens op de ontvangen rijen (`cbs_sectorselectie`).
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

# CBS-tabellen over mbo én vo met een dimensie die de sector vastlegt (VSV). get_cbs_data
# vraagt alleen mbo-rijen op en houdt na het ophalen ook alleen de rijen met een mbo-code
# over: geen filter van het model en geen herstelpoging kan de sector verbreden (CH-03).
# De CBS-feed gebruikt bij twee clausules op dezelfde dimensie alleen de eerste: op
# "(vo-code) and (mbo-codes)" kwamen de vo-rijen. De mbo-selectie staat daarom vooraan.
# Codes uit de dimensie zelf.
_VSV_MBO = frozenset({"T001336", "A041868", "A025293", "A041773"})  # mbo totaal, bol, bbl, extranei
CBS_SECTORFILTER: dict[str, tuple[str, frozenset[str]]] = {
    "85368NED": (
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
    ),
    "85859NED": ("Onderwijssoort", _VSV_MBO),
    "85860NED": ("Onderwijssoort", _VSV_MBO),
    "85861NED": ("Onderwijssoort", _VSV_MBO),
    "85862NED": ("Onderwijssoort", _VSV_MBO),
    "84534NED": ("Onderwijssoort", _VSV_MBO),
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
    # CBS-tabellen over mbo en vo: alleen met de mbo-codes (CBS_SECTORFILTER).
    **dict.fromkeys(CBS_SECTORFILTER, "CBS-tabel over mbo en vo; get_cbs_data selecteert alleen mbo"),
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
    """De aanroep van een CBS-tabel over mbo én vo, met de mbo-codes die de chat toelaat."""

    params: dict
    dimensie: str
    codes: frozenset[str]

    def rijen(self, rows: list[dict]) -> list[dict]:
        """Alleen de rijen met een toegelaten code: de feed is geen grens op zichzelf."""
        return [r for r in rows if str(r.get(self.dimensie, "")).strip() in self.codes]


def cbs_sectorselectie(dataset_id: str, params: dict) -> CbsSectorselectie | str | None:
    """De params met de mbo-selectie vooraan in $filter; None voor een andere tabel.

    Noemt het filter van het model zelf codes van de sectordimensie, dan is de selectie de
    doorsnede met mbo. Een lege doorsnede, of de dimensie in een andere vorm dan `eq`, geeft
    een melding in plaats van een aanroep (CH-03).
    """
    if dataset_id not in CBS_SECTORFILTER:
        return None
    dimensie, mbo = CBS_SECTORFILTER[dataset_id]
    eigen = str(params.get("$filter") or "").strip()
    genoemd = re.findall(rf"\b{dimensie}\s+eq\s+'([^']*)'", eigen)
    if len(re.findall(rf"\b{dimensie}\b", eigen)) != len(genoemd):
        return f"Filter in $filter op {dimensie} alleen met '{dimensie} eq <code>' en een mbo-code: {sorted(mbo)}."
    codes = mbo & {c.strip() for c in genoemd} if genoemd else mbo
    if not codes:
        return (
            f"Dataset '{dataset_id}' gaat over mbo en vo; de chat laadt alleen de mbo-rijen, en deze "
            f"selectie bevat er geen. Filter in $filter op {dimensie} met een mbo-code: {sorted(mbo)}."
        )
    sector = " or ".join(f"{dimensie} eq '{c}'" for c in sorted(codes))
    nieuw = {**params, "$filter": f"({sector}) and ({eigen})" if eigen else sector}
    if "$select" in nieuw and dimensie not in (k.strip() for k in str(nieuw["$select"]).split(",")):
        nieuw["$select"] = f"{nieuw['$select']},{dimensie}"
    return CbsSectorselectie(nieuw, dimensie, codes)


def cbs_sectordeel(dataset_id: str) -> str | None:
    """Welk deel van een CBS-tabel over mbo én vo de chat laadt; None voor een andere tabel.

    `cbs_sectorselectie` en de snippet laden zo'n tabel altijd zonder de vo-rijen, dus de bron
    van die data is het mbo-deel, niet de hele tabel (CH-45)."""
    return "alleen mbo" if dataset_id in CBS_SECTORFILTER else None


def buiten_scope(bron: str, *, register: bool = False) -> dict:
    """Het toolresultaat voor een record buiten de grens; `opvraagbaar: false` zoals bij #200,
    zodat de afwezigheidscontrole (#396) 'niet via de chat' als eerlijk antwoord ziet."""
    melding = REGISTER_MELDING if register else MELDING
    return {"bron": bron, "opvraagbaar": False, "buiten_scope": True, "melding": melding}


def buiten_scope_voor(entry: dict) -> dict:
    """`buiten_scope` voor een bekend catalogusrecord."""
    return buiten_scope(entry.get("bron") or dataset_id(entry) or "?", register=entry.get("leverancier") == "RIO")
