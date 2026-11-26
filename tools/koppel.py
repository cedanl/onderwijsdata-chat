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
from dataclasses import dataclass, replace
from itertools import combinations, islice

import numpy as np
import pandas as pd
from onderwijsbronnen import skdb as skdbbron
from onderwijsbronnen import sleutels as kern

from . import dekking, fouten, opvolger, relaties, store, studiekeuze
from .analysis import modelrijen, rijmaximum
from .kolomlabel import is_labelkolom

logger = logging.getLogger(__name__)

KOPPELSTATUS = "koppelstatus"
STAP = "koppeling (koppel_data)"  # het begin van KeyMeta.stap: zo noemt de herkomst de stap
BEIDE = "beide"
_HERKOMST = "__koppel_herkomst"  # de indicatorkolom van pd.merge; komt nooit in het resultaat
_EEN, _VEEL = "one", "many"
# SKDB naast DUO (#1231): per SKDB-rij de vlag van de kleine-n-regel van get_studiekeuze, en de SKDB-rijen zonder
# DUO-rij per graad. De code telt; het model neemt over.
ONZEKER = "onzeker"
PER_GRAAD = "niet_gekoppeld_per_graad"
GEEN_GRAAD = "onbekend"
_GRADEN = ("bachelor", "master", "associate degree")
# "Alle opleidingen" van een instelling (#1274): ook de rijen `beide` per graad, per graad met het aantal met een
# NSE-score en het aantal onzeker, en de rijen `alleen DUO` met een vaste reden. De delen tellen op tot de telling.
GEKOPPELD_PER_GRAAD = "gekoppeld_per_graad"
ALLEEN_DUO = "alleen_duo"
REDEN_ALLEEN_DUO = "alleen in DUO: de Studiekeuzedatabase heeft geen opleiding met deze brin en croho"
# Zoveel opleidingen `alleen DUO` noemt het resultaat hooguit; het aantal rijen staat er altijd volledig in. Een
# DUO-tabel van alle instellingen naast de SKDB van één instelling geeft er duizenden.
MAX_ALLEEN_DUO = 50
# Zoveel rijen mag een koppeling hooguit geven. De koppeling draait in het serverproces, niet in de sandbox van
# run_analysis (1 GiB, 10 s): veel-op-veel op een grove sleutel (alleen schooljaar of brin) is een kruisproduct per
# waarde en groeit kwadratisch (2 x 1500 rijen op één waarde: 2,25 miljoen rijen, 1 GB). Daarom eerst tellen, dan
# koppelen. Dezelfde orde als relaties._MAX_WAARDEN; een één-op-veel van twee gewone loads blijft er ver onder.
# Rijen alleen is niet genoeg: een brede koppeling onder MAX_RIJEN kan toch te groot zijn, zie MAX_CELLEN.
MAX_RIJEN = 200_000
# Zoveel cellen (rijen x kolommen) mag een koppeling hooguit geven, ook onder MAX_RIJEN (#1011). Twee tabellen van 447
# rijen met 40 tekstkolommen op één brin gaven 199.809 rijen x 81 kolommen: ruim 16 miljoen cellen, in de store
# ongeveer 1.070 MB (zo'n 67 bytes per tekstcel), boven STORE_MAX_MB (512), en de store gooide elke andere key weg.
# 5 miljoen tekstcellen is ongeveer 335 MB, onder die grens met ruimte over; een één-op-veel van twee gewone loads
# (honderdduizenden rijen x zo'n 10 kolommen) blijft eronder.
MAX_CELLEN = 5_000_000
# Veel-op-veel (n:m) gaat nooit door, ook klein niet (#1031): meting #1009 gaf geen enkele zinnige n:m-koppeling. De
# melding noemt per kant de korrelkolommen. De zoeker draait alleen bij een weigering, in het serverproces: exact voor
# één en twee kolommen (hooguit _MAX_PAREN paren), daarna gulzig tot hooguit _MAX_KORREL kolommen; zo blijft hij
# lineair in de rijen.
_MAX_PAREN = 200
_MAX_KORREL = 8


class _Melding(Exception):
    """De koppeling gaat niet door; de tekst is de melding voor het model. Er komt niets in de store."""


@dataclass(frozen=True)
class _Kant:
    """Eén tabel van de koppeling: haar key, haar label in `koppelstatus`, de kolom per sleutel en per sleutel alle
    kolommen die hem dragen (`_kandidaten`)."""

    key: str
    label: str
    df: pd.DataFrame
    kolommen: dict[str, str]
    kandidaten: dict[str, list[str]]

    @property
    def alleen(self) -> str:
        return f"alleen {self.label}"


@dataclass(frozen=True)
class _Uitkomst:
    df: pd.DataFrame
    korrel: dict[str, str]
    kardinaliteit: str
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


def _is_koppeling(key: str) -> bool:
    known = store.meta(key)
    return known is not None and (known.stap or "").startswith(STAP)


def _gelijke_kolom(df: pd.DataFrame, sleutel: str, opties: list[str]) -> str | None:
    """De bronkolom als een sleutel in een kolom en haar labelkolommen staat met dezelfde waarden (#1032), anders None.

    DUO-ho heeft STUDIEJAAR (2021) en STUDIEJAAR_LABEL (2021/2022): na normalisatie in elke rij gelijk (leeg is gelijk
    aan leeg), dus één sleutel. Twee bronkolommen (INSTELLINGSCODE en INSTELLINGSCODE_ACTUEEL) blijven een keuze voor het
    model, ook als ze nu gelijk zijn: ze betekenen niet hetzelfde.
    """
    bron = [k for k in opties if not is_labelkolom(k)]
    if len(bron) > 1:
        return None
    normaliseer = kern.SLEUTELS[sleutel].normaliseer
    eerste, *rest = (df[k].map(normaliseer).astype(object) for k in opties)
    return (bron or opties)[0] if all(eerste.equals(r) for r in rest) else None


