"""De lader van CBS 85081NED (#1227): ontstane vacatures per jaar en beroep (BRC 2014), landelijk.

Alles uit het opgenomen OData-antwoord (tests/fixtures/cbs/85081NED_beroepen.json, 26-11-2026), zonder netwerk. Alle
economische activiteiten (A-U), in duizendtallen volgens de metadata (Unit "x 1 000"): totaal 1183,0 (2018) t/m 1417,0
(2025); 08 ICT beroepen 61,0 (2018) t/m 64,3 (2025). CBS noemt elk jaar 2018-2025 voorlopig. Beroepssegment 013
Leidsters kinderopvang en onderwijsassistenten en de hele klasse 02 Creatieve en taalkundige beroepen hebben lege cellen.
"""

import pytest

from core import brongebruik
from data import vacatures_ontstaan
from tests import cbs_85081ned


def _per_jaar(beroep) -> dict:
    return {w.jaar.titel: w.vacatures for w in vacatures_ontstaan.waarden(beroep)}


def test_jaren_2018_tot_2025_en_allemaal_voorlopig(cbs_ontstane_vacatures):
    jaren = vacatures_ontstaan.jaren()
    assert [j.titel for j in jaren] == [str(j) for j in range(2018, 2026)]
    assert all(j.voorlopig and j.status == "voorlopig" for j in jaren)


def test_waarden_als_aantal_volgens_de_eenheid_uit_de_metadata(cbs_ontstane_vacatures):
    assert vacatures_ontstaan.eenheid() == "x 1 000"
    totaal = vacatures_ontstaan.totaal()
    assert (totaal.niveau, totaal.label) == ("totaal", "Totaal")
    assert _per_jaar(totaal)["2018"] == 1_183_000
    assert _per_jaar(totaal)["2025"] == 1_417_000
    ict = vacatures_ontstaan.zoek("08")
    assert ict is not None and (ict.label, ict.niveau) == ("08 ICT beroepen", "klasse")
    assert _per_jaar(ict) == {
        "2018": 61_000,
        "2019": 69_500,
        "2020": 65_900,
        "2021": 87_400,
        "2022": 89_700,
        "2023": 77_500,
        "2024": 66_100,
        "2025": 64_300,
    }


def test_een_lege_cel_is_geen_gegevens_geen_nul(cbs_ontstane_vacatures):
    leidsters = vacatures_ontstaan.zoek("013")
    assert leidsters is not None and leidsters.niveau == "segment"
    waarden = vacatures_ontstaan.waarden(leidsters)
    assert [w.vacatures for w in waarden] == [None] * 8
    assert {w.status for w in waarden} == {"geen gegevens"}


def test_een_ontbrekende_rij_is_ook_geen_gegevens(monkeypatch, cbs_vacatures):
    def zonder_ict_2025(bron):
        bron["TypedDataSet"] = [
            r for r in bron["TypedDataSet"] if not (r["Beroepenindeling"] == "A000273" and r["Perioden"] == "2025JJ00")
        ]

    cbs_85081ned.zet_klaar(monkeypatch, zonder_ict_2025)
    ict = vacatures_ontstaan.zoek("ICT beroepen")
    assert ict is not None and _per_jaar(ict)["2025"] is None and _per_jaar(ict)["2024"] == 66_100
    vacatures_ontstaan._tabel.cache_clear()


@pytest.mark.parametrize(("eenheid", "factor"), [("x 1 000", 1000), ("x 1000", 1000), ("aantal", 1)])
def test_de_eenheid_bepaalt_de_factor(monkeypatch, cbs_vacatures, eenheid, factor):
    def met_eenheid(bron):
        for p in bron["DataProperties"]:
            if p["Key"] == vacatures_ontstaan.MEETWAARDE:
                p["Unit"] = eenheid

    cbs_85081ned.zet_klaar(monkeypatch, met_eenheid)
    assert _per_jaar(vacatures_ontstaan.totaal())["2018"] == round(1183.0 * factor)
    vacatures_ontstaan._tabel.cache_clear()


