"""SRAM-korte namen en e-maildomeinen komen via de registry bij de frontend-prefill (#233).

oidc_callback geeft ruwe org/institution/email_domein door; de frontend
(instellingenMatch.js) matcht die tegen de aliassen en domeinen die
_apply_sram_mappings in de registry zet. Dat is de enige route.
"""

from data.instellingen import _apply_sram_mappings


def _registry(*namen):
    return {naam: {"naam": naam, "aliassen": [], "domeinen": []} for naam in namen}


def test_sram_korte_naam_wordt_alias_van_de_instelling():
    result = _apply_sram_mappings(_registry("Hogeschool Utrecht", "Universiteit van Amsterdam"))
    assert "hu" in result["Hogeschool Utrecht"]["aliassen"]
    assert "uva" in result["Universiteit van Amsterdam"]["aliassen"]


def test_alle_nhl_stenden_domeinen_komen_in_de_registry():
    # De tweede DOMEINEN-entry overschreef de eerste: nhlstenden.nl ontbrak (#202).
    result = _apply_sram_mappings(_registry("NHL Stenden Hogeschool"))
    assert {"nhlstenden.nl", "nhl.nl", "stenden.com"} <= set(result["NHL Stenden Hogeschool"]["domeinen"])


def test_onbekende_instelling_krijgt_geen_mapping():
    result = _apply_sram_mappings(_registry("Bestaat Niet"))
    assert result["Bestaat Niet"] == {"naam": "Bestaat Niet", "aliassen": [], "domeinen": []}
