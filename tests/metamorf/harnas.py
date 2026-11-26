"""Bevroren fixtures en leeshulp voor de metamorfe tests (#1263), zonder netwerk en zonder model.

De fixtures zijn kleine, verzonnen tabellen met de vorm van de bron: DUO met een instellingscode, een sector
(ONDERWIJSSOORT), een leerweg en STUDIEJAAR, en de sentinel -1 voor een onderdrukte cel (data/domeinregels.toml);
CBS met dimensiecodes, een totaalcode per dimensie, de periodecode 2024SJ00 en een lege cel voor een onderdrukt
cijfer. De getallen komen uit een `random.Random` met vaste seed: elke run dezelfde data.

De tools geven tekst (JSON) terug. `uit` leest die, en faalt met de melding erbij als de tool weigerde: een relatie
die niet te toetsen is, is geen geslaagde relatie. `per_periode` en `waarde` maken er getallen van.
"""

from __future__ import annotations

import json
import random
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from unittest.mock import patch

import pandas as pd

from tools import cbs, store

SEED = 1263
JAREN = (2021, 2022, 2023, 2024)
AANTAL = "AANTAL"

# --- DUO -------------------------------------------------------------------------------------------------------------

DUO_INSCHRIJVINGEN = "duo:fxm:inschrijvingen"
DUO_MBO = "duo:fxm:mbo"
DUO_HO = "duo:fxm:ho"
DUO_LANDELIJK = "duo:fxm:landelijk"
DUO_ONDERDRUKT = "duo:fxm:onderdrukt"
DUO_ONDERDRUKT_LANDELIJK = "duo:fxm:onderdrukt_landelijk"

# (code, naam, sector, leerwegen): de sector bepaalt de leerwegen, zoals in de bestanden van DUO.
INSTELLINGEN = (
    ("90AA", "ROC Alfa", "mbo", ("BOL", "BBL")),
    ("90BB", "ROC Beta", "mbo", ("BOL", "BBL")),
    ("90CC", "Hogeschool Gamma", "hbo", ("VT", "DT")),
    ("90DD", "Universiteit Delta", "wo", ("VT", "DT")),
)
SECTOREN = ("mbo", "hbo", "wo")

# Echte, door DUO onderdrukte waarde (1-4) achter de -1 in DUO_ONDERDRUKT; staat alleen in het landelijke totaal.
VERBORGEN = 3


def _meta(dataset: str, instellingskolom: str | None = "INSTELLINGSCODE") -> store.KeyMeta:
    return store.KeyMeta(
        bron="duo", dataset=dataset, resource=0, periodekolom="STUDIEJAAR", instellingskolom=instellingskolom
    )


def duo_basis() -> pd.DataFrame:
    """De inschrijvingen per jaar, instelling en leerweg: de bron waar de andere DUO-fixtures uit volgen."""
    rng = random.Random(SEED)
    rijen = [
        (jaar, code, naam, sector, leerweg, rng.randint(40, 900))
        for jaar in JAREN
        for code, naam, sector, leerwegen in INSTELLINGEN
        for leerweg in leerwegen
    ]
    return pd.DataFrame(
        rijen, columns=["STUDIEJAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", "ONDERWIJSSOORT", "LEERWEG", AANTAL]
    )


def duo_fixtures(volgorde_seed: int | None = None) -> pd.DataFrame:
    """Zet de DUO-fixtures in de store; met `volgorde_seed` in een andere (vaste) rijvolgorde. Geeft de basis terug."""
    basis = duo_basis()
    if volgorde_seed is not None:
        basis = basis.sample(frac=1, random_state=volgorde_seed).reset_index(drop=True)
    store.put(DUO_INSCHRIJVINGEN, basis, _meta("fxm"))
    # Het mbo- en het ho-bestand apart, zoals DUO ze publiceert, en een landelijk bestand met één rij per jaar.
    store.put(DUO_MBO, basis[basis["ONDERWIJSSOORT"] == "mbo"].reset_index(drop=True), _meta("fxm-mbo"))
    store.put(DUO_HO, basis[basis["ONDERWIJSSOORT"] != "mbo"].reset_index(drop=True), _meta("fxm-ho"))
    landelijk = basis.groupby("STUDIEJAAR", as_index=False)[AANTAL].sum()
    store.put(DUO_LANDELIJK, landelijk, _meta("fxm-landelijk", instellingskolom=None))
    return basis


