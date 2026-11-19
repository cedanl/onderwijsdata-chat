"""Vergelijkingsgroep en landelijke ranking per type van de instelling (#926, #928).

Mijn instelling vergelijkt een hogeschool met hogescholen, een universiteit met universiteiten en een mbo-instelling
met mbo-instellingen, in de smalste regio met ten minste drie andere (#948; arbeidsmarktregio, provincie, landelijk); het
label noemt regio, aantal en de reden van een terugval. Landelijk rangschikt alleen instellingen van het eigen type, en
rekent het marktaandeel over het totaal van dat type (#950).

De trap staat hier met een verzonnen register en verzonnen adressen; de rest draait op de bevroren DUO-bestanden
(`duo_fixtures`) en rekent de verwachting met pandas na, los van data/dashboard.py.
"""

import json

import pandas as pd
import pytest

from data import dashboard

# ─── De trap: arbeidsmarktregio → provincie → landelijk ──────────────────────


def _adres(provincie: str | None, amr: str | None) -> dict:
    return {"provincie": provincie, "arbeidsmarktregio": amr, "plaatsnaam": None, "bevoegd_gezag": None}


@pytest.fixture
def register(monkeypatch):
    """Een verzonnen register: (naam, code, type, provincie, arbeidsmarktregio[, omvang]) per instelling.

    De omvang (ingeschrevenen in het laatste jaar, #1008) is optioneel; zonder omvang bij één instelling kent het register
    geen omvang, zoals wanneer de DUO-bestanden niet laden, en geldt er geen omvangsdrempel.
    """

    def zet(*instellingen):
        registry = [{"naam": i[0], "instellingscode": i[1], "type": i[2]} for i in instellingen]
        adres = {i[1]: _adres(i[3], i[4]) for i in instellingen if i[3] or i[4]}
        omvang = {i[1]: i[5] for i in instellingen if len(i) > 5 and i[5] is not None}
        monkeypatch.setattr(dashboard, "get_all_instellingen", lambda: registry)
        monkeypatch.setattr(dashboard, "get_adres_lookup", lambda: adres)
        monkeypatch.setattr(dashboard, "_omvang_per_code", lambda _onderwijs_type: omvang)

    return zet


def _context(instelling: str, onderwijs_type: str = "ho") -> dashboard.RegioContext:
    ctx = dashboard._build_regio_context(instelling, onderwijs_type)
    assert ctx is not None
    return ctx


def test_hbo_in_de_arbeidsmarktregio_zonder_de_universiteit_ernaast(register):
    register(
        ("Hogeschool A", "HA", "hbo", "Utrecht", "Midden-Utrecht"),
        ("Hogeschool B", "HB", "hbo", "Utrecht", "Midden-Utrecht"),
        ("Hogeschool C", "HC", "hbo", "Utrecht", "Midden-Utrecht"),
        ("Hogeschool D", "HD", "hbo", "Utrecht", "Midden-Utrecht"),
        ("Universiteit U", "UU", "wo", "Utrecht", "Midden-Utrecht"),
        ("Roc R", "RR", "mbo", "Utrecht", "Midden-Utrecht"),
    )

    ctx = _context("Hogeschool A")

    assert (ctx.regio_type, ctx.regio_naam, ctx.soort) == ("arbeidsmarktregio", "Midden-Utrecht", "hbo")
    assert ctx.peer_codes == {"HB", "HC", "HD"}
    assert ctx.terugval is None
    kop = dashboard._benchmark_kop(ctx, 3)
    assert kop["label"] == "Arbeidsmarktregio Midden-Utrecht, 3 andere hogescholen"
    assert kop["populatie"] == "hogescholen in arbeidsmarktregio Midden-Utrecht"


