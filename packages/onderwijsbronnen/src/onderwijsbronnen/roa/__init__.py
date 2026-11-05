"""ROA Arbeidsmarktinformatiesysteem client via DataverseNL.

Het Researchcentrum voor Onderwijs en Arbeidsmarkt (ROA) publiceert
arbeidsmarktprognoses en schoolverlatersdata via DataverseNL (DANS).

Gebruik:
    from onderwijsbronnen import roa

    # Catalogus
    datasets = roa.catalog()

    # Arbeidsmarktprognoses laden (AIS tot 2030, ~42 MB)
    df = roa.load("ais2030", "arbeidsmarkt")

    # Schoolverlaterscijfers laden (~23 MB)
    df = roa.load("ais2030", "schoolverlaters")

    # Arbeidsmarktuitkomsten (klein, ~0.2 MB)
    df = roa.load("ais2030", "uitkomsten")
"""
from __future__ import annotations

import hashlib
import io

import httpx

from .._kern import broncontract

DATAVERSE_BASE = "https://dataverse.nl/api"

# DOI's van de ROA datasets op DataverseNL
def catalog() -> list[dict]:
    """Geef beschikbare ROA datasets als catalogusrecords (lokale snapshot).

    ``roa_resources.json`` is de enige resourcebron: de loader leest dezelfde lijst.
    """
    import json
    from importlib.resources import files
    return json.loads(files("onderwijsbronnen.roa.data").joinpath("roa_resources.json").read_text(encoding="utf-8"))


def _datasets() -> dict[str, dict]:
    return {
        r["_roa_id"]: {
            "naam": r["bron"],
            "resources": {x["naam"]: x["file_id"] for x in r["_resources"]},
            "schemas": {x["file_id"]: x.get("schema") for x in r["_resources"]},
        }
        for r in catalog()
    }


def _schema(meta: dict, file_id: int) -> dict | None:
    """Gevalideerd schema van een bestand (zie catalogus/valideer_roa_uwv.py), of None."""
    return meta.get("schemas", {}).get(file_id)


def resources(dataset_id: str) -> list[dict]:
    """Geef beschikbare bestanden voor een ROA dataset."""
    meta = _get_meta(dataset_id)
    return [
        {"naam": naam, "file_id": fid, "url": f"{DATAVERSE_BASE}/access/datafile/{fid}"}
        for naam, fid in meta["resources"].items()
    ]


def load(
    dataset_id: str,
    resource: int | str = 0,
    **kwargs,
) -> "pd.DataFrame":
    """Download en laad een ROA dataset als DataFrame.

    Args:
        dataset_id: "ais2030" of "ais2028"
        resource:   Index (int), resourcenaam (str, bijv. "arbeidsmarkt", "schoolverlaters")
                    of file_id (int > 1000)
        **kwargs:   Doorgegeven aan pd.read_csv()

    Bron-URL, checksum en encoding staan in ``df.attrs['bron']``. Download-, decodeer-,
    parser- en schemafouten zijn aparte uitzonderingen (zie ``onderwijsbronnen._kern.lezen``).

    Vereist pandas (uv add 'onderwijsbronnen[analyse]').
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Installeer pandas: uv add 'onderwijsbronnen[analyse]'")

    meta = _get_meta(dataset_id)
    file_id = _pick_file_id(meta, resource, dataset_id)

    r = httpx.get(
        f"{DATAVERSE_BASE}/access/datafile/{file_id}",
        timeout=180,
        follow_redirects=True,
    )
    r.raise_for_status()

    from .._kern.lezen import ChecksumFout, herkomst, lees_csv

    schema = _schema(meta, file_id)
    if schema and schema.get("dataverse_sha1"):
        sha1 = hashlib.sha1(r.content).hexdigest()
        if sha1 != schema["dataverse_sha1"]:
            raise ChecksumFout(
                f"ROA-bestand {file_id} wijkt af van de gecontroleerde versie "
                f"(sha1 {sha1}, verwacht {schema['dataverse_sha1']}); draai catalogus/valideer_roa_uwv.py"
            )
    # Getallen gebruiken een decimale komma ('42,6'); zonder decimal=',' worden ze tekst.
    defaults = {"sep": ";", "decimal": ",", "low_memory": False}
    if kwargs.get("sep") == ",":  # eigen separator ',' kan niet samen met decimale komma
        defaults["decimal"] = "."
    verwacht = tuple(schema["kolommen"]) if schema and "usecols" not in kwargs else ()
    df, enc = lees_csv(r.content, defaults=defaults, verwacht=verwacht, **kwargs)
    df.attrs["bron"] = {**herkomst(r.content, str(r.url)), "encoding": enc, "file_id": file_id}
    if schema:
        df.attrs["schema"] = {k: schema.get(k) for k in (
            "bestandsnaam", "editie", "meest_recente_editie", "granulariteit", "beperkingen", "dataverse_sha1")}
    return df


# ── intern ────────────────────────────────────────────────────────────────────

def _get_meta(dataset_id: str) -> dict:
    datasets = _datasets()
    if dataset_id not in datasets:
        raise ValueError(
            f"Onbekende dataset '{dataset_id}'. Kies uit: {list(datasets)}"
        )
    return datasets[dataset_id]


def _pick_file_id(meta: dict, resource: int | str, dataset_id: str) -> int:
    res = meta["resources"]
    if isinstance(resource, int) and not isinstance(resource, bool) and resource > 1000:
        # Directe file_id meegegeven
        return resource
    from .._kern.resolutie import kies
    items = [{"naam": naam, "file_id": fid} for naam, fid in res.items()]
    return kies(items, resource, dataset_id, id_key="file_id")["file_id"]


# ── broncontract (#911) ────────────────────────────────────────────────────────

BRON = "roa"
catalogusrecords = catalog  # roa_resources.json, dezelfde lijst die de lader leest
laad = load


def metadata(record: dict) -> dict:
    edities = sorted({e for r in record.get("_resources") or [] if (e := (r.get("schema") or {}).get("editie"))})
    return broncontract.metadata(
        BRON,
        record["_roa_id"],
        record.get("bron"),
        peildatum_of_editie=edities[-1] if edities else None,
        redenen={
            "peildatum_of_editie": "geen gevalideerd schema met editie in de catalogus",
            "voorlopig": "ROA publiceert prognoses per editie, zonder voorlopig-markering",
            "laatste_update": "de DataverseNL-release staat in de periodetekst, niet als veld",
        },
    )