def duo_onderdrukt_fixtures() -> None:
    """Delen per sector met één onderdrukte cel (-1) in 2024; het landelijke bestand kent de echte waarde wel."""
    rijen = [
        (2023, "90AA", "ROC Alfa", "mbo", 120),
        (2023, "90CC", "Hogeschool Gamma", "hbo", 80),
        (2023, "90DD", "Universiteit Delta", "wo", 15),
        (2024, "90AA", "ROC Alfa", "mbo", 130),
        (2024, "90CC", "Hogeschool Gamma", "hbo", 90),
        (2024, "90DD", "Universiteit Delta", "wo", -1),  # DUO: een klein aantal (1-4), hier VERBORGEN
    ]
    delen = pd.DataFrame(rijen, columns=["STUDIEJAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", "ONDERWIJSSOORT", AANTAL])
    store.put(DUO_ONDERDRUKT, delen, _meta("fxm-onderdrukt"))
    echt = delen.assign(**{AANTAL: delen[AANTAL].where(delen[AANTAL] != -1, VERBORGEN)})
    totaal = echt.groupby("STUDIEJAAR", as_index=False)[AANTAL].sum()
    store.put(DUO_ONDERDRUKT_LANDELIJK, totaal, _meta("fxm-onderdrukt-landelijk", instellingskolom=None))


# --- Fusie (#728) ----------------------------------------------------------------------------------------------------

DUO_OUD = "duo:fxm:voor_de_fusie"  # een publicatie van vóór de fusie: elke instelling onder haar eigen code
DUO_NIEUW = "duo:fxm:na_de_fusie"  # een publicatie van erna: DUO rekent de reeks om naar de huidige code
XBRL_REEKS = "duo:fxm:verantwoording"  # DUO's verantwoording uit XBRL: rekent niet om (#935)

VOORGANGER_A, VOORGANGER_B, OPVOLGER = ("91AA", "ROC Oost"), ("91BB", "ROC West"), ("91CC", "ROC Midden")
FUSIEDAG = "2023-08-01"  # na de telling van 1-10-2022: 2021 en 2022 zijn vóór de fusie


def fusie_fixtures() -> dict[int, tuple[int, int]]:
    """De twee publicaties rond een fusie; geeft per jaar vóór de fusie de aantallen (A, B)."""
    rng = random.Random(SEED + 728)
    voor = {jaar: (rng.randint(200, 900), rng.randint(200, 900)) for jaar in (2021, 2022)}
    oud = pd.DataFrame(
        [
            (jaar, code, naam, n)
            for jaar, ab in voor.items()
            for (code, naam), n in zip((VOORGANGER_A, VOORGANGER_B), ab, strict=True)
        ],
        columns=["STUDIEJAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", AANTAL],
    )
    nieuw = pd.DataFrame(
        [(jaar, *OPVOLGER, a + b) for jaar, (a, b) in voor.items()]
        + [(jaar, *OPVOLGER, rng.randint(900, 1500)) for jaar in (2023, 2024)],
        columns=["STUDIEJAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", AANTAL],
    )
    store.put(DUO_OUD, oud, _meta("fxm-oud"))
    store.put(DUO_NIEUW, nieuw, _meta("fxm-nieuw"))
    return voor


def xbrl_fixtures() -> dict[int, tuple[int, int]]:
    """Een reeks zonder omrekening: de voorganger houdt eigen rijen tot zijn laatste jaar, de opvolger maakt een sprong."""
    rng = random.Random(SEED + 935)
    voor = {jaar: (rng.randint(10, 90), rng.randint(10, 90)) for jaar in (2021, 2022)}
    rijen = [(jaar, VOORGANGER_A[0], VOORGANGER_A[1], a) for jaar, (a, _) in voor.items()]
    rijen += [(jaar, OPVOLGER[0], OPVOLGER[1], b) for jaar, (_, b) in voor.items()]
    rijen += [(jaar, OPVOLGER[0], OPVOLGER[1], rng.randint(100, 180)) for jaar in (2023, 2024)]
    df = pd.DataFrame(rijen, columns=["STUDIEJAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", "BATEN"])
    store.put(XBRL_REEKS, df, _meta("fxm-xbrl"))
    return voor


# --- CBS -------------------------------------------------------------------------------------------------------------

CBS_DATASET = "fxm"
CBS_KEY = f"cbs:{CBS_DATASET}"
CBS_ONDERDRUKT_DATASET = "fxmo"
CBS_ONDERDRUKT = f"cbs:{CBS_ONDERDRUKT_DATASET}"
CBS_DIMENSIES = ["Geslacht", "Onderwijssoort", "Perioden"]
CBS_WAARDE = "TotaalIngeschrevenen_1"
CBS_AANDEEL = "AandeelVrouwen_2"  # een %-kolom: een som erover betekent niets (#866)