def _kolommen(
    kant: tuple[str, str],
    df: pd.DataFrame,
    kandidaten: dict[str, list[str]],
    sleutels: list[str],
    opgave: object,
    veld: str,
):
    """De kolom per sleutel in één tabel, en wat er niet klopt; een opgave kiest uit de kandidaten, nooit daarbuiten.

    Een eerdere koppeling (ketenen) heeft de sleutel twee keer: de oorspronkelijke kolom en vooraan de genormaliseerde
    onder de sleutelnaam. Die laatste is dan de keuze, zonder melding. Een kolom met haar labelkolom en dezelfde waarden
    ook (`_gelijke_kolom`).
    """
    key, label = kant
    voorkeur = _is_koppeling(key)
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
        elif gekozen is None and len(opties) > 1 and not (voorkeur and sleutel in opties):
            if (gelijk := _gelijke_kolom(df, sleutel, opties)) is not None:
                kolommen[sleutel] = gelijk
                continue
            problemen.append(
                f"Sleutel {sleutel} staat in {label} in meer kolommen: {opties}. Kies er één met "
                f'{veld}: {{"{sleutel}": "<kolom>"}}.'
            )
        else:
            kolommen[sleutel] = gekozen or (sleutel if voorkeur and sleutel in opties else opties[0])
    return kolommen, problemen


def _kanten(data_key: str, andere_key: str, opgegeven: object, links_opgave, rechts_opgave) -> tuple[_Kant, _Kant]:
    """Beide tabellen met hun kolom per sleutel. Een onbekende key gaat voor elke andere melding: dezelfde foutcode
    als bij elke tool met een data_key (tests/test_tool_keten_contract.py)."""
    links_df, rechts_df = _tabel(data_key), _tabel(andere_key)
    if data_key == andere_key:
        raise _Melding(_melding("Koppel twee verschillende tabellen: data_key en andere_key zijn dezelfde key."))
    sleutels = _sleutelnamen(opgegeven)
    links_label, rechts_label = _labels(data_key, andere_key)
    k_links, k_rechts = _kandidaten(links_df), _kandidaten(rechts_df)
    links, p_links = _kolommen((data_key, links_label), links_df, k_links, sleutels, links_opgave, "kolommen_links")
    rechts, p_rechts = _kolommen(
        (andere_key, rechts_label), rechts_df, k_rechts, sleutels, rechts_opgave, "kolommen_rechts"
    )
    if problemen := [*p_links, *p_rechts]:
        raise _Melding(_melding(" ".join(problemen), kandidaten={links_label: k_links, rechts_label: k_rechts}))
    return (
        _Kant(data_key, links_label, links_df, links, k_links),
        _Kant(andere_key, rechts_label, rechts_df, rechts, k_rechts),
    )


def _bezet(sleutels: list[str], ander: _Kant) -> set[str]:
    """De namen die een kolom van de ene kant niet mag houden: de sleutels, `koppelstatus` en de kolommen van de andere."""
    return {*sleutels, KOPPELSTATUS} | set(ander.df.columns)


def _hernoeming(kant: _Kant, bezet: set[str]) -> dict[str, str]:
    """Een eigen kolom met een naam die al bezet is, krijgt het label ervoor, zo vaak als nodig: een eerdere koppeling
    heeft zelf al `SKDB_brin` naast `brin`. Alleen de kolommen die een andere naam krijgen."""
    genomen = set(kant.df.columns) | bezet
    nieuw: dict[str, str] = {}
    for k in kant.df.columns:
        if k in bezet:
            naam = f"{kant.label}_{k}"
            while naam in genomen:
                naam = f"{kant.label}_{naam}"
            nieuw[k] = naam
            genomen.add(naam)
    return nieuw


def _genormaliseerd(kant: _Kant, sleutels: list[str], bezet: set[str]) -> pd.DataFrame:
    """De tabel met vooraan een kolom per sleutel in de vorm van onderwijsbronnen.sleutels; een eigen kolom met een
    naam die al bezet is (de sleutel, `koppelstatus`, een kolom van de andere tabel) heet zoals _hernoeming zegt."""
    df = kant.df.rename(columns=_hernoeming(kant, bezet))
    norm = {s: kant.df[kant.kolommen[s]].map(kern.SLEUTELS[s].normaliseer).astype(object) for s in sleutels}
    return pd.concat([pd.DataFrame(norm, index=df.index), df], axis=1)


def _korrel(df: pd.DataFrame, sleutels: list[str]) -> str:
    """Geeft de sleutel in deze tabel één rij per waarde (`one`) of meer (`many`)? Vgl. relaties._kardinaliteit."""
    return _VEEL if df.duplicated(subset=sleutels).any() else _EEN


