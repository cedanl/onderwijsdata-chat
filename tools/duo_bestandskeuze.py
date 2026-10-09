"""Welk DUO-bestand leidend is voor een totaal per instelling (#325).

Een DUO-dataset heeft per sector meerdere bestanden met dezelfde telling en een andere
uitsplitsing (geslacht, opleidingsvorm, niveau opleiding). Elk bestand onderdrukt andere
kleine aantallen als -1, dus het totaal per instelling verschilt per bestand: Hanze 26.362
uit het geslacht-bestand van p01hoinges, 26.379 uit het opleidingsvorm-bestand. Zonder -1
in de selectie zijn de totalen gelijk; het verschil is alleen onderdrukking. Het model koos
per gesprek een ander bestand, en de standaard (index 0) was het geslacht-bestand, met de
meeste -1.

Leidend is per groep het bestand dat over alle jaren het minst onder het hoogste totaal per
instelling blijft (scripts/meet_duo_bestandskeuze.py, 09-10-2026). Voor wo is dat steeds
het opleidingsvorm-bestand; voor hbo wisselt het per dataset tussen niveau opleiding en
opleidingsvorm. Het geslacht-bestand komt overal het meest tekort. Bij mbo is het bestand
per instelling en leerweg leidend: de fijnere uitsplitsingen tellen honderden studenten
minder per instelling.

Op resource-ID, niet op index: de ID's zijn stabiel. Een ID dat de catalogus niet meer
kent, geeft geen keuze; test_duo_bestandskeuze houdt de ID's bij de gepinde catalogus.
"""

from . import duo_meta

# Per dataset de groepen bestanden met dezelfde telling; het eerste ID is leidend.
_GROEPEN: dict[str, tuple[tuple[str, ...], ...]] = {
    "p01hoinges": (
        (  # hbo: niveau opleiding, geslacht, opleidingsvorm
            "7761bd6a-b87b-4389-a943-829872116f92",
            "c454d7e1-b9b1-4460-b9ff-55938c85788e",
            "ef11448c-e8c3-4afe-899f-67f90a3c3be0",
        ),
        (  # wo: opleidingsvorm, geslacht, niveau opleiding
            "f9a16992-8f11-4579-809c-bcdbc93c9d2b",
            "b88721ef-9787-4299-afc7-5d74380d29ba",
            "6a7e10c1-6ae8-4949-89da-b6e59151698c",
        ),
    ),
    "p02ho1ejrs": (
        (  # hbo: opleidingsvorm, geslacht, niveau opleiding
            "2ddccc54-ae20-45dd-ba0a-5af9a69ef713",
            "5338f63e-af6a-434c-8086-c4584767c3fc",
            "0f594842-cca9-4f17-8cbc-e502dba408b4",
        ),
        (  # wo: opleidingsvorm, geslacht, niveau opleiding
            "5639a642-bf6a-4fad-a8ab-d4bf62010c0c",
            "2e0a58a1-f7aa-4ed6-9a76-65bc569edcfc",
            "1a67316d-db9f-415c-8057-8c47bee19d44",
        ),
    ),
    "p03hoinschr": (
        (  # hbo: niveau opleiding, geslacht, opleidingsvorm
            "9ec2ffc8-6121-485f-acda-1838d8c44a93",
            "50c36789-8073-41ad-88bd-5dc178d091cb",
            "6a012a57-4664-4e6c-bd4a-82c7e3f587cd",
        ),
        (  # wo: opleidingsvorm, geslacht, niveau opleiding
            "2a95ae4e-3d9b-49cf-bebd-5a3e5a289e52",
            "3cd18619-a881-4ec5-bba1-53cd47af712c",
            "84b7bec1-0774-4e0a-bcdf-1ac460f2fc2e",
        ),
    ),
    "p04hogdipl": (
        (  # hbo: opleidingsvorm, geslacht, niveau opleiding
            "3f2541ca-6acd-4b98-ac08-7b68d05bb06a",
            "e7b2aabd-1c10-4990-a33c-bf558f02ed12",
            "0488fa97-d0ba-4285-9569-19bf26050204",
        ),
        (  # wo: opleidingsvorm, geslacht, niveau opleiding
            "63dc7252-5538-42b1-98ac-19b8ba7522dd",
            "4938e55f-45f5-4f74-a512-baa2db99f5a9",
            "b74aeac5-ea8c-4697-a909-3aaae7e25f09",
        ),
    ),
    "mbo-studenten-per-instelling": (
        (  # per instelling en leerweg, dan sectorkamer en de fijnere uitsplitsingen
            "0f1fba7c-5003-459d-8845-20ff055b9dc1",
            "8d25e951-92ed-48ca-b4a9-4185f4835748",
            "0cf33778-666c-4a6d-bd58-0b4d1ddefb61",
            "2442d620-b5ac-42ba-92ea-f7b3c31e918e",
            "4ca1ec61-61aa-46f2-b01f-b657633fadf0",
            "99053b39-5852-4645-914c-d6d16421b266",
        ),
    ),
}

