"""Fonts are self-hosted, so the strict CSP (font-src 'self') needs no CDN exception."""
from pathlib import Path

from fastapi.testclient import TestClient

import server

INDEX_HTML = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


def test_index_html_loads_no_external_fonts():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html


def test_csp_keeps_fonts_same_origin():
    csp = TestClient(server.app).get("/health").headers["content-security-policy"]
    assert "font-src 'self'" in csp