@dataclass(frozen=True)
class _Tellingen:
    """Rijen per sleutelwaarde aan elke kant, uitgelijnd over de vereniging (NaN: de waarde ontbreekt aan die kant).

    Eén telling per tabel, voor de omvang, de n:m-weigering en de kardinaliteit samen.
    """

    links: pd.Series
    rechts: pd.Series

    @classmethod
    def van(cls, a_ok: pd.DataFrame, b_ok: pd.DataFrame, sleutels: list[str]) -> "_Tellingen":
        links, rechts = (t.value_counts(subset=sleutels, sort=False) for t in (a_ok, b_ok))
        alle = links.index.union(rechts.index)
        return cls(links.reindex(alle), rechts.reindex(alle))

    @property
    def rijen(self) -> int:
        """Per gedeelde waarde links x rechts, anders het aantal van de kant die haar heeft."""
        return int((self.links.fillna(1) * self.rechts.fillna(1)).to_numpy(dtype="int64").sum())

    @property
    def nm_waarden(self) -> int:
        """Hoeveel gedeelde waarden aan beide kanten meer dan één rij hebben (NaN > 1 is False)."""
        return int(((self.links > 1) & (self.rechts > 1)).sum())

    @property
    def kardinaliteit(self) -> str:
        """1:1, n:1 of 1:n, links eerst, op de gedeelde waarden; n:m komt na de weigering niet meer voor."""
        gedeeld = self.links.notna() & self.rechts.notna()
        links, rechts = ("n" if (t[gedeeld] > 1).any() else "1" for t in (self.links, self.rechts))
        return f"{links}:{rechts}"


def omvang(a_ok: pd.DataFrame, b_ok: pd.DataFrame, sleutels: list[str]) -> int:
    """Hoeveel rijen de outer join geeft, zonder hem te maken: per gedeelde waarde links x rechts, anders het aantal
    van de kant die haar heeft. Kost één telling per tabel."""
    return _Tellingen.van(a_ok, b_ok, sleutels).rijen


# --- Korrelkolommen: wat maakt een rij eenduidig (#1031) ------------------------------------------------------------


def _codes(reeks: pd.Series) -> np.ndarray | None:
    """De waarden als groepsnummers 0..k-1, leeg als eigen waarde (zoals df.duplicated); None als ze niet te hashen
    zijn (een lijst in een cel)."""
    try:
        return pd.factorize(reeks, use_na_sentinel=False)[0].astype("int64")
    except TypeError:
        return None