# Prognosebestanden met een terugblik ('Historie'): voor gerealiseerde aantallen geldt het
# bestand ernaast. De Historie-jaren van de mbo-prognose volgen bol en bbl zonder
# examendeelnemers (EX), op enkele studenten na; ROC Mondriaan 2025: 14.517 tegen 14.519 (#442).
_REALISATIE: dict[str, tuple[str, str]] = {
    "studentprognoses-mbo-per-instelling": ("mbo-studenten-per-instelling", "0f1fba7c-5003-459d-8845-20ff055b9dc1"),
}


def _bestanden(dataset_id: str) -> list[dict]:
    return duo_meta.record(dataset_id).get("_resources") or []


def _indexen(dataset_id: str, ids: tuple[str, ...]) -> list[int | None]:
    positie = {r.get("id"): i for i, r in enumerate(_bestanden(dataset_id))}
    return [positie.get(i) for i in ids]


def _naam(dataset_id: str, index: int) -> str:
    return _bestanden(dataset_id)[index].get("naam", str(index))


def leidende_ids(dataset_id: str) -> set[str]:
    """De resource-ID's die leidend zijn voor een totaal per instelling."""
    return {groep[0] for groep in _GROEPEN.get(dataset_id, ())}


def leidend(dataset_id: str, resource: int | str | None) -> int | None:
    """De index van het leidende bestand in de groep van dit bestand; None zonder groep."""
    for groep in _GROEPEN.get(dataset_id, ()):
        indexen = _indexen(dataset_id, groep)
        if resource in indexen and indexen[0] is not None:
            return indexen[0]
    return None


def standaard(dataset_id: str) -> int:
    """Het bestand als het model er geen noemt: het leidende van de eerste groep, anders 0."""
    groepen = _GROEPEN.get(dataset_id)
    eerste = _indexen(dataset_id, groepen[0][:1])[0] if groepen else None
    return eerste if eerste is not None else 0


def melding(dataset_id: str, resource: int | str) -> str | None:
    """Voor get_duo_data: welk bestand leidend is als dit het niet is; None als het dat wel is."""
    if dataset_id in _REALISATIE:
        andere, id_ = _REALISATIE[dataset_id]
        index = _indexen(andere, (id_,))[0]
        bron = andere if index is None else f"get_duo_data('{andere}', {index})"
        return (
            "Prognosebestand: gebruik het voor prognosejaren (Type 'Prognose'). De jaren met Type "
            "'Historie' zijn de terugblik van de prognose en wijken licht af van de gerealiseerde aantallen. "
            f"Voor een gerealiseerd aantal per instelling is {bron} leidend."
        )
    index = leidend(dataset_id, resource)
    if index is None or index == resource:
        return None
    return (
        f"Voor een totaal per instelling is get_duo_data('{dataset_id}', {index}) leidend "
        f"('{_naam(dataset_id, index)}'): daarin zijn de minste cellen onderdrukt. Dit bestand "
        "onderdrukt andere kleine aantallen, dus een totaal hieruit valt meestal lager uit. Gebruik het "
        "alleen voor de uitsplitsing die alleen dit bestand heeft."
    )


def noot(dataset_id: str, resource: int | str | None) -> str | None:
    """Voor het Telling-blok bij een ondergrens: uit welk bestand, en dat de andere afwijken."""
    index = leidend(dataset_id, resource)
    if index is None or not isinstance(resource, int):
        return None
    keuze = f"totalen uit bestand '{_naam(dataset_id, resource)}'"
    if index == resource:
        keuze += ", het leidende bestand voor totalen per instelling"
    else:
        keuze += f"; leidend voor totalen per instelling is '{_naam(dataset_id, index)}'"
    return (
        f"{keuze}. De andere bestanden van deze dataset splitsen anders uit en onderdrukken "
        "andere cellen; hun totalen wijken daardoor af."
    )


def historienoot(dataset_id: str, selectie) -> str | None:
    """Voor het Telling-blok: een selectie uit een prognosebestand met Historie-jaren.

    Zonder kolom Type is niet te zien welke jaren het zijn; dan staat de noot er ook.
    """
    if dataset_id not in _REALISATIE:
        return None
    if "Type" in selectie.columns and not (selectie["Type"] == "Historie").any():
        return None
    andere, _ = _REALISATIE[dataset_id]
    return (
        "jaren met Type 'Historie' komen uit het prognosebestand en wijken licht af van de "
        f"gerealiseerde aantallen in {andere}."
    )
