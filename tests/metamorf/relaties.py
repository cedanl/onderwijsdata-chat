"""De metamorfe relaties (#1263): elk een functie die faalt (AssertionError) als de relatie breekt.

Een relatie kent de juiste uitkomst niet; ze toetst dat twee wegen naar hetzelfde getal hetzelfde geven: de delen en
het totaal, de sectoren en landelijk, een jaar uit een reeks en dat jaar alleen, een andere volgorde, een fusie
voor en na de omrekening, een verschil uit compute_kpi en uit twee losse jaren. Waar de bron geen gelijkheid belooft
(een niet-additieve CBS-maat, een onderdrukte cel), eist de relatie juist geen gelijkheid.

Elke relatie zet haar eigen fixtures in een lege store, zodat `test_scherpte.py` ze één voor één tegen een kapotte
variant van de tools kan draaien. De tests staan in `test_relaties.py`.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from unittest.mock import patch

from onderwijsbronnen.rio import Stap

from tools import duo, fusies, optelbaar, query, store
from tools.koppel import koppel_data
from tools.kpi import compute_kpi
from tools.maten import get_maat
from tools.query import query_data

from . import harnas as h


@dataclass(frozen=True)
class Relatie:
    naam: str
    soort: str  # de relatie uit de tabel in README.md
    tool: str
    bron: str
    toets: Callable[[], None]
    # Het issue van een relatie die in de tool echt breekt: de test is dan xfail (strict) tot dat issue is opgelost.
    breekt: str | None = None

    def __call__(self) -> None:
        store.clear()
        try:
            self.toets()
        finally:
            store.clear()


RELATIES: list[Relatie] = []


def relatie(
    soort: str, tool: str, bron: str, breekt: str | None = None
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    """Registreer een relatie; `breekt="#<issue>"` als ze in de tool echt breekt (een apart issue, geen toolwijziging)."""

    def registreer(toets: Callable[[], None]) -> Callable[[], None]:
        RELATIES.append(Relatie(getattr(toets, "__name__", repr(toets)), soort, tool, bron, toets, breekt))
        return toets

    return registreer


def _som(waarden) -> float:
    """Som van de getallen; een lege (onderdrukte) waarde telt niet, zoals in de tools."""
    return sum(w for w in waarden if w is not None)


# --- Delen en totaal -------------------------------------------------------------------------------------------------


@relatie("Delen en totaal", "query_data", "duo")
def delen_en_totaal_duo() -> None:
    """Per jaar: de som over de sectoren (en over de leerwegen) = het totaal van dezelfde selectie zonder uitsplitsing."""
    h.duo_fixtures()
    selectie = {"INSTELLINGSCODE__in": ["90AA", "90CC", "90DD"]}
    totaal = h.per_periode(
        query_data(h.DUO_INSCHRIJVINGEN, filters=selectie, group_by=["STUDIEJAAR"], aggregate={h.AANTAL: "sum"}),
        "STUDIEJAAR",
        h.AANTAL,
    )
    assert set(totaal) == set(h.JAREN), totaal
    for kolom in ("ONDERWIJSSOORT", "LEERWEG"):
        delen = h.per_periode(
            query_data(
                h.DUO_INSCHRIJVINGEN, filters=selectie, group_by=["STUDIEJAAR", kolom], aggregate={h.AANTAL: "sum"}
            ),
            "STUDIEJAAR",
            h.AANTAL,
            sleutels=[kolom],
        )
        for jaar, n in totaal.items():
            som = _som(v for (j, _), v in delen.items() if j == jaar)
            assert som == n, f"{kolom} {jaar}: delen {som} ≠ totaal {n}"


@relatie("Delen en totaal", "query_data", "cbs")
def delen_en_totaal_cbs() -> None:
    """Per periode en onderwijssoort: mannen + vrouwen = de totaalcode van Geslacht (additief), uit dezelfde tabel."""
    h.cbs_fixtures()
    for soort in (h.HBO, h.WO, h.HO_TOTAAL):
        delen = h.per_periode(
            query_data(
                h.CBS_KEY,
                filters={"Onderwijssoort": soort, "Geslacht__in": [h.MANNEN, h.VROUWEN]},
                group_by=["Perioden", "Geslacht"],
                aggregate={h.CBS_WAARDE: "sum"},
            ),
            "Perioden",
            h.CBS_WAARDE,
            sleutels=["Geslacht"],
        )
        totaal = h.per_periode(
            query_data(
                h.CBS_KEY,
                filters={"Onderwijssoort": soort, "Geslacht": h.TOTAAL_GESLACHT},
                group_by=["Perioden"],
                aggregate={h.CBS_WAARDE: "sum"},
            ),
            "Perioden",
            h.CBS_WAARDE,
        )
        assert set(totaal) == set(h.CBS_PERIODEN), totaal
        for periode, n in totaal.items():
            som = _som(v for (p, _), v in delen.items() if p == periode)
            assert som == n, f"{soort} {periode}: mannen + vrouwen {som} ≠ totaal {n}"


# --- Sectoren en landelijk -------------------------------------------------------------------------------------------


@relatie("Sectoren en landelijk", "query_data", "duo")
def sectoren_en_landelijk_duo() -> None:
    """mbo (mbo-bestand) + hbo + wo (ho-bestand) = het landelijke bestand, per jaar: DUO telt additief over sectoren."""
    h.duo_fixtures()
    mbo = h.per_periode(
        query_data(h.DUO_MBO, group_by=["STUDIEJAAR"], aggregate={h.AANTAL: "sum"}), "STUDIEJAAR", h.AANTAL
    )
    ho = {
        sector: h.per_periode(
            query_data(
                h.DUO_HO, filters={"ONDERWIJSSOORT": sector}, group_by=["STUDIEJAAR"], aggregate={h.AANTAL: "sum"}
            ),
            "STUDIEJAAR",
            h.AANTAL,
        )
        for sector in ("hbo", "wo")
    }
    for jaar in h.JAREN:
        landelijk = h.getal(query_data(h.DUO_LANDELIJK, filters={"STUDIEJAAR": jaar}), h.AANTAL)
        som = mbo[jaar] + ho["hbo"][jaar] + ho["wo"][jaar]
        assert som == landelijk, f"{jaar}: mbo + hbo + wo {som} ≠ landelijk {landelijk}"


@relatie("Sectoren en landelijk", "query_data", "cbs")
def sectoren_niet_additief_cbs() -> None:
    """Een niet-additieve CBS-maat (cbs_meta.py: hbo + wo is meer dan het HO-totaal): geen gelijkheid, en de tools
    weigeren de som over de onderwijssoorten en over een %-kolom (optelbaar, #866) in plaats van hem te geven."""
    h.cbs_fixtures()
    geslacht_totaal = {"Geslacht": h.TOTAAL_GESLACHT}
    per_soort = {
        soort: h.per_periode(
            query_data(h.CBS_KEY, filters={**geslacht_totaal, "Onderwijssoort": soort}), "Perioden", h.CBS_WAARDE
        )
        for soort in (h.HBO, h.WO, h.HO_TOTAAL)
    }
    for periode in h.CBS_PERIODEN:
        som, totaal = per_soort[h.HBO][periode] + per_soort[h.WO][periode], per_soort[h.HO_TOTAAL][periode]
        assert som != totaal, f"{periode}: hbo + wo = HO-totaal; deze maat is niet additief, de fixture klopt niet"
        assert som > totaal, f"{periode}: hbo + wo {som} < HO-totaal {totaal}: dubbel ingeschrevenen tellen één keer"
    # Een som over de onderwijssoorten telt dubbel: de dimensiecontrole weigert (#162), er komt geen getal.
    som_over_soorten = query_data(
        h.CBS_KEY,
        filters={**geslacht_totaal, "Onderwijssoort__in": [h.HBO, h.WO]},
        group_by=["Perioden"],
        aggregate={h.CBS_WAARDE: "sum"},
    )
    assert "telt dubbel" in som_over_soorten and not som_over_soorten.startswith("{"), som_over_soorten[:300]
    # Een som over een percentage betekent niets: query_data en compute_kpi weigeren met de regel van optelbaar.
    fout = optelbaar.somfout(h.CBS_KEY, h.CBS_AANDEEL)
    assert fout, "optelbaar ziet de %-kolom niet"
    aandeel = query_data(
        h.CBS_KEY,
        filters={"Geslacht": h.TOTAAL_GESLACHT, "Onderwijssoort": h.HBO},
        group_by=["Perioden"],
        aggregate={h.CBS_AANDEEL: "sum"},
    )
    assert aandeel == fout, aandeel[:300]
    reeks = h.uit(query_data(h.CBS_KEY, filters={"Geslacht": h.TOTAAL_GESLACHT, "Onderwijssoort": h.HBO}))["data_key"]
    assert h.uit_fout(compute_kpi(reeks, h.CBS_AANDEEL, "sum", sort_column="Perioden")) == fout


# --- Reeks en los jaar -----------------------------------------------------------------------------------------------


@relatie("Reeks en los jaar", "query_data", "duo")
def reeks_en_los_jaar_duo() -> None:
    """Jaar n uit een reeks = dezelfde vraag voor alleen jaar n, ook in een andere schooljaarspelling (2022/23)."""
    h.duo_fixtures()
    for code in ("90AA", "90CC"):
        reeks = h.per_periode(
            query_data(
                h.DUO_INSCHRIJVINGEN,
                filters={"INSTELLINGSCODE": code},
                group_by=["STUDIEJAAR"],
                aggregate={h.AANTAL: "sum"},
            ),
            "STUDIEJAAR",
            h.AANTAL,
        )
        assert set(reeks) == set(h.JAREN), reeks
        for jaar in h.JAREN:
            for spelling in (jaar, f"{jaar}/{(jaar + 1) % 100:02d}"):
                los = query_data(
                    h.DUO_INSCHRIJVINGEN,
                    filters={"INSTELLINGSCODE": code, "STUDIEJAAR": spelling},
                    group_by=["STUDIEJAAR"],
                    aggregate={h.AANTAL: "sum"},
                )
                assert h.per_periode(los, "STUDIEJAAR", h.AANTAL) == {jaar: reeks[jaar]}, (code, spelling)


@relatie("Reeks en los jaar", "query_data", "cbs")
def reeks_en_los_jaar_cbs() -> None:
    """Periode n uit een CBS-reeks = dezelfde selectie op alleen periode n (code 2022SJ00 of spelling 2022/23)."""
    h.cbs_fixtures()
    selectie = {"Geslacht": h.TOTAAL_GESLACHT, "Onderwijssoort": h.HBO}
    reeks = h.per_periode(query_data(h.CBS_KEY, filters=selectie), "Perioden", h.CBS_WAARDE)
    assert set(reeks) == set(h.CBS_PERIODEN), reeks
    for jaar in h.JAREN:
        for spelling in (h.cbs_code(jaar), f"{jaar}/{(jaar + 1) % 100:02d}"):
            los = query_data(h.CBS_KEY, filters={**selectie, "Perioden": spelling})
            assert h.per_periode(los, "Perioden", h.CBS_WAARDE) == {h.cbs_code(jaar): reeks[h.cbs_code(jaar)]}, spelling


@relatie("Reeks en los jaar", "get_maat", "duo")
def reeks_en_los_jaar_maat() -> None:
    """get_maat: jaar n uit de reeks = get_maat met alleen schooljaar n."""
    with h.maat_bronnen():
        reeks = h.per_periode(
            get_maat("ingeschreven_personen_ho", "Hogeschool Utrecht"), "STUDIEJAAR", "AANTAL_INGESCHREVENEN"
        )
        assert set(reeks) == set(h.JAREN), reeks
        for jaar in h.JAREN:
            los = get_maat(
                "ingeschreven_personen_ho", "Hogeschool Utrecht", schooljaren=[f"{jaar}/{(jaar + 1) % 100:02d}"]
            )
            assert h.per_periode(los, "STUDIEJAAR", "AANTAL_INGESCHREVENEN") == {jaar: reeks[jaar]}, jaar


# --- Delen en totaal bij get_maat en koppel_data ---------------------------------------------------------------------


@relatie("Delen en totaal", "get_maat", "duo")
def delen_en_totaal_maat() -> None:
    """get_maat: voltijd + deeltijd + duaal = alle vormen, per jaar."""
    with h.maat_bronnen():
        alle = h.per_periode(get_maat("ingeschreven_personen_ho", "HU"), "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
        vormen = [
            h.per_periode(get_maat("ingeschreven_personen_ho", "HU", vorm=vorm), "STUDIEJAAR", "AANTAL_INGESCHREVENEN")
            for vorm in ("voltijd", "deeltijd", "duaal")
        ]
    assert set(alle) == set(h.JAREN), alle
    for jaar, n in alle.items():
        som = _som(vorm.get(jaar) for vorm in vormen)
        assert som == n, f"{jaar}: voltijd + deeltijd + duaal {som} ≠ alle vormen {n}"


@relatie("Delen en totaal", "koppel_data", "duo")
def delen_en_totaal_koppel() -> None:
    """Na koppel_data is de som van de DUO-kolom die van de DUO-tabel zelf: de outer join verliest en verdubbelt niets."""
    h.koppel_fixtures()
    with patch("data.instellingen.get_all", return_value=[]):
        gekoppeld = store.get(h.uit(koppel_data(h.SKDB_KEY, h.KOPPEL_DUO, ["croho"]))["data_key"])
    totaal = h.getal(
        query_data(h.KOPPEL_DUO, group_by=["INSTELLINGSCODE_ACTUEEL"], aggregate={h.AANTAL: "sum"}), h.AANTAL
    )
    assert gekoppeld[h.AANTAL].sum() == totaal, f"koppeling {gekoppeld[h.AANTAL].sum()} ≠ DUO-tabel {totaal}"


# --- Volgorde --------------------------------------------------------------------------------------------------------


def _duo_groepen(filters: dict | None = None) -> str:
    return query_data(
        h.DUO_INSCHRIJVINGEN, filters=filters, group_by=["STUDIEJAAR", "ONDERWIJSSOORT"], aggregate={h.AANTAL: "sum"}
    )


@relatie("Volgorde", "query_data", "duo")
def volgorde_duo() -> None:
    """Een andere rijvolgorde van de bron of van de filterwaarden geeft hetzelfde resultaat."""
    h.duo_fixtures()
    filters = {"INSTELLINGSCODE__in": ["90AA", "90CC", "90DD"], "LEERWEG__in": ["BOL", "VT"]}
    gewoon = h.rijen(_duo_groepen(filters))
    omgekeerd = {kolom: list(reversed(waarden)) for kolom, waarden in filters.items()}
    assert _duo_groepen(omgekeerd) == _duo_groepen(filters), "andere filtervolgorde, andere uitkomst"
    for seed in (1, 2, 3):
        store.clear()
        h.duo_fixtures(volgorde_seed=h.SEED + seed)
        assert h.rijen(_duo_groepen(filters)) == gewoon, f"andere rijvolgorde (seed {seed}), andere uitkomst"


def _cbs_groepen(geslachten: list[str]) -> str:
    return query_data(
        h.CBS_KEY,
        filters={"Onderwijssoort": h.WO, "Geslacht__in": geslachten},
        group_by=["Perioden", "Geslacht"],
        aggregate={h.CBS_WAARDE: "sum"},
    )


@relatie("Volgorde", "query_data", "cbs")
def volgorde_cbs() -> None:
    """Idem voor CBS: een geschudde tabel of omgekeerde filterwaarden geven dezelfde rijen."""
    h.cbs_fixtures()
    geslachten = [h.MANNEN, h.VROUWEN, h.TOTAAL_GESLACHT]
    gewoon = h.rijen(_cbs_groepen(geslachten))
    assert _cbs_groepen(list(reversed(geslachten))) == _cbs_groepen(geslachten), "andere filtervolgorde"
    for seed in (1, 2, 3):
        store.clear()
        h.cbs_fixtures(volgorde_seed=h.SEED + seed)
        assert h.rijen(_cbs_groepen(geslachten)) == gewoon, f"andere rijvolgorde (seed {seed}), andere uitkomst"


@relatie("Volgorde", "koppel_data", "duo")
def volgorde_koppel() -> None:
    """koppel_data op geschudde tabellen geeft dezelfde koppeling en dezelfde telling."""

    def koppeling(seed: int | None):
        store.clear()
        h.koppel_fixtures(volgorde_seed=seed)
        with patch("data.instellingen.get_all", return_value=[]):
            gekoppeld = h.uit(koppel_data(h.SKDB_KEY, h.KOPPEL_DUO, ["croho"]))
        df = store.get(gekoppeld["data_key"])
        return gekoppeld["telling"], df.sort_values(list(df.columns)).reset_index(drop=True)

    telling, df = koppeling(None)
    for seed in (1, 2):
        andere_telling, andere_df = koppeling(h.SEED + seed)
        assert andere_telling == telling, (seed, andere_telling, telling)
        assert andere_df.equals(df), f"andere rijvolgorde (seed {seed}), andere koppeling"


# --- Fusie (#728) ----------------------------------------------------------------------------------------------------


def _som_per_jaar(data_key: str, codes: list[str], kolom: str = h.AANTAL) -> dict:
    return h.per_periode(
        query_data(data_key, filters={"INSTELLINGSCODE__in": codes}, group_by=["STUDIEJAAR"], aggregate={kolom: "sum"}),
        "STUDIEJAAR",
        kolom,
    )


@relatie("Fusie", "query_data", "duo")
def fusie_duo_rekent_om() -> None:
    """DUO rekent een reeks om naar de huidige code: A + B vóór de fusie = de opvolger in de omgerekende publicatie.

    En de meerjarige selectie van de opvolger draagt de vaste fusieregel (#728), zodat het antwoord het zegt.
    """
    voor = h.fusie_fixtures()
    oud = _som_per_jaar(h.DUO_OUD, [h.VOORGANGER_A[0], h.VOORGANGER_B[0]])
    stap = Stap(h.VOORGANGER_A[0], h.VOORGANGER_A[1], "volledig", h.FUSIEDAG, via=h.OPVOLGER[0], wet="WEB")
    with patch.object(fusies, "_voorgangers", lambda code, sinds: (stap,) if code == h.OPVOLGER[0] else ()):
        uitkomst = query_data(
            h.DUO_NIEUW,
            filters={"INSTELLINGSCODE": h.OPVOLGER[0]},
            group_by=["STUDIEJAAR"],
            aggregate={h.AANTAL: "sum"},
        )
    nieuw = h.per_periode(uitkomst, "STUDIEJAAR", h.AANTAL)
    for jaar, (a, b) in voor.items():
        assert oud[jaar] == a + b, f"{jaar}: A + B uit de oude publicatie {oud[jaar]} ≠ {a + b}"
        assert nieuw[jaar] == oud[jaar], (
            f"{jaar}: opvolger na omrekening {nieuw[jaar]} ≠ A + B vóór de fusie {oud[jaar]}"
        )
    known = store.meta(h.uit(uitkomst)["data_key"])
    assert known is not None and len(known.fusies) == 1, known and known.fusies
    assert "DUO telt de jaren vóór de fusie (1 augustus 2023) bij de huidige instelling" in known.fusies[0]


@relatie("Fusie", "query_data", "duo-xbrl")
def fusie_xbrl_rekent_niet_om() -> None:
    """Een bron zonder omrekening (DUO's verantwoording uit XBRL, #935): vóór de fusie is de opvolger alleen zichzelf,
    A + B komt pas uit beide codes samen, en de vaste regel zegt dat de reeks niet is omgerekend."""
    voor = h.xbrl_fixtures()
    opvolger = _som_per_jaar(h.XBRL_REEKS, [h.OPVOLGER[0]], "BATEN")
    samen = _som_per_jaar(h.XBRL_REEKS, [h.VOORGANGER_A[0], h.OPVOLGER[0]], "BATEN")
    for jaar, (a, b) in voor.items():
        assert opvolger[jaar] == b and opvolger[jaar] != a + b, f"{jaar}: de opvolger telt de voorganger mee"
        assert samen[jaar] == a + b, f"{jaar}: voorganger + opvolger {samen[jaar]} ≠ {a + b}"
    stap = Stap("40295", "Stichting Oost", "volledig", "2023-01-01", via="30932", wet=None)
    with patch.object(fusies, "_voorgangers", lambda code, sinds: (stap,)):
        (regel,) = fusies.bestuur_in_reeks(30932, "Stichting Midden", (2021, 2024), {40295: ("Stichting Oost", 2022)})
    assert "rekent niet om" in regel and "tot en met verslagjaar 2022 staat Stichting Oost apart" in regel, regel


# --- Verschil --------------------------------------------------------------------------------------------------------


@relatie("Verschil", "compute_kpi", "duo")
def verschil_duo() -> None:
    """compute_kpi delta van jaar a tot b = waarde b - waarde a uit query_data, voor elk paar jaren."""
    h.duo_fixtures()
    reeks = h.uit(
        query_data(
            h.DUO_INSCHRIJVINGEN,
            filters={"INSTELLINGSCODE": "90DD"},
            group_by=["STUDIEJAAR"],
            aggregate={h.AANTAL: "sum"},
        )
    )["data_key"]
    for a, b in itertools.combinations(h.JAREN, 2):
        los = {
            jaar: h.getal(
                query_data(
                    h.DUO_INSCHRIJVINGEN,
                    filters={"INSTELLINGSCODE": "90DD", "STUDIEJAAR": jaar},
                    group_by=["STUDIEJAAR"],
                    aggregate={h.AANTAL: "sum"},
                ),
                h.AANTAL,
            )
            for jaar in (a, b)
        }
        delta = h.kpi(compute_kpi(reeks, h.AANTAL, "delta", sort_column="STUDIEJAAR", van=a, tot=b))
        assert delta == los[b] - los[a], f"delta {a}-{b}: {delta} ≠ {los[b]} - {los[a]}"


@relatie("Verschil", "compute_kpi", "cbs")
def verschil_cbs() -> None:
    """Idem op een CBS-reeks met vaste dimensies: delta = waarde b - waarde a."""
    h.cbs_fixtures()
    selectie = {"Geslacht": h.VROUWEN, "Onderwijssoort": h.WO}
    reeks = h.uit(query_data(h.CBS_KEY, filters=selectie))["data_key"]
    for a, b in itertools.combinations(h.JAREN, 2):
        los = {
            jaar: h.getal(query_data(h.CBS_KEY, filters={**selectie, "Perioden": h.cbs_code(jaar)}), h.CBS_WAARDE)
            for jaar in (a, b)
        }
        delta = h.kpi(compute_kpi(reeks, h.CBS_WAARDE, "delta", sort_column="Perioden", van=a, tot=b))
        assert delta == los[b] - los[a], f"delta {a}-{b}: {delta} ≠ {los[b]} - {los[a]}"


# --- Onderdrukte cel -------------------------------------------------------------------------------------------------


def _ondergrens(uitkomst: dict, kolom: str, bron: str, rij: dict) -> None:
    """De rij draagt het label van de tool en de noot noemt het totaal een ondergrens, in de woorden uit de code."""
    label = f"{kolom}{query._ONDERDRUKT}"
    assert rij.get(label) == 1, f"de rij mist het label '{label}': {rij}"
    (noot,) = duo.sentinel_notes({kolom: 1}, bron)
    assert "ondergrens" in noot and noot in uitkomst.get("databewerking", []), uitkomst.get("databewerking")


@relatie("Onderdrukte cel", "query_data", "duo")
def onderdrukt_duo() -> None:
    """Met een onderdrukte cel (-1) is de som van de delen een ondergrens: som <= totaal, nooit gelijk, met het label;
    in een jaar zonder onderdrukte cel blijft het gelijk en zonder label."""
    h.duo_onderdrukt_fixtures()
    uitkomst = h.uit(query_data(h.DUO_ONDERDRUKT, group_by=["STUDIEJAAR"], aggregate={h.AANTAL: "sum"}))
    per_jaar = {rij["STUDIEJAAR"]: rij for rij in uitkomst["rijen"]}
    for jaar, rij in per_jaar.items():
        totaal = h.getal(query_data(h.DUO_ONDERDRUKT_LANDELIJK, filters={"STUDIEJAAR": jaar}), h.AANTAL)
        som = rij[h.AANTAL]
        assert som is not None and som >= 0, f"{jaar}: som {som}: een onderdrukte cel telde als getal"
        if jaar == 2024:
            assert som <= totaal and som != totaal, f"{jaar}: som {som} is geen ondergrens van totaal {totaal}"
            _ondergrens(uitkomst, h.AANTAL, "duo", rij)
        else:
            assert som == totaal and f"{h.AANTAL}{query._ONDERDRUKT}" not in rij, (jaar, rij, totaal)
    # De onderdrukte cel zelf is leeg, geen -1 en geen 0.
    cel = h.per_periode(
        query_data(h.DUO_ONDERDRUKT, filters={"STUDIEJAAR": 2024, "ONDERWIJSSOORT": "wo"}), "STUDIEJAAR", h.AANTAL
    )
    assert cel == {2024: None}, cel


@relatie("Onderdrukte cel", "query_data", "cbs")
def onderdrukt_cbs() -> None:
    """Een lege CBS-cel ('.') bij een deel: mannen + vrouwen <= totaal, nooit gelijk, met het label bij die groep."""
    h.cbs_onderdrukt_fixtures()
    tekst = query_data(
        h.CBS_ONDERDRUKT,
        filters={"Geslacht__in": [h.MANNEN, h.VROUWEN]},
        group_by=["Perioden", "Geslacht"],
        aggregate={h.CBS_WAARDE: "sum"},
    )
    uitkomst = h.uit(tekst)
    delen = h.per_periode(tekst, "Perioden", h.CBS_WAARDE, sleutels=["Geslacht"])
    totaal = h.per_periode(
        query_data(h.CBS_ONDERDRUKT, filters={"Geslacht": h.TOTAAL_GESLACHT}), "Perioden", h.CBS_WAARDE
    )
    for jaar in h.JAREN:
        periode = h.cbs_code(jaar)
        som = _som(v for (p, _), v in delen.items() if p == periode)
        if jaar == 2024:
            assert som <= totaal[periode] and som != totaal[periode], f"{periode}: {som} geen ondergrens"
            rij = next(r for r in uitkomst["rijen"] if r["Perioden"] == periode and r["Geslacht"] == h.VROUWEN)
            assert rij[h.CBS_WAARDE] is None, rij
            _ondergrens(uitkomst, h.CBS_WAARDE, "cbs", rij)
        else:
            assert som == totaal[periode], f"{periode}: {som} ≠ {totaal[periode]}"