def test_een_onbekende_eenheid_is_een_fout_geen_gok(monkeypatch, cbs_vacatures):
    def in_procent(bron):
        for p in bron["DataProperties"]:
            if p["Key"] == vacatures_ontstaan.MEETWAARDE:
                p["Unit"] = "%"

    cbs_85081ned.zet_klaar(monkeypatch, in_procent)
    with pytest.raises(ValueError, match="onbekende eenheid"):
        vacatures_ontstaan.jaren()
    vacatures_ontstaan._tabel.cache_clear()


def test_een_definitief_jaar_is_niet_voorlopig(monkeypatch, cbs_vacatures):
    def definitief_2018(bron):
        bron["Perioden"][0]["Status"] = "Definitief"

    cbs_85081ned.zet_klaar(monkeypatch, definitief_2018)
    eerste, *rest = vacatures_ontstaan.waarden(vacatures_ontstaan.totaal())
    assert (eerste.jaar.titel, eerste.status) == ("2018", "definitief")
    assert {w.status for w in rest} == {"voorlopig"}
    vacatures_ontstaan._tabel.cache_clear()


def test_klassen_en_segmenten_van_de_brc(cbs_ontstane_vacatures):
    klassen = vacatures_ontstaan.beroepen("klasse")
    assert [k.code for k in klassen] == ["01", "02", "03", "04", "05", "06", "07", "08", "10", "11", "12"]
    techniek = vacatures_ontstaan.zoek("Technische beroepen")
    assert techniek is not None
    assert [s.code for s in vacatures_ontstaan.segmenten(techniek)] == ["072", "073", "074", "076"]
    segment = vacatures_ontstaan.zoek("072")
    assert segment is not None and vacatures_ontstaan.klasse_van(segment) == techniek


@pytest.mark.parametrize(
    ("tekst", "code"),
    [
        ("07", "07"),
        ("07 Technische beroepen", "07"),
        ("technische beroepen", "07"),
        ("Docenten", "011"),
        # CBS kort de naam af ("013 Leidsters kinderopvang en onderw..."): het volle begin past ook.
        ("Leidsters kinderopvang en onderwijsassistenten", "013"),
        ("Schoonmakers", "112"),
    ],
)
def test_zoek_een_beroep(cbs_ontstane_vacatures, tekst, code):
    beroep = vacatures_ontstaan.zoek(tekst)
    assert beroep is not None and beroep.code == code


@pytest.mark.parametrize("tekst", ["", "Astronauten", "beroepen", "Managers"])
def test_zoek_geeft_geen_gok(cbs_ontstane_vacatures, tekst):
    """Geen, of meer dan één beroep ("beroepen"; "Managers" is klasse 05 en een deel van twee segmentnamen)."""
    beroep = vacatures_ontstaan.zoek(tekst)
    assert beroep is None or (tekst == "Managers" and beroep.code == "05")


def test_de_lader_vraagt_alleen_alle_economische_activiteiten(cbs_ontstane_vacatures):
    vacatures_ontstaan.jaren()
    assert cbs_ontstane_vacatures and all(p["$filter"] == cbs_85081ned.FILTER for p in cbs_ontstane_vacatures)
    assert vacatures_ontstaan.API_URL == "https://opendata.cbs.nl/ODataApi/odata/85081NED"


def test_de_lading_meldt_haar_bron(cbs_ontstane_vacatures):
    with brongebruik.verzamel() as gemeld:
        vacatures_ontstaan.jaren()
    bron = next(b for b in gemeld if b["dataset"] == "85081NED")
    assert (bron["titel"], bron["licentie"], bron["laatste_periode"]) == (vacatures_ontstaan.TITEL, "CC BY 4.0", "2025")
    assert bron["url"] == "https://opendata.cbs.nl/#/CBS/nl/dataset/85081NED/table"
