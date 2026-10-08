"""Arbeidsmarkt na mbo/hbo/wo in de chat: UWV-vacatures en ROA-schoolverlatersinformatie (#441).

Beide bronnen zijn landelijk of per provincie, niet per instelling. De data komt uit
`data/arbeidsmarkt.py` (gedeeld met de dashboards, CH-23) en elke aanroep loopt langs
dezelfde scopepoort als CBS, DUO en RIO (`scope_blokkade`, CH-37). Elk getal komt uit de
bron, met de peildatum of versie uit de data zelf: tot CH-37 gaf get_roa_benchmark vaste,
in de code geschreven waarden ("~80%") als ROA-cijfers door.
"""

import json

from data import arbeidsmarkt

from . import fouten
from .catalog import catalogus_titel, scope_blokkade

UWV_ID = "uwv-open-match-data"
ROA_ID = "ais2030"
# Zoveel beroepenclusters zonder sectorfilter; het totaal staat er altijd bij.
_MAX_CLUSTERS = 15


def _json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def get_uwv_vacatures(provincie: str, sector: str | None = None) -> str:
    if blokkade := scope_blokkade(UWV_ID):
        return blokkade
    if sector and sector not in arbeidsmarkt.SECTOR_CLUSTER_MAP:
        return f"Sector '{sector}' is onbekend. Kies een van: {sorted(arbeidsmarkt.SECTOR_CLUSTER_MAP)}."
    try:
        stand = arbeidsmarkt.uwv_stand(provincie)
        if stand is None:
            return f"Geen UWV-vacatures voor provincie '{provincie}'. Provincies: {arbeidsmarkt.provincies()}."
    except Exception as e:
        return fouten.bronfout("UWV", e)

    result = {
        "bron": catalogus_titel(UWV_ID),
        "dataset": UWV_ID,
        "peildatum": stand.peildatum,
        "momentopname": "Vacatures op de peildatum; geen actuele stand en geen reeks.",
        "provincie": provincie,
        "totaal_vacatures": stand.totaal,
    }
    if sector:
        clusters = arbeidsmarkt.relevante_clusters(stand.clusters, (sector,))
        result |= {"sector": sector, "vacatures_sector": sum(clusters.values()), "clusters": clusters}
    else:
        result["clusters"] = dict(list(stand.clusters.items())[:_MAX_CLUSTERS])
        if len(stand.clusters) > _MAX_CLUSTERS:
            result["clusters_getoond"] = f"de {_MAX_CLUSTERS} grootste van {len(stand.clusters)} beroepenclusters"
    return _json(result)


def get_roa_benchmark(sector: str | None = None) -> str:
    if blokkade := scope_blokkade(ROA_ID):
        return blokkade
    try:
        if sector:
            if sector not in (sectoren := arbeidsmarkt.roa_sectoren()):
                return f"ROA-opleidingssector '{sector}' is onbekend. Kies een van: {sectoren}."
            niveaus, per_sector = (sector,), True
        else:
            niveaus, per_sector = tuple(n for ns in arbeidsmarkt.ROA_NIVEAUS.values() for n in ns), False
        result = {
            "bron": f"ROA, {catalogus_titel(ROA_ID)}",
            "dataset": ROA_ID,
            "versie": arbeidsmarkt.roa_versie(),
            "regio": arbeidsmarkt.ROA_LANDELIJK,
            "schoolverlaters_sis_2024": arbeidsmarkt.roa_schoolverlaters(niveaus, per_sector),
            "prognose_tot_2030": arbeidsmarkt.roa_prognose(niveaus, per_sector),
        }
    except Exception as e:
        return fouten.bronfout("ROA", e)
    return _json(result)
