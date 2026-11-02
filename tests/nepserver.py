"""Een nepbron op 127.0.0.1 voor tests die de echte `httpx.get` van de bronpakketten laten lopen (#867, #868).

De pakketten `onderwijsdata` en `riodata` roepen `httpx.get` op een vaste basis-URL aan; een test zet die URL op
deze server (monkeypatch van `BASE_FEED`, `CKAN_BASE`, ...) en geeft per verzoek een antwoord. Geen netwerk buiten
de machine, wel een echte HTTP-ronde: status, headers en body gaan door httpx zoals bij de bron.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class Antwoord:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Nepserver:
    url: str
    verzoeken: list[str] = field(default_factory=list)  # pad plus querystring, in volgorde


@contextmanager
def nepserver(antwoord: Callable[[str], Antwoord]) -> Generator[Nepserver]:
    """Start de server; `antwoord(pad)` beslist per GET wat hij teruggeeft."""
    server: Nepserver

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            server.verzoeken.append(self.path)
            uit = antwoord(self.path)
            self.send_response(uit.status)
            for naam, waarde in {"Content-Length": str(len(uit.body)), **uit.headers}.items():
                self.send_header(naam, waarde)
            self.end_headers()
            self.wfile.write(uit.body)

        def log_message(self, format, *args):  # geen ruis in de testuitvoer
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server = Nepserver(f"http://127.0.0.1:{http.server_address[1]}")
    draad = threading.Thread(target=http.serve_forever, daemon=True)
    draad.start()
    try:
        yield server
    finally:
        http.shutdown()
        http.server_close()


def reeks(*antwoorden: Antwoord) -> Callable[[str], Antwoord]:
    """Een antwoord per verzoek, in volgorde; het laatste herhaalt zich."""
    rest = list(antwoorden)

    def volgende(_pad: str) -> Antwoord:
        return rest.pop(0) if len(rest) > 1 else rest[0]

    return volgende
