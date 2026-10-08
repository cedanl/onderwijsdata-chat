"""VO-bestanden publiceren elk aantal van 1 t/m 4 als 4: een som ervan is een bovengrens (#406, #407).

Naast de -1-sentinel (onderdrukt, dus een ondergrens). De regel staat in de
DUO-beschrijving, maar niet elk bestand volgt hem: de HO-bestanden gebruiken -1
(#407). Daarom toetst dit de data: de regel geldt als er 4-cellen zijn en geen 1-3.
"""

import pandas as pd

from core.sentinels import EMPTY_CELLS

# Het kleinste aantal dat DUO wel exact publiceert is 5: tot en met 4 is samengevoegd.
_PUBLICATIEWAARDE = 4
_ACHTERGROND = 3  # 1..4 gepubliceerd als 4: een 4 kan maximaal 3 te hoog zijn

VOLGT = "volgt"
CONFLICT = "conflict"
NIET_VAST_TE_STELLEN = "niet_vast_te_stellen"


def _aantalkolommen(df: pd.DataFrame) -> list:
    return [c for c in df.columns if "AANTAL" in str(c).upper() and pd.api.types.is_numeric_dtype(df[c])]


def waargenomen(df: pd.DataFrame, min_een: dict[str, int]) -> dict[str, int] | None:
    """Wat de aantalkolommen van dit bestand laten zien; None zonder aantalkolom.

    `df` is gemaskeerd of niet: 1 t/m 4 blijven staan, de -1-cellen komen uit `min_een`.
    """
    kolommen = _aantalkolommen(df)
    if not kolommen:
        return None
    waarden = df[kolommen]
    return {
        "cellen_met_4": int((waarden == _PUBLICATIEWAARDE).sum().sum()),
        "cellen_1_t_m_3": int(waarden.isin([1, 2, 3]).sum().sum()),
        "cellen_min_een": sum(n for kolom, n in min_een.items() if kolom in kolommen),
    }


def beoordeling(profiel: dict[str, int] | None) -> tuple[str, str | None]:
    """Status en melding: volgt het bestand de regel '1-4 als 4' uit de beschrijving? (CH-31)

    Een bestandspatroon zegt hoogstens dat de regel niet uniform is toegepast, niet welke
    bewerking op elke 4 zit: geen melding beweert dat een 4 exact is.
    """
    if profiel is None:
        return (
            NIET_VAST_TE_STELLEN,
            "Dit bestand heeft geen aantalkolom: of de regel geldt, is niet aan de data te toetsen.",
        )
    if profiel["cellen_1_t_m_3"]:
        return CONFLICT, (
            "Dit bestand bevat ook aantallen 1 t/m 3: de regel '1-4 gepubliceerd als 4' uit de beschrijving is "
            "niet uniform toegepast. Welke bewerking op een 4 zit, is niet vast te stellen: noem een 4 niet exact "
            "en een som niet als bovengrens."
        )
    if profiel["cellen_met_4"]:
        return VOLGT, None
    if profiel["cellen_min_een"]:
        return CONFLICT, (
            "Dit bestand bevat geen 4-cellen maar wel -1-cellen (onderdrukt): kleine aantallen lijken hier als -1 "
            "gepubliceerd, niet als 4. Dat volgt uit dit bestand, niet uit de beschrijving; welke regel DUO "
            "toepaste, is niet vast te stellen."
        )
    return (
        NIET_VAST_TE_STELLEN,
        "Geen 4-cellen, geen 1 t/m 3 en geen -1: of de regel geldt, is niet aan de data te toetsen.",
    )


def regel_geldt(df: pd.DataFrame) -> bool:
    """Volgt de data de regel: 4-cellen aanwezig en geen 1-3-cellen in de aantalkolommen?"""
    return beoordeling(waargenomen(df, {}))[0] == VOLGT


def vier_cellen(df: pd.DataFrame) -> pd.DataFrame:
    """Per rij en aantalkolom 1 voor een als 4 gepubliceerde cel; alleen rijen met er minstens één."""
    kolommen = _aantalkolommen(df)
    if not kolommen:
        return EMPTY_CELLS
    cellen = (df[kolommen] == _PUBLICATIEWAARDE).astype(int)
    return cellen[cellen.any(axis=1)]


def bereik(som: float, cellen: int) -> tuple[int, int]:
    """Tussen welke waarden ligt het werkelijke totaal: elke als-4-cel is 1 tot 4."""
    return round(som - _ACHTERGROND * cellen), round(som)


def noten(aantallen: dict[str, int]) -> list[str]:
    """Melding per kolom voor de tool-output van een selectie."""
    return [
        f"{n} cellen met waarde 4 in '{kolom}': DUO publiceert 1 t/m 4 als 4, dus de som is een bovengrens "
        f"(het werkelijke totaal ligt per cel 0 tot 3 lager)"
        for kolom, n in aantallen.items()
    ]
