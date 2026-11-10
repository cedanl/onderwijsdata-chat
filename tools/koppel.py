"""koppel_data: twee geladen tabellen koppelen in code, niet in een script van het model (#988, epic #191).

Een koppeling die het model zelf in pandas schreef, verloor rijen: een draaitabel met `dropna=True`, een filter op een
lege score vóór de koppeling, `how="left"` vanuit de verkeerde kant (reaudit A02/A03, eerder review 08 en #962). Een
promptregel hield dat niet tegen. Hier koppelt de code; het model kiest alleen de twee keys en de sleutels.

De koppeling is een outer join over de vereniging van de genormaliseerde sleutelwaarden (`onderwijsbronnen.sleutels`:
30020.0 is 30020, 2021SJ00 is 2021). Elke rij van beide tabellen blijft, ook een rij zonder match of met een lege
sleutel; een rij zonder match houdt lege cellen voor de andere kant, nooit 0. De kolom `koppelstatus` zegt per rij
waar ze vandaan komt. Het resultaat is een afgeleide key met de herkomst van beide tabellen (#977, #985).
"""

import hashlib
import json
import logging
from dataclasses import dataclass

import pandas as pd
from onderwijsbronnen import sleutels as kern

from . import dekking, fouten, relaties, store
from .analysis import modelrijen

logger = logging.getLogger(__name__)

KOPPELSTATUS = "koppelstatus"
STAP = "koppeling (koppel_data)"  # het begin van KeyMeta.stap: zo noemt de herkomst de stap
BEIDE = "beide"
_HERKOMST = "__koppel_herkomst"  # de indicatorkolom van pd.merge; komt nooit in het resultaat
_EEN, _VEEL = "one", "many"


class _Melding(Exception):
    """De koppeling gaat niet door; de tekst is de melding voor het model. Er komt niets in de store."""


@dataclass(frozen=True)
class _Kant:
    """Eén tabel van de koppeling: haar key, haar label in `koppelstatus` en de kolom per sleutel."""

    key: str
    label: str
    df: pd.DataFrame
    kolommen: dict[str, str]

    @property
    def alleen(self) -> str:
        return f"alleen {self.label}"


@dataclass(frozen=True)
class _Uitkomst:
    df: pd.DataFrame
    korrel: dict[str, str]
    uniek: dict[str, int]
    zonder_sleutel: dict[str, int]

    @property
    def koppeling(self) -> str:
        """De kardinaliteit van de koppeling, links eerst: one_to_many, zoals relatie haar noemt."""
        return "_to_".join(self.korrel.values())


def _tabel(key: str) -> pd.DataFrame:
    df = store.get(key)
    if not isinstance(df, pd.DataFrame):
        raise _Melding(fouten.onbekende_key(key))
    return df.rename(columns=str)


def _labels(links: str, rechts: str) -> tuple[str, str]:
    """De bron in hoofdletters (SKDB, DUO); bij twee tabellen van dezelfde bron de keys zelf."""
    bronnen = [m.bron.upper() if (m := store.meta(k)) else k for k in (links, rechts)]
    return (links, rechts) if bronnen[0] == bronnen[1] else (bronnen[0], bronnen[1])


def _sleutelnamen(sleutels: object) -> list[str]:
    if isinstance(sleutels, str):
        sleutels = [sleutels]
    if not isinstance(sleutels, list) or not sleutels or not all(isinstance(s, str) for s in sleutels):
        raise _Melding(_melding('Geef in `sleutels` minstens één sleutelnaam uit relatie, zoals ["brin", "croho"].'))
    namen = list(dict.fromkeys(s.strip().lower() for s in sleutels))
    if onbekend := [s for s in namen if s not in kern.SLEUTELS]:
        raise _Melding(
            _melding(
                f"Onbekende sleutel {onbekend}. Bekende sleutels: {', '.join(kern.SLEUTELS)}. Vraag eerst relatie."
            )
        )
    return namen


def _melding(tekst: str, **extra) -> str:
    return json.dumps({"melding": tekst, **extra}, ensure_ascii=False)


