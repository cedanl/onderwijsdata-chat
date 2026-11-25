"""De koppen van de regels die code onder een antwoord zet (#1271), zonder verdere afhankelijkheden.

`agent/controlestappen.py` schrijft de regels (andere definities, kruiscontrole, vergelijkingsgroep) en
`agent/verschilverklaring.py` de uitkomst bij een eigen getal. De historie naar het model (`history`), de chatroute
(`routes/chat._parse_history`) en het bewijs (`beurtbewijs.eerdere_antwoorden`) herkennen ze hier aan hun kop.
"""

import re

KOP_DEFINITIES = "**Andere definities:**"
KOP_KRUISCONTROLE = "**Ter controle:**"
KOP_GROEP = "**Vergelijkingsgroep:**"
KOPPEN = (KOP_DEFINITIES, KOP_KRUISCONTROLE, KOP_GROEP)
# De uitkomst bij een eigen getal (#1258): een eigen bericht, geen regel onder een antwoord.
KOP_VERSCHILVERKLARING = "**Vergelijking met je eigen cijfer:**"

_EIGEN_REGEL = re.compile(rf"^[ \t]*(?:{'|'.join(re.escape(k) for k in KOPPEN)}).*(?:\n|\Z)", re.MULTILINE)


def zonder_regels(tekst: str) -> str:
    """De tekst zonder de regels onder het antwoord, van de app of overgenomen door het model."""
    uit, aantal = _EIGEN_REGEL.subn("", tekst)
    return uit.rstrip() if aantal else tekst


def is_verschilverklaring(tekst: str) -> bool:
    """Is dit bericht de uitkomst bij een eigen getal? Die is nooit bewijs en hoort niet in de historie (#1258)."""
    return tekst.lstrip().startswith(KOP_VERSCHILVERKLARING)
