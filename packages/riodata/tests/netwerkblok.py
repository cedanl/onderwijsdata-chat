"""Uitgaand netwerk dicht in de tests (#915): een test die stil een live bron ophaalt, faalt met de host erbij.

Geïnstalleerd op socketniveau, zodat het voor elke client geldt (httpx, urllib, requests, asyncio): de DNS-vraag
(`socket.getaddrinfo`) en de verbinding (`socket.socket.connect`, `connect_ex`) naar een host buiten deze machine
falen met `NetwerkGeblokkeerd`. Lokaal blijft open: localhost, 127.0.0.0/8, ::1 en Unix-sockets, voor TestClient, de
lokale testservers en een Postgres op dezelfde host. Subprocessen (helm, `uv build`) vallen er buiten.

Elke weigering wordt onthouden. De conftest laat een test daarna alsnog falen, ook als de code de fout opving en
terugviel op iets anders: dat pad hangt in CI af van het netwerk van de runner, en dat is precies wat hier dicht moet.

Dit bestand staat ook in `packages/*/tests/` (de pakketten importeren de chat niet, #886); `tests/test_netwerkblok.py`
bewaakt dat de kopieën gelijk blijven. Pas het dus overal tegelijk aan.
"""

from __future__ import annotations

import ipaddress
import socket

UITLEG = "markeer de test als live of gebruik een fixture"


class NetwerkGeblokkeerd(RuntimeError):
    """Een test zonder live-markering probeerde naar buiten te gaan."""


def is_lokaal(host: object) -> bool:
    """Of een verbinding naar `host` op deze machine blijft; alleen de vorm, zonder naamopvraging."""
    if host is None:
        return True  # getaddrinfo(None, poort): het eigen adres
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    if not isinstance(host, str):
        return True  # geen IP-familie (netlink en dergelijke)
    naam = host.rstrip(".").lower()
    if naam in ("", "localhost") or naam.endswith(".localhost"):
        return True
    try:
        adres = ipaddress.ip_address(naam.split("%", 1)[0])
    except ValueError:
        return False  # een hostnaam: die ligt buiten deze machine
    return adres.is_loopback or adres.is_unspecified


class Blok:
    """De drie socketfuncties met een poort ervoor; `begin(open=True)` zet hem voor één test open (live)."""

    def __init__(self) -> None:
        self.open = False
        self.pogingen: list[str] = []
        self._origineel: dict = {}

    def installeer(self) -> None:
        if self._origineel:
            return
        getaddrinfo, connect, connect_ex = socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex
        self._origineel = {"getaddrinfo": getaddrinfo, "connect": connect, "connect_ex": connect_ex}
        blok = self

        def bewaakte_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            blok.toets(host)
            return getaddrinfo(host, port, family, type, proto, flags)

        def bewaakte_connect(sock, adres):
            blok.toets_adres(sock, adres)
            return connect(sock, adres)

        def bewaakte_connect_ex(sock, adres):
            blok.toets_adres(sock, adres)
            return connect_ex(sock, adres)

        # De stub van getaddrinfo typeert het precieze retourtype; de bewaker geeft het ongewijzigd door.
        socket.getaddrinfo = bewaakte_getaddrinfo  # ty: ignore[invalid-assignment]
        socket.socket.connect = bewaakte_connect
        socket.socket.connect_ex = bewaakte_connect_ex

    def verwijder(self) -> None:
        if not self._origineel:
            return
        socket.getaddrinfo = self._origineel["getaddrinfo"]
        socket.socket.connect = self._origineel["connect"]
        socket.socket.connect_ex = self._origineel["connect_ex"]
        self._origineel = {}

    def begin(self, *, open: bool) -> None:
        """Bij de start van een test: de poort open of dicht, en geen weigeringen van een vorige test."""
        self.open = open
        self.pogingen.clear()

    def einde(self) -> list[str]:
        """Bij het einde van een test: de geweigerde hosts, en de poort weer dicht tot de volgende test."""
        pogingen, self.pogingen = self.pogingen, []
        self.open = False
        return pogingen

    def toets(self, host: object) -> None:
        if self.open or is_lokaal(host):
            return
        self.pogingen.append(str(host))
        raise NetwerkGeblokkeerd(f"uitgaand netwerk naar {host} is dicht in tests: {UITLEG}")

    def toets_adres(self, sock: socket.socket, adres: object) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(adres, tuple):
            self.toets(adres[0])


def melding(pogingen: list[str]) -> str:
    """De faalreden van een test die naar buiten probeerde, ook als de code de weigering zelf opving."""
    hosts = ", ".join(dict.fromkeys(pogingen))
    return f"deze test probeerde naar buiten te gaan ({hosts}): {UITLEG}"


BLOK = Blok()
