"""Arbeidsmarkt na mbo/hbo/wo in de chat: UWV-vacatures en ROA-schoolverlatersinformatie (#441).

UWV is per provincie of gemeente, ROA landelijk of per arbeidsmarktregio of provincie; geen van
beide is per instelling. De data komt uit `data/arbeidsmarkt.py` (gedeeld met de dashboards,
CH-23) en elke aanroep loopt langs dezelfde scopepoort als CBS, DUO en RIO (`scope_blokkade`, CH-37). Elk getal komt uit de
bron, met de peildatum of versie uit de data zelf: tot CH-37 gaf get_roa_benchmark vaste,
in de code geschreven waarden ("~80%") als ROA-cijfers door.

Een arbeidsmarktresultaat is een dataset (#577): de tabel achter het resultaat staat in de store
onder een `data_key`, met de laadaanroep en de peildatum of versie in haar KeyMeta. Zo lopen
rapport en dashboard (`build_dataset_context`), het recept na een herstart (#472), de bronnenlijst,
de citaties, de snippet en de CSV-export vanzelf mee; tot #577 bestonden UWV en ROA voor het
rapport niet en schreef het model dat er geen vacaturegegevens waren.
"""

import json
import re

import pandas as pd

from data import arbeidsmarkt

from . import fouten, store
from .catalog import catalogus_titel, scope_blokkade
from .schemas import TOOL_GET_ROA_BENCHMARK, TOOL_GET_UWV_VACATURES

UWV_ID = "uwv-open-match-data"
ROA_ID = "ais2030"
# De vaste dataset en bron achter elke arbeidsmarkttool: de aanroep noemt geen dataset-ID (#577).
DATASET = {TOOL_GET_UWV_VACATURES: UWV_ID, TOOL_GET_ROA_BENCHMARK: ROA_ID}
_BRON = {TOOL_GET_UWV_VACATURES: "uwv", TOOL_GET_ROA_BENCHMARK: "roa"}
# De onderdelen van een ROA-resultaat, met hun naam voor de tabel en de citaties.
ROA_ONDERDELEN = {"schoolverlaters_sis_2024": "Schoolverlaters (SIS 2024)", "prognose_tot_2030": "Prognose tot 2030"}
_ROA_KOLOMMEN = ["ONDERDEEL", "REGIO", "OPLEIDING", "INDICATOR", "PERCENTAGE", "AANTAL", "TYPERING"]
# Zoveel beroepenclusters in het resultaat; het totaal staat er altijd bij.
_MAX_CLUSTERS = 15
# De niveaukolommen zijn bij vacatures leeg; zonder deze regel las het model chauffeursbanen als hbo-vraag (#449).
_OPLEIDINGSNIVEAU = (
    "onbekend: UWV legt bij vacatures geen opleidingsniveau vast. Een sector telt ook banen op een ander "
    "niveau mee (bijv. chauffeurs bij TECHNIEK); het is geen vraag naar mbo-, hbo- of wo-gediplomeerden."
)
_TELLING_SECTOR = (
    "Een cluster dat {sector} deelt met andere sectoren van dezelfde indeling (hbo/wo of mbo) telt naar rato "
    "mee, bij twee sectoren voor de helft, naar beneden afgerond. Zo tellen de sectoren samen nooit op tot meer "
    "dan het totaal; de clustergetallen zelf zijn ongewogen. Lokale weging, geen UWV-cijfer."
)
_TELLING_ONGEDEELD = (
    "De som van de clusters die de lokale classificatie aan {sector} toewijst; geen van die clusters hoort ook "
    "bij een andere sector van dezelfde indeling. Lokale telling, geen UWV-cijfer."
)
# #460: zonder aparte lagen schreef het model de sectortoewijzing en de weging aan UWV toe.
_BRONCIJFER = (
    "Ongewogen aantallen vacatures, zoals UWV ze publiceert: totaal_vacatures over alle beroepenclusters en "
    "het aantal per cluster."
)
_TOEWIJZING = (
    "Welke beroepenclusters bij een onderwijssector horen, is een indeling van deze app, gemaakt met een "
    "taalmodel; niet van UWV."
)


def _json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _slug(tekst: str) -> str:
    """Een naam als deel van een data_key: "Noord-Holland" en "noord-holland" zijn dezelfde selectie."""
    return re.sub(r"[^a-z0-9]+", "-", tekst.lower()).strip("-")


