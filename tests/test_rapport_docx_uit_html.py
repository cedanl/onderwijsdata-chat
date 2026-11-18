"""De tekst van een bewaard rapport uit zijn HTML (#1038): de Python-tweeling van rapportUitHtml.js (#746).

Hetzelfde vaste rapport als de JS-test (tests/fixtures/rapport_docx): beide lezers moeten er hetzelfde uit halen. De
conclusie gaat daarna naar blokken, met een pipetabel als echte tabel.
"""

import pytest

from tests.rapport_docx_hulp import RAPPORT_HTML, RAPPORT_JS
from tools.rapport_docx.uit_html import Blok, conclusie_blokken, kan_docx, rapport_uit_html, veilige_url


def _als_js(r) -> dict:
    """Het rapport in de vorm van rapportUitHtml.js, om met dezelfde verwachting te vergelijken."""
    return {
        "title": r.titel,
        "meta": list(r.meta),
        "instelling": r.instelling,
        "afwijkingen": list(r.afwijkingen),
        "onderzoeksvraag": r.onderzoeksvraag,
        "beantwoordt": list(r.beantwoordt),
        "beantwoordtNiet": list(r.beantwoordt_niet),
        "definities": [{"begrip": d.begrip, "delen": list(d.delen)} for d in r.definities],
        "visualisaties": [
            {
                "titel": v.titel,
                "noot": v.noot,
                "bron": {"regel": v.bron.regel, "url": v.bron.url, "linkTekst": v.bron.link_tekst},
                "toelichting": v.toelichting,
            }
            for v in r.visualisaties
        ],
        "conclusie": r.conclusie,
        "bronnen": list(r.bronnen),
        "herkomst": list(r.herkomst),
    }


def test_leest_hetzelfde_als_de_js_tweeling():
    assert _als_js(rapport_uit_html(RAPPORT_HTML)) == RAPPORT_JS


def test_alleen_een_rapport_kan_naar_word():
    assert kan_docx(RAPPORT_HTML)
    assert not kan_docx("<p>rapport</p>")
    assert not kan_docx(None)
    assert not kan_docx("")


def test_een_pipetabel_wordt_een_tabel_met_de_kop_als_eerste_rij():
    blokken = conclusie_blokken(rapport_uit_html(RAPPORT_HTML).conclusie)
    assert [b.soort for b in blokken] == ["kop", "alinea", "punt", "punt", "tabel", "alinea"]
    tabel = blokken[4]
    assert tabel.kop == ("Jaar", "Instroom")
    assert tabel.rijen == (("2023", "**475.460**"), ("2024", "476.000"))


def test_pipe_regels_zonder_scheidingsregel_blijven_tekst():
    assert conclusie_blokken("| a | b |\n| 1 | 2 |") == (Blok(soort="alinea", regels=("| a | b |", "| 1 | 2 |")),)


def test_een_rij_krijgt_de_breedte_van_de_kop():
    (tabel,) = conclusie_blokken("| a | b | c |\n|:--|---|--:|\n| 1 |\n| 1 | 2 | 3 | 4 |")
    assert tabel.rijen == (("1", "", ""), ("1", "2", "3"))


def test_regels_zonder_lege_regel_ertussen_vormen_een_alinea():
    assert conclusie_blokken("een\ntwee\n\ndrie") == (
        Blok(soort="alinea", regels=("een", "twee")),
        Blok(soort="alinea", regels=("drie",)),
    )


def test_alleen_een_http_adres_wordt_een_link():
    html = (
        '<div class="vraag"><div class="vraag-text">V</div></div>'
        '<div class="vis"><h3 class="vis-title">A</h3><p class="vis-bron">Bron: X · <a href="javascript:alert(1)">klik</a></p></div>'
        '<div class="vis"><h3 class="vis-title">B</h3><p class="vis-bron">Bron: Y · <a href="https://example.org/y">Bekijk</a></p></div>'
    )
    a, b = rapport_uit_html(html).visualisaties
    assert (a.bron.regel, a.bron.url) == ("Bron: X", None)
    assert (b.bron.regel, b.bron.url, b.bron.link_tekst) == ("Bron: Y", "https://example.org/y", "Bekijk")


@pytest.mark.parametrize(
    "url",
    ["https://ok.nl/\x01x", "https://ok.nl/\x07", "https://ok.nl/a\nb", "https://ok.nl/\x7f", "https://ok.nl/\ufffe"],
)
def test_een_adres_met_een_stuurteken_wordt_geen_link(url):
    assert veilige_url(url) is None


def test_een_gewoon_adres_blijft_een_link():
    assert veilige_url("https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85353NED?a=1&b=é") is not None


def test_een_script_in_het_rapport_is_alleen_tekst():
    html = '<div class="vraag"><div class="vraag-text">Vraag<script>document.title="x"</script></div></div>'
    assert rapport_uit_html(html).onderzoeksvraag == 'Vraagdocument.title="x"'


def test_een_ouder_of_leeg_rapport_geeft_lege_onderdelen():
    leeg = rapport_uit_html('<div class="vraag"><div class="vraag-text">Alleen een vraag</div></div>')
    assert leeg.onderzoeksvraag == "Alleen een vraag"
    assert (leeg.titel, leeg.meta, leeg.visualisaties, leeg.conclusie, leeg.bronnen) == ("", (), (), "", ())
    assert rapport_uit_html("").onderzoeksvraag == ""
