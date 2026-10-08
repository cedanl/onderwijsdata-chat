"""Arbeidsmarkt na mbo/hbo/wo in de chat: UWV-vacatures en ROA-schoolverlatersinformatie (#441).

UWV is per provincie of gemeente, ROA landelijk of per arbeidsmarktregio of provincie; geen van
beide is per instelling. De data komt uit `data/arbeidsmarkt.py` (gedeeld met de dashboards,
CH-23) en elke aanroep loopt langs dezelfde scopepoort als CBS, DUO en RIO (`scope_blokkade`, CH-37). Elk getal komt uit de
bron, met de peildatum of versie uit de data zelf: tot CH-37 gaf get_roa_benchmark vaste,
in de code geschreven waarden ("~80%") als ROA-cijfers door.
"""

import json

from data import arbeidsmarkt

from . import fouten
from .catalog import catalogus_titel, scope_blokkade

UWV_ID = "uwv-open-match-data"
ROA_ID = "ais2030"
# Zoveel beroepenclusters in het resultaat; het totaal staat er altijd bij.
_MAX_CLUSTERS = 15
# De niveaukolommen zijn bij vacatures leeg; zonder deze regel las het model chauffeursbanen als hbo-vraag (#449).
_OPLEIDINGSNIVEAU = (
    "onbekend: UWV legt bij vacatures geen opleidingsniveau vast. Een sector telt ook banen op een ander "
    "niveau mee (bijv. chauffeurs bij TECHNIEK); het is geen vraag naar mbo-, hbo- of wo-gediplomeerden."
)
_TELLING_SECTOR = (
    "Een cluster dat {sector} deelt met andere sectoren van dezelfde indeling (hbo/wo of mbo) telt naar rato "
    "mee, bij twee sectoren voor de helft, naar beneden afgerond. Zo tellen de sectoren samen nooit op tot meer "
    "dan het totaal; de clustergetallen zelf zijn ongewogen."
)


def _json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _grootste_clusters(clusters: dict[str, int]) -> dict:
    """De grootste clusters (de invoer is aflopend), met een melding als er meer zijn."""
    uit: dict = {"clusters": dict(list(clusters.items())[:_MAX_CLUSTERS])}
    if len(clusters) > _MAX_CLUSTERS:
        uit["clusters_getoond"] = f"de {_MAX_CLUSTERS} grootste van {len(clusters)} beroepenclusters"
    return uit


def _sectordeel(clusters: dict[str, int], sector: str) -> dict:
    deel = arbeidsmarkt.sector_vacatures(clusters, sector)
    getoond = _grootste_clusters(deel.clusters)
    uit: dict = {"sector": sector, "vacatures_sector": deel.totaal} | getoond
    if deel.gedeeld:
        uit["telling_sector"] = _TELLING_SECTOR.format(sector=sector)
    if gedeeld := {c: deel.gedeeld[c] for c in getoond["clusters"] if c in deel.gedeeld}:
        uit["gedeelde_clusters"] = gedeeld
    return uit


def _geen_vacatures(provincie: str, gemeente: str | None) -> str:
    if gemeente and (gemeenten := arbeidsmarkt.gemeenten(provincie)):
        return f"Geen UWV-vacatures voor gemeente '{gemeente}' in {provincie}. Gemeenten: {gemeenten}."
    return f"Geen UWV-vacatures voor provincie '{provincie}'. Provincies: {arbeidsmarkt.provincies()}."


def get_uwv_vacatures(provincie: str, sector: str | None = None, gemeente: str | None = None) -> str:
    if blokkade := scope_blokkade(UWV_ID):
        return blokkade
    if sector and sector not in arbeidsmarkt.SECTOR_CLUSTER_MAP:
        return f"Sector '{sector}' is onbekend. Kies een van: {sorted(arbeidsmarkt.SECTOR_CLUSTER_MAP)}."
    try:
        stand = arbeidsmarkt.uwv_stand(provincie, gemeente)
        if stand is None:
            return _geen_vacatures(provincie, gemeente)
    except Exception as e:
        return fouten.bronfout("UWV", e)

    result = {
        "bron": catalogus_titel(UWV_ID),
        "dataset": UWV_ID,
        "peildatum": stand.peildatum,
        "momentopname": "Vacatures op de peildatum; geen actuele stand en geen reeks.",
        "provincie": provincie,
        **({"gemeente": gemeente} if gemeente else {}),
        "totaal_vacatures": stand.totaal,
        "opleidingsniveau": _OPLEIDINGSNIVEAU,
    }
    result |= _sectordeel(stand.clusters, sector) if sector else _grootste_clusters(stand.clusters)
    return _json(result)


def _roa_onderdelen(niveaus: tuple[str, ...], per_sector: bool, regio: str) -> dict:
    """Schoolverlaters en prognose voor de regio; een onderdeel zonder regionale cijfers is landelijk.

    Regionaal heeft ROA alleen de prognose (#450). Welke regio elk onderdeel draagt staat in
    `herkomst`, zodat een landelijk cijfer niet als regionaal wordt gelezen.
    """
    ophalen = {
        "schoolverlaters_sis_2024": arbeidsmarkt.roa_schoolverlaters,
        "prognose_tot_2030": arbeidsmarkt.roa_prognose,
    }
    landelijk = arbeidsmarkt.ROA_LANDELIJK
    if regio == landelijk:
        return {"regio": landelijk} | {k: f(niveaus, per_sector) for k, f in ophalen.items()}

    uit: dict = {"regio": regio, "regiotype": arbeidsmarkt.roa_regiotype(regio), "herkomst": {}}
    for onderdeel, f in ophalen.items():
        waarden = f(niveaus, per_sector, regio)
        uit[onderdeel] = waarden or f(niveaus, per_sector, landelijk)
        uit["herkomst"][onderdeel] = regio if waarden else landelijk
    if terugval := [k for k, r in uit["herkomst"].items() if r == landelijk]:
        uit["terugval"] = f"ROA heeft voor {regio} geen {' en '.join(terugval)}; daar staan de landelijke cijfers."
    return uit


def get_roa_benchmark(sector: str | None = None, regio: str | None = None) -> str:
    if blokkade := scope_blokkade(ROA_ID):
        return blokkade
    try:
        if sector:
            if sector not in (sectoren := arbeidsmarkt.roa_sectoren()):
                return f"ROA-opleidingssector '{sector}' is onbekend. Kies een van: {sectoren}."
            niveaus, per_sector = (sector,), True
        else:
            niveaus, per_sector = tuple(n for ns in arbeidsmarkt.ROA_NIVEAUS.values() for n in ns), False
        regionaam = arbeidsmarkt.roa_regio(regio) if regio else arbeidsmarkt.ROA_LANDELIJK
        if regionaam is None:
            return f"ROA-regio '{regio}' is onbekend. Kies een arbeidsmarktregio of provincie: {arbeidsmarkt.roa_regios()}."
        result = {
            "bron": f"ROA, {catalogus_titel(ROA_ID)}",
            "dataset": ROA_ID,
            "versie": arbeidsmarkt.roa_versie(),
            **_roa_onderdelen(niveaus, per_sector, regionaam),
        }
    except Exception as e:
        return fouten.bronfout("ROA", e)
    return _json(result)
