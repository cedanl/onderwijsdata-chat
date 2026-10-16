"""Het voorbehoud bij een afgekapte bron in een rapport en een dashboard (#578): uit code, niet uit het model.

De chat zegt het als de data één pagina van de bron is, niet de hele bron (#186): het model leest de
waarschuwing in het toolresultaat. Een rapport op dezelfde data zweeg erover, want de datasetcontext gaf
`volledig` niet mee. Zoals de afrondingsnoot (#352) en de bronregel onder een grafiek (#569) maakt de code
er één vaste regel van, per laadkey: een selectie op een afgekapte pagina noemt dezelfde bron en dezelfde
pagina, dus één regel voor beide. Een key zonder KeyMeta heeft geen bron om te noemen en krijgt geen regel.
"""

from tools import store
from tools.getal import nl_getal
from tools.store import KeyMeta

from .selectie import bestand_in_woorden, bron_in_woorden, laadkey


def afkappingsregels(datasets: list[dict], waar: str) -> list[str]:
    """Per afgekapte laadkey in de datasetcontext één regel voor de lezer; `waar` is "rapport" of "dashboard".

    Alleen een dataset waarvan de context `volledig: False` zegt en waarvan de store de herkomst kent.
    """
    regels: dict[str, str] = {}
    for ds in datasets:
        key = ds.get("data_key")
        if ds.get("volledig") is not False or not isinstance(key, str) or not (eigen := store.meta(key)):
            continue
        root = laadkey(key)
        if root not in regels:
            # Is de laadkey uit de store verdwenen, dan noemt de selectie, die de herkomst erfde, de bron.
            regels[root] = _regel(store.meta(root) or eigen, store.get(root), waar)
    return list(regels.values())


def _regel(known: KeyMeta, pagina, waar: str) -> str:
    """De bron in woorden zoals de chat haar noemt (CH-45, #540), dan het voorbehoud uit de store."""
    bron = bron_in_woorden(known)
    if bestand := bestand_in_woorden(known):
        bron += f", bestand {bestand}"
    aantal = store.AFGEKAPT_AANTAL.format(rijen=nl_getal(len(pagina))) if pagina is not None else ""
    return f"{bron}: {store.AFGEKAPT.format(aantal=aantal, waar=waar)}"
