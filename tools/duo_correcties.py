"""Correcties op DUO-kolombeschrijvingen die in de bron fout of leeg zijn (#451).

De riodata-glossary geeft een kolomnaam één betekenis voor alle bestanden, en DUO's eigen
metadata is op plekken leeg. Zo heette DIPLOMAJAAR in p04hogdipl het jaar van het
vooropleidingsdiploma en was PROVINCIENAAM in de ho-bestanden "Naam van de provincie",
waarna het model de vestiging las als woonplaats. Hier staan de correcties per dataset en
kolom, in code: ze hangen niet af van een herstel bij DUO. Een correctie gaat voor op
riodata, in get_duo_data én in dataset_details. Bij de ho-bestanden zegt de catalogus
bovendien dat ze niet over woonplaats of herkomst gaan.

Bewijs, nagegaan op 2026-10-08:
- p04hogdipl: SOORT_DIPLOMA heeft alleen de waarden hbo associate degree/bachelor/master
  en wo bachelor/master/postmaster, en de DUO-selectie telt "hoofd-bachelor-diploma" enz.:
  het behaalde ho-diploma. DIPLOMAJAAR loopt 2020-2024, "de laatste vijf diplomajaren".
- p01-p04: per instelling 1 tot 9 gemeenten (Hogeschool Utrecht: Utrecht, Amersfoort en
  drie kleine locaties), geen honderden woongemeenten: de plaats is de vestiging.
- instromende-mbo-studenten: DUO's "Uitleg kolomnamen" (duo.nl, instromende studenten
  mbo). In het bestand per hoofdgroep geldt in elke rij zonder -1:
  INSTROOM MBO <= INSTROOM OPLEIDING <= TOTAAL MBO (2025: 155k, 208k, 473k).
"""

_NIET_WOONPLAATS = "niet de woonplaats of herkomst van de student"
_HO_VESTIGING = {
    "PROVINCIENAAM": f"Provincie van de vestiging waar de instelling de opleiding geeft; {_NIET_WOONPLAATS}.",
    "GEMEENTENAAM": f"Gemeente van de vestiging waar de instelling de opleiding geeft; {_NIET_WOONPLAATS}.",
    "GEMEENTENUMMER": f"CBS-gemeentecode van de vestigingsgemeente (zie GEMEENTENAAM); {_NIET_WOONPLAATS}.",
}

# Voor de bestanden per hoofdgroep een aantal, voor de bestanden 'met soorten instroom' een indicator.
_AANTAL_OF_INDICATOR = (
    "In de bestanden per hoofdgroep en vooropleiding een aantal studenten; in de bestanden "
    "'met soorten instroom' een indicator J/N, met het aantal in AANTAL."
)

KOLOMCORRECTIES: dict[str, dict[str, str]] = {
    "p01hoinges": _HO_VESTIGING,
    "p02ho1ejrs": _HO_VESTIGING,
    "p03hoinschr": _HO_VESTIGING,
    "p04hogdipl": {
        **_HO_VESTIGING,
        "DIPLOMAJAAR": (
            "Jaar waarin het hoger-onderwijsdiploma uit SOORT_DIPLOMA is behaald; DUO publiceert de "
            "laatste vijf diplomajaren. Niet het jaar van een vooropleidingsdiploma."
        ),
        "SOORT_DIPLOMA": (
            "Het behaalde hoger-onderwijsdiploma: hbo associate degree, hbo bachelor of hbo master in de "
            "hbo-bestanden; wo bachelor, wo master of wo postmaster in de wo-bestanden. Niet de vooropleiding."
        ),
    },
    "instromende-mbo-studenten": {
        "TOTAAL MBO": (
            "Aantal studenten dat in het studiejaar in het mbo ingeschreven is (peildatum 1 oktober), "
            "nieuw of niet: geen instroom. De instroom staat in INSTROOM MBO en INSTROOM OPLEIDING."
        ),
        "INSTROOM MBO": (
            f"Studenten die nieuw in het mbo zijn: een jaar eerder geen mbo-inschrijving. {_AANTAL_OF_INDICATOR}"
        ),
        "INSTROOM OPLEIDING": (
            "Studenten die nieuw in de beroepsopleiding zijn: een jaar eerder niet in deze opleiding "
            "ingeschreven. Telt ook overstappers binnen het mbo, en dus iedereen uit INSTROOM MBO. "
            f"{_AANTAL_OF_INDICATOR}"
        ),
    },
}

# Datasets waarvan de plaatskolommen de vestiging zijn: geen bron voor waar studenten wonen.
_VESTIGING_NIET_HERKOMST = frozenset({"p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"})
NIET_GESCHIKT_VOOR_HERKOMST = (
    "Niet geschikt voor woonplaats of herkomst van studenten: PROVINCIENAAM en GEMEENTENAAM zijn "
    "de vestiging van de instelling, niet waar de student woont."
)
# De catalogus vraagt hier "In welke provincie wonen de meeste ingeschrevenen?". Herschreven, niet
# weggelaten: de vraag draagt ook de treffer op 'ingeschrevenen' (gouden set, tests/test_catalog_gouden_set.py).
_VOORBEELDVRAGEN = {
    "In welke provincie wonen de meeste ingeschrevenen?": (
        "In welke provincie liggen de vestigingen met de meeste ingeschrevenen?"
    ),
    "In welke provincie wonen de meeste eerstejaars ingeschrevenen?": (
        "In welke provincie liggen de vestigingen met de meeste eerstejaars ingeschrevenen?"
    ),
}


def kolomdefinities(columns: list[str], dataset_id: str) -> dict[str, str]:
    """De correcties voor de kolommen van deze dataset die er een hebben."""
    correcties = KOLOMCORRECTIES.get(dataset_id, {})
    return {kolom: correcties[kolom] for kolom in columns if kolom in correcties}


def _met_kolomcorrecties(entry: dict, dataset_id: str) -> dict:
    correcties = KOLOMCORRECTIES.get(dataset_id)
    if not correcties:
        return entry
    return {**entry, "_kolomdefinities": {**(entry.get("_kolomdefinities") or {}), **correcties}}


def _zonder_herkomstsuggestie(entry: dict, dataset_id: str) -> dict:
    if dataset_id not in _VESTIGING_NIET_HERKOMST:
        return entry
    vragen = [_VOORBEELDVRAGEN.get(v, v) for v in entry.get("voorbeeldvragen") or []]
    return {**entry, "voorbeeldvragen": vragen, "niet_geschikt_voor": NIET_GESCHIKT_VOOR_HERKOMST}


def catalogusrecord(entry: dict) -> dict:
    """Het catalogusrecord met de correcties; een record zonder correctie komt ongewijzigd terug."""
    dataset_id = entry.get("_ckan_id") or ""
    return _zonder_herkomstsuggestie(_met_kolomcorrecties(entry, dataset_id), dataset_id)
