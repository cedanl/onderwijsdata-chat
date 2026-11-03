"""Dataset-gebonden glossary en bewijsvlag voor _meest_recent."""
import re

import riodata
from riodata import duo

STARTJAAR_DATASETS = ("p01hoinges", "p02ho1ejrs", "p03hoinschr")


def test_zonder_dataset_geen_studiejaardefinitie():
    """STUDIEJAAR komt alleen in p01-p03 voor (als startjaar); 'YYYY/YYYY' klopte nergens."""
    assert duo.column_definitions(["STUDIEJAAR", "ONBEKEND"]) == {}
    assert "STUDIEJAAR" not in duo.DUO_COLUMN_GLOSSARY


def test_studiejaar_p01_p02_p03_is_startjaar():
    for ds in STARTJAAR_DATASETS:
        tekst = duo.column_definitions(["STUDIEJAAR"], ds)["STUDIEJAAR"]
        assert "Startjaar" in tekst and "2023 = studiejaar 2023/2024" in tekst
        assert "YYYY/YYYY" not in tekst


def test_scope_lekt_niet_naar_andere_datasets():
    assert duo.column_definitions(["STUDIEJAAR"], "functiemix") == {}
    assert duo.column_definitions(["STUDIEJAAR"], "p04hogdipl") == {}
    assert "VT = voltijd" in duo.column_definitions(["OPLEIDINGSVORM"], "p01hoinges")["OPLEIDINGSVORM"]
    assert duo.column_definitions(["OPLEIDINGSVORM"], "functiemix") == {}


def test_opleidingsvorm_in_mbo_aanbod_zijn_geen_vt_dt_du_codes():
    """Volledige scan (2026-10-05): zes vormen, geen VT/DT/DU."""
    tekst = duo.column_definitions(["OPLEIDINGSVORM"], "mbo_opleidingsaanbod")["OPLEIDINGSVORM"]
    for w in ("KLASSIKAAL", "COACHING", "KLASSIKAAL_EN_ONLINE", "ONLINE", "LEZING", "ZELFSTUDIE"):
        assert w in tekst
    assert "VT = voltijd" not in tekst


def test_leerweg_volgt_gepubliceerde_codes_en_niet_voltijd_deeltijd_duaal():
    for ds in ("mbo-studenten-per-instelling", "mbo-studenten-per-sectorkamer-en-leerweg",
               "instromende-mbo-studenten", "gediplomeerde-mbo-studenten"):
        tekst = duo.column_definitions(["LEERWEG"], ds)["LEERWEG"]
        assert "BBL" in tekst and "BOLVT" in tekst and "afgeleid" in tekst
    # geen algemene LEERWEG-definitie meer: elders is de betekenis niet vastgesteld
    assert duo.column_definitions(["LEERWEG"]) == {}
    assert duo.column_definitions(["LEERWEG"], "04_voex-v1") == {}
    assert "LEERWEG" not in duo.DUO_COLUMN_GLOSSARY


def test_catalogus_kolomdefinities_gelijk_aan_scoped_glossary():
    """Catalogus en column_definitions() geven dezelfde definitie voor dezelfde dataset."""
    per_id = {r["_ckan_id"]: r for r in riodata.catalog("duo")}
    for ds in STARTJAAR_DATASETS:
        kd = per_id[ds]["_kolomdefinities"]
        assert kd["STUDIEJAAR"] == duo.column_definitions(["STUDIEJAAR"], ds)["STUDIEJAAR"]


def test_meest_recent_bewijs_klopt_met_de_naam():
    n = 0
    for r in riodata.catalog("duo"):
        if "_meest_recent" not in r:
            assert "_meest_recent_bewijs" not in r
            continue
        n += 1
        heeft_jaar = bool(re.search(r"\b20\d{2}\b", r["_meest_recent"]))
        assert r["_meest_recent_bewijs"] == ("jaartal_in_naam" if heeft_jaar else "geen")
    assert n == 30


def test_controlebestand_is_niet_autoritatief():
    r = next(r for r in riodata.catalog("duo") if r.get("_meest_recent") == "controlebestand")
    assert r["_meest_recent_bewijs"] == "geen"


def test_opleidingsvorm_ho_volgt_de_notes():
    """De notes van p01-p04 definiëren de codes letterlijk; de definitie mag niet zeggen dat dat niet zo is."""
    for ds in ("p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"):
        tekst = duo.column_definitions(["OPLEIDINGSVORM"], ds)["OPLEIDINGSVORM"]
        assert all(c in tekst for c in ("VT = voltijd", "DT = deeltijd", "DU = duaal"))
        assert "DUO-datasetbeschrijving" in tekst and "niet in de dataset" not in tekst
