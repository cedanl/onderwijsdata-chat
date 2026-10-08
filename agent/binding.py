"""Staat een getal bij het jaar en de instelling van zijn eigen rij? (#197, #212)

De getalcontrole (#185) vraagt of een getal ergens in de data staat, de
selectiecontroles (#187, #143) of het genoemde jaar en de genoemde instelling
ergens in de selectie zitten. Samen laten ze "2025/26 = 27.135" door als beide
jaren geselecteerd zijn, terwijl 27.135 bij 2024/25 hoort.

Hier moet een getal in een rij staan die past bij het jaar én de instelling die
dezelfde zin of tabelrij noemt. De index loopt per rij (jaar, instelling), niet
per as: anders komt "2024/25 + NHL Stenden + 55.555" door twee losse helften.
Noemt een zin meer waarden op één as (een vergelijking), dan is niet vast te
stellen welk getal waarbij hoort; de rij moet dan bij een van die waarden
passen. Een vergelijking in de tijd noemt vaak maar één jaar ("ten opzichte van
2020/21 gedaald van 518.940 naar 475.460", #379): staat een getal van de zin bij
het genoemde jaar, dan hoeven de andere alleen bij de genoemde instelling te
passen. Niet elke vergelijking zegt "van … naar": ook "komt uit van … en komt uit
op …" en "begon … eindigde" zijn er een (CH-01). Staat een getal in geen enkele rij (een som, een KPI), dan beslist de
getalcontrole erover, niet deze.

Een afgeleide waarde (#409) staat niet in een rij en kan toevallig gelijk zijn aan
een cel van een ander jaar: 478.660 - 475.460 = 3.200, terwijl 3.200 ook een cel
van 2021/22 is. Is het getal het verschil tussen twee genoemde jaren in dezelfde
kolom, of een compute_kpi-waarde over de genoemde jaren, dan hoort het daarbij.
Past het alleen niet bij het jaar, in een vergelijking waarvan elk genoemd jaar
al een eigen getal heeft, dan is het vermoedelijk afgeleid: twijfel, dus een
zacht probleem (#207) in plaats van een ingehouden antwoord.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations, product

import pandas as pd

from tools import instelling, periode, store
from tools.store import KeyMeta

from .grounding import checked_numbers
from .kpi_bron import bereik as kpi_bereik
from .kpi_bron import met_periode
from .probleem import Probleem, hard
from .selectie import data_keys

# Een zin die een verandering in de tijd beschrijft; het andere jaar staat er vaak niet bij (#379).
_VERGELIJKING = re.compile(
    r"\bvan\b.+\bnaar\b|ten opzichte van|t\.o\.v\.|vergeleken met|\beerder\b|vorig jaar"
    r"|\b(?:gedaald|daalde|gestegen|steeg|toegenomen|afgenomen)\b|\b(?:daling|stijging|groei|toename|afname)\b"
    # Zonder "van … naar": "komt uit van … en komt uit op …", "begon … eindigde", "verschil tussen" (CH-01).
    r"|\b(?:komt|kwam) uit (?:van|op)\b|\bbegon\b.+\beindigde\b|\bverschil tussen\b",
    re.IGNORECASE,
)

# Een zin of een tabelrij. Een punt in een getal (27.135) wordt niet gevolgd door witruimte.
_SEGMENT = re.compile(r"\n|(?<=[.!?;])\s+")

_Rij = tuple[int | None, str | None]  # (startjaar, instellingscode); None als de selectie die as mist
_Index = dict[str, set[_Rij]]  # getal (cijfers) → de dimensies van de rijen waarin het staat
# (selectie en kolom, instellingscode) → startjaar → de gehele waarden in die kolom
_Reeksen = dict[tuple[str, str | None], dict[int, set[int]]]


@dataclass
class _Data:
    index: _Index = field(default_factory=lambda: defaultdict(set))
    reeksen: _Reeksen = field(default_factory=lambda: defaultdict(lambda: defaultdict(set)))
    namen: dict[str, str] = field(default_factory=dict)
    kpis: list[tuple[str, set[int]]] = field(default_factory=list)  # (cijfers, startjaren van de periode)


def segmenten(tekst: str) -> list[str]:
    """De zinnen en tabelrijen van een tekst, zonder lege."""
    return [s for s in (s.strip() for s in _SEGMENT.split(tekst)) if s]


def _jaren(df: pd.DataFrame, known: KeyMeta) -> pd.Series | None:
    """Het startjaar per rij, uit de periodecode of, zonder code, uit haar label (#194)."""
    kolom = known.periodekolom
    if kolom and kolom in df.columns:
        return df[kolom].map(lambda v: periode.startjaar(known.bron, v))
    if kolom and (label := f"{kolom}_label") in df.columns:
        return df[label].map(lambda v: next(iter(periode.gevraagde_schooljaren(str(v))), None))
    return None


def _waarden(reeks: pd.Series | None, rijen: int) -> list:
    """De waarde per rij, None waar de as ontbreekt of de cel leeg is."""
    if reeks is None:
        return [None] * rijen
    return [None if pd.isna(v) else v for v in reeks]


def _index(key: str, df: pd.DataFrame, jaren: pd.Series | None, codes: pd.Series | None, data: _Data) -> None:
    getallen = df.select_dtypes("number")
    if getallen.columns.empty:
        # Alleen tekst (RIO, labels, '22410' als string): geen getal om te binden (#392).
        return
    per_rij = zip(
        _waarden(jaren, len(df)),
        _waarden(codes, len(df)),
        getallen.itertuples(index=False),
        strict=True,
    )
    for jaar, code, rij in per_rij:
        for kolom, v in zip(getallen.columns, rij, strict=True):
            if pd.notna(v) and float(v).is_integer():
                data.index[str(int(v))].add((jaar, code))
                if jaar is not None:
                    data.reeksen[(f"{key}:{kolom}", code)][jaar].add(int(v))


def _kpis(tool_results: list[str]) -> list[tuple[str, set[int]]]:
    """De gehele compute_kpi-waarden (cijfers) met de startjaren waarover ze rekenen."""
    kpis = []
    for kpi in met_periode(tool_results):
        waarde = str(kpi["value"]).lstrip("+-−").rstrip("%")
        if "," not in waarde and (jaren := kpi_bereik(kpi)):
            kpis.append((waarde.replace(".", ""), set(jaren)))
    return kpis


def _past(rij: _Rij, genoemd: tuple[set, set]) -> bool:
    """Past de rij bij wat de zin noemt? Een as die de zin niet noemt of de selectie mist, telt niet mee."""
    return all(not noemt or waarde is None or waarde in noemt for waarde, noemt in zip(rij, genoemd, strict=True))


def _label(rij: _Rij, genoemd: tuple[set, set], namen: dict[str, str]) -> str:
    """De rij als de lezer hem kent, alleen met de assen die de zin noemt."""
    jaar, code = rij
    delen = []
    if genoemd[0] and jaar is not None:
        delen.append(periode.label(jaar))
    if genoemd[1] and code is not None:
        delen.append(f"{namen.get(code, code)} ({code})")
    return " · ".join(delen)


def _vergelijkt(segment: str, getallen: list[tuple[str, str]], index: _Index, genoemd: tuple[set, set]) -> bool:
    """Beschrijft de zin een verandering vanaf één genoemd jaar, met een van zijn getallen bij dat jaar?

    Noemt de zin beide jaren, dan moet elk getal bij een van beide passen: dan is er niets te raden.
    """
    return bool(len(genoemd[0]) == 1 and _VERGELIJKING.search(segment)) and any(
        any(_past(rij, genoemd) for rij in index.get(getal, ())) for _, getal in getallen
    )


def _verschil(getal: str, genoemd: tuple[set, set], reeksen: _Reeksen) -> bool:
    """Is het getal het verschil tussen twee genoemde jaren in dezelfde kolom en instelling?"""
    n = int(getal)
    for (_, code), per_jaar in reeksen.items():
        if genoemd[1] and code is not None and code not in genoemd[1]:
            continue
        for a, b in combinations(sorted(genoemd[0] & per_jaar.keys()), 2):
            if any(x - n in per_jaar[b] or x + n in per_jaar[b] for x in per_jaar[a]):
                return True
    return False


def _afgeleid(getal: str, genoemd: tuple[set, set], data: _Data) -> bool:
    """Komt het getal uit de genoemde jaren zelf: hun verschil, of een KPI over precies die periode?"""
    kpi = any(cijfers == getal and jaren <= genoemd[0] for cijfers, jaren in data.kpis)
    return kpi or _verschil(getal, genoemd, data.reeksen)


def _twijfel(segment: str, getal: str, getallen: list[tuple[str, str]], data: _Data, genoemd: tuple[set, set]) -> bool:
    """Past het getal alleen niet bij het jaar, in een vergelijking waarvan elk genoemd jaar al een getal heeft?

    Dan is het vermoedelijk afgeleid (een afgerond verschil, een som) en toevallig gelijk aan een cel.
    """
    if not (genoemd[0] and _VERGELIJKING.search(segment)):
        return False
    if not any(_past(rij, (set(), genoemd[1])) for rij in data.index.get(getal, ())):
        return False
    anderen = [rij for _, ander in getallen if ander != getal for rij in data.index.get(ander, ())]
    return all(any(_past(rij, ({jaar}, genoemd[1])) for rij in anderen) for jaar in genoemd[0])


def _verkeerd(tekst: str, data: _Data, bekend: tuple[set, set]) -> list[Probleem]:
    problemen = []
    for segment in segmenten(tekst):
        genoemd = (
            periode.gevraagde_schooljaren(segment) & bekend[0],
            instelling.genoemde(segment, data.namen) & bekend[1],
        )
        if not any(genoemd):
            continue
        gevraagd = ", ".join(
            _label(r, genoemd, data.namen) for r in product(genoemd[0] or [None], genoemd[1] or [None])
        )
        getallen = checked_numbers(segment)
        # Het andere jaar van een vergelijking staat niet in de zin: dan telt alleen de instelling.
        eis = (set(), genoemd[1]) if _vergelijkt(segment, getallen, data.index, genoemd) else genoemd
        for geschreven, getal in getallen:
            rijen = data.index.get(getal)
            if not rijen or any(_past(rij, eis) for rij in rijen) or _afgeleid(getal, genoemd, data):
                continue
            echt = ", ".join(sorted({_label(r, genoemd, data.namen) for r in rijen}))
            opdracht = f"Neem het getal uit de rij van {gevraagd}."
            if _twijfel(segment, getal, getallen, data, genoemd):
                problemen.append(
                    Probleem(
                        f"{geschreven} staat in de data bij {echt}, niet bij {gevraagd} ('{segment}'); "
                        "als afgeleide waarde is het niet na te rekenen.",
                        f"{opdracht} Een verschil of som reken je uit met compute_kpi over die jaren.",
                    )
                )
            else:
                problemen += hard(
                    [Probleem(f"{geschreven} hoort bij {echt}, niet bij {gevraagd} ('{segment}').", opdracht)]
                )
    return problemen


def verkeerd_gebonden(tekst: str, tool_results: list[str]) -> list[Probleem]:
    """Getallen in de tekst die in de data bij een andere jaar-instellingcombinatie staan dan de zin noemt.

    Een zeker verkeerde binding is hard; een vermoedelijk afgeleide waarde zacht (#409).
    """
    data = _Data(kpis=_kpis(tool_results))
    for key in data_keys(tool_results):
        known, df = store.meta(key), store.get(key)
        if known is None or df is None:
            continue
        kolom = known.instellingskolom
        codes = None
        if kolom and kolom in df.columns and instelling.codekolom(df.columns):
            codes = df[kolom].astype(str)
            data.namen |= instelling.namen(df, kolom)
        _index(key, df, _jaren(df, known), codes, data)

    rijen = set().union(*data.index.values()) if data.index else set()
    bekend = ({j for j, _ in rijen if j is not None}, {c for _, c in rijen if c is not None})
    return _verkeerd(tekst, data, bekend)
