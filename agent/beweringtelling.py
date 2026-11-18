"""Een telling of vergelijking in de verhaallijn moet kloppen met de tabel eronder (#1013).

Foutklasse (reaudit 10-11, C01, N07 en M01): de getallen in het antwoord staan in de data en de tabel klopt, maar de
zin erboven niet. "10 van de 12 hogescholen is gedaald" bij een tabel met 9 dalers, of "In 2023/24 en 2024/25 waren
er meer bachelor- dan wo-masterdiploma's" terwijl de tabel in beide jaren meer wo-masterdiploma's heeft. De
getalcontrole ziet dat niet: 10 en 12 hebben geen vier cijfers, en een vergelijking heeft geen getal.

Deze controle leest precies twee zinsvormen en rekent ze na tegen één eenduidige tabel:

1. Telling: "N van de M <eenheden> <werkwoord>", met N en M als cijfer of als telwoord (twee tot twintig) en een
   werkwoord van `_OMLAAG` of `_OMHOOG`, eventueel na is/zijn/was/waren. Per rij telt het teken van de verschilkolom
   (kop met verschil, groei, mutatie, ontwikkeling, toe-/afname, delta), of het latere min het eerdere jaar van
   precies twee jaarkolommen; nul is noch dalen noch stijgen. M moet gelijk zijn aan het aantal rijen met een waarde,
   zonder totaalrij (Totaal, Landelijk, Gemiddelde) of, als M daar beter bij past, met.
2. Vergelijking: "meer/minder <A> dan <B>" met een of meer schooljaren in dezelfde zin. A en B wijzen elk precies één
   kolomkop aan (de jaren staan dan in de rijlabels) of precies één rijlabel (de jaren staan dan in de kolomkoppen).
   Fout is de zin alleen als hij in elk genoemd jaar niet klopt.

De tabel is een markdowntabel in hetzelfde antwoord, of, als geen enkele tabel past, de data van een afgeleide key van
de beurt met dezelfde kolommen. Streng en stil: meer dan één passende tabel of key, een kolom of label dat niet
eenduidig te vinden is, een M die bij geen rijtelling past, een jaar dat de tabel niet heeft, een ontkenning, een
vraag, een benadering ("bijna 10 van de 12") of een andere formulering ("de meeste", "bijna alle") geeft geen
melding. Een telwoord "een/één" telt niet: "een van de 12 hogescholen" betekent vaak "een van hen", niet "precies één".

Zacht, met herkansing: een herkenningsfout mag een goed antwoord niet intrekken. Alleen een telling tegen de tabel in
het antwoord, waarvan M gelijk is aan het aantal rijen met een waarde zonder totaalrij, is hard: die blijft na de
herkansing staan als bewering die de gebruiker zelf in de tabel kan natellen.

Eigenaar: `agent/`, naast de rekensomcontrole (`agent/rekensom.py`) en de tabelbinding (`agent/tabelbinding.py`).
Heroverwegen als de controle een kwartaal lang niet afgaat in de logregel CONTROLES.
"""

import math
import numbers
import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd

from tools import periode, store

from .beschermd import BESCHERMD, lopende_regels
from .mdtabel import Tabel, tabellen
from .probleem import Probleem, hard
from .selectie import data_keys

_TELWOORDEN = {
    "twee": 2,
    "drie": 3,
    "vier": 4,
    "vijf": 5,
    "zes": 6,
    "zeven": 7,
    "acht": 8,
    "negen": 9,
    "tien": 10,
    "elf": 11,
    "twaalf": 12,
    "dertien": 13,
    "veertien": 14,
    "vijftien": 15,
    "zestien": 16,
    "zeventien": 17,
    "achttien": 18,
    "negentien": 19,
    "twintig": 20,
}
_AANTAL = rf"\d+|{'|'.join(_TELWOORDEN)}"
_OMLAAG = ("gedaald", "daalde", "daalden", "gekrompen", "kromp", "krompen", "kromen", "afgenomen", "nam af", "namen af")
_OMHOOG = ("gestegen", "steeg", "stegen", "gegroeid", "groeide", "groeiden", "toegenomen", "nam toe", "namen toe")
_WERKWOORD = "|".join(w.replace(" ", r"\s+") for w in _OMLAAG + _OMHOOG)
_TERM = r"[^\W\d_][\w'’-]*"
_TELLING = re.compile(
    rf"(?<![\w.,])(?P<n>{_AANTAL})\s+van\s+de\s+(?P<m>{_AANTAL})\s+(?P<eenheid>{_TERM})\s+"
    rf"(?:(?:is|zijn|was|waren)\s+)?(?P<werkwoord>{_WERKWOORD})(?![\w-])",
    re.IGNORECASE,
)
_VERGELIJKING = re.compile(rf"\b(?P<richting>meer|minder)\s+(?P<a>{_TERM})\s+dan\s+(?P<b>{_TERM})", re.IGNORECASE)

