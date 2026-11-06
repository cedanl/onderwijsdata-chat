"""Het bronblok van een dashboard (#904): per gebruikte bron wat de lading echt laadde.

De laders melden elk bestand dat ze met succes laadden (`core.brongebruik`): DUO in `_duo_load` van data/dashboard.py,
UWV en ROA in `_uwv` en `_roa` van data/arbeidsmarkt.py, LCSK in `_export` van data/dashboard_opleidingen.py. Een bron die niet laadde, meldt niets en staat er dus niet in;
hij staat in `niet_beschikbaar` (#901). Per dataset één regel, in de volgorde waarin het dashboard ze laadde:

- `bron`, `dataset`, `titel` en `url`: de titel en documentatielink uit de riodata-catalogus, zoals de chat de bron
  noemt (`catalogus_titel`).
- `editie`, `last_modified` en `peilmoment`: de versie van wat er geladen is. DUO: `last_modified` per bestand (#717)
  en het peilmoment in de woorden van de bronregel in de chat ("versie van 08-04-2026"). ROA: de editie uit het schema
  van riodata en de kolom `versie` van het bestand. UWV: geen editie; de momentopname heeft een peildatum.
  LCSK (de Studiekeuzedatabase, dashboard Opleidingen): het versienummer van de export als editie, en als peilmoment
  versie, exportdatum, NSE-jaar en 1cijferHO-jaar; `vermelding` is de bronregel met de zin die LCSK verplicht stelt.
- `peildatum`: DUO de teldatum uit de DUO-beschrijving ("1 oktober"), UWV de PEILDATUM uit de data.
- Een bron met een editie in plaats van een versie per bestand (de financiën van DUO, #935; WOPI van UNL, #936): de
  lader meldt editie, peildatum en versie zelf (`tools/financien._bron`, `tools/wo_personeel._wopi`), en titel en link
  als de catalogus de bron niet kent.
- `voorlopig` en `voorlopig_jaren`: de jaren die de DUO-beschrijving voorlopig noemt (gepind met de catalogus).
- `opgehaald_op`: het vroegste ophaalmoment van de bestanden, ISO met tijdzone.
"""

import functools
from collections.abc import Callable, Iterable, Mapping

import onderwijsbronnen

from tools import bestandsversie
from tools.scopeprofiel import dataset_id


@functools.cache
def _catalogus() -> dict[str, dict]:
    """Het catalogusrecord per dataset-ID, met het ID zoals de rest van de chat het leest (`scopeprofiel.dataset_id`,
    één lijst, #967/#971). De Studiekeuzedatabase staat niet in "all": de chat zoekt haar alleen waar de sleutel staat."""
    records = (*onderwijsbronnen.catalog(source="all"), *onderwijsbronnen.catalog(source="skdb"))
    return {dataset: record for record in records if (dataset := dataset_id(record))}


def _duo(meldingen: list[Mapping]) -> dict:
    """De bestanden van één DUO-dataset, elk één keer, en de jongste versie onder hen als peilmoment."""
    bestanden = {
        m["resource"]: {
            "resource": m["resource"],
            "resource_id": m.get("resource_id"),
            "last_modified": m.get("last_modified"),
        }
        for m in meldingen
    }
    versies = [b["last_modified"] for b in bestanden.values() if isinstance(b["last_modified"], str)]
    laatste = max(versies, default=None)
    return {
        "bestanden": list(bestanden.values()),
        "last_modified": laatste,
        "peilmoment": bestandsversie.peilmoment({"last_modified": laatste}),
    }


def _uwv(meldingen: list[Mapping]) -> dict:
    peildatum = meldingen[0].get("peildatum")
    return {"peildatum": peildatum, "peilmoment": f"peildatum {peildatum}" if peildatum else None}


def _roa(meldingen: list[Mapping]) -> dict:
    editie, versie = meldingen[0].get("editie"), meldingen[0].get("versie")
    delen = [f"editie {editie}" if editie else None, f"versie {versie}" if versie else None]
    return {"editie": editie, "versie": versie, "peilmoment": ", ".join(d for d in delen if d) or None}


def _lcsk(meldingen: list[Mapping]) -> dict:
    """De export van de Studiekeuzedatabase: het versienummer, de jaren en de vermelding die LCSK bij elke uiting
    verplicht stelt (art. 4 van de leveringsvoorwaarden: de zin, de link en de versie)."""
    melding = meldingen[0]
    return {
        "editie": melding.get("versie"),
        "peilmoment": melding.get("peilmoment"),
        "vermelding": melding["vermelding"],
    }


def _editie(meldingen: list[Mapping]) -> dict:
    melding = meldingen[0]
    editie, versie = melding.get("editie"), melding.get("versie")
    delen = [f"editie {editie}" if editie else None, f"versie van {versie}" if versie else None]
    uit = {
        "editie": editie,
        "peildatum": melding.get("peildatum"),
        "peilmoment": ", ".join(d for d in delen if d) or None,
    }
    return uit | {k: melding[k] for k in ("titel", "url") if melding.get(k)}


_VERSIE: dict[str, Callable[[list[Mapping]], dict]] = {"DUO": _duo, "UWV": _uwv, "ROA": _roa, "LCSK": _lcsk}
# Per dataset, vóór de regel van de bron: de financiën zijn DUO, maar zonder bestanden met een eigen versie.
_VERSIE_PER_DATASET: dict[str, Callable[[list[Mapping]], dict]] = {"financien": _editie, "unl:wopi": _editie}


def _regel(bron: str, dataset: str, meldingen: list[Mapping]) -> dict:
    record = _catalogus().get(dataset, {})
    tijd = (record.get("_zoekkaart") or {}).get("tijd") or {}
    voorlopig = [str(j) for j in tijd.get("voorlopig") or []]
    return {
        "bron": bron,
        "dataset": dataset,
        "titel": record.get("bron") or dataset,
        "url": (record.get("documentatie") or {}).get("url"),
        "editie": None,
        "last_modified": None,
        "peilmoment": None,
        "peildatum": tijd.get("peildatum"),
        **(_VERSIE_PER_DATASET.get(dataset) or _VERSIE[bron])(meldingen),
        "voorlopig": bool(voorlopig),
        "voorlopig_jaren": voorlopig,
        "opgehaald_op": min(m["opgehaald_op"] for m in meldingen),
    }


def blok(gemeld: Iterable[Mapping]) -> list[dict]:
    """De regels van het bronblok uit de meldingen van één lading; een dataset met meer bestanden is één regel."""
    per_dataset: dict[tuple[str, str], list[Mapping]] = {}
    for melding in gemeld:
        per_dataset.setdefault((melding["bron"], melding["dataset"]), []).append(melding)
    return [_regel(bron, dataset, meldingen) for (bron, dataset), meldingen in per_dataset.items()]