def _samen(groep: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """De indeling naar groep én codes, weer als groepsnummers 0..k-1."""
    return pd.factorize(groep * (int(codes.max(initial=-1)) + 1) + codes)[0]


def _dubbel(groep: np.ndarray) -> int:
    """Hoeveel rijen een groep delen met een eerdere rij: 0 is elke rij uniek."""
    return len(groep) - (int(groep.max()) + 1 if len(groep) else 0)


def _uniek_met(groep: np.ndarray, codes: dict[str, np.ndarray], kolommen: list[str]) -> bool:
    for k in kolommen:
        groep = _samen(groep, codes[k])
    return not _dubbel(groep)


def _kleinste(groep: np.ndarray, codes: dict[str, np.ndarray], kandidaten: list[str]) -> list[str] | None:
    """Exact: de eerste kolom, anders het eerste paar, dat elke rij uniek maakt; anders None.

    Een paar dat te weinig waarden heeft om elke rij te onderscheiden, wordt overgeslagen; hooguit _MAX_PAREN paren
    worden echt geteld.
    """
    met = {k: _samen(groep, codes[k]) for k in kandidaten}
    if (een := next((k for k in kandidaten if not _dubbel(met[k])), None)) is not None:
        return [een]
    aantal = {k: int(c.max(initial=-1)) + 1 for k, c in codes.items()}
    met_aantal = {k: int(c.max(initial=-1)) + 1 for k, c in met.items()}
    paren = ((i, j) for i, j in combinations(kandidaten, 2) if met_aantal[i] * aantal[j] >= len(groep))
    for i, j in islice(paren, _MAX_PAREN):
        if not _dubbel(_samen(met[i], codes[j])):
            return [i, j]
    return None


def _gulzig(groep: np.ndarray, codes: dict[str, np.ndarray], pools: list[list[str]]) -> list[str]:
    """Telkens de kolom die de meeste dubbele rijen wegneemt (bij gelijkspel de eerste), eerst uit de eerste pool;
    tot elke rij uniek is, geen kolom meer helpt of er _MAX_KORREL gekozen zijn."""
    gekozen: list[str] = []
    for pool in pools:
        while _dubbel(groep) and len(gekozen) < _MAX_KORREL:
            nog = np.bincount(groep)[groep] > 1  # een rij die al uniek is, blijft dat: alleen de rest telt
            groep, codes = pd.factorize(groep[nog])[0], {k: c[nog] for k, c in codes.items()}
            scores = [(_dubbel(_samen(groep, codes[k])), k) for k in pool if k not in gekozen]
            beste = min(scores, key=lambda paar: paar[0], default=None)
            if beste is None or beste[0] >= _dubbel(groep):
                break
            gekozen.append(beste[1])
            groep = _samen(groep, codes[beste[1]])
    return gekozen


def _gesnoeid(groep: np.ndarray, codes: dict[str, np.ndarray], gekozen: list[str]) -> list[str]:
    """Zonder de gulzig gekozen kolommen die achteraf niet nodig zijn."""
    for k in list(gekozen):
        zonder = [c for c in gekozen if c != k]
        if _uniek_met(groep, codes, zonder):
            gekozen = zonder
    return gekozen


def _korrelkandidaten(kant: _Kant, gedeeld: set[str]) -> tuple[list[str], list[str]]:
    """De kolommen die de korrel kunnen dragen, in zoekvolgorde, en het deel dat een dimensie is.

    Eerst een kolom met een sleutel die beide tabellen dragen (een code voor een naam), dan de andere kolommen in
    kolomvolgorde; `koppelstatus` en de gekozen sleutelkolommen tellen niet mee. Een getal zonder sleutel (AANTAL, een
    CBS-meetwaarde) is een waarde, geen korrel: het komt pas in aanmerking als de dimensies de rijen niet uniek maken.
    """
    draagt: dict[str, list[str]] = {}
    for sleutel, kolommen in kant.kandidaten.items():
        for k in kolommen:
            draagt.setdefault(k, []).append(sleutel)

    def rang(kolom: str) -> int:
        eigen = draagt.get(kolom, [])
        if any(s in gedeeld and not kern.SLEUTELS[s].op_naam for s in eigen):
            return 0
        if any(s in gedeeld for s in eigen):
            return 1
        reeks = kant.df[kolom]
        getal = pd.api.types.is_numeric_dtype(reeks) and not pd.api.types.is_bool_dtype(reeks)
        return 3 if getal and not eigen else 2

    uit = {KOPPELSTATUS, *kant.kolommen.values()}
    kandidaten = sorted((k for k in kant.df.columns if k not in uit), key=rang)
    return kandidaten, [k for k in kandidaten if rang(k) < 3]


def _eigen(kant: _Kant, t_ok: pd.DataFrame, sleutels: list[str]) -> pd.DataFrame:
    """De rijen met een sleutel onder hun eigen kolomnamen, zonder de genormaliseerde sleutels vooraan: zo noemt de
    melding de kolommen die het model in query_data kent (_genormaliseerd hernoemt alleen, in dezelfde volgorde)."""
    return t_ok.iloc[:, len(sleutels) :].set_axis(list(kant.df.columns), axis=1)


def _korrelkolommen(kant: _Kant, t_ok: pd.DataFrame, sleutels: list[str], gedeeld: set[str]) -> tuple[list[str], bool]:
    """De kolommen die samen met de sleutels elke rij van deze kant uniek maken, en of dat lukt.

    Zo klein als bekend: exact voor één en twee kolommen, daarna gulzig en gesnoeid; deterministisch. Zijn rijen
    volledig gelijk, dan is de lijst onvolledig (False). Werkt op de rijen met een sleutel, met de eigen kolomnamen.
    """
    eigen = _eigen(kant, t_ok, sleutels)
    groep = t_ok.groupby(sleutels, sort=False).ngroup().to_numpy()
    kandidaten, dimensies = _korrelkandidaten(kant, gedeeld)
    codes = {k: c for k in kandidaten if (c := _codes(eigen[k])) is not None}
    pools = [[k for k in dimensies if k in codes], [k for k in kandidaten if k in codes]]
    gekozen = _kleinste(groep, codes, pools[0]) if _dubbel(groep) else []
    if gekozen is None:
        gekozen = _gesnoeid(groep, codes, _gulzig(groep, codes, pools))
    return gekozen, _uniek_met(groep, codes, gekozen)


# --- De n:m-melding ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Korrel:
    """De korrelkolommen van één kant en of ze elke rij uniek maken."""

    kant: _Kant
    t_ok: pd.DataFrame
    kolommen: list[str]
    volledig: bool

    def sleutelkolom(self, sleutel: str) -> str | None:
        """De korrelkolom die `sleutel` draagt, of None."""
        return next((k for k in self.kolommen if k in self.kant.kandidaten.get(sleutel, [])), None)


def _ook_op(korrels: tuple[_Korrel, _Korrel], gedeeld: set[str]) -> list[str]:
    """De sleutels die een korrelkolom aan beide kanten draagt, in de volgorde van de linker korrel."""
    links, rechts = korrels
    if not (links.volledig and rechts.volledig):
        return []
    volgorde = [s for k in links.kolommen for s, kolommen in links.kant.kandidaten.items() if k in kolommen]
    return [s for s in dict.fromkeys(volgorde) if s in gedeeld and rechts.sleutelkolom(s) is not None]


def _nog_nm(korrels: tuple[_Korrel, _Korrel], sleutels: list[str], ook: list[str]) -> int:
    """Hoeveel gedeelde waarden ook op de uitgebreide sleutels nog n:m zijn (een rij zonder de extra sleutel valt af)."""
    delen = []
    for korrel in korrels:
        eigen = _eigen(korrel.kant, korrel.t_ok, sleutels)
        extra = {s: eigen[korrel.sleutelkolom(s)].map(kern.SLEUTELS[s].normaliseer).astype(object) for s in ook}
        delen.append(korrel.t_ok[sleutels].assign(**extra).dropna())
    return _Tellingen.van(*delen, [*sleutels, *ook]).nm_waarden


def _is_cbs(kant: _Kant) -> bool:
    known = store.meta(kant.key)
    return known is not None and known.bron.lower() == "cbs"


def _aggregeren(links: _Kant, rechts: _Kant, op: str) -> str:
    tekst = (
        f"Maak eerst één kant één rij per {op}: aggregeer met query_data (group_by op de sleutelkolom, aggregate som "
        "van de aantallen) en koppel die data_key"
    )
    if cbs := [k.label for k in (links, rechts) if _is_cbs(k)]:
        tekst += (
            f", of zet bij {' en '.join(cbs)} de andere dimensies op hun totaalcode (selectie in get_cbs_data, of een "
            "filter in query_data)"
        )
    return f"{tekst}."


def _korrel_van(kant: _Kant, t_ok: pd.DataFrame, sleutels: list[str], gedeeld: set[str]) -> _Korrel:
    return _Korrel(kant, t_ok, *_korrelkolommen(kant, t_ok, sleutels, gedeeld))


def _nm_melding(
    links: _Kant,
    rechts: _Kant,
    sleutels: list[str],
    oks: tuple[pd.DataFrame, pd.DataFrame],
    tellingen: _Tellingen,
    rijen: int,
) -> _Melding:
    """De weigering van een veel-op-veel-koppeling, met per kant de korrelkolommen en een route die wel werkt.

    `rijen` is wat de join zou geven (zoals voor de grenzen): `verwachte_rijen`."""
    gedeeld = (set(links.kandidaten) & set(rechts.kandidaten)) - set(sleutels)
    korrels = (_korrel_van(links, oks[0], sleutels, gedeeld), _korrel_van(rechts, oks[1], sleutels, gedeeld))
    op, nm = ", ".join(sleutels), tellingen.nm_waarden
    tekst = (
        f"Deze koppeling op {op} is veel-op-veel (n:m): bij {nm} waarden van {op} hebben {links.label} en "
        f"{rechts.label} allebei meer dan één rij, en elke rij van de ene kant zou bij elke rij van de andere kant "
        f"komen ({rijen} rijen, met dubbele waarden). Er is niets gekoppeld. korrel_kolommen noemt per kant de "
        f"kolommen die samen met {op} één rij aanwijzen."
    )
    for korrel in korrels:
        if not korrel.volledig:
            tekst += (
                f" In {korrel.kant.label} maakt geen kolomkeuze elke rij eenduidig: rijen zijn volledig gelijk, of "
                f"verschillen pas in meer dan {_MAX_KORREL} kolommen."
            )
    if ook := _ook_op(korrels, gedeeld):
        tekst += (
            f" Koppel ook op {', '.join(ook)}: sleutels={json.dumps([*sleutels, *ook])}. Die kolommen dragen in beide "
            "tabellen dezelfde sleutel; controleer met relatie dat ze hetzelfde betekenen"
        )
        if any(_is_cbs(k) for k in (links, rechts)):
            tekst += " (bij DUO en CBS is gemeente bijvoorbeeld vestigingsgemeente tegenover woongemeente)"
        tekst += "."
        if rest := _nog_nm(korrels, sleutels, ook):
            tekst += f" Ook dan hebben nog {rest} waarden aan beide kanten meer rijen. {_aggregeren(links, rechts, op)}"
    else:
        tekst += f" {_aggregeren(links, rechts, op)}"
    return _Melding(
        _melding(
            tekst,
            kardinaliteit="n:m",
            verwachte_rijen=rijen,
            nm_waarden=nm,
            korrel_kolommen={k.kant.label: k.kolommen for k in korrels},
        )
    )


def _te_groot(
    links: _Kant, rechts: _Kant, sleutels: list[str], rijen: int, kolommen: int, korrel: str
) -> _Melding | None:
    """De melding als de koppeling boven MAX_RIJEN of MAX_CELLEN uitkomt, anders None. Eén melding: de rijgrens gaat
    voor, want dan is het een kruisproduct en helpen minder kolommen niet."""
    cellen = rijen * kolommen
    if rijen > MAX_RIJEN:
        grens = (
            f"{rijen} rijen geven (korrel {korrel}), meer dan {MAX_RIJEN}: elke waarde van {links.label} staat dan "
            f"bij elke rij van {rechts.label} met dezelfde sleutel."
        )
        kolomtip = ""
    elif cellen > MAX_CELLEN:
        grens = (
            f"{rijen} rijen van {kolommen} kolommen geven, {cellen} cellen (korrel {korrel}), meer dan {MAX_CELLEN} "
            f"cellen: elke rij draagt de kolommen van {links.label} en {rechts.label} samen."
        )
        kolomtip = " Houd met columns in query_data alleen de kolommen die je nodig hebt."
    else:
        return None
    return _Melding(
        _melding(
            f"Deze koppeling op {', '.join(sleutels)} zou {grens} Er is niets gekoppeld. Koppel op meer sleutels "
            "(zie relatie, bijv. ook croho of schooljaar) of maak een tabel eerst kleiner met query_data (filters, "
            f"group_by) en koppel die data_key.{kolomtip}",
            verwachte_rijen=rijen,
            verwachte_cellen=cellen,
            korrel=korrel,
        )
    )


def _koppel(links: _Kant, rechts: _Kant, sleutels: list[str]) -> _Uitkomst:
    """De outer join; een rij met een lege of onleesbare sleutel kan niet matchen en blijft met haar eigen status.

    Een veel-op-veel-koppeling gaat nooit door, een join boven MAX_RIJEN of MAX_CELLEN ook niet (_Melding): eerst
    tellen, dan pas koppelen.
    """
    a = _genormaliseerd(links, sleutels, _bezet(sleutels, rechts))
    b = _genormaliseerd(rechts, sleutels, _bezet(sleutels, links))
    a_ok, b_ok = (t[t[sleutels].notna().all(axis=1)] for t in (a, b))
    tellingen = _Tellingen.van(a_ok, b_ok, sleutels)
    rijen = tellingen.rijen + (len(a) - len(a_ok)) + (len(b) - len(b_ok))
    if tellingen.nm_waarden:
        raise _nm_melding(links, rechts, sleutels, (a_ok, b_ok), tellingen, rijen)
    korrel = {links.label: _korrel(a_ok, sleutels), rechts.label: _korrel(b_ok, sleutels)}
    # De sleutels één keer, plus koppelstatus, plus onzeker bij SKDB naast DUO (_skdb_signalen).
    kolommen = len(a.columns) + len(b.columns) - len(sleutels) + 1 + int(_met_onzeker(links, rechts, sleutels))
    melding = _te_groot(links, rechts, sleutels, rijen, kolommen, "_to_".join(korrel.values()))
    if melding is not None:
        raise melding
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
        korrel=korrel,
        kardinaliteit=tellingen.kardinaliteit,
        uniek={
            links.label: len(a_ok[sleutels].drop_duplicates()),
            rechts.label: len(b_ok[sleutels].drop_duplicates()),
            "totaal": len(gekoppeld[sleutels].drop_duplicates()),
        },
        zonder_sleutel={
            k.label: n for k, t, t_ok in ((links, a, a_ok), (rechts, b, b_ok)) if (n := len(t) - len(t_ok))
        },
    )