TOTAAL_GESLACHT, MANNEN, VROUWEN = "T001038", "3000", "4000"
HO_TOTAAL, HBO, WO = "T001128", "A025294", "A025297"
CBS_PERIODEN = tuple(f"{jaar}SJ00" for jaar in JAREN)


def cbs_code(jaar: int) -> str:
    return f"{jaar}SJ00"


def _cbs_rijen(rng: random.Random) -> list[dict]:
    """Geslacht is additief (mannen + vrouwen = totaal); Onderwijssoort niet: hbo + wo is meer dan het HO-totaal,
    want wie in beide staat ingeschreven, telt in het totaal één keer (cbs_meta.py, additiviteit)."""
    rijen = []
    for periode in CBS_PERIODEN:
        delen = {
            soort: {MANNEN: rng.randint(100, 900) * 10, VROUWEN: rng.randint(100, 900) * 10} for soort in (HBO, WO)
        }
        dubbel = {MANNEN: rng.randint(1, 30) * 10, VROUWEN: rng.randint(1, 30) * 10}
        delen[HO_TOTAAL] = {g: delen[HBO][g] + delen[WO][g] - dubbel[g] for g in (MANNEN, VROUWEN)}
        for soort, per_geslacht in delen.items():
            totaal = per_geslacht[MANNEN] + per_geslacht[VROUWEN]
            waarden = {**per_geslacht, TOTAAL_GESLACHT: totaal}
            aandelen = {MANNEN: 0.0, VROUWEN: 100.0, TOTAAL_GESLACHT: 100 * per_geslacht[VROUWEN] / totaal}
            for geslacht, n in waarden.items():
                aandeel = aandelen[geslacht]
                rijen.append(
                    {
                        "Geslacht": geslacht,
                        "Onderwijssoort": soort,
                        "Perioden": periode,
                        CBS_WAARDE: n,
                        CBS_AANDEEL: round(aandeel, 1),
                    }
                )
    return rijen


def cbs_fixtures(volgorde_seed: int | None = None) -> pd.DataFrame:
    """De CBS-tabel in de store met haar dimensies en eenheden, zoals get_cbs_data ze vastlegt."""
    df = pd.DataFrame(_cbs_rijen(random.Random(SEED + 1)))
    if volgorde_seed is not None:
        df = df.sample(frac=1, random_state=volgorde_seed).reset_index(drop=True)
    store.put(CBS_KEY, df, store.KeyMeta(bron="cbs", dataset=CBS_DATASET, periodekolom="Perioden"))
    cbs.register_dimensions(CBS_DATASET, CBS_DIMENSIES)
    cbs.register_units(CBS_DATASET, {CBS_WAARDE: "aantal", CBS_AANDEEL: "%"})
    return df


def cbs_onderdrukt_fixtures() -> None:
    """Een CBS-tabel met een lege cel ('.') bij de vrouwen in het wo in 2024; het totaal publiceert CBS wel.

    Leeg in één jaar en niet in alle: een onderdrukt cijfer, geen combinatie die niet bestaat (#1213).
    """
    rijen = []
    for jaar, (man, vrouw) in zip(JAREN, ((500, 40), (510, 50), (520, 60), (530, 30)), strict=True):
        for geslacht, n in ((MANNEN, man), (VROUWEN, None if jaar == 2024 else vrouw), (TOTAAL_GESLACHT, man + vrouw)):
            rijen.append({"Geslacht": geslacht, "Onderwijssoort": WO, "Perioden": cbs_code(jaar), CBS_WAARDE: n})
    df = pd.DataFrame(rijen)
    meta = store.KeyMeta(bron="cbs", dataset=CBS_ONDERDRUKT_DATASET, periodekolom="Perioden")
    store.put(CBS_ONDERDRUKT, df, meta)
    cbs.register_dimensions(CBS_ONDERDRUKT_DATASET, CBS_DIMENSIES)
    cbs.register_units(CBS_ONDERDRUKT_DATASET, {CBS_WAARDE: "aantal"})


# --- get_maat: de bestanden en het register zoals tests/test_maten.py ze nepen -----------------------------------------

