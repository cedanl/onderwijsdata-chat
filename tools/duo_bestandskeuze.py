"""Welk DUO-bestand een totaal per instelling en jaar geeft (#325, #1238).

Een DUO-dataset heeft per sector meerdere bestanden met dezelfde telling en een andere
uitsplitsing (geslacht, opleidingsvorm, niveau opleiding). Elk bestand onderdrukt andere
kleine aantallen als -1, dus het totaal per instelling verschilt per bestand: Hanze 26.362
uit het geslacht-bestand van p01hoinges, 26.379 uit het opleidingsvorm-bestand. Zonder -1
in de selectie zijn de totalen gelijk; het verschil is alleen onderdrukking. Het model koos
per gesprek een ander bestand, en de standaard (index 0) was het geslacht-bestand, met de
meeste -1.

Keuze per instelling en jaar (#1238, besluit #1214): chat (`get_maat`) en dashboard
(`data/dashboard._load_ho_dataset`) nemen voor de ho-datasets p01hoinges, p02ho1ejrs,
p03hoinschr en p04hogdipl per (dataset, sector, instelling, jaar) hetzelfde bestand uit de
groep van die sector (`kies_rijen`). Tiebreak, in deze volgorde:
  1. het bestand met de minste onderdrukte cellen (-1) in de telkolom voor die instelling en dat jaar;
  2. bij een gelijk aantal onderdrukte cellen het hoogste totaal (zonder de -1);
  3. bij een nog gelijk totaal het bestand dat in de groep het eerst staat (deterministisch).
Zonder instelling (landelijk) telt de keuze de onderdrukte cellen per jaar over alle
instellingen samen. Een bestand zonder rijen voor die instelling en dat jaar doet niet mee.
Tot #1238 nam de chat per groep één bestand over alle jaren en voegde het dashboard de twee
geslacht-bestanden (resource 0 en 1) samen: voor dezelfde instelling en hetzelfde jaar gaven ze
een ander getal. Een vorm-filter (voltijd, deeltijd, duaal) kan alleen op het bestand met de
kolom OPLEIDINGSVORM; daar is er dus één kandidaat.

Het eerste ID van een groep heet nog het leidende bestand: dat bestand bleef over alle jaren het
minst onder het hoogste totaal per instelling (scripts/meet_duo_bestandskeuze.py, 09-10-2026). Het
is de standaard van get_duo_data zonder resource en het eerste bestand bij een gelijke stand. Voor
wo is dat steeds het opleidingsvorm-bestand; voor hbo wisselt het per dataset tussen niveau
opleiding en opleidingsvorm. Het geslacht-bestand komt overal het meest tekort. Bij mbo is het
bestand per instelling en leerweg leidend: de fijnere uitsplitsingen tellen honderden studenten
minder per instelling (mbo valt buiten de keuze per jaar).

Buiten de groepen een vaste standaard per dataset (#1033): de adressenbestanden hebben de
besturen op index 0 en de instellingen (met BRIN) op index 1; zonder resource het tweede.
Die staan bewust niet in de groepen: ze tellen niets, dus geen tekst over onderdrukte cellen.

Op resource-ID, niet op index: de ID's zijn stabiel. Een ID dat de catalogus niet meer
kent, geeft geen keuze; test_duo_bestandskeuze houdt de ID's bij de gepinde catalogus.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pandas as pd

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

# Per dataset zonder groep het bestand als het model er geen noemt (#1033): de adressen van de instellingen,
# met INSTELLINGSCODE, niet die van de besturen op index 0.
_STANDAARD: dict[str, str] = {
    "adressen_ho": "bf1da9c6-c688-4873-91b1-b12c9ac2c132",  # Adressen van instellingen in het hoger onderwijs
    "adressen_mbo": "1a946297-a7ca-48d5-9ae8-19ad73bf8176",  # Adressen instellingen
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


def titel(dataset_id: str, index: int) -> str:
    """De naam van bestand `index` in de catalogus; de index zelf als de catalogus hem niet kent."""
    bestanden = _bestanden(dataset_id)
    return bestanden[index].get("naam", str(index)) if 0 <= index < len(bestanden) else str(index)


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
    """Het bestand als het model er geen noemt: de vaste standaard, anders het leidende van de eerste groep, anders 0."""
    if dataset_id in _STANDAARD:
        eerste = _indexen(dataset_id, (_STANDAARD[dataset_id],))[0]
    elif groepen := _GROEPEN.get(dataset_id):
        eerste = _indexen(dataset_id, groepen[0][:1])[0]
    else:
        eerste = None
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
    keuze = (
        " Een vaste maat (get_maat) kiest voor een totaal per instelling zelf per instelling en jaar het bestand met de "
        "minste onderdrukte cellen."
        if dataset_id in TELKOLOMMEN
        else ""
    )
    return (
        f"Voor een totaal per instelling is get_duo_data('{dataset_id}', {index}) leidend "
        f"('{_naam(dataset_id, index)}'): daarin zijn over alle jaren de minste cellen onderdrukt. Dit bestand "
        "onderdrukt andere kleine aantallen, dus een totaal hieruit valt meestal lager uit. Gebruik het "
        f"alleen voor de uitsplitsing die alleen dit bestand heeft.{keuze}"
    )


def noot(dataset_id: str, resource: int | str | None) -> str | None:
    """Voor het Telling-blok bij een ondergrens: uit welk bestand, en dat de andere afwijken."""
    index = leidend(dataset_id, resource)
    if index is None or not isinstance(resource, int):
        return None
    keuze = f"totalen uit bestand '{_naam(dataset_id, resource)}'"
    if index == resource:
        keuze += ", het leidende bestand voor totalen per instelling (over alle jaren de minste onderdrukte cellen)"
    else:
        keuze += f"; leidend voor totalen per instelling is '{_naam(dataset_id, index)}' (over alle jaren)"
    per_jaar = (
        " Een vaste maat en het dashboard kiezen per instelling en jaar het bestand met de minste onderdrukte cellen."
        if dataset_id in TELKOLOMMEN
        else ""
    )
    return (
        f"{keuze}. De andere bestanden van deze dataset splitsen anders uit en onderdrukken "
        f"andere cellen; hun totalen wijken daardoor af.{per_jaar}"
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


# --- De keuze per instelling en jaar (#1238) ---------------------------------------------------------------------------

# Per ho-dataset de jaar- en de telkolom: de keuze telt de onderdrukte cellen (-1) in de telkolom.
TELKOLOMMEN: dict[str, tuple[str, str]] = {
    "p01hoinges": ("STUDIEJAAR", "AANTAL_INGESCHREVENEN"),
    "p02ho1ejrs": ("STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"),
    "p03hoinschr": ("STUDIEJAAR", "AANTAL_INSCHRIJVINGEN"),
    "p04hogdipl": ("DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"),
}
INSTELLINGSKOLOM = "INSTELLINGSCODE_ACTUEEL"
# De groepen van een ho-dataset in _GROEPEN, in deze volgorde: eerst hbo, dan wo.
HO_SECTOREN = ("hbo", "wo")

KEUZEREGEL = (
    "per instelling en jaar het bestand met de minste onderdrukte cellen (-1); bij een gelijk aantal het hoogste "
    "totaal, bij een nog gelijk totaal het eerste bestand van de groep"
)


@dataclass(frozen=True)
class Telling:
    """Wat één bestand voor één instelling (of landelijk) in één jaar telt."""

    onderdrukt: int  # cellen met -1 in de telkolom
    totaal: float  # de som van de telkolom zonder de -1


def _rang(telling: Telling) -> tuple[int, float]:
    return telling.onderdrukt, -telling.totaal


def kies(tellingen: Sequence[Telling | None]) -> int | None:
    """De positie van het gekozen bestand in `tellingen` (in groepsvolgorde); None als geen bestand rijen heeft.

    Eerst de minste onderdrukte cellen, dan het hoogste totaal, dan het eerste in de groep. None is een bestand zonder
    rijen voor die instelling en dat jaar: dat doet niet mee.
    """
    beste: tuple[tuple[int, float], int] | None = None
    for positie, telling in enumerate(tellingen):
        if telling is not None and (beste is None or _rang(telling) < beste[0]):
            beste = (_rang(telling), positie)
    return None if beste is None else beste[1]


def kandidaten(dataset_id: str, sector: str) -> list[int]:
    """De indexen van de bestanden van een ho-sector (hbo, wo), in groepsvolgorde; leeg zonder groep."""
    groepen = _GROEPEN.get(dataset_id, ()) if dataset_id in TELKOLOMMEN else ()
    if sector not in HO_SECTOREN or len(groepen) != len(HO_SECTOREN):
        return []
    return [i for i in _indexen(dataset_id, groepen[HO_SECTOREN.index(sector)]) if i is not None]


def geslachtbestanden(dataset_id: str) -> list[int]:
    """Per ho-sector het bestand met de kolom GESLACHT (de verdeling naar geslacht staat alleen daarin)."""
    return [
        i
        for sector in HO_SECTOREN
        for i in kandidaten(dataset_id, sector)
        if "geslacht" in _naam(dataset_id, i).lower()
    ]


def _sleutelkolommen(periodekolom: str, instellingskolom: str | None) -> list[str]:
    return [instellingskolom, periodekolom] if instellingskolom else [periodekolom]


def _sleutel(waarde) -> tuple[str, int] | int:
    if isinstance(waarde, tuple):
        code, jaar = waarde
        return str(code), int(jaar)
    return int(waarde)


def tellingen(
    df: pd.DataFrame,
    cellen: pd.DataFrame | None,
    periodekolom: str,
    waardekolom: str,
    instellingskolom: str | None = INSTELLINGSKOLOM,
) -> dict:
    """Per (instellingscode, jaar), of per jaar zonder instellingskolom (landelijk), de telling van één bestand.

    `df` is gemaskeerd en `cellen` zijn zijn onderdrukte cellen zoals `core.sentinels.mask_sentinels` ze geeft (index
    van df, per kolom 0/1). Zonder `cellen` maskeert deze functie zelf: dan mag `df` nog -1 hebben.
    """
    from core.sentinels import mask_sentinels  # lazy: core.sentinels leest de domeinregels

    if cellen is None:
        df, cellen = mask_sentinels(df)
    kolommen = _sleutelkolommen(periodekolom, instellingskolom)
    onderdrukt = (
        cellen[waardekolom].reindex(df.index, fill_value=0)
        if waardekolom in cellen.columns
        else pd.Series(0, index=df.index)
    )
    per = df[kolommen].assign(_onderdrukt=onderdrukt, _totaal=pd.to_numeric(df[waardekolom], errors="coerce"))
    som = per.groupby(kolommen if instellingskolom else periodekolom, dropna=True)[["_onderdrukt", "_totaal"]].sum()
    return {
        _sleutel(sleutel): Telling(int(rij["_onderdrukt"]), float(rij["_totaal"])) for sleutel, rij in som.iterrows()
    }


@dataclass(frozen=True)
class Keuze:
    """De rijen uit de gekozen bestanden: per sleutel (instellingscode en jaar, of jaar) de rijen van één bestand."""

    rijen: pd.DataFrame  # gemaskeerd, index 0..n-1
    cellen: pd.DataFrame  # de onderdrukte cellen van die rijen, zoals mask_sentinels (alleen rijen met een cel)
    bestand: Mapping = field(default_factory=dict)  # sleutel -> index van het gekozen bestand

    def gebruikt(self) -> list[int]:
        """De bestanden waaruit minstens één sleutel komt, in de volgorde van hun eerste jaar en dan hun index."""
        return sorted(
            set(self.bestand.values()), key=lambda i: (min(_jaar(s) for s, b in self.bestand.items() if b == i), i)
        )

    def per_jaar(self) -> dict[int, list[int]]:
        """Per jaar de gekozen bestanden (meer dan één als de instellingscodes verschillend kozen)."""
        uit: dict[int, set[int]] = {}
        for sleutel, index in self.bestand.items():
            uit.setdefault(_jaar(sleutel), set()).add(index)
        return {jaar: sorted(uit[jaar]) for jaar in sorted(uit)}


def _jaar(sleutel) -> int:
    return sleutel[1] if isinstance(sleutel, tuple) else sleutel


def kies_rijen(
    bestanden: Sequence[tuple[int, pd.DataFrame, pd.DataFrame | None]],
    periodekolom: str,
    waardekolom: str,
    instellingskolom: str | None = INSTELLINGSKOLOM,
) -> Keuze:
    """Kies per instelling en jaar (of per jaar zonder instellingskolom) één bestand en geef zijn rijen.

    `bestanden`: (index, gemaskeerde rijen, cellen) per kandidaat, in groepsvolgorde (`kandidaten`); cellen None
    laat de functie zelf maskeren. Chat en dashboard roepen dit allebei aan, dus ze kiezen hetzelfde bestand.
    """
    from core.sentinels import mask_sentinels

    klaar = [(index, *((df, cellen) if cellen is not None else mask_sentinels(df))) for index, df, cellen in bestanden]
    per_bestand = [tellingen(df, cellen, periodekolom, waardekolom, instellingskolom) for _, df, cellen in klaar]
    alle = dict.fromkeys(s for telling in per_bestand for s in telling)
    gekozen = {
        sleutel: klaar[positie][0]
        for sleutel in alle
        if (positie := kies([telling.get(sleutel) for telling in per_bestand])) is not None
    }
    rijen, cellen = [], []
    for index, df, bestandscellen in klaar:
        eigen = [s for s, i in gekozen.items() if i == index]
        if not eigen:
            continue
        if instellingskolom:
            sleutels = pd.MultiIndex.from_arrays([df[instellingskolom].astype(str), df[periodekolom]])
            masker = sleutels.isin(eigen)
        else:
            masker = df[periodekolom].isin(eigen)
        rijen.append(df[masker])
        cellen.append(bestandscellen.reindex(df.index[masker], fill_value=0))
    if not rijen:
        leeg = klaar[0][1].iloc[0:0] if klaar else pd.DataFrame()
        return Keuze(leeg.reset_index(drop=True), pd.DataFrame(index=pd.RangeIndex(0)), {})
    samen = pd.concat(rijen, ignore_index=True)
    alle_cellen = pd.concat(cellen, ignore_index=True).fillna(0).astype(int)
    return Keuze(samen, alle_cellen[alle_cellen.any(axis=1)], gekozen)
