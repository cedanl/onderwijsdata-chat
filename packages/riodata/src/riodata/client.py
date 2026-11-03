"""RIO LOD API v3 (``RIO_LOD_API_v3.yml``). Versie 2 is op 19-10-2026 verwijderd (HTTP 410).

Wat v3 anders doet dan v2, voor wie code migreert:
- de typefilters heten op elke resource ``type`` (was ``erkenningtype``, ``opleidingseenheidtype``,
  ``opleidingserkenningtype``, ``organisatorischeEenheidType``);
- ``aangeboden-opleiding-cohorten``, ``contactadressen`` en ``onderwijslocatiegebruiken`` hebben geen
  lijst-endpoint meer: alleen als sub-resource (``related``), zie ``via`` in het filtercontract;
- een relatie (``instellingsrelaties``, ``organisatierelaties``) draagt ``vanErkenningId`` en
  ``naarErkenningId`` naast ``_links.van``/``_links.naar``;
- ``pageSize`` is nog steeds maximaal 100; ongeldige filterwaarden geven HTTP 400 met een melding;
- pagina's tellen vanaf 1: ``page=0`` geeft dezelfde pagina als ``page=1`` en de next-link gaat dan
  naar 2, dus ``fetch`` (dat bij 0 begint) mist niets; de laatste pagina kan leeg zijn (alleen een
  self-link). Dubbele ID's in een reeks zijn records per geldigheidsperiode, geen pagineringsfout.
"""
import httpx

from ._filtercontract import filtercontract

BASE_URL = "https://lod.onderwijsregistratie.nl/api/rio/v3"
PAGE_SIZE = 100  # API maximum


def _extract(response: dict) -> tuple[list, str | None]:
    """Haal items en 'next'-link uit een HATEOAS-response."""
    embedded = response.get("_embedded", {})
    items = next(iter(embedded.values()), []) if embedded else []
    next_href = response.get("_links", {}).get("next", {}).get("href")
    return items, next_href


def zonder_lijstendpoint(resource: str) -> str | None:
    """Waarom ``fetch(resource)`` niet kan: de resource bestaat in v3 alleen als sub-resource.

    None als de resource een lijst-endpoint heeft of niet in het contract staat (dan beslist de API).
    """
    res = filtercontract()["resources"].get(resource)
    if res is None or res.get("lijst_endpoint", True):
        return None
    via = ", ".join(res.get("via", [])) or "onbekend"
    return (
        f"RIO v3 heeft geen lijst-endpoint /{resource}; de resource is alleen als sub-resource op te halen "
        f"({via}): gebruik related(resource, id, '{resource}')."
    )


def get(resource: str, id: str, **params) -> dict:
    """Haal één resource op via ID."""
    r = httpx.get(f"{BASE_URL}/{resource}/{id}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch(resource: str, **params) -> list:
    """Haal alle items op van een list-resource (automatisch pagineren via HATEOAS).

    Geef page= mee om slechts één pagina op te halen (v3 telt vanaf 1; 0 is ook de eerste).
    pageSize= overschrijft de standaard (100, API-maximum).
    Alle andere kwargs worden als query-parameters meegegeven.
    Een resource zonder lijst-endpoint in v3 geeft een ValueError vóór de netwerkaanroep.
    """
    if reden := zonder_lijstendpoint(resource):
        raise ValueError(reden)
    page_size = params.pop("pageSize", PAGE_SIZE)
    single_page = "page" in params
    page = params.pop("page", 0)

    url = f"{BASE_URL}/{resource}"
    query = {"page": page, "pageSize": page_size, **params}

    results = []
    while url:
        # Geef params alleen mee als ze niet leeg zijn —
        # httpx overschrijft anders de query-string in de URL
        kwargs = {"params": query} if query else {}
        r = httpx.get(url, timeout=30, **kwargs)
        r.raise_for_status()
        data = r.json()

        if "_embedded" not in data:
            if results:
                # Lege laatste HATEOAS-pagina — stop paginering
                break
            # Endpoint dat nooit HATEOAS gebruikt (plain array of object)
            return data if isinstance(data, list) else [data]

        items, next_href = _extract(data)
        results.extend(items)

        if single_page or not next_href:
            break
        # Volg de HATEOAS 'next'-link (bevat al alle params)
        url, query = next_href, None

    return results


def related(resource: str, id: str, sub: str, **params) -> list:
    """Haal sub-resources op die gelinkt zijn aan een resource.

    Voorbeeld: related("aangeboden-opleidingen", uuid, "aangeboden-opleiding-cohorten")
    """
    r = httpx.get(f"{BASE_URL}/{resource}/{id}/{sub}", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "_embedded" in data:
        items, _ = _extract(data)
        return items
    return data if isinstance(data, list) else [data]