def test_hbo_valt_terug_op_de_provincie_als_de_arbeidsmarktregio_alleen_universiteiten_heeft(register):
    # Breda (#926): in West-Brabant geen andere hogeschool; in Noord-Brabant wel, naast twee universiteiten.
    register(
        ("Breda", "BR", "hbo", "Noord-Brabant", "West-Brabant"),
        ("Fontys", "FO", "hbo", "Noord-Brabant", "Zuidoost-Brabant"),
        ("Avans", "AV", "hbo", "Noord-Brabant", "Midden-Brabant"),
        ("HAS", "HS", "hbo", "Noord-Brabant", "Noordoost-Brabant"),
        ("Tilburg", "TI", "wo", "Noord-Brabant", "Midden-Brabant"),
        ("TU Eindhoven", "TE", "wo", "Noord-Brabant", "Zuidoost-Brabant"),
    )

    ctx = _context("Breda")

    assert (ctx.regio_type, ctx.regio_naam) == ("provincie", "Noord-Brabant")
    assert ctx.peer_codes == {"FO", "AV", "HS"}
    assert dashboard._benchmark_kop(ctx, 3)["label"] == (
        "Provincie Noord-Brabant, 3 andere hogescholen — te weinig hogescholen in arbeidsmarktregio West-Brabant (0 andere)"
    )


def test_wo_valt_terug_op_landelijk_met_de_reden_van_de_provincie(register):
    # Tilburg (#926): één andere universiteit in de provincie is te weinig; landelijk telt ook een universiteit zonder
    # adres mee, want daar speelt de regio geen rol.
    register(
        ("Tilburg", "TI", "wo", "Noord-Brabant", "Midden-Brabant"),
        ("TU Eindhoven", "TE", "wo", "Noord-Brabant", "Zuidoost-Brabant"),
        ("Leiden", "LE", "wo", "Zuid-Holland", "Holland Rijnland"),
        ("Zonder adres", "ZA", "wo", None, None),
        ("Fontys", "FO", "hbo", "Noord-Brabant", "Zuidoost-Brabant"),
        ("Avans", "AV", "hbo", "Noord-Brabant", "Midden-Brabant"),
    )

    ctx = _context("Tilburg")

    assert (ctx.regio_type, ctx.regio_naam, ctx.soort) == ("nationaal", "Nederland", "wo")
    assert ctx.peer_codes == {"TE", "LE", "ZA"}
    assert ctx.provincie == "Noord-Brabant"  # de UWV-vacatures blijven die van de eigen provincie
    kop = dashboard._benchmark_kop(ctx, 3)
    assert kop["label"] == (
        "Landelijk, 3 andere universiteiten — te weinig universiteiten in provincie Noord-Brabant (1 andere)"
    )
    assert kop["populatie"] == "universiteiten in heel Nederland"
    assert kop["terugval"] == "te weinig universiteiten in provincie Noord-Brabant (1 andere)"


def test_mbo_met_één_andere_in_de_arbeidsmarktregio_vergelijkt_in_de_provincie(register):
    register(
        ("Roc A", "RA", "mbo", "Gelderland", "FoodValley"),
        ("Roc B", "RB", "mbo", "Gelderland", "FoodValley"),
        ("Roc C", "RC", "mbo", "Gelderland", "Achterhoek"),
        ("Roc D", "RD", "mbo", "Gelderland", "Rijk van Nijmegen"),
        ("Hogeschool H", "HH", "hbo", "Gelderland", "FoodValley"),
    )

    ctx = _context("Roc A", "mbo")

    assert (ctx.regio_type, ctx.regio_naam, ctx.soort) == ("provincie", "Gelderland", "mbo")
    assert ctx.peer_codes == {"RB", "RC", "RD"}
    assert dashboard._benchmark_kop(ctx, 1)["label"] == (
        "Provincie Gelderland, 1 andere mbo-instelling — te weinig mbo-instellingen in arbeidsmarktregio FoodValley "
        "(1 andere)"
    )


_ONDERWIJSTYPE = {"mbo": "mbo", "hbo": "ho", "wo": "ho"}
# Per trede: (arbeidsmarktregio, provincie) van de `n` andere op die trede, en van drie extra op de trede erboven.
_OP_DE_TREDE = {
    "arbeidsmarktregio": (("Thuis", "Eigen"), ("Thuis", "Buur")),
    "provincie": (("Thuis", "Buur"), ("Ver", "Ver weg")),
}
_BREDER = {"arbeidsmarktregio": "provincie", "provincie": "nationaal"}


