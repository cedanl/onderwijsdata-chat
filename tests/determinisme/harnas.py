"""Meet determinisme zonder netwerk en zonder model (#347).

Drie metingen op een vaste gevallenset:

- **plan-invariantie**: N gegenereerde spellingen van dezelfde aanroep → unieke plan-digests
  (hoort 1 te zijn);
- **golden stand**: plan-digest, het compilaat van een gesloten selectie (#343) en de
  uitkomst-digest van uitvoerbare gevallen tegen `gevallen.json`;
- **reparatie-/weigeringsgraad**: wat de periodeherstelroute (#342) op een vaste sample doet.

De scorekaart is gekoppeld aan de promptversie (hash van prompts/system.md), het
geconfigureerde model en de toolschema-digest: zo is een meting achteraf toe te schrijven.
"""

import hashlib
import json
import random
from datetime import date
from pathlib import Path

import pandas as pd

from core.config import MODEL
from tools import canoniek, store
from tools.cbs_selectie import compileer
from tools.query import query_data

from .varianten import variant

GOLDEN = Path(__file__).parent / "gevallen.json"
_PROMPT = Path(__file__).resolve().parent.parent.parent / "prompts" / "system.md"
AANTAL_VARIANTEN = 40
SEED = 347

# Dimensies van de fixture-CBS-tabel, zoals DataProperties ze zou geven.
COL_DEFS = {
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Opleidingsfase": {"type": "Dimension", "title": "Opleidingsfase"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "Aantal_1": {"type": "Topic", "title": "Aantal"},
}

# (id, toelichting, tool, canonieke args). De argumenten zijn de canonieke spelling;
# varianten.py maakt er per meting N gelijkwaardige spellingen van.
GEVALLEN: list[tuple[str, str, str, dict]] = [
    (
        "duo-filter-geslacht",
        "eq/__in-vormen, waardenkast en sleutelvolgorde op een DUO-selectie",
        "query_data",
        {"data_key": "duo:fx:geslacht", "filters": {"GESLACHT": "Man"}},
    ),
    (
        "duo-periode-studiejaar",
        "schooljaarspelling op STUDIEJAAR (2023, 2023/24, 2023-2024, 2023SJ00)",
        "query_data",
        {"data_key": "duo:fx:geslacht", "filters": {"STUDIEJAAR": 2023, "GESLACHT": "Vrouw"}},
    ),
    (
        "duo-groepering",
        "groepering met aggregatie; max_rows op de default is dezelfde aanroep",
        "query_data",
        {"data_key": "duo:fx:geslacht", "group_by": ["GESLACHT"], "aggregate": {"AANTAL": "sum"}},
    ),
    (
        "cbs-rauwe-filter",
        "OData-spatiëring buiten literals en de default $top (interne filters-route)",
        "get_cbs_data",
        {"dataset_id": "fx", "filters": {"$filter": "Geslacht eq 'T001038' and Perioden eq '2024SJ00'"}},
    ),
    (
        "cbs-selectie",
        "gesloten selectie (#343): dimensievolgorde, codelijsten en periodespelling",
        "get_cbs_data",
        {
            "dataset_id": "fx",
            "selectie": {"dimensies": {"Geslacht": "T001038", "Opleidingsfase": "*"}, "periode": ["2024/25"]},
        },
    ),
    (
        "cbs-selectie-bereik",
        "periodebereik: van/tot is volgorde-ongevoelig en spelling-ongevoelig",
        "get_cbs_data",
        {
            "dataset_id": "fx",
            "selectie": {
                "dimensies": {"Geslacht": "*", "Opleidingsfase": "*"},
                "periode": {"van": "2020/21", "tot": "2022/23"},
            },
        },
    ),
    (
        "kpi-op-selectie",
        "compute_kpi: data_key-spelling en argumentvolgorde",
        "compute_kpi",
        {"data_key": "cbs:fx", "metric": "last", "value_column": "Aantal_1", "label": "aantal"},
    ),
]

# Vaste sample voor de reparatie-/weigeringsgraad van de periodeherstelroute (#342).
HERSTEL_SAMPLE: list[tuple[str, str, dict, str]] = [
    ("herstel-studiejaar-label", "duo:fx:geslacht", {"STUDIEJAAR": "2023/24"}, "herstel"),
    ("herstel-cbs-label", "cbs:fx", {"Perioden_label": "2024/25"}, "herstel"),
    ("herstel-cbs-code-uit-label", "cbs:fx", {"Perioden": "2024-2025"}, "herstel"),
    ("exacte-spelling-blijft", "duo:fx:geslacht", {"STUDIEJAAR": 2023}, "geen"),
    ("weigering-buiten-vocabulaire", "duo:fx:geslacht", {"STUDIEJAAR": "2015/16"}, "weigering"),
]


