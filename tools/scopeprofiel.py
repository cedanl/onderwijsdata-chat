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
Een CBS-tabel over mbo én vo krijgt de mbo-selectie van de code zelf (`CBS_SECTORFILTER`).
"""

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
# houdt alleen de rijen met een mbo-code over, direct na het ophalen: geen filter van het
# model en geen herstelpoging kan de sector dan verbreden (CH-03). Een EN-clausule in
# $filter is geen grens: de CBS-feed gaf op "(vo-code) and (mbo-codes)" toch de vo-rijen.
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


def cbs_sectorrijen(dataset_id: str, rows: list[dict]) -> list[dict]:
    """Alleen de mbo-rijen van een CBS-tabel over mbo én vo; ongewijzigd voor een andere tabel."""
    if dataset_id not in CBS_SECTORFILTER:
        return rows
    dimensie, codes = CBS_SECTORFILTER[dataset_id]
    return [r for r in rows if str(r.get(dimensie, "")).strip() in codes]


def buiten_scope(bron: str, *, register: bool = False) -> dict:
    """Het toolresultaat voor een record buiten de grens; `opvraagbaar: false` zoals bij #200,
    zodat de afwezigheidscontrole (#396) 'niet via de chat' als eerlijk antwoord ziet."""
    melding = REGISTER_MELDING if register else MELDING
    return {"bron": bron, "opvraagbaar": False, "buiten_scope": True, "melding": melding}


def buiten_scope_voor(entry: dict) -> dict:
    """`buiten_scope` voor een bekend catalogusrecord."""
    return buiten_scope(entry.get("bron") or dataset_id(entry) or "?", register=entry.get("leverancier") == "RIO")
