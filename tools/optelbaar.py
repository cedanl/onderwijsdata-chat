"""Welke kolommen een som verdragen: geen percentage, verhouding of verschil (#866).

query_data en compute_kpi sommeerden elke numerieke kolom. Een som over een %-kolom (85368NED heeft
'%' naast 'aantal') of over een DUO-percentagekolom is een getal zonder betekenis, dat het model daarna
met gezag noemt. Eén regel voor beide tools: de eenheid uit CBS (DataProperties.Unit), anders de
kolomnaam; kolommen met een teken (MUTATIE, SALDO, ...) uit de sentinelregel in data/domeinregels.toml.
Een gemiddelde blijft mogelijk; de foutmelding zegt wat dat is.
"""

from core.sentinels import SIGNED_HINTS

from .cbs import column_unit

# CBS-eenheden van een verhouding (kleine letters, deel van de eenheid): '%', '‰', 'per 1 000 inwoners', 'index'.
_VERHOUDING_EENHEDEN = ("%", "‰", "promille", "per ", "index")
# Kolomnamen (hoofdletters) van een percentage of aandeel, voor DUO en kolommen zonder CBS-eenheid.
_VERHOUDING_IN_NAAM = ("%", "PERCENTAGE", "AANDEEL")


def _verhouding(data_key: str, kolom: str) -> str | None:
    """Waarom `kolom` een percentage of verhouding is, of None."""
    eenheid = column_unit(data_key, kolom)
    if eenheid and any(deel in eenheid.lower() for deel in _VERHOUDING_EENHEDEN):
        return f"de eenheid is '{eenheid}'"
    if any(deel in kolom.upper() for deel in _VERHOUDING_IN_NAAM):
        return "de kolomnaam noemt een percentage of aandeel"
    return None


def somfout(data_key: str, kolom: str) -> str | None:
    """De foutmelding voor een som over `kolom`, of None als die som een betekenis heeft."""
    if reden := _verhouding(data_key, kolom):
        return (
            f"Een som over '{kolom}' betekent niets: {reden}, en percentages of verhoudingen tel je niet op. "
            "Tel de tellers en de noemers apart op en deel daarna (een gewogen gemiddelde), of gebruik 'mean' "
            "en zeg erbij dat het een ongewogen gemiddelde van de percentages is."
        )
    if teken := next((hint for hint in SIGNED_HINTS if hint in kolom.upper()), None):
        return (
            f"Een som over '{kolom}' telt verschillen op: de kolomnaam bevat '{teken}' (een mutatie, saldo, verschil "
            "of groei). Toon de waarden per groep, of tel de onderliggende standen op en neem daarvan het verschil."
        )
    return None
