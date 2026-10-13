"""Wat er veranderde tussen bewaarde en verse Plotly-figuren, in gewone taal (#346).

Ververs haalt de data opnieuw op bij de bron; hier wordt de bewaarde grafiek
vergeleken met de verse en worden de gewijzigde waarden benoemd (een CBS-
herziening, een DUO-mutatie). Oud en nieuw horen bij elkaar via hun recept-id,
niet via hun positie in een lijst (#523). De vergelijking leest beide kanten via
plotly (pio.from_json); die laat binair gecodeerde reeksen (bdata) als dict staan,
maar de figuren van create_plot en de sandbox dragen gewone lijsten. De meldingen
zijn voor de gebruiker geschreven: data, geen instructies.
"""

import logging
from collections import Counter
from collections.abc import Mapping, Sequence

import plotly.io as pio

from tools.getal import nl_getal

logger = logging.getLogger(__name__)

MAX_MELDINGEN = 8
_DECIMALEN = 1  # de precisie van nl_getal voor niet-gehele waarden


def figuur_verschillen(oud: Mapping[str, str], nieuw: Mapping[str, str], volgorde: Sequence[str] = ()) -> list[str]:
    """De gewijzigde waarden tussen bewaarde en verse figuur-JSON, als meldingen.

    `oud` en `nieuw` gaan van recept-id naar figuur-JSON. Een id aan één kant geeft
    een eigen regel ("niet meer in het dashboard" / "nieuw"), nooit een vergelijking
    met een andere figuur. `volgorde` (alle recept-ids, in receptvolgorde) bepaalt de
    volgorde van de meldingen en de N van "Grafiek N"; zonder telt oud, dan nieuw.
    Leeg betekent: geen zichtbaar verschil. De lijst is begrensd op MAX_MELDINGEN;
    de rest wordt samengevat in een slotregel.
    """
    if dict(oud) == dict(nieuw):
        return []
    meldingen: list[str] = []
    for index, sleutel in enumerate(dict.fromkeys([*volgorde, *oud, *nieuw])):
        meldingen.extend(_sleutel_diff(index, oud.get(sleutel), nieuw.get(sleutel)))
    if len(meldingen) > MAX_MELDINGEN:
        rest = len(meldingen) - MAX_MELDINGEN
        meldingen = [*meldingen[:MAX_MELDINGEN], f"… en nog {rest} andere wijzigingen."]
    return meldingen


def _sleutel_diff(index: int, oud_json: str | None, nieuw_json: str | None) -> list[str]:
    if oud_json == nieuw_json:
        return []
    if oud_json is None:
        return [f"{_titel(nieuw_json, index)} is nieuw in het dashboard."]
    if nieuw_json is None:
        return [f"{_titel(oud_json, index)} staat niet meer in het dashboard."]
    return _figuur_diff(index, oud_json, nieuw_json)


def _titel(figuur_json: str | None, index: int) -> str:
    """De naam van een figuur die maar aan één kant staat: zijn titel, anders "Grafiek N"."""
    if figuur_json is None:
        return _naam(None, index)
    try:
        return _naam(pio.from_json(figuur_json, skip_invalid=True), index)
    except Exception:
        return _naam(None, index)


def _figuur_diff(index: int, oud_json: str, nieuw_json: str) -> list[str]:
    try:
        oud_fig = pio.from_json(oud_json, skip_invalid=True)
        nieuw_fig = pio.from_json(nieuw_json, skip_invalid=True)
    except Exception:
        logger.debug("Figuur %d is niet te vergelijken", index, exc_info=True)
        return [f"{_naam(None, index)} is gewijzigd."]

    titel = _naam(nieuw_fig, index)
    oud_reeksen = _reeksen(oud_fig)
    nieuw_reeksen = _reeksen(nieuw_fig)
    if len(oud_reeksen) != len(nieuw_reeksen):
        return [f"{titel}: het aantal reeksen veranderde van {len(oud_reeksen)} naar {len(nieuw_reeksen)}."]

    meldingen: list[str] = []
    for (_, oud), (naam, nieuw) in zip(oud_reeksen, nieuw_reeksen, strict=False):
        meldingen.extend(_reeks_diff(titel, naam, oud, nieuw))
    # Zonder meldingen zijn alleen de bytes anders (bv. opmaak), geen waarden: geen datawijziging.
    return meldingen


def _naam(fig, index: int) -> str:
    tekst = fig.layout.title.text if fig is not None and fig.layout.title else None
    return f"'{tekst}'" if tekst else f"Grafiek {index + 1}"


