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

Geslacht per opleiding (#742) is dezelfde maat met `opleiding_naar_geslacht`: de code legt het niveau- en het
geslachtsbestand naast elkaar en geeft de verdeling alleen waar die exact is (`geslacht_opleiding`).
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any, ClassVar

import pandas as pd

from data import instellingen

from . import cbs_selectie, cbs_standaard, dekking, duo, geslacht_opleiding, periode, store
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
class AlternatieveBron:
    """Een andere bron voor dezelfde vraag, met een andere definitie: de app noemt haar onder het antwoord (#667)."""

    naam: str
    dataset: str
    bestand: str
    definitie: str
    gebruik: str


@dataclass(frozen=True)
class CbsRecept:
    """Een landelijke CBS-tabel met vaste totaalcodes; vorm en, als de tabel meer sectoren heeft, sector zijn codes.

    Bij vorm `alle` volgt een dimensie met een standaardselectie (`cbs_standaard`, #653) die standaard.
    """

    naam: str
    omschrijving: str
    dataset: str
    teldefinitie: str
    onderwerp: str
    sectoren: tuple[str, ...] = _HO
    sectordimensie: str | None = "Onderwijssoort"  # None: de tabel telt één sector
    sectorcodes: Mapping[str, str] = field(default_factory=lambda: dict(SECTORCODES_CBS))
    vormdimensie: str = "Opleidingsvorm"
    vormen: Mapping[str, str] = field(default_factory=lambda: dict(VORMEN_HO_CBS))
    vast: Mapping[str, str] = field(default_factory=lambda: {"Opleidingsfase": "A045745", "Geslacht": "T001038"})
    alternatieve_bron: AlternatieveBron | None = None
    bron: ClassVar[str] = "cbs"


@dataclass(frozen=True)
class CbsSomRecept:
    """Een landelijke CBS-maat die de som is van vaste codes in één dimensie (#667).

    De codes zijn losse delen van hetzelfde totaal, dus de code telt ze op, niet het model. Elke andere dimensie ligt
    op een vaste code; een dimensie met een standaardselectie (`cbs_standaard`, #653) volgt die, met de uitsluiting
    uit het gesprek. De bronkeuze staat in dit ene recept: een andere keuze is een ander recept.
    """

    naam: str
    omschrijving: str
    dataset: str
    teldefinitie: str
    onderwerp: str
    somdimensie: str
    somcodes: tuple[str, ...]
    vast: Mapping[str, str]
    alternatieve_bron: AlternatieveBron
    sectoren: tuple[str, ...] = ("mbo",)
    vormen: Mapping[str, str] = field(default_factory=lambda: {ALLE: ALLE})
    bron: ClassVar[str] = "cbs"


Recept = DuoRecept | DuoBreedRecept | CbsRecept | CbsSomRecept
CbsRecepten = (CbsRecept, CbsSomRecept)

PERSONEN_HO = "ingeschreven_personen_ho"
INSCHRIJVINGEN_HO = "inschrijvingen_ho"
EERSTEJAARS_HO = "eerstejaars_ho"
DEELNEMERS_HO_LANDELIJK = "deelnemers_ho_landelijk"
MBO_STUDENTEN = "mbo_studenten_instelling"
MBO_STUDENTEN_LANDELIJK = "mbo_studenten_landelijk"
DOORSTROOM_VMBO_MBO = "doorstroom_vmbo_mbo"

# Mbo-studenten landelijk (#805): dezelfde vraag kreeg in één sessie DUO (474.963, de som van het bestand per
# sectorkamer, met onderdrukte cellen) en CBS 85354NED (475.460). Beide klopten, met een andere definitie. De code
# kiest CBS; DUO komt als alternatief in de regel onder het antwoord, zoals bij vmbo → mbo (#667).
_LEERWEGEN_MBO_CBS = {ALLE: "A025290", "bol": "A041868", "bbl": "A025293"}  # alle: de standaard van de tabel (#653)
_DUO_MBO_STUDENTEN = AlternatieveBron(
    naam="DUO 'Mbo-studenten per instelling'",
    dataset="mbo-studenten-per-instelling",
    bestand="het bestand per instelling en leerweg",
    definitie=(
        "hoofdinschrijvingen op 1 oktober per instelling (bol, bbl en examendeelnemers, bekostigd en niet-bekostigd), "
        "opgeteld; aantallen van 1 tot en met 4 staan op -1 en tellen niet mee, dus de som is een ondergrens die per "
        "DUO-bestand verschilt"
    ),
    gebruik=(
        "Alleen als de gebruiker om de DUO-telling vraagt: per instelling get_maat mbo_studenten_instelling, "
        "landelijk get_duo_data op dit bestand met de gewone gronding. De app zet de bron, de definitie en dit "
        "alternatief zelf onder het antwoord."
    ),
)

# Vmbo → mbo (#667): dezelfde vraag kreeg CBS 85569NED (83.020) of DUO "Instromende mbo-studenten" (96.629). Beide
# klopten, met een andere definitie. De code kiest CBS; DUO komt als alternatief in de regel onder het antwoord.
_VMBO_3_4 = ("A041923", "A041922")  # Vmbo-b/k 3-4 totaal, Vmbo-g/t 3-4: losse delen, samen het vmbo in leerjaar 3-4
_DUO_INSTROOM_MBO = AlternatieveBron(
    naam="DUO 'Instromende mbo-studenten'",
    dataset="instromende-mbo-studenten",
    bestand="het bestand met soorten instroom",
    definitie=(
        "mbo-instromers met een vmbo-diploma (gemengde leerweg inbegrepen, ongediplomeerden niet), direct na het "
        "diploma of indirect (later of via een andere route), direct en indirect samen"
    ),
    gebruik=(
        "Alleen als de gebruiker om de DUO-telling of de diplomaroute vraagt: dan get_duo_data op dit bestand, "
        "met de gewone gronding. De app zet de bron, de definitie en dit alternatief zelf onder het antwoord."
    ),
)

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
    MBO_STUDENTEN_LANDELIJK: CbsRecept(
        MBO_STUDENTEN_LANDELIJK,
        "mbo-studenten landelijk, per studiejaar, naar leerweg (CBS 85354NED, afgerond op tientallen)",
        "85354NED",
        "mbo-studenten landelijk, alle niveaus, geslachten en herkomsten; CBS rondt af op tientallen",
        "MboStudenten_1",
        sectoren=("mbo",),
        sectordimensie=None,
        sectorcodes={},
        vormdimensie="Leerweg",
        vormen=_LEERWEGEN_MBO_CBS,
        vast={"Geslacht": "T001038", "Niveau": "T001336", "Herkomstland": "T001040", "GeboortelandOuders": "T001638"},
        alternatieve_bron=_DUO_MBO_STUDENTEN,
    ),
    DOORSTROOM_VMBO_MBO: CbsSomRecept(
        DOORSTROOM_VMBO_MBO,
        "doorstroom vmbo → mbo landelijk, per schooljaar: mbo-instromers uit vmbo-leerjaar 3-4 (CBS)",
        "85569NED",
        "mbo-instromers met als positie vmbo-leerjaar 3-4 een jaar eerder (vmbo-b/k en vmbo-g/t, met of zonder "
        "vmbo-diploma), landelijk; de som van twee door CBS op tientallen afgeronde aantallen",
        "InstromersTotaal_1",
        "MaatschappelijkePositie1JaarEerder",
        _VMBO_3_4,
        {
            "Geslacht": "T001038",
            "Niveau": "T001336",
            "Leerweg": "A025290",  # de standaard van de tabel (#653): cbs_standaard.keuze beslist per gesprek
            "Sectorkamer": "T001637",
            "Persoonskenmerken": "T001638",
        },
        _DUO_INSTROOM_MBO,
    ),
}
# De maat voor één instelling bij een landelijke maat: een instelling erbij is een fout die daarheen wijst.
_PER_INSTELLING = {DEELNEMERS_HO_LANDELIJK: PERSONEN_HO, MBO_STUDENTEN_LANDELIJK: MBO_STUDENTEN}


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
    opleiding: str | None = None  # geslacht per opleiding (#742): de opleiding zoals het model haar noemde
    bestanden: tuple[int, int] | None = None  # en dan het niveau- en het geslachtsbestand


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