# Wat een zin tot iets anders maakt dan een stellige bewering over de tabel.
_ONTKENNING = re.compile(r"\b(?:niet|geen|nooit)\b|\?", re.IGNORECASE)
_BENADERING = re.compile(
    r"(?:\b(?:bijna|ongeveer|circa|ca\.|zo'n|ruim|minstens|tenminste|ten\s+minste|hooguit|maximaal|minimaal|"
    r"meer\s+dan|minder\s+dan)|≈)\s*$",
    re.IGNORECASE,
)
_OF_ANDERS = re.compile(r"^\s*(?:,\s*)?(?:of|en/of)\b", re.IGNORECASE)
# Een vergelijking van groei is geen vergelijking van niveaus: "in 2024/25 groeiden meer bachelor- dan ...".
_VERANDERING = re.compile(
    r"\b(?:gestegen|steeg|stegen|stijging\w*|gegroeid|groei\w*|gedaald|daal\w*|daling\w*|toegenomen|toename\w*|"
    r"afgenomen|afname\w*|gekrompen|kromp\w*)\b",
    re.IGNORECASE,
)
_ZIN = re.compile(r"(?<=[.!?])\s+|\n+")

_VERSCHILKOP = re.compile(
    r"verschil|groei|mutatie|ontwikkeling|verandering|toe-?\s*/\s*afname|toename|afname|delta|Δ", re.IGNORECASE
)
_TOTAALRIJ = re.compile(r"^(?:totaal|landelijk|gemiddeld|gemiddelde|nederland)\b", re.IGNORECASE)
_GETAL = re.compile(r"^(?P<teken>[+\-−–]?)\s*(?P<geheel>\d{1,3}(?:\.\d{3})+|\d+)(?:,(?P<decimalen>\d+))?\s*(?:%|pp)?$")
_OPMAAK = " \t*_`\u00a0\u202f"
_MAX_RIJEN = 500
# Woorden na "meer"/"minder" of "dan" die geen soort aanwijzen: "meer studenten dan in 2023/24", "dan vorig jaar".
_GEEN_TERM = frozenset(
    {"in", "op", "bij", "van", "voor", "na", "de", "het", "een", "er", "dat", "die", "toen", "vorig", "vorige", "ooit"}
)
_MIN_VOORVOEGSEL = 3


@dataclass(frozen=True)
class _Cel:
    tekst: str  # zoals de lezer haar ziet
    getal: Decimal | None  # None: leeg of geen getal ("-", "n.v.t.", "*", een label)


@dataclass(frozen=True)
class _Raster:
    """Een tabel uit het antwoord of de data van een key, als kop en rijen met cellen."""

    kop: tuple[str, ...]
    rijen: tuple[tuple[_Cel, ...], ...]
    in_antwoord: bool  # een tabel die de gebruiker ziet (True) of de data van een key (False)


@dataclass(frozen=True)
class _Uitkomst:
    dalers: int
    stijgers: int
    met_totaal: bool  # M past alleen met de totaalrij erbij


def _getal(tekst: str) -> Decimal | None:
    """Een getal in Nederlandse notatie, met teken en eventueel procent: -3,2% (ook met het minteken U+2212) of
    +1.250; anders None."""
    if not (m := _GETAL.match(tekst.strip(_OPMAAK))):
        return None
    waarde = Decimal(m["geheel"].replace(".", "") + (f".{m['decimalen']}" if m["decimalen"] else ""))
    return -waarde if m["teken"] and m["teken"] != "+" else waarde


