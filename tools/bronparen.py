"""De gecureerde koppeltabel DUO-CBS (#1259), uit data/bronparen.toml, en het getal van de andere bron.

Voor een deel van de maten tellen DUO en CBS hetzelfde, met een andere definitie of peildatum. Welke DUO-maat bij welke
CBS-maat hoort, is een keuze van een mens met een bron, geen keuze van het model: elk paar staat in het bestand, met het
niveau waarop beide vergelijkbaar zijn, de bekende redenen voor een verschil (elk met een bron) en het issue en de
datum van vaststelling. Een paar haakt op een vaste maat (`maat`): alleen een get_maat-resultaat van die maat, op het
niveau van het paar, krijgt een kruiscontrole. Geen toolargument kiest het paar; `paar_voor` leest alleen de maat en
het niveau uit het resultaat.

Faalt gesloten: een ongeldig bestand geeft een BronpaarFout, nooit een paar met ontbrekende velden.
"""

import json
import tomllib
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from . import duo, maten, store
from .catalog import tabelbestanden
from .duo import get_duo_data
from .query import query_data

PAD = Path(__file__).resolve().parent.parent / "data" / "bronparen.toml"
NIVEAUS = ("landelijk",)
AANTAL = "AANTAL"


class BronpaarFout(ValueError):
    """Het bestand met bronparen is ongeldig; de melding noemt het paar en wat eraan mankeert."""


@dataclass(frozen=True)
class Reden:
    tekst: str
    bron: str


@dataclass(frozen=True)
class DuoKant:
    naam: str
    dataset: str
    bestand: tuple[str, ...]  # woorden in de titel van het bestand, zoals in tools/maten.py
    periodekolom: str
    kolommen: tuple[str, ...]  # de telkolommen; het getal is hun som over alle rijen van het jaar
    afbakening: str


@dataclass(frozen=True)
class CbsKant:
    naam: str
    dataset: str
    codes: dict[str, str]


@dataclass(frozen=True)
class Bronpaar:
    id: str
    maat: str
    niveau: str
    drempel_pct: float
    issue: str
    vastgesteld: date
    waarneming: str
    cbs: CbsKant
    duo: DuoKant
    redenen: tuple[Reden, ...]


def _tekst(paar: str, tabel: dict, veld: str) -> str:
    waarde = tabel.get(veld)
    if not isinstance(waarde, str) or not waarde.strip():
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: '{veld}' ontbreekt of is leeg")
    if "\n" in waarde:
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: '{veld}' moet op één regel staan")
    return waarde.strip()


def _teksten(paar: str, tabel: dict, veld: str) -> tuple[str, ...]:
    waarde = tabel.get(veld)
    if not isinstance(waarde, list) or not waarde or not all(isinstance(w, str) and w.strip() for w in waarde):
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: '{veld}' moet een lijst met tekst zijn")
    return tuple(w.strip() for w in waarde)


def _tabel(paar: str, tabel: dict, veld: str) -> dict:
    waarde = tabel.get(veld)
    if not isinstance(waarde, dict):
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: [{veld}] ontbreekt")
    return waarde


def _reden(paar: str, ruw) -> Reden:
    if not isinstance(ruw, dict):
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: een reden is geen tabel")
    return Reden(_tekst(paar, ruw, "tekst"), _tekst(paar, ruw, "bron"))


