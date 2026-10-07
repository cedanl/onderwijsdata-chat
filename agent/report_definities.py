"""Het definitieblok van een rapport komt uitsluitend uit de bron (#329, #402, #422).

Een model schreef bij p01hoinges "één persoon telt één keer per opleidingsvorm" waar
DUO één keer in het hele domein hoger onderwijs zegt, en verwees naar "resource 3".
Na het weren van zulke tellingzinnen bleef het model eigen begrippen naast de bron
zetten ("Ingeschrevene" naast de DUO-teldefinitie). Wat een bron telt en wat de
opleidingsvormcodes betekenen staat in de metadata van de geladen keys; het model
schrijft geen definities meer.
"""

import re

from tools import store
from tools.duo import OPLEIDINGSVORM_DATASETS, OPLEIDINGSVORMEN

# Het rapport gaat over opleidingsvorm als de kolom, een code of een vorm erin staat.
# Anders is de codelijst ruis: het Twente-rapport toonde hem zonder één opleidingsvorm (#422).
_OVER_OPLEIDINGSVORM = re.compile(
    r"opleidingsvorm|\b(?:" + "|".join(OPLEIDINGSVORMEN) + r")\b|\b(?:" + "|".join(OPLEIDINGSVORMEN.values()) + ")",
    re.IGNORECASE,
)


def definities_uit_bron(datasets: list[dict], rapporttekst: str = "") -> list[dict]:
    """De teldefinitie van de geladen datasets en, als het rapport erover gaat, de opleidingsvormcodes."""
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
    if vormen and _OVER_OPLEIDINGSVORM.search(rapporttekst):
        codes = ", ".join(f"{code} = {vorm}" for code, vorm in OPLEIDINGSVORMEN.items())
        definities.append({"begrip": "Opleidingsvorm", "definitie": codes})
    return definities
