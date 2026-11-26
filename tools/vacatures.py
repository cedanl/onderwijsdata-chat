"""Actuele vacatures in de chat uit CBS (#1226, #1227; besluit #1221): de opvolger van UWV Open Match.

- `get_vacatures`: de openstaande vacatures per provincie en SBI-sectie uit CBS 83599NED (data/vacatures_cbs.py, de
  lader van de dashboards): het laatste kwartaal en het gemiddelde van de laatste vier kwartalen, elk met periode en
  status (voorlopig of definitief). Een stand op de laatste dag van het kwartaal, bij de bedrijfstak van de werkgever.
- `get_ontstane_vacatures`: de ontstane vacatures per jaar en beroep (BRC 2014) uit CBS 85081NED
  (data/vacatures_ontstaan.py), alleen landelijk. Een stroom over het jaar, geen stand.

Beide resultaten zijn een dataset zoals UWV en ROA (#577): de tabel staat in de store onder een `data_key`, met de
laadaanroep en het peilmoment in haar KeyMeta. Zo lopen bronnenlijst, citaties, snippet, herlaad en CSV-export mee.
Een lege cel is "geen gegevens" (None), nooit 0. Elke aanroep loopt langs de scopepoort (`scope_blokkade`): beide
tabellen zijn de arbeidsmarktkant van het chatprofiel (tools/scopeprofiel.py).

CBS heeft 83599NED tot provincie, niet per gemeente of arbeidsmarktregio. Een gemeente, plaats of regio krijgt de
provincie waarin ze ligt, met die melding erbij (`plaatsniveau`); de ligging komt uit de CBS-indelingen van de app
(data/woonplaatsen.py voor gemeente en woonplaats, data/arbeidsmarktregio.py voor de regio), niet uit het model.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pandas as pd

from data import arbeidsmarktregio, vacatures_cbs, vacatures_ontstaan, woonplaatsen

from . import fouten, store
from .catalog import scope_blokkade
from .schemas import TOOL_GET_ONTSTANE_VACATURES, TOOL_GET_VACATURES

# De vaste dataset achter elke vacaturetool: de aanroep noemt geen dataset-ID (#577).
DATASET = {TOOL_GET_VACATURES: vacatures_cbs.DATASET, TOOL_GET_ONTSTANE_VACATURES: vacatures_ontstaan.DATASET}
LAATSTE_KWARTAAL = "laatste kwartaal"
GEMIDDELDE = f"gemiddelde van {vacatures_cbs.GEMIDDELD_OVER} kwartalen"
NIVEAUS = (vacatures_ontstaan.SEGMENT, vacatures_ontstaan.KLASSE)
_VOORLOPIG, _DEFINITIEF = "Voorlopig", "Definitief"  # zoals CBS de Periodestatus schrijft
_VACATURE_KOLOMMEN = ["PROVINCIE", "SECTIE", "MAAT", "Perioden", "Periodestatus", "VACATURES"]
_ONTSTAAN_KOLOMMEN = ["BEROEP", "NIVEAU", "KLASSE", "Perioden", "Periodestatus", "ONTSTANE_VACATURES"]
_GEEN_GEGEVENS = "Een waarde null is bij CBS 'geen gegevens' (een lege cel): noem er geen getal voor, ook geen 0."
_VOORLOPIG_TEKST = "Voorlopige cijfers kan CBS nog herzien: noem ze voorlopig."
_TELLING_STAND = (
    "Openstaande vacatures op de laatste dag van het kwartaal (een stand, geen stroom), bij de bedrijfstak van de "
    "werkgever: niet naar beroep of opleidingsniveau. CBS publiceert ze in duizendtallen; hier staan ze als aantal."
)
_TELLING_STROOM = (
    "Ontstane vacatures: alle vacatures die in het jaar ontstonden (de som van vier kwartalen), een stroom en geen "
    "stand; niet te vergelijken met de openstaande vacatures van get_vacatures (83599NED). Landelijk, alle "
    "bedrijfstakken samen. CBS publiceert ze in de eenheid '{eenheid}'; hier staan ze als aantal."
)
_LANDELIJK = "Alleen landelijk: CBS heeft de ontstane vacatures per beroep niet per provincie, regio of gemeente."
_TOT_PROVINCIE = "De actuele vacatures van CBS (83599NED) gaan tot provincie, niet tot gemeente of arbeidsmarktregio."
# Spellingen van gemeenten die de CBS-indeling anders schrijft.
_GEMEENTE_ALIAS = {"den haag": "'s-gravenhage", "den bosch": "'s-hertogenbosch"}


def _json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _slug(tekst: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tekst.lower()).strip("-")


def _bewaar(key: str, tabel: pd.DataFrame, tool: str, args: dict, peilmoment: str) -> None:
    """De tabel achter een resultaat in de store, met haar laadaanroep en peilmoment (#577)."""
    meta = store.KeyMeta(
        bron="cbs", dataset=DATASET[tool], laad=(tool, args), peilmoment=peilmoment, periodekolom="Perioden"
    )
    store.put(key, tabel, meta)


def _bron(dataset: str, titel: str, link: str, licentie: str) -> dict:
    return {"naam": "CBS", "titel": titel, "dataset": dataset, "link": link, "licentie": licentie}


def _periodestatus(voorlopig: bool) -> str:
    return _VOORLOPIG if voorlopig else _DEFINITIEF


def peilmoment(tool: str) -> str | None:
    """Welke periode de tabel achter een vacaturetool dekt, voor een bronregel zonder lading (#577); None bij een
    andere tool of als de bron nu niet antwoordt."""
    try:
        if tool == TOOL_GET_VACATURES:
            return f"{LAATSTE_KWARTAAL} {vacatures_cbs.laatste_periode().titel}"
        if tool == TOOL_GET_ONTSTANE_VACATURES:
            return _jarentekst(vacatures_ontstaan.jaren())
    except Exception:  # een bronregel zonder peilmoment is beter dan geen bronregel
        return None
    return None


# --- get_vacatures: openstaande vacatures per provincie (83599NED) -------------------------------------------------


def _naam(tekst: str) -> str:
    sleutel = " ".join(str(tekst).split()).casefold().removeprefix("gemeente ").removeprefix("provincie ")
    return _GEMEENTE_ALIAS.get(sleutel, sleutel)


def _provincies_van_gemeenten(codes: list[str]) -> Counter:
    """Per provincie (CBS-regiocode, PV25) hoeveel van deze gemeenten erin liggen."""
    indeling = woonplaatsen.gemeenten()
    return Counter(indeling[c]["provincie"] for c in codes if c in indeling)


def _ligging(naam: str) -> tuple[str, Counter] | None:
    """Wat `naam` is (gemeente, woonplaats of arbeidsmarktregio) en in welke provincies die ligt; None als onbekend."""
    gezocht = _naam(naam)
    gemeenten = [c for c, g in woonplaatsen.gemeenten().items() if _naam(g["naam"]) == gezocht]
    if gemeenten:
        return "gemeente", _provincies_van_gemeenten(gemeenten)
    plaatsen = [c for plaats, codes in woonplaatsen.woonplaatsen().items() if _naam(plaats) == gezocht for c in codes]
    if plaatsen:
        return "plaats", _provincies_van_gemeenten(plaatsen)
    regio = [c for c, r in arbeidsmarktregio.gemeenten().items() if _naam(r) == gezocht]
    if regio:
        return "arbeidsmarktregio", _provincies_van_gemeenten(regio)
    return None


def _hoofdletter(tekst: str) -> str:
    """Alleen de eerste letter groot: "arbeidsmarktregio Rijk van Nijmegen" → "Arbeidsmarktregio Rijk van Nijmegen"."""
    return tekst[:1].upper() + tekst[1:]


def _soortnaam(soort: str, naam: str) -> str:
    return f"{soort} {naam}" if soort != "plaats" else naam


def _provincie_bij_plaats(naam: str, soort_gevraagd: str | None) -> tuple[str | None, str]:
    """De provincie bij een gemeente, plaats of regio, met de melding voor `plaatsniveau`; zonder unieke provincie
    (None) een melding die de provincies aanbiedt."""
    ligging = _ligging(naam)
    if ligging is None:
        soort = soort_gevraagd or "plaats"
        return None, f"{_TOT_PROVINCIE} {_hoofdletter(soort)} '{naam}' is in de CBS-indeling niet gevonden."
    soort, provincies = ligging
    namen = [(vacatures_cbs.provincie_bij_code(code), n) for code, n in provincies.most_common()]
    namen = [(p, n) for p, n in namen if p]
    if not namen:
        return None, f"{_TOT_PROVINCIE} Bij {_soortnaam(soort, naam)} is geen provincie gevonden."
    (eerste, aantal), *rest = namen
    if rest and rest[0][1] == aantal:
        # Even veel gemeenten in twee provincies: geen keuze van de app.
        opties = " of ".join(p for p, n in namen if n == aantal)
        return None, f"{_TOT_PROVINCIE} {_hoofdletter(_soortnaam(soort, naam))} ligt in {opties}: kies een provincie."
    ligt = f"ligt grotendeels in {eerste} (ook in {', '.join(p for p, _ in rest)})" if rest else f"ligt in {eerste}"
    return eerste, (
        f"{_TOT_PROVINCIE} {_hoofdletter(_soortnaam(soort, naam))} {ligt}: dit zijn de cijfers voor de hele provincie "
        f"{eerste}, niet voor {_soortnaam(soort, naam)}."
    )


def _plaats(provincie: str | None, gemeente: str | None, regio: str | None) -> tuple[str | None, str | None]:
    """De provincie voor de tool en de melding over het plaatsniveau; (None, melding) als er geen provincie is."""
    fijner = [(n, s) for n, s in ((gemeente, "gemeente"), (regio, "arbeidsmarktregio")) if n]
    if provincie and (stand := vacatures_cbs.stand(provincie)) is not None:
        if not fijner:
            return provincie, None
        naam, soort = fijner[0]
        return provincie, (
            f"{_TOT_PROVINCIE} Voor {soort} {naam} zijn er geen eigen cijfers: dit zijn de cijfers voor de hele "
            f"provincie {stand.provincie}."
        )
    # Een gemeente of regio, of een plaatsnaam in het veld provincie ("Arnhem").
    for naam, soort in [*fijner, *([(provincie, None)] if provincie else [])]:
        gevonden, melding = _provincie_bij_plaats(naam, soort)
        if gevonden or soort:
            return gevonden, melding
    if provincie:
        return None, f"Provincie '{provincie}' is onbekend. {_TOT_PROVINCIE}"
    return None, f"Noem een provincie. {_TOT_PROVINCIE}"


def _sectie(stand: vacatures_cbs.Provinciestand, sectie: str) -> vacatures_cbs.Sectie | None:
    gezocht = " ".join(sectie.split()).casefold()
    for kandidaat in (stand.totaal, *stand.secties):
        if gezocht in (kandidaat.code.casefold(), kandidaat.naam.casefold(), kandidaat.label.casefold()):
            return kandidaat
    return None


def _vacaturerijen(stand: vacatures_cbs.Provinciestand, secties: list[vacatures_cbs.Sectie]) -> list[dict]:
    """Per sectie twee rijen: het laatste kwartaal en het gemiddelde, met periode, status en aantal (None: geen
    gegevens)."""
    rijen = []
    for sectie in secties:
        for maat, waarde in ((LAATSTE_KWARTAAL, sectie.laatste), (GEMIDDELDE, sectie.gemiddelde)):
            rijen.append(
                {
                    "PROVINCIE": stand.provincie,
                    "SECTIE": sectie.label,
                    "MAAT": maat,
                    "Perioden": vacatures_cbs.periodetekst(waarde.perioden),
                    "Periodestatus": _periodestatus(waarde.voorlopig) if waarde.perioden else None,
                    "VACATURES": waarde.vacatures,
                }
            )
    return rijen


def vacaturetabel(rijen: list[dict]) -> pd.DataFrame:
    """De tabel in de store: de rijen van het resultaat, met de aantallen als geheel getal met lege cellen."""
    tabel = pd.DataFrame(rijen, columns=_VACATURE_KOLOMMEN)
    tabel["VACATURES"] = tabel["VACATURES"].astype("Int64")
    return tabel


def get_vacatures(
    provincie: str | None = None, sectie: str | None = None, gemeente: str | None = None, regio: str | None = None
) -> str:
    if blokkade := scope_blokkade(vacatures_cbs.DATASET):
        return blokkade
    try:
        gekozen, plaatsniveau = _plaats(provincie, gemeente, regio)
        if gekozen is None:
            return f"{plaatsniveau} Kies een provincie: {vacatures_cbs.provincies()}."
        stand = vacatures_cbs.stand(gekozen)
    except Exception as e:
        return fouten.bronfout("CBS", e)
    if stand is None:  # de plaatsindeling noemde een provincie die 83599NED niet kent
        return f"{_TOT_PROVINCIE} Provincie '{gekozen}' staat niet in de tabel. Kies een van: {vacatures_cbs.provincies()}."
    gevonden = _sectie(stand, sectie) if sectie else None
    if sectie and gevonden is None:
        return f"SBI-sectie '{sectie}' is onbekend. Kies een van: {[s.label for s in stand.secties]}."
    # Het totaal staat er altijd bij, zodat een sectie een deel van iets is; zonder sectie alle secties.
    hoofd = gevonden or stand.totaal
    if gevonden is None:
        secties = [stand.totaal, *stand.secties]
    else:
        secties = [stand.totaal] if gevonden is stand.totaal else [stand.totaal, gevonden]

    args = {"provincie": stand.provincie, **({"sectie": gevonden.code} if gevonden else {})}
    key = ":".join(
        [
            "cbs",
            vacatures_cbs.DATASET,
            "vacatures",
            _slug(stand.provincie),
            *([_slug(gevonden.code)] if gevonden else []),
        ]
    )
    rijen = _vacaturerijen(stand, secties)
    _bewaar(key, vacaturetabel(rijen), TOOL_GET_VACATURES, args, f"{LAATSTE_KWARTAAL} {stand.laatste.titel}")
    voorlopig = any(w.voorlopig for s in secties for w in (s.laatste, s.gemiddelde))
    result = {
        "bron": _bron(vacatures_cbs.DATASET, vacatures_cbs.TITEL, vacatures_cbs.STATLINE_URL, vacatures_cbs.LICENTIE),
        "dataset": vacatures_cbs.DATASET,
        "data_key": key,
        "provincie": stand.provincie,
        **({"plaatsniveau": plaatsniveau} if plaatsniveau else {}),
        "sectie": hoofd.label,
        "laatste_kwartaal": hoofd.laatste.als_dict(),
        "gemiddelde": {"kwartalen": vacatures_cbs.GEMIDDELD_OVER, **hoofd.gemiddelde.als_dict()},
        "telling": _TELLING_STAND,
        "geen_gegevens": _GEEN_GEGEVENS,
        **({"voorlopig": _VOORLOPIG_TEKST} if voorlopig else {}),
        "rijen": rijen,
    }
    return _json(result)


# --- get_ontstane_vacatures: ontstane vacatures per beroep (85081NED) ----------------------------------------------


def _jarentekst(jaren: tuple[vacatures_ontstaan.Jaar, ...]) -> str:
    if not jaren:
        return "geen jaren"
    return f"jaren {jaren[0].titel} t/m {jaren[-1].titel}" if len(jaren) > 1 else f"jaar {jaren[0].titel}"


def _selectie(beroep: vacatures_ontstaan.Beroep | None, niveau: str) -> list[vacatures_ontstaan.Beroep]:
    """Het totaal, en dan het gevraagde beroep (een klasse met haar segmenten, tenzij `niveau` klasse is) of alle
    beroepen op `niveau`."""
    totaal = vacatures_ontstaan.totaal()
    if beroep is None:
        return [totaal, *vacatures_ontstaan.beroepen(niveau)]
    if beroep.niveau == vacatures_ontstaan.KLASSE and niveau == vacatures_ontstaan.SEGMENT:
        return [totaal, beroep, *vacatures_ontstaan.segmenten(beroep)]
    return [totaal, beroep]


def _klasselabel(beroep: vacatures_ontstaan.Beroep) -> str | None:
    if beroep.niveau != vacatures_ontstaan.SEGMENT:
        return None
    klasse = vacatures_ontstaan.klasse_van(beroep)
    return klasse.label if klasse else None


def ontstaantabel(beroepen: list[vacatures_ontstaan.Beroep]) -> pd.DataFrame:
    """De tabel in de store: per beroep en jaar één rij, met de status van het jaar en het aantal (leeg: geen
    gegevens)."""
    rijen = [
        {
            "BEROEP": beroep.label,
            "NIVEAU": beroep.niveau,
            "KLASSE": _klasselabel(beroep),
            "Perioden": waarde.jaar.titel,
            "Periodestatus": _periodestatus(waarde.jaar.voorlopig),
            "ONTSTANE_VACATURES": waarde.vacatures,
        }
        for beroep in beroepen
        for waarde in vacatures_ontstaan.waarden(beroep)
    ]
    tabel = pd.DataFrame(rijen, columns=_ONTSTAAN_KOLOMMEN)
    tabel["ONTSTANE_VACATURES"] = tabel["ONTSTANE_VACATURES"].astype("Int64")
    return tabel


def _reeks(beroep: vacatures_ontstaan.Beroep) -> dict:
    klasse = _klasselabel(beroep)
    return {
        "beroep": beroep.label,
        "niveau": beroep.niveau,
        **({"klasse": klasse} if klasse else {}),
        "per_jaar": {w.jaar.titel: w.vacatures for w in vacatures_ontstaan.waarden(beroep)},
    }


def get_ontstane_vacatures(beroep: str | None = None, niveau: str = vacatures_ontstaan.SEGMENT) -> str:
    if blokkade := scope_blokkade(vacatures_ontstaan.DATASET):
        return blokkade
    if niveau not in NIVEAUS:
        return f"Niveau '{niveau}' is onbekend. Kies een van: {list(NIVEAUS)}."
    try:
        gevonden = vacatures_ontstaan.zoek(beroep) if beroep else None
        if beroep and gevonden is None:
            klassen = [b.label for b in vacatures_ontstaan.beroepen(vacatures_ontstaan.KLASSE)]
            return (
                f"Beroep '{beroep}' staat niet (of niet eenduidig) in de BRC 2014 van CBS 85081NED. Geef een code of "
                f"naam van een beroepsklasse of -segment, bijv. een van de klassen: {klassen}."
            )
        selectie = _selectie(gevonden, niveau)
        jaren = vacatures_ontstaan.jaren()
        eenheid = vacatures_ontstaan.eenheid()
        tabel = ontstaantabel(selectie)
        reeksen = [_reeks(b) for b in selectie]
    except Exception as e:
        return fouten.bronfout("CBS", e)

    args = {"niveau": niveau, **({"beroep": gevonden.code} if gevonden else {})}
    key = ":".join(["cbs", vacatures_ontstaan.DATASET, "ontstaan", niveau, *([gevonden.code] if gevonden else [])])
    _bewaar(key, tabel, TOOL_GET_ONTSTANE_VACATURES, args, _jarentekst(jaren))
    result = {
        "bron": _bron(
            vacatures_ontstaan.DATASET,
            vacatures_ontstaan.TITEL,
            vacatures_ontstaan.STATLINE_URL,
            vacatures_ontstaan.LICENTIE,
        ),
        "dataset": vacatures_ontstaan.DATASET,
        "data_key": key,
        "landelijk": _LANDELIJK,
        "niveau": niveau,
        **({"beroep": gevonden.label} if gevonden else {}),
        "jaren": [{"jaar": j.titel, "status": j.status} for j in jaren],
        "telling": _TELLING_STROOM.format(eenheid=eenheid),
        "geen_gegevens": _GEEN_GEGEVENS,
        **({"voorlopig": _VOORLOPIG_TEKST} if any(j.voorlopig for j in jaren) else {}),
        "reeksen": reeksen,
    }
    return _json(result)
