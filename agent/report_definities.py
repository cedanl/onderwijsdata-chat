"""Het definitieblok van een rapport komt uit de bron, niet uit het model (#329).

Een model schreef bij p01hoinges "één persoon telt één keer per opleidingsvorm" waar
DUO één keer in het hele domein hoger onderwijs zegt, en verwees naar "resource 3".
Wat een bron telt en wat de opleidingsvormcodes betekenen staat in de metadata van
de geladen keys; het model schrijft alleen de getalvrije begrippen erbij.
"""

import re

from tools import store
from tools.duo import OPLEIDINGSVORM_DATASETS, OPLEIDINGSVORMEN

# Wat een model over tellen schrijft als de bron zelf al zegt wat hij telt.
_TELLING = re.compile(r"\b(?:tel(?:t|len|ling|lingen)|geteld|meegeteld)\b|\bper opleidingsvorm\b", re.IGNORECASE)


def definities_uit_bron(datasets: list[dict]) -> list[dict]:
    """De teldefinitie en opleidingsvormcodes van de geladen datasets, zoals de bron ze geeft."""
    definities: list[dict] = []
    vormen = False
    for ds in datasets:
        known = store.meta(ds["data_key"])
        if known is None:
            continue
        if (
            known.teldefinitie
            and (telling := {"begrip": f"Telling ({known.dataset})", "definitie": known.teldefinitie}) not in definities
        ):
            definities.append(telling)
        vormen = vormen or known.dataset in OPLEIDINGSVORM_DATASETS
    if vormen:
        codes = ", ".join(f"{code} = {vorm}" for code, vorm in OPLEIDINGSVORMEN.items())
        definities.append({"begrip": "Opleidingsvorm", "definitie": codes})
    return definities


def samengevoegd(uit_bron: list[dict], van_model: list[dict]) -> list[dict]:
    """De definities uit de bron eerst; die van het model alleen waar de bron niets te zeggen heeft."""
    begrippen = {d["begrip"].lower() for d in uit_bron}
    heeft_telling = any(d["begrip"].startswith("Telling") for d in uit_bron)
    behouden = [
        d
        for d in van_model
        if str(d.get("begrip", "")).lower() not in begrippen
        and not (heeft_telling and _TELLING.search(f"{d.get('begrip', '')} {d.get('definitie', '')}"))
    ]
    return [*uit_bron, *behouden]
