"""De provincie van de instelling bij mbo-bestanden die er geen hebben (#453).

Het mbo-diplomabestand en de jaarbestanden instroom hebben geen provinciekolom. "Gediplomeerden
van ROC Midden Nederland tegenover de andere instellingen in Utrecht" kostte daardoor een tweede
bestand, een selectie van de Utrechtse instellingen en een koppeling: elke stap een modelronde.

De kolom komt uit DUO's adressenbestand op INSTELLINGSCODE, via data/instellingen.get_adres_lookup:
dezelfde bron als de provincie van de instelling in het profiel (#448). Nagegaan op 2026-10-08:
voor alle 55 codes in het diplomabestand en de instroombestanden 2021 en 2025 is er een adres, en
het is dezelfde provincie als DUO's eigen PROVINCIE INSTELLING in mbo-studenten-per-instelling.
Een code zonder adres krijgt geen provincie: leeg, niet geraden.
"""

import pandas as pd

from data.instellingen import get_adres_lookup

KOLOM = "PROVINCIE INSTELLING"  # dezelfde naam als in DUO's eigen mbo-bestanden
_CODEKOLOM = "INSTELLINGSCODE"
# DUO-bestanden met de mbo-instellingscode; een bestand dat de kolom al heeft, houdt die van DUO.
DATASETS = frozenset({"gediplomeerde-mbo-studenten", "instromende-mbo-studenten", "mbo-studenten-per-instelling"})
# Het mbo-deel van get_adres_lookup (mbo- en ho-codes overlappen niet); de snippet laadt alleen dit.
ADRESBESTAND = ("adressen_mbo", 1)

DEFINITIE = (
    "Provincie van het adres van de instelling volgens DUO's adressenbestand (adressen_mbo): niet de "
    "woonprovincie van de student, en niet per vestiging. Waar DUO deze kolom niet in het bestand zet, "
    "voegt de chat hem toe op INSTELLINGSCODE; een code zonder adres blijft leeg."
)


def leidt_af(dataset_id: str, kolommen) -> bool:
    """Krijgt dit bestand de kolom van de chat?"""
    return dataset_id in DATASETS and _CODEKOLOM in kolommen and KOLOM not in kolommen


def _provincies() -> dict[str, str]:
    return {code: adres["provincie"] for code, adres in get_adres_lookup().items() if adres.get("provincie")}


def met_provincie(df: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    """`df` met de provincie van de instelling erbij, als het bestand die mist."""
    if not leidt_af(dataset_id, df.columns):
        return df
    codes = df[_CODEKOLOM].astype(str).str.strip()
    return df.assign(**{KOLOM: codes.map(_provincies())})
