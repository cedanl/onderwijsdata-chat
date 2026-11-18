"""Gedeeld door de tests van "Download als Word" (#1038): het vaste rapport en kleine PNG's zonder beeldbibliotheek."""

import json
import struct
import zlib
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "rapport_docx"
# rapport.html is gemaakt met buildReportHtml (frontend/src/reportHtml.js); rapport.json is wat rapportUitHtml.js
# eruit leest. frontend/src/__tests__/rapportDocxPariteit.test.js toetst de JS-kant tegen dezelfde twee bestanden.
RAPPORT_HTML = (FIXTURES / "rapport.html").read_text(encoding="utf-8")
RAPPORT_JS = json.loads((FIXTURES / "rapport.json").read_text(encoding="utf-8"))


def _chunk(soort: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + soort + data + struct.pack(">I", zlib.crc32(soort + data))


def png(breedte: int = 4, hoogte: int = 3, *, extra: int = 0) -> bytes:
    """Een geldige grijze PNG; `extra` bytes in een eigen hulpchunk maken haar groter zonder het beeld te veranderen."""
    rijen = b"".join(b"\x00" + b"\x80" * breedte for _ in range(hoogte))
    delen = [
        b"\x89PNG\r\n\x1a\n",
        _chunk(b"IHDR", struct.pack(">IIBBBBB", breedte, hoogte, 8, 0, 0, 0, 0)),
        _chunk(b"IDAT", zlib.compress(rijen)),
    ]
    if extra:
        delen.append(_chunk(b"prVt", b"\x00" * extra))
    delen.append(_chunk(b"IEND", b""))
    return b"".join(delen)