def _paar(ruw: dict) -> Bronpaar:
    paar = ruw.get("id") if isinstance(ruw.get("id"), str) and ruw["id"].strip() else None
    if paar is None:
        raise BronpaarFout("bronparen.toml: een paar zonder 'id'")
    maat = _tekst(paar, ruw, "maat")
    if maat not in maten.MATEN:
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: onbekende maat {maat!r}")
    niveau = _tekst(paar, ruw, "niveau")
    if niveau not in NIVEAUS:
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: niveau {niveau!r}; bekend: {', '.join(NIVEAUS)}")
    drempel = ruw.get("drempel_pct")
    if isinstance(drempel, bool) or not isinstance(drempel, int | float) or drempel <= 0:
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: 'drempel_pct' moet een getal boven 0 zijn")
    issue = _tekst(paar, ruw, "issue")
    if not issue.startswith("#") or not issue[1:].isdigit():
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: 'issue' moet een issuenummer zijn (#1259), niet {issue!r}")
    vastgesteld = ruw.get("vastgesteld")
    if not isinstance(vastgesteld, date):
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: 'vastgesteld' moet een datum zijn zonder aanhalingstekens")
    cbs, duo_ = _tabel(paar, ruw, "cbs"), _tabel(paar, ruw, "duo")
    codes = cbs.get("codes")
    if not isinstance(codes, dict) or not codes or not all(isinstance(v, str) for v in codes.values()):
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: [paar.cbs] 'codes' ontbreekt")
    redenen = ruw.get("reden", [])
    if not isinstance(redenen, list):
        raise BronpaarFout(f"bronparen.toml: paar {paar!r}: 'reden' moet een lijst zijn ([[paar.reden]])")
    return Bronpaar(
        id=paar,
        maat=maat,
        niveau=niveau,
        drempel_pct=float(drempel),
        issue=issue,
        vastgesteld=vastgesteld,
        waarneming=_tekst(paar, ruw, "waarneming"),
        cbs=CbsKant(_tekst(paar, cbs, "naam"), _tekst(paar, cbs, "dataset"), dict(codes)),
        duo=DuoKant(
            _tekst(paar, duo_, "naam"),
            _tekst(paar, duo_, "dataset"),
            _teksten(paar, duo_, "bestand"),
            _tekst(paar, duo_, "periodekolom"),
            _teksten(paar, duo_, "kolommen"),
            _tekst(paar, duo_, "afbakening"),
        ),
        redenen=tuple(_reden(paar, r) for r in redenen),
    )


def laad(pad: Path = PAD) -> tuple[Bronpaar, ...]:
    """De gevalideerde paren uit `pad`; elk gebrek is een BronpaarFout."""
    try:
        ruw = tomllib.loads(pad.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise BronpaarFout(f"bronparen.toml: geen geldige TOML: {e}") from e
    paren = ruw.get("paar")
    if not isinstance(paren, list) or not paren:
        raise BronpaarFout("bronparen.toml: geen [[paar]]")
    uit = tuple(_paar(p) for p in paren if isinstance(p, dict))
    if len(uit) != len(paren):
        raise BronpaarFout("bronparen.toml: een [[paar]] is geen tabel")
    ids = [p.id for p in uit]
    if len(set(ids)) != len(ids):
        raise BronpaarFout("bronparen.toml: een id staat er twee keer")
    maten_ = [(p.maat, p.niveau) for p in uit]
    if len(set(maten_)) != len(maten_):
        raise BronpaarFout("bronparen.toml: twee paren op dezelfde maat en hetzelfde niveau")
    return uit


@cache
def paren() -> tuple[Bronpaar, ...]:
    return laad()


def _niveau(resultaat: dict) -> str | None:
    """Het niveau van een get_maat-resultaat: landelijk als er geen instelling is."""
    return None if resultaat.get("instelling") else "landelijk"


def paar_voor(resultaat: dict) -> Bronpaar | None:
    """Het paar van een get_maat-resultaat: dezelfde maat en hetzelfde niveau, bij vorm alle; anders None.

    Alleen de maat en het niveau van het resultaat tellen: wat het model in de tekst vraagt of in een ander argument
    zet, kiest geen paar (#1259)."""
    if resultaat.get("vorm", maten.ALLE) != maten.ALLE:
        return None
    niveau = _niveau(resultaat)
    return next((p for p in paren() if p.maat == resultaat.get("maat") and p.niveau == niveau), None)


def _bestand(kant: DuoKant) -> int | None:
    for index, titel in tabelbestanden(kant.dataset):
        if all(w in titel.lower() for w in kant.bestand):
            return index
    return None


def _json(tekst: str):
    try:
        return json.loads(tekst)
    except (TypeError, ValueError):
        return tekst


def duo_getal(paar: Bronpaar, startjaar: int) -> str:
    """Het getal van de DUO-kant van `paar` in één schooljaar, als toolresultaat met een eigen key: de som van de
    telkolommen over alle rijen van dat jaar. Laden met get_duo_data (scopegrens, -1 maskeren), selecteren met
    query_data, zoals een vaste maat; een melding als tekst."""
    kant = paar.duo
    bestand = _bestand(kant)
    if bestand is None:
        return f"Het bestand van bronpaar {paar.id} staat niet in {kant.dataset}."
    geladen = _json(get_duo_data(kant.dataset, bestand))
    if not isinstance(geladen, dict) or "data_key" not in geladen:
        return str(geladen)
    gekozen = _json(
        query_data(
            geladen["data_key"],
            filters={kant.periodekolom: [startjaar]},
            group_by=[kant.periodekolom],
            aggregate=dict.fromkeys(kant.kolommen, "sum"),
        )
    )
    if not isinstance(gekozen, dict) or "data_key" not in gekozen:
        return str(gekozen)
    querykey = str(gekozen["data_key"])
    df = store.get(querykey)
    if df is None or df.empty:
        return f"{kant.dataset} heeft geen rijen voor {startjaar}."
    totaal = df.assign(**{AANTAL: df[list(kant.kolommen)].sum(axis=1, min_count=1)})
    key = f"{querykey}:bronpaar:{paar.id}"
    store.derive(querykey, key, totaal, stap=f"bronpaar {paar.id}: {AANTAL} = {' + '.join(kant.kolommen)}")
    if (cellen := duo.sentinel_cells(querykey)) is not None:
        duo.record_sentinel_cells(key, cellen, groepen=True)
    rijen = [{k: duo.json_waarde(v) for k, v in rij.items()} for rij in store.get(key).to_dict(orient="records")]
    onderdrukt = sum(duo.onderdrukt(key).values())
    return json.dumps(
        {
            "data_key": key,
            "bronpaar": paar.id,
            "teldefinitie": f"{kant.naam}: {kant.afbakening}",
            "periodekolom": kant.periodekolom,
            "waardekolom": AANTAL,
            "rijen": rijen,
            "recept": {"bron": "duo", "dataset": kant.dataset, "bestand": bestand, "som": list(kant.kolommen)},
            **({"onderdrukte_cellen": onderdrukt} if onderdrukt else {}),
        },
        ensure_ascii=False,
        default=str,
    )
