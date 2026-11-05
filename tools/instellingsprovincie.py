"""De provincie en de arbeidsmarktregio van de instelling bij mbo-bestanden die ze niet hebben (#453, #744).

Het mbo-diplomabestand en de jaarbestanden instroom hebben geen provinciekolom. "Gediplomeerden
van ROC Midden Nederland tegenover de andere instellingen in Utrecht" kostte daardoor een tweede
bestand, een selectie van de Utrechtse instellingen en een koppeling: elke stap een modelronde.

De provincie komt uit DUO's adressenbestand op INSTELLINGSCODE, via data/instellingen.get_adres_lookup:
dezelfde bron als de provincie van de instelling in het profiel (#448). Nagegaan op 2026-10-08:
voor alle 55 codes in het diplomabestand en de instroombestanden 2021 en 2025 is er een adres, en
het is dezelfde provincie als DUO's eigen PROVINCIE INSTELLING in mbo-studenten-per-instelling.

Geen DUO-bestand heeft de arbeidsmarktregio van de instelling (#744). Die volgt uit de gemeente van de hoofdvestiging en
de CBS-indeling van data/arbeidsmarktregio.py, dezelfde als in het profiel: uit GEMEENTENUMMER INSTELLING waar het
bestand die heeft, anders uit het adres. Een code zonder adres en een gemeente zonder regio blijven leeg, niet geraden.
"""

import pandas as pd

from data import arbeidsmarktregio
from data.instellingen import HOOFDVESTIGING, REGIO_VIA_LOCATIES, get_adres_lookup

KOLOM = "PROVINCIE INSTELLING"  # dezelfde naam als in DUO's eigen mbo-bestanden
REGIOKOLOM = "ARBEIDSMARKTREGIO INSTELLING"
GEMEENTEKOLOM = "GEMEENTENUMMER INSTELLING"
_CODEKOLOM = "INSTELLINGSCODE"
# DUO-bestanden met de mbo-instellingscode; een bestand dat de kolom al heeft, houdt die van DUO.
DATASETS = frozenset({"gediplomeerde-mbo-studenten", "instromende-mbo-studenten", "mbo-studenten-per-instelling"})
# Het mbo-deel van get_adres_lookup (mbo- en ho-codes overlappen niet); de snippet laadt alleen dit.
ADRESBESTAND = ("adressen_mbo", 1)

DEFINITIE = (
    "Provincie van het adres van de instelling volgens DUO's adressenbestand (adressen_mbo): niet de "
    "woonprovincie van de student, en niet per vestiging. Waar DUO deze kolom niet in het bestand zet, "
    "voegt de chat hem toe op INSTELLINGSCODE; een code zonder adres blijft leeg. "
    + HOOFDVESTIGING
    + " "
    + REGIO_VIA_LOCATIES
)
REGIODEFINITIE = (
    "Arbeidsmarktregio (een van de 35 regio's van UWV en ROA) van de gemeente van de instelling: niet de woonregio "
    f"van de student, en niet per vestiging. De gemeente komt uit {GEMEENTEKOLOM}, anders uit DUO's adressenbestand "
    f"(adressen_mbo); de indeling is CBS {arbeidsmarktregio.bron()['tabel']} ({arbeidsmarktregio.bron()['titel']}). "
    "De chat voegt deze kolom toe; een gemeente zonder regio blijft leeg. " + HOOFDVESTIGING + " " + REGIO_VIA_LOCATIES
)
DEFINITIES = {KOLOM: DEFINITIE, REGIOKOLOM: REGIODEFINITIE}


def leidt_af(dataset_id: str, kolommen, kolom: str = KOLOM) -> bool:
    """Krijgt dit bestand `kolom` van de chat?"""
    return dataset_id in DATASETS and _CODEKOLOM in kolommen and kolom not in kolommen


def _per_code(veld: str) -> dict[str, str]:
    return {code: adres[veld] for code, adres in get_adres_lookup().items() if adres.get(veld)}


def _regio(df: pd.DataFrame, codes: pd.Series) -> pd.Series:
    if GEMEENTEKOLOM in df.columns:
        return df[GEMEENTEKOLOM].map(arbeidsmarktregio.van_gemeente)
    return codes.map(_per_code("arbeidsmarktregio"))


def met_regio(df: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    """`df` met de provincie en de arbeidsmarktregio van de instelling erbij, voor zover het bestand ze mist."""
    if not (leidt_af(dataset_id, df.columns) or leidt_af(dataset_id, df.columns, REGIOKOLOM)):
        return df
    codes = df[_CODEKOLOM].astype(str).str.strip()
    if leidt_af(dataset_id, df.columns):
        df = df.assign(**{KOLOM: codes.map(_per_code("provincie"))})
    if leidt_af(dataset_id, df.columns, REGIOKOLOM):
        df = df.assign(**{REGIOKOLOM: _regio(df, codes)})
    return df