def peilmoment(tool: str) -> str | None:
    """Wanneer de momentopname achter een arbeidsmarkttool is genomen, in de woorden van de bron (#577):
    de peildatum van UWV, de versie van ROA. None voor een andere tool."""
    if tool == TOOL_GET_UWV_VACATURES:
        return f"peildatum {arbeidsmarkt.uwv_peildatum()}"
    if tool == TOOL_GET_ROA_BENCHMARK:
        return f"versie {arbeidsmarkt.roa_versie()}"
    return None


def _bewaar(key: str, tabel: pd.DataFrame, tool: str, args: dict, peilmoment: str) -> None:
    """De tabel achter een resultaat in de store, met haar laadaanroep en peilmoment (#577)."""
    meta = store.KeyMeta(bron=_BRON[tool], dataset=DATASET[tool], laad=(tool, args), peilmoment=peilmoment)
    store.put(key, tabel, meta)


def _uwv_tabel(stand: arbeidsmarkt.UwvStand) -> pd.DataFrame:
    """Alle beroepenclusters van de plaats, aflopend, met de plaats als kolom: de rijen zeggen zelf waar ze over gaan."""
    plaats = {"PROVINCIE": stand.provincie, **({"GEMEENTE": stand.gemeente} if stand.gemeente else {})}
    return pd.DataFrame([{**plaats, "BEROEPENCLUSTER": c, "VACATURES": n} for c, n in stand.clusters.items()])


def _roa_tabel(onderdelen: dict) -> pd.DataFrame:
    """Elk ROA-cijfer als rij: onderdeel, de regio van dat onderdeel (een landelijke terugval heet landelijk),
    opleiding, indicator en de waarde als percentage, aantal of typering."""
    herkomst = onderdelen.get("herkomst") or {}
    rijen = [
        {
            "ONDERDEEL": naam,
            "REGIO": herkomst.get(sleutel) or onderdelen["regio"],
            "OPLEIDING": opleiding,
            "INDICATOR": indicator,
            "PERCENTAGE": waarden.get("perc"),
            "AANTAL": waarden.get("aantal"),
            "TYPERING": waarden.get("typering"),
        }
        for sleutel, naam in ROA_ONDERDELEN.items()
        for opleiding, indicatoren in (onderdelen.get(sleutel) or {}).items()
        for indicator, waarden in indicatoren.items()
    ]
    return pd.DataFrame(rijen, columns=_ROA_KOLOMMEN)


def _grootste_clusters(clusters: dict[str, int], soort: str = "beroepenclusters") -> dict:
    """De grootste clusters (de invoer is aflopend), met een melding als er meer zijn."""
    uit: dict = {"clusters": dict(list(clusters.items())[:_MAX_CLUSTERS])}
    if len(clusters) > _MAX_CLUSTERS:
        uit["clusters_getoond"] = f"de {_MAX_CLUSTERS} grootste van {len(clusters)} {soort}"
    return uit


def _sectordeel(clusters: dict[str, int], totaal: int, sector: str) -> dict:
    """De sector in drie lagen (#460): de UWV-aantallen, onze clustertoewijzing en onze weging."""
    deel = arbeidsmarkt.sector_vacatures(clusters, sector)
    # Het aantal clusters is onze selectie voor de sector, geen UWV-telling.
    getoond = _grootste_clusters(deel.clusters, f"beroepenclusters die de lokale classificatie aan {sector} toewijst")
    telling = _TELLING_SECTOR if deel.gedeeld else _TELLING_ONGEDEELD
    gewogen: dict = {"vacatures_sector": deel.totaal, "telling_sector": telling.format(sector=sector)}
    if gedeeld := {c: deel.gedeeld[c] for c in getoond["clusters"] if c in deel.gedeeld}:
        gewogen["gedeelde_clusters"] = gedeeld
    classificatie = {"sector": sector, "clusters": list(getoond["clusters"]), "toewijzing": _TOEWIJZING}
    return {
        "uwv_broncijfer": {"toelichting": _BRONCIJFER, "totaal_vacatures": totaal} | getoond,
        "lokale_classificatie": classificatie | arbeidsmarkt.SECTOR_MANIFEST,
        "gewogen_aandeel": gewogen,
    }


def _geen_vacatures(provincie: str, gemeente: str | None) -> str:
    if gemeente and (gemeenten := arbeidsmarkt.gemeenten(provincie)):
        return f"Geen UWV-vacatures voor gemeente '{gemeente}' in {provincie}. Gemeenten: {gemeenten}."
    return f"Geen UWV-vacatures voor provincie '{provincie}'. Provincies: {arbeidsmarkt.provincies()}."


