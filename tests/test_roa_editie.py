"""De app laadt de ROA-editie die de catalogus de nieuwste noemt, en leest de thema's uit dat bestand (#1091).

Dashboards, get_roa_benchmark en de snippet laadden `roa.load("ais2030", "arbeidsmarkt")`: editie 2025, terwijl de
catalogus editie 2026 (`arbeidsmarkt_editie2026`) als `meest_recente_editie` markeert. Het SIS-thema stond als vaste
tekst in de code ("SIS 2024"); in editie 2026 heet het "SIS 2025" en de prognose "…, actualisering", zodat een vaste
tekst bij een nieuwe editie een lege tabel gaf.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

import data.dashboard as dashboard
from data import arbeidsmarkt
from tools import snippet
from tools.arbeidsmarkt import get_roa_benchmark

_DOCS = Path(__file__).resolve().parent.parent / "docs" / "databronnen.md"


def _arbeidsmarktbestanden() -> list[dict]:
    from onderwijsbronnen import roa

    record = next(r for r in roa.catalog() if r["_roa_id"] == "ais2030")
    return [x for x in record["_resources"] if (x.get("schema") or {}).get("soort") == "arbeidsmarkt"]


def test_de_app_laadt_de_nieuwste_editie_van_de_catalogus_of_een_pin_met_reden():
    """Faalt zodra de catalogus een nieuwere editie de nieuwste noemt dan de app laadt, tenzij een pin het uitlegt."""
    bestanden = _arbeidsmarktbestanden()
    nieuwste = max(bestanden, key=lambda x: int(x["schema"]["editie"]))
    gemarkeerd = [x["naam"] for x in bestanden if x["schema"].get("meest_recente_editie")]
    assert gemarkeerd == [nieuwste["naam"]], "de catalogus markeert een andere editie als nieuwste"

    bestand = arbeidsmarkt.roa_bestand()

    if arbeidsmarkt.ROA_PIN is None:
        assert (bestand.resource, bestand.editie) == (nieuwste["naam"], nieuwste["schema"]["editie"])
        assert bestand.pin is None
    else:
        # Een bewuste pin: met de reden in de code én in docs/databronnen.md.
        assert arbeidsmarkt.ROA_PIN_REDEN and bestand.pin == arbeidsmarkt.ROA_PIN_REDEN
        docs = _DOCS.read_text(encoding="utf-8")
        assert arbeidsmarkt.ROA_PIN in docs and arbeidsmarkt.ROA_PIN_REDEN in docs


def test_nu_is_dat_editie_2026_met_sis_2025():
    bestand = arbeidsmarkt.roa_bestand()

    assert (bestand.resource, bestand.editie) == ("arbeidsmarkt_editie2026", "2026")
    assert arbeidsmarkt.roa_sis(bestand.themas) == "SIS 2025"


@pytest.mark.parametrize(
    ("editie", "sis", "prognose"),
    [
        ("2025", "SIS 2024", "Risicoindicatoren en arbeidsmarktprognoses tot 2030"),
        ("2026", "SIS 2025", "Risicoindicatoren en arbeidsmarktprognoses tot 2030, actualisering"),
    ],
)
def test_de_themas_van_elke_editie_worden_herkend(editie, sis, prognose):
    [bestand] = [x for x in _arbeidsmarktbestanden() if x["schema"]["editie"] == editie]
    df = pd.DataFrame({"thema": bestand["schema"]["themas"]})

    assert arbeidsmarkt.roa_sis(bestand["schema"]["themas"]) == sis
    assert arbeidsmarkt.roa_sis_thema(df) == f"Schoolverlatersinformatie ({sis})"
    assert arbeidsmarkt.roa_prognose_thema(df) == prognose


@pytest.fixture
def catalogus_2027(monkeypatch):
    """De catalogus met een editie 2027 als nieuwste; editie 2026 is dan niet meer de nieuwste."""
    from onderwijsbronnen import roa

    echt = roa.catalog()

    def catalog():
        records = json.loads(json.dumps(echt))
        record = next(r for r in records if r["_roa_id"] == "ais2030")
        for x in record["_resources"]:
            if x.get("schema"):
                x["schema"]["meest_recente_editie"] = False
        schema = {
            "bestandsnaam": "AIStot2030_Arbeidsmarktinformatie_editie2027.csv",
            "editie": "2027",
            "meest_recente_editie": True,
            "soort": "arbeidsmarkt",
            "themas": ["Schoolverlatersinformatie (SIS 2026)", "Risicoindicatoren en arbeidsmarktprognoses tot 2030"],
        }
        record["_resources"].append({"naam": "arbeidsmarkt_editie2027", "file_id": 999999, "schema": schema})
        return records

    monkeypatch.setattr(roa, "catalog", catalog)


def test_een_nieuwere_editie_in_de_catalogus_is_wat_dashboard_chat_en_snippet_laden(catalogus_2027, monkeypatch):
    from onderwijsbronnen import roa

    geladen: list = []
    rijen = pd.DataFrame(
        {
            "regionaam": ["Nederland"],
            "thema": ["Schoolverlatersinformatie (SIS 2026)"],
            "aggregatieniveau": [arbeidsmarkt._ROA_NIVEAU],
            "detailniveau": ["Mbo4"],
            "onderwerp": ["werkloosheid"],
            "perc": [4.0],
            "aantal": [None],
            "typering": [None],
            "versie": ["v20270901"],
        }
    )
    monkeypatch.setattr(roa, "load", lambda *a, **k: geladen.append(a) or rijen.copy())
    arbeidsmarkt._roa.cache_clear()
    try:
        assert arbeidsmarkt.roa_schoolverlaters(("Mbo4",)) == {"Mbo4": {"werkloosheid": {"perc": 4}}}
        assert geladen == [("ais2030", "arbeidsmarkt_editie2027")]
        assert arbeidsmarkt.roa_peilmoment() == "editie 2027, SIS 2026, versie v20270901"
    finally:
        arbeidsmarkt._roa.cache_clear()
    script = "\n".join(snippet._roa_laadregels({}))
    assert 'roa.load("ais2030", "arbeidsmarkt_editie2027")' in script


def test_een_pin_laadt_de_gepinde_editie_met_haar_reden(monkeypatch):
    monkeypatch.setattr(arbeidsmarkt, "ROA_PIN", "arbeidsmarkt")
    monkeypatch.setattr(arbeidsmarkt, "ROA_PIN_REDEN", "editie 2026 mist een thema")

    bestand = arbeidsmarkt.roa_bestand()

    assert (bestand.resource, bestand.editie, bestand.pin) == ("arbeidsmarkt", "2025", "editie 2026 mist een thema")


def test_de_snippet_laadt_het_bestand_van_de_app():
    script = "\n".join(snippet._roa_laadregels({"regio": "Groningen"}))

    assert f'roa.load("ais2030", "{arbeidsmarkt.roa_bestand().resource}")' in script
    assert 'roa.load("ais2030", "arbeidsmarkt")' not in script
    assert "editie 2026" in script


# ── Een editie zonder herkend thema is een fout, geen lege tabel ─────────────────────────────────────────────────────


def _zonder_sis() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "regionaam": ["Nederland"],
            "thema": ["Risicoindicatoren en arbeidsmarktprognoses tot 2030, actualisering"],
            "aggregatieniveau": [arbeidsmarkt._ROA_NIVEAU],
            "detailniveau": ["Mbo4"],
            "onderwerp": ["ITA toekomstige arbeidsmarktsituatie in 2030"],
            "perc": [None],
            "aantal": [None],
            "typering": ["redelijk"],
            "versie": ["v1"],
        }
    )


def test_een_bestand_zonder_sis_thema_geeft_een_fout(monkeypatch):
    monkeypatch.setattr(arbeidsmarkt, "_roa", _zonder_sis)

    with pytest.raises(arbeidsmarkt.RoaThemaOnbekend, match="schoolverlatersinformatie"):
        arbeidsmarkt.roa_schoolverlaters(("Mbo4",))
    # De prognose heeft haar thema wel.
    assert arbeidsmarkt.roa_prognose(("Mbo4",)) == {
        "Mbo4": {"ITA toekomstige arbeidsmarktsituatie in 2030": {"typering": "redelijk"}}
    }


def test_een_bestand_met_een_onbekend_sis_thema_geeft_een_fout(monkeypatch):
    df = _zonder_sis()
    df["thema"] = "Schoolverlatersinformatie 2025"  # niet zoals ROA het spelt: geen gok
    monkeypatch.setattr(arbeidsmarkt, "_roa", lambda: df.copy())

    with pytest.raises(arbeidsmarkt.RoaThemaOnbekend):
        arbeidsmarkt.roa_schoolverlaters(("Mbo4",))
    with pytest.raises(arbeidsmarkt.RoaThemaOnbekend, match="prognose"):
        arbeidsmarkt.roa_prognose(("Mbo4",))


def test_chat_en_dashboard_melden_de_fout_in_plaats_van_een_lege_tabel(monkeypatch):
    monkeypatch.setattr(arbeidsmarkt, "_roa", _zonder_sis)
    monkeypatch.setattr("tools.arbeidsmarkt.scope_blokkade", lambda *a: None)

    uit = get_roa_benchmark()

    with pytest.raises(json.JSONDecodeError):
        json.loads(uit)  # een foutmelding, geen resultaat met lege schoolverlaters
    assert "ROA" in uit
    gaten: list = []
    monkeypatch.setattr(dashboard, "_niet_beschikbaar", lambda e, *a, **k: gaten.append(type(e)))
    assert dashboard._roa_schoolverlaters("mbo") == {}
    assert gaten == [arbeidsmarkt.RoaThemaOnbekend]