def _landelijkplan(
    recept: CbsRecept | CbsSomRecept, instelling, sector, vorm: str, jaren: tuple[int, ...]
) -> Plan | str:
    """Een landelijke maat: een instelling is een fout (geen gok); bij één sector volgt de sector uit het recept."""
    if instelling and str(instelling).strip():
        if andere := _PER_INSTELLING.get(recept.naam):
            return f"{recept.naam} is landelijk; per instelling is dat {andere}, met de instelling."
        return f"{recept.naam} is landelijk; per instelling of regio is er geen vaste maat. Laat de instelling weg."
    enige = recept.sectoren[0] if len(recept.sectoren) == 1 else ""
    sector = str(sector or enige).strip().lower()
    if not sector:
        return f"Geef voor {recept.naam} de sector: {' of '.join(recept.sectoren)}."
    if sector not in recept.sectoren:
        return f"{recept.naam} geldt voor {'/'.join(recept.sectoren)}, niet voor {sector}."
    return Plan(recept, sector, vorm, jaren, None, None)


def _geslachtplan(p: Plan, opleiding: str) -> Plan | str:
    """Geslacht per opleiding (#742): het niveau- en het geslachtsbestand van dezelfde maat en sector."""
    recept = p.recept
    assert isinstance(recept, DuoRecept)
    if p.vorm != ALLE:
        return "Het geslachtsbestand kent geen opleidingsvorm: laat vorm weg bij opleiding_naar_geslacht."
    sectorwoord = recept.bestand[p.sector][0]
    niveau = _bestand(recept.dataset, (sectorwoord, "niveau opleiding"))
    geslacht = _bestand(recept.dataset, (sectorwoord, "geslacht"))
    if niveau is None or geslacht is None:
        return (
            f"{recept.dataset} heeft voor {p.sector} geen niveau- en geslachtsbestand; geslacht per opleiding kan niet."
        )
    return replace(p, opleiding=opleiding, bestanden=(niveau, geslacht))


