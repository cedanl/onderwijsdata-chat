"""Schooljaren: van de vraag naar de broncode en terug (#187).

Een schooljaar heet naar zijn startjaar: 2025/26 is CBS-periode 2025SJ00 en
DUO STUDIEJAAR 2025 (peildatum 1 oktober 2025). Het model vertaalde dat zelf en
koos daarbij soms het jaar ervoor; hier gebeurt het in code, op één plek.
"""

import re

import pandas as pd

# 2025/26, 2025-2026, 2025/'26, 2025–26. Een los "2025" is dubbelzinnig en telt niet.
_SCHOOLJAAR = re.compile(r"(?<!\d)(20\d{2})\s*[/\-–]\s*'?(\d{4}|\d{2})(?!\d)")
# 2024 tot 2030, 2024 t/m 2030, 2030-2024, 2024 → 2030: kale jaartallen, zoals DUO's JAAR ze heeft.
# Twee opeenvolgende jaren met een streepje (2024-2025) zijn een schooljaar, geen bereik.
_JAARBEREIK = re.compile(r"(?<![\d/'])(20\d{2})\s*(tot(?:\s+en\s+met)?|t/m|[-–→]|naar)\s*(20\d{2})(?![\d/])")
_CBS_SCHOOLJAAR = re.compile(r"^(\d{4})SJ\d{2}$")
_DUO_PERIODEKOLOMMEN = ("STUDIEJAAR", "JAAR")

# Jaarkolommen die geen schooljaar zijn en waarvan de bron niet zegt welk soort jaar het is
# (CH-41). Bewust geen omzetting: diplomajaar 2023 blijft diplomajaar 2023, tenzij een
# officiële bron onderbouwt welk studiejaar dat is.
GEEN_SCHOOLJAAR = {
    "DIPLOMAJAAR": (
        "DIPLOMAJAAR is het jaar van het diploma; DUO legt niet vast of dat een kalenderjaar of een "
        "studiejaar is. Diplomajaar 2023 is dus niet aantoonbaar studiejaar 2023/24."
    ),
}


def jaarnoten(kolommen) -> list[str]:
    """Wat een antwoord moet zeggen over de jaarkolommen van deze data die geen schooljaar zijn."""
    return [noot for kolom, noot in GEEN_SCHOOLJAAR.items() if kolom in kolommen]


def gevraagde_schooljaren(tekst: str) -> set[int]:
    """Startjaren van de schooljaren die de tekst eenduidig noemt."""
    jaren: set[int] = set()
    for start, eind in _SCHOOLJAAR.findall(tekst):
        begin = int(start)
        volgend = begin + 1 if len(eind) == 4 else (begin + 1) % 100
        if int(eind) == volgend:
            jaren.add(begin)
    return jaren


def jaarbereiken(tekst: str) -> set[int]:
    """Begin- en eindjaar van elk bereik in kale jaartallen dat de tekst noemt."""
    jaren: set[int] = set()
    for begin, scheiding, eind in _JAARBEREIK.findall(tekst):
        if abs(int(begin) - int(eind)) == 1 and scheiding in "-–":
            continue
        jaren |= {int(begin), int(eind)}
    return jaren


def genoemd_bereik(tekst: str) -> tuple[int, int] | None:
    """Eerste en laatste startjaar van het periodebereik dat de tekst noemt; None zonder bereik."""
    jaren = gevraagde_schooljaren(tekst) | jaarbereiken(tekst)
    return (min(jaren), max(jaren)) if len(jaren) >= 2 else None


def schooljaarbereik(van: str, tot: str) -> tuple[int, int] | None:
    """Startjaren van twee periodelabels (2024/25); None als een van beide geen schooljaar is."""
    begin = next(iter(gevraagde_schooljaren(van)), None)
    eind = next(iter(gevraagde_schooljaren(tot)), None)
    return None if begin is None or eind is None else (begin, eind)


def label(startjaar: int) -> str:
    return f"{startjaar}/{(startjaar + 1) % 100:02d}"


STUDIEJAAR_LABEL = "STUDIEJAAR_LABEL"


def studiejaar_label(startjaar: int) -> str:
    """Het volledige label van een DUO-studiejaar: 2021 is 2021/2022 (#115)."""
    return f"{startjaar}/{startjaar + 1}"


def met_studiejaarlabel(df: pd.DataFrame) -> pd.DataFrame:
    """Zet naast een DUO-STUDIEJAAR het label, zodat het model de jaren niet zelf omrekent."""
    if "STUDIEJAAR" not in df.columns or STUDIEJAAR_LABEL in df.columns:
        return df
    jaren = pd.to_numeric(df["STUDIEJAAR"], errors="coerce")
    labels = jaren.map(lambda j: studiejaar_label(int(j)) if pd.notna(j) else None)
    return df.assign(**{STUDIEJAAR_LABEL: labels})


def met_labelkolom_in_groep(df: pd.DataFrame, group_by: list[str] | None) -> list[str] | None:
    """Groepeer je op STUDIEJAAR, dan reist het label mee: het hangt er één-op-één aan."""
    if group_by and "STUDIEJAAR" in group_by and STUDIEJAAR_LABEL in df.columns and STUDIEJAAR_LABEL not in group_by:
        return [*group_by, STUDIEJAAR_LABEL]
    return group_by


def labels(startjaren) -> list[str]:
    return [label(j) for j in startjaren or ()]


def broncode(bron: str, startjaar: int) -> str:
    """Hoe de bron dit schooljaar noemt, voor in een foutmelding aan het model."""
    return f"{startjaar}SJ00" if bron == "cbs" else f"STUDIEJAAR={startjaar}"


def startjaar(bron: str, waarde) -> int | None:
    """Startjaar van een periodewaarde; None als het geen schooljaar is (bijv. CBS-kalenderjaar)."""
    if bron == "cbs":
        match = _CBS_SCHOOLJAAR.match(str(waarde).strip())
        return int(match.group(1)) if match else None
    try:
        return int(float(waarde))
    except (TypeError, ValueError):
        return None


def duo_periodekolom(kolommen) -> str | None:
    return next((k for k in _DUO_PERIODEKOLOMMEN if k in kolommen), None)


def dekking(df: pd.DataFrame, bron: str, kolom: str | None) -> tuple[int, ...] | None:
    """De schooljaren (startjaren) in `df`; () bij een lege selectie, None als onbekend."""
    if not kolom or kolom not in df.columns:
        return None
    if df.empty:
        return ()
    jaren = {startjaar(bron, v) for v in df[kolom].dropna().unique()} - {None}
    return tuple(sorted(jaren)) if jaren else None