def _skdb_duo(links: _Kant, rechts: _Kant, sleutels: list[str]) -> tuple[_Kant, _Kant] | None:
    """De SKDB- en de DUO-kant bij SKDB naast DUO op precies brin + croho, geen van beide zelf een koppeling; anders
    None."""
    if set(sleutels) != {"brin", "croho"}:
        return None
    bron = {k.key: m.bron.lower() for k in (links, rechts) if (m := store.meta(k.key)) and not _is_koppeling(k.key)}
    skdb = next((k for k in (links, rechts) if bron.get(k.key) == "skdb"), None)
    duo = next((k for k in (links, rechts) if bron.get(k.key) == "duo"), None)
    return (skdb, duo) if skdb and duo else None


def _opvolgers(links: _Kant, rechts: _Kant, sleutels: list[str], uitkomst: _Uitkomst) -> tuple[_Uitkomst, dict]:
    """SKDB naast DUO op brin + croho: per SKDB-rij zonder DUO-rij de reden uit RIO (#1060, `tools/opvolger.py`).

    Een andere koppeling (andere bronnen, andere sleutels, of een kant die zelf een koppeling is) raakt RIO niet aan.
    """
    paar = _skdb_duo(links, rechts, sleutels)
    tabel = opvolger.DuoTabel.van(paar[1].df, paar[1].kolommen, store.meta(paar[1].key)) if paar else None
    if paar is None or tabel is None:
        return uitkomst, {}
    df, extra = opvolger.bij_koppeling(uitkomst.df, KOPPELSTATUS, paar[0].alleen, tabel)
    return replace(uitkomst, df=df), extra