def _nl(getal: Decimal) -> str:
    if getal == getal.to_integral_value():
        return f"{int(getal):,}".replace(",", ".")
    return f"{getal:,f}".translate(str.maketrans(",.", ".,"))


def _datacel(waarde) -> _Cel:
    """Een cel van een DataFrame: een getal als Decimal, NaN als lege cel, tekst zoals in een markdowntabel."""
    if isinstance(waarde, numbers.Real) and not isinstance(waarde, bool):
        try:
            getal = Decimal(str(waarde))
        except InvalidOperation:
            return _Cel(str(waarde), None)
        if getal.is_nan():
            return _Cel("", None)
        return _Cel(_nl(getal), getal) if getal.is_finite() else _Cel(str(waarde), None)
    tekst = "" if waarde is None else str(waarde)
    return _Cel(tekst, _getal(tekst))


def _cel(rij: tuple[_Cel, ...], kolom: int) -> _Cel:
    return rij[kolom] if kolom < len(rij) else _Cel("", None)


def _labels(rij: tuple[_Cel, ...]) -> list[str]:
    """De cellen van een rij die geen getal zijn maar wel iets noemen: de instelling, het schooljaar, de soort."""
    return [c.tekst for c in rij if c.getal is None and re.search(r"\w", c.tekst)]


def _totaalrij(rij: tuple[_Cel, ...]) -> bool:
    return any(_TOTAALRIJ.match(label.strip(_OPMAAK)) for label in _labels(rij))


def _kopjaar(kop: str) -> int | None:
    """Het schooljaar van een kolomkop die er precies één noemt (2024/25, 2024/'25, 2024SJ00, 'Instroom 2024/25')."""
    if (jaar := periode.startjaar_van_spelling(kop)) is not None:
        return jaar
    jaren = periode.gevraagde_schooljaren(kop)
    return next(iter(jaren)) if len(jaren) == 1 else None


# --- De tabellen ---------------------------------------------------------------------------------------------------


def _uit_antwoord(gevonden: list[Tabel]) -> list[_Raster]:
    return [
        _Raster(tabel.kop, tuple(tuple(_Cel(c, _getal(c)) for c in rij) for rij in tabel.rijen), True)
        for tabel in gevonden
    ]


def _uit_keys(tool_results: list[str]) -> list[_Raster]:
    """De data van de afgeleide keys van de beurt, als raster: alleen als het antwoord geen passende tabel heeft."""
    rasters = []
    for key in dict.fromkeys(data_keys(tool_results)):
        known = store.meta(key)
        if known is None or known.afgeleid_van is None:
            continue
        df = store.get(key)
        if not isinstance(df, pd.DataFrame) or df.empty or len(df) > _MAX_RIJEN:
            continue
        kop = tuple(str(k) for k in df.columns)
        rijen = tuple(tuple(_datacel(v) for v in rij) for rij in df.itertuples(index=False, name=None))
        rasters.append(_Raster(kop, rijen, False))
    return rasters


class _Sleutels:
    """De rasters van de keys, pas opgehaald als een bewering geen passende tabel in het antwoord heeft."""

    def __init__(self, tool_results: list[str]):
        self._tool_results = tool_results
        self._rasters: list[_Raster] | None = None

    def __call__(self) -> list[_Raster]:
        if self._rasters is None:
            self._rasters = _uit_keys(self._tool_results)
        return self._rasters


# --- Telling -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Telling:
    fragment: str
    n: int
    m: int
    omlaag: bool
    jaren: frozenset[int]


def _aantal(woord: str) -> int:
    return int(woord) if woord.isdigit() else _TELWOORDEN[woord.lower()]


