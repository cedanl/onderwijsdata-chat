"""De verzameling voor de Prompt Library (#1047, B) blijft een verzameling geteste vragen die als deep link werkt."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import prompt_library_export as export

BASIS = "https://onderwijsdata-chat.test.sdp.surf.nl"
# De kolommen die de bulkimport van de library kent (app/importing.py, COLUMNS).
KOLOMMEN_LIBRARY = {
    "titel", "samenvatting", "prompttekst", "taal", "tips", "waarom_dit_werkt",
    "voorbeelduitkomst", "getest_in", "bron", "licentie", "labels",
}  # fmt: skip


def test_elke_vraag_is_een_geteste_vraag_uit_de_evaluatieset():
    """Een label dat uit de evaluatieset verdwijnt of een andere naam krijgt, breekt de verzameling hier."""
    assert export.rijen(BASIS)


def test_de_verzameling_is_klein_en_de_library_neemt_haar_aan():
    uit = export.rijen(BASIS)
    assert 5 <= len(uit) <= 10, "5 tot 10 vragen (#1047); de library neemt er hoogstens 100 per bestand"
    for rij in uit:
        assert set(rij) <= KOLOMMEN_LIBRARY
        assert len(rij["titel"]) <= 200
        assert len(rij["samenvatting"]) <= 1000
        assert len(rij["bron"]) <= 500
    assert len({r["titel"] for r in uit}) == len(uit), "de library waarschuwt bij dubbele titels"
    assert all("getest_in" not in r and "licentie" not in r for r in uit), "EDUdata staat niet op de lijst van ADR-008"


def test_de_deep_link_geeft_de_vraag_terug():
    for rij in export.rijen(BASIS):
        link = rij["bron"].rsplit(" ", 1)[1]
        deel = urlsplit(link)
        assert (deel.scheme, deel.netloc, deel.path) == ("https", "onderwijsdata-chat.test.sdp.surf.nl", "/chat")
        # De app leest het fragment als query (URLSearchParams, voorgevuldeVraag.js).
        assert parse_qs(deel.fragment) == {"vraag": [rij["prompttekst"]]}
        assert "?" not in link, "de vraag staat in het fragment, niet in de query (docs/api.md)"


def test_een_vraag_staat_op_een_regel_zonder_hoekige_haken():
    """Wat `schoonVraag` weghaalt, mag er niet in staan: dan is de link niet de vraag."""
    for rij in export.rijen(BASIS):
        assert "\n" not in rij["prompttekst"]
        assert "<" not in rij["prompttekst"] and ">" not in rij["prompttekst"]
        assert len(rij["prompttekst"]) <= export.MAX_VRAAG


@pytest.mark.parametrize("basis", ["http://x.nl", "https://x.nl/chat", "https://x.nl/?a=1", "x.nl", ""])
def test_een_basis_url_met_pad_of_zonder_https_wordt_geweigerd(basis):
    with pytest.raises(ValueError, match="basis-url"):
        export.rijen(basis)


def test_een_onbekend_label_wordt_geweigerd(monkeypatch, tmp_path):
    bestand = tmp_path / "vragen.json"
    bestand.write_text(json.dumps({"vragen": [{"eval": "bestaat-niet"}]}), encoding="utf-8")
    monkeypatch.setattr(export, "VRAGEN", bestand)
    with pytest.raises(ValueError, match="bestaat-niet"):
        export.rijen(BASIS)
