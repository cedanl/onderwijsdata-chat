"""get_maat: vaste recepten. Het model kiest maat en afbakening, code kiest dataset, bestand en codes (#188).

Voor een gewone telvraag ("hoeveel studenten heeft de HU?") liep het model zelf de keten
search_catalog → dataset_details → bestandskeuze → get_cbs_dimension → codes → filters. Bijna
alle ernstige fouten uit de audits zaten in die keten: een verkeerde instellingscode (#143),
T001228 als voltijd (#163), totaal en delen opgeteld (#162), het bestand zonder OPLEIDINGSVORM
(#173), personen of inschrijvingen per sessie anders (audit 7b), een verkeerd schooljaar (#187).

Hier staat per maat één recept: bron, dataset, bestand, kolommen, codes en teldefinitie. Het
model geeft de maat en de afbakening (instelling, sector, vorm, schooljaren); de code lost de
instelling op in het register (#143), het schooljaar in de spelling van de bron (#187) en de
vorm in de code van de bron, en laadt en selecteert met dezelfde tools als anders
(get_duo_data, get_cbs_data, query_data): scopegrens, sentinelmaskering, afronding en KeyMeta
komen zo gewoon mee. Het resultaat is een gewone data_key met rijen plus teldefinitie, bron
en recept; plot, KPI en rapport werken er zoals altijd mee. Een onbekende instelling, maat of
vorm is een expliciete fout, geen gok. "Studenten" is standaard personen (p01);
inschrijvingen (p03) alleen op expliciete vraag, en dan met vermelding.
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, ClassVar

import pandas as pd

from data import instellingen

from . import cbs_selectie, duo, periode, store
from .catalog import tabelbestanden
from .cbs import get_cbs_data
from .duo import get_duo_data
from .query import query_data

logger = logging.getLogger(__name__)

ALLE = "alle"
AANTAL = "AANTAL"
VORMEN_HO = {"voltijd": "VT", "deeltijd": "DT", "duaal": "DU"}
VORMEN_HO_CBS = {"voltijd": "A028666", "deeltijd": "A028667", "duaal": "A028668", ALLE: "T001228"}
LEERWEGEN_MBO = {"bol": ("BOLVT", "BOLDT"), "bbl": ("BBL",), ALLE: ("BBL", "BOLDT", "BOLVT", "EX")}
SECTORCODES_CBS = {"hbo": "A025294", "wo": "A025297"}
_HO = ("hbo", "wo")
# Het bestand per sector, aan de woorden in zijn titel: het opleidingsvorm-bestand is leidend (het
# geslacht-bestand onderdrukt de meeste cellen, #325) en heeft de kolom waar de vorm op filtert (#173).
_BESTAND_HO: Mapping[str, tuple[str, ...]] = {
    "hbo": ("hoger beroepsonderwijs", "opleidingsvorm"),
    "wo": ("wetenschappelijk", "opleidingsvorm"),
}


@dataclass(frozen=True)
class DuoRecept:
    """Een DUO-bestand met één telkolom en per rij een instelling, studiejaar en opleidingsvorm."""

    naam: str
    omschrijving: str
    dataset: str
    teldefinitie: str
    waardekolom: str
    sectoren: tuple[str, ...] = _HO
    instellingskolom: str = "INSTELLINGSCODE_ACTUEEL"
    periodekolom: str = "STUDIEJAAR"
    vormkolom: str = "OPLEIDINGSVORM"
    vormen: Mapping[str, str] = field(default_factory=lambda: dict(VORMEN_HO))
    bestand: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: dict(_BESTAND_HO))
    bron: ClassVar[str] = "duo"


@dataclass(frozen=True)
class DuoBreedRecept:
    """Een DUO-bestand met de leerwegen als kolommen (mbo): de maat is een som over kolommen."""

    naam: str
    omschrijving: str
    dataset: str
    teldefinitie: str
    sectoren: tuple[str, ...] = ("mbo",)
    instellingskolom: str = "INSTELLINGSCODE"
    periodekolom: str = "JAAR"
    leerwegen: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: dict(LEERWEGEN_MBO))
    bestand: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {"mbo": ("instelling", "en leerweg")})
    bron: ClassVar[str] = "duo"


@dataclass(frozen=True)
class CbsRecept:
    """Een CBS-tabel met vaste totaalcodes; sector en vorm zijn dimensiecodes."""

    naam: str
    omschrijving: str
    dataset: str
    teldefinitie: str
    onderwerp: str
    sectoren: tuple[str, ...] = _HO
    sectordimensie: str = "Onderwijssoort"
    sectorcodes: Mapping[str, str] = field(default_factory=lambda: dict(SECTORCODES_CBS))
    vormdimensie: str = "Opleidingsvorm"
    vormen: Mapping[str, str] = field(default_factory=lambda: dict(VORMEN_HO_CBS))
    vast: Mapping[str, str] = field(default_factory=lambda: {"Opleidingsfase": "A045745", "Geslacht": "T001038"})
    bron: ClassVar[str] = "cbs"


Recept = DuoRecept | DuoBreedRecept | CbsRecept

PERSONEN_HO = "ingeschreven_personen_ho"
INSCHRIJVINGEN_HO = "inschrijvingen_ho"
EERSTEJAARS_HO = "eerstejaars_ho"
DEELNEMERS_HO_LANDELIJK = "deelnemers_ho_landelijk"
MBO_STUDENTEN = "mbo_studenten_instelling"

MATEN: dict[str, Recept] = {
    PERSONEN_HO: DuoRecept(
        PERSONEN_HO,
        "ingeschreven personen (studenten) per hbo- of wo-instelling, per studiejaar",
        "p01hoinges",
        "personen: hoofdinschrijvingen op 1 oktober, elke persoon één keer in het hele ho (DUO p01hoinges)",
        "AANTAL_INGESCHREVENEN",
    ),
    INSCHRIJVINGEN_HO: DuoRecept(
        INSCHRIJVINGEN_HO,
        "inschrijvingen (hoofd- én neveninschrijvingen) per hbo- of wo-instelling, per studiejaar",
        "p03hoinschr",
        "inschrijvingen: hoofd- én neveninschrijvingen op 1 oktober, geen personen (DUO p03hoinschr)",
        "AANTAL_INSCHRIJVINGEN",
    ),
    EERSTEJAARS_HO: DuoRecept(
        EERSTEJAARS_HO,
        "eerstejaars personen per hbo- of wo-instelling, per studiejaar",
        "p02ho1ejrs",
        "eerstejaars personen: eerste hoofdinschrijving in het ho op 1 oktober (DUO p02ho1ejrs)",
        "AANTAL_EERSTEJAARS_INGESCHREVENEN",
    ),
    DEELNEMERS_HO_LANDELIJK: CbsRecept(
        DEELNEMERS_HO_LANDELIJK,
        "ingeschrevenen hbo of wo landelijk, per studiejaar (CBS, afgerond op tientallen)",
        "85423NED",
        "ingeschrevenen in het hbo of wo landelijk, alle fasen en geslachten; CBS rondt af op tientallen",
        "TotaalIngeschrevenen_1",
    ),
    MBO_STUDENTEN: DuoBreedRecept(
        MBO_STUDENTEN,
        "mbo-studenten per instelling, per studiejaar, naar leerweg",
        "mbo-studenten-per-instelling",
        "hoofdinschrijvingen op 1 oktober: bol en bbl (bekostigd en niet-bekostigd) en examendeelnemers "
        "(DUO mbo-studenten-per-instelling)",
    ),
}


def vormen(recept: Recept) -> tuple[str, ...]:
    """De vormen die het model bij deze maat mag kiezen; `alle` staat vooraan."""
    namen = recept.leerwegen if isinstance(recept, DuoBreedRecept) else recept.vormen
    return (ALLE, *(v for v in namen if v != ALLE))


@dataclass(frozen=True)
class Plan:
    """Wat de code koos uit maat en afbakening, vóór er iets wordt geladen."""

    recept: Recept
    sector: str
    vorm: str
    jaren: tuple[int, ...]  # startjaren; leeg is alle beschikbare
    instelling: dict | None  # naam, instellingscode, sector uit het register; None bij een landelijke maat
    bestand: int | None  # DUO: de index van het bestand


def _jaren(schooljaren) -> tuple[int, ...] | str:
    """Startjaren uit de spelling van het model (2024/25, 2024SJ00, 2024); een onbekende spelling is een fout."""
    if schooljaren is None or schooljaren == []:
        return ()
    uit = set()
    for waarde in schooljaren if isinstance(schooljaren, list) else [schooljaren]:
        jaar = periode.startjaar_van_spelling(waarde)
        if jaar is None:
            tekst = str(waarde).strip()
            jaar = int(tekst) if tekst.isdigit() and len(tekst) == 4 else None
        if jaar is None:
            return f"Schooljaar {waarde!r} niet begrepen. Geef schooljaren als 2024/25 (of het startjaar 2024)."
        uit.add(jaar)
    return tuple(sorted(uit))


def _bestand(dataset: str, woorden: tuple[str, ...]) -> int | None:
    """De index van het DUO-bestand waarvan de titel alle woorden bevat; None als het er niet is."""
    for index, titel in tabelbestanden(dataset):
        if all(w in titel.lower() for w in woorden):
            return index
    return None


def plan(maat, instelling=None, sector=None, vorm=ALLE, schooljaren=None) -> Plan | str:
    """Het plan voor een maat en afbakening, of de fout als tekst voor het model. Geen gok."""
    recept = MATEN.get(str(maat or "").strip().lower())
    if recept is None:
        return f"Onbekende maat {maat!r}. Kies uit: {', '.join(MATEN)}."
    vorm = str(vorm or ALLE).strip().lower()
    if vorm not in vormen(recept):
        return f"Vorm {vorm!r} past niet bij {recept.naam}; kies uit {', '.join(vormen(recept))}."
    jaren = _jaren(schooljaren)
    if isinstance(jaren, str):
        return jaren
    if isinstance(recept, CbsRecept):
        sector = str(sector or "").strip().lower()
        if sector not in recept.sectoren:
            return f"Geef voor {recept.naam} de sector: {' of '.join(recept.sectoren)}."
        return Plan(recept, sector, vorm, jaren, None, None)
    if not instelling or not str(instelling).strip():
        return f"Geef voor {recept.naam} de instelling (officiële naam of alias)."
    profiel = instellingen.instellingsprofiel(str(instelling))
    if profiel is None:
        return (
            f"Onbekende instelling {instelling!r}: het register kent deze naam of alias niet. "
            "Geen gok; controleer de naam, bijvoorbeeld via dataset_details van het DUO-bestand."
        )
    if profiel["sector"] not in recept.sectoren:
        andere = MBO_STUDENTEN if profiel["sector"] == "mbo" else PERSONEN_HO
        return (
            f"{profiel['naam']} is een {profiel['sector']}-instelling; {recept.naam} geldt voor "
            f"{'/'.join(recept.sectoren)}. Gebruik {andere}."
        )
    bestand = _bestand(recept.dataset, recept.bestand[profiel["sector"]])
    if bestand is None:
        return f"Het recept {recept.naam} vindt het bestand voor {profiel['sector']} niet in {recept.dataset}."
    return Plan(recept, profiel["sector"], vorm, jaren, profiel, bestand)


def filters(p: Plan) -> dict:
    """De query_data-filters van een DUO-plan: instellingscode, vorm (tenzij alle) en schooljaren."""
    recept = p.recept
    assert not isinstance(recept, CbsRecept) and p.instelling is not None
    uit: dict[str, Any] = {recept.instellingskolom: p.instelling["instellingscode"]}
    if isinstance(recept, DuoRecept) and p.vorm != ALLE:
        uit[recept.vormkolom] = recept.vormen[p.vorm]
    if p.jaren:
        uit[recept.periodekolom] = list(p.jaren)
    return uit


def aggregate(p: Plan) -> dict[str, str]:
    """Wat query_data per studiejaar optelt: de telkolom, of bij mbo de leerwegkolommen van de vorm."""
    if isinstance(p.recept, DuoBreedRecept):
        return dict.fromkeys(p.recept.leerwegen[p.vorm], "sum")
    assert isinstance(p.recept, DuoRecept)
    return {p.recept.waardekolom: "sum"}


def selectie(p: Plan) -> dict:
    """De gesloten CBS-selectie van een landelijk plan (#343): elke dimensie gepind."""
    r = p.recept
    assert isinstance(r, CbsRecept)
    return {
        "dimensies": {r.sectordimensie: r.sectorcodes[p.sector], r.vormdimensie: r.vormen[p.vorm], **r.vast},
        "periode": [periode.label(j) for j in p.jaren] or cbs_selectie.ALLES,
        "onderwerpen": [r.onderwerp],
        "sector": p.sector,
    }


def _json(tekst: str):
    try:
        return json.loads(tekst)
    except (TypeError, ValueError):
        return tekst


def _melding(uit) -> str:
    """Een tooluitkomst zonder data_key, doorgegeven zoals de tool hem gaf."""
    return json.dumps(uit, ensure_ascii=False) if isinstance(uit, dict | list) else str(uit)


def _records(df: pd.DataFrame) -> list[dict]:
    """De rijen voor het model, met tellingen als tellingen: na het maskeren van -1 is een kolom float en
    stond 4507.0 in het antwoord (#631); dezelfde regel als query_data (duo.json_waarde)."""
    return [{k: duo.json_waarde(v) for k, v in rij.items()} for rij in df.to_dict(orient="records")]


def _met_totaal(querykey: str, p: Plan) -> tuple[str, list[dict]]:
    """Bij mbo: de som van de leerwegkolommen als AANTAL, als eigen key afgeleid van de selectie."""
    assert isinstance(p.recept, DuoBreedRecept)
    df = store.get(querykey)
    kolommen = list(p.recept.leerwegen[p.vorm])
    totaal = df.assign(**{AANTAL: df[kolommen].sum(axis=1, min_count=1)})
    key = f"{querykey}:{p.recept.naam}"
    store.derive(querykey, key, totaal, stap=f"recept {p.recept.naam}: {AANTAL} = {' + '.join(kolommen)}")
    if (cellen := duo.sentinel_cells(querykey)) is not None:
        duo.record_sentinel_cells(key, cellen, groepen=True)  # dezelfde rijen: de onderdrukking reist mee
    return key, _records(store.get(key))


def _duo(p: Plan) -> dict | str:
    r = p.recept
    assert not isinstance(r, CbsRecept)
    geladen = _json(get_duo_data(r.dataset, p.bestand))
    if not isinstance(geladen, dict) or "data_key" not in geladen:
        return _melding(geladen)
    # Een gevraagd schooljaar dat het bestand niet heeft, blijft weg uit de selectie en komt terug als
    # `ontbrekende_schooljaren`; staat er geen enkel gevraagd jaar in, dan is dat de melding (#187).
    known = store.meta(geladen["data_key"])
    beschikbaar = set(known.schooljaren or ()) if known else set()
    if p.jaren and beschikbaar:
        binnen = tuple(j for j in p.jaren if j in beschikbaar)
        if not binnen:
            return (
                f"Geen van de gevraagde schooljaren ({', '.join(periode.labels(p.jaren))}) staat in {r.dataset}; "
                f"beschikbaar: {', '.join(periode.labels(sorted(beschikbaar)))}."
            )
        p = replace(p, jaren=binnen)
    gekozen = _json(
        query_data(geladen["data_key"], filters=filters(p), group_by=[r.periodekolom], aggregate=aggregate(p))
    )
    if not isinstance(gekozen, dict) or "data_key" not in gekozen:
        return _melding(gekozen)
    key, rijen = gekozen["data_key"], gekozen["rijen"]
    if isinstance(r, DuoBreedRecept):
        key, rijen = _met_totaal(key, p)
    uit = {"data_key": key, "rijen": rijen, "bestand": geladen.get("resource_titel"), "recept": _recept(p)}
    for veld in ("databewerking", "beschikbare_schooljaren", "publicatieregels"):
        if geladen.get(veld) is not None or gekozen.get(veld) is not None:
            uit[veld] = gekozen.get(veld) if gekozen.get(veld) is not None else geladen.get(veld)
    return uit


def _cbs(p: Plan) -> dict | str:
    r = p.recept
    assert isinstance(r, CbsRecept)
    geladen = _json(get_cbs_data(r.dataset, selectie=selectie(p)))
    if not isinstance(geladen, dict) or "data_key" not in geladen:
        return _melding(geladen)
    key = geladen["data_key"]
    df = store.get(key)
    known = store.meta(key)
    tijd = (known.periodekolom if known else None) or "Perioden"
    kolommen = [c for c in (tijd, f"{tijd}_label", "Periodestatus", r.onderwerp) if c in df.columns]
    uit = {"data_key": key, "rijen": _records(df[kolommen])}
    for veld in ("afronding", "afronding_onbekend", "laatste_update", "beschikbare_schooljaren", "metadata_ontbreekt"):
        if geladen.get(veld) is not None:
            uit[veld] = geladen[veld]
    return uit


def _periodekolom(p: Plan) -> str:
    return "Perioden" if isinstance(p.recept, CbsRecept) else p.recept.periodekolom


def _waardekolom(p: Plan) -> str:
    r = p.recept
    if isinstance(r, CbsRecept):
        return r.onderwerp
    return AANTAL if isinstance(r, DuoBreedRecept) else r.waardekolom


def _ontbrekend(p: Plan, rijen: list[dict]) -> list[str]:
    """Gevraagde schooljaren die de bron niet gaf, als label: het antwoord mag ze niet invullen."""
    if not p.jaren:
        return []
    kolom = _periodekolom(p)
    gevonden = {periode.startjaar(p.recept.bron, rij.get(kolom)) for rij in rijen}
    return [periode.label(j) for j in p.jaren if j not in gevonden]


def _recept(p: Plan) -> dict:
    """Wat de code koos, voor het model en de redeneerkaart: geen gok die onzichtbaar blijft."""
    r = p.recept
    uit: dict[str, Any] = {"bron": r.bron, "dataset": r.dataset}
    if isinstance(r, CbsRecept):
        return {**uit, "selectie": selectie(p)}
    return {**uit, "bestand": p.bestand, "filters": filters(p), "per": r.periodekolom, "som": aggregate(p)}


def get_maat(
    maat: str,
    instelling: str | None = None,
    sector: str | None = None,
    vorm: str = ALLE,
    schooljaren: list | None = None,
) -> str:
    """Een vaste maat voor een instelling of landelijk: de code kiest dataset, bestand en codes."""
    p = plan(maat, instelling, sector, vorm, schooljaren)
    if isinstance(p, str):
        return p
    uit = _cbs(p) if isinstance(p.recept, CbsRecept) else _duo(p)
    if isinstance(uit, str):
        return uit
    r = p.recept
    rijen = uit.pop("rijen")
    result: dict[str, Any] = {
        "data_key": uit.pop("data_key"),
        "maat": r.naam,
        "teldefinitie": r.teldefinitie,
        **({"instelling": p.instelling} if p.instelling else {"sector": p.sector}),
        "vorm": p.vorm,
        "periodekolom": _periodekolom(p),
        "waardekolom": _waardekolom(p),
        **store.rijtelling(len(rijen), True),
        "rijen": rijen,
        "recept": uit.pop("recept", None) or _recept(p),
        **uit,
    }
    if ontbrekend := _ontbrekend(p, rijen):
        result["ontbrekende_schooljaren"] = ontbrekend
    if r.naam == INSCHRIJVINGEN_HO:
        result["noot"] = (
            "Dit zijn inschrijvingen (hoofd- én neveninschrijvingen), geen personen: zeg dat in het antwoord. "
            f"Voor personen (studenten): {PERSONEN_HO}."
        )
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
