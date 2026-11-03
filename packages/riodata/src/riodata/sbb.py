"""SBB Kwalificatiestructuur MBO client.

SBB (Samenwerkingsorganisatie Beroepsonderwijs Bedrijfsleven) publiceert:
- CREBO-codelijsten (XLSX): erkende MBO-kwalificaties met codes, namen en niveaus
- Kwalificatiedossiers (XML): volledige inhoud met kerntaken, werkprocessen en competenties

Gebruik:
    from riodata import sbb

    # Catalogus
    datasets = sbb.catalog()

    # CREBO-codelijst laden als DataFrame
    df = sbb.load("crebolijst")

    # Specifiek bestand laden
    df = sbb.load("crebolijst", resource=0)

    # XML-bytes ophalen (voor eigen XML-parsing)
    xml_bytes = sbb.fetch_xml("kwalificatiedossiers-xml", resource="dossiers_vanaf_2015")
"""
from __future__ import annotations

import io

import httpx

_BASE = "https://kwalificatie-mijn.s-bb.nl"



def _datasets() -> dict[str, dict]:
    """Loaderconfig uit dezelfde bron als de catalogus (``sbb_resources.json``)."""
    return {
        r["_sbb_id"]: {
            "naam": r["bron"],
            "resources": {x["naam"]: x["output_id"] for x in r["_resources"]},
        }
        for r in catalog()
    }


def catalog() -> list[dict]:
    """Geef SBB-datasets als catalogusrecords (lokale snapshot)."""
    import json
    from importlib.resources import files
    return json.loads(
        files("riodata.data").joinpath("sbb_resources.json").read_text(encoding="utf-8")
    )


def resources(dataset_id: str) -> list[dict]:
    """Geef beschikbare bestanden voor een SBB-dataset.

    Args:
        dataset_id: "crebolijst" of "kwalificatiedossiers-xml"

    Returns:
        Lijst van {"naam": ..., "output_id": ..., "url": ...}
    """
    meta = _get_meta(dataset_id)
    return [
        {"naam": naam, "output_id": oid, "url": f"{_BASE}/Lijsten/Output/{oid}"}
        for naam, oid in meta["resources"].items()
    ]


def load(
    dataset_id: str = "crebolijst",
    resource: int | str = 0,
    **kwargs,
) -> "pd.DataFrame":
    """Download en laad een SBB CREBO-codelijst als DataFrame.

    Werkt alleen voor XLSX-bestanden (crebolijst). Gebruik fetch_xml() voor
    XML-dossiers.

    Args:
        dataset_id: "crebolijst"
        resource:   Index (int) of naam-substring (str) van het bestand.
        **kwargs:   Doorgegeven aan pd.read_excel()

    Vereist pandas + openpyxl (uv add 'riodata[analyse]').
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Installeer pandas: uv add 'riodata[analyse]'")

    res_list = resources(dataset_id)
    res = _pick_resource(res_list, resource, dataset_id)

    r = httpx.get(res["url"], timeout=60, follow_redirects=True)
    r.raise_for_status()

    return pd.read_excel(io.BytesIO(r.content), **kwargs)


def fetch_xml(
    dataset_id: str = "kwalificatiedossiers-xml",
    resource: int | str = "dossiers_vanaf_2015",
) -> bytes:
    """Download een SBB XML-kwalificatiedossier als bytes.

    Args:
        dataset_id: "kwalificatiedossiers-xml"
        resource:   Index (int) of naam-substring (str) van het bestand.

    Returns:
        Ruwe XML als bytes. Parseer met xml.etree.ElementTree of lxml.

    Voorbeeld:
        import xml.etree.ElementTree as ET
        xml_bytes = sbb.fetch_xml("kwalificatiedossiers-xml", "dossiers_vanaf_2015")
        root = ET.fromstring(xml_bytes)
    """
    res_list = resources(dataset_id)
    res = _pick_resource(res_list, resource, dataset_id)

    r = httpx.get(res["url"], timeout=120, follow_redirects=True)
    r.raise_for_status()
    return r.content


# ── intern ────────────────────────────────────────────────────────────────────

def _get_meta(dataset_id: str) -> dict:
    datasets = _datasets()
    if dataset_id not in datasets:
        raise ValueError(
            f"Onbekende dataset '{dataset_id}'. Kies uit: {list(datasets)}"
        )
    return datasets[dataset_id]


def _pick_resource(res_list: list[dict], resource: int | str, dataset_id: str) -> dict:
    if not res_list:
        raise RuntimeError(f"Geen bestanden voor '{dataset_id}'.")
    from ._resolutie import kies
    return kies(res_list, resource, dataset_id, id_key=None)
