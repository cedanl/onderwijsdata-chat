"""Geslacht per opleiding uit code, alleen waar het exact is (#742).

"Wat is de man-vrouwverhouding bij de instroom van Luchtvaart van Inholland?" gaf de ene keer een verdeling en de
andere keer "niet beschikbaar": of het model het geslachtsbestand aan de opleiding koppelde, besliste het per run.
DUO heeft geslacht niet per opleiding, maar Luchtvaarttechnologie is de enige opleiding in haar cel van het
geslachtsbestand en de totalen zijn gelijk: de verdeling is exact. Nu beslist de code, met per jaar de reden als
het niet kan.

De bestanden zijn fixtures in de vorm van DUO p02ho1ejrs (0: hbo met geslacht, 2: hbo niveau opleiding); de
catalogus is echt, zodat de bestandskeuze op de gepinde titels staat.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.uitgangspunt import uitgangspunt
from tools import herlaad, snippet, store
from tools.geslacht_opleiding import Opleiding, kies_opleiding, verdeling
from tools.maten import get_maat, plan
from tools.schemas import TOOL_GET_MAAT

W = "AANTAL_EERSTEJAARS_INGESCHREVENEN"
_CEL = ["STUDIEJAAR", "GEMEENTENAAM", "TYPE_HOGER_ONDERWIJS", "INSTELLINGSCODE_ACTUEEL", "ONDERDEEL", "SUBONDERDEEL"]
_LUCHT = ("34278", "B Luchtvaarttechnologie")
_WTB = ("34397", "B Werktuigbouwkunde")
_RECHTEN = ("39205", "B HBO - Rechten")
_ACC = ("34406", "B Accountancy")
_LEEG = None  # een lege SUBONDERDEEL, zoals DUO hem soms geeft


def _niveau_rij(jaar, gemeente, onderdeel, opl, aantal, instelling="27PZ"):
    return (jaar, gemeente, "bachelor", instelling, onderdeel, _LEEG, *opl, aantal)


def _geslacht_rij(jaar, gemeente, onderdeel, geslacht, aantal, instelling="27PZ"):
    return (jaar, gemeente, "bachelor", instelling, onderdeel, _LEEG, geslacht, aantal)


# 2021: Luchtvaart alleen in Delft/TECHNIEK, totalen gelijk: exact.
# 2022: Werktuigbouwkunde in dezelfde cel. 2023: VROUW onderdrukt. 2024: totalen verschillen. 2025: geen opleiding.
# Een andere instelling in Delft/TECHNIEK telt niet als andere opleiding. Rechten deelt elk jaar haar cel.
_NIVEAU = pd.DataFrame(
    [
        _niveau_rij(2021, "Delft", "TECHNIEK", _LUCHT, 174),
        _niveau_rij(2021, "Delft", "TECHNIEK", _WTB, 12, instelling="99ZZ"),
        _niveau_rij(2022, "Delft", "TECHNIEK", _LUCHT, 170),
        _niveau_rij(2022, "Delft", "TECHNIEK", _WTB, 40),
        _niveau_rij(2023, "Delft", "TECHNIEK", _LUCHT, 210),
        _niveau_rij(2024, "Delft", "TECHNIEK", _LUCHT, 157),
        _niveau_rij(2025, "Delft", "TECHNIEK", _WTB, 45),
        *(
            _niveau_rij(j, "Den Haag", "ECONOMIE", opl, n)
            for j in (2021, 2022)
            for opl, n in ((_RECHTEN, 90), (_ACC, 60))
        ),
    ],
    columns=[*_CEL, "OPLEIDINGSCODE_ACTUEEL", "OPLEIDINGSNAAM_ACTUEEL", W],
).assign(INSTELLINGSNAAM_ACTUEEL=lambda df: df["INSTELLINGSCODE_ACTUEEL"].map({"27PZ": "Hogeschool Inholland"}))
_GESLACHT = pd.DataFrame(
    [
        _geslacht_rij(2021, "Delft", "TECHNIEK", "MAN", 152),
        _geslacht_rij(2021, "Delft", "TECHNIEK", "VROUW", 22),
        _geslacht_rij(2021, "Delft", "TECHNIEK", "MAN", 12, instelling="99ZZ"),
        _geslacht_rij(2022, "Delft", "TECHNIEK", "MAN", 180),
        _geslacht_rij(2022, "Delft", "TECHNIEK", "VROUW", 30),
        _geslacht_rij(2023, "Delft", "TECHNIEK", "MAN", 176),
        _geslacht_rij(2023, "Delft", "TECHNIEK", "VROUW", -1),
        _geslacht_rij(2024, "Delft", "TECHNIEK", "MAN", 121),
        _geslacht_rij(2024, "Delft", "TECHNIEK", "VROUW", 30),
        _geslacht_rij(2025, "Delft", "TECHNIEK", "MAN", 45),
        *(
            _geslacht_rij(j, "Den Haag", "ECONOMIE", g, n)
            for j in (2021, 2022)
            for g, n in (("MAN", 70), ("VROUW", 80))
        ),
    ],
    columns=[*_CEL, "GESLACHT", W],
).assign(INSTELLINGSNAAM_ACTUEEL=lambda df: df["INSTELLINGSCODE_ACTUEEL"].map({"27PZ": "Hogeschool Inholland"}))
_BESTANDEN = {("p02ho1ejrs", 2): _NIVEAU, ("p02ho1ejrs", 0): _GESLACHT}
_REGISTER = {"hogeschool inholland": {"naam": "Hogeschool Inholland", "sector": "hbo", "instellingscode": "27PZ"}}


@pytest.fixture(autouse=True)
def _bronnen():
    def laad(dataset_id, resource):
        return _BESTANDEN[(dataset_id, resource)].copy()

    with (
        patch(
            "tools.maten.instellingen.instellingsprofiel", side_effect=lambda naam: _REGISTER.get(naam.strip().lower())
        ),
        patch("tools.duo._duo.load", side_effect=laad),
        patch("riodata.duo.load", side_effect=laad),
    ):
        yield


def _van(df: pd.DataFrame, instelling: str = "27PZ") -> pd.DataFrame:
    df = df[df["INSTELLINGSCODE_ACTUEEL"] == instelling]
    return df.assign(**{W: df[W].where(df[W] >= 0)})  # zoals de store: -1 gemaskeerd


def _maat(**args) -> dict:
    return json.loads(get_maat("eerstejaars_ho", "Hogeschool Inholland", **args))


# --- de regel ---------------------------------------------------------------------------------------------------


def test_de_enige_opleiding_in_haar_cel_met_gelijke_totalen_krijgt_de_verdeling_van_de_cel():
    v = verdeling(_van(_NIVEAU), _van(_GESLACHT), Opleiding(*_LUCHT), W, jaren=(2021,))

    assert v.rijen[["STUDIEJAAR", "GESLACHT", W, "AANDEEL_PROCENT"]].values.tolist() == [
        [2021, "MAN", 152, 87.4],
        [2021, "VROUW", 22, 12.6],
    ]
    assert v.niet_af_te_leiden == {}


@pytest.mark.parametrize(
    ("jaar", "reden"),
    [
        (2022, "samen met andere opleidingen in dezelfde vestiging en hetzelfde onderdeel (B Werktuigbouwkunde)"),
        (2023, "onderdrukte kleine aantallen (-1)"),
        (2024, "de totalen verschillen: 157 in het opleidingsbestand, 151 in het geslachtsbestand"),
        (2025, "de opleiding staat dit jaar niet in het bestand"),
        (2019, "het bestand heeft dit studiejaar niet"),
    ],
)
def test_anders_geen_getal_maar_de_reden(jaar, reden):
    v = verdeling(_van(_NIVEAU), _van(_GESLACHT), Opleiding(*_LUCHT), W, jaren=(jaar,))

    assert v.rijen.empty
    assert reden in v.niet_af_te_leiden[jaar]


def test_een_onderdrukte_cel_is_niet_uit_het_totaal_terug_te_rekenen():
    """2023: MAN 176 en een totaal van 210 zouden VROUW = 34 geven; dat is precies wat DUO onderdrukte."""
    v = verdeling(_van(_NIVEAU), _van(_GESLACHT), Opleiding(*_LUCHT), W, jaren=(2023,))
    assert v.rijen.empty and 34 not in v.rijen.values


def test_een_cel_in_twee_vestigingen_is_alleen_exact_als_beide_het_zijn():
    tweede = _NIVEAU[_NIVEAU["STUDIEJAAR"] == 2021].assign(GEMEENTENAAM="Haarlem")
    niveau = pd.concat([_NIVEAU, tweede, tweede.assign(**{"OPLEIDINGSCODE_ACTUEEL": _WTB[0]})])
    geslacht = pd.concat([_GESLACHT, _GESLACHT[_GESLACHT["STUDIEJAAR"] == 2021].assign(GEMEENTENAAM="Haarlem")])

    v = verdeling(_van(niveau), _van(geslacht), Opleiding(*_LUCHT), W, jaren=(2021,))

    assert v.rijen.empty and "andere opleidingen" in v.niet_af_te_leiden[2021]


@pytest.mark.parametrize(
    ("gevraagd", "verwacht"),
    [
        ("34278", Opleiding(*_LUCHT)),
        ("b luchtvaarttechnologie", Opleiding(*_LUCHT)),
        ("Luchtvaart", Opleiding(*_LUCHT)),
        ("  luchtvaart  ", Opleiding(*_LUCHT)),
    ],
)
def test_de_opleiding_op_code_naam_of_deel_van_de_naam(gevraagd, verwacht):
    assert kies_opleiding(_van(_NIVEAU), gevraagd) == verwacht


def test_meer_passende_opleidingen_is_een_keuze_met_de_codes_geen_gok():
    uit = kies_opleiding(_van(_NIVEAU), "B ")
    assert isinstance(uit, str) and "B Luchtvaarttechnologie (34278)" in uit and "CROHO-code" in uit


def test_een_onbekende_opleiding_noemt_wat_er_wel_is():
    uit = kies_opleiding(_van(_NIVEAU), "Luchtvaarttechniek")
    assert isinstance(uit, str) and "Geen opleiding 'Luchtvaarttechniek'" in uit and "B Luchtvaarttechnologie" in uit


# --- get_maat ---------------------------------------------------------------------------------------------------


def test_get_maat_geeft_de_exacte_jaren_met_de_afleiding_en_de_rest_met_de_reden():
    uit = _maat(opleiding_naar_geslacht="Luchtvaart")

    assert [(r["STUDIEJAAR"], r["GESLACHT"], r[W]) for r in uit["rijen"]] == [(2021, "MAN", 152), (2021, "VROUW", 22)]
    assert uit["opleiding"] == {"code": "34278", "naam": "B Luchtvaarttechnologie"}
    assert "geen schatting" in uit["afleiding"]
    assert [n["schooljaar"] for n in uit["niet_af_te_leiden"]] == ["2022/23", "2023/24", "2024/25", "2025/26"]
    assert uit["recept"]["bestanden"] == {"niveau opleiding": 2, "geslacht": 0}


def test_zonder_enig_exact_jaar_een_vaste_melding_zonder_verdeling():
    uit = get_maat("eerstejaars_ho", "Hogeschool Inholland", opleiding_naar_geslacht="Rechten")

    assert "data_key" not in uit
    assert uit.startswith("Geslacht staat in DUO (p02ho1ejrs) niet per opleiding")
    assert "2021/22, 2022/23: het geslachtsbestand telt de opleiding samen met andere opleidingen" in uit
    assert "B Accountancy" in uit and "schat haar niet" in uit


@pytest.mark.parametrize(
    ("args", "tekst"),
    [
        ({"vorm": "voltijd"}, "kent geen opleidingsvorm"),
        ({"maat": "deelnemers_ho_landelijk", "sector": "hbo", "instelling": None}, "kan alleen bij"),
    ],
)
def test_een_vorm_of_een_landelijke_maat_is_een_melding(args, tekst):
    volledig = {"maat": "eerstejaars_ho", "instelling": "Hogeschool Inholland", "opleiding_naar_geslacht": "Luchtvaart"}
    uitkomst = plan(**{**volledig, **args})
    assert isinstance(uitkomst, str) and tekst in uitkomst


def test_dezelfde_vraag_geeft_dezelfde_uitkomst():
    """De kern van #742: wel of geen verdeling is geen toeval meer."""
    eerste, tweede = _maat(opleiding_naar_geslacht="Luchtvaart"), _maat(opleiding_naar_geslacht="Luchtvaart")
    assert eerste == tweede