def get_uwv_vacatures(provincie: str, sector: str | None = None, gemeente: str | None = None) -> str:
    if blokkade := scope_blokkade(UWV_ID):
        return blokkade
    if sector and sector not in arbeidsmarkt.SECTOR_CLUSTER_MAP:
        return f"Sector '{sector}' is onbekend. Kies een van: {sorted(arbeidsmarkt.SECTOR_CLUSTER_MAP)}."
    try:
        stand = arbeidsmarkt.uwv_stand(provincie, gemeente)
        if stand is None:
            return _geen_vacatures(provincie, gemeente)
    except Exception as e:
        return fouten.bronfout("UWV", e)

    # Sector is een zicht op dezelfde tabel, geen andere selectie: één key per plaats, in de spelling van de bron.
    args = {"provincie": stand.provincie, **({"gemeente": stand.gemeente} if stand.gemeente else {})}
    key = ":".join(["uwv", _slug(stand.provincie), *([_slug(stand.gemeente)] if stand.gemeente else [])])
    _bewaar(key, _uwv_tabel(stand), TOOL_GET_UWV_VACATURES, args, f"peildatum {stand.peildatum}")
    result = {
        "bron": catalogus_titel(UWV_ID),
        "dataset": UWV_ID,
        "data_key": key,
        "peildatum": stand.peildatum,
        "momentopname": "Vacatures op de peildatum; geen actuele stand en geen reeks.",
        "provincie": stand.provincie,
        **({"gemeente": stand.gemeente} if stand.gemeente else {}),
        "totaal_vacatures": stand.totaal,
        "opleidingsniveau": _OPLEIDINGSNIVEAU,
    }
    result |= _sectordeel(stand.clusters, stand.totaal, sector) if sector else _grootste_clusters(stand.clusters)
    return _json(result)


def _roa_onderdelen(niveaus: tuple[str, ...], per_sector: bool, regio: str) -> dict:
    """Schoolverlaters en prognose voor de regio; een onderdeel zonder regionale cijfers is landelijk.

    Regionaal heeft ROA alleen de prognose (#450). Welke regio elk onderdeel draagt staat in
    `herkomst`, zodat een landelijk cijfer niet als regionaal wordt gelezen.
    """
    ophalen = {
        "schoolverlaters_sis_2024": arbeidsmarkt.roa_schoolverlaters,
        "prognose_tot_2030": arbeidsmarkt.roa_prognose,
    }
    landelijk = arbeidsmarkt.ROA_LANDELIJK
    if regio == landelijk:
        return {"regio": landelijk} | {k: f(niveaus, per_sector) for k, f in ophalen.items()}

    uit: dict = {"regio": regio, "regiotype": arbeidsmarkt.roa_regiotype(regio), "herkomst": {}}
    for onderdeel, f in ophalen.items():
        waarden = f(niveaus, per_sector, regio)
        uit[onderdeel] = waarden or f(niveaus, per_sector, landelijk)
        uit["herkomst"][onderdeel] = regio if waarden else landelijk
    if terugval := [k for k, r in uit["herkomst"].items() if r == landelijk]:
        uit["terugval"] = f"ROA heeft voor {regio} geen {' en '.join(terugval)}; daar staan de landelijke cijfers."
    return uit


def get_roa_benchmark(sector: str | None = None, regio: str | None = None) -> str:
    if blokkade := scope_blokkade(ROA_ID):
        return blokkade
    try:
        if sector:
            if sector not in (sectoren := arbeidsmarkt.roa_sectoren()):
                return f"ROA-opleidingssector '{sector}' is onbekend. Kies een van: {sectoren}."
            niveaus, per_sector = (sector,), True
        else:
            niveaus, per_sector = tuple(n for ns in arbeidsmarkt.ROA_NIVEAUS.values() for n in ns), False
        regionaam = arbeidsmarkt.roa_regio(regio) if regio else arbeidsmarkt.ROA_LANDELIJK
        if regionaam is None:
            return f"ROA-regio '{regio}' is onbekend. Kies een arbeidsmarktregio of provincie: {arbeidsmarkt.roa_regios()}."
        onderdelen = _roa_onderdelen(niveaus, per_sector, regionaam)
        versie = arbeidsmarkt.roa_versie()
    except Exception as e:
        return fouten.bronfout("ROA", e)
    args = {k: v for k, v in (("sector", sector), ("regio", regio)) if v}
    key = ":".join(["roa", _slug(regionaam), *([_slug(sector)] if sector else [])])
    _bewaar(key, _roa_tabel(onderdelen), TOOL_GET_ROA_BENCHMARK, args, f"versie {versie}")
    return _json(
        {"bron": f"ROA, {catalogus_titel(ROA_ID)}", "dataset": ROA_ID, "data_key": key, "versie": versie, **onderdelen}
    )
