"""Tests voor de notes-parser (riodata.duo_notes), op vastgelegde CKAN-responses."""
import json
from pathlib import Path

import pytest

from riodata.duo_notes import details_from_pkg, parse_notes

FIXTURES = Path(__file__).parent / "fixtures"


def _details(dataset_id: str) -> dict:
    return details_from_pkg(json.loads((FIXTURES / f"{dataset_id}.json").read_text(encoding="utf-8")))


class TestTelverschilHo:
    def test_p01_personen_met_hoofdinschrijving(self):
        t = _details("p01hoinges")["_teldefinitie"]
        assert t["teleenheid"] == "personen"
        assert t["inschrijvingstype"] == "hoofdinschrijvingen"
        assert t["peildatum"] == "1 oktober"
        assert t["ontdubbelingsdomein"]["waarde"] == "hoger onderwijs"

    def test_p03_inschrijvingen_incl_neveninschrijvingen(self):
        t = _details("p03hoinschr")["_teldefinitie"]
        assert t["teleenheid"] == "inschrijvingen"
        assert t["inschrijvingstype"] == "hoofd- en neveninschrijvingen"
        assert t["ontdubbelingsdomein"] is None

    def test_p02_eerstejaars_sluit_hbo_master_uit(self):
        d = _details("p02ho1ejrs")
        uitsluitingen = [u["tekst"] for u in d["_teldefinitie"]["uitsluitingen"]]
        assert any("master inschrijvingen in het hoger beroepsonderwijs" in u for u in uitsluitingen)
        assert "Eerstejaars ingeschrevenen" in d["_teldefinitie"]["selectie"]

    def test_drie_datasets_zijn_onderscheidbaar(self):
        kaarten = {
            ds: json.dumps(_details(ds)["_zoekkaart"], sort_keys=True)
            for ds in ("p01hoinges", "p02ho1ejrs", "p03hoinschr")
        }
        assert len(set(kaarten.values())) == 3


class TestKopvarianten:
    @pytest.mark.parametrize("kop", ["Selectie", "Selecties", "Selectiecriteria"])
    def test_selectiesectie_onder_alle_kopvarianten(self, kop):
        r = parse_notes(f"## {kop}\nTelt personen.\n\n## Periode\nJaarlijks.")
        assert r["teldefinitie"]["selectie"] == "Telt personen."


class TestPublicatieregel:
    @pytest.mark.parametrize("ds", ["p01hoinges", "p02ho1ejrs", "p03hoinschr"])
    def test_1_tot_4_wordt_4_met_bronpassage(self, ds):
        (regel,) = _details(ds)["_publicatieregels"]
        assert regel["bereik"] == [1, 4]
        assert regel["gepubliceerd_als"] == 4
        assert "weergegeven door 4" in regel["bronpassage"]
        assert regel["toepassingsgebied"]["dataset"] == ds
        assert regel["sectie"] == "Toelichting"

    def test_resource_en_meetkolom_blijven_onbekend(self):
        (regel,) = _details("p01hoinges")["_publicatieregels"]
        assert regel["toepassingsgebied"]["meetkolom"] is None
        assert regel["toepassingsgebied"]["resources"] == "niet gespecificeerd in bron"

    def test_geen_regel_zonder_bronpassage(self):
        assert _details("p01hoinges")["_publicatieregels"][0]["maat"] == "aantal ingeschrevenen"
        assert parse_notes("## Inleiding\nGeen filter hier.")["publicatieregels"] == []


class TestBrongetrouwheid:
    def test_volledige_notes_blijven_behouden(self):
        pkg = json.loads((FIXTURES / "p01hoinges.json").read_text(encoding="utf-8"))
        d = details_from_pkg(pkg)
        assert d["_details"]["notes"] == pkg["notes"]
        assert len(d["_details"]["notes"]) > 300

    def test_provenance_herleidbaar_naar_revisie(self):
        prov = _details("p02ho1ejrs")["_notes_provenance"]
        assert prov["bron_url"].endswith("/dataset/p02ho1ejrs")
        assert prov["metadata_modified"].startswith("2026-")
        assert len(prov["notes_sha256"]) == 64
        assert prov["parse_status"] == "ok"

    def test_onbekende_publicatieregel_wordt_zichtbaar(self):
        r = parse_notes("## Toelichting\nEr is een AVG-filter toegepast op kleine aantallen.")
        assert r["parse_status"] == "gedeeltelijk"
        assert "publicatieregel genoemd in notes maar niet geparseerd" in r["parse_fouten"]

    def test_conflicterende_regels_worden_gemeld(self):
        tekst = (
            "## Toelichting\nAantallen kleiner dan 5 (1,2,3,4) allemaal worden weergegeven door 4. "
            "Verder zijn aantallen kleiner dan 3 (1,2) allemaal worden weergegeven door 2."
        )
        r = parse_notes(tekst.replace("Aantallen", "aantallen", 1))
        assert any("bronconflict" in f for f in r["parse_fouten"])

    def test_geen_globale_omzetting_van_vieren(self):
        # De regel beschrijft de publicatiewaarde (4); er is geen omzettingsveld naar null/NaN.
        for ds in ("p01hoinges", "p02ho1ejrs", "p03hoinschr"):
            for regel in _details(ds)["_publicatieregels"]:
                assert regel["gepubliceerd_als"] == 4
                assert not {"vervang_door", "omzetten_naar", "genormaliseerd"} & regel.keys()

    def test_lege_notes_crashen_niet(self):
        r = parse_notes(None)
        assert r["parse_status"] == "ongestructureerd"
        assert r["teldefinitie"]["teleenheid"] is None


class TestZoekkaart:
    def test_compact_en_bevat_kritieke_beperking(self):
        kaart = _details("p02ho1ejrs")["_zoekkaart"]
        assert kaart["publicatieregels"] == ["1–4 gepubliceerd als 4"]
        assert len(json.dumps(kaart)) < 600