def fixtures() -> None:
    """Vaste frames in de store; dezelfde data bij elke meting."""
    store.put(
        "duo:fx:geslacht",
        pd.DataFrame(
            {
                "GESLACHT": ["Man", "Vrouw", "Man", "Vrouw"],
                "STUDIEJAAR": [2022, 2022, 2023, 2023],
                "AANTAL": [100, 110, 120, 130],
            }
        ),
        store.KeyMeta(bron="duo", dataset="fx", resource=1, periodekolom="STUDIEJAAR"),
    )
    store.put(
        "cbs:fx",
        pd.DataFrame(
            {
                "Geslacht": ["T001038", "T001038"],
                "Perioden": ["2023SJ00", "2024SJ00"],
                "Perioden_label": ["2023/'24", "2024/'25"],
                "Aantal_1": [500, 510],
            }
        ),
        store.KeyMeta(bron="cbs", dataset="fx", periodekolom="Perioden"),
    )


def digests_van_varianten(tool: str, args: dict, aantal: int = AANTAL_VARIANTEN) -> set[str]:
    """De unieke plan-digests van `aantal` gegenereerde spellingen plus de canonieke."""
    rng = random.Random(SEED)
    digests = {canoniek.digest(tool, args)}
    digests.update(canoniek.digest(tool, variant(rng, tool, args)) for _ in range(aantal))
    return digests


def _uitkomst_digest(tool: str, args: dict) -> str | None:
    """De digest van de uitvoering, voor gevallen die zonder netwerk draaien."""
    if tool != "query_data":
        return None
    fixtures()
    return hashlib.sha256(query_data(**args).encode()).hexdigest()[:12]


def _compilaat(tool: str, args: dict) -> dict | None:
    """Het compilaat van een gesloten selectie: de OData-parameters die de server bouwt."""
    if tool != "get_cbs_data" or "selectie" not in args:
        return None
    gebouwd = compileer(args["dataset_id"], args["selectie"], COL_DEFS)
    assert isinstance(gebouwd, dict), gebouwd
    return gebouwd


def herstelgraad() -> dict:
    """Reparaties en weigeringen van de periodeherstelroute op de vaste sample."""
    fixtures()
    telling = {"herstel": 0, "weigering": 0, "geen": 0}
    uitkomsten = {}
    for naam, key, filters, _verwacht in HERSTEL_SAMPLE:
        df = store.get(key)
        known = store.meta(key)
        hersteld, fout = canoniek.herstel_perioden(filters, df, known.periodekolom if known else None, True)
        uitkomst = "weigering" if fout else ("herstel" if hersteld != filters else "geen")
        telling[uitkomst] += 1
        uitkomsten[naam] = uitkomst
    return {"sample": len(HERSTEL_SAMPLE), **telling, "per_geval": uitkomsten}


def _prompt_hash() -> str:
    return hashlib.sha256(_PROMPT.read_bytes()).hexdigest()[:12]


def _schema_digest() -> str:
    from tools.schemas import TOOL_SCHEMAS

    vorm = json.dumps(TOOL_SCHEMAS, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(vorm.encode()).hexdigest()[:12]


def scorekaart() -> dict:
    """De volledige meting: per geval de digests, plus herkomst (prompt, model, schema)."""
    gevallen = []
    for naam, toelichting, tool, args in GEVALLEN:
        digests = digests_van_varianten(tool, args)
        geval = {
            "id": naam,
            "toelichting": toelichting,
            "tool": tool,
            "plan_digest": canoniek.digest(tool, args),
            "unieke_digests": len(digests),
        }
        if (gebouwd := _compilaat(tool, args)) is not None:
            geval["compilaat"] = gebouwd
        if (uitkomst := _uitkomst_digest(tool, args)) is not None:
            geval["uitkomst_digest"] = uitkomst
        gevallen.append(geval)
    return {
        "gemeten_op": f"{date.today():%Y-%m-%d}",
        "prompt_hash": _prompt_hash(),
        "model": MODEL,
        "schema_digest": _schema_digest(),
        "varianten_per_geval": AANTAL_VARIANTEN,
        "gevallen": gevallen,
        "herstel": herstelgraad(),
    }


def golden() -> dict:
    return json.loads(GOLDEN.read_text())


def schrijf_golden() -> dict:
    kaart = scorekaart()
    GOLDEN.write_text(json.dumps(kaart, indent=2, ensure_ascii=False) + "\n")
    return kaart