@pytest.mark.parametrize("soort", ["mbo", "hbo", "wo"])
@pytest.mark.parametrize("trede", ["arbeidsmarktregio", "provincie"])
@pytest.mark.parametrize("n", [2, 3])
def test_drempel_van_drie_andere_per_niveau(register, soort, trede, n):
    """Op elke trede: met twee andere van het type schuift de vergelijking een trede op, met drie blijft ze (#948).

    De eigen instelling staat in arbeidsmarktregio Eigen, provincie Thuis. Op de trede erboven staan er altijd genoeg,
    zodat het verschil alleen van `n` komt; drie instellingen van een ander type op de trede tellen niet mee.
    """
    (provincie, amr), (provincie_erboven, amr_erboven) = _OP_DE_TREDE[trede]
    ander = "hbo" if soort == "wo" else "wo"
    register(
        ("Eigen", "E0", soort, "Thuis", "Eigen"),
        *[(f"Op de trede {i}", f"T{i}", soort, provincie, amr) for i in range(n)],
        *[(f"Erboven {i}", f"B{i}", soort, provincie_erboven, amr_erboven) for i in range(3)],
        *[(f"Ander type {i}", f"A{i}", ander, provincie, amr) for i in range(3)],
    )

    ctx = _context("Eigen", _ONDERWIJSTYPE[soort])

    assert dashboard._MIN_PEERS == 3
    assert ctx.soort == soort
    if n == 3:
        assert ctx.regio_type == trede
        assert ctx.peer_codes == {"T0", "T1", "T2"}
    else:
        regio_naam = "Eigen" if trede == "arbeidsmarktregio" else "Thuis"
        assert ctx.regio_type == _BREDER[trede]
        assert ctx.terugval == f"te weinig {dashboard._SOORTNAAM[soort][1]} in {trede} {regio_naam} (2 andere)"


def test_zonder_adres_landelijk_met_die_reden(register):
    # Eerder gaf dit geen vergelijking, zonder uitleg (HZ en NHL Stenden: geen andere instelling in de regio).
    register(("Zonder adres", "ZA", "hbo", None, None), ("Hogeschool B", "HB", "hbo", "Utrecht", "Midden-Utrecht"))

    ctx = _context("Zonder adres")

    assert (ctx.regio_type, ctx.peer_codes) == ("nationaal", {"HB"})
    assert ctx.terugval == "regio onbekend: DUO heeft geen adres van de instelling"


def test_een_mbo_instelling_heeft_geen_ho_vergelijking(register):
    register(("Roc A", "RA", "mbo", "Utrecht", "Midden-Utrecht"), ("Roc B", "RB", "mbo", "Utrecht", "Midden-Utrecht"))

    assert dashboard._build_regio_context("Roc A", "ho") is None
    assert dashboard._build_regio_context("Onbekend", "mbo") is None


# ─── Een peer telt vanaf 10% van de eigen omvang (#1008) ─────────────────────

_OMVANG_TE_KLEIN = "minder dan 10% van de eigen omvang"


def _universiteiten_elders():
    return (
        ("TU Delft", "TD", "wo", "Zuid-Holland", "Haaglanden", 25977),
        ("UvA", "UA", "wo", "Noord-Holland", "Groot-Amsterdam", 43236),
        ("VU", "VU", "wo", "Noord-Holland", "Groot-Amsterdam", 30733),
    )


def test_de_universiteit_utrecht_vergelijkt_niet_met_drie_kleine_universiteiten(register):
    # #1008: in Midden-Utrecht en de provincie Utrecht staan naast de UU (37.090) alleen PThU, TUU en Humanistiek,
    # samen nog geen 1% van haar omvang. Met drie andere haalde de regio de drempel van #948.
    register(
        ("Universiteit U", "UU", "wo", "Utrecht", "Midden-Utrecht", 37090),
        ("Humanistiek", "UH", "wo", "Utrecht", "Midden-Utrecht", 445),
        ("TUU", "TU", "wo", "Utrecht", "Midden-Utrecht", 142),
        ("PThU", "PT", "wo", "Utrecht", "Midden-Utrecht", 118),
        *_universiteiten_elders(),
    )

    ctx = _context("Universiteit U")

    assert ctx.regio_type == "nationaal"
    assert ctx.peer_codes == {"TD", "UA", "VU"}  # ook landelijk telt geen van de drie
    assert ctx.terugval == (
        f"te weinig universiteiten van vergelijkbare omvang in provincie Utrecht (0 van 3 andere; {_OMVANG_TE_KLEIN})"
    )
    assert dashboard._benchmark_kop(ctx, 3)["label"] == f"Landelijk, 3 andere universiteiten — {ctx.terugval}"


