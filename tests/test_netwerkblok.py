"""Het netwerkblok van de tests bewaakt (#915): naar buiten dicht, lokaal open, live-tests open.

De CI-pytest haalde UWV stil live op en faalde op runners zonder route naar data.overheid.nl. Het blok in
`tests/netwerkblok.py` (aangezet in `tests/conftest.py`) laat zo'n test overal falen, met de host erbij.
"""

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import httpx
import pytest

from tests.netwerkblok import BLOK, UITLEG, NetwerkGeblokkeerd, is_lokaal, melding

ROOT = Path(__file__).resolve().parent.parent
# TEST-NET-1 (RFC 5737): een adres buiten deze machine dat nooit iemand is.
BUITEN_IP = "192.0.2.1"


@pytest.fixture
def weigeringen_vergeten():
    """Voor de tests hieronder die bewust naar buiten proberen: hun weigeringen laten de test zelf niet falen."""
    yield
    BLOK.pogingen.clear()


@pytest.mark.usefixtures("weigeringen_vergeten")
class TestNaarBuitenDicht:
    def test_httpx_naar_een_bron_faalt_met_de_host_en_wat_te_doen(self):
        with pytest.raises(NetwerkGeblokkeerd, match=r"data\.overheid\.nl") as fout:
            httpx.get("https://data.overheid.nl/", timeout=1)
        assert UITLEG in str(fout.value)

    def test_de_dns_vraag_zelf_faalt(self):
        with pytest.raises(NetwerkGeblokkeerd, match=r"example\.org"):
            socket.getaddrinfo("example.org", 443)

    def test_een_verbinding_naar_een_ip_buiten_faalt(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            with pytest.raises(NetwerkGeblokkeerd, match=BUITEN_IP):
                sock.connect((BUITEN_IP, 80))
            with pytest.raises(NetwerkGeblokkeerd, match=BUITEN_IP):
                sock.connect_ex((BUITEN_IP, 80))

    def test_elke_weigering_wordt_onthouden_ook_als_de_code_hem_opvangt(self):
        """De conftest laat de test daarop falen: een stille terugval hangt in CI van het netwerk af."""
        with contextlib.suppress(Exception):
            httpx.get("https://duo.nl/", timeout=1)
        assert BLOK.pogingen == ["duo.nl"]
        assert "duo.nl" in melding(BLOK.pogingen) and UITLEG in melding(BLOK.pogingen)


class TestLokaalOpen:
    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
    def test_een_tcp_server_op_deze_machine(self, host):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with socket.create_connection((host, server.getsockname()[1]), timeout=2):
                pass

    @pytest.mark.skipif(not socket.has_ipv6, reason="geen IPv6 in deze omgeving")
    def test_ipv6_loopback(self):
        try:
            server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            server.bind(("::1", 0))
        except OSError:
            pytest.skip("::1 niet beschikbaar")
        with server:
            server.listen(1)
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                sock.connect(("::1", server.getsockname()[1]))

    def test_een_unix_socket(self):
        # Kort pad: AF_UNIX staat maar ~100 tekens toe, tmp_path is vaak langer.
        with tempfile.TemporaryDirectory(dir="/tmp") as map_:
            pad = os.path.join(map_, "s")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(pad)
                server.listen(1)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.connect(pad)

    def test_een_http_server_op_localhost_via_httpx(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Antwoord(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(204)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Antwoord)
        draad = threading.Thread(target=server.handle_request, daemon=True)
        draad.start()
        try:
            assert httpx.get(f"http://localhost:{server.server_port}/", timeout=2, trust_env=False).status_code == 204
        finally:
            draad.join(timeout=2)
            server.server_close()

    @pytest.mark.parametrize(
        "host", [None, "", "localhost", "LOCALHOST.", "db.localhost", "127.0.0.53", "::1", "0.0.0.0"]
    )
    def test_lokale_vormen(self, host):
        assert is_lokaal(host)

    @pytest.mark.parametrize("host", ["data.overheid.nl", "postgres", BUITEN_IP, "2001:db8::1", b"duo.nl"])
    def test_vormen_buiten(self, host):
        assert not is_lokaal(host)


@pytest.mark.live
def test_een_live_test_mag_naar_buiten():
    """Draait alleen met `-m live` (in de run van de test hieronder): het blok staat open."""
    assert BLOK.open
    # Een numeriek adres: getaddrinfo vraagt dan geen DNS, dus dit raakt het netwerk niet.
    assert socket.getaddrinfo(BUITEN_IP, 80)


def test_het_blok_staat_open_voor_een_live_test():
    """Via de echte conftest in een eigen run: de marker `live` zet het blok voor die test open."""
    run = subprocess.run(
        [sys.executable, "-m", "pytest", f"{__file__}::test_een_live_test_mag_naar_buiten", "-m", "live", "-q",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 passed" in run.stdout


def test_de_pakketten_hebben_hetzelfde_blok():
    """De pakketten importeren de chat niet (#886) en hebben daarom een kopie; die mag niet uit de pas lopen."""
    pakketten = sorted(p for p in (ROOT / "packages").iterdir() if (p / "pyproject.toml").is_file())
    assert pakketten
    origineel = (ROOT / "tests" / "netwerkblok.py").read_text()
    for pakket in pakketten:
        kopie = pakket / "tests" / "netwerkblok.py"
        assert kopie.is_file(), f"{kopie} ontbreekt"
        assert kopie.read_text() == origineel, f"{kopie} wijkt af van tests/netwerkblok.py"
        assert "BLOK.installeer()" in (pakket / "tests" / "conftest.py").read_text()