def _tellingen(zin: str) -> list[_Telling]:
    if _ONTKENNING.search(zin):
        return []
    gevonden = []
    for m in _TELLING.finditer(zin):
        if _BENADERING.search(zin[: m.start()]) or _OF_ANDERS.match(zin[m.end() :]):
            continue
        n, totaal = _aantal(m["n"]), _aantal(m["m"])
        if n > totaal or totaal < 2:
            continue
        omlaag = re.sub(r"\s+", " ", m["werkwoord"].lower()) in _OMLAAG
        jaren = frozenset(periode.gevraagde_schooljaren(zin))
        gevonden.append(_Telling(m.group(0), n, totaal, omlaag, jaren))
    return gevonden


def _waardebronnen(raster: _Raster) -> list[tuple[list[Decimal | None], frozenset[int]]]:
    """Per bron van een richting de waarde per rij en de schooljaren die de bron noemt: elke verschilkolom, en het
    verschil van precies twee jaarkolommen."""
    verschil = [i for i, kop in enumerate(raster.kop) if _VERSCHILKOP.search(kop)]
    bronnen = [
        ([_cel(rij, i).getal for rij in raster.rijen], frozenset(periode.gevraagde_schooljaren(raster.kop[i])))
        for i in verschil
    ]
    jaarkolommen = {i: jaar for i, kop in enumerate(raster.kop) if i not in verschil and (jaar := _kopjaar(kop))}
    if len(jaarkolommen) == 2 and len(set(jaarkolommen.values())) == 2:
        eerder, later = sorted(jaarkolommen, key=jaarkolommen.__getitem__)
        waarden = []
        for rij in raster.rijen:
            a, b = _cel(rij, eerder).getal, _cel(rij, later).getal
            waarden.append(None if a is None or b is None else b - a)
        bronnen.append((waarden, frozenset(jaarkolommen.values())))
    return bronnen


def _uitkomst(waarden: list[Decimal | None], raster: _Raster, m: int) -> _Uitkomst | None:
    """Dalers en stijgers op de rijen met een waarde, als M het aantal van die rijen is (zonder of met totaalrij)."""
    met = [(w, _totaalrij(rij)) for w, rij in zip(waarden, raster.rijen, strict=True) if w is not None]
    zonder = [w for w, totaal in met if not totaal]
    if m == len(zonder):
        gekozen, met_totaal = zonder, False
    elif m == len(met):
        gekozen, met_totaal = [w for w, _ in met], True
    else:
        return None
    return _Uitkomst(sum(w < 0 for w in gekozen), sum(w > 0 for w in gekozen), met_totaal)


def _telling_in(raster: _Raster, telling: _Telling) -> tuple[bool, _Uitkomst | None]:
    """Past de tabel bij de telling, en zo ja met welke uitkomst? None als haar bronnen elkaar tegenspreken."""
    bronnen = _waardebronnen(raster)
    genoemd = frozenset().union(*(jaren for _, jaren in bronnen)) if bronnen else frozenset()
    if not bronnen or (telling.jaren and genoemd and not telling.jaren <= genoemd):
        return False, None
    uitkomsten = [_uitkomst(waarden, raster, telling.m) for waarden, _ in bronnen]
    if all(u is None for u in uitkomsten):
        return False, None
    return True, uitkomsten[0] if len(set(uitkomsten)) == 1 else None


def _telprobleem(telling: _Telling, raster: _Raster, uitkomst: _Uitkomst) -> list[Probleem]:
    juist = uitkomst.dalers if telling.omlaag else uitkomst.stijgers
    if juist == telling.n:
        return []
    waar = "in de tabel" if raster.in_antwoord else "in de opgehaalde data"
    fragment = telling.fragment[0].upper() + telling.fragment[1:]
    probleem = Probleem(
        f"{fragment}, maar {waar} zijn het er {juist} van de {telling.m}.",
        "Tel de rijen na in de tabel en noem het aantal dat erin staat, of laat de telling weg.",
    )
    if raster.in_antwoord and not uitkomst.met_totaal:
        return hard([probleem])
    return [probleem]


def _telfout(telling: _Telling, rasters: list[_Raster], sleutels: _Sleutels) -> list[Probleem]:
    for kandidaten in (rasters, sleutels()):
        passend = [(r, uitkomst) for r in kandidaten for past, uitkomst in [_telling_in(r, telling)] if past]
        if passend:
            if len(passend) > 1 or (uitkomst := passend[0][1]) is None:
                return []
            return _telprobleem(telling, passend[0][0], uitkomst)
    return []