@pytest.mark.parametrize(("kleinste", "telt"), [(100, True), (99, False)])
def test_precies_tien_procent_telt_net_niet_tien_procent_niet(register, kleinste, telt):
    register(
        ("Hogeschool A", "HA", "hbo", "Utrecht", "Midden-Utrecht", 1000),
        ("Hogeschool B", "HB", "hbo", "Utrecht", "Midden-Utrecht", 100),
        ("Hogeschool C", "HC", "hbo", "Utrecht", "Midden-Utrecht", 5000),
        ("Hogeschool D", "HD", "hbo", "Utrecht", "Midden-Utrecht", kleinste),
        ("Hogeschool E", "HE", "hbo", "Utrecht", "Eemland", 900),
    )

    ctx = _context("Hogeschool A")

    assert dashboard._MIN_PEER_OMVANG == 0.10
    if telt:
        assert (ctx.regio_type, ctx.peer_codes, ctx.terugval) == ("arbeidsmarktregio", {"HB", "HC", "HD"}, None)
    else:
        assert (ctx.regio_type, ctx.peer_codes) == ("provincie", {"HB", "HC", "HE"})
        assert ctx.terugval == (
            "te weinig hogescholen van vergelijkbare omvang in arbeidsmarktregio Midden-Utrecht "
            f"(2 van 3 andere; {_OMVANG_TE_KLEIN})"
        )


def test_twee_grote_en_drie_kleine_in_de_regio_valt_terug(register):
    register(
        ("Roc A", "RA", "mbo", "Gelderland", "FoodValley", 10000),
        ("Roc B", "RB", "mbo", "Gelderland", "FoodValley", 9000),
        ("Roc C", "RC", "mbo", "Gelderland", "FoodValley", 12000),
        *[(f"Klein {i}", f"K{i}", "mbo", "Gelderland", "FoodValley", 300) for i in range(3)],
        ("Roc D", "RD", "mbo", "Gelderland", "Achterhoek", 4000),
    )

    ctx = _context("Roc A", "mbo")

    assert (ctx.regio_type, ctx.regio_naam) == ("provincie", "Gelderland")
    assert ctx.peer_codes == {"RB", "RC", "RD"}  # de kleine vallen ook in de provincie af
    assert ctx.terugval == (
        f"te weinig mbo-instellingen van vergelijkbare omvang in arbeidsmarktregio FoodValley (2 van 5 andere; "
        f"{_OMVANG_TE_KLEIN})"
    )


_MIDDELGROOT = (
    ("Breda", "BR", "hbo", "Noord-Brabant", "West-Brabant", 9000),
    ("Fontys", "FO", "hbo", "Noord-Brabant", "Zuidoost-Brabant", 45000),
    ("Avans", "AV", "hbo", "Noord-Brabant", "Midden-Brabant", 30000),
    ("HAS", "HS", "hbo", "Noord-Brabant", "Noordoost-Brabant", 2500),
    ("Tilburg", "TI", "wo", "Noord-Brabant", "Midden-Brabant", 20000),
)


def test_een_middelgrote_hogeschool_met_gewone_peers_houdt_haar_vergelijking(register):
    # Alle peers halen 10%: dezelfde groep, regio en reden als zonder omvangsdrempel (zoals vóór #1008).
    register(*(i[:5] for i in _MIDDELGROOT))
    zonder_omvang = _context("Breda")
    register(*_MIDDELGROOT)

    ctx = _context("Breda")

    assert ctx == zonder_omvang
    assert (ctx.regio_type, ctx.peer_codes) == ("provincie", {"FO", "AV", "HS"})
    assert dashboard._benchmark_kop(ctx, 3)["label"] == (
        "Provincie Noord-Brabant, 3 andere hogescholen — te weinig hogescholen in arbeidsmarktregio West-Brabant (0 andere)"
    )


@pytest.mark.parametrize("eigen", [None, 0])
def test_zonder_eigen_omvang_geldt_geen_drempel(register, eigen):
    register(
        ("Universiteit U", "UU", "wo", "Utrecht", "Midden-Utrecht", eigen),
        ("Humanistiek", "UH", "wo", "Utrecht", "Midden-Utrecht", 445),
        ("TUU", "TU", "wo", "Utrecht", "Midden-Utrecht", 142),
        ("PThU", "PT", "wo", "Utrecht", "Midden-Utrecht", 118),
        *_universiteiten_elders(),
    )

    ctx = _context("Universiteit U")

    assert (ctx.regio_type, ctx.peer_codes, ctx.terugval) == ("arbeidsmarktregio", {"UH", "TU", "PT"}, None)


