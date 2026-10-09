"""Koppelt een geladen dataset aan de zoekactie ervoor (#18).

Een miss in search_catalog is zeldzaam. Het echte faalsignaal is een hit met de verkeerde
dataset bovenaan: er komt gewoon een resultaat uit en niemand merkt iets. Laadt het model
daarna een dataset die niet in de top-3 van zijn laatste zoekactie stond, dan heeft het
moeten corrigeren. Dat staat als aparte regel in de logs (CATALOGUS_AFWIJKING), per model te tellen.
Elke regel draagt de catalogus_digest: een verschoven top-3 na een catalogusupdate is zo te
onderscheiden van een gedragswijziging (#344).

Per run, dus per sessie: een module-global zou gelijktijdige gebruikers door elkaar halen.
De zoekterm komt uit de vraag van de gebruiker en staat daarom alleen als lengte en hash in het
log, dezelfde als op de search_catalog-regel; de tekst zelf alleen op DEBUG (#475).
"""

import json
import logging
from dataclasses import dataclass, field

from core.logging_util import tekst_kenmerk
from tools.catalog import catalogus_digest
from tools.schemas import TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_GET_RIO_DATA, TOOL_SEARCH_CATALOG

logger = logging.getLogger(__name__)

_TOP = 3
_ID_FIELDS = ("_cbs_id", "_ckan_id", "_rio_resource")
_LOAD_ARGUMENT = {TOOL_GET_CBS_DATA: "dataset_id", TOOL_GET_DUO_DATA: "dataset_id", TOOL_GET_RIO_DATA: "resource"}


@dataclass
class SearchTrace:
    query: str | None = None
    top: list[str] | None = None
    loaded: list[str] = field(default_factory=list)
    catalogus_digest: str | None = None

    def note(self, name: str, args: dict | None, content: str) -> None:
        if name == TOOL_SEARCH_CATALOG:
            self._note_search(args or {}, content)
        elif name in _LOAD_ARGUMENT:
            self._note_load(str((args or {}).get(_LOAD_ARGUMENT[name]) or ""))

    def _note_search(self, args: dict, content: str) -> None:
        try:
            hits = json.loads(content)
        except (TypeError, ValueError):
            return  # "Geen resultaten": an unsuccessful search leaves the previous top as it was
        if not isinstance(hits, list):
            return
        ids = [next((h[f] for f in _ID_FIELDS if h.get(f)), None) for h in hits if "melding" not in h]
        self.query = args.get("query")
        self.top = [i for i in ids if i][:_TOP]
        self.catalogus_digest = catalogus_digest()

    def _note_load(self, dataset_id: str) -> None:
        if not dataset_id:
            return
        self.loaded.append(dataset_id)
        if self.top is None:
            logger.info("CATALOGUS_GELADEN geladen=%s zonder voorafgaande zoekactie", dataset_id)
            return
        # The model writes the query as JSON; str() keeps a non-string value from breaking the log call.
        kenmerk = tekst_kenmerk(str(self.query or ""), "query_")
        if dataset_id in self.top:
            logger.info(
                "CATALOGUS_GELADEN geladen=%s %s top3=%s afwijking=nee catalogus=%s",
                dataset_id,
                kenmerk,
                self.top,
                self.catalogus_digest,
            )
        else:
            logger.warning(
                "CATALOGUS_AFWIJKING geladen=%s %s top3=%s afwijking=ja catalogus=%s",
                dataset_id,
                kenmerk,
                self.top,
                self.catalogus_digest,
            )
        logger.debug("CATALOGUS ZOEKTERM  geladen=%s query=%r", dataset_id, self.query)