# --- Vergelijking --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Vergelijking:
    fragment: str
    meer: bool
    a: str
    b: str
    jaren: frozenset[int]


def _vergelijkingen(zin: str) -> list[_Vergelijking]:
    if _ONTKENNING.search(zin) or _VERANDERING.search(zin):
        return []
    if not (jaren := frozenset(periode.gevraagde_schooljaren(zin))):
        return []
    gevonden = list(_VERGELIJKING.finditer(zin))
    if len(gevonden) != 1:
        return []
    m = gevonden[0]
    return [_Vergelijking(m.group(0), m["richting"].lower() == "meer", m["a"], m["b"], jaren)]


def _norm(tekst: str) -> str:
    return tekst.strip(_OPMAAK).lower().replace("’", "'").rstrip("-")


def _kies(term: str, labels: Sequence[str]) -> int | None:
    """De index van het label dat de term eenduidig aanwijst: gelijk, of het een begint met het ander, met een
    voorvoegsel van minstens drie tekens ("wo-masterdiploma's" en "Wo-master", "bachelor-" en "Bachelor"); bij gelijke
    stand geen."""
    t = _norm(term)
    if len(t) < 2 or t in _GEEN_TERM:
        return None
    scores = {}
    for i, label in enumerate(labels):
        if len(lab := _norm(label)) < 2:
            continue
        if t == lab:
            scores[i] = math.inf
        elif min(len(t), len(lab)) >= _MIN_VOORVOEGSEL and (t.startswith(lab) or lab.startswith(t)):
            scores[i] = min(len(t), len(lab))
    if not scores:
        return None
    beste = max(scores.values())
    winnaars = [i for i, s in scores.items() if s == beste]
    return winnaars[0] if len(winnaars) == 1 else None


_Paar = tuple[int, _Cel, _Cel]  # schooljaar, cel van A, cel van B


@dataclass(frozen=True)
class _Jaarpaar:
    jaar: int
    a: Decimal
    b: Decimal
    tekst_a: str
    tekst_b: str


@dataclass(frozen=True)
class _Aangewezen:
    paren: list[_Jaarpaar]
    label_a: str
    label_b: str


def _in_kolommen(raster: _Raster, v: _Vergelijking) -> tuple[list[_Paar], str, str] | None:
    """A en B als kolomkoppen, de schooljaren in de rijlabels."""
    ka, kb = _kies(v.a, raster.kop), _kies(v.b, raster.kop)
    if ka is None or kb is None or ka == kb:
        return None
    per_jaar: dict[int, list[tuple[_Cel, ...]]] = {}
    for rij in raster.rijen:
        jaren = set().union(*(periode.gevraagde_schooljaren(label) for label in _labels(rij)))
        if len(jaren) == 1:
            per_jaar.setdefault(jaren.pop(), []).append(rij)
    paren = []
    for jaar in sorted(v.jaren):
        if len(rijen := per_jaar.get(jaar, [])) != 1:
            return None
        paren.append((jaar, _cel(rijen[0], ka), _cel(rijen[0], kb)))
    return paren, raster.kop[ka], raster.kop[kb]


def _in_rijen(raster: _Raster, v: _Vergelijking) -> tuple[list[_Paar], str, str] | None:
    """A en B als rijlabels (de eerste cel van de rij), de schooljaren in de kolomkoppen."""
    rijlabels = [rij[0].tekst if rij and rij[0].getal is None else "" for rij in raster.rijen]
    ra, rb = _kies(v.a, rijlabels), _kies(v.b, rijlabels)
    if ra is None or rb is None or ra == rb:
        return None
    per_jaar: dict[int, list[int]] = {}
    for i, kop in enumerate(raster.kop):
        if (jaar := _kopjaar(kop)) is not None:
            per_jaar.setdefault(jaar, []).append(i)
    paren = []
    for jaar in sorted(v.jaren):
        if len(kolommen := per_jaar.get(jaar, [])) != 1:
            return None
        paren.append((jaar, _cel(raster.rijen[ra], kolommen[0]), _cel(raster.rijen[rb], kolommen[0])))
    return paren, rijlabels[ra], rijlabels[rb]