def test_een_peer_zonder_omvang_telt_niet_als_de_eigen_omvang_bekend_is(register):
    register(
        ("Hogeschool A", "HA", "hbo", "Utrecht", "Midden-Utrecht", 1000),
        ("Hogeschool B", "HB", "hbo", "Utrecht", "Midden-Utrecht", 800),
        ("Hogeschool C", "HC", "hbo", "Utrecht", "Midden-Utrecht", 700),
        ("Zonder omvang", "HZ", "hbo", "Utrecht", "Midden-Utrecht"),
    )

    ctx = _context("Hogeschool A")

    assert (ctx.regio_type, ctx.peer_codes) == ("nationaal", {"HB", "HC"})
    assert ctx.terugval == (
        f"te weinig hogescholen van vergelijkbare omvang in provincie Utrecht (2 van 3 andere; {_OMVANG_TE_KLEIN})"
    )


def test_de_omvang_van_een_mbo_instelling_telt_al_haar_codes_in_het_laatste_jaar(monkeypatch):
    mbo = pd.DataFrame(
        [
            # JAAR, INSTELLINGSCODE, INSTELLINGSNAAM, BBL, BOLVT, BOLDT, EX
            (2024, "11AA", "Twee codes", 9999, 9999, 0, 0),
            (2025, "11AA", "Twee codes", 100, 200, 0, 10),
            (2025, "22BB", "Twee codes", 1000, 2000, 5, None),  # een lege cel telt niet mee
            (2025, "33CC", "Eén code", 50, 60, 0, 0),
            (2025, "44DD", "Alles leeg", None, None, None, None),
        ],
        columns=["JAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", "BBL", "BOLVT", "BOLDT", "EX"],
    )
    monkeypatch.setattr(dashboard, "_load_mbo_studenten", lambda: mbo)

    assert dashboard._omvang_per_code("mbo") == {"11AA": 3315, "22BB": 3315, "33CC": 110}


def test_de_omvang_is_leeg_als_de_bron_niet_laadt(monkeypatch):
    def faalt():
        raise OSError("DUO is weg")

    monkeypatch.setattr(dashboard, "_load_ho_ingeschrevenen", faalt)
    monkeypatch.setattr(dashboard, "_load_mbo_studenten", faalt)

    assert dashboard._omvang_per_code("ho") == {}
    assert dashboard._omvang_per_code("mbo") == {}


# ─── Mijn instelling op de bevroren DUO-bestanden ────────────────────────────

_met_duo = pytest.mark.usefixtures("duo_fixtures", "arbeidsmarkt_fixtures")


def _typen() -> dict[str, str]:
    from data.instellingen import get_all

    return {i["naam"]: i["type"] for i in get_all()}


@_met_duo
@pytest.mark.parametrize(
    ("instelling", "soort", "label"),
    [
        # mbo: Rijnmond heeft alleen Zadkine en Grafisch Lyceum naast Albeda; twee is te weinig (#948).
        (
            "Albeda",
            "mbo",
            "Provincie Zuid-Holland, 3 andere mbo-instellingen — te weinig mbo-instellingen in arbeidsmarktregio "
            "Rijnmond (2 andere)",
        ),
        # mbo: West-Brabant heeft geen andere; in Noord-Brabant zeven, waarvan BBO de Schalm zonder gegevens (#925).
        (
            "Curio",
            "mbo",
            "Provincie Noord-Brabant, 6 andere mbo-instellingen — te weinig mbo-instellingen in arbeidsmarktregio "
            "West-Brabant (0 andere)",
        ),
        # hbo: in Midden-Utrecht staan HKU en Universiteit Utrecht; alleen HKU is een hogeschool, en in de provincie
        # ook. Eerder stond de universiteit tussen de peers van HU. Landelijk valt Codarts af: 966 ingeschrevenen is
        # minder dan 10% van de 35.058 van HU (#1008).
        (
            "Hogeschool Utrecht",
            "hbo",
            "Landelijk, 3 andere hogescholen — te weinig hogescholen in provincie Utrecht (1 andere)",
        ),
        # wo: geen andere universiteit in Midden-Utrecht of de provincie Utrecht.
        (
            "Universiteit Utrecht",
            "wo",
            "Landelijk, 3 andere universiteiten — te weinig universiteiten in provincie Utrecht (0 andere)",
        ),
    ],
)
def test_vergelijkingsgroep_per_niveau_is_type_zuiver(instelling, soort, label):
    bm = dashboard.load_dashboard_regio(instelling)["benchmark"]

    typen = _typen()
    assert typen[instelling] == soort
    peers = set(bm["peers"]["ingeschrevenen"]) | set(bm.get("geen_gegevens", {}).get("ingeschrevenen", []))
    assert peers
    assert {typen[p] for p in peers} == {soort}
    assert bm["soort"] == soort
    assert bm["label"] == label
    assert bm["n_instellingen"] == len(bm["peers"]["ingeschrevenen"])