def _met_onzeker(links: _Kant, rechts: _Kant, sleutels: list[str]) -> bool:
    """Krijgt de koppeling de kolom `onzeker`: SKDB naast DUO, de SKDB-kant heeft een NSE-cijfer en geen van beide
    tabellen heeft zelf een kolom met die naam. Ook de celtelling vooraf rekent haar mee."""
    paar = _skdb_duo(links, rechts, sleutels)
    if paar is None or any(ONZEKER in k.df.columns for k in paar):
        return False
    return any(k in paar[0].df.columns for k in studiekeuze.NSE_CIJFERS)


def _graadsoort(waarde: object) -> str:
    """De graad van een SKDB-rij als sleutel van PER_GRAAD: bachelor, master, associate degree (ook 'ad'); een andere
    waarde in kleine letters, een lege onder GEEN_GRAAD. Nooit weggelaten."""
    tekst = str(waarde).strip().lower() if isinstance(waarde, str) else ""
    if not tekst:
        return GEEN_GRAAD
    return skdbbron.overzicht.GRADEN.get(tekst, tekst).lower()


def _per_graad(graad: pd.Series, met_score: pd.Series | None, onzeker: pd.Series) -> dict[str, dict[str, int]]:
    """Per graadsoort het aantal rijen en, als de SKDB-kant NSE-cijfers heeft, het aantal met een NSE-cijfer en het
    aantal onzeker (#1274): eerst bachelor, master, associate degree, dan de rest op naam. Dezelfde index overal."""
    tabel = pd.DataFrame({"graad": graad.map(_graadsoort), "onzeker": onzeker})
    velden = {"rijen": ("graad", "size")}
    if met_score is not None:
        tabel["met_score"] = met_score
        velden |= {"met_score": ("met_score", "sum"), "onzeker": ("onzeker", "sum")}
    tel = tabel.groupby("graad", sort=False).agg(**velden)
    volgorde = [*(g for g in _GRADEN if g in tel.index), *sorted(g for g in tel.index if g not in _GRADEN)]
    return {g: {k: int(tel.at[g, k]) for k in velden} for g in volgorde}


def _alleen_duo(df: pd.DataFrame, status: str, sleutels: list[str]) -> dict:
    """De rijen `alleen DUO` (#1274): hun aantal, en per opleiding (de sleutels, hooguit MAX_ALLEEN_DUO) de vaste
    reden. Een DUO-rij die vaker voorkomt (meer jaren) staat er één keer in; `rijen` telt ze allemaal."""
    rijen = df.loc[df[KOPPELSTATUS] == status, sleutels]
    uniek = rijen.drop_duplicates()
    getoond = uniek.head(MAX_ALLEEN_DUO).astype(object)
    opleidingen = getoond.where(getoond.notna(), None).to_dict(orient="records")
    uit: dict = {"rijen": len(rijen), "opleidingen": [{**o, "reden": REDEN_ALLEEN_DUO} for o in opleidingen]}
    if len(uniek) > len(getoond):
        uit["niet_getoond"] = len(uniek) - len(getoond)
    return uit


def _onzekerheid(df: pd.DataFrame, van_skdb: pd.Series, nse: dict[str, str]) -> list[bool | None]:
    """Per rij de vlag van studiekeuze.is_onzeker voor een SKDB-rij, None voor een rij zonder SKDB-kant. `nse` zegt per
    NSE-kolom van de SKDB hoe ze in de koppeling heet."""
    rijen = df[list(nse.values())].set_axis(list(nse), axis=1).to_dict(orient="records")
    return [bool(studiekeuze.is_onzeker(r)) if s else None for r, s in zip(rijen, van_skdb, strict=True)]


