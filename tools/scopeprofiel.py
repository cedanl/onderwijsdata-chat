"""Productscope mbo/hbo/wo: welke RIO/DUO-records de chat toelaat (#355).

riodata kent per record alleen het besluit `buiten_scope`; alles zonder besluit is daar
`onbekend` (#375). Dat is geen grens: `voprognoses` kwam zo bij een mbo-vraag terecht.
De chat laat een record daarom alleen toe als het aantoonbaar over mbo, hbo of wo gaat:

- `onderwijstype` noemt alleen MBO, HBO, WO of HO; of
- het ID staat in `TOEGELATEN`, met de reden waarom.

Al het andere valt erbuiten: po/so/vo, gemengde bestanden zonder veilige sectorselectie,
en een record zonder besluit. De bronpackage mag een bredere inventaris houden.
"""

from riodata import scope

SECTOREN = frozenset({"MBO", "HBO", "WO", "HO"})

# Records waarvan `onderwijstype` de sector niet noemt ('Allen', 'Arbeidsmarkt') of
# meer sectoren omvat. Een nieuw record zonder besluit hier valt erbuiten.
TOEGELATEN: dict[str, str] = {
    # DUO labelt deze mbo-bestanden als 'Allen'.
    "mbo-studenten-per-instelling": "mbo-bestand; DUO labelt het als 'Allen'",
    "mbo-studenten-per-sectorkamer-en-leerweg": "mbo-bestand; DUO labelt het als 'Allen'",
    "instromende-mbo-studenten": "mbo-bestand; DUO labelt het als 'Allen'",
    "gediplomeerde-mbo-studenten": "mbo-bestand; DUO labelt het als 'Allen'",
    # RIO-registers over alle sectoren: de chat vraagt ze op met een instellings- of
    # opleidingscode uit het mbo/hbo/wo-register. Een sectorfilter op de rijen zelf
    # bestaat nog niet (#355).
    "organisatorische-eenheden": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "erkenningen": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "contactadressen": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "onderwijslocaties": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "onderwijslocatiegebruiken": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "aangeboden-opleidingen": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "opleidingen": "RIO-register; CREBO- en CROHO-opleidingen",
    "opleidingserkenningen": "RIO-register; opgevraagd per mbo/hbo/wo-opleiding",
    "onderwijslicenties": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    "examenlicenties": "RIO-register; opgevraagd per mbo/hbo/wo-instelling",
    # Arbeidsmarkt na mbo/hbo/wo; niet via de chat op te vragen (#200), wel vindbaar.
    "ais2030": "ROA-prognoses per mbo/hbo/wo-opleiding",
    "ais2028": "ROA-prognoses per mbo/hbo/wo-opleiding",
    "uwv-open-match-data": "UWV-vacatures; arbeidsmarktkant van het chatprofiel",
}

MELDING = (
    "Deze dataset valt buiten het profiel van de chat: die werkt alleen voor mbo, hbo en wo. "
    "Geef er geen cijfers voor en zeg niet dat de bron niet bestaat; noem dat de chat deze "
    "sector niet behandelt."
)


def dataset_id(entry: dict) -> str | None:
    return entry.get("_ckan_id") or entry.get("_rio_resource") or entry.get("_roa_id")


def in_scope(entry: dict) -> bool:
    if scope.buiten_scope(entry):
        return False
    if dataset_id(entry) in TOEGELATEN:
        return True
    typen = set(entry.get("onderwijstype") or [])
    return bool(typen) and typen <= SECTOREN


def buiten_scope(bron: str) -> dict:
    """Het toolresultaat voor een record buiten de grens; `opvraagbaar: false` zoals bij #200,
    zodat de afwezigheidscontrole (#396) 'niet via de chat' als eerlijk antwoord ziet."""
    return {"bron": bron, "opvraagbaar": False, "buiten_scope": True, "melding": MELDING}