def _vergelijking_in(raster: _Raster, v: _Vergelijking) -> _Aangewezen | None:
    """De waarden van A en B per genoemd jaar, als de tabel ze in precies één richting eenduidig aanwijst."""
    gevonden = [p for p in (_in_kolommen(raster, v), _in_rijen(raster, v)) if p is not None]
    if len(gevonden) != 1:
        return None
    paren, label_a, label_b = gevonden[0]
    waarden = [
        _Jaarpaar(jaar, a.getal, b.getal, a.tekst, b.tekst)
        for jaar, a, b in paren
        if a.getal is not None and b.getal is not None
    ]
    return _Aangewezen(waarden, label_a, label_b) if len(waarden) == len(paren) else None


def _vergelijkfout(v: _Vergelijking, rasters: list[_Raster], sleutels: _Sleutels) -> list[Probleem]:
    for kandidaten in (rasters, sleutels()):
        passend = [(r, p) for r in kandidaten if (p := _vergelijking_in(r, v)) is not None]
        if not passend:
            continue
        if len(passend) > 1:
            return []
        raster, aangewezen = passend[0]
        if any((p.a > p.b) if v.meer else (p.a < p.b) for p in aangewezen.paren):
            return []
        waar = "in de tabel" if raster.in_antwoord else "in de opgehaalde data"
        per_jaar = "; ".join(
            f"in {periode.label(p.jaar)} {aangewezen.label_a} {p.tekst_a} en {aangewezen.label_b} {p.tekst_b}"
            for p in aangewezen.paren
        )
        jaren = " en ".join(periode.labels(sorted(v.jaren)))
        return [
            Probleem(
                f"Het antwoord zegt '{v.fragment}' voor {jaren}, maar {waar} staat {per_jaar}.",
                "Vergelijk de twee waarden per schooljaar in de tabel en schrijf de vergelijking zoals de data haar "
                "geeft, of laat haar weg.",
            )
        ]
    return []


# --- De controle ---------------------------------------------------------------------------------------------------


def _zinnen(regels: list[str], rasterregels: set[int]) -> list[str]:
    """De zinnen van de lopende tekst: niet in een codeblok, niet in een tabel, zonder inline code en links."""
    lopend = [
        BESCHERMD.sub(" ", regel).replace("*", "")
        for i, (regel, isloop) in enumerate(lopende_regels(regels))
        if isloop and i not in rasterregels
    ]
    return [z.strip() for z in _ZIN.split("\n".join(lopend)) if z.strip()]


def _fouten(tekst: str, sleutels: _Sleutels) -> list[Probleem]:
    regels = tekst.split("\n")
    gevonden = tabellen(regels)
    rasters = _uit_antwoord(gevonden)
    rasterregels = {i for t in gevonden for i in range(t.begin, t.einde + 1)}
    problemen: list[Probleem] = []
    for zin in _zinnen(regels, rasterregels):
        for telling in _tellingen(zin):
            problemen += _telfout(telling, rasters, sleutels)
        for vergelijking in _vergelijkingen(zin):
            problemen += _vergelijkfout(vergelijking, rasters, sleutels)
    return problemen


def onjuiste_tabelbeweringen(lezingen: Sequence[str], tool_results: list[str]) -> list[Probleem]:
    """Elke telling ("10 van de 12 hogescholen is gedaald") en vergelijking ("meer bachelor- dan wo-masterdiploma's
    in 2024/25") in de lopende tekst die niet klopt met de ene tabel waarop ze rust.

    `lezingen`: het antwoord zoals de gebruiker het leest, in elke notatie die de controle moet toetsen
    (agent/controles.lezingen). Een bewering is alleen fout als ze in elke lezing fout is.
    """
    if not lezingen:
        return []
    sleutels = _Sleutels(tool_results)
    problemen = _fouten(lezingen[0], sleutels)
    for lezing in lezingen[1:]:
        ook = set(_fouten(lezing, sleutels))
        problemen = [p for p in problemen if p in ook]
    return list(dict.fromkeys(problemen))
