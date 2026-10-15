"""Geheugengebruik van het serverproces, voor het log (#546).

De testpod werd tijdens zware analyses OOMKilled op de limiet van 2 GiB (14-10-2026, vier
herstarts, de laatste om 17:58 UTC midden in de testronde). Met het proces vielen alle open
WebSockets weg en de browser zei "Verbinding verbroken — antwoord onvolledig". Van buiten was
niet te zien welke stap het geheugen opjoeg. Elke toolstap logt nu het residente geheugen van
het proces en de omvang van de datastore, alleen getallen, zodat de volgende maatregel (limiet,
STORE_MAX_MB, een loader) op een meting rust.
"""

import os
from pathlib import Path

_STATM = Path("/proc/self/statm")
_PAGINA = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def rss_mb() -> int | None:
    """Het residente geheugen van dit proces in MiB; None waar /proc ontbreekt (macOS, Windows)."""
    try:
        velden = _STATM.read_text().split()
        return int(velden[1]) * _PAGINA // 2**20
    except (OSError, IndexError, ValueError):
        return None
