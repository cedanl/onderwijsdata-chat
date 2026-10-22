"""Het manifest in frontend/public (#669): geldig, binnen de scope, en elk icoon bestaat op de beloofde maat."""

import json
import re
import struct
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "frontend" / "public"
MANIFEST = json.loads((PUBLIC / "manifest.webmanifest").read_text())


def _png_maat(pad: Path) -> tuple[int, int]:
    kop = pad.read_bytes()[:24]
    assert kop[:8] == b"\x89PNG\r\n\x1a\n", pad
    return struct.unpack(">II", kop[16:24])


def test_manifest_is_installeerbaar_en_start_binnen_de_scope():
    assert MANIFEST["display"] == "standalone"
    assert MANIFEST["start_url"].startswith(MANIFEST["scope"])
    # Launchers kappen lange namen af.
    assert len(MANIFEST["short_name"]) <= 12


def test_elk_icoon_bestaat_op_de_beloofde_maat():
    for icoon in MANIFEST["icons"]:
        pad = PUBLIC / icoon["src"].lstrip("/")
        breed, hoog = icoon["sizes"].split("x")
        assert _png_maat(pad) == (int(breed), int(hoog)), icoon["src"]


def test_manifest_heeft_het_icoon_dat_chrome_vraagt_en_een_maskable():
    maten = {(i["sizes"], i["purpose"]) for i in MANIFEST["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= maten


def test_apple_touch_icon_is_180_vierkant_en_ondoorzichtig():
    pad = PUBLIC / "icons" / "apple-touch-icon.png"
    assert _png_maat(pad) == (180, 180)
    # Kleurtype 2 (RGB) heeft geen alfakanaal: iOS rondt het zelf af en vult transparantie zwart.
    assert pad.read_bytes()[25] == 2


def test_index_html_verwijst_naar_manifest_en_apple_touch_icon():
    html = (PUBLIC.parent / "index.html").read_text()
    assert '<link rel="manifest" href="/manifest.webmanifest"' in html
    href = re.search(r'rel="apple-touch-icon" href="([^"]+)"', html)
    assert href and (PUBLIC / href.group(1).lstrip("/")).is_file()
