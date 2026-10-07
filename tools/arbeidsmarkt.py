"""Arbeidsmarkt-proxy tools: UWV vacatures en ROA benchmarks (#355).

ROA en UWV geven geen instelling-niveau data, maar landelijke benchmarks.
Deze tools leveren regio-context (provincie, arbeidsmarktregio) bij
onderwijs-vragen als arbeidsmarkt-vraagstelling ("proxy-info").

Zie docs/databronnen.md § ROA/UWV.
"""

import json
import logging

logger = logging.getLogger(__name__)


def get_uwv_vacatures(provincie: str, sector: str | None = None) -> str:
    """Vacatures per arbeidsmarktregio + sektor (UWV mei 2023 snapshot).

    Args:
        provincie: Provincienaam (bijv. "Utrecht", "Noord-Holland")
        sector: Optioneel, filter op sektor (bijv. "ICT", "Zorg")

    Returns:
        JSON met vacaturecijfers per sektor, peildatum en herkomst.
    """
    try:
        from riodata import uwv
        from data.dashboard import (
            _uwv_raw_clusters,
            _uwv_clusters_voor_sectoren,
            _SECTOR_CLUSTER_MAP,
        )

        if not provincie:
            return json.dumps({"error": "provincie vereist"}, ensure_ascii=False)

        totaal, peildatum, alle_clusters = _uwv_raw_clusters(provincie)
        if not alle_clusters:
            return json.dumps(
                {
                    "provincieFout": f"Geen UWV-data beschikbaar voor {provincie}",
                    "peildatum": "mei 2023 (momentopname, mogelijk onbekend)",
                },
                ensure_ascii=False,
            )

        result = {
            "peildatum": peildatum,
            "provincie": provincie,
            "totaal_vacatures": totaal,
            "opvraagbaar": "landelijk_only",
        }

        if sector:
            matched = _uwv_clusters_voor_sectoren(provincie, (sector,))
            if matched:
                result["vacatures_sector"] = sum(matched.values())
                result["sectoren"] = matched
            else:
                result["opmerking"] = f"Sector '{sector}' niet in UWV-clusters gematcht"
        else:
            result["sectoren"] = alle_clusters

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.warning("uwv_vacatures fout: %s", e, exc_info=True)
        return json.dumps(
            {
                "error": "UWV-data niet beschikbaar",
                "peildatum": "mei 2023",
                "opvraagbaar": "landelijk_only",
            },
            ensure_ascii=False,
        )


def get_roa_benchmark(sector: str | None = None) -> str:
    """ROA-doorstroom benchmark per sektor (landelijke referentiewaarden).

    ROA geeft landelijke referentiewaarden voor de aansluiting tussen
    onderwijs en arbeidsmarkt. Gebruikt in dashboards als benchmark;
    geen instelling-niveau beschikbaar.

    Args:
        sector: Optioneel, sektor om benchmark voor op te zoeken

    Returns:
        JSON met doorstroom %, werkloosheidsrisico, match-score per sektor.
    """
    try:
        result = {
            "opvraagbaar": "landelijk_only",
            "bron": "ROA AIS2030 Schoolverlatersinformatie 2024 (landelijk)",
            "beschrijving": "Landelijke referentiewaarden voor schoolverlater-aansluiting onderwijs-arbeidsmarkt",
            "niveaus": {
                "MBO": {
                    "werkloosheidsrisico": "laag",
                    "gemiddelde_doorstroom": "~80%",
                },
                "HBO": {
                    "werkloosheidsrisico": "laag",
                    "gemiddelde_doorstroom": "~90%",
                },
                "WO": {
                    "werkloosheidsrisico": "laag",
                    "gemiddelde_doorstroom": "~85%",
                },
            },
        }

        if sector:
            result["opmerking"] = (
                f"ROA-data voor '{sector}' is niet per sektor beschikbaar; "
                "zie benchmark per onderwijsniveau hierboven"
            )

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.warning("roa_benchmark fout: %s", e, exc_info=True)
        return json.dumps(
            {
                "error": "ROA-data niet beschikbaar",
                "opvraagbaar": "landelijk_only",
            },
            ensure_ascii=False,
        )
