"""Waarom een rapportcijfer kan afwijken van eigen cijfers, in het definitieblok, uit code (#736).

Vier gebruikers legden een rapport naast eigen cijfers of die van de Vereniging Hogescholen en konden het verschil
niet verklaren: "wijkt af van VH en niet duidelijk waarom", "eigen cijfers zijn net anders". De teldefinitie stond
er wel, maar als één DUO-alinea; wat tussen bron en eigen administratie meestal verschilt (peildatum, personen of
inschrijvingen, wat niet meetelt, opleidingsvorm, afronding) moest de lezer er zelf uit halen. Hier staat het per
dataset waarop het rapport rust, alleen wat de metadata van de geladen key zegt: test_report_vergelijken leest elke
zin na in de teldefinitie van DUO.
"""

from tools import store
from tools.duo import OPLEIDINGSVORM_DATASETS
from tools.store import KeyMeta

from .niet_meegeteld import NIET_MEEGETELD

BEGRIP = "Vergelijken met eigen cijfers"

# Eén zin per feit: het rapport toont een definitie van meer zinnen als opsomming, per zin (#748).
PEILDATUM = (
    "DUO telt op de peildatum 1 oktober, dus een telling op een andere datum of over een ander tijdvak komt op een "
    "ander aantal."
)
PERSONEN = (
    "DUO telt personen, met één hoofdinschrijving per student in het hele hoger onderwijs, dus wie inschrijvingen "
    "telt (ook neveninschrijvingen) komt hoger uit."
)
INSCHRIJVINGEN = "DUO telt inschrijvingen, ook echte neveninschrijvingen, dus wie personen telt komt lager uit."
OPLEIDINGSVORM = (
    "Voltijd, deeltijd en duaal staan in aparte rijen en een totaal telt ze samen, tenzij het rapport één "
    "opleidingsvorm kiest."
)
SLOT = (
    "Leg bij een verschil met eigen cijfers of een andere publicatie, zoals die van de Vereniging Hogescholen, eerst "
    "de peildatum, de telwijze en de versie van de data naast elkaar; de versie staat bij de bronnen."
)


def _duo(known: KeyMeta) -> list[str]:
    tel = known.teldefinitie or ""
    zinnen = []
    if "peildatum 1 oktober" in tel:
        zinnen.append(PEILDATUM)
    if "natuurlijke personen" in tel:
        zinnen.append(PERSONEN)
    elif "neveninschrijvingen meegeteld" in tel:
        zinnen.append(INSCHRIJVINGEN)
    if known.dataset in NIET_MEEGETELD:
        zinnen.append(f"Niet meegeteld: {NIET_MEEGETELD[known.dataset]}.")
    if known.dataset in OPLEIDINGSVORM_DATASETS:
        zinnen.append(OPLEIDINGSVORM)
    return zinnen


def _cbs(known: KeyMeta) -> list[str]:
    if not known.afronding:
        return []
    return [
        f"CBS rondt de aantallen af op {known.afronding}-tallen, dus een optelling of een eigen telling wijkt iets af."
    ]


def vergelijken(datasets: list[dict]) -> list[dict]:
    """Per dataset van het rapport wat een verschil met eigen cijfers kan verklaren; leeg als de metadata niets zegt.

    In de vorm van het definitieblok ({begrip, definitie}), met daarna één item met wat de lezer bij een verschil
    eerst naast elkaar legt.
    """
    items: list[dict] = []
    gezien: set[str] = set()
    for ds in datasets:
        known = store.meta(ds["data_key"])
        if known is None or known.dataset in gezien:
            continue
        gezien.add(known.dataset)
        zinnen = _duo(known) if known.bron == "duo" else _cbs(known) if known.bron == "cbs" else []
        if zinnen:
            items.append({"begrip": f"{BEGRIP} ({known.dataset})", "definitie": " ".join(zinnen)})
    if items:
        items.append({"begrip": BEGRIP, "definitie": SLOT})
    return items