def _kandidaten(df: pd.DataFrame) -> dict[str, list[str]]:
    """Per sleutel de kolommen die hem dragen (relaties.sleutelkolommen), in kolomvolgorde."""
    uit: dict[str, list[str]] = {}
    for s in relaties.sleutelkolommen(df):
        uit.setdefault(s.sleutel.naam, []).append(s.kolom)
    return uit


def _kolommen(label: str, df: pd.DataFrame, sleutels: list[str], opgave: object, veld: str) -> tuple[dict, list[str]]:
    """De kolom per sleutel in één tabel, en wat er niet klopt; een opgave kiest uit de kandidaten, nooit daarbuiten."""
    kandidaten = _kandidaten(df)
    opgave = opgave if isinstance(opgave, dict) else {}
    kolommen: dict[str, str] = {}
    problemen: list[str] = []
    for sleutel in sleutels:
        opties = kandidaten.get(sleutel, [])
        gekozen = opgave.get(sleutel)
        if not opties:
            problemen.append(
                f"{label} heeft geen kolom met sleutel {sleutel}; sleutels in {label}: {kandidaten or 'geen'}."
            )
        elif gekozen is not None and gekozen not in opties:
            problemen.append(f"Kolom {gekozen!r} draagt in {label} geen sleutel {sleutel}; kandidaten: {opties}.")
        elif gekozen is None and len(opties) > 1:
            problemen.append(
                f"Sleutel {sleutel} staat in {label} in meer kolommen: {opties}. Kies er één met "
                f'{veld}: {{"{sleutel}": "<kolom>"}}.'
            )
        else:
            kolommen[sleutel] = gekozen or opties[0]
    return kolommen, problemen


def _kanten(data_key: str, andere_key: str, sleutels: list[str], links_opgave, rechts_opgave) -> tuple[_Kant, _Kant]:
    if data_key == andere_key:
        raise _Melding(_melding("Koppel twee verschillende tabellen: data_key en andere_key zijn dezelfde key."))
    links_df, rechts_df = _tabel(data_key), _tabel(andere_key)
    links_label, rechts_label = _labels(data_key, andere_key)
    links, p_links = _kolommen(links_label, links_df, sleutels, links_opgave, "kolommen_links")
    rechts, p_rechts = _kolommen(rechts_label, rechts_df, sleutels, rechts_opgave, "kolommen_rechts")
    if problemen := [*p_links, *p_rechts]:
        kandidaten = {links_label: _kandidaten(links_df), rechts_label: _kandidaten(rechts_df)}
        raise _Melding(_melding(" ".join(problemen), kandidaten=kandidaten))
    return _Kant(data_key, links_label, links_df, links), _Kant(andere_key, rechts_label, rechts_df, rechts)


def _genormaliseerd(kant: _Kant, sleutels: list[str], bezet: set[str]) -> pd.DataFrame:
    """De tabel met vooraan een kolom per sleutel in de vorm van onderwijsbronnen.sleutels; een eigen kolom met een
    naam die al bezet is (de sleutel, `koppelstatus`, een kolom van de andere tabel) krijgt het label ervoor."""
    df = kant.df.rename(columns={k: f"{kant.label}_{k}" for k in kant.df.columns if k in bezet})
    norm = {s: kant.df[kant.kolommen[s]].map(kern.SLEUTELS[s].normaliseer).astype(object) for s in sleutels}
    return pd.concat([pd.DataFrame(norm, index=df.index), df], axis=1)


def _korrel(df: pd.DataFrame, sleutels: list[str]) -> str:
    """Geeft de sleutel in deze tabel één rij per waarde (`one`) of meer (`many`)? Vgl. relaties._kardinaliteit."""
    return _VEEL if df.duplicated(subset=sleutels).any() else _EEN