@_met_duo
def test_de_omvang_komt_uit_de_ingeschrevenen_van_het_laatste_jaar():
    # ho: per INSTELLINGSCODE_ACTUEEL over hbo en wo samen (HvA: 41.889 hbo + 58 wo); mbo: per naam over alle codes,
    # dezelfde 15.288 als de reeks van Curio (test_dashboard_mbo_reeksen).
    ho, mbo = dashboard._omvang_per_code("ho"), dashboard._omvang_per_code("mbo")

    assert (ho["21PD"], ho["28DN"], ho["14NI"]) == (37090, 41889 + 58, 966)
    assert mbo["21CY"] == mbo["25LX"] == 15288
    assert mbo["24ZW"] == 0  # BBO de Schalm: onderdrukte cellen en nullen


@_met_duo
def test_kaart_en_benchmark_volgen_de_peers_van_vergelijkbare_omvang():
    # Hogeschool Utrecht landelijk: Codarts (966) valt af in de context, en dus overal waar die context komt.
    ctx = _context("Hogeschool Utrecht")
    assert "14NI" not in ctx.peer_codes

    regio = dashboard.load_dashboard_regio("Hogeschool Utrecht")
    bm = regio["benchmark"]
    peers = set(bm["peers"]["ingeschrevenen"]) | set(bm.get("geen_gegevens", {}).get("ingeschrevenen", []))
    assert peers == {"Hogeschool voor de Kunsten Utrecht", "De Haagse Hogeschool", "Hogeschool van Amsterdam"}
    assert bm["n_instellingen"] == 3
    kaart = json.loads(regio["kaart_figure_json"])["layout"]["meta"]
    assert "Codarts, Hogeschool voor de Kunsten" not in json.dumps(kaart)

    # Curio: BBO de Schalm (0 ingeschrevenen in 2025) is geen peer meer, ook niet in het rendement.
    curio = _context("Curio", "mbo")
    assert "24ZW" not in curio.peer_codes
    rendement = dashboard.load_dashboard_rendement("Curio")
    assert "BBO de Schalm" not in rendement["peers_rendement"] | rendement["peers_weggelaten"]


# ─── Landelijk per type (#928) ───────────────────────────────────────────────

_INST = "INSTELLINGSNAAM_ACTUEEL"


def _ho_laatste_jaar() -> tuple[pd.DataFrame, set[str]]:
    """De ingeschrevenen ho van het laatste jaar (beide resources, -1 als leeg) en de hogescholen: de namen uit de
    hbo-resource. Een hogeschool met wo-studenten (HvA) staat ook in de wo-resource, maar is een hogeschool."""
    from onderwijsbronnen import duo

    hbo, wo = duo.load("p01hoinges", 0), duo.load("p01hoinges", 1)
    df = pd.concat([hbo, wo], ignore_index=True)
    df = df[df["AANTAL_INGESCHREVENEN"] >= 0]
    return df[df["STUDIEJAAR"] == df["STUDIEJAAR"].max()], set(hbo[_INST])