def _skdb_signalen(links: _Kant, rechts: _Kant, sleutels: list[str], uitkomst: _Uitkomst) -> tuple[_Uitkomst, dict]:
    """SKDB naast DUO op brin + croho (#1231): de kleine-n-vlag per SKDB-rij en de SKDB-rijen zonder DUO-rij per graad,
    in code. Bij HU telde het model zelf: een opleiding met 28 respondenten heette niet onzeker, en 31 opleidingen
    zonder DUO-rij heetten "bijna allemaal masters".

    De kolom `onzeker` (na `koppelstatus` en een `koppelreden`) volgt dezelfde regel als get_studiekeuze
    (`studiekeuze.is_onzeker`, MIN_RESPONDENTEN): true of false bij een SKDB-rij, leeg bij een rij alleen uit DUO. Alleen
    als de SKDB-kant een NSE-cijfer heeft en geen tabel een eigen kolom `onzeker` (_met_onzeker).
    `niet_gekoppeld_per_graad` telt de rijen `alleen SKDB` per `graad`, `gekoppeld_per_graad` de rijen `beide` (#1274),
    elk per graad met `rijen`, `met_score` (een NSE-cijfer) en `onzeker` (dezelfde regel, ook als de tabel een eigen
    kolom onzeker heeft); `alleen_duo` noemt de rijen `alleen DUO` met een vaste reden. De delen tellen op tot hun
    `telling`. Koppelen op alleen croho (#1273) krijgt dit nog niet. Andere koppelingen blijven zoals ze waren.
    """
    paar = _skdb_duo(links, rechts, sleutels)
    if paar is None:
        return uitkomst, {}
    skdb, duo = paar
    hernoemd = _hernoeming(skdb, _bezet(sleutels, duo))
    naam = {k: hernoemd.get(k, k) for k in skdb.df.columns}
    df, extra, toelichting = uitkomst.df, {}, {}
    statussen = (BEIDE, skdb.alleen)
    van_skdb = df[KOPPELSTATUS].isin(statussen)
    nse = {k: naam[k] for k in ("nse_respondenten", *studiekeuze.NSE_CIJFERS) if k in naam}
    vlag = _onzekerheid(df, van_skdb, nse)
    # Per rij: een NSE-cijfer (oordeel of thema) en de vlag; telt ook als de SKDB-tabel een eigen kolom onzeker heeft.
    cijfers = [nse[k] for k in studiekeuze.NSE_CIJFERS if k in nse]
    met_score = df[cijfers].notna().any(axis=1) if cijfers else None
    onzeker = pd.Series([v is True for v in vlag], index=df.index)
    if _met_onzeker(links, rechts, sleutels):
        na = [k for k in (KOPPELSTATUS, opvolger.KOPPELREDEN) if k in df.columns][-1]
        df = df.copy()
        df.insert(list(df.columns).index(na) + 1, ONZEKER, vlag)
        zin = (
            f"Een rij met {ONZEKER}: true heeft minder dan {studiekeuze.MIN_RESPONDENTEN} NSE-respondenten of geen "
            "bekend aantal: noem het NSE-oordeel en de thema's van die rij onzeker. De code zette de vlag; neem haar "
            "over en tel de respondenten niet zelf."
        )
        toelichting = {s: zin for s in statussen if (df[KOPPELSTATUS] == s).any()}
    alleen = df[KOPPELSTATUS] == skdb.alleen
    if "graad" in naam and alleen.any():
        extra[PER_GRAAD] = _per_graad(df.loc[alleen, naam["graad"]], _deel(met_score, alleen), onzeker[alleen])
        velden = ", met per graad rijen, met_score (een NSE-cijfer) en onzeker" if cijfers else ""
        zin = (
            f"{PER_GRAAD} telt deze rijen per graad (bachelor, master, associate degree; zonder graad: {GEEN_GRAAD})"
            f"{velden}, in code: noem die aantallen zoals ze er staan en tel de rijen niet zelf."
        )
        toelichting[skdb.alleen] = f"{toelichting.get(skdb.alleen, '')} {zin}".strip()
    beide = df[KOPPELSTATUS] == BEIDE
    if "graad" in naam and beide.any():
        extra[GEKOPPELD_PER_GRAAD] = _per_graad(df.loc[beide, naam["graad"]], _deel(met_score, beide), onzeker[beide])
        toelichting[BEIDE] = f"{toelichting.get(BEIDE, '')} {_alle(bool(cijfers))}".strip()
    if (df[KOPPELSTATUS] == duo.alleen).any():
        extra[ALLEEN_DUO] = _alleen_duo(df, duo.alleen, sleutels)
        zin = f"{ALLEEN_DUO} noemt deze rijen met hun reden en hun aantal, in code: neem ze over en tel niet zelf."
        toelichting[duo.alleen] = zin
    if toelichting:
        extra["toelichting"] = toelichting
    return replace(uitkomst, df=df), extra


def _deel(reeks: pd.Series | None, masker: pd.Series) -> pd.Series | None:
    return None if reeks is None else reeks[masker]


