"""Profiel van een geladen tabel zonder model (#59, #61): schema, statistiek en korrel, uit de cache."""

import json
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from tools import profiel, store
from tools.profiel import (
    CATEGORIE,
    DATUM,
    GEOCODE,
    GETAL,
    IDENTIFICATIE,
    JAAR,
    SCHOOLJAAR,
    TEKST,
    dataset_profiel,
    profileer,
)

_DUO = pd.DataFrame(
    {
        "STUDIEJAAR": [2021, 2021, 2022, 2022],
        "STUDIEJAAR_LABEL": ["2021/2022", "2021/2022", "2022/2023", "2022/2023"],
        "INSTELLINGSCODE_ACTUEEL": ["21PK", "22OJ", "21PK", "22OJ"],
        "INSTELLINGSNAAM_ACTUEEL": ["Fontys", "Avans", "Fontys", "Avans"],
        "GEMEENTECODE": ["GM0855", "GM0758", "GM0855", "GM0758"],
        "GESLACHT": ["man", "vrouw", "man", None],
        "AANTAL": [100, 250.0, 120, 300],
        "PEILDATUM": pd.to_datetime(["2021-10-01", "2021-10-01", "2022-10-01", "2022-10-01"]),
    }
)


def _put(key: str, df: pd.DataFrame, volledig: bool = True) -> None:
    store.put(key, df, store.KeyMeta(bron="test", dataset=key, volledig=volledig))


# --- per kolom -----------------------------------------------------------------------------------


def test_per_kolom_type_leeg_uniek_en_waar_hij_op_lijkt():
    kolommen = profileer(_DUO).kolommen
    assert {naam: k.lijkt_op for naam, k in kolommen.items()} == {
        "STUDIEJAAR": JAAR,
        "STUDIEJAAR_LABEL": SCHOOLJAAR,
        "INSTELLINGSCODE_ACTUEEL": IDENTIFICATIE,
        "INSTELLINGSNAAM_ACTUEEL": CATEGORIE,
        "GEMEENTECODE": GEOCODE,
        "GESLACHT": CATEGORIE,
        "AANTAL": GETAL,
        "PEILDATUM": DATUM,
    }
    geslacht = kolommen["GESLACHT"]
    assert (geslacht.leeg, geslacht.leeg_pct, geslacht.uniek, geslacht.uniek_pct) == (1, 25.0, 2, 66.7)
    assert geslacht.top == (("man", 2), ("vrouw", 1))
    assert geslacht.min is None and geslacht.kwartielen is None


def test_een_meetkolom_heeft_bereik_en_kwartielen_een_jaar_alleen_bereik():
    kolommen = profileer(_DUO).kolommen
    aantal = kolommen["AANTAL"]
    assert (aantal.min, aantal.max, aantal.kwartielen, aantal.top) == (100, 300, (115, 185, 262.5), ())
    jaar = kolommen["STUDIEJAAR"]
    assert (jaar.min, jaar.max, jaar.kwartielen) == (2021, 2022, None)
    assert jaar.top == (("2021", 2), ("2022", 2))
    assert (kolommen["PEILDATUM"].min, kolommen["PEILDATUM"].max) == ("2021-10-01", "2022-10-01")


def test_cbs_periodecode_en_schooljaar_met_apostrof_zijn_schooljaren():
    df = pd.DataFrame({"Perioden": ["2024SJ00", "2025SJ00"], "Jaar": ["2015/'16", "2016/'17"], "Tekst": ["a/b", "c"]})
    kolommen = profileer(df).kolommen
    assert (kolommen["Perioden"].lijkt_op, kolommen["Jaar"].lijkt_op, kolommen["Tekst"].lijkt_op) == (
        SCHOOLJAAR,
        SCHOOLJAAR,
        CATEGORIE,
    )


def test_veel_verschillende_namen_zijn_tekst_een_getal_met_jaar_in_de_naam_buiten_bereik_is_geen_jaar():
    df = pd.DataFrame({"OMSCHRIJVING": [f"tekst {i}" for i in range(400)], "AANTAL_PER_JAAR": range(400)})
    kolommen = profileer(df).kolommen
    assert kolommen["OMSCHRIJVING"].lijkt_op == TEKST
    assert kolommen["AANTAL_PER_JAAR"].lijkt_op == GETAL


# --- de tabel: dubbele rijen en korrel ------------------------------------------------------------


def test_de_korrel_is_de_kleinste_combinatie_die_elke_rij_apart_aanwijst():
    """Alle combinaties van twee kolommen die werken, de code vóór de naam; geen enkele kolom alleen."""
    p = profileer(_DUO)
    assert p.kandidaat_sleutels[0] == ("INSTELLINGSCODE_ACTUEEL", "STUDIEJAAR")
    assert ("INSTELLINGSCODE_ACTUEEL", "STUDIEJAAR_LABEL") in p.kandidaat_sleutels
    assert (
        "INSTELLINGSCODE_ACTUEEL",
        "GEMEENTECODE",
    ) not in p.kandidaat_sleutels  # dezelfde instelling, zelfde gemeente
    assert {len(s) for s in p.kandidaat_sleutels} == {2} and len(p.kandidaat_sleutels) <= profiel.MAX_SLEUTELS
    assert p.dubbele_rijen_pct == 0.0