@_met_duo
@pytest.mark.parametrize(("instelling", "soort"), [("Hogeschool Utrecht", "hbo"), ("Universiteit Utrecht", "wo")])
def test_landelijk_rangschikt_binnen_het_eigen_type(instelling, soort):
    laatste, hogescholen = _ho_laatste_jaar()
    in_soort = laatste[laatste[_INST].isin(hogescholen) == (soort == "hbo")]
    totaal = in_soort.groupby(_INST)["AANTAL_INGESCHREVENEN"].sum().sort_values(ascending=False)

    result = dashboard.load_dashboard_nationaal(instelling)

    assert [i["naam"] for i in result["alle_instellingen"]] == list(totaal.index)
    assert {i["type"] for i in result["alle_instellingen"]} == {soort}
    assert result["populatie"] == {"soort": soort, "n": len(totaal)}
    if soort == "wo":
        assert "Hogeschool van Amsterdam" not in totaal.index  # een paar wo-studenten maken haar geen universiteit

    positie, van = {}, {}
    for onderdeel, groep in in_soort.groupby("ONDERDEEL"):
        sommen = groep.groupby(_INST)["AANTAL_INGESCHREVENEN"].sum()
        if sommen.get(instelling, 0) <= 0:
            continue
        positie[onderdeel] = 1 + int((sommen > sommen[instelling]).sum())
        van[onderdeel] = int((sommen > 0).sum())
    assert positie
    assert result["eigen_positie"] == positie
    assert result["positie_populatie"] == van
    assert all(p <= van[o] for o, p in positie.items())


@_met_duo
def test_landelijk_mbo_noemt_zijn_populatie():
    result = dashboard.load_dashboard_nationaal("Albeda")

    assert result["populatie"] == {"soort": "mbo", "n": len(result["alle_instellingen"])}
    assert set(result["positie_populatie"]) == set(result["eigen_positie"])


@_met_duo
@pytest.mark.parametrize(("instelling", "soort"), [("Hogeschool Utrecht", "hbo"), ("Universiteit Utrecht", "wo")])
def test_marktaandeel_rekent_over_het_totaal_van_het_eigen_type(instelling, soort):
    # #950: de noemer van het marktaandeel (`sectoren_landelijk`) is het totaal van hetzelfde type, in elk jaar; een
    # hogeschool met wo-studenten (HvA) telt met al haar studenten bij de hogescholen, zoals in de ranking.
    from onderwijsbronnen import duo

    hbo, wo = duo.load("p01hoinges", 0), duo.load("p01hoinges", 1)
    alles = pd.concat([hbo, wo], ignore_index=True)
    alles = alles[alles["AANTAL_INGESCHREVENEN"] >= 0]
    in_soort = alles[alles[_INST].isin(set(hbo[_INST])) == (soort == "hbo")]
    verwacht: dict[str, dict[int, int]] = {}
    for (onderdeel, jaar), n in in_soort.groupby(["ONDERDEEL", "STUDIEJAAR"])["AANTAL_INGESCHREVENEN"].sum().items():
        verwacht.setdefault(onderdeel, {})[int(jaar)] = int(n)

    result = dashboard.load_dashboard_nationaal(instelling)

    assert result["sectoren_landelijk"] == verwacht
    # Het eigen aantal zit in de noemer: per sector ligt het aandeel tussen 0 en 1.
    laatste = result["laatste_jaar"]
    for onderdeel, reeks in result["eigen_sectoren"].items():
        if reeks.get(laatste):
            assert 0 < reeks[laatste] <= result["sectoren_landelijk"][onderdeel][laatste]
    assert result["landelijk"]["definitie"].startswith(
        f"de som van DUO p01hoinges over alle {dashboard._SOORTNAAM[soort][1]};"
    )


@_met_duo
def test_marktaandeel_mbo_blijft_over_alle_mbo_instellingen():
    # Het mbo was al type-zuiver: het bestand kent alleen mbo-instellingen, en de noemer blijft het hele bestand.
    result = dashboard.load_dashboard_nationaal("Albeda")

    mbo = dashboard._load_mbo_studenten()
    laatste = result["laatste_jaar"]
    for leerweg, kolom in (("BBL", "BBL"), ("BOL voltijd", "BOLVT")):
        assert result["sectoren_landelijk"][leerweg][laatste] == int(mbo[mbo["JAAR"] == laatste][kolom].sum())
    assert result["landelijk"]["definitie"].startswith(
        "de som van DUO mbo-studenten-per-instelling over alle mbo-instellingen;"
    )
