"""Inspectie van het Onderwijs — open data client.

Publiceert maandelijkse kwaliteitsoordelen per school en per bestuur (PO/SO/VO),
en jaarlijkse schorsings- en verwijderingscijfers.

Gebruik:
    from riodata import inspectie

    # Catalogus
    datasets = inspectie.catalog()

    # Meest recente oordelen laden (zoekt automatisch de laatste maand op)
    df_scholen, df_besturen = inspectie.load("oordelen")

    # Specifiek bestand laden (index of naam-substring)
    df = inspectie.load("oordelen", resource="scholen")
    df = inspectie.load("schorsingen", resource=0)
"""
from __future__ import annotations

import io
import re
import urllib.request

import httpx

_BASE = "https://www.onderwijsinspectie.nl"

_DATASETS: dict[str, dict] = {
    "oordelen": {
        "naam": "Oordelen per school",
        "schooljaar_slug": "oordelen-2024-2025",
        "index_url": f"{_BASE}/trends-en-ontwikkelingen/onderwijsdata/oordelen/oordelen-2024-2025",
    },
    "schorsingen": {
        "naam": "Schorsingen en verwijderingen",
        "index_url": f"{_BASE}/trends-en-ontwikkelingen/onderwijsdata/schorsingen-en-verwijderingen",
    },
}


def catalog() -> list[dict]:
    """Geef Inspectie-datasets als catalogusrecords (lokale snapshot)."""
    import json
    from importlib.resources import files
    return json.loads(
        files("riodata.data").joinpath("inspectie_resources.json").read_text(encoding="utf-8")
    )


def resources(dataset_id: str) -> list[dict]:
    """Geef de meest recente downloadbare bestanden voor een dataset.

    Args:
        dataset_id: "oordelen" of "schorsingen"

    Returns:
        Lijst van {"naam": ..., "url": ..., "format": "ODS"}
    """
    return _find_latest_ods(dataset_id)


def load(
    dataset_id: str,
    resource: int | str = 0,
    sheet: int | str = 0,
    **kwargs,
) -> "pd.DataFrame":
    """Download en laad een Inspectie-dataset als DataFrame.

    Args:
        dataset_id: "oordelen" of "schorsingen"
        resource:   Index (int) of naam-substring (str) van het bestand.
                    "oordelen" heeft twee bestanden: scholen en besturen.
                    "schorsingen" heeft twee bestanden: scholen en redenen.
        sheet:      Werkbladnaam of -index (default 0). ODS-bestanden bevatten
                    soms meerdere werkbladen.
        **kwargs:   Doorgegeven aan pd.read_excel()

    Vereist pandas + odfpy (uv add 'riodata[analyse]' en pip install odfpy).
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Installeer pandas: uv add 'riodata[analyse]'")

    files_list = _find_latest_ods(dataset_id)
    file_info = _pick_resource(files_list, resource, dataset_id)

    r = httpx.get(file_info["url"], timeout=60, follow_redirects=True)
    r.raise_for_status()

    try:
        df = pd.read_excel(
            io.BytesIO(r.content),
            engine="odf",
            sheet_name=sheet,
            **kwargs,
        )
    except ImportError:
        raise ImportError(
            "Installeer odfpy voor ODS-bestanden: pip install odfpy"
        )

    return df


# ── intern ────────────────────────────────────────────────────────────────────

def _find_latest_ods(dataset_id: str) -> list[dict]:
    """Zoek de meest recente ODS-downloadlinks op de Inspectie-website."""
    meta = _get_meta(dataset_id)
    index_url = meta["index_url"]

    req = urllib.request.Request(index_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")

    # Zoek documentpagina-links (bijv. /documenten/2025/08/04/oordelen-1-augustus-2025)
    doc_pages = sorted(
        set(re.findall(r'href=["\'](/documenten/[^"\'<>]+)["\']', html)),
        reverse=True,
    )
    if not doc_pages:
        raise RuntimeError(f"Geen documentpagina's gevonden op {index_url}")

    # Probeer de meest recente pagina's totdat ODS-links gevonden worden
    for page_path in doc_pages[:5]:
        req2 = urllib.request.Request(_BASE + page_path, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req2, timeout=10) as r2:
                html2 = r2.read().decode("utf-8", errors="ignore")
        except Exception:
            continue

        ods_urls = re.findall(
            r'href=["\'](' + re.escape(_BASE) + r'[^"\'<>]+\.ods)["\']',
            html2,
            re.IGNORECASE,
        )
        if ods_urls:
            return [
                {"naam": _ods_label(url, i), "url": url, "format": "ODS"}
                for i, url in enumerate(ods_urls)
            ]

    raise RuntimeError(
        f"Geen ODS-bestanden gevonden voor '{dataset_id}'. "
        f"Controleer {index_url}"
    )


def _ods_label(url: str, index: int) -> str:
    """Maak een leesbare naam van een ODS-URL."""
    filename = url.split("/")[-1].replace("+", " ").replace(".ods", "")
    return filename if filename else f"bestand_{index}"


def _get_meta(dataset_id: str) -> dict:
    if dataset_id not in _DATASETS:
        raise ValueError(
            f"Onbekende dataset '{dataset_id}'. Kies uit: {list(_DATASETS)}"
        )
    return _DATASETS[dataset_id]


def _pick_resource(files_list: list[dict], resource: int | str, dataset_id: str) -> dict:
    if not files_list:
        raise RuntimeError(f"Geen bestanden gevonden voor '{dataset_id}'.")
    from ._resolutie import kies
    return kies(files_list, resource, dataset_id, id_key=None)
