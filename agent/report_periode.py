"""De periode van een rapport: het startjaar van een tijdaswaarde en de periode in de rapporttitel (#385, #893).

Tot #993 sneed de code een grafiek van het rapportmodel bij tot de periode in haar titel (#385). Het rapport toont nu
alleen figuren uit het gesprek, zoals de gebruiker ze daar zag (besluit 18-11): die worden niet meer bijgesneden.
"""

from __future__ import annotations

import re

from tools import periode

# Een tijdas: jaartal, schooljaar (2021/22, 2021/2022) of CBS-periodecode (2021SJ00, 2021JJ00).
_JAARTAL = re.compile(r"^(20\d{2})$")
_CBS_PERIODE = re.compile(r"^(20\d{2})(?:SJ|JJ)\d{2}$")


def startjaar(waarde) -> int | None:
    """Het startjaar van een tijdaswaarde (2021, 2021/22, 2021SJ00); None als het geen jaar is."""
    if isinstance(waarde, bool):
        return None
    if isinstance(waarde, int | float):
        return int(waarde) if float(waarde).is_integer() and 2000 <= waarde < 2100 else None
    tekst = str(waarde).strip()
    if match := _JAARTAL.match(tekst) or _CBS_PERIODE.match(tekst):
        return int(match.group(1))
    jaren = periode.gevraagde_schooljaren(tekst)
    return next(iter(jaren)) if len(jaren) == 1 else None


def gevraagd_bereik(*teksten: str) -> tuple[int, int] | None:
    """Het eerste periodebereik dat een van de teksten noemt, in volgorde van voorrang."""
    return next((b for t in teksten if t and (b := periode.genoemd_bereik(t))), None)


def titelperiode(figuurperioden: list[tuple[int, int] | None], onderzoeksvraag: str) -> tuple[int, int] | None:
    """De periode die de rapporttitel noemt (#893): wat de figuren samen dekken (startjaren), begrensd tot het bereik
    van de onderzoeksvraag als die er een noemt.
    None als geen figuur haar periode kent."""
    bekend = [p for p in figuurperioden if p]
    if not bekend:
        return None
    data = (min(p[0] for p in bekend), max(p[1] for p in bekend))
    if not (gevraagd := gevraagd_bereik(onderzoeksvraag)):
        return data
    begrensd = (max(data[0], gevraagd[0]), min(data[1], gevraagd[1]))
    return begrensd if begrensd[0] <= begrensd[1] else data