def plan(maat, instelling=None, sector=None, vorm=ALLE, schooljaren=None, opleiding_naar_geslacht=None) -> Plan | str:
    """Het plan voor een maat en afbakening, of de fout als tekst voor het model. Geen gok."""
    recept = MATEN.get(str(maat or "").strip().lower())
    if recept is None:
        return f"Onbekende maat {maat!r}. Kies uit: {', '.join(MATEN)}."
    opleiding = " ".join(str(opleiding_naar_geslacht or "").split()) or None
    if opleiding and not isinstance(recept, DuoRecept):
        namen = ", ".join(naam for naam, r in MATEN.items() if isinstance(r, DuoRecept))
        return f"Geslacht per opleiding kan alleen bij {namen}, met een instelling."
    vorm = str(vorm or ALLE).strip().lower()
    if vorm not in vormen(recept):
        return f"Vorm {vorm!r} past niet bij {recept.naam}; kies uit {', '.join(vormen(recept))}."
    jaren = _jaren(schooljaren)
    if isinstance(jaren, str):
        return jaren
    if isinstance(recept, CbsRecepten):
        return _landelijkplan(recept, instelling, sector, vorm, jaren)
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
    gewoon = Plan(recept, profiel["sector"], vorm, jaren, profiel, bestand)
    return _geslachtplan(gewoon, opleiding) if opleiding else gewoon