def _koppel(links: _Kant, rechts: _Kant, sleutels: list[str]) -> _Uitkomst:
    """De outer join; een rij met een lege of onleesbare sleutel kan niet matchen en blijft met haar eigen status."""
    bezet = {*sleutels, KOPPELSTATUS}
    a = _genormaliseerd(links, sleutels, bezet | set(rechts.df.columns))
    b = _genormaliseerd(rechts, sleutels, bezet | set(links.df.columns))
    a_ok, b_ok = (t[t[sleutels].notna().all(axis=1)] for t in (a, b))
    # pd.merge koppelt NaN aan NaN: rijen zonder sleutel gaan er daarom buitenom.
    gekoppeld = a_ok.merge(b_ok, on=sleutels, how="outer", indicator=_HERKOMST)
    status = {"both": BEIDE, "left_only": links.alleen, "right_only": rechts.alleen}
    gekoppeld.insert(len(sleutels), KOPPELSTATUS, gekoppeld.pop(_HERKOMST).astype(str).map(status))
    los = [
        t.drop(t_ok.index).assign(**{KOPPELSTATUS: k.alleen}) for t, t_ok, k in ((a, a_ok, links), (b, b_ok, rechts))
    ]
    delen = [d for d in (gekoppeld, *los) if not d.empty] or [gekoppeld]
    kolommen = list(gekoppeld.columns)
    df = pd.concat(delen, ignore_index=True)[kolommen] if len(delen) > 1 else delen[0].reset_index(drop=True)
    return _Uitkomst(
        df=df,
        korrel={links.label: _korrel(a_ok, sleutels), rechts.label: _korrel(b_ok, sleutels)},
        uniek={
            links.label: len(a_ok[sleutels].drop_duplicates()),
            rechts.label: len(b_ok[sleutels].drop_duplicates()),
            "totaal": len(gekoppeld[sleutels].drop_duplicates()),
        },
        zonder_sleutel={
            k.label: n for k, t, t_ok in ((links, a, a_ok), (rechts, b, b_ok)) if (n := len(t) - len(t_ok))
        },
    )


def _koppelkey(links: _Kant, rechts: _Kant, df: pd.DataFrame) -> str:
    """Deterministisch: dezelfde twee tabellen, sleutels en kolommen geven dezelfde key."""
    plan = json.dumps([links.key, links.kolommen, rechts.key, rechts.kolommen])
    inhoud = f"{plan}{df.to_json(orient='split', default_handler=str)}"
    return f"koppel:{hashlib.sha256(inhoud.encode()).hexdigest()[:12]}"


def _stap(links: _Kant, rechts: _Kant, sleutels: list[str], korrel: str) -> str:
    return (
        f"{STAP} van {links.label} ({links.key}) en {rechts.label} ({rechts.key}) op "
        f"{', '.join(sleutels)}, outer join, korrel {korrel}"
    )


def _bewaar(key: str, df: pd.DataFrame, links: _Kant, rechts: _Kant, stap: str) -> bool:
    """De koppeling als afgeleide key van de eerste tabel, op beide gelezen (#977): zo noemt haar herkomst elke bron.

    Zoals analysis._bewaar: volledig alleen als beide tabellen volledig zijn, zo oud als de oudste.
    """
    gelezen = (links.key, rechts.key)
    metas = [m for k in gelezen if (m := store.meta(k)) is not None]
    volledig = all(store.volledig(k) for k in gelezen)
    titels = {k: v for m in reversed(metas) for k, v in (m.kolomtitels or {}).items()}
    store.derive(
        links.key,
        key,
        df,
        stap=stap,
        gelezen=gelezen,
        volledig=volledig,
        scriptconstanten=tuple(dict.fromkeys(c for m in metas for c in m.scriptconstanten)),
        **({"kolomtitels": titels} if titels else {}),
        **({"opgehaald_op": min(m.opgehaald_op for m in metas)} if metas else {}),
        **dekking.van(df, store.meta(links.key)),
    )
    return volledig


def _toelichting(links: _Kant, rechts: _Kant, sleutels: list[str], telling: dict[str, int]) -> dict[str, str]:
    """Per status die voorkomt wat ze betekent en welke reden het antwoord noemt."""
    op = ", ".join(sleutels)
    teksten = {BEIDE: f"Rij met een match in {links.label} en {rechts.label} op {op}."}
    for kant, ander in ((links, rechts), (rechts, links)):
        teksten[kant.alleen] = (
            f"Rij uit {kant.label} zonder rij in {ander.label} met dezelfde {op}: de kolommen van {ander.label} zijn "
            f"leeg, geen 0. Reden: {ander.label} is een andere bron die deze {op} niet telt, of heeft een andere "
            "afbakening (jaar, vorm, sector, selectie). Noem deze rijen en de reden in je antwoord."
        )
    return {status: tekst for status, tekst in teksten.items() if telling.get(status)}


