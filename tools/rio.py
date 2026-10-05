import json

import pandas as pd
from riodata import fetch, filtercontract, valideer_filters

from core.config import RIO_PAGE_SIZE

from . import fouten, store
from .catalog import catalogus_titel
from .columns import sample_values

_SAMPLE_ROWS = 5
_PAGING = frozenset({"page", "pageSize"})


def rio_filters(resource: str) -> list[str]:
    """De serverfilters van een RIO-resource, uit het filtercontract van riodata; leeg als onbekend."""
    filters = filtercontract()["resources"].get(resource, {}).get("filters", [])
    return [f["naam"] for f in filters]


def _filter_hint(allowed: list[str]) -> str:
    return f" Toegestane filters: {allowed} (exacte waarden, geen operatoren als __contains)." if allowed else ""


def _filterfout(resource: str, filters: dict) -> str | None:
    """Wat er mis is aan resource of filters, met de herstelhint van riodata; None als RIO ze accepteert.

    Een ongeldig filter of een ongeldige waarde kost anders een HTTP 400, waarna het
    model in een ongefilterde eerste pagina gaat zoeken (#186). Het filtercontract komt
    uit de OpenAPI-spec van RIO: ook enum-waarden ("G", niet "OPEN") en datums (#353, #373).
    """
    # Paging zet get_rio_data zelf; een getal als code ("erkendeopleidingscode": 25295)
    # stuurt httpx als tekst door, dus toetsen we het ook zo.
    params = {k: v if isinstance(v, str) else str(v) for k, v in filters.items() if k not in _PAGING}
    try:
        problemen = valideer_filters(resource, params)
    except ValueError as e:
        # Het filtercontract uit de OpenAPI-spec, lokaal en vast: die tekst mag naar het model.
        return fouten.melding(fouten.Fout.BRON_WEIGERT, str(e))
    # 'waarschuwing': de catalogus noemt het filter, de spec niet; RIO beslist zelf.
    herstel = [p["herstel"] for p in problemen if p["probleem"] != "waarschuwing"]
    if not herstel:
        return None
    return (
        f"RIO-resource '{resource}' weigert deze filters: {' '.join(herstel)} "
        "(exacte waarden, geen operatoren als __contains)."
    )


def get_rio_data(resource: str, filters: dict | None = None) -> str:
    if fout := _filterfout(resource, filters or {}):
        return fout
    # Eén pagina van RIO_PAGE_SIZE-rijen: volledige paginatie blokkeert bij
    # upstream 4xx op een late pagina (#159). Een grotere pageSize uit filters
    # zou onderstaande slice toch weer afkappen.
    params = {**(filters or {}), "page": 0, "pageSize": RIO_PAGE_SIZE}
    try:
        results = fetch(resource, **params)
    except Exception as e:
        uitleg = f" Resource '{resource}' met filters {filters or {}}.{_filter_hint(rio_filters(resource))}"
        return fouten.bronfout("RIO", e, uitleg)

    if not results:
        return f"Geen resultaten voor RIO resource '{resource}' met filters {filters or {}}."

    df = pd.DataFrame(results[:RIO_PAGE_SIZE])
    filter_suffix = "_".join(f"{k}={v}" for k, v in sorted((filters or {}).items()) if k not in ("page", "pageSize"))
    key = f"rio:{resource}:{filter_suffix}" if filter_suffix else f"rio:{resource}"

    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": sample_values(df[col], 5),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")
    # RIO levert geen totaal-aantal (#170): een volle pagina betekent dat er
    # waarschijnlijk meer rijen zijn. Geen "totaal_rijen" zoals bij CBS/DUO: die
    # naam las het model als registertotaal (#177).
    meer_beschikbaar = len(results) >= RIO_PAGE_SIZE
    # Pas cachen als de beschrijving gelukt is: een mislukte tool mag geen data achterlaten.
    store.put(
        key,
        df,
        store.KeyMeta(
            bron="rio",
            dataset=resource,
            volledig=not meer_beschikbaar,
            laad=("get_rio_data", {"resource": resource, "filters": filters}),
        ),
    )
    result = {
        "data_key": key,
        "catalogus_titel": catalogus_titel(resource),
        "opgehaalde_rijen": len(df),
        "meer_beschikbaar": meer_beschikbaar,
        "kolommen": schema,
        "preview": preview,
    }
    if meer_beschikbaar:
        result["waarschuwing"] = (
            f"Afgekapt op {RIO_PAGE_SIZE} rijen (één pagina); dit is geen telling. "
            "RIO levert geen totaal-aantal: beantwoord 'hoeveel'-vragen over het "
            "register niet met deze data. Verfijn met filters of gebruik DUO/CBS voor aantallen."
        )

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