def filters(p: Plan) -> dict:
    """De query_data-filters van een DUO-plan: instellingscode, vorm (tenzij alle) en schooljaren."""
    recept = p.recept
    assert not isinstance(recept, CbsRecepten) and p.instelling is not None
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
    if isinstance(r, CbsSomRecept):
        dimensies = {**r.vast, r.somdimensie: list(r.somcodes)}
    else:
        assert isinstance(r, CbsRecept)
        dimensies = {r.sectordimensie: r.sectorcodes[p.sector]} if r.sectordimensie else {}
        dimensies |= {r.vormdimensie: r.vormen[p.vorm], **r.vast}
    if p.vorm == ALLE and (standaard := cbs_standaard.keuze(r.dataset)):
        dimensie, code, _ = standaard
        dimensies[dimensie] = code
    return {
        "dimensies": dimensies,
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


def _per_reden(niet: dict[int, str]) -> str:
    """De jaren zonder exacte verdeling, per reden: "2021/22, 2022/23: reden"."""
    jaren: dict[str, list[int]] = {}
    for jaar, reden in sorted(niet.items()):
        jaren.setdefault(reden, []).append(jaar)
    return "; ".join(f"{', '.join(periode.labels(j))}: {reden}" for reden, j in jaren.items())


def _geslacht(p: Plan) -> dict | str:
    """Geslacht per opleiding (#742): de verdeling uit het geslachtsbestand in de jaren waarin die exact is."""
    r = p.recept
    assert isinstance(r, DuoRecept) and p.instelling is not None and p.bestanden is not None and p.opleiding
    geladen = [_json(get_duo_data(r.dataset, index)) for index in p.bestanden]
    for uit in geladen:
        if not isinstance(uit, dict) or "data_key" not in uit:
            return _melding(uit)
    niveaukey, geslachtkey = (str(uit["data_key"]) for uit in geladen)
    code = p.instelling["instellingscode"]
    niveau, geslacht = (store.get(k) for k in (niveaukey, geslachtkey))
    niveau = niveau[niveau[r.instellingskolom] == code]
    geslacht = geslacht[geslacht[r.instellingskolom] == code]
    opl = geslacht_opleiding.kies_opleiding(niveau, p.opleiding)
    if isinstance(opl, str):
        return f"{opl} (instelling {p.instelling['naam']}, {r.dataset})"
    v = geslacht_opleiding.verdeling(niveau, geslacht, opl, r.waardekolom, r.periodekolom, r.instellingskolom, p.jaren)
    if v.rijen.empty:
        return (
            f"Geslacht staat in DUO ({r.dataset}) niet per opleiding, en voor {opl.naam} ({opl.code}) bij "
            f"{p.instelling['naam']} is de verdeling in geen enkel jaar exact af te leiden. {_per_reden(v.niet_af_te_leiden)}. "
            "Zeg dat in het antwoord, zonder verdeling: schat haar niet uit een groep met andere opleidingen."
        )
    jaren = f":{'-'.join(map(str, p.jaren))}" if p.jaren else ""
    key = f"{geslachtkey}:{r.naam}:geslacht:{code}:{opl.code}{jaren}"
    stap = (
        f"recept {r.naam}: geslacht van opleiding {opl.code} uit de cel van het geslachtsbestand waarin zij de enige is"
    )
    store.derive(geslachtkey, key, v.rijen, stap=stap, **dekking.van(v.rijen, store.meta(geslachtkey)))
    uit = {
        "data_key": key,
        "rijen": _records(v.rijen),
        "bestand": geladen[1].get("resource_titel"),
        "recept": _recept(p),
        "opleiding": {"code": opl.code, "naam": opl.naam},
    }
    if v.niet_af_te_leiden:
        uit["niet_af_te_leiden"] = [
            {"schooljaar": periode.label(jaar), "reden": reden} for jaar, reden in sorted(v.niet_af_te_leiden.items())
        ]
    if geladen[1].get("beschikbare_schooljaren") is not None:
        uit["beschikbare_schooljaren"] = geladen[1]["beschikbare_schooljaren"]
    return uit


def _duo(p: Plan) -> dict | str:
    r = p.recept
    assert not isinstance(r, CbsRecepten)
    if p.opleiding:
        return _geslacht(p)
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


def _somlabel(df: pd.DataFrame, r: CbsSomRecept) -> str:
    """De labels van de opgetelde codes, in de volgorde van het recept; de code zelf als de bron geen label gaf."""
    labelkolom = f"{r.somdimensie}_label"
    labels = dict(zip(df[r.somdimensie], df[labelkolom], strict=True)) if labelkolom in df.columns else {}
    return " + ".join(str(labels.get(code) or code) for code in r.somcodes)


def _met_som(querykey: str, p: Plan) -> str | None:
    """De som van de codes per periode, als eigen key afgeleid van de selectie; None als de bron er een mist.

    Elke andere dimensie ligt vast, dus per periode staat er één rij per code. Ontbreekt een code of zijn waarde, dan
    geen som van een deel: die periode krijgt geen getal (min_count). Het label noemt de opgetelde codes, zodat de
    Telling- en Uitgangspunt-regel zeggen wat er opgeteld is.
    """
    r = p.recept
    assert isinstance(r, CbsSomRecept)
    df = store.get(querykey)
    labelkolom = f"{r.somdimensie}_label"
    per = [c for c in df.columns if c not in (r.somdimensie, labelkolom, r.onderwerp)]
    som = df.groupby(per, dropna=False, sort=True)[r.onderwerp].sum(min_count=len(r.somcodes)).reset_index()
    som = som.assign(**{r.somdimensie: " + ".join(r.somcodes), labelkolom: _somlabel(df, r)})
    som = som[[c for c in df.columns if c in som.columns]]
    if som[r.onderwerp].isna().all():
        return None
    key = f"{querykey}:{r.naam}"
    stap = f"recept {r.naam}: {r.onderwerp} = som van {r.somdimensie} {' + '.join(r.somcodes)}"
    store.derive(querykey, key, som, stap=stap)
    return key


def _cbs(p: Plan) -> dict | str:
    r = p.recept
    assert isinstance(r, CbsRecepten)
    geladen = _json(get_cbs_data(r.dataset, selectie=selectie(p)))
    if not isinstance(geladen, dict) or "data_key" not in geladen:
        return _melding(geladen)
    key: str = geladen["data_key"]
    if isinstance(r, CbsSomRecept):
        somkey = _met_som(key, p)
        if somkey is None:
            return f"{r.dataset} gaf niet voor elke code van {r.naam} een getal ({', '.join(r.somcodes)}); geen som."
        key = somkey
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
    return "Perioden" if isinstance(p.recept, CbsRecepten) else p.recept.periodekolom


def _waardekolom(p: Plan) -> str:
    r = p.recept
    if isinstance(r, CbsRecepten):
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
    if isinstance(r, CbsSomRecept):
        return {**uit, "selectie": selectie(p), "som": {r.somdimensie: list(r.somcodes)}}
    if isinstance(r, CbsRecept):
        return {**uit, "selectie": selectie(p)}
    if p.bestanden is not None and p.instelling is not None:
        niveau, geslacht = p.bestanden
        return {
            **uit,
            "bestanden": {"niveau opleiding": niveau, "geslacht": geslacht},
            "instelling": p.instelling["instellingscode"],
            "regel": "de cel van het geslachtsbestand waarin de opleiding de enige is, zonder -1, met gelijke totalen",
        }
    return {**uit, "bestand": p.bestand, "filters": filters(p), "per": r.periodekolom, "som": aggregate(p)}


def _teldefinitie(p: Plan) -> str:
    """De teldefinitie van het recept, bij CBS met de telling die geladen is: de standaard (vorm alle) of de vorm.

    De regel onder het antwoord (`agent/bronkeuze.py`) noemt haar: een bol-cijfer mag daar niet als alle leerwegen staan.
    """
    r = p.recept
    if isinstance(r, CbsRecepten) and p.vorm == ALLE and (standaard := cbs_standaard.keuze(r.dataset)):
        dimensie, _, label = standaard
        return f"{r.teldefinitie}; {dimensie}: {label}"
    if isinstance(r, CbsRecept) and p.vorm != ALLE:
        return f"{r.teldefinitie}; {r.vormdimensie}: {p.vorm}"
    return r.teldefinitie


def get_maat(
    maat: str,
    instelling: str | None = None,
    sector: str | None = None,
    vorm: str = ALLE,
    schooljaren: list | None = None,
    opleiding_naar_geslacht: str | None = None,
) -> str:
    """Een vaste maat voor een instelling of landelijk: de code kiest dataset, bestand en codes."""
    p = plan(maat, instelling, sector, vorm, schooljaren, opleiding_naar_geslacht)
    if isinstance(p, str):
        return p
    uit = _cbs(p) if isinstance(p.recept, CbsRecepten) else _duo(p)
    if isinstance(uit, str):
        return uit
    r = p.recept
    rijen = uit.pop("rijen")
    result: dict[str, Any] = {
        "data_key": uit.pop("data_key"),
        "maat": r.naam,
        "teldefinitie": _teldefinitie(p),
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
    if p.opleiding:
        result["afleiding"] = (
            "Geslacht staat in DUO niet per opleiding. Deze verdeling is toch exact: in elk jaar met rijen is de "
            "opleiding de enige in haar cel van het geslachtsbestand (instelling, vestigingsgemeente, onderdeel en "
            "subonderdeel), zonder onderdrukte aantallen en met hetzelfde totaal als in het opleidingsbestand. Zeg dat "
            "zo in het antwoord; het is geen schatting. Een jaar onder niet_af_te_leiden krijgt geen getal."
        )
    if isinstance(r, CbsRecepten) and r.alternatieve_bron is not None:
        result["alternatieve_bron"] = asdict(r.alternatieve_bron)
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
