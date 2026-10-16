"""De bronregel onder een grafiek in het rapport (#569): uit code, niet uit het model.

Twee gebruikers vroegen bij een rapportgrafiek waar precies deze cijfers vandaan komen. De lijst
Bronnen onderaan en de Verantwoording zeggen dat niet per grafiek, en doorklikken naar de bron om
het na te kijken kon niet. De figuur kent haar data_key; de store weet uit welke bron en dataset
die key komt (#193) en welke schooljaren de getekende rijen dekken; de catalogus kent de titel en
de documentatie-URL van de dataset. Daaruit maakt de code één regel per grafiek, met dezelfde
woorden als de chatcitaties (CH-45, #540): bron en titel, dataset-ID, bij meer bestanden het
bestand, de periode en de CBS-periodestatus van de getekende rijen, en de link. Een figuur zonder
herleidbare bron krijgt geen regel; het rapport zegt dan dat de bron niet is vastgesteld.
"""

from tools import store
from tools.catalog import documentatie_url

from .selectie import bestand_in_woorden, bron_in_woorden, laadkey, periode_in_woorden

_PERIODESTATUS = "Periodestatus"


def _periodestatus(data_key: str) -> str | None:
    """De CBS-periodestatus van de getekende rijen (Voorlopig, Definitief), zoals het manifest die leest (#180)."""
    df = store.get(data_key)
    if df is None or not hasattr(df, "columns") or _PERIODESTATUS not in df.columns:
        return None
    return "/".join(sorted({str(s) for s in df[_PERIODESTATUS].dropna().unique()})) or None


def figuurbron(data_key) -> dict | None:
    """De bronregel van de grafiek die `data_key` tekende.

    `tekst` is de regel onder de grafiek, `url` de link naar de open-databron (None als de catalogus
    die niet kent), `bron` en `dataset` staan er los bij. None als de figuur geen data_key heeft of de
    store die niet kent: dan is de bron niet vastgesteld, en zegt het rapport dat.
    """
    if not isinstance(data_key, str) or not data_key or not (known := store.meta(laadkey(data_key))):
        return None
    # De periode van wat de grafiek toont: de selectie, niet de hele geladen dataset.
    getekend = store.meta(data_key) or known
    delen = [f"{bron_in_woorden(known)} ({known.dataset})"]
    if bestand := bestand_in_woorden(known):
        delen.append(f"bestand {bestand}")
    if jaren := periode_in_woorden(getekend):
        delen.append(jaren)
    if status := _periodestatus(data_key):
        delen.append(f"status {status}")
    return {
        "bron": known.bron.upper(),
        "dataset": str(known.dataset),
        "tekst": ", ".join(delen),
        "url": documentatie_url(str(known.dataset)),
    }