def test_een_enkele_sleutelkolom_wint_en_een_meetkolom_doet_niet_mee():
    df = pd.DataFrame({"CODE": ["a", "b", "c"], "VORM": ["VT", "VT", "DT"], "AANTAL": [1, 2, 3]})
    assert profileer(df).kandidaat_sleutels == (("CODE",),)


def test_drie_kolommen_als_twee_niet_genoeg_zijn_en_niets_als_het_niet_lukt():
    rijen = [(c, j, v) for c in ("a", "b") for j in (2021, 2022) for v in ("VT", "DT")]
    df = pd.DataFrame(rijen, columns=["CODE", "JAAR", "VORM"])
    assert profileer(df).kandidaat_sleutels == (("CODE", "JAAR", "VORM"),)
    dubbel = pd.concat([df, df.head(1)])
    p = profileer(dubbel)
    assert p.kandidaat_sleutels == ()
    assert p.dubbele_rijen_pct == 11.1


def test_lege_tabel_en_een_rij_breken_niets():
    leeg = profileer(pd.DataFrame({"A": pd.Series([], dtype=float), "B": pd.Series([], dtype=object)}))
    assert (leeg.rijen, leeg.kandidaat_sleutels, leeg.dubbele_rijen_pct) == (0, (), 0.0)
    assert leeg.kolommen["A"].als_dict() == {
        "type": "float64",
        "lijkt_op": GETAL,
        "leeg": 0,
        "leeg_pct": 0.0,
        "uniek": 0,
        "uniek_pct": 0.0,
    }
    een = profileer(pd.DataFrame({"CODE": ["a"], "N": [1]}))
    assert (een.rijen, een.kandidaat_sleutels) == (1, ())


def test_een_cel_met_een_lijst_of_dict_telt_mee_als_tekst():
    df = pd.DataFrame({"ID": [1, 2, 2], "ADRES": [{"stad": "Utrecht"}, ["a", "b"], ["a", "b"]]})
    p = profileer(df)
    assert p.kolommen["ADRES"].uniek == 2
    assert p.dubbele_rijen_pct == 33.3


def test_profiel_van_50k_rijen_binnen_een_seconde():
    rng = np.random.default_rng(59)
    n = 50_000
    df = pd.DataFrame(
        {
            "INSTELLINGSCODE": rng.choice([f"{i:02d}XX" for i in range(60)], n),
            "STUDIEJAAR": rng.choice([2021, 2022, 2023, 2024, 2025], n),
            "OPLEIDINGSCODE": rng.choice([str(30000 + i) for i in range(400)], n),
            "GESLACHT": rng.choice(["man", "vrouw"], n),
            "VORM": rng.choice(["VT", "DT", "DU"], n),
            "AANTAL": rng.integers(0, 5000, n),
        }
    )
    start = time.perf_counter()
    p = profileer(df)
    assert time.perf_counter() - start < 1.0
    assert p.rijen == n and p.kolommen["AANTAL"].lijkt_op == GETAL


# --- cache en tool --------------------------------------------------------------------------------


def test_het_profiel_wordt_een_keer_berekend_en_opnieuw_na_nieuwe_data():
    _put("test:p", _DUO)
    with patch("tools.profiel.profileer", wraps=profileer) as berekend:
        assert profiel.profiel_van("test:p") is profiel.profiel_van("test:p")
        assert berekend.call_count == 1
        _put("test:p", _DUO.head(2))
        opnieuw = profiel.profiel_van("test:p")
        assert opnieuw is not None and opnieuw.rijen == 2
        assert berekend.call_count == 2
    assert profiel.profiel_van("test:weg") is None


def test_dataset_profiel_geeft_rijen_korrel_en_kolommen():
    _put("test:p", _DUO)
    uit = json.loads(dataset_profiel("test:p"))
    assert uit["data_key"] == "test:p" and uit["totaal_rijen"] == 4
    assert uit["korrel"] == "elke rij is uniek op INSTELLINGSCODE_ACTUEEL + STUDIEJAAR"
    assert uit["kandidaat_sleutels"][0] == ["INSTELLINGSCODE_ACTUEEL", "STUDIEJAAR"]
    assert uit["kolommen"]["AANTAL"] == {
        "type": "float64",
        "lijkt_op": "getal",
        "leeg": 0,
        "leeg_pct": 0.0,
        "uniek": 4,
        "uniek_pct": 100.0,
        "min": 100,
        "max": 300,
        "kwartielen": [115, 185, 262.5],
    }
    assert uit["kolommen"]["GESLACHT"]["top"] == [{"waarde": "man", "aantal": 2}, {"waarde": "vrouw", "aantal": 1}]
    assert "waarschuwing" not in uit


def test_dataset_profiel_op_een_afgekapte_pagina_waarschuwt_en_op_een_onbekende_key_meldt():
    _put("test:half", _DUO, volledig=False)
    uit = json.loads(dataset_profiel("test:half"))
    assert uit["opgehaalde_rijen"] == 4 and uit["volledig"] is False
    assert "pagina" in uit["waarschuwing"]
    assert "test:weg" in dataset_profiel("test:weg")


def test_korrel_in_woorden_als_er_geen_sleutel_is():
    df = pd.DataFrame({"CODE": ["a", "a"], "N": [1, 1]})
    _put("test:dubbel", df)
    assert "ontdubbelen" in json.loads(dataset_profiel("test:dubbel"))["korrel"]
    _put("test:een", df.head(1))
    assert "minder dan twee rijen" in json.loads(dataset_profiel("test:een"))["korrel"]
