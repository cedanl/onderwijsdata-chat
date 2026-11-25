"""Een lege CBS-cel ('.', in OData null) is een onderdrukte cel, net als DUO -1 (#862).

Bevroren payload: 85701NED, entreeopleiding 2023/'24, vier gemeenten; GM0738 en GM0366 zijn leeg.
Een selectie met zo'n cel krijgt de ondergrens in de tool-output, het Telling-blok en de CSV-kop;
een volledig gevulde selectie niet.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from core.sentinels import CBS_BETEKENIS, lege_cellen, lege_cellen_onderdrukt
from tools import cbs, duo, store
from tools.cbs import get_cbs_data
from tools.exportnoten import herkomstregels
from tools.query import query_data

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "cbs" / "85701NED_entree_2023.json").read_text())
_KOLOM = "LeerlingenStudenten_1"


def _geen_dimensierijen(*_args, **_kwargs):
    raise RuntimeError("geen netwerk in deze test")


@pytest.fixture
def key() -> str:
    with (
        patch("tools.cbs.data", return_value=_PAYLOAD["rows"]),
        patch("tools.cbs.definitions", return_value=_PAYLOAD["definitions"]),
        patch("tools.cbs.get", side_effect=_geen_dimensierijen),
    ):
        return json.loads(get_cbs_data("85701NED"))["data_key"]


def _selectie(key: str, gemeenten: list[str]) -> dict:
    return json.loads(query_data(key, filters={"Regiokenmerken": gemeenten}))


def test_de_geladen_tabel_legt_haar_lege_cellen_vast(key):
    assert duo.count_cells(duo.sentinel_cells(key)) == {_KOLOM: 6}


def test_een_selectie_met_lege_cellen_meldt_ze_per_jaar(key):
    result = _selectie(key, ["GM1680", "GM0738"])

    noten = " ".join(result["databewerking"])
    assert "Onderdrukte cellen ('.')" in noten and "2023/24: 3" in noten
    assert "-1" not in noten


def test_een_deels_lege_selectie_is_een_ondergrens_in_telling_en_csv(key):
    afgeleid = _selectie(key, ["GM1680", "GM0738"])["data_key"]

    blok = telling_blok([json.dumps({"data_key": afgeleid})])
    assert "Ondergrens" in blok and "85701NED" in blok and "lege cellen ('.')" in blok and CBS_BETEKENIS in blok
    assert "cellen met -1" not in blok
    csv = " ".join(herkomstregels(afgeleid))
    assert f"3 lege CBS-cellen ('.') in '{_KOLOM}'" in csv and "ondergrens" in csv


def test_een_volledig_gevulde_selectie_is_geen_ondergrens(key):
    result = _selectie(key, ["GM1680", "GM0358"])

    assert "databewerking" not in result
    assert "Ondergrens" not in telling_blok([json.dumps({"data_key": result["data_key"]})])
    assert not any("ondergrens" in regel for regel in herkomstregels(result["data_key"]))


def test_een_groepstotaal_over_cbs_krijgt_de_cbs_woorden():
    # Rechtstreeks in de store: de dimensiecontrole laat bij een echte CBS-tabel geen som over een open
    # dimensie toe, dus hier heeft één groep twee rijen zonder tweede dimensie.
    store.put(
        "cbs:TEST",
        pd.DataFrame({"Groep": ["a", "a", "b"], "Aantal": [10.0, None, 30.0]}),
        store.KeyMeta(bron="cbs", dataset="TEST"),
    )
    cbs.register_dimensions("TEST", ["Groep"])
    result = json.loads(query_data("cbs:TEST", group_by=["Groep"], aggregate={"Aantal": "sum"}))

    rijen = {r["Groep"]: r for r in result["rijen"]}
    assert rijen["a"]["Aantal"] == 10 and rijen["a"]["Aantal (onderdrukte cellen)"] == 1
    assert "Aantal (onderdrukte cellen)" not in rijen["b"]
    noten = " ".join(result["databewerking"])
    assert "1 lege CBS-cellen ('.') in 'Aantal' uitgesloten" in noten and "ondergrens" in noten
    assert "onderdrukte cellen ('.')" in noten


def test_lege_cellen_slaat_tekst_en_kolommen_met_een_teken_over():
    df = pd.DataFrame({"Code": ["a", None], "Mutatie_1": [None, 3.0], "Aantal_2": [1.0, None]})

    assert duo.count_cells(lege_cellen(df)) == {"Aantal_2": 1}


def test_een_afgeleide_cbs_key_erft_geen_lege_groepstotalen_als_broncellen():
    store.put("cbs:TEST", pd.DataFrame({"Aantal": [1.0]}), store.KeyMeta(bron="cbs", dataset="TEST"))
    store.derive("cbs:TEST", "cbs:TEST:som", pd.DataFrame({"Aantal": [None]}))

    assert duo.sentinel_cells("cbs:TEST:som") is None


# Een combinatie die niet bestaat (#1213): 85424NED heeft geen hbo-associate degree binnen het wo, dus die cel is in elk
# jaar leeg. Dat is geen onderdrukt cijfer; een som erover is volledig en geen ondergrens.
_PERIODEN = ["2022SJ00", "2023SJ00"]


def _laad(dataset: str, aantallen: dict[tuple[str, str], list[float | None]], dims_eerst: bool = True) -> str:
    """Een geladen CBS-tabel met de dimensies Onderwijssoort x Opleidingsfase over twee jaren; per combinatie de
    aantallen per jaar."""
    rijen = [
        {"Onderwijssoort": soort, "Opleidingsfase": fase, "Perioden": jaar, "Aantal": aantal}
        for (soort, fase), per_jaar in aantallen.items()
        for jaar, aantal in zip(_PERIODEN, per_jaar, strict=True)
    ]
    key = f"cbs:{dataset}"
    dims = ["Onderwijssoort", "Opleidingsfase", "Perioden"]
    if dims_eerst:
        cbs.register_dimensions(dataset, dims)
    store.put(key, pd.DataFrame(rijen), store.KeyMeta(bron="cbs", dataset=dataset, periodekolom="Perioden"))
    if not dims_eerst:
        cbs.register_dimensions(dataset, dims)
    return key


_WO_AD_BESTAAT_NIET = {
    ("WO", "AD"): [None, None],
    ("WO", "BA"): [100.0, 110.0],
    ("HBO", "AD"): [20.0, 25.0],
    ("HBO", "BA"): [200.0, 210.0],
}


def _ondergrens_overal(key: str, result: dict) -> tuple[bool, bool, bool]:
    """(Telling-blok, databewerking, CSV-kop): meldt elk de lege cellen als onderdrukt? De databewerking van een
    selectie telt ze per jaar, die van een som noemt de ondergrens."""
    blok = telling_blok([json.dumps({"data_key": key})])
    noten = " ".join(result.get("databewerking", [])).lower()
    return (
        "Ondergrens" in blok,
        "onderdrukte cellen ('.')" in noten or "ondergrens" in noten,
        any("ondergrens" in r for r in herkomstregels(key)),
    )


@pytest.mark.parametrize("dims_eerst", [True, False])
def test_een_combinatie_die_in_elk_jaar_leeg_is_is_geen_ondergrens(dims_eerst):
    key = _laad("TNVT", _WO_AD_BESTAAT_NIET, dims_eerst)

    assert duo.count_cells(duo.sentinel_cells(key)) == {}
    result = json.loads(query_data(key, filters={"Onderwijssoort": ["WO"]}))
    assert _ondergrens_overal(result["data_key"], result) == (False, False, False)
    # Geen noot: de lege cel is een combinatie zonder waarde, geen onderdrukt cijfer (#1213).
    assert "databewerking" not in result
    assert "onderdrukt" not in json.dumps(result, ensure_ascii=False).lower()


def test_een_som_over_een_combinatie_die_niet_bestaat_is_volledig():
    key = _laad("TNVT", _WO_AD_BESTAAT_NIET)

    result = json.loads(
        query_data(
            key,
            filters={"Onderwijssoort": ["WO"]},
            group_by=["Opleidingsfase", "Perioden"],
            aggregate={"Aantal": "sum"},
        )
    )
    assert _ondergrens_overal(result["data_key"], result) == (False, False, False)
    assert not any("onderdrukte cellen" in kolom for rij in result["rijen"] for kolom in rij)


def test_een_cel_die_alleen_in_sommige_jaren_leeg_is_blijft_een_ondergrens():
    key = _laad("TDEELS", {**_WO_AD_BESTAAT_NIET, ("HBO", "AD"): [20.0, None]})

    result = json.loads(query_data(key, filters={"Onderwijssoort": ["HBO"]}))
    assert _ondergrens_overal(result["data_key"], result) == (True, True, True)
    assert CBS_BETEKENIS in telling_blok([json.dumps({"data_key": result["data_key"]})])


def test_beide_soorten_lege_cellen_tellen_alleen_de_onderdrukte():
    key = _laad("TBEIDE", {**_WO_AD_BESTAAT_NIET, ("WO", "BA"): [100.0, None]})

    assert duo.count_cells(duo.sentinel_cells(key)) == {"Aantal": 1}
    selectie = json.loads(query_data(key, filters={"Onderwijssoort": ["WO"]}))
    assert _ondergrens_overal(selectie["data_key"], selectie) == (True, True, True)
    noten = " ".join(selectie["databewerking"])
    assert "per jaar (Perioden): 2023/24: 1." in noten and "2022/23" not in noten
    assert "1 lege CBS-cellen ('.') in 'Aantal'" in " ".join(herkomstregels(selectie["data_key"]))

    som = json.loads(
        query_data(
            key,
            filters={"Onderwijssoort": ["WO"]},
            group_by=["Opleidingsfase", "Perioden"],
            aggregate={"Aantal": "sum"},
        )
    )
    assert "1 lege CBS-cellen ('.') in 'Aantal' uitgesloten" in " ".join(som["databewerking"])
    rijen = {(r["Opleidingsfase"], r["Perioden"]): r for r in som["rijen"]}
    assert rijen[("BA", "2023SJ00")]["Aantal (onderdrukte cellen)"] == 1
    assert "Aantal (onderdrukte cellen)" not in rijen[("AD", "2023SJ00")]


def test_get_cbs_data_kent_de_dimensies_al_bij_het_wegen_van_de_lege_cellen():
    # Geconstrueerd: de payload van 85701NED met een tweede jaar erbij, waarin GM0738 wel cijfers heeft en GM0366 weer
    # leeg is. GM0738 is dan deels leeg (onderdrukt), GM0366 in elk jaar (een combinatie zonder cijfer).
    vorig_jaar = [
        {**r, "ID": r["ID"] + 1, "Perioden": "2022SJ00", **({_KOLOM: 5} if r["Regiokenmerken"] == "GM0738" else {})}
        for r in _PAYLOAD["rows"]
    ]
    with (
        patch("tools.cbs.data", return_value=[*vorig_jaar, *_PAYLOAD["rows"]]),
        patch("tools.cbs.definitions", return_value=_PAYLOAD["definitions"]),
        patch("tools.cbs.get", side_effect=_geen_dimensierijen),
    ):
        key = json.loads(get_cbs_data("85701NED"))["data_key"]

    assert duo.count_cells(duo.sentinel_cells(key)) == {_KOLOM: 3}
    assert "Ondergrens" not in telling_blok([json.dumps({"data_key": _selectie(key, ["GM0366"])["data_key"]})])
    assert "Ondergrens" in telling_blok([json.dumps({"data_key": _selectie(key, ["GM0738"])["data_key"]})])


def test_een_lege_combinatie_in_maar_een_geladen_jaar_blijft_onderdrukt():
    # Eén jaar zegt niet of de combinatie bestaat: dan de voorzichtige ondergrens, zoals bij GM0738 hierboven.
    df = pd.DataFrame({"Soort": ["WO", "HBO"], "Perioden": ["2023SJ00", "2023SJ00"], "Aantal": [None, 5.0]})

    assert duo.count_cells(lege_cellen_onderdrukt(df, ["Soort", "Perioden"], "Perioden")) == {"Aantal": 1}


def test_zonder_dimensies_of_periodekolom_is_elke_lege_cel_onderdrukt():
    df = pd.DataFrame({"Soort": ["WO", "WO"], "Perioden": ["2022SJ00", "2023SJ00"], "Aantal": [None, None]})
    df = df.astype({"Aantal": float})

    assert duo.count_cells(lege_cellen_onderdrukt(df, [], "Perioden")) == {"Aantal": 2}
    assert duo.count_cells(lege_cellen_onderdrukt(df, ["Soort"], None)) == {"Aantal": 2}
    assert duo.count_cells(lege_cellen_onderdrukt(df, ["Soort", "Perioden"], "Perioden")) == {}