def _waarschuwingen(links: _Kant, rechts: _Kant, sleutels: list[str], uitkomst: _Uitkomst) -> list[str]:
    uit = []
    for kant, ander in ((links, rechts), (rechts, links)):
        if uitkomst.korrel[kant.label] == _VEEL:
            uit.append(
                f"In {kant.label} geeft {', '.join(sleutels)} meer rijen per waarde (many): elke waarde van "
                f"{ander.label} staat dan per rij herhaald. Tel waarden van {ander.label} niet zonder meer op over "
                "de gekoppelde tabel; bekijk de korrel met dataset_profiel."
            )
    for kant, n in uitkomst.zonder_sleutel.items():
        uit.append(f"{n} rijen van {kant} hebben een lege of onleesbare sleutel: ze staan erin zonder match.")
    if any(kern.SLEUTELS[s].op_naam for s in sleutels):
        uit.append(relaties.NAAMWAARSCHUWING)
    return uit


def _telling(df: pd.DataFrame) -> dict[str, int]:
    return {str(k): int(v) for k, v in df[KOPPELSTATUS].value_counts(sort=False).items()}


def _tekst(key: str, links: _Kant, rechts: _Kant, sleutels: list[str], uitkomst: _Uitkomst, volledig: bool) -> str:
    df = uitkomst.df
    telling = _telling(df)
    rijen = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    uit: dict = {
        **(modelrijen(rijen, key, volledig) if rijen else {"data_key": key, "rijen": []}),
        "sleutels": sleutels,
        "kolommen": {links.label: links.kolommen, rechts.label: rechts.kolommen},
        "korrel": {**uitkomst.korrel, "koppeling": uitkomst.koppeling},
        "uniek": uitkomst.uniek,
        "telling": telling,
        "toelichting": _toelichting(links, rechts, sleutels, telling),
    }
    if uitkomst.zonder_sleutel:
        uit["zonder_sleutel"] = uitkomst.zonder_sleutel
    waarschuwingen: list[str] = [w for w in (uit.pop("waarschuwing", None),) if isinstance(w, str)]
    waarschuwingen += _waarschuwingen(links, rechts, sleutels, uitkomst)
    if waarschuwingen:
        uit["waarschuwing"] = " ".join(waarschuwingen)
    return json.dumps(uit, ensure_ascii=False, default=str)


def koppel_data(
    data_key: str,
    andere_key: str,
    sleutels: list[str],
    kolommen_links: dict[str, str] | None = None,
    kolommen_rechts: dict[str, str] | None = None,
) -> str:
    """Koppel twee geladen tabellen op `sleutels` (namen uit relatie), als outer join; het resultaat is een nieuwe key."""
    try:
        namen = _sleutelnamen(sleutels)
        links, rechts = _kanten(
            store.canoniek(data_key), store.canoniek(andere_key), namen, kolommen_links, kolommen_rechts
        )
    except _Melding as melding:
        return str(melding)
    uitkomst = _koppel(links, rechts, namen)
    key = _koppelkey(links, rechts, uitkomst.df)
    volledig = _bewaar(key, uitkomst.df, links, rechts, _stap(links, rechts, namen, uitkomst.koppeling))
    # Wat er gekoppeld is, zonder waarden (#475): de sleutels, de korrel en de telling per status.
    telling = _telling(uitkomst.df)
    logger.info(
        "KOPPEL sleutels=%s korrel=%s beide=%d links=%d rechts=%d",
        ",".join(namen),
        uitkomst.koppeling,
        telling.get(BEIDE, 0),
        telling.get(links.alleen, 0),
        telling.get(rechts.alleen, 0),
    )
    return _tekst(key, links, rechts, namen, uitkomst, volledig)