def _reeksen(fig) -> list[tuple[str | None, dict[str, object]]]:
    """Per reeks de naam en de waarden per categorie.

    Een staaf per reeks, elk genoemd naar zijn eigen categorie, is één reeks: zo tekende
    create_plot een uitgelichte staaf tot de grafieken één reeks met een kleur per staaf
    kregen. Een bewaarde grafiek in de oude vorm is na verversen niet "anders".
    """
    reeksen = [(getattr(trace, "name", None), _waarden(trace)) for trace in fig.data]
    if len(reeksen) > 1 and all(list(waarden) == [naam] for naam, waarden in reeksen):
        return [(None, {categorie: waarde for _, waarden in reeksen for categorie, waarde in waarden.items()})]
    return reeksen


def _reeks_diff(titel: str, naam: str | None, oud: dict[str, object], nieuw: dict[str, object]) -> list[str]:
    """Per categorie (x-waarde, taartlabel of heatmapcel) de gewijzigde waarde benoemen."""
    reeks = f", reeks '{naam}'" if naam else ""

    meldingen = [
        f"{titel}{reeks}, {cat}: {_getal(oud[cat])} → {_getal(nieuw[cat])}"
        for cat in oud
        if cat in nieuw and not _gelijk(oud[cat], nieuw[cat])
    ]
    erbij = [c for c in nieuw if c not in oud]
    weg = [c for c in oud if c not in nieuw]
    if erbij:
        meldingen.append(f"{titel}{reeks}: nieuw in de data: {', '.join(erbij[:3])}")
    if weg:
        meldingen.append(f"{titel}{reeks}: niet meer in de data: {', '.join(weg[:3])}")
    return meldingen


def _waarden(trace) -> dict[str, object]:
    """Categorie → waarde van een reeks: x/y voor staaf en lijn, labels/values voor taart, z voor een heatmap.

    Een categorie die vaker voorkomt, krijgt een volgnummer ("2024 (2e)") in plaats
    van de eerdere te overschrijven.
    """
    raster = _raster(getattr(trace, "z", None))
    return _uniek(_cellen(trace, raster) if raster is not None else _punten(trace))


def _punten(trace) -> list[tuple[str, object]]:
    categorieen = getattr(trace, "labels", None)
    waarden = getattr(trace, "values", None)
    if categorieen is None or waarden is None:
        # Liggende staven hebben de categorie op de y-as en de waarde op de x-as.
        liggend = getattr(trace, "orientation", None) == "h"
        categorieen = getattr(trace, "y" if liggend else "x", None)
        waarden = getattr(trace, "x" if liggend else "y", None)
    if categorieen is None or waarden is None:
        return []
    return [(str(c), w) for c, w in zip(_lijst(categorieen), _lijst(waarden), strict=False)]


def _raster(z) -> list[list] | None:
    """De rijen van een tweedimensionale z (heatmap); None zonder z of als z geen raster is."""
    if z is None:
        return None
    rijen = _lijst(z)
    if not all(isinstance(rij, (list, tuple)) for rij in rijen):
        return None
    return [list(rij) for rij in rijen]


def _cellen(trace, raster: list[list]) -> list[tuple[str, object]]:
    """Per heatmapcel "rij …, kolom …" en de waarde: labels uit y en x, zonder labels de positie."""
    rijen = _labels(getattr(trace, "y", None))
    kolommen = _labels(getattr(trace, "x", None))
    return [
        (f"rij {_label(rijen, i)}, kolom {_label(kolommen, j)}", waarde)
        for i, rij in enumerate(raster)
        for j, waarde in enumerate(rij)
    ]


def _labels(as_) -> list:
    return _lijst(as_) if as_ is not None else []


def _label(labels: list, index: int) -> str:
    return str(labels[index]) if index < len(labels) else str(index + 1)


def _uniek(paren: list[tuple[str, object]]) -> dict[str, object]:
    gezien: Counter[str] = Counter()
    waarden: dict[str, object] = {}
    for categorie, waarde in paren:
        gezien[categorie] += 1
        waarden[categorie if gezien[categorie] == 1 else f"{categorie} ({gezien[categorie]}e)"] = waarde
    return waarden


def _lijst(reeks) -> list:
    return reeks.tolist() if hasattr(reeks, "tolist") else list(reeks)


def _gelijk(a, b) -> bool:
    """Gelijk zoals de gebruiker het ziet: getallen op de ene decimaal die nl_getal toont.

    Een exacte float-vergelijking meldde 0,3 → 0,3 bij ruis als 0.30000000000000004.
    """
    try:
        return round(float(a), _DECIMALEN) == round(float(b), _DECIMALEN)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _getal(waarde) -> str:
    try:
        return nl_getal(float(waarde))
    except (TypeError, ValueError):
        return str(waarde)