def test_de_key_komt_na_een_herstart_terug_door_het_recept():
    args = {"maat": "eerstejaars_ho", "instelling": "Hogeschool Inholland", "opleiding_naar_geslacht": "Luchtvaart"}
    key = json.loads(get_maat(**args))["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_MAAT, "arguments": args})
    assert recept is not None and recept["tool"] == TOOL_GET_MAAT
    rijen = store.get(key).copy()
    store.clear()

    assert herlaad.herlaad(key, recept).gelukt
    pd.testing.assert_frame_equal(store.get(key), rijen)


def test_de_snippet_rekent_hetzelfde_uit():
    args = {"maat": "eerstejaars_ho", "instelling": "Hogeschool Inholland", "opleiding_naar_geslacht": "Luchtvaart"}
    script = snippet.generate(TOOL_GET_MAAT, args)
    assert script is not None and 'duo.load("p02ho1ejrs", 2)' in script and 'duo.load("p02ho1ejrs", 0)' in script
    ruimte: dict = {}
    exec(script.replace("print(df)", ""), ruimte)

    assert ruimte["df"][["STUDIEJAAR", "GESLACHT", W]].values.tolist() == [[2021, "MAN", 152], [2021, "VROUW", 22]]


def test_het_uitgangspunt_noemt_de_opleiding_die_de_code_koos():
    stap = (TOOL_GET_MAAT, get_maat("eerstejaars_ho", "Hogeschool Inholland", opleiding_naar_geslacht="Luchtvaart"))
    vraag = "Wat is de man-vrouwverhouding bij Luchtvaart van Hogeschool Inholland?"

    regel = uitgangspunt(vraag, "In 2021/22 was 87,4% man.", [stap])

    assert regel is not None and "B Luchtvaarttechnologie" in regel