HU = {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"}


def _maat_ho() -> pd.DataFrame:
    rng = random.Random(SEED + 188)
    rijen = [
        (jaar, "25DW", "Hogeschool Utrecht", vorm, rng.randint(1, 900))
        for jaar in JAREN
        for vorm in ("VT", "VT", "DT", "DU")  # twee VT-rijen: de maat telt ze op
    ]
    rijen += [(jaar, "99ZZ", "Andere Hogeschool", "VT", 7) for jaar in JAREN]
    kolommen = [
        "STUDIEJAAR",
        "INSTELLINGSCODE_ACTUEEL",
        "INSTELLINGSNAAM_ACTUEEL",
        "OPLEIDINGSVORM",
        "AANTAL_INGESCHREVENEN",
    ]
    return pd.DataFrame(rijen, columns=kolommen)


@contextmanager
def maat_bronnen() -> Generator[None]:
    """get_maat zonder netwerk: het register is een nep, DUO laadt de fixture (de catalogus is echt)."""
    bestand = _maat_ho()
    register = {"hogeschool utrecht": HU, "hu": HU}
    with (
        patch(
            "tools.maten.instellingen.instellingsprofiel", side_effect=lambda naam: register.get(naam.strip().lower())
        ),
        patch("tools.duo._duo.load", side_effect=lambda dataset_id, resource: bestand.copy()),
    ):
        yield


# --- koppel_data (#988): de vorm van tests/test_koppel.py -----------------------------------------------------------

SKDB_KEY = "skdb:opleidingen:fxm"
KOPPEL_DUO = "duo:p01hoinges:0"


def koppel_fixtures(volgorde_seed: int | None = None) -> pd.DataFrame:
    """Een SKDB- en een DUO-tabel met deels dezelfde opleidingen; geeft de DUO-tabel terug."""
    rng = random.Random(SEED + 988)
    gedeeld = [30020 + 10 * i for i in range(12)]
    skdb_df = pd.DataFrame({"brin": "25DW", "croho": [*gedeeld, 50001, 50002], "nse_oordeel": 3.5})
    duo_codes = [*gedeeld, 35999]
    duo_df = pd.DataFrame(
        {
            "INSTELLINGSCODE_ACTUEEL": "25DW",
            "OPLEIDINGSCODE_ACTUEEL": [float(c) for c in duo_codes],
            AANTAL: [rng.randint(5, 400) for _ in duo_codes],
        }
    )
    if volgorde_seed is not None:
        skdb_df = skdb_df.sample(frac=1, random_state=volgorde_seed).reset_index(drop=True)
        duo_df = duo_df.sample(frac=1, random_state=volgorde_seed + 1).reset_index(drop=True)
    store.put(SKDB_KEY, skdb_df, store.KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase"))
    store.put(KOPPEL_DUO, duo_df, store.KeyMeta(bron="duo", dataset="p01hoinges", resource=0))
    return duo_df


# --- uitkomsten lezen ------------------------------------------------------------------------------------------------


def uit(tekst: str) -> dict:
    """De JSON van een tool; een weigering of foutmelding laat de relatie falen, met de melding erbij."""
    try:
        data = json.loads(tekst)
    except ValueError:
        raise AssertionError(f"de tool gaf geen uitkomst maar een melding: {tekst[:400]}") from None
    if not isinstance(data, dict) or "fout" in data:
        raise AssertionError(f"de tool weigerde: {str(data)[:400]}")
    return data


def uit_fout(tekst: str) -> str:
    """De foutmelding van compute_kpi; faalt als de tool toch een getal gaf."""
    data = json.loads(tekst)
    assert isinstance(data, dict) and "fout" in data, f"verwacht een weigering, kreeg: {tekst[:400]}"
    return data["fout"]


def rijen(tekst: str) -> list[dict]:
    data = uit(tekst)
    assert data.get("totaal_rijen", len(data["rijen"])) == len(data["rijen"]), "afgekapt resultaat: verklein de fixture"
    return data["rijen"]


def per_periode(tekst: str, periodekolom: str, kolom: str, sleutels: Iterable[str] = ()) -> dict:
    """Per periode (en per waarde van `sleutels`) het getal in `kolom`; een lege (onderdrukte) waarde blijft None."""
    uitkomst: dict = {}
    for rij in rijen(tekst):
        sleutel = (rij[periodekolom], *(rij[s] for s in sleutels))
        assert sleutel not in uitkomst, f"twee rijen voor {sleutel}: de selectie is niet eenduidig"
        uitkomst[sleutel if len(sleutel) > 1 else sleutel[0]] = rij[kolom]
    return uitkomst


def waarde(tekst: str, kolom: str) -> float | None:
    """Het getal van een uitkomst met precies één rij."""
    gevonden = rijen(tekst)
    assert len(gevonden) == 1, f"verwacht één rij, kreeg {len(gevonden)}: {gevonden[:5]}"
    return gevonden[0][kolom]


def getal(tekst: str, kolom: str) -> float:
    """Als `waarde`, maar het getal moet er zijn: een lege cel is hier een fout in de fixture of de tool."""
    gevonden = waarde(tekst, kolom)
    assert gevonden is not None, f"lege waarde in '{kolom}'"
    return gevonden


def kpi(tekst: str) -> float:
    """De ruwe waarde van compute_kpi."""
    return float(uit(tekst)["raw"])