def _alle(met_nse: bool) -> str:
    """De regel voor een vraag naar "alle opleidingen" van een instelling (#1274; besluit van de eigenaar: een tabel
    per graad, geen ongevraagde vernauwing). Kort: de tekst stuurt het model. Zonder NSE-cijfers geen zin over score
    of onzeker."""
    if not met_nse:
        return (
            "Vraagt de gebruiker naar alle opleidingen, toon dan één tabel per graad uit "
            f"{GEKOPPELD_PER_GRAAD}; daarna de rijen zonder match uit {PER_GRAAD} en {ALLEEN_DUO}, elk met hun reden. "
            "Vernauw de graad niet zonder dat de gebruiker erom vroeg (doe je een aanname, noem die dan vóór het "
            "getal). De aantallen per graad staan in die velden: neem ze over, tel niet zelf."
        )
    return (
        "Vraagt de gebruiker naar alle opleidingen, toon dan één tabel per graad: de rijen beide per graad uit "
        f"{GEKOPPELD_PER_GRAAD} (bachelor, associate degree, master) en een graad zonder DUO-rij maar met NSE-score "
        f"(met_score in {PER_GRAAD}, zoals master); daarna de rijen zonder match uit {PER_GRAAD} en {ALLEEN_DUO}, "
        "elk met hun reden. Een rij met onzeker: true staat erin met dat label: laat ze niet weg; vernauw de graad "
        "niet zonder dat de gebruiker erom vroeg (doe je een aanname, noem die dan vóór het getal). De aantallen per "
        "graad (rijen, met_score, onzeker) staan in die velden: neem ze over, tel niet zelf."
    )


def _samengevoegd(*extras: dict) -> dict:
    """De aanvullingen van de stappen na de koppeling samen: een toelichting per status en een waarschuwing aan elkaar
    geregen, de rest naast elkaar."""
    uit: dict = {}
    for extra in extras:
        for veld, waarde in extra.items():
            if veld == "toelichting":
                eerder = uit.setdefault("toelichting", {})
                for status, tekst in waarde.items():
                    eerder[status] = f"{eerder.get(status, '')} {tekst}".strip()
            elif veld == "waarschuwing" and uit.get(veld):
                uit[veld] = f"{uit[veld]} {waarde}"
            else:
                uit[veld] = waarde
    return uit


def _koppelkey(links: _Kant, rechts: _Kant) -> str:
    """Deterministisch: dezelfde twee tabellen, sleutels en kolommen geven dezelfde key.

    De hash gaat over de invoer, niet over het resultaat: dat kan veel groter zijn dan beide tabellen samen.
    """
    plan = json.dumps([links.key, links.kolommen, rechts.key, rechts.kolommen])
    inhoud = f"{plan}{links.df.to_json(orient='split', default_handler=str)}"
    inhoud += f"{rechts.df.to_json(orient='split', default_handler=str)}"
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
                "de gekoppelde tabel; bekijk de korrel met dataset_profiel. Hoort er één rij per "
                f"{', '.join(sleutels)} bij, aggregeer {kant.label} dan eerst met query_data naar die korrel "
                "(group_by op de sleutel, weighted_mean met een gewicht in weights voor scores en percentages, sum voor "
                "aantallen) en koppel die data_key."
            )
    for kant, n in uitkomst.zonder_sleutel.items():
        uit.append(f"{n} rijen van {kant} hebben een lege of onleesbare sleutel: ze staan erin zonder match.")
    if any(kern.SLEUTELS[s].op_naam for s in sleutels):
        uit.append(relaties.NAAMWAARSCHUWING)
    return uit


def _telling(df: pd.DataFrame) -> dict[str, int]:
    return {str(k): int(v) for k, v in df[KOPPELSTATUS].value_counts(sort=False).items()}


def _tekst(
    key: str, links: _Kant, rechts: _Kant, sleutels: list[str], uitkomst: _Uitkomst, volledig: bool, extra: dict
) -> str:
    df = uitkomst.df
    telling = _telling(df)
    # Alleen de rijen die het model ziet worden dicts; modelrijen krijgt het echte aantal apart.
    deel = df.head(rijmaximum(df.shape[1]))
    rijen = deel.astype(object).where(deel.notna(), None).to_dict(orient="records")
    uit: dict = {
        **(modelrijen(rijen, key, volledig, totaal=len(df)) if rijen else {"data_key": key, "rijen": []}),
        "sleutels": sleutels,
        "kolommen": {links.label: links.kolommen, rechts.label: rechts.kolommen},
        "korrel": {**uitkomst.korrel, "koppeling": uitkomst.koppeling},
        "kardinaliteit": uitkomst.kardinaliteit,
        "uniek": uitkomst.uniek,
        "telling": telling,
        "toelichting": _toelichting(links, rechts, sleutels, telling),
    }
    for status, aanvulling in extra.get("toelichting", {}).items():
        uit["toelichting"][status] = f"{uit['toelichting'].get(status, '')} {aanvulling}".strip()
    if opvolgers := extra.get("opvolgers"):
        uit["opvolgers"] = opvolgers
    for veld in (GEKOPPELD_PER_GRAAD, PER_GRAAD, ALLEEN_DUO):
        if waarde := extra.get(veld):
            uit[veld] = waarde
    if uitkomst.zonder_sleutel:
        uit["zonder_sleutel"] = uitkomst.zonder_sleutel
    waarschuwingen: list[str] = [w for w in (uit.pop("waarschuwing", None),) if isinstance(w, str)]
    waarschuwingen += _waarschuwingen(links, rechts, sleutels, uitkomst)
    waarschuwingen += [w for w in (extra.get("waarschuwing"),) if w]
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
        links, rechts = _kanten(
            store.canoniek(data_key), store.canoniek(andere_key), sleutels, kolommen_links, kolommen_rechts
        )
        namen = list(links.kolommen)  # de sleutels zoals _sleutelnamen ze las, in volgorde
        uitkomst = _koppel(links, rechts, namen)
    except _Melding as melding:
        return str(melding)
    uitkomst, opvolging = _opvolgers(links, rechts, namen, uitkomst)
    uitkomst, signalen = _skdb_signalen(links, rechts, namen, uitkomst)
    key = _koppelkey(links, rechts)
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
    return _tekst(key, links, rechts, namen, uitkomst, volledig, _samengevoegd(opvolging, signalen))
